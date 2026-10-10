from flask import Flask, request, jsonify, render_template, url_for, redirect
import os
import logging
from pathlib import Path
import sqlite3
import json
from datetime import datetime, timezone

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setLevel(logging.INFO)
    formatter = logging.Formatter(
        "%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)


from security import (
    configure_session,
    apply_security_headers,
    find_user,
    verify_password,
    password_needs_rehash,
    hash_password,
    login_user,
    logout_user,
    current_username,
    current_user_role,
    get_csrf_token,
    audit_log,
    current_user_id,
    login_required,
    role_required,
    ROLE_ADMINISTRATOR,
    ROLE_OPERATOR,
    ROLE_VIEWER,
    VALID_ROLES,
    csrf_required,
    client_auth_required,
    authenticated_client,
    generate_client_token,
    hash_client_token,
    get_login_rate_limit_key,
    is_login_rate_limited,
    is_valid_package_name,
    PACKAGE_NAME_MAX_LENGTH,
    record_login_failure,
    clear_login_rate_limit,
)


app = Flask(__name__)

# Security foundation
#
# The Flask secret is preferably supplied through a root-managed
# Docker secret file. The environment variable remains available
# only as a temporary compatibility fallback.
def load_secret_key():
    secret_file = os.environ.get(
        "LUMS_SECRET_KEY_FILE",
        "/run/secrets/lums_secret",
    )

    try:
        secret = Path(secret_file).read_text().strip()
    except FileNotFoundError:
        secret = os.environ.get("LUMS_SECRET_KEY")

    if not secret:
        raise RuntimeError(
            "LUMS secret is not configured. "
            "Provide LUMS_SECRET_KEY_FILE or LUMS_SECRET_KEY."
        )

    return secret


app.secret_key = load_secret_key()

configure_session(app)

DB_PATH = "/var/lib/lums/lums.db"

PACKAGE_SEARCH_QUERY_MAX_LENGTH = 128
PACKAGE_SEARCH_MAX_RESULTS = 50


def normalize_package_search_query(query):
    if not isinstance(query, str):
        return None

    query = query.strip()

    if not query:
        return None

    if query.startswith("-"):
        return None

    if len(query) > PACKAGE_SEARCH_QUERY_MAX_LENGTH:
        return None

    return query


app.config["LUMS_GET_CONNECTION"] = lambda: get_connection()


@app.after_request
def security_headers(response):
    return apply_security_headers(response)


# ============================================================
# DATABASE HELPERS
# ============================================================

def get_connection():
    connection = sqlite3.connect(DB_PATH)
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA busy_timeout = 5000")
    connection.row_factory = sqlite3.Row
    return connection


# ============================================================
# CLIENT REPORT
# ============================================================

def save_client(client_id, data):

    connection = get_connection()
    cursor = connection.cursor()

    last_seen = datetime.now(timezone.utc).isoformat()

    idle = 1 if data.get("idle") else 0

    try:
        idle_seconds = max(0, int(data.get("idle_seconds", 0)))
    except (TypeError, ValueError):
        idle_seconds = 0

    try:
        idle_threshold_seconds = max(
            1,
            int(data.get("idle_threshold_seconds", 300))
        )
    except (TypeError, ValueError):
        idle_threshold_seconds = 300

    idle_source = str(
        data.get("idle_source", "unknown") or "unknown"
    ).strip()

    idle_supported = 1 if data.get("idle_supported") else 0

    cursor.execute("""
        UPDATE clients
        SET hostname = ?,
            ip = ?,
            os = ?,
            kernel = ?,
            architecture = ?,
            agent_version = ?,
            last_seen = ?,
            idle = ?,
            idle_seconds = ?,
            idle_threshold_seconds = ?,
            idle_source = ?,
            idle_supported = ?
        WHERE id = ?
    """, (
        data.get("hostname"),
        data.get("ip"),
        data.get("os"),
        data.get("kernel"),
        data.get("architecture"),
        data.get("agent_version"),
        last_seen,
        idle,
        idle_seconds,
        idle_threshold_seconds,
        idle_source,
        idle_supported,
        client_id
    ))

    connection.commit()
    connection.close()

    return client_id

def save_updates(client_id, updates):

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        "DELETE FROM available_updates WHERE client_id = ?",
        (client_id,)
    )

    for update in updates:

        package = update.get("package")
        installed_version = update.get("installed_version")
        available_version = update.get("available_version")

        if not package or not available_version:
            continue

        cursor.execute("""
            INSERT INTO available_updates (
                client_id,
                package,
                installed_version,
                available_version
            )
            VALUES (?, ?, ?, ?)
        """, (
            client_id,
            package,
            installed_version,
            available_version
        ))

    connection.commit()
    connection.close()


def save_packages(client_id, packages):

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        "DELETE FROM installed_packages WHERE client_id = ?",
        (client_id,)
    )

    for package, version in packages.items():

        if not package or not version:
            continue

        cursor.execute("""
            INSERT INTO installed_packages (
                client_id,
                package,
                version
            )
            VALUES (?, ?, ?)
        """, (
            client_id,
            package,
            version
        ))

    connection.commit()
    connection.close()


# ============================================================
# CLIENT STATUS
# ============================================================

def get_client_status(last_seen):

    last_seen_time = datetime.fromisoformat(last_seen)

    now = datetime.now(timezone.utc)

    difference = (now - last_seen_time).total_seconds()

    if difference <= 120:
        return "online"

    if difference <= 600:
        return "unknown"

    return "offline"


# ============================================================
# WEB PAGES
# ============================================================

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        return render_template(
            "login.html",
            csrf_token=get_csrf_token(),
        )

    username = (request.form.get("username") or "").strip()
    password = request.form.get("password") or ""

    rate_limit_key = get_login_rate_limit_key(
        username,
        request.remote_addr,
    )

    connection = get_connection()

    try:
        if is_login_rate_limited(
            connection,
            rate_limit_key,
        ):
            audit_log(
                connection,
                actor_type="user",
                actor_id=username or None,
                action="login.rate_limit",
                target=None,
                result="blocked",
                details="login temporarily rate limited",
            )
            connection.commit()

            return render_template(
                "login.html",
                csrf_token=get_csrf_token(),
                error="Invalid username or password.",
                username=username,
            ), 401

        user = find_user(connection, username)

        # Deliberately use the same generic failure response for
        # unknown and disabled users to avoid account enumeration.
        if user is None or not user["enabled"]:
            failed_attempts, locked_until = record_login_failure(
                connection,
                rate_limit_key,
                username,
            )

            audit_log(
                connection,
                actor_type="user",
                actor_id=username or None,
                action="login",
                target=None,
                result="failure",
                details="invalid credentials",
            )

            if locked_until is not None:
                audit_log(
                    connection,
                    actor_type="user",
                    actor_id=username or None,
                    action="login.rate_limit",
                    target=None,
                    result="locked",
                    details=(
                        f"failed_attempts={failed_attempts}"
                    ),
                )

            connection.commit()

            return render_template(
                "login.html",
                csrf_token=get_csrf_token(),
                error="Invalid username or password.",
                username=username,
            ), 401

        if not verify_password(
            user["password_hash"],
            password,
        ):
            failed_attempts, locked_until = record_login_failure(
                connection,
                rate_limit_key,
                username,
            )

            audit_log(
                connection,
                actor_type="user",
                actor_id=user["id"],
                action="login",
                target=f"user:{user['id']}",
                result="failure",
                details="invalid credentials",
            )

            if locked_until is not None:
                audit_log(
                    connection,
                    actor_type="user",
                    actor_id=user["id"],
                    action="login.rate_limit",
                    target=f"user:{user['id']}",
                    result="locked",
                    details=(
                        f"failed_attempts={failed_attempts}"
                    ),
                )

            connection.commit()

            return render_template(
                "login.html",
                csrf_token=get_csrf_token(),
                error="Invalid username or password.",
                username=username,
            ), 401

        # Upgrade the password hash automatically if Argon2 parameters
        # have changed since the account was created.
        if password_needs_rehash(user["password_hash"]):
            new_hash = hash_password(password)

            connection.execute(
                """
                UPDATE users
                SET password_hash = ?
                WHERE id = ?
                """,
                (new_hash, user["id"]),
            )

        clear_login_rate_limit(
            connection,
            rate_limit_key,
        )

        login_user(
            user_id=user["id"],
            username=user["username"],
        )

        audit_log(
            connection,
            actor_type="user",
            actor_id=user["id"],
            action="login",
            target=f"user:{user['id']}",
            result="success",
            details="interactive login",
        )

        connection.commit()

        return redirect(url_for("index"))

    finally:
        connection.close()


@app.route("/logout", methods=["POST"])
@login_required
@csrf_required
def logout():
    user_id = current_user_id()

    if user_id is not None:
        connection = get_connection()

        try:
            audit_log(
                connection,
                actor_type="user",
                actor_id=user_id,
                action="logout",
                target=f"user:{user_id}",
                result="success",
            )
            connection.commit()
        finally:
            connection.close()

    logout_user()

    return redirect(url_for("login"))


@app.route("/")
@login_required
@role_required(
    ROLE_ADMINISTRATOR,
    ROLE_OPERATOR,
    ROLE_VIEWER,
)
def index():
    return render_template(
        "index.html",
        csrf_token=get_csrf_token(),
        user_role=current_user_role(),
    )


@app.route("/users")
@login_required
@role_required(ROLE_ADMINISTRATOR)
def users_page():
    return render_template(
        "users.html",
        csrf_token=get_csrf_token(),
        user_role=current_user_role(),
    )


@app.route("/client")
@login_required
@role_required(
    ROLE_ADMINISTRATOR,
    ROLE_OPERATOR,
    ROLE_VIEWER,
)
def client_page():

    return render_template(
        "client.html",
        csrf_token=get_csrf_token(),
        user_role=current_user_role(),
    )


# ============================================================
# USER MANAGEMENT
# ============================================================

@app.route("/api/users", methods=["GET"])
@login_required
@role_required(ROLE_ADMINISTRATOR)
def list_users():

    connection = get_connection()

    try:
        rows = connection.execute(
            """
            SELECT
                id,
                username,
                role,
                enabled,
                created_at
            FROM users
            ORDER BY username COLLATE NOCASE ASC
            """
        ).fetchall()

        return jsonify([
            {
                "id": row["id"],
                "username": row["username"],
                "role": row["role"],
                "enabled": bool(row["enabled"]),
                "created_at": row["created_at"],
            }
            for row in rows
        ])

    finally:
        connection.close()


@app.route("/api/users", methods=["POST"])
@login_required
@role_required(ROLE_ADMINISTRATOR)
@csrf_required
def create_user():

    data = request.get_json(silent=True) or {}

    username = str(data.get("username", "")).strip()
    password = str(data.get("password", ""))
    role = str(data.get("role", "")).strip()

    if not username:
        return jsonify({
            "error": "username_required"
        }), 400

    if len(username) > 64:
        return jsonify({
            "error": "username_too_long"
        }), 400

    if not password:
        return jsonify({
            "error": "password_required"
        }), 400

    if len(password) < 12:
        return jsonify({
            "error": "password_too_short"
        }), 400

    if role not in VALID_ROLES:
        return jsonify({
            "error": "invalid_user_role"
        }), 400

    connection = get_connection()

    try:
        existing = connection.execute(
            """
            SELECT id
            FROM users
            WHERE username = ?
            """,
            (username,),
        ).fetchone()

        if existing is not None:
            return jsonify({
                "error": "user_already_exists"
            }), 409

        password_hash = hash_password(password)

        cursor = connection.execute(
            """
            INSERT INTO users (
                username,
                password_hash,
                created_at,
                enabled,
                role
            )
            VALUES (?, ?, ?, 1, ?)
            """,
            (
                username,
                password_hash,
                datetime.now(timezone.utc).isoformat(),
                role,
            ),
        )

        user_id = cursor.lastrowid

        audit_log(
            connection,
            actor_type="user",
            actor_id=current_user_id(),
            action="user.create",
            target=f"user:{user_id}",
            result="success",
            details=f"username={username}, role={role}",
        )

        connection.commit()

        return jsonify({
            "status": "created",
            "user": {
                "id": user_id,
                "username": username,
                "role": role,
                "enabled": True,
            },
        }), 201

    except sqlite3.IntegrityError:
        connection.rollback()

        return jsonify({
            "error": "user_already_exists"
        }), 409

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()



@app.route("/api/users/<int:user_id>", methods=["DELETE"])
@login_required
@role_required(ROLE_ADMINISTRATOR)
@csrf_required
def delete_user(user_id):
    actor_id = current_user_id()

    if actor_id == user_id:
        return jsonify({"error": "cannot_delete_self"}), 400

    connection = get_connection()

    try:
        target = connection.execute(
            """
            SELECT id, username, role, enabled
            FROM users
            WHERE id = ?
            """,
            (user_id,),
        ).fetchone()

        if target is None:
            return jsonify({"error": "user_not_found"}), 404

        if target["enabled"] and target["role"] == ROLE_ADMINISTRATOR:
            active_admins = connection.execute(
                """
                SELECT COUNT(*)
                FROM users
                WHERE enabled = 1 AND role = ?
                """,
                (ROLE_ADMINISTRATOR,),
            ).fetchone()[0]

            if active_admins <= 1:
                return jsonify({
                    "error": "last_enabled_administrator"
                }), 409

        connection.execute(
            "DELETE FROM users WHERE id = ?",
            (user_id,),
        )

        audit_log(
            connection,
            actor_type="user",
            actor_id=actor_id,
            action="user.delete",
            target=f"user:{user_id}",
            result="success",
            details=f"username={target['username']}, role={target['role']}",
        )

        connection.commit()

        return jsonify({
            "status": "deleted",
            "user_id": user_id,
        }), 200

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()



# ============================================================
# CLIENT MANAGEMENT
# ============================================================

@app.route("/api/clients", methods=["POST"])
@login_required
@role_required(ROLE_ADMINISTRATOR)
@csrf_required
def create_client():

    data = request.get_json(silent=True) or {}

    hostname = str(data.get("hostname", "")).strip() or None
    ip = str(data.get("ip", "")).strip() or None
    os_name = str(data.get("os", "")).strip() or None
    kernel = str(data.get("kernel", "")).strip() or None
    architecture = str(data.get("architecture", "")).strip() or None
    agent_version = str(data.get("agent_version", "")).strip() or None

    if not ip:
        return jsonify({
            "error": "ip_required"
        }), 400

    connection = get_connection()

    try:
        existing = connection.execute(
            "SELECT id FROM clients WHERE ip = ?",
            (ip,)
        ).fetchone()

        if existing:
            return jsonify({
                "error": "client_already_exists"
            }), 409

        token = generate_client_token()
        token_hash = hash_client_token(token)
        now = datetime.now(timezone.utc).isoformat()

        cursor = connection.execute(
            """
            INSERT INTO clients (
                hostname,
                ip,
                os,
                kernel,
                architecture,
                agent_version,
                last_seen,
                client_token_hash,
                token_created_at,
                token_revoked_at,
                enabled
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, 1)
            """,
            (
                hostname,
                ip,
                os_name,
                kernel,
                architecture,
                agent_version,
                now,
                token_hash,
                now,
            )
        )

        client_id = cursor.lastrowid

        audit_log(
            connection,
            actor_type="user",
            actor_id=current_user_id(),
            action="client.create",
            target=f"client:{client_id}",
            result="success",
            details=f"hostname={hostname}",
        )

        connection.commit()

        return jsonify({
            "status": "created",
            "client": {
                "id": client_id,
                "hostname": hostname,
                "ip": ip,
                "os": os_name,
                "kernel": kernel,
                "architecture": architecture,
                "agent_version": agent_version,
                "enabled": True,
            },
            "token": token,
        }), 201

    except sqlite3.IntegrityError:
        connection.rollback()

        return jsonify({
            "error": "client_already_exists"
        }), 409

    finally:
        connection.close()




@app.route(
    "/api/clients/<int:client_id>/token/rotate",
    methods=["POST"],
)
@login_required
@role_required(ROLE_ADMINISTRATOR)
@csrf_required
def rotate_client_token(client_id):
    connection = get_connection()

    try:
        client = connection.execute(
            """
            SELECT
                id,
                hostname,
                enabled
            FROM clients
            WHERE id = ?
            """,
            (client_id,),
        ).fetchone()

        if client is None:
            return jsonify({
                "error": "client_not_found"
            }), 404

        token = generate_client_token()
        token_hash = hash_client_token(token)
        now = datetime.now(timezone.utc).isoformat()

        connection.execute(
            """
            UPDATE clients
            SET
                client_token_hash = ?,
                token_created_at = ?,
                token_revoked_at = NULL
            WHERE id = ?
            """,
            (
                token_hash,
                now,
                client_id,
            ),
        )

        audit_log(
            connection,
            actor_type="user",
            actor_id=current_user_id(),
            action="client.token.rotate",
            target=f"client:{client_id}",
            result="success",
            details=f"hostname={client['hostname']}",
        )

        connection.commit()

        return jsonify({
            "status": "rotated",
            "client": {
                "id": client["id"],
                "hostname": client["hostname"],
                "enabled": bool(client["enabled"]),
            },
            "token": token,
        }), 200

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()


@app.route("/api/clients/<int:client_id>", methods=["DELETE"])
@login_required
@role_required(ROLE_ADMINISTRATOR)
@csrf_required
def delete_client(client_id):

    connection = get_connection()

    try:
        client = connection.execute(
            """
            SELECT id, hostname
            FROM clients
            WHERE id = ?
            """,
            (client_id,)
        ).fetchone()

        if client is None:
            return jsonify({
                "error": "client_not_found"
            }), 404

        # Remove current client state first.
        connection.execute(
            "DELETE FROM available_updates WHERE client_id = ?",
            (client_id,)
        )

        connection.execute(
            "DELETE FROM installed_packages WHERE client_id = ?",
            (client_id,)
        )

        # Keep the client record for historical integrity.
        # Deactivate the client instead of deleting it so that
        # foreign-key relationships and update history remain intact.
        revoked_at = datetime.now(timezone.utc).isoformat()

        connection.execute(
            """
            UPDATE clients
            SET
                enabled = 0,
                token_revoked_at = ?
            WHERE id = ?
            """,
            (revoked_at, client_id)
        )

        audit_log(
            connection,
            actor_type="user",
            actor_id=current_user_id(),
            action="client.disable",
            target=f"client:{client_id}",
            result="success",
            details=f"hostname={client['hostname']}",
        )

        connection.commit()

        return jsonify({
            "status": "disabled",
            "client_id": client_id,
            "hostname": client["hostname"],
        }), 200

    except sqlite3.IntegrityError:
        connection.rollback()

        return jsonify({
            "error": "client_has_dependencies"
        }), 409

    finally:
        connection.close()

# ============================================================
# HEALTH
# ============================================================

@app.route("/api/health", methods=["GET"])
def health():

    return jsonify({
        "status": "ok",
        "service": "LUMS API"
    })


# ============================================================
# CLIENT REPORT
# ============================================================

@app.route("/api/report", methods=["POST"])
@client_auth_required
def report():

    client = authenticated_client()

    data = request.get_json(silent=True)

    if not isinstance(data, dict) or not data:

        return jsonify({
            "status": "error",
            "message": "Invalid or missing JSON data"
        }), 400

    client_id = save_client(
        client["id"],
        data
    )

    if client_id is not None:

        save_updates(
            client_id,
            data.get("updates", [])
        )

        save_packages(
            client_id,
            data.get("packages", {})
        )

    logger.info(
        "Client report: %s (%s) Updates: %d Pakete: %d",
        data.get("hostname"),
        data.get("ip"),
        len(data.get("updates", [])),
        len(data.get("packages", {})),
    )

    return jsonify({
        "status": "received"
    })


# ============================================================
# AUTHENTICATED CLIENT
# ============================================================

@app.route("/api/client/me", methods=["GET"])
@client_auth_required
def client_me():

    client = authenticated_client()

    return jsonify({
        "id": client["id"],
        "hostname": client["hostname"],
        "enabled": bool(client["enabled"])
    })


# ============================================================
# CLIENT LIST
# ============================================================

@app.route("/api/clients", methods=["GET"])
@login_required
@role_required(
    ROLE_ADMINISTRATOR,
    ROLE_OPERATOR,
    ROLE_VIEWER,
)
def clients():

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
        SELECT
            c.id,
            c.hostname,
            c.ip,
            c.os,
            c.kernel,
            c.architecture,
            c.agent_version,
            c.last_seen,
            c.idle,
            c.idle_seconds,
            c.idle_threshold_seconds,
            c.idle_source,
            c.idle_supported,
            COUNT(DISTINCT p.id) AS package_count,
            COUNT(DISTINCT u.id) AS update_count
        FROM clients c
        LEFT JOIN installed_packages p
            ON p.client_id = c.id
        LEFT JOIN available_updates u
            ON u.client_id = c.id
        WHERE c.enabled = 1
        GROUP BY c.id
        ORDER BY c.hostname
    """)

    rows = cursor.fetchall()

    connection.close()

    result = []

    for row in rows:

        client_data = dict(row)

        client_data["status"] = get_client_status(
            client_data["last_seen"]
        )

        result.append(client_data)

    return jsonify(result)


# ============================================================
# CLIENT DETAILS
# ============================================================

@app.route("/api/clients/<int:client_id>", methods=["GET"])
@login_required
@role_required(
    ROLE_ADMINISTRATOR,
    ROLE_OPERATOR,
    ROLE_VIEWER,
)
def client(client_id):

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
        SELECT
            id,
            hostname,
            ip,
            os,
            kernel,
            architecture,
            agent_version,
            last_seen
        FROM clients
        WHERE id = ?
          AND enabled = 1
    """, (client_id,))

    row = cursor.fetchone()

    if row is None:

        connection.close()

        return jsonify({
            "status": "error",
            "message": "Client not found"
        }), 404

    client_data = dict(row)

    cursor.execute("""
        SELECT COUNT(*)
        FROM installed_packages
        WHERE client_id = ?
    """, (client_id,))

    client_data["package_count"] = cursor.fetchone()[0]

    cursor.execute("""
        SELECT COUNT(*)
        FROM available_updates
        WHERE client_id = ?
    """, (client_id,))

    client_data["update_count"] = cursor.fetchone()[0]

    connection.close()

    client_data["status"] = get_client_status(
        client_data["last_seen"]
    )

    return jsonify(client_data)


# ============================================================
# AVAILABLE UPDATES
# ============================================================

@app.route("/api/clients/<int:client_id>/updates", methods=["GET"])
@login_required
@role_required(
    ROLE_ADMINISTRATOR,
    ROLE_OPERATOR,
    ROLE_VIEWER,
)
def client_updates(client_id):

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
        SELECT
            id,
            package,
            installed_version,
            available_version
        FROM available_updates
        WHERE client_id = ?
        ORDER BY package
    """, (client_id,))

    rows = cursor.fetchall()

    connection.close()

    return jsonify([
        dict(row)
        for row in rows
    ])


# ============================================================
# INSTALLED PACKAGES
# ============================================================

@app.route("/api/clients/<int:client_id>/packages", methods=["GET"])
@login_required
@role_required(
    ROLE_ADMINISTRATOR,
    ROLE_OPERATOR,
    ROLE_VIEWER,
)
def client_packages(client_id):

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
        SELECT
            package,
            version
        FROM installed_packages
        WHERE client_id = ?
        ORDER BY package
    """, (client_id,))

    rows = cursor.fetchall()

    connection.close()

    return jsonify([
        dict(row)
        for row in rows
    ])


# ============================================================
# PACKAGE SEARCH
# ============================================================

@app.route(
    "/api/clients/<int:client_id>/package-search",
    methods=["POST"]
)
@login_required
@role_required(ROLE_ADMINISTRATOR, ROLE_OPERATOR)
@csrf_required
def create_package_search(client_id):

    payload = request.get_json(silent=True)

    if not isinstance(payload, dict):
        return jsonify({
            "error": "invalid_request"
        }), 400

    query = normalize_package_search_query(
        payload.get("query")
    )

    if query is None:
        return jsonify({
            "error": "invalid_package_search_query"
        }), 400

    connection = get_connection()

    try:
        cursor = connection.cursor()

        cursor.execute("""
            SELECT
                id,
                enabled
            FROM clients
            WHERE id = ?
        """, (client_id,))

        client = cursor.fetchone()

        if client is None:
            return jsonify({
                "error": "client_not_found"
            }), 404

        if not client["enabled"]:
            return jsonify({
                "error": "client_disabled"
            }), 409

        created_at = datetime.now(timezone.utc).isoformat()

        cursor.execute("""
            INSERT INTO package_search_requests (
                client_id,
                query,
                status,
                created_at
            )
            VALUES (?, ?, 'pending', ?)
        """, (
            client_id,
            query,
            created_at,
        ))

        search_id = cursor.lastrowid

        audit_log(
            connection,
            actor_type="user",
            actor_id=current_user_id(),
            action="package_search.create",
            target=f"client:{client_id}",
            result="success",
            details=f"search_id={search_id} query={query}",
        )

        connection.commit()

        logger.info(
            "Package search created: Search #%s Client %s Query=%r",
            search_id,
            client_id,
            query,
        )

        return jsonify({
            "status": "pending",
            "search_id": search_id,
            "client_id": client_id,
            "query": query,
        }), 202

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()


# ============================================================
# CREATE UPDATE JOB
# ============================================================

@app.route(
    "/api/clients/<int:client_id>/update-jobs",
    methods=["POST"]
)
@login_required
@role_required(ROLE_ADMINISTRATOR, ROLE_OPERATOR)
@csrf_required
def create_update_job(client_id):

    data = request.get_json(silent=True)

    if not isinstance(data, dict) or not data:

        return jsonify({
            "status": "error",
            "message": "Invalid or missing JSON data"
        }), 400

    action = data.get("action", "UPDATE_PACKAGE")

    allowed_actions = {
        "INSTALL_PACKAGE",
        "REMOVE_PACKAGE",
        "UPDATE_PACKAGE",
        "UPDATE_SYSTEM"
    }

    if action not in allowed_actions:

        return jsonify({
            "status": "error",
            "message": "Invalid package action",
            "allowed_actions": sorted(allowed_actions)
        }), 400

    if action == "UPDATE_SYSTEM":

        packages = []

    else:

        packages = data.get("packages")

        if not isinstance(packages, list):

            return jsonify({
                "status": "error",
                "message": "packages must be a list"
            }), 400

        invalid_packages = [
            package
            for package in packages
            if not is_valid_package_name(package)
        ]

        if invalid_packages:

            return jsonify({
                "status": "error",
                "message": "Invalid package name",
                "packages": invalid_packages
            }), 400

        packages = [
            package.strip()
            for package in packages
        ]

        packages = list(dict.fromkeys(packages))

        if not packages:

            return jsonify({
                "status": "error",
                "message": "No packages selected"
            }), 400

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
        SELECT
            id,
            hostname
        FROM clients
        WHERE id = ?
          AND enabled = 1
    """, (client_id,))

    client_row = cursor.fetchone()

    if client_row is None:

        connection.close()

        return jsonify({
            "status": "error",
            "message": "Client not found"
        }), 404

    update_rows = []

    if action == "UPDATE_PACKAGE":

        placeholders = ",".join(
            "?" for _ in packages
        )

        cursor.execute(
            f"""
            SELECT
                package,
                installed_version,
                available_version
            FROM available_updates
            WHERE client_id = ?
            AND package IN ({placeholders})
            ORDER BY package
            """,
            [client_id] + packages
        )

        update_rows = cursor.fetchall()

        found_packages = {
            row["package"]
            for row in update_rows
        }

        invalid_packages = [
            package
            for package in packages
            if package not in found_packages
        ]

        if invalid_packages:

            connection.close()

            return jsonify({
                "status": "error",
                "message": (
                    "One or more packages are "
                    "not available as updates"
                ),
                "invalid_packages": invalid_packages
            }), 400

    elif action in {
        "INSTALL_PACKAGE",
        "REMOVE_PACKAGE"
    }:

        update_rows = [
            {
                "package": package,
                "installed_version": None,
                "available_version": ""
            }
            for package in packages
        ]

    created_at = datetime.now(
        timezone.utc
    ).isoformat()

    cursor.execute("""
        INSERT INTO update_jobs (
            client_id,
            status,
            created_at,
            action
        )
        VALUES (?, ?, ?, ?)
    """, (
        client_id,
        "pending",
        created_at,
        action
    ))

    job_id = cursor.lastrowid

    for row in update_rows:

        cursor.execute("""
            INSERT INTO update_job_packages (
                job_id,
                package,
                installed_version,
                target_version,
                status
            )
            VALUES (?, ?, ?, ?, ?)
        """, (
            job_id,
            row["package"],
            row["installed_version"],
            row["available_version"],
            "pending"
        ))

    audit_log(
        connection,
        actor_type="user",
        actor_id=current_user_id(),
        action="update_job.create",
        target=f"job:{job_id}",
        result="success",
        details=(
            f"client={client_id} "
            f"action={action} "
            f"packages={len(update_rows)}"
        ),
    )

    connection.commit()

    connection.close()

    logger.info(
        "Update job created: Job #%s Client %s Action: %s Packages: %d",
        job_id,
        client_row["hostname"],
        action,
        len(update_rows),
    )

    return jsonify({
        "status": "created",
        "job_id": job_id,
        "client_id": client_id,
        "hostname": client_row["hostname"],
        "action": action,
        "package_count": len(update_rows),
        "packages": [
            {
                "package": row["package"],
                "installed_version": row["installed_version"],
                "target_version": row["available_version"]
            }
            for row in update_rows
        ]
    }), 201


# ============================================================
# LIST UPDATE JOBS FOR CLIENT
# ============================================================

@app.route(
    "/api/clients/<int:client_id>/update-jobs",
    methods=["GET"]
)
@login_required
@role_required(
    ROLE_ADMINISTRATOR,
    ROLE_OPERATOR,
    ROLE_VIEWER,
)
def client_update_jobs(client_id):

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        "SELECT id FROM clients WHERE id = ?",
        (client_id,)
    )

    if cursor.fetchone() is None:

        connection.close()

        return jsonify({
            "status": "error",
            "message": "Client not found"
        }), 404

    cursor.execute("""
        SELECT
            j.id,
            j.client_id,
            j.status,
            j.created_at,
            j.started_at,
            j.finished_at,
            j.reboot_required,
            COUNT(p.id) AS package_count
        FROM update_jobs j
        LEFT JOIN update_job_packages p
            ON p.job_id = j.id
        WHERE j.client_id = ?
        GROUP BY j.id
        ORDER BY j.id DESC
    """, (client_id,))

    rows = cursor.fetchall()

    connection.close()

    return jsonify([
        dict(row)
        for row in rows
    ])


# ============================================================
# AGENT: CLAIM NEXT PENDING UPDATE JOB
# ============================================================

@app.route(
    "/api/update-jobs/<int:job_id>/checkpoint",
    methods=["POST"],
)
@client_auth_required
def update_job_checkpoint(job_id):
    client = authenticated_client()

    data = request.get_json(silent=True)

    if not isinstance(data, dict) or not data:
        return jsonify({
            "error": "invalid_json"
        }), 400

    package = data.get("package")
    package_status = data.get("status")
    message = data.get("message")

    if not isinstance(package, str) or not package.strip():
        return jsonify({
            "error": "invalid_package"
        }), 400

    if package_status not in (
        "success",
        "failed",
        "timeout",
    ):
        return jsonify({
            "error": "invalid_status"
        }), 400

    if message is not None:
        if not isinstance(message, str):
            return jsonify({
                "error": "invalid_message"
            }), 400

        if len(message) > 4096:
            return jsonify({
                "error": "message_too_long"
            }), 400

    connection = get_connection()

    try:
        job = connection.execute(
            """
            SELECT
                id,
                client_id,
                status
            FROM update_jobs
            WHERE id = ?
            """,
            (job_id,),
        ).fetchone()

        if job is None:
            return jsonify({
                "error": "job_not_found"
            }), 404

        if job["client_id"] != client["id"]:
            return jsonify({
                "error": "client_access_denied"
            }), 403

        if job["status"] != "running":
            return jsonify({
                "error": "job_not_running",
                "job_id": job_id,
                "job_status": job["status"],
            }), 409

        package_row = connection.execute(
            """
            SELECT
                id,
                status
            FROM update_job_packages
            WHERE job_id = ?
              AND package = ?
            """,
            (
                job_id,
                package.strip(),
            ),
        ).fetchone()

        if package_row is None:
            return jsonify({
                "error": "package_not_found"
            }), 404

        update_cursor = connection.execute(
            """
            UPDATE update_job_packages
            SET
                status = ?,
                message = ?
            WHERE job_id = ?
              AND package = ?
            """,
            (
                package_status,
                message,
                job_id,
                package.strip(),
            ),
        )

        if update_cursor.rowcount != 1:
            return jsonify({
                "error": "package_update_conflict"
            }), 409

        connection.commit()

        return jsonify({
            "status": "checkpointed",
            "job_id": job_id,
            "package": package.strip(),
            "package_status": package_status,
        }), 200

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()


@app.route(
    "/api/package-search/<int:search_id>/result",
    methods=["POST"]
)
@client_auth_required
def package_search_result(search_id):

    client = authenticated_client()

    data = request.get_json(silent=True) or {}

    status = data.get("status")
    results = data.get("results", [])
    error_message = data.get("error_message")

    if status not in ("completed", "failed"):
        return jsonify({
            "error": "invalid status"
        }), 400

    if status == "completed":

        if not isinstance(results, list):
            return jsonify({
                "error": "invalid results"
            }), 400

        if len(results) > PACKAGE_SEARCH_MAX_RESULTS:
            return jsonify({
                "error": "too many results"
            }), 400

        for result in results:

            if not isinstance(result, dict):
                return jsonify({
                    "error": "invalid result"
                }), 400

            package = result.get("package")

            if not isinstance(package, str):
                return jsonify({
                    "error": "invalid package"
                }), 400

            package = package.strip()

            if not package:
                return jsonify({
                    "error": "invalid package"
                }), 400

            if len(package) > PACKAGE_NAME_MAX_LENGTH:
                return jsonify({
                    "error": "invalid package"
                }), 400

            if not all(
                character.isalnum()
                or character in ".:+@_/-"
                for character in package
            ):
                return jsonify({
                    "error": "invalid package"
                }), 400

    else:

        if error_message is not None:

            if not isinstance(error_message, str):
                return jsonify({
                    "error": "invalid error_message"
                }), 400

            error_message = error_message.strip()

            if len(error_message) > 1024:
                return jsonify({
                    "error": "error_message too long"
                }), 400

        else:
            error_message = "Package search failed"

        results = []

    connection = get_connection()

    try:

        search = connection.execute(
            """
            SELECT
                id,
                client_id,
                status
            FROM package_search_requests
            WHERE id = ?
            """,
            (search_id,)
        ).fetchone()

        if search is None:
            return jsonify({
                "error": "search_not_found"
            }), 404

        if search["client_id"] != client["id"]:
            return jsonify({
                "error": "client_access_denied"
            }), 403

        if search["status"] != "running":
            return jsonify({
                "error": "search_not_running",
                "search_id": search_id,
                "search_status": search["status"],
            }), 409

        finished_at = datetime.now(
            timezone.utc
        ).isoformat()

        if status == "completed":
            result_json = json.dumps(
                results,
                ensure_ascii=False,
            )
            error_message = None
        else:
            result_json = "[]"

        connection.execute(
            """
            UPDATE package_search_requests
            SET
                status = ?,
                finished_at = ?,
                result_json = ?,
                error_message = ?
            WHERE id = ?
              AND client_id = ?
              AND status = 'running'
            """,
            (
                status,
                finished_at,
                result_json,
                error_message,
                search_id,
                client["id"],
            )
        )

        connection.commit()

        logger.info(
            "Package search completed: Search #%s Client %s "
            "Status=%s Results=%d",
            search_id,
            client["id"],
            status,
            len(results),
        )

        return jsonify({
            "status": status,
            "search_id": search_id,
            "result_count": len(results),
            "finished_at": finished_at,
        })

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()


@app.route("/api/update-jobs/<int:job_id>/result", methods=["POST"])
@client_auth_required
def update_job_result(job_id):
    client = authenticated_client()

    data = request.get_json(silent=True) or {}

    if not isinstance(data, dict):
        return jsonify({
            "error": "invalid_json"
        }), 400

    status = data.get("status")
    reboot_required = 1 if data.get("reboot_required") is True else 0
    packages = data.get("packages", [])

    if status not in ("success", "partial", "failed"):
        return jsonify({
            "error": "invalid status"
        }), 400

    if not isinstance(packages, list):
        return jsonify({
            "error": "invalid packages"
        }), 400

    MAX_PACKAGE_RESULTS = 100
    MAX_RESULT_MESSAGE_LENGTH = 4096

    if len(packages) > MAX_PACKAGE_RESULTS:
        return jsonify({
            "error": "too_many_package_results"
        }), 400

    allowed_package_statuses = {
        "success",
        "failed",
        "timeout",
    }

    seen_packages = set()

    for package_result in packages:

        if not isinstance(package_result, dict):
            return jsonify({
                "error": "invalid package result"
            }), 400

        package = package_result.get("package")
        package_status = package_result.get("status")
        message = package_result.get("message")

        if not isinstance(package, str) or not package.strip():
            return jsonify({
                "error": "invalid package"
            }), 400

        package = package.strip()

        if package in seen_packages:
            return jsonify({
                "error": "duplicate package",
                "package": package,
            }), 400

        seen_packages.add(package)

        if package_status not in allowed_package_statuses:
            return jsonify({
                "error": "invalid package status"
            }), 400

        if message is not None:
            if not isinstance(message, str):
                return jsonify({
                    "error": "invalid package message",
                    "package": package,
                }), 400

            if len(message) > MAX_RESULT_MESSAGE_LENGTH:
                return jsonify({
                    "error": "package message too long",
                    "package": package,
                }), 400

    conn = get_connection()

    try:
        job = conn.execute(
            """
            SELECT *
            FROM update_jobs
            WHERE id = ?
            """,
            (job_id,)
        ).fetchone()

        if job is None:
            return jsonify({
                "error": "job not found"
            }), 404

        if job["client_id"] != client["id"]:
            return jsonify({
                "error": "client_access_denied"
            }), 403

        if job["status"] != "running":
            return jsonify({
                "error": "job_not_running",
                "job_id": job_id,
                "job_status": job["status"]
            }), 409

        job_packages = {
            row["package"]
            for row in conn.execute(
                """
                SELECT package
                FROM update_job_packages
                WHERE job_id = ?
                """,
                (job_id,)
            ).fetchall()
        }

        # UPDATE_SYSTEM jobs intentionally contain no package rows.
        if job["action"] == "UPDATE_SYSTEM":

            if packages:
                return jsonify({
                    "error": "system_update_must_not_contain_packages"
                }), 400

            now = datetime.now(timezone.utc).isoformat()

            update_cursor = conn.execute(
                """
                UPDATE update_jobs
                SET status = ?,
                    finished_at = ?,
                    reboot_required = ?
                WHERE id = ?
                  AND client_id = ?
                  AND status = 'running'
                """,
                (
                    status,
                    now,
                    reboot_required,
                    job_id,
                    client["id"],
                )
            )

            if update_cursor.rowcount != 1:
                conn.rollback()
                return jsonify({
                    "error": "job_update_conflict"
                }), 409

            conn.execute(
                """
                INSERT INTO update_history (
                    client_id,
                    job_id,
                    status,
                    package_count,
                    successful_count,
                    failed_count,
                    reboot_required,
                    started_at,
                    finished_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    job["client_id"],
                    job_id,
                    status,
                    0,
                    0,
                    0,
                    reboot_required,
                    job["started_at"],
                    now
                )
            )

            conn.commit()

            return jsonify({
                "status": "ok",
                "job_id": job_id,
                "job_status": status,
                "successful_count": 0,
                "failed_count": 0,
                "reboot_required": bool(reboot_required)
            })

        expected_count = len(job_packages)

        if len(packages) != expected_count:
            return jsonify({
                "error": "incomplete_package_results",
                "expected": expected_count,
                "received": len(packages),
            }), 400

        if seen_packages != job_packages:
            missing_packages = sorted(job_packages - seen_packages)
            unexpected_packages = sorted(seen_packages - job_packages)

            return jsonify({
                "error": "package_result_mismatch",
                "missing_packages": missing_packages,
                "unexpected_packages": unexpected_packages,
            }), 400

        successful_count = sum(
            1
            for package_result in packages
            if package_result["status"] == "success"
        )

        failed_count = len(packages) - successful_count

        if failed_count == 0:
            derived_status = "success"
        elif successful_count > 0:
            derived_status = "partial"
        else:
            derived_status = "failed"

        if status != derived_status:
            return jsonify({
                "error": "status_mismatch",
                "submitted_status": status,
                "derived_status": derived_status,
            }), 400

        now = datetime.now(timezone.utc).isoformat()

        for package_result in packages:

            package = package_result["package"].strip()
            package_status = package_result["status"]
            message = package_result.get("message")

            package_cursor = conn.execute(
                """
                UPDATE update_job_packages
                SET status = ?,
                    message = ?
                WHERE job_id = ?
                  AND package = ?
                """,
                (
                    package_status,
                    message,
                    job_id,
                    package
                )
            )

            if package_cursor.rowcount != 1:
                conn.rollback()
                return jsonify({
                    "error": "package_update_conflict",
                    "package": package,
                }), 409

        update_cursor = conn.execute(
            """
            UPDATE update_jobs
            SET status = ?,
                finished_at = ?,
                reboot_required = ?
            WHERE id = ?
              AND client_id = ?
              AND status = 'running'
            """,
            (
                derived_status,
                now,
                reboot_required,
                job_id,
                client["id"],
            )
        )

        if update_cursor.rowcount != 1:
            conn.rollback()
            return jsonify({
                "error": "job_update_conflict"
            }), 409

        conn.execute(
            """
            INSERT INTO update_history (
                client_id,
                job_id,
                status,
                package_count,
                successful_count,
                failed_count,
                reboot_required,
                started_at,
                finished_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                job["client_id"],
                job_id,
                derived_status,
                len(packages),
                successful_count,
                failed_count,
                reboot_required,
                job["started_at"],
                now
            )
        )

        conn.commit()

        return jsonify({
            "status": "ok",
            "job_id": job_id,
            "job_status": derived_status,
            "successful_count": successful_count,
            "failed_count": failed_count,
            "reboot_required": bool(reboot_required)
        })

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()


@app.route(
    "/api/update-jobs/<int:job_id>/abandon",
    methods=["POST"]
)
@client_auth_required
def abandon_update_job(job_id):

    client = authenticated_client()

    connection = get_connection()

    try:
        cursor = connection.cursor()

        cursor.execute("""
            SELECT
                id,
                client_id,
                status,
                created_at,
                started_at,
                reboot_required
            FROM update_jobs
            WHERE id = ?
        """, (job_id,))

        job = cursor.fetchone()

        if job is None:
            return jsonify({
                "error": "job_not_found"
            }), 404

        if job["client_id"] != client["id"]:
            return jsonify({
                "error": "client_access_denied"
            }), 403

        if job["status"] != "running":
            return jsonify({
                "error": "job_not_running"
            }), 409

        now = datetime.now(timezone.utc).isoformat()

        cursor.execute("""
            SELECT COUNT(*) AS package_count
            FROM update_job_packages
            WHERE job_id = ?
        """, (job_id,))

        package_count = cursor.fetchone()["package_count"]

        recovery_reason = "Agent did not submit a final result."

        cursor.execute("""
            UPDATE update_jobs
            SET status = ?,
                finished_at = ?,
                recovery_reason = ?
            WHERE id = ?
              AND client_id = ?
              AND status = 'running'
        """, (
            "abandoned",
            now,
            recovery_reason,
            job_id,
            client["id"]
        ))

        if cursor.rowcount != 1:
            connection.rollback()

            return jsonify({
                "error": "job_recovery_conflict"
            }), 409

        cursor.execute("""
            INSERT INTO update_history (
                client_id,
                job_id,
                status,
                package_count,
                successful_count,
                failed_count,
                reboot_required,
                started_at,
                finished_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            job["client_id"],
            job_id,
            "abandoned",
            package_count,
            0,
            0,
            job["reboot_required"],
            job["started_at"],
            now
        ))

        connection.commit()

        return jsonify({
            "status": "abandoned",
            "job_id": job_id,
            "client_id": client["id"],
            "package_count": package_count,
            "recovery_reason": recovery_reason
        }), 200

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()



@app.route(
    "/api/clients/<int:client_id>/package-search/pending",
    methods=["GET"]
)
@client_auth_required
def get_pending_package_search(client_id):

    client = authenticated_client()

    if client["id"] != client_id:
        return jsonify({
            "error": "client_access_denied"
        }), 403

    connection = get_connection()

    try:
        connection.execute("BEGIN IMMEDIATE")

        cursor = connection.cursor()

        cursor.execute("""
            SELECT
                id,
                query,
                created_at
            FROM package_search_requests
            WHERE client_id = ?
              AND status = 'pending'
            ORDER BY id ASC
            LIMIT 1
        """, (client_id,))

        search = cursor.fetchone()

        if search is None:
            connection.rollback()

            return jsonify({
                "status": "no_search"
            }), 204

        started_at = datetime.now(
            timezone.utc
        ).isoformat()

        cursor.execute("""
            UPDATE package_search_requests
            SET
                status = 'running',
                started_at = ?
            WHERE id = ?
              AND client_id = ?
              AND status = 'pending'
        """, (
            started_at,
            search["id"],
            client_id,
        ))

        if cursor.rowcount != 1:
            connection.rollback()

            return jsonify({
                "error": "search_claim_conflict"
            }), 409

        connection.commit()

        logger.info(
            "Package search claimed: Search #%s Client %s Query=%r",
            search["id"],
            client_id,
            search["query"],
        )

        return jsonify({
            "status": "running",
            "search_id": search["id"],
            "client_id": client_id,
            "query": search["query"],
            "created_at": search["created_at"],
            "started_at": started_at,
        })

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()


@app.route(
    "/api/clients/<int:client_id>/package-search/<int:search_id>",
    methods=["GET"]
)
@login_required
@role_required(ROLE_ADMINISTRATOR, ROLE_OPERATOR)
def get_package_search_status(client_id, search_id):

    connection = get_connection()

    try:
        search = connection.execute(
            """
            SELECT
                id,
                client_id,
                query,
                status,
                created_at,
                started_at,
                finished_at,
                result_json,
                error_message
            FROM package_search_requests
            WHERE id = ?
              AND client_id = ?
            """,
            (
                search_id,
                client_id,
            )
        ).fetchone()

        if search is None:
            return jsonify({
                "error": "search_not_found"
            }), 404

        results = []

        if search["status"] == "completed":
            try:
                results = json.loads(
                    search["result_json"] or "[]"
                )
            except (TypeError, json.JSONDecodeError):
                logger.error(
                    "Invalid package search result JSON: Search #%s",
                    search_id,
                )

                return jsonify({
                    "error": "invalid_search_result"
                }), 500

        return jsonify({
            "status": search["status"],
            "search_id": search["id"],
            "client_id": search["client_id"],
            "query": search["query"],
            "created_at": search["created_at"],
            "started_at": search["started_at"],
            "finished_at": search["finished_at"],
            "results": results,
            "error_message": search["error_message"],
        })

    finally:
        connection.close()



@app.route(
    "/api/clients/<int:client_id>/update-jobs/pending",
    methods=["GET"]
)
@client_auth_required
def get_pending_update_job(client_id):

    client = authenticated_client()

    if client["id"] != client_id:
        return jsonify({
            "error": "client_access_denied"
        }), 403

    connection = get_connection()

    try:
        cursor = connection.cursor()

        cursor.execute("""
            SELECT
                id,
                hostname
            FROM clients
            WHERE id = ?
        """, (client_id,))

        client_row = cursor.fetchone()

        if client_row is None:
            return jsonify({
                "status": "error",
                "message": "Client not found"
            }), 404

        cursor.execute("""
            SELECT
                id,
                client_id,
                created_at,
                reboot_required,
                action
            FROM update_jobs
            WHERE client_id = ?
            AND status = 'pending'
            ORDER BY id ASC
            LIMIT 1
        """, (client_id,))

        job_row = cursor.fetchone()

        if job_row is None:
            return jsonify({
                "status": "no_job"
            }), 204

        job_id = job_row["id"]

        cursor.execute("""
            SELECT
                package,
                installed_version,
                target_version,
                status
            FROM update_job_packages
            WHERE job_id = ?
            ORDER BY id ASC
        """, (job_id,))

        package_rows = cursor.fetchall()

        return jsonify({
            "status": "pending",
            "job_id": job_id,
            "client_id": job_row["client_id"],
            "created_at": job_row["created_at"],
            "action": job_row["action"],
            "reboot_required": bool(job_row["reboot_required"]),
            "packages": [
                {
                    "package": row["package"],
                    "installed_version": row["installed_version"],
                    "target_version": row["target_version"],
                    "status": row["status"]
                }
                for row in package_rows
            ]
        })

    finally:
        connection.close()



@app.route(
    "/api/clients/<int:client_id>/update-jobs/running",
    methods=["GET"]
)
@client_auth_required
def get_running_update_job(client_id):

    client = authenticated_client()

    if client["id"] != client_id:
        return jsonify({
            "error": "client_access_denied"
        }), 403

    connection = get_connection()

    try:
        cursor = connection.cursor()

        cursor.execute("""
            SELECT
                id,
                hostname
            FROM clients
            WHERE id = ?
        """, (client_id,))

        client_row = cursor.fetchone()

        if client_row is None:
            return jsonify({
                "status": "error",
                "message": "Client not found"
            }), 404

        cursor.execute("""
            SELECT
                id,
                client_id,
                created_at,
                started_at,
                reboot_required,
                action
            FROM update_jobs
            WHERE client_id = ?
            AND status = 'running'
            ORDER BY id ASC
            LIMIT 1
        """, (client_id,))

        job_row = cursor.fetchone()

        if job_row is None:
            return jsonify({
                "status": "no_job"
            }), 204

        cursor.execute("""
            SELECT
                package,
                target_version,
                status
            FROM update_job_packages
            WHERE job_id = ?
            ORDER BY id ASC
        """, (job_row["id"],))

        packages = [
            {
                "package": row["package"],
                "target_version": row["target_version"],
                "status": row["status"]
            }
            for row in cursor.fetchall()
        ]

        return jsonify({
            "status": "running",
            "job_id": job_row["id"],
            "client_id": job_row["client_id"],
            "created_at": job_row["created_at"],
            "started_at": job_row["started_at"],
            "reboot_required": bool(job_row["reboot_required"]),
            "action": job_row["action"],
            "packages": packages
        }), 200

    finally:
        connection.close()

@app.route(
    "/api/clients/<int:client_id>/update-jobs/<int:job_id>/claim",
    methods=["POST"]
)
@client_auth_required
def claim_update_job(client_id, job_id):

    client = authenticated_client()

    if client["id"] != client_id:
        return jsonify({
            "error": "client_access_denied"
        }), 403

    connection = get_connection()

    try:
        connection.execute("BEGIN IMMEDIATE")
        cursor = connection.cursor()

        cursor.execute("""
            SELECT
                id,
                client_id,
                status,
                created_at,
                reboot_required,
                action
            FROM update_jobs
            WHERE id = ?
            AND client_id = ?
        """, (
            job_id,
            client_id
        ))

        job_row = cursor.fetchone()

        if job_row is None:
            connection.rollback()
            return jsonify({
                "status": "error",
                "message": "Job not found"
            }), 404

        if job_row["status"] != "pending":
            connection.rollback()
            return jsonify({
                "status": "not_claimable",
                "job_id": job_id,
                "job_status": job_row["status"]
            }), 409

        started_at = datetime.now(timezone.utc).isoformat()

        cursor.execute("""
            UPDATE update_jobs
            SET
                status = 'running',
                started_at = ?
            WHERE id = ?
            AND client_id = ?
            AND status = 'pending'
        """, (
            started_at,
            job_id,
            client_id
        ))

        if cursor.rowcount != 1:
            connection.rollback()
            return jsonify({
                "status": "error",
                "message": "Job could not be claimed"
            }), 409

        cursor.execute("""
            SELECT
                package,
                installed_version,
                target_version,
                status
            FROM update_job_packages
            WHERE job_id = ?
            ORDER BY id ASC
        """, (job_id,))

        package_rows = cursor.fetchall()

        connection.commit()

        logger.info(
            "Update job claimed: Job #%s Client %s Packages: %d",
            job_id,
            client_id,
            len(package_rows),
        )

        return jsonify({
            "status": "claimed",
            "job_id": job_id,
            "client_id": client_id,
            "started_at": started_at,
            "reboot_required": bool(job_row["reboot_required"]),
            "action": job_row["action"],
            "packages": [
                {
                    "package": row["package"],
                    "installed_version": row["installed_version"],
                    "target_version": row["target_version"],
                    "status": row["status"]
                }
                for row in package_rows
            ]
        })

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()

@app.route(
    "/api/update-jobs/<int:job_id>",
    methods=["GET"]
)
@login_required
@role_required(
    ROLE_ADMINISTRATOR,
    ROLE_OPERATOR,
    ROLE_VIEWER,
)
def update_job(job_id):

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
        SELECT
            j.id,
            j.client_id,
            c.hostname,
            c.ip,
            j.status,
            j.created_at,
            j.started_at,
            j.finished_at,
            j.reboot_required
        FROM update_jobs j
        JOIN clients c
            ON c.id = j.client_id
        WHERE j.id = ?
    """, (job_id,))

    job_row = cursor.fetchone()

    if job_row is None:

        connection.close()

        return jsonify({
            "status": "error",
            "message": "Update job not found"
        }), 404

    cursor.execute("""
        SELECT
            id,
            package,
            installed_version,
            target_version,
            status,
            message
        FROM update_job_packages
        WHERE job_id = ?
        ORDER BY package
    """, (job_id,))

    package_rows = cursor.fetchall()

    connection.close()

    job = dict(job_row)

    job["packages"] = [
        dict(row)
        for row in package_rows
    ]

    job["package_count"] = len(package_rows)

    job["successful_count"] = sum(
        1
        for row in package_rows
        if row["status"] == "success"
    )

    job["failed_count"] = sum(
        1
        for row in package_rows
        if row["status"] == "failed"
    )

    return jsonify(job)


# ============================================================
# UPDATE HISTORY
# ============================================================

@app.route(
    "/api/clients/<int:client_id>/update-history",
    methods=["GET"]
)
@login_required
@role_required(
    ROLE_ADMINISTRATOR,
    ROLE_OPERATOR,
    ROLE_VIEWER,
)
def client_update_history(client_id):

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
        SELECT
            id,
            client_id,
            job_id,
            status,
            package_count,
            successful_count,
            failed_count,
            reboot_required,
            started_at,
            finished_at
        FROM update_history
        WHERE client_id = ?
        ORDER BY id DESC
    """, (client_id,))

    rows = cursor.fetchall()

    connection.close()

    return jsonify([
        dict(row)
        for row in rows
    ])


# ============================================================
# ALL UPDATE HISTORY
# ============================================================

@app.route(
    "/api/update-history",
    methods=["GET"]
)
@login_required
@role_required(
    ROLE_ADMINISTRATOR,
    ROLE_OPERATOR,
    ROLE_VIEWER,
)
def update_history():

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
        SELECT
            h.id,
            h.client_id,
            c.hostname,
            c.ip,
            h.job_id,
            h.status,
            h.package_count,
            h.successful_count,
            h.failed_count,
            h.reboot_required,
            h.started_at,
            h.finished_at
        FROM update_history h
        JOIN clients c
            ON c.id = h.client_id
        ORDER BY h.id DESC
    """)

    rows = cursor.fetchall()

    connection.close()

    return jsonify([
        dict(row)
        for row in rows
    ])


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":

    app.run(
        host="0.0.0.0",
        port=5000
    )
