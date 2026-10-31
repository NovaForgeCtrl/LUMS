import hashlib
import hmac
import secrets
from datetime import datetime, timezone, timedelta
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

ROLE_ADMINISTRATOR = "administrator"
ROLE_OPERATOR = "operator"
ROLE_VIEWER = "viewer"

VALID_ROLES = {
    ROLE_ADMINISTRATOR,
    ROLE_OPERATOR,
    ROLE_VIEWER,
}

PERMISSIONS = {
    "clients.view": "Clients und Systeminformationen ansehen",
    "software.view": "Installierte Software ansehen",
    "updates.view": "Updates, Jobs und Verlauf ansehen",
    "packages.search": "Pakete suchen",
    "jobs.manage": "Paketänderungen und Update-Jobs anlegen",
    "clients.manage": "Clients registrieren, entfernen und Tokens rotieren",
    "users.manage": "Benutzerkonten verwalten",
    "permissions.manage": "Berechtigungen zuweisen und ändern",
    "backups.manage": "Datenbank-Backups erstellen und einsehen",
    "system.update": "LUMS-Systemupdates prüfen und starten",
    "infrastructure.manage": "Infrastruktur-Topologie verwalten",
    "alerts.view": "Alerts und Alert-Historie ansehen",
    "alerts.manage": "Alert-Regeln und Integrationen verwalten",
}

ROLE_DEFAULT_PERMISSIONS = {
    ROLE_VIEWER: frozenset({
        "clients.view",
        "software.view",
    }),
    ROLE_OPERATOR: frozenset({
        "clients.view",
        "software.view",
        "updates.view",
        "packages.search",
        "jobs.manage",
    }),
    ROLE_ADMINISTRATOR: frozenset(
        permission
        for permission in PERMISSIONS
        if permission != "permissions.manage"
    ),
}

ROLE_DESCRIPTIONS = {
    ROLE_VIEWER: (
        "Clients und installierte Software ansehen."
    ),
    ROLE_OPERATOR: (
        "Viewer-Rechte sowie Updates ansehen, Pakete suchen "
        "und Update-Jobs verwalten."
    ),
    ROLE_ADMINISTRATOR: (
        "Alle Bereiche verwalten, einschließlich Clients, "
        "Update-Jobs, Benutzerkonten und Datenbank-Backups."
    ),
}

PERMISSION_DEPENDENCIES = {
    "software.view": {"clients.view"},
    "updates.view": {"clients.view"},
    "packages.search": {"clients.view"},
    "jobs.manage": {"clients.view", "updates.view"},
    "clients.manage": {"clients.view"},
    "permissions.manage": {"users.manage", "clients.view"},
    "system.update": {"users.manage", "clients.view"},
    "infrastructure.manage": {"users.manage", "clients.view"},
    "alerts.manage": {"alerts.view"},
}

SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}

PACKAGE_NAME_MAX_LENGTH = 256


def is_valid_package_name(package):
    if not isinstance(package, str):
        return False

    package = package.strip()

    if not package:
        return False

    if len(package) > PACKAGE_NAME_MAX_LENGTH:
        return False

    if package.startswith("-"):
        return False

    return all(
        character.isalnum()
        or character in ".:+@_/-"
        for character in package
    )


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
        SELECT id, username, password_hash, enabled, role
        FROM users
        WHERE username = ?
        """,
        (username,),
    ).fetchone()



# ============================================================
# LOGIN RATE LIMITING
# ============================================================

LOGIN_RATE_LIMIT_LOCK_STEPS = (
    (5, 30),
    (6, 60),
    (7, 120),
    (8, 300),
)


def get_login_rate_limit_key(username, source):
    normalized_username = (username or "").strip().casefold()
    normalized_source = (source or "").strip()

    return f"{normalized_username}|{normalized_source}"


def get_login_rate_limit(connection, rate_limit_key):
    return connection.execute(
        """
        SELECT
            id,
            rate_limit_key,
            username,
            failed_attempts,
            first_failed_at,
            last_failed_at,
            locked_until
        FROM login_rate_limits
        WHERE rate_limit_key = ?
        """,
        (rate_limit_key,),
    ).fetchone()


def is_login_rate_limited(connection, rate_limit_key):
    row = get_login_rate_limit(connection, rate_limit_key)

    if row is None or row["locked_until"] is None:
        return False

    try:
        locked_until = datetime.fromisoformat(
            row["locked_until"]
        )
    except ValueError:
        return False

    return locked_until > datetime.now(timezone.utc)


def record_login_failure(
    connection,
    rate_limit_key,
    username,
):
    now = datetime.now(timezone.utc)
    now_iso = now.isoformat()

    connection.execute("BEGIN IMMEDIATE")

    row = get_login_rate_limit(
        connection,
        rate_limit_key,
    )

    if row is None:
        failed_attempts = 1
        locked_until = None

        connection.execute(
            """
            INSERT INTO login_rate_limits (
                rate_limit_key,
                username,
                failed_attempts,
                first_failed_at,
                last_failed_at,
                locked_until
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                rate_limit_key,
                username or "",
                failed_attempts,
                now_iso,
                now_iso,
                locked_until,
            ),
        )

        return failed_attempts, locked_until

    failed_attempts = row["failed_attempts"] + 1
    locked_until = None

    for threshold, seconds in LOGIN_RATE_LIMIT_LOCK_STEPS:
        if failed_attempts >= threshold:
            locked_until = (
                now + timedelta(seconds=seconds)
            ).isoformat()

    connection.execute(
        """
        UPDATE login_rate_limits
        SET
            username = ?,
            failed_attempts = ?,
            last_failed_at = ?,
            locked_until = ?
        WHERE rate_limit_key = ?
        """,
        (
            username or "",
            failed_attempts,
            now_iso,
            locked_until,
            rate_limit_key,
        ),
    )

    return failed_attempts, locked_until

def clear_login_rate_limit(connection, rate_limit_key):
    connection.execute(
        """
        DELETE FROM login_rate_limits
        WHERE rate_limit_key = ?
        """,
        (rate_limit_key,),
    )


def current_user_id():
    return session.get(SESSION_USER_KEY)


def current_username():
    return session.get(SESSION_USERNAME_KEY)


def current_user_role():
    user = request.environ.get("lums.user")
    if user is None:
        return None
    return user["role"]


def current_user_permissions():
    return request.environ.get("lums.permissions", frozenset())


def _table_exists(connection, table_name):
    row = connection.execute(
        """
        SELECT 1
        FROM sqlite_master
        WHERE type = 'table' AND name = ?
        """,
        (table_name,),
    ).fetchone()
    return row is not None


def custom_rbac_is_active(connection):
    """Check migration 018 and reject incomplete custom-RBAC schemas."""
    custom_tables = (
        "roles",
        "role_permissions",
        "user_roles",
        "user_permission_overrides",
    )

    existing = {
        table for table in custom_tables
        if _table_exists(connection, table)
    }

    if not _table_exists(connection, "schema_migrations"):
        if existing:
            raise RuntimeError(
                "Custom RBAC tables exist without schema_migrations"
            )
        return False

    marker = connection.execute(
        "SELECT 1 FROM schema_migrations WHERE version = ?",
        ("018-custom-rbac",),
    ).fetchone()

    if marker is None:
        if existing:
            raise RuntimeError(
                "Custom RBAC tables exist without migration marker 018"
            )
        return False

    missing = set(custom_tables) - existing
    if missing:
        raise RuntimeError(
            "Custom RBAC schema is incomplete: "
            + ", ".join(sorted(missing))
        )

    return True


def store_user_permissions(
    connection,
    user_id,
    role,
    permissions,
    actor_id=None,
    timestamp=None,
):
    """
    Store a user's effective permission selection.

    The caller owns the transaction. This helper does not commit.
    """
    if role not in VALID_ROLES:
        raise ValueError(f"Invalid user role: {role!r}")

    if not isinstance(permissions, (list, tuple, set, frozenset)):
        raise ValueError("Permissions must be a collection")

    permission_list = list(permissions)
    selected = set(permission_list)

    if len(selected) != len(permission_list):
        raise ValueError("Duplicate permissions are not allowed")

    unknown = selected - set(PERMISSIONS)
    if unknown:
        raise ValueError(
            "Unknown permissions: " + ", ".join(sorted(unknown))
        )

    for permission in selected:
        dependencies = PERMISSION_DEPENDENCIES.get(permission, set())
        missing_dependencies = dependencies - selected
        if missing_dependencies:
            raise ValueError(
                f"Permission {permission!r} is missing dependencies: "
                + ", ".join(sorted(missing_dependencies))
            )

    if timestamp is None:
        timestamp = utc_now()

    if custom_rbac_is_active(connection):
        role_key = "system-" + role
        role_rows = connection.execute(
            """
            SELECT id
            FROM roles
            WHERE role_key = ?
              AND is_system = 1
              AND is_migration = 0
            """,
            (role_key,),
        ).fetchall()

        if len(role_rows) != 1:
            raise RuntimeError(
                f"Expected exactly one protected system role: {role_key}"
            )

        # Index access works with both sqlite3.Row and ordinary tuples.
        role_id = role_rows[0][0]

        base_permissions = {
            row[0]
            for row in connection.execute(
                """
                SELECT permission
                FROM role_permissions
                WHERE role_id = ?
                """,
                (role_id,),
            ).fetchall()
        }

        unknown_base = base_permissions - set(PERMISSIONS)
        if unknown_base:
            raise RuntimeError(
                "System role contains unknown permissions: "
                + ", ".join(sorted(unknown_base))
            )

        grants = selected - base_permissions
        denies = base_permissions - selected

        connection.execute(
            "DELETE FROM user_roles WHERE user_id = ?",
            (user_id,),
        )
        connection.execute(
            "DELETE FROM user_permission_overrides WHERE user_id = ?",
            (user_id,),
        )
        connection.execute(
            """
            INSERT INTO user_roles (
                user_id, role_id, assigned_at, assigned_by
            )
            VALUES (?, ?, ?, ?)
            """,
            (user_id, role_id, timestamp, actor_id),
        )

        overrides = [
            (user_id, permission, "grant", timestamp, actor_id)
            for permission in sorted(grants)
        ]
        overrides.extend(
            (user_id, permission, "deny", timestamp, actor_id)
            for permission in sorted(denies)
        )

        connection.executemany(
            """
            INSERT INTO user_permission_overrides (
                user_id, permission, effect, changed_at, changed_by
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            overrides,
        )
        return "custom"

    if not _table_exists(connection, "user_permissions"):
        raise RuntimeError(
            "Legacy RBAC is active but user_permissions is missing"
        )

    connection.execute(
        "DELETE FROM user_permissions WHERE user_id = ?",
        (user_id,),
    )
    connection.executemany(
        """
        INSERT INTO user_permissions (user_id, permission)
        VALUES (?, ?)
        """,
        [(user_id, permission) for permission in sorted(selected)],
    )
    return "legacy"


def _filter_permission_dependencies(permissions):
    """Remove permissions whose prerequisites are not effective."""
    effective = set(permissions)

    while True:
        invalid_permissions = {
            permission
            for permission in effective
            if not PERMISSION_DEPENDENCIES.get(
                permission, set()
            ).issubset(effective)
        }

        if not invalid_permissions:
            return frozenset(effective)

        effective.difference_update(invalid_permissions)


def _calculate_effective_permissions(
    role_permissions,
    grants=(),
    denies=(),
):
    """Calculate role permissions plus grants, minus denies."""
    effective = (
        set(role_permissions)
        | set(grants)
    ) - set(denies)

    return _filter_permission_dependencies(effective)


class _InvalidLegacyRoleError(RuntimeError):
    """Raised when legacy RBAC contains an invalid user role."""


def resolve_user_permissions(connection, user_id, user_role=None):
    """
    Resolve effective permissions using either legacy RBAC or custom RBAC.

    Migration 018 is the authoritative switch. Once recorded, missing or
    inconsistent custom-RBAC data is an error; legacy permissions are never
    used as a fallback.
    """
    if not _table_exists(connection, "schema_migrations"):
        raise RuntimeError(
            "RBAC state is unavailable: schema_migrations table is missing"
        )

    migration_marker = connection.execute(
        """
        SELECT 1
        FROM schema_migrations
        WHERE version = ?
        """,
        ("018-custom-rbac",),
    ).fetchone()

    custom_tables = (
        "roles",
        "role_permissions",
        "user_roles",
        "user_permission_overrides",
    )

    existing_custom_tables = {
        table
        for table in custom_tables
        if _table_exists(connection, table)
    }

    if migration_marker is None:
        if existing_custom_tables:
            raise RuntimeError(
                "Custom RBAC tables exist without migration marker 018"
            )

        if user_role is None:
            user_row = connection.execute(
                "SELECT role FROM users WHERE id = ?",
                (user_id,),
            ).fetchone()

            if user_row is None:
                raise RuntimeError(
                    f"Cannot resolve permissions for missing user id {user_id}"
                )

            user_role = user_row["role"]

        if user_role not in VALID_ROLES:
            raise _InvalidLegacyRoleError(
                f"Cannot resolve permissions for invalid legacy role {user_role!r}"
            )

        if _table_exists(connection, "user_permissions"):
            legacy_permissions = {
                row["permission"]
                for row in connection.execute(
                    """
                    SELECT permission
                    FROM user_permissions
                    WHERE user_id = ?
                    """,
                    (user_id,),
                ).fetchall()
            }
        else:
            legacy_permissions = set(
                ROLE_DEFAULT_PERMISSIONS[user_role]
            )

        return _filter_permission_dependencies(legacy_permissions)

    missing_tables = set(custom_tables) - existing_custom_tables
    if missing_tables:
        raise RuntimeError(
            "Custom RBAC schema is incomplete; missing tables: "
            + ", ".join(sorted(missing_tables))
        )

    assignments = connection.execute(
        """
        SELECT
            ur.role_id,
            r.id AS resolved_role_id
        FROM user_roles AS ur
        LEFT JOIN roles AS r
          ON r.id = ur.role_id
        WHERE ur.user_id = ?
        """,
        (user_id,),
    ).fetchall()

    if len(assignments) != 1:
        raise RuntimeError(
            f"User id {user_id} must have exactly one custom RBAC role assignment"
        )

    if assignments[0]["resolved_role_id"] is None:
        raise RuntimeError(
            f"User id {user_id} references a missing custom RBAC role"
        )

    role_id = assignments[0]["role_id"]

    role_permissions = {
        row["permission"]
        for row in connection.execute(
            """
            SELECT permission
            FROM role_permissions
            WHERE role_id = ?
            """,
            (role_id,),
        ).fetchall()
    }

    override_rows = connection.execute(
        """
        SELECT permission, effect
        FROM user_permission_overrides
        WHERE user_id = ?
        """,
        (user_id,),
    ).fetchall()

    grants = set()
    denies = set()

    for row in override_rows:
        permission = row["permission"]
        effect = row["effect"]

        if effect == "grant":
            grants.add(permission)
        elif effect == "deny":
            denies.add(permission)
        else:
            raise RuntimeError(
                f"User id {user_id} has an invalid permission override effect"
            )

    unknown_permissions = (
        role_permissions | grants | denies
    ) - set(PERMISSIONS)

    if unknown_permissions:
        raise RuntimeError(
            "Custom RBAC data contains unknown permissions: "
            + ", ".join(sorted(unknown_permissions))
        )

    return _calculate_effective_permissions(
        role_permissions,
        grants,
        denies,
    )


def is_authenticated():
    return current_user_id() is not None


# ============================================================
# AUTHORIZATION DECORATORS
# ============================================================

def _is_api_request():
    """Recognize API endpoints, including APIs nested under blueprints."""
    path = request.path
    return path.startswith("/api/") or "/api/" in path


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):

        user_id = current_user_id()

        if user_id is None:
            if _is_api_request():
                return jsonify({
                    "error": "authentication_required"
                }), 401

            return redirect(url_for("login"))

        from flask import current_app

        connection = None
        user = None
        permissions = None
        invalid_legacy_role = False

        try:
            connection = current_app.config[
                "LUMS_GET_CONNECTION"
            ]()

            user = connection.execute(
                """
                SELECT id, username, enabled, role
                FROM users
                WHERE id = ?
                """,
                (user_id,),
            ).fetchone()

            if user is not None and user["enabled"]:
                permissions = resolve_user_permissions(
                    connection,
                    user_id,
                    user["role"],
                )

        except _InvalidLegacyRoleError:
            invalid_legacy_role = True

        except Exception:
            current_app.logger.exception(
                "Failed to resolve authorization state for user id %r",
                user_id,
            )

            request.environ.pop("lums.user", None)
            request.environ.pop("lums.permissions", None)

            if _is_api_request():
                return jsonify({
                    "error": "authorization_state_unavailable"
                }), 503

            abort(
                503,
                description="Authorization state is temporarily unavailable.",
            )

        finally:
            if connection is not None:
                connection.close()

        if invalid_legacy_role:
            logout_user()

            if _is_api_request():
                return jsonify({
                    "error": "invalid_user_role"
                }), 403

            return jsonify({
                "error": "invalid_user_role"
            }), 403

        if user is None or not user["enabled"]:
            logout_user()

            if _is_api_request():
                return jsonify({
                    "error": "authentication_required"
                }), 401

            return redirect(url_for("login"))

        request.environ["lums.user"] = user
        request.environ["lums.permissions"] = permissions

        return view(*args, **kwargs)

    return wrapped


def role_required(*roles, permission=None):
    required_roles = set(roles)

    if not required_roles and permission is None:
        raise ValueError(
            "role_required() requires at least one role."
        )

    if not required_roles.issubset(VALID_ROLES):
        invalid_roles = sorted(
            required_roles - VALID_ROLES
        )
        raise ValueError(
            f"Unknown LUMS role(s): {invalid_roles}"
        )

    if permission is not None and permission not in PERMISSIONS:
        raise ValueError(
            f"Unknown LUMS permission: {permission}"
        )

    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):

            user = request.environ.get("lums.user")

            if user is None:
                if _is_api_request():
                    return jsonify({
                        "error": "authentication_required"
                    }), 401

                return redirect(
                    url_for("login")
                )

            authorized = (
                permission in current_user_permissions()
                if permission is not None
                else user["role"] in required_roles
            )

            if not authorized:
                return jsonify({
                    "error": "authorization_required"
                }), 403

            return view(*args, **kwargs)

        return wrapped

    return decorator


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
