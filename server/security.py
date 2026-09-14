import hashlib
import hmac
import secrets
from datetime import datetime, timezone
from functools import wraps

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError
from flask import (
    abort,
    jsonify,
    redirect,
    request,
    session,
    url_for,
)


# ============================================================
# CONFIGURATION
# ============================================================

PASSWORD_HASHER = PasswordHasher()

CLIENT_TOKEN_BYTES = 32
CSRF_TOKEN_BYTES = 32

SESSION_USER_KEY = "user_id"
SESSION_USERNAME_KEY = "username"
SESSION_CSRF_KEY = "csrf_token"

SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


# ============================================================
# TIME
# ============================================================

def utc_now():
    return datetime.now(timezone.utc).isoformat()


# ============================================================
# PASSWORDS
# ============================================================

def hash_password(password):
    return PASSWORD_HASHER.hash(password)


def verify_password(password_hash, password):
    try:
        return PASSWORD_HASHER.verify(password_hash, password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def password_needs_rehash(password_hash):
    try:
        return PASSWORD_HASHER.check_needs_rehash(password_hash)
    except (InvalidHashError, VerificationError):
        return False


# ============================================================
# RANDOM TOKENS
# ============================================================

def generate_client_token():
    return secrets.token_urlsafe(CLIENT_TOKEN_BYTES)


def hash_client_token(token):
    return hashlib.sha256(
        token.encode("utf-8")
    ).hexdigest()


def verify_client_token(token, token_hash):
    if not token or not token_hash:
        return False

    calculated = hash_client_token(token)

    return hmac.compare_digest(
        calculated,
        token_hash
    )


# ============================================================
# CSRF
# ============================================================

def get_csrf_token():
    token = session.get(SESSION_CSRF_KEY)

    if not token:
        token = secrets.token_urlsafe(CSRF_TOKEN_BYTES)
        session[SESSION_CSRF_KEY] = token
        session.modified = True

    return token


def validate_csrf():
    if request.method in SAFE_METHODS:
        return True

    if request.path == "/login":
        return True

    supplied_token = (
        request.headers.get("X-CSRF-Token")
        or request.form.get("csrf_token")
    )

    session_token = session.get(SESSION_CSRF_KEY)

    if not supplied_token or not session_token:
        return False

    return hmac.compare_digest(
        supplied_token,
        session_token
    )


# ============================================================
# SESSION
# ============================================================

def configure_session(app):
    app.config.update(
        SESSION_COOKIE_NAME="lums_session",
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SECURE=True,
        SESSION_COOKIE_SAMESITE="Strict",
        SESSION_COOKIE_PATH="/",
        PERMANENT_SESSION_LIFETIME=1800,
        SESSION_REFRESH_EACH_REQUEST=True,
    )


def login_user(user_id, username):
    session.clear()

    session[SESSION_USER_KEY] = int(user_id)
    session[SESSION_USERNAME_KEY] = username
    session[SESSION_CSRF_KEY] = secrets.token_urlsafe(
        CSRF_TOKEN_BYTES
    )

    session.permanent = True
    session.modified = True


def logout_user():
    session.clear()


def find_user(connection, username):
    return connection.execute(
        """
        SELECT id, username, password_hash, enabled
        FROM users
        WHERE username = ?
        """,
        (username,),
    ).fetchone()


def current_user_id():
    return session.get(SESSION_USER_KEY)


def current_username():
    return session.get(SESSION_USERNAME_KEY)


def is_authenticated():
    return current_user_id() is not None


# ============================================================
# AUTHORIZATION DECORATORS
# ============================================================

def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):

        if not is_authenticated():

            if request.path.startswith("/api/"):
                return jsonify({
                    "error": "authentication_required"
                }), 401

            return redirect(
                url_for("login")
            )

        return view(*args, **kwargs)

    return wrapped


def csrf_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):

        if not validate_csrf():
            return jsonify({
                "error": "csrf_validation_failed"
            }), 400

        return view(*args, **kwargs)

    return wrapped


# ============================================================
# CLIENT AUTHENTICATION
# ============================================================

def get_bearer_token():
    authorization = request.headers.get(
        "Authorization",
        ""
    )

    scheme, separator, token = authorization.partition(" ")

    if not separator:
        return None

    if scheme.lower() != "bearer":
        return None

    token = token.strip()

    if not token:
        return None

    return token


def authenticate_client(connection):
    token = get_bearer_token()

    if not token:
        return None

    token_hash = hash_client_token(token)

    row = connection.execute(
        """
        SELECT
            id,
            hostname,
            enabled,
            client_token_hash,
            token_revoked_at
        FROM clients
        WHERE client_token_hash = ?
        """,
        (token_hash,)
    ).fetchone()

    if row is None:
        return None

    if not row["enabled"]:
        return None

    if row["token_revoked_at"] is not None:
        return None

    return row


def client_auth_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):

        connection = None

        try:
            from flask import current_app

            connection = current_app.config[
                "LUMS_GET_CONNECTION"
            ]()

            client = authenticate_client(
                connection
            )

            if client is None:
                return jsonify({
                    "error": "client_authentication_required"
                }), 401

            request.environ["lums.client"] = client

            return view(*args, **kwargs)

        finally:
            if connection is not None:
                connection.close()

    return wrapped


def authenticated_client():
    return request.environ.get(
        "lums.client"
    )


# ============================================================
# AUDIT LOGGING
# ============================================================

def audit_log(
    connection,
    actor_type,
    actor_id,
    action,
    target=None,
    result="success",
    details=None,
):
    connection.execute(
        """
        INSERT INTO audit_log (
            timestamp,
            actor_type,
            actor_id,
            action,
            target,
            result,
            details
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            utc_now(),
            actor_type,
            str(actor_id) if actor_id is not None else None,
            action,
            target,
            result,
            details,
        )
    )


# ============================================================
# SECURITY HEADERS
# ============================================================

def apply_security_headers(response):
    response.headers.setdefault(
        "X-Content-Type-Options",
        "nosniff"
    )

    response.headers.setdefault(
        "X-Frame-Options",
        "DENY"
    )

    response.headers.setdefault(
        "Referrer-Policy",
        "no-referrer"
    )

    response.headers.setdefault(
        "Permissions-Policy",
        "camera=(), microphone=(), geolocation=(), payment=()"
    )

    response.headers.setdefault(
        "Content-Security-Policy",
        (
            "default-src 'self'; "
            "script-src 'self'; "
            "style-src 'self'; "
            "img-src 'self' data:; "
            "font-src 'self'; "
            "connect-src 'self'; "
            "object-src 'none'; "
            "base-uri 'self'; "
            "frame-ancestors 'none'; "
            "form-action 'self'"
        )
    )

    return response
