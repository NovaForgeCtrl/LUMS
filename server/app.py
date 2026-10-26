from flask import (
    Flask,
    request,
    jsonify,
    render_template,
    url_for,
    redirect,
    session,
    Response,
)
import csv
import io
import hmac
import os
import logging
from pathlib import Path
import sqlite3
import json
import math
import ipaddress
from datetime import datetime, timedelta, timezone
from urllib.parse import urlsplit

if __package__:
    from .i18n import (
        LANGUAGES,
        browser_language,
        locale_for,
        normalize_language,
        translations_for,
        translate,
    )
else:
    from i18n import (
        LANGUAGES,
        browser_language,
        locale_for,
        normalize_language,
        translations_for,
        translate,
    )

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


if __package__:
    from .security import (
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
        current_user_permissions,
        get_csrf_token,
        audit_log,
        current_user_id,
        login_required,
        role_required,
        ROLE_ADMINISTRATOR,
        ROLE_OPERATOR,
        ROLE_VIEWER,
        VALID_ROLES,
        PERMISSIONS,
        ROLE_DEFAULT_PERMISSIONS,
        ROLE_DESCRIPTIONS,
        PERMISSION_DEPENDENCIES,
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
    from .database_backup import (
        BACKUP_FORMATS,
        BackupPathError,
        BackupStorageError,
        create_database_backup,
        delete_database_backup,
        list_database_backups,
    )
    from .system_updates import ReleaseLookupError, latest_release
else:
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
        current_user_permissions,
        get_csrf_token,
        audit_log,
        current_user_id,
        login_required,
        role_required,
        ROLE_ADMINISTRATOR,
        ROLE_OPERATOR,
        ROLE_VIEWER,
        VALID_ROLES,
        PERMISSIONS,
        ROLE_DEFAULT_PERMISSIONS,
        ROLE_DESCRIPTIONS,
        PERMISSION_DEPENDENCIES,
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
    from database_backup import (
        BACKUP_FORMATS,
        BackupPathError,
        BackupStorageError,
        create_database_backup,
        delete_database_backup,
        list_database_backups,
    )
    from system_updates import ReleaseLookupError, latest_release


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

DB_PATH = os.environ.get(
    "LUMS_DB_PATH",
    "/var/lib/lums/lums.db",
)

PACKAGE_SEARCH_QUERY_MAX_LENGTH = 128
PACKAGE_SEARCH_MAX_RESULTS = 50
ADMIN_NOTE_MAX_LENGTH = 2000
BACKUP_DIRECTORY = Path(
    os.environ.get(
        "LUMS_BACKUP_DIR",
        "/var/backups/lums",
    )
)


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


@app.before_request
def initialize_language():
    if normalize_language(session.get("language")) is None:
        session["language"] = browser_language(request.accept_languages)


@app.context_processor
def language_context():
    language = normalize_language(
        session.get("language")
    ) or browser_language(request.accept_languages)
    return {
        "language": language,
        "language_locale": locale_for(language),
        "languages": LANGUAGES,
        "translations": translations_for(language),
        "tr": lambda message: translate(message, language),
    }


# ============================================================
# DATABASE HELPERS
# ============================================================

def get_connection():
    connection = sqlite3.connect(DB_PATH)
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA busy_timeout = 5000")
    connection.row_factory = sqlite3.Row
    return connection


def get_user_permissions(connection, user_id, role):
    permissions_table = connection.execute(
        """
        SELECT 1
        FROM sqlite_master
        WHERE type = 'table' AND name = 'user_permissions'
        """
    ).fetchone()

    if permissions_table is None:
        return sorted(ROLE_DEFAULT_PERMISSIONS[role])

    return [
        row["permission"]
        for row in connection.execute(
            """
            SELECT permission
            FROM user_permissions
            WHERE user_id = ?
            ORDER BY permission
            """,
            (user_id,),
        ).fetchall()
    ]


def validate_permission_selection(permissions):
    if (
        not isinstance(permissions, list)
        or any(
            not isinstance(permission, str)
            or permission not in PERMISSIONS
            for permission in permissions
        )
        or len(permissions) != len(set(permissions))
    ):
        return False

    selected = set(permissions)

    return all(
        dependencies.issubset(selected)
        for permission, dependencies in PERMISSION_DEPENDENCIES.items()
        if permission in selected
    )


def count_active_user_managers(connection):
    permissions_table = connection.execute(
        """
        SELECT 1
        FROM sqlite_master
        WHERE type = 'table' AND name = 'user_permissions'
        """
    ).fetchone()

    if permissions_table is None:
        return connection.execute(
            "SELECT COUNT(*) FROM users WHERE enabled = 1 AND role = ?",
            (ROLE_ADMINISTRATOR,),
        ).fetchone()[0]

    return connection.execute(
        """
        SELECT COUNT(DISTINCT users.id)
        FROM users
        JOIN user_permissions
            ON user_permissions.user_id = users.id
        WHERE users.enabled = 1
          AND user_permissions.permission = 'users.manage'
        """
    ).fetchone()[0]


def count_active_permission_managers(connection):
    return connection.execute("""
        SELECT COUNT(DISTINCT users.id)
        FROM users
        WHERE users.enabled = 1
          AND EXISTS (
              SELECT 1
              FROM user_permissions
              WHERE user_permissions.user_id = users.id
                AND user_permissions.permission = 'permissions.manage'
          )
          AND EXISTS (
              SELECT 1
              FROM user_permissions
              WHERE user_permissions.user_id = users.id
                AND user_permissions.permission = 'users.manage'
          )
          AND EXISTS (
              SELECT 1
              FROM user_permissions
              WHERE user_permissions.user_id = users.id
                AND user_permissions.permission = 'clients.view'
          )
    """).fetchone()[0]

def permission_ui_context():
    language = normalize_language(
        session.get("language")
    ) or browser_language(request.accept_languages)
    return {
        "user_permissions": sorted(current_user_permissions()),
        "permission_definitions": [
            {"key": key, "label": translate(label, language)}
            for key, label in PERMISSIONS.items()
        ],
        "role_default_permissions": {
            role: sorted(permissions)
            for role, permissions in ROLE_DEFAULT_PERMISSIONS.items()
        },
        "role_descriptions": {
            role: translate(description, language)
            for role, description in ROLE_DESCRIPTIONS.items()
        },
    }


# ============================================================
# CLIENT REPORT
# ============================================================

def validate_client_report(data):
    text_fields = (
        "hostname",
        "ip",
        "os",
        "kernel",
        "architecture",
        "agent_version",
    )

    if any(
        not isinstance(data.get(field), str) or not data[field].strip()
        for field in text_fields
    ):
        return False

    if "idle" in data and not isinstance(data["idle"], bool):
        return False

    for field in ("idle_seconds", "idle_threshold_seconds"):
        if field in data and (
            not isinstance(data[field], int)
            or isinstance(data[field], bool)
            or data[field] < (1 if field == "idle_threshold_seconds" else 0)
        ):
            return False

    if "idle_source" in data and not isinstance(data["idle_source"], str):
        return False

    if "idle_supported" in data and not isinstance(data["idle_supported"], bool):
        return False

    updates = data.get("updates", [])
    if not isinstance(updates, list):
        return False

    for update in updates:
        if not isinstance(update, dict):
            return False

        package = update.get("package")
        available_version = update.get("available_version")
        installed_version = update.get("installed_version")

        if (
            not is_valid_package_name(package)
            or not isinstance(available_version, str)
            or not available_version.strip()
            or (
                installed_version is not None
                and not isinstance(installed_version, str)
            )
        ):
            return False

    packages = data.get("packages", {})
    if not isinstance(packages, dict):
        return False

    return all(
        is_valid_package_name(package)
        and isinstance(version, str)
        and bool(version.strip())
        for package, version in packages.items()
    )


def save_client_report(client_id, data):
    connection = get_connection()

    try:
        cursor = connection.cursor()
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
            data["hostname"],
            data["ip"],
            data["os"],
            data["kernel"],
            data["architecture"],
            data["agent_version"],
            datetime.now(timezone.utc).isoformat(),
            int(data.get("idle", False)),
            data.get("idle_seconds", 0),
            data.get("idle_threshold_seconds", 300),
            data.get("idle_source", "unknown").strip() or "unknown",
            int(data.get("idle_supported", False)),
            client_id,
        ))

        cursor.execute(
            "DELETE FROM available_updates WHERE client_id = ?",
            (client_id,),
        )

        for update in data.get("updates", []):
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
                update["package"],
                update.get("installed_version"),
                update["available_version"],
            ))

        cursor.execute(
            "DELETE FROM installed_packages WHERE client_id = ?",
            (client_id,),
        )

        for package, version in data.get("packages", {}).items():
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
                version,
            ))

        connection.commit()
    except sqlite3.Error:
        connection.rollback()
        raise
    finally:
        connection.close()

    return client_id


# ============================================================
# CLIENT STATUS
# ============================================================

def classify_health_client(last_seen, now=None):
    """Classify a client timestamp without allowing malformed data to break the dashboard."""
    if not isinstance(last_seen, str) or not last_seen.strip():
        return "unknown"

    try:
        last_seen_time = datetime.fromisoformat(last_seen)
        if last_seen_time.tzinfo is None:
            last_seen_time = last_seen_time.replace(tzinfo=timezone.utc)

        current_time = now or datetime.now(timezone.utc)
        if current_time.tzinfo is None:
            current_time = current_time.replace(tzinfo=timezone.utc)

        difference = (current_time - last_seen_time).total_seconds()
    except (TypeError, ValueError, OverflowError):
        return "unknown"

    if difference < 0:
        return "unknown"
    if difference <= 120:
        return "online"
    if difference <= 600:
        return "unknown"
    return "offline"


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
        language_column_exists = any(
            column["name"] == "language"
            for column in connection.execute(
                "PRAGMA table_info(users)"
            ).fetchall()
        )
        preferred_language_row = (
            connection.execute(
                "SELECT language FROM users WHERE id = ?",
                (user["id"],),
            ).fetchone()
            if language_column_exists
            else None
        )
        preferred_language = normalize_language(
            preferred_language_row["language"]
            if preferred_language_row is not None
            else None
        )
        selected_language = normalize_language(
            request.form.get("language")
        ) or browser_language(request.accept_languages)
        session["language"] = preferred_language or selected_language
        if preferred_language is None and language_column_exists:
            connection.execute(
                "UPDATE users SET language = ? WHERE id = ?",
                (selected_language, user["id"]),
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


@app.route("/language", methods=["POST"])
@csrf_required
def change_language():
    language = normalize_language(request.form.get("language"))
    if language is None:
        return jsonify({"error": "invalid_language"}), 400

    session["language"] = language
    user_id = current_user_id()
    if user_id is not None:
        connection = get_connection()
        try:
            cursor = connection.execute(
                "UPDATE users SET language = ? WHERE id = ?",
                (language, user_id),
            )
            if cursor.rowcount != 1:
                connection.rollback()
                return jsonify({"error": "user_not_found"}), 404
            connection.commit()
        except sqlite3.Error:
            connection.rollback()
            logger.exception("Unable to save the user's language preference.")
            return jsonify({"error": "language_preference_save_failed"}), 500
        finally:
            connection.close()

    referrer = request.referrer
    if referrer and urlsplit(referrer).netloc == request.host:
        return redirect(referrer)
    return redirect(
        url_for("index") if user_id is not None else url_for("login")
    )


@app.route("/")
@login_required
@role_required(
    ROLE_ADMINISTRATOR,
    ROLE_OPERATOR,
    ROLE_VIEWER,
    permission="clients.view",
)
def index():
    return render_template(
        "index.html",
        csrf_token=get_csrf_token(),
        user_role=current_user_role(),
        **permission_ui_context(),
    )


INFRASTRUCTURE_NODE_TYPES = {
    "server", "vm", "container", "network_device", "service", "storage",
}
INFRASTRUCTURE_RELATION_TYPES = {
    "depends_on", "hosts", "connects_to", "runs_on",
}
TOPOLOGY_FIELD_LIMITS = {
    "name": 120,
    "hostname": 253,
    "ip_address": 45,
    "role": 120,
    "location": 120,
    "notes": 1000,
    "details": 500,
}


def topology_node_input(payload):
    if not isinstance(payload, dict):
        return None, "invalid_node"

    values = {}
    for key, maximum in TOPOLOGY_FIELD_LIMITS.items():
        if key == "details":
            continue
        value = payload.get(key, "")
        if not isinstance(value, str):
            return None, "invalid_node"
        value = value.strip()
        if len(value) > maximum:
            return None, "field_too_long"
        values[key] = value

    node_type = payload.get("node_type")
    if (
        not isinstance(node_type, str)
        or node_type not in INFRASTRUCTURE_NODE_TYPES
    ):
        return None, "invalid_node_type"
    if not values["name"]:
        return None, "name_required"
    if values["ip_address"]:
        try:
            ipaddress.ip_address(values["ip_address"])
        except ValueError:
            return None, "invalid_ip_address"

    values["node_type"] = node_type
    return values, None


def topology_endpoint_input(payload, prefix):
    kind = payload.get(f"{prefix}_type")
    raw_id = payload.get(f"{prefix}_id")
    if not isinstance(kind, str) or kind not in {"client", "node"}:
        return None
    try:
        entity_id = int(raw_id)
    except (TypeError, ValueError):
        return None
    if entity_id < 1:
        return None
    return kind, entity_id


@app.route("/infrastructure")
@login_required
@role_required(
    ROLE_ADMINISTRATOR,
    ROLE_OPERATOR,
    ROLE_VIEWER,
    permission="clients.view",
)
def infrastructure_page():
    return render_template(
        "infrastructure.html",
        csrf_token=get_csrf_token(),
        user_role=current_user_role(),
        can_manage=(
            current_user_role() == ROLE_ADMINISTRATOR
            and "infrastructure.manage" in current_user_permissions()
        ),
        **permission_ui_context(),
    )


@app.route("/api/infrastructure/topology")
@login_required
@role_required(
    ROLE_ADMINISTRATOR,
    ROLE_OPERATOR,
    ROLE_VIEWER,
    permission="clients.view",
)
def infrastructure_topology():
    connection = get_connection()
    try:
        clients = connection.execute(
            """
            SELECT id, hostname, ip, os, last_seen, enabled
            FROM clients
            ORDER BY hostname COLLATE NOCASE
            """
        ).fetchall()
        manual_nodes = connection.execute(
            """
            SELECT id, name, node_type, hostname, ip_address, role,
                   location, notes, created_at, updated_at
            FROM infrastructure_nodes
            ORDER BY name COLLATE NOCASE
            """
        ).fetchall()
        relation_rows = connection.execute(
            """
            SELECT id, source_node_id, source_client_id,
                   target_node_id, target_client_id, relation_type, details
            FROM infrastructure_relations
            ORDER BY id
            """
        ).fetchall()

        nodes = [
            {
                "id": f"client:{row['id']}",
                "entity_type": "client",
                "entity_id": row["id"],
                "name": row["hostname"],
                "node_type": "client",
                "hostname": row["hostname"],
                "ip_address": row["ip"] or "",
                "role": row["os"] or "",
                "location": "",
                "status": (
                    classify_health_client(row["last_seen"])
                    if row["enabled"] else "disabled"
                ),
                "editable": False,
            }
            for row in clients
        ]
        nodes.extend(
            {
                "id": f"node:{row['id']}",
                "entity_type": "node",
                "entity_id": row["id"],
                "name": row["name"],
                "node_type": row["node_type"],
                "hostname": row["hostname"],
                "ip_address": row["ip_address"],
                "role": row["role"],
                "location": row["location"],
                "notes": row["notes"],
                "updated_at": row["updated_at"],
                "status": "unknown",
                "editable": True,
            }
            for row in manual_nodes
        )
        relations = [
            {
                "id": row["id"],
                "source": {
                    "type": "node" if row["source_node_id"] else "client",
                    "id": row["source_node_id"] or row["source_client_id"],
                },
                "target": {
                    "type": "node" if row["target_node_id"] else "client",
                    "id": row["target_node_id"] or row["target_client_id"],
                },
                "relation_type": row["relation_type"],
                "details": row["details"],
            }
            for row in relation_rows
        ]
        return jsonify({"nodes": nodes, "relations": relations})
    except sqlite3.Error:
        logger.exception("Unable to load infrastructure topology.")
        return jsonify({"error": "topology_load_failed"}), 500
    finally:
        connection.close()


@app.route("/api/infrastructure/nodes", methods=["POST"])
@login_required
@role_required(ROLE_ADMINISTRATOR)
@role_required(permission="infrastructure.manage")
@csrf_required
def create_infrastructure_node():
    values, error = topology_node_input(request.get_json(silent=True))
    if error:
        return jsonify({"error": error}), 400

    now = datetime.now(timezone.utc).isoformat()
    connection = get_connection()
    try:
        cursor = connection.execute(
            """
            INSERT INTO infrastructure_nodes (
                name, node_type, hostname, ip_address, role, location,
                notes, created_at, updated_at, created_by
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                values["name"], values["node_type"], values["hostname"],
                values["ip_address"], values["role"], values["location"],
                values["notes"], now, now, current_user_id(),
            ),
        )
        node_id = cursor.lastrowid
        audit_log(
            connection, "user", current_user_id(),
            "infrastructure.node.create", str(node_id),
        )
        connection.commit()
        return jsonify({"id": node_id}), 201
    except sqlite3.Error:
        connection.rollback()
        logger.exception("Unable to create infrastructure node.")
        return jsonify({"error": "topology_save_failed"}), 500
    finally:
        connection.close()


@app.route("/api/infrastructure/nodes/<int:node_id>", methods=["PUT", "DELETE"])
@login_required
@role_required(ROLE_ADMINISTRATOR)
@role_required(permission="infrastructure.manage")
@csrf_required
def update_or_delete_infrastructure_node(node_id):
    connection = get_connection()
    try:
        existing = connection.execute(
            "SELECT id FROM infrastructure_nodes WHERE id = ?",
            (node_id,),
        ).fetchone()
        if existing is None:
            return jsonify({"error": "node_not_found"}), 404

        if request.method == "DELETE":
            connection.execute(
                """
                DELETE FROM infrastructure_relations
                WHERE source_node_id = ? OR target_node_id = ?
                """,
                (node_id, node_id),
            )
            connection.execute(
                "DELETE FROM infrastructure_nodes WHERE id = ?",
                (node_id,),
            )
            audit_log(
                connection, "user", current_user_id(),
                "infrastructure.node.delete", str(node_id),
            )
        else:
            values, error = topology_node_input(request.get_json(silent=True))
            if error:
                return jsonify({"error": error}), 400
            connection.execute(
                """
                UPDATE infrastructure_nodes
                SET name = ?, node_type = ?, hostname = ?, ip_address = ?,
                    role = ?, location = ?, notes = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    values["name"], values["node_type"], values["hostname"],
                    values["ip_address"], values["role"], values["location"],
                    values["notes"], datetime.now(timezone.utc).isoformat(),
                    node_id,
                ),
            )
            audit_log(
                connection, "user", current_user_id(),
                "infrastructure.node.update", str(node_id),
            )
        connection.commit()
        return jsonify({"status": "saved"})
    except sqlite3.Error:
        connection.rollback()
        logger.exception(
            "Unable to change infrastructure node %s.", node_id
        )
        return jsonify({"error": "topology_save_failed"}), 500
    finally:
        connection.close()


@app.route("/api/infrastructure/relations", methods=["POST"])
@login_required
@role_required(ROLE_ADMINISTRATOR)
@role_required(permission="infrastructure.manage")
@csrf_required
def create_infrastructure_relation():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify({"error": "invalid_relation"}), 400
    source = topology_endpoint_input(payload, "source")
    target = topology_endpoint_input(payload, "target")
    relation_type = payload.get("relation_type")
    details = payload.get("details", "")
    if (
        source is None
        or target is None
        or source == target
        or not isinstance(relation_type, str)
        or relation_type not in INFRASTRUCTURE_RELATION_TYPES
        or not isinstance(details, str)
        or len(details.strip()) > TOPOLOGY_FIELD_LIMITS["details"]
    ):
        return jsonify({"error": "invalid_relation"}), 400

    connection = get_connection()
    try:
        for kind, entity_id in (source, target):
            table = "clients" if kind == "client" else "infrastructure_nodes"
            exists = connection.execute(
                f"SELECT id FROM {table} WHERE id = ?",
                (entity_id,),
            ).fetchone()
            if exists is None:
                return jsonify({"error": "topology_endpoint_not_found"}), 404

        source_node_id = source[1] if source[0] == "node" else None
        source_client_id = source[1] if source[0] == "client" else None
        target_node_id = target[1] if target[0] == "node" else None
        target_client_id = target[1] if target[0] == "client" else None
        duplicate = connection.execute(
            """
            SELECT id FROM infrastructure_relations
            WHERE COALESCE(source_node_id, 0) = ?
              AND COALESCE(source_client_id, 0) = ?
              AND COALESCE(target_node_id, 0) = ?
              AND COALESCE(target_client_id, 0) = ?
              AND relation_type = ?
            """,
            (
                source_node_id or 0, source_client_id or 0,
                target_node_id or 0, target_client_id or 0,
                relation_type,
            ),
        ).fetchone()
        if duplicate is not None:
            return jsonify({"error": "relation_exists"}), 409

        cursor = connection.execute(
            """
            INSERT INTO infrastructure_relations (
                source_node_id, source_client_id, target_node_id,
                target_client_id, relation_type, details, created_at,
                created_by
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                source_node_id, source_client_id, target_node_id,
                target_client_id, relation_type, details.strip(),
                datetime.now(timezone.utc).isoformat(), current_user_id(),
            ),
        )
        audit_log(
            connection, "user", current_user_id(),
            "infrastructure.relation.create", str(cursor.lastrowid),
        )
        connection.commit()
        return jsonify({"id": cursor.lastrowid}), 201
    except sqlite3.Error:
        connection.rollback()
        logger.exception("Unable to create infrastructure relation.")
        return jsonify({"error": "topology_save_failed"}), 500
    finally:
        connection.close()


@app.route("/api/infrastructure/relations/<int:relation_id>", methods=["DELETE"])
@login_required
@role_required(ROLE_ADMINISTRATOR)
@role_required(permission="infrastructure.manage")
@csrf_required
def delete_infrastructure_relation(relation_id):
    connection = get_connection()
    try:
        cursor = connection.execute(
            "DELETE FROM infrastructure_relations WHERE id = ?",
            (relation_id,),
        )
        if cursor.rowcount != 1:
            connection.rollback()
            return jsonify({"error": "relation_not_found"}), 404
        audit_log(
            connection, "user", current_user_id(),
            "infrastructure.relation.delete", str(relation_id),
        )
        connection.commit()
        return jsonify({"status": "saved"})
    except sqlite3.Error:
        connection.rollback()
        logger.exception(
            "Unable to delete infrastructure relation %s.", relation_id
        )
        return jsonify({"error": "topology_save_failed"}), 500
    finally:
        connection.close()


@app.route("/health")
@login_required
@role_required(
    ROLE_ADMINISTRATOR,
    ROLE_OPERATOR,
    ROLE_VIEWER,
    permission="clients.view",
)
def health_page():
    return render_health_page(monitoring_only=False)


@app.route("/monitoring")
@login_required
@role_required(
    ROLE_ADMINISTRATOR,
    ROLE_OPERATOR,
    ROLE_VIEWER,
    permission="clients.view",
)
def monitoring_page():
    return render_health_page(monitoring_only=True)


def render_health_page(monitoring_only):
    database_status = "unavailable"
    client_counts = {"total": 0, "online": 0, "unknown": 0, "offline": 0}
    latest_backup_run = None

    connection = None
    try:
        connection = get_connection()
        connection.execute("SELECT 1").fetchone()
        rows = connection.execute("SELECT last_seen FROM clients").fetchall()

        for row in rows:
            status = classify_health_client(row["last_seen"])
            client_counts["total"] += 1
            client_counts[status] += 1

        try:
            backup_run = connection.execute(
                """
                SELECT timestamp
                FROM audit_log
                WHERE action = 'database.backup.create'
                    AND result = 'success'
                ORDER BY timestamp DESC
                LIMIT 1
                """
            ).fetchone()
            if backup_run is not None:
                latest_backup_run = backup_run["timestamp"]
        except sqlite3.Error:
            logger.warning(
                "Health dashboard could not query successful backup history."
            )

        database_status = "ok"
    except (sqlite3.Error, OSError, RuntimeError):
        logger.warning("Health dashboard could not query the LUMS database.")
    finally:
        if connection is not None:
            try:
                connection.close()
            except sqlite3.Error:
                logger.warning("Health dashboard could not close its database connection.")

    backup_status = "unavailable"
    latest_backup = None
    try:
        backups = list_database_backups(
            app.config.get("LUMS_BACKUP_DIR", BACKUP_DIRECTORY),
            limit=1,
        )
        backup_status = "ok"
        if backups:
            latest_backup = backups[0]
        else:
            backup_status = "empty"
    except (BackupPathError, BackupStorageError, OSError, RuntimeError):
        logger.warning("Health dashboard could not inspect backup storage.")

    return render_template(
        "health.html",
        csrf_token=get_csrf_token(),
        user_role=current_user_role(),
        monitoring_only=monitoring_only,
        database_status=database_status,
        client_counts=client_counts,
        backup_status=backup_status,
        latest_backup=latest_backup,
        latest_backup_run=latest_backup_run,
        **permission_ui_context(),
    )


@app.route("/users")
@login_required
@role_required(ROLE_ADMINISTRATOR, permission="users.manage")
def users_page():
    return render_template(
        "users.html",
        csrf_token=get_csrf_token(),
        user_role=current_user_role(),
        **permission_ui_context(),
    )


@app.route("/updates")
@login_required
@role_required(ROLE_ADMINISTRATOR)
@role_required(permission="system.update")
def system_updates_page():
    return render_template(
        "updates.html",
        csrf_token=get_csrf_token(),
        user_role=current_user_role(),
        **permission_ui_context(),
    )



@app.route("/api/host-updater/heartbeat", methods=["POST"])
def host_updater_heartbeat():
    """Authenticate the dedicated host updater and record its heartbeat."""
    token_file = os.environ.get(
        "LUMS_HOST_UPDATER_TOKEN_FILE",
        "/run/secrets/lums_host_updater_token",
    )

    try:
        configured_token = Path(token_file).read_text(
            encoding="utf-8"
        ).strip()
    except OSError:
        logger.error("Host-updater token file is unavailable")
        return jsonify({"error": "host_updater_not_configured"}), 503

    if len(configured_token) < 32:
        logger.error("Host-updater token configuration is invalid")
        return jsonify({"error": "host_updater_not_configured"}), 503

    authorization = request.headers.get("Authorization", "")
    scheme, separator, supplied_token = authorization.partition(" ")
    supplied_token = supplied_token.strip()

    if (
        not separator
        or scheme.lower() != "bearer"
        or not supplied_token
        or not hmac.compare_digest(
            hash_client_token(supplied_token),
            hash_client_token(configured_token),
        )
    ):
        return jsonify({"error": "host_updater_authentication_required"}), 401

    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify({"error": "invalid_json"}), 400

    version = payload.get("version")
    deployment = payload.get("deployment")
    status_message = payload.get("status_message", "Heartbeat received")

    for field, value, limit in (
        ("version", version, 80),
        ("deployment", deployment, 80),
        ("status_message", status_message, 500),
    ):
        if value is not None and (
            not isinstance(value, str) or len(value) > limit
        ):
            return jsonify({"error": "invalid_" + field}), 400

    if not isinstance(status_message, str) or not status_message.strip():
        return jsonify({"error": "invalid_status_message"}), 400

    now = datetime.now(timezone.utc).isoformat()
    connection = None

    try:
        connection = app.config["LUMS_GET_CONNECTION"]()
        connection.execute(
            """
            INSERT INTO system_update_agent
                (id, last_seen, current_version, deployment, status_message)
            VALUES (1, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                last_seen = excluded.last_seen,
                current_version = excluded.current_version,
                deployment = excluded.deployment,
                status_message = excluded.status_message
            """,
            (now, version, deployment, status_message.strip()),
        )
        connection.commit()
    except sqlite3.Error:
        if connection is not None:
            connection.rollback()
        logger.exception("Could not record host-updater heartbeat")
        return jsonify({"error": "heartbeat_storage_failed"}), 500
    finally:
        if connection is not None:
            connection.close()

    return jsonify({
        "status": "ok",
        "last_seen": now,
        "update_execution_enabled": False,
    }), 200


@app.route("/api/system-updates", methods=["GET"])
@login_required
@role_required(ROLE_ADMINISTRATOR)
@role_required(permission="system.update")
def system_updates_status():
    release = None
    release_error = None
    try:
        release = latest_release()
    except ReleaseLookupError as error:
        release_error = str(error)

    connection = get_connection()
    try:
        agent = connection.execute(
            """
            SELECT last_seen, current_version, deployment, status_message
            FROM system_update_agent
            WHERE id = 1
            """
        ).fetchone()
        jobs = connection.execute(
            """
            SELECT id, requested_at, requested_by, target_tag, target_commit,
                   status, step,
                   progress_json, details_json, error, rollback_status,
                   updated_at, finished_at
            FROM system_update_jobs
            ORDER BY id DESC
            LIMIT 20
            """
        ).fetchall()
    finally:
        connection.close()

    agent_data = dict(agent) if agent else None
    if agent_data:
        try:
            heartbeat = datetime.fromisoformat(agent_data["last_seen"])
            if heartbeat.tzinfo is None:
                heartbeat = heartbeat.replace(tzinfo=timezone.utc)
            agent_data["online"] = (
                datetime.now(timezone.utc) - heartbeat
            ).total_seconds() <= 60
        except (TypeError, ValueError):
            agent_data["online"] = False
    else:
        agent_data = {"online": False}

    history = []
    for row in jobs:
        item = dict(row)
        item["progress"] = json.loads(item.pop("progress_json") or "[]")
        item["details"] = json.loads(item.pop("details_json") or "{}")
        history.append(item)

    return jsonify({
        "release": release,
        "release_error": release_error,
        "agent": agent_data,
        "history": history,
    })


@app.route("/api/system-updates", methods=["POST"])
@login_required
@role_required(ROLE_ADMINISTRATOR)
@role_required(permission="system.update")
@csrf_required
def request_system_update():
    try:
        release = latest_release()
    except ReleaseLookupError as error:
        return jsonify({"error": str(error)}), 503

    connection = get_connection()
    try:
        agent = connection.execute(
            """
            SELECT last_seen FROM system_update_agent WHERE id = 1
            """
        ).fetchone()
        if agent is None:
            return jsonify({
                "error": "Der Host-Update-Dienst ist nicht installiert oder nicht erreichbar."
            }), 503

        try:
            heartbeat = datetime.fromisoformat(agent["last_seen"])
            if heartbeat.tzinfo is None:
                heartbeat = heartbeat.replace(tzinfo=timezone.utc)
        except (TypeError, ValueError):
            heartbeat = None
        if (
            heartbeat is None
            or (datetime.now(timezone.utc) - heartbeat).total_seconds() > 60
        ):
            return jsonify({
                "error": "Der Host-Update-Dienst ist nicht erreichbar. Es wurde kein Update gestartet."
            }), 503

        active = connection.execute(
            """
            SELECT id FROM system_update_jobs
            WHERE status IN (
                'queued', 'running', 'rolling_back'
            )
            LIMIT 1
            """
        ).fetchone()
        if active is not None:
            return jsonify({
                "error": "Ein Update läuft bereits.",
                "job_id": active["id"],
            }), 409

        now = datetime.now(timezone.utc).isoformat()
        cursor = connection.execute(
            """
            INSERT INTO system_update_jobs (
                requested_at, requested_by, target_tag, target_commit,
                status, step, updated_at
            )
            VALUES (?, ?, ?, ?, 'queued', 'queued', ?)
            """,
            (
                now,
                current_username(),
                release["tag"],
                release["commit"],
                now,
            ),
        )
        job_id = cursor.lastrowid
        audit_log(
            connection,
            actor_type="user",
            actor_id=current_user_id(),
            action="system_update.request",
            target=release["tag"],
            result="success",
            details=json.dumps({
                "job_id": job_id,
                "commit": release["commit"],
            }),
        )
        connection.commit()
    finally:
        connection.close()

    return jsonify({"job_id": job_id, "target_tag": release["tag"]}), 202


@app.route("/backups")
@login_required
@role_required(
    ROLE_ADMINISTRATOR,
    ROLE_OPERATOR,
    ROLE_VIEWER,
    permission="backups.manage",
)
def backups_page():
    return render_template(
        "backups.html",
        csrf_token=get_csrf_token(),
        backup_root=str(BACKUP_DIRECTORY),
        user_role=current_user_role(),
        **permission_ui_context(),
    )


@app.route("/api/backups", methods=["GET"])
@login_required
@role_required(
    ROLE_ADMINISTRATOR,
    ROLE_OPERATOR,
    ROLE_VIEWER,
    permission="backups.manage",
)
def list_backups():
    relative_path = request.args.get("path", "")
    try:
        backups = list_database_backups(
            app.config.get("LUMS_BACKUP_DIR", BACKUP_DIRECTORY),
            relative_path=relative_path,
        )
    except BackupPathError as error:
        return jsonify({
            "error": "invalid_backup_path",
            "message": str(error),
        }), 400
    except BackupStorageError as error:
        return jsonify({
            "error": "backup_storage_unavailable",
            "message": str(error),
        }), 503
    except OSError:
        logger.exception("Unable to list LUMS database backups.")
        return jsonify({"error": "backup_storage_unavailable"}), 503

    return jsonify({"backups": backups})


@app.route("/api/backups", methods=["POST"])
@login_required
@role_required(
    ROLE_ADMINISTRATOR,
    ROLE_OPERATOR,
    ROLE_VIEWER,
    permission="backups.manage",
)
@csrf_required
def create_backup():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"error": "invalid_request"}), 400

    backup_format = data.get("format")
    if (
        not isinstance(backup_format, str)
        or backup_format not in BACKUP_FORMATS
    ):
        return jsonify({"error": "invalid_backup_format"}), 400

    relative_path = data.get("path", "")
    if not isinstance(relative_path, str):
        return jsonify({"error": "invalid_backup_path"}), 400

    try:
        backup = create_database_backup(
            DB_PATH,
            app.config.get("LUMS_BACKUP_DIR", BACKUP_DIRECTORY),
            backup_format,
            relative_path=relative_path,
        )
    except BackupPathError as error:
        return jsonify({
            "error": "invalid_backup_path",
            "message": str(error),
        }), 400
    except BackupStorageError as error:
        return jsonify({
            "error": "backup_storage_unavailable",
            "message": str(error),
        }), 503
    except (OSError, sqlite3.Error):
        logger.exception("Unable to create LUMS database backup.")
        return jsonify({"error": "backup_failed"}), 500

    connection = None
    try:
        connection = get_connection()
        audit_log(
            connection,
            actor_type="user",
            actor_id=current_user_id(),
            action="database.backup.create",
            target=backup["filename"],
            result="success",
            details=(
                f"format={backup['format']}, "
                f"size_bytes={backup['size_bytes']}"
            ),
        )
        connection.commit()
    except sqlite3.Error:
        if connection is not None:
            connection.rollback()
        logger.exception(
            "Backup %s was created, but its audit entry failed.",
            backup["filename"],
        )
        return jsonify({
            "error": "backup_audit_failed",
            "backup": backup,
        }), 500
    finally:
        if connection is not None:
            connection.close()

    return jsonify({"backup": backup}), 201


@app.route("/api/backups/<filename>", methods=["DELETE"])
@login_required
@role_required(
    ROLE_ADMINISTRATOR,
    ROLE_OPERATOR,
    ROLE_VIEWER,
    permission="backups.manage",
)
@csrf_required
def delete_backup(filename):
    relative_path = request.args.get("path", "")

    try:
        delete_database_backup(
            app.config.get("LUMS_BACKUP_DIR", BACKUP_DIRECTORY),
            filename,
            relative_path=relative_path,
        )
    except BackupPathError as error:
        return jsonify({
            "error": "invalid_backup_path",
            "message": str(error),
        }), 400
    except FileNotFoundError:
        return jsonify({"error": "backup_not_found"}), 404
    except BackupStorageError as error:
        return jsonify({
            "error": "backup_storage_unavailable",
            "message": str(error),
        }), 503
    except OSError:
        logger.exception("Unable to delete LUMS backup %s.", filename)
        return jsonify({"error": "backup_delete_failed"}), 500

    connection = None
    try:
        connection = get_connection()
        audit_log(
            connection,
            actor_type="user",
            actor_id=current_user_id(),
            action="database.backup.delete",
            target=filename,
            result="success",
        )
        connection.commit()
    except sqlite3.Error:
        if connection is not None:
            connection.rollback()
        logger.exception(
            "Backup %s was deleted, but its audit entry failed.",
            filename,
        )
        return jsonify({"error": "backup_audit_failed"}), 500
    finally:
        if connection is not None:
            connection.close()

    return jsonify({"status": "deleted", "filename": filename})


@app.route("/client")
@login_required
@role_required(
    ROLE_ADMINISTRATOR,
    ROLE_OPERATOR,
    ROLE_VIEWER,
    permission="clients.view",
)
def client_page():

    return render_template(
        "client.html",
        csrf_token=get_csrf_token(),
        user_role=current_user_role(),
        **permission_ui_context(),
    )


# ============================================================
# USER MANAGEMENT
# ============================================================

@app.route("/api/users", methods=["GET"])
@login_required
@role_required(ROLE_ADMINISTRATOR, permission="users.manage")
def list_users():

    connection = get_connection()

    try:
        rows = connection.execute(
            """
            SELECT
                users.id,
                users.username,
                users.role,
                users.enabled,
                users.created_at,
                users.admin_note,
                users.first_name,
                users.last_name,
                users.department,
                users.function_id,
                user_functions.name AS function_name
            FROM users
            LEFT JOIN user_functions
                ON user_functions.id = users.function_id
            ORDER BY users.username COLLATE NOCASE ASC
            """
        ).fetchall()

        return jsonify([
            {
                "id": row["id"],
                "username": row["username"],
                "role": row["role"],
                "permissions": get_user_permissions(
                    connection,
                    row["id"],
                    row["role"],
                ),
                "enabled": bool(row["enabled"]),
                "created_at": row["created_at"],
                "admin_note": row["admin_note"],
                "first_name": row["first_name"],
                "last_name": row["last_name"],
                "department": row["department"],
                "function_id": row["function_id"],
                "function_name": row["function_name"],
            }
            for row in rows
        ])

    finally:
        connection.close()



@app.route("/api/user-functions", methods=["GET"])
@login_required
@role_required(ROLE_ADMINISTRATOR, permission="users.manage")
def list_user_functions():
    connection = get_connection()
    try:
        rows = connection.execute("""
            SELECT
                functions.id,
                functions.name,
                functions.created_at,
                functions.created_by,
                COUNT(users.id) AS user_count
            FROM user_functions AS functions
            LEFT JOIN users ON users.function_id = functions.id
            GROUP BY functions.id
            ORDER BY functions.name COLLATE NOCASE
        """).fetchall()
        return jsonify([
            {
                "id": row["id"],
                "name": row["name"],
                "created_at": row["created_at"],
                "created_by": row["created_by"],
                "user_count": row["user_count"],
            }
            for row in rows
        ])
    finally:
        connection.close()


@app.route("/api/user-functions", methods=["POST"])
@login_required
@role_required(ROLE_ADMINISTRATOR, permission="users.manage")
@csrf_required
def create_user_function():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"error": "invalid_request"}), 400

    name = data.get("name")
    if not isinstance(name, str):
        return jsonify({"error": "invalid_function_name"}), 400

    name = name.strip()
    if not name or len(name) > 100:
        return jsonify({"error": "invalid_function_name"}), 400

    connection = get_connection()
    try:
        cursor = connection.execute("""
            INSERT INTO user_functions (name, created_at, created_by)
            VALUES (?, ?, ?)
        """, (
            name,
            datetime.now(timezone.utc).isoformat(),
            current_user_id(),
        ))
        function_id = cursor.lastrowid

        audit_log(
            connection,
            actor_type="user",
            actor_id=current_user_id(),
            action="user_function.create",
            target=f"user_function:{function_id}",
            result="success",
            details=f"name={name}",
        )
        connection.commit()
        return jsonify({
            "status": "created",
            "function": {"id": function_id, "name": name},
        }), 201
    except sqlite3.IntegrityError:
        connection.rollback()
        return jsonify({"error": "function_already_exists"}), 409
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


@app.route("/api/user-functions/<int:function_id>", methods=["DELETE"])
@login_required
@role_required(ROLE_ADMINISTRATOR, permission="users.manage")
@csrf_required
def delete_user_function(function_id):
    connection = get_connection()
    try:
        target = connection.execute(
            "SELECT id, name FROM user_functions WHERE id = ?",
            (function_id,),
        ).fetchone()
        if target is None:
            return jsonify({"error": "function_not_found"}), 404

        connection.execute(
            "DELETE FROM user_functions WHERE id = ?",
            (function_id,),
        )
        audit_log(
            connection,
            actor_type="user",
            actor_id=current_user_id(),
            action="user_function.delete",
            target=f"user_function:{function_id}",
            result="success",
            details=f"name={target['name']}",
        )
        connection.commit()
        return jsonify({"status": "deleted", "id": function_id})
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


@app.route("/api/users/<int:user_id>/profile", methods=["PUT"])
@login_required
@role_required(ROLE_ADMINISTRATOR, permission="users.manage")
@csrf_required
def update_user_profile(user_id):
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"error": "invalid_request"}), 400

    fields = ("first_name", "last_name", "department")
    values = {}
    limits = {"first_name": 100, "last_name": 100, "department": 120}

    for field in fields:
        value = data.get(field, "")
        if not isinstance(value, str):
            return jsonify({"error": "invalid_user_profile"}), 400
        value = value.strip()
        if len(value) > limits[field]:
            return jsonify({"error": "invalid_user_profile"}), 400
        values[field] = value

    function_id = data.get("function_id")
    if function_id in ("", None):
        function_id = None
    elif isinstance(function_id, bool) or not isinstance(function_id, int) or function_id < 1:
        return jsonify({"error": "invalid_user_function"}), 400

    connection = get_connection()
    try:
        target = connection.execute(
            "SELECT id, username FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()
        if target is None:
            return jsonify({"error": "user_not_found"}), 404

        if function_id is not None:
            function = connection.execute(
                "SELECT id FROM user_functions WHERE id = ?",
                (function_id,),
            ).fetchone()
            if function is None:
                return jsonify({"error": "user_function_not_found"}), 400

        connection.execute("""
            UPDATE users
            SET first_name = ?,
                last_name = ?,
                department = ?,
                function_id = ?
            WHERE id = ?
        """, (
            values["first_name"],
            values["last_name"],
            values["department"],
            function_id,
            user_id,
        ))

        audit_log(
            connection,
            actor_type="user",
            actor_id=current_user_id(),
            action="user.profile.update",
            target=f"user:{user_id}",
            result="success",
            details=(
                f"username={target['username']}, "
                f"function_id={function_id}"
            ),
        )
        connection.commit()
        return jsonify({
            "status": "updated",
            "user_id": user_id,
            **values,
            "function_id": function_id,
        })
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


@app.route("/api/users", methods=["POST"])
@login_required
@role_required(ROLE_ADMINISTRATOR, permission="users.manage")
@csrf_required
def create_user():

    data = request.get_json(silent=True) or {}

    username = str(data.get("username", "")).strip()
    password = str(data.get("password", ""))
    role = str(data.get("role", "")).strip()
    permissions = data.get(
        "permissions",
        sorted(ROLE_DEFAULT_PERMISSIONS.get(role, ())),
    )

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

    if not validate_permission_selection(permissions):
        return jsonify({
            "error": "invalid_user_permissions"
        }), 400

    # Creating an account with no permissions is allowed for users.manage.
    # Assigning any permissions requires the separate delegation permission.
    if permissions and "permissions.manage" not in current_user_permissions():
        return jsonify({
            "error": "permission_delegation_required"
        }), 403

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
        connection.executemany(
            """
            INSERT INTO user_permissions (user_id, permission)
            VALUES (?, ?)
            """,
            [
                (user_id, permission)
                for permission in permissions
            ],
        )

        audit_log(
            connection,
            actor_type="user",
            actor_id=current_user_id(),
            action="user.create",
            target=f"user:{user_id}",
            result="success",
            details=(
                f"username={username}, role={role}, "
                f"permissions={','.join(sorted(permissions))}"
            ),
        )

        connection.commit()

        return jsonify({
            "status": "created",
            "user": {
                "id": user_id,
                "username": username,
                "role": role,
                "permissions": sorted(permissions),
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



@app.route("/api/users/<int:user_id>/permissions", methods=["PUT"])
@login_required
@role_required(ROLE_ADMINISTRATOR, permission="users.manage")
@csrf_required
def update_user_permissions(user_id):
    if "permissions.manage" not in current_user_permissions():
        return jsonify({
            "error": "permission_delegation_required"
        }), 403

    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return jsonify({"error": "invalid_request"}), 400

    role = data.get("role")
    permissions = data.get("permissions")

    if role not in VALID_ROLES:
        return jsonify({"error": "invalid_user_role"}), 400

    if not validate_permission_selection(permissions):
        return jsonify({"error": "invalid_user_permissions"}), 400

    connection = get_connection()

    try:
        connection.execute("BEGIN IMMEDIATE")
        target = connection.execute(
            "SELECT id, username, role, enabled FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()

        if target is None:
            return jsonify({"error": "user_not_found"}), 404

        had_user_management = "users.manage" in get_user_permissions(
            connection,
            user_id,
            target["role"],
        )

        if (
            target["enabled"]
            and had_user_management
            and "users.manage" not in permissions
            and count_active_user_managers(connection) <= 1
        ):
            return jsonify({
                "error": "last_enabled_administrator"
            }), 409

        had_permission_management = (
            "permissions.manage" in get_user_permissions(
                connection,
                user_id,
                target["role"],
            )
        )

        if (
            target["enabled"]
            and had_permission_management
            and "permissions.manage" not in permissions
            and count_active_permission_managers(connection) <= 1
        ):
            return jsonify({
                "error": "last_enabled_permission_manager"
            }), 409

        connection.execute(
            "UPDATE users SET role = ? WHERE id = ?",
            (role, user_id),
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
            [
                (user_id, permission)
                for permission in permissions
            ],
        )

        audit_log(
            connection,
            actor_type="user",
            actor_id=current_user_id(),
            action="user.permissions.update",
            target=f"user:{user_id}",
            result="success",
            details=(
                f"username={target['username']}, role={role}, "
                f"permissions={','.join(sorted(permissions))}"
            ),
        )
        connection.commit()

        return jsonify({
            "status": "updated",
            "user": {
                "id": user_id,
                "username": target["username"],
                "role": role,
                "permissions": sorted(permissions),
            },
        })
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


@app.route("/api/users/<int:user_id>/note", methods=["PUT"])
@login_required
@role_required(ROLE_ADMINISTRATOR, permission="users.manage")
@csrf_required
def update_user_admin_note(user_id):
    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return jsonify({"error": "invalid_request"}), 400

    note = data.get("note")
    if (
        not isinstance(note, str)
        or len(note) > ADMIN_NOTE_MAX_LENGTH
    ):
        return jsonify({"error": "invalid_admin_note"}), 400

    connection = get_connection()

    try:
        target = connection.execute(
            "SELECT username FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()

        if target is None:
            return jsonify({"error": "user_not_found"}), 404

        connection.execute(
            "UPDATE users SET admin_note = ? WHERE id = ?",
            (note.strip(), user_id),
        )
        audit_log(
            connection,
            actor_type="user",
            actor_id=current_user_id(),
            action="user.admin_note.update",
            target=f"user:{user_id}",
            result="success",
            details=(
                f"username={target['username']}, "
                f"note_length={len(note.strip())}"
            ),
        )
        connection.commit()

        return jsonify({
            "status": "updated",
            "user_id": user_id,
            "note": note.strip(),
        })
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


@app.route("/api/users/<int:user_id>", methods=["DELETE"])
@login_required
@role_required(ROLE_ADMINISTRATOR, permission="users.manage")
@csrf_required
def delete_user(user_id):
    actor_id = current_user_id()

    if actor_id == user_id:
        return jsonify({"error": "cannot_delete_self"}), 400

    connection = get_connection()

    try:
        connection.execute("BEGIN IMMEDIATE")
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

        target_permissions = get_user_permissions(
            connection,
            user_id,
            target["role"],
        )

        if (
            target["enabled"]
            and "users.manage" in target_permissions
            and count_active_user_managers(connection) <= 1
        ):
            return jsonify({
                "error": "last_enabled_administrator"
            }), 409

        if (
            target["enabled"]
            and {
                "permissions.manage",
                "users.manage",
                "clients.view",
            }.issubset(target_permissions)
            and count_active_permission_managers(connection) <= 1
        ):
            return jsonify({
                "error": "last_enabled_permission_manager"
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
@role_required(ROLE_ADMINISTRATOR, permission="clients.manage")
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
@role_required(ROLE_ADMINISTRATOR, permission="clients.manage")
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
@role_required(ROLE_ADMINISTRATOR, permission="clients.manage")
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
# CLIENT TELEMETRY
# ============================================================

TELEMETRY_RETENTION_DAYS = 7
TELEMETRY_MAX_HISTORY_HOURS = 168
TELEMETRY_MAX_RESPONSE_POINTS = 1000
TELEMETRY_MAX_COUNTER_VALUE = 2**63 - 1
# Counter deltas across longer gaps would hide real traffic peaks.
TELEMETRY_MAX_RATE_GAP_SECONDS = 300
TELEMETRY_STALE_SECONDS = 120
TELEMETRY_WIDGET_WIDTHS = (4, 6, 8, 12)
TELEMETRY_WIDGET_IDS = (
    "summary", "clients", "history", "events", "backup",
)
TELEMETRY_INTEGRATIONS = ("wazuh", "suricata")


def default_telemetry_dashboard_settings():
    return {
        "layout": [
            {"id": "summary", "width": 12, "visible": True},
            {"id": "clients", "width": 4, "visible": True},
            {"id": "history", "width": 8, "visible": True},
            {"id": "events", "width": 12, "visible": True},
            {"id": "backup", "width": 6, "visible": True},
        ],
        "thresholds": {"cpu": 90, "memory": 90, "disk": 90},
        "integrations": {"wazuh": False, "suricata": False},
    }


def validate_telemetry_dashboard_settings(settings):
    if not isinstance(settings, dict) or set(settings) != {
        "layout", "thresholds", "integrations",
    }:
        return False
    layout = settings["layout"]
    if not isinstance(layout, list) or len(layout) != len(TELEMETRY_WIDGET_IDS):
        return False
    seen = set()
    for widget in layout:
        if (
            not isinstance(widget, dict)
            or set(widget) != {"id", "width", "visible"}
            or widget["id"] not in TELEMETRY_WIDGET_IDS
            or widget["id"] in seen
            or isinstance(widget["width"], bool)
            or widget["width"] not in TELEMETRY_WIDGET_WIDTHS
            or not isinstance(widget["visible"], bool)
        ):
            return False
        seen.add(widget["id"])
    thresholds = settings["thresholds"]
    if (
        not isinstance(thresholds, dict)
        or set(thresholds) != {"cpu", "memory", "disk"}
        or any(
            isinstance(value, bool)
            or not isinstance(value, int)
            or not 50 <= value <= 99
            for value in thresholds.values()
        )
    ):
        return False
    integrations = settings["integrations"]
    return (
        isinstance(integrations, dict)
        and set(integrations) == set(TELEMETRY_INTEGRATIONS)
        and all(isinstance(value, bool) for value in integrations.values())
    )


def migrate_telemetry_dashboard_settings(settings):
    if (
        not isinstance(settings, dict)
        or not isinstance(settings.get("layout"), list)
        or not any(
            isinstance(widget, dict) and widget.get("id") == "system"
            for widget in settings["layout"]
        )
    ):
        return settings

    migrated = dict(settings)
    migrated["layout"] = [
        widget for widget in settings["layout"]
        if not (isinstance(widget, dict) and widget.get("id") == "system")
    ]
    return migrated


def parse_telemetry_time(value):
    try:
        parsed = datetime.fromisoformat(value)
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def add_network_rates(rows):
    """Turn cumulative byte counters into bytes per second.

    Rows must be ordered by time. A rate is None when counters are missing,
    were reset (reboot), or the gap between samples is too long.
    """
    samples = []
    previous = None
    for row in rows:
        sample = dict(row)
        rx = sample.pop("network_rx_bytes", None)
        tx = sample.pop("network_tx_bytes", None)
        sample["network_rx_bytes_per_second"] = None
        sample["network_tx_bytes_per_second"] = None

        current_time = parse_telemetry_time(sample["recorded_at"])
        if (
            previous is not None
            and current_time is not None
            and rx is not None
            and tx is not None
        ):
            prev_time, prev_rx, prev_tx = previous
            seconds = (current_time - prev_time).total_seconds()
            if (
                prev_rx is not None
                and 0 < seconds <= TELEMETRY_MAX_RATE_GAP_SECONDS
                and rx >= prev_rx
                and tx >= prev_tx
            ):
                sample["network_rx_bytes_per_second"] = round(
                    (rx - prev_rx) / seconds, 2
                )
                sample["network_tx_bytes_per_second"] = round(
                    (tx - prev_tx) / seconds, 2
                )

        previous = (
            (current_time, rx, tx) if current_time is not None else None
        )
        samples.append(sample)
    return samples


def validate_system_snapshot(system):
    def is_counter(value):
        return (
            isinstance(value, int)
            and not isinstance(value, bool)
            and 0 <= value <= TELEMETRY_MAX_COUNTER_VALUE
        )

    def is_text(value, maximum):
        return isinstance(value, str) and bool(value.strip()) and len(value) <= maximum

    def is_optional_bool(value):
        return value is None or isinstance(value, bool)

    required = {
        "load_average", "uptime_seconds", "os", "kernel", "disk",
        "interfaces", "dns_servers", "gateway", "gateway_reachable",
        "dns_reachable", "internet_reachable", "temperatures", "fans",
        "services", "containers",
    }
    if not isinstance(system, dict) or set(system) not in (
        required, required | {"security_events"}
    ):
        return False

    loads = system["load_average"]
    if loads is not None and (
        not isinstance(loads, list)
        or len(loads) != 3
        or any(
            not isinstance(value, (int, float))
            or isinstance(value, bool)
            or value < 0
            or value > 1_000_000
            or not math.isfinite(value)
            for value in loads
        )
    ):
        return False

    uptime = system["uptime_seconds"]
    if uptime is not None and not is_counter(uptime):
        return False
    if not is_text(system["os"], 128) or not is_text(system["kernel"], 128):
        return False

    disk = system["disk"]
    if disk is not None and (
        not isinstance(disk, dict)
        or set(disk) != {"total_bytes", "used_bytes", "free_bytes"}
        or not all(is_counter(disk[key]) for key in disk)
        or disk["total_bytes"] <= 0
        or disk["used_bytes"] > disk["total_bytes"]
        or disk["free_bytes"] > disk["total_bytes"]
    ):
        return False

    interfaces = system["interfaces"]
    if not isinstance(interfaces, list) or len(interfaces) > 32:
        return False
    interface_names = set()
    for interface in interfaces:
        if (
            not isinstance(interface, dict)
            or set(interface) != {
                "name", "state", "rx_bytes", "tx_bytes", "rx_errors",
                "tx_errors", "rx_dropped", "tx_dropped",
            }
            or not is_text(interface["name"], 32)
            or interface["name"] in interface_names
            or interface["state"] not in (
                "up", "down", "unknown", "dormant", "lowerlayerdown"
            )
            or not all(
                is_counter(interface[key])
                for key in (
                    "rx_bytes", "tx_bytes", "rx_errors", "tx_errors",
                    "rx_dropped", "tx_dropped",
                )
            )
        ):
            return False
        interface_names.add(interface["name"])

    dns_servers = system["dns_servers"]
    if not isinstance(dns_servers, list) or len(dns_servers) > 8:
        return False
    try:
        if any(
            not isinstance(server, str)
            or str(ipaddress.ip_address(server)) != server
            for server in dns_servers
        ):
            return False
        if system["gateway"] is not None:
            if not isinstance(system["gateway"], str):
                return False
            ipaddress.IPv4Address(system["gateway"])
    except (ipaddress.AddressValueError, TypeError):
        return False

    if not all(
        is_optional_bool(system[key])
        for key in (
            "gateway_reachable", "dns_reachable", "internet_reachable"
        )
    ):
        return False

    temperatures = system["temperatures"]
    if not isinstance(temperatures, list) or len(temperatures) > 16:
        return False
    for sensor in temperatures:
        value = sensor.get("celsius") if isinstance(sensor, dict) else None
        if (
            not isinstance(sensor, dict)
            or set(sensor) != {"name", "celsius"}
            or not is_text(sensor["name"], 64)
            or not isinstance(value, (int, float))
            or isinstance(value, bool)
            or not -50 <= value <= 250
            or not math.isfinite(value)
        ):
            return False

    fans = system["fans"]
    if not isinstance(fans, list) or len(fans) > 16:
        return False
    for fan in fans:
        if (
            not isinstance(fan, dict)
            or set(fan) != {"name", "rpm"}
            or not is_text(fan["name"], 64)
            or not is_counter(fan["rpm"])
            or fan["rpm"] > 100_000
        ):
            return False

    legacy_snapshot = "security_events" not in system
    for key, max_items in (
        ("services", 60 if legacy_snapshot else 20),
        ("containers", 60),
    ):
        collection = system[key]
        if (
            not isinstance(collection, dict)
            or set(collection) != {"available", "items"}
            or not isinstance(collection["available"], bool)
            or not isinstance(collection["items"], list)
            or len(collection["items"]) > max_items
        ):
            return False
        for item in collection["items"]:
            if key == "services":
                if not isinstance(item, dict) or not is_text(item.get("name"), 128):
                    return False
                if set(item) == {"name", "state"}:
                    if item["state"] not in ("active", "failed", "inactive"):
                        return False
                elif (
                    set(item) != {
                        "name", "state", "substate", "restarts",
                        "runtime_seconds",
                    }
                    or item["state"] not in (
                        "active", "failed", "inactive", "unknown"
                    )
                    or not is_text(item["substate"], 64)
                    or (
                        item["restarts"] is not None
                        and not is_counter(item["restarts"])
                    )
                    or (
                        item["runtime_seconds"] is not None
                        and not is_counter(item["runtime_seconds"])
                    )
                ):
                    return False
            elif (
                not isinstance(item, dict)
                or set(item) != {"runtime", "name", "state"}
                or item["runtime"] not in ("docker", "podman")
                or not is_text(item["name"], 128)
                or not is_text(item["state"], 64)
                or (
                    not legacy_snapshot
                    and item["state"] not in (
                        "up", "stopped", "unhealthy", "unknown"
                    )
                )
            ):
                return False

    if legacy_snapshot:
        try:
            return len(json.dumps(system, allow_nan=False).encode("utf-8")) <= 32768
        except (TypeError, ValueError):
            return False

    events = system["security_events"]
    if not isinstance(events, dict) or set(events) != {
        "ssh_available", "ssh_failed_24h", "ssh_last_failed_at",
        "journal_available", "journal_errors_1h", "journal_warnings_1h",
        "login_history_available", "login_events",
        "boot_history_available", "boot_history",
    }:
        return False
    for key in (
        "ssh_available", "journal_available",
        "login_history_available", "boot_history_available",
    ):
        if not isinstance(events[key], bool):
            return False
    for key in (
        "ssh_failed_24h", "journal_errors_1h", "journal_warnings_1h",
    ):
        if not is_counter(events[key]):
            return False
    last_ssh = events["ssh_last_failed_at"]
    if last_ssh is not None and (
        not is_text(last_ssh, 64) or parse_telemetry_time(last_ssh) is None
    ):
        return False
    login_events = events["login_events"]
    if not isinstance(login_events, list) or len(login_events) > 20:
        return False
    for event in login_events:
        if (
            not isinstance(event, dict)
            or set(event) != {"timestamp", "action"}
            or not is_text(event["timestamp"], 64)
            or parse_telemetry_time(event["timestamp"]) is None
            or event["action"] not in ("login", "logout")
        ):
            return False
    boot_history = events["boot_history"]
    if not isinstance(boot_history, list) or len(boot_history) > 10:
        return False
    for boot in boot_history:
        if (
            not isinstance(boot, dict)
            or set(boot) != {"started_at", "ended_at"}
            or not is_text(boot["started_at"], 64)
            or not is_text(boot["ended_at"], 64)
        ):
            return False

    try:
        return len(json.dumps(system, allow_nan=False).encode("utf-8")) <= 32768
    except (TypeError, ValueError):
        return False


def add_system_interface_rates(system, previous, seconds):
    result = dict(system)
    previous_interfaces = {
        interface["name"]: interface
        for interface in (previous or {}).get("interfaces", [])
    }
    interfaces = []
    for interface in system["interfaces"]:
        current = dict(interface)
        old = previous_interfaces.get(current["name"])
        rx_rate = None
        tx_rate = None
        if old and 0 < seconds <= TELEMETRY_MAX_RATE_GAP_SECONDS:
            if current["rx_bytes"] >= old["rx_bytes"]:
                rx_rate = round(
                    (current["rx_bytes"] - old["rx_bytes"]) / seconds, 2
                )
            if current["tx_bytes"] >= old["tx_bytes"]:
                tx_rate = round(
                    (current["tx_bytes"] - old["tx_bytes"]) / seconds, 2
                )
        current["rx_bytes_per_second"] = rx_rate
        current["tx_bytes_per_second"] = tx_rate
        interfaces.append(current)
    result["interfaces"] = interfaces
    return result


def record_telemetry_system_events(
    connection, client_id, recorded_at, previous, current
):
    previous_services = {
        item["name"]: item["state"]
        for item in (previous or {}).get("services", {}).get("items", [])
    }
    for service in current.get("services", {}).get("items", []):
        name = service["name"]
        old_state = previous_services.get(name)
        state = service["state"]
        if state == "failed" and old_state != "failed":
            event_type = "service_failed"
        elif state in ("active", "inactive") and old_state == "failed":
            event_type = "service_recovered"
        else:
            continue
        connection.execute(
            """
            INSERT INTO client_telemetry_events (
                client_id, recorded_at, event_type, metric, value
            ) VALUES (?, ?, ?, ?, NULL)
            """,
            (client_id, recorded_at, event_type, name),
        )

    security = current.get("security_events", {})
    old_security = (previous or {}).get("security_events", {})
    last_failed = parse_telemetry_time(
        security.get("ssh_last_failed_at")
    )
    previous_failed = parse_telemetry_time(
        old_security.get("ssh_last_failed_at")
    )
    recorded_time = parse_telemetry_time(recorded_at)
    if (
        last_failed is not None
        and (previous_failed is None or last_failed > previous_failed)
        and recorded_time is not None
        and last_failed <= recorded_time + timedelta(minutes=5)
    ):
        connection.execute(
            """
            INSERT INTO client_telemetry_events (
                client_id, recorded_at, event_type, metric, value
            ) VALUES (?, ?, 'ssh_failure', 'ssh', ?)
            """,
            (
                client_id,
                last_failed.isoformat(),
                security.get("ssh_failed_24h"),
            ),
        )


@app.route("/api/telemetry", methods=["POST"])
@client_auth_required
def ingest_telemetry():
    client = authenticated_client()
    data = request.get_json(silent=True)

    required_fields = {
        "cpu_percent",
        "memory_percent",
        "memory_total_bytes",
        "memory_available_bytes",
    }
    network_fields = {"network_rx_bytes", "network_tx_bytes"}
    optional_fields = network_fields | {"system"}

    if (
        not isinstance(data, dict)
        or not required_fields <= set(data)
        or not set(data) <= required_fields | optional_fields
        or len(set(data) & network_fields) == 1
    ):
        return jsonify({
            "status": "error",
            "message": "Invalid telemetry payload",
        }), 400

    cpu = data["cpu_percent"]
    memory = data["memory_percent"]
    memory_total = data["memory_total_bytes"]
    memory_available = data["memory_available_bytes"]
    network_rx = data.get("network_rx_bytes")
    network_tx = data.get("network_tx_bytes")

    def valid_counter(value):
        return (
            isinstance(value, int)
            and not isinstance(value, bool)
            and 0 <= value <= TELEMETRY_MAX_COUNTER_VALUE
        )

    def valid_percentage(value):
        return (
            isinstance(value, (int, float))
            and not isinstance(value, bool)
            and math.isfinite(value)
            and 0 <= value <= 100
        )

    if (
        not valid_percentage(cpu)
        or not valid_percentage(memory)
        or isinstance(memory_total, bool)
        or not isinstance(memory_total, int)
        or memory_total <= 0
        or isinstance(memory_available, bool)
        or not isinstance(memory_available, int)
        or memory_available < 0
        or memory_available > memory_total
        or (
            "network_rx_bytes" in data
            and not (valid_counter(network_rx) and valid_counter(network_tx))
        )
        or ("system" in data and not validate_system_snapshot(data["system"]))
    ):
        return jsonify({
            "status": "error",
            "message": "Invalid telemetry values",
        }), 400

    now = datetime.now(timezone.utc)
    recorded_at = now.isoformat()
    cutoff = (
        now - timedelta(days=TELEMETRY_RETENTION_DAYS)
    ).isoformat()

    connection = get_connection()
    try:
        if "system" in data:
            previous_row = connection.execute(
                """
                SELECT recorded_at, payload_json
                FROM client_system_status
                WHERE client_id = ?
                """,
                (client["id"],),
            ).fetchone()
            previous = None
            elapsed = 0
            if previous_row is not None:
                previous = json.loads(previous_row["payload_json"])
                previous_time = parse_telemetry_time(
                    previous_row["recorded_at"]
                )
                current_time = parse_telemetry_time(recorded_at)
                if previous_time is not None and current_time is not None:
                    elapsed = (
                        current_time - previous_time
                    ).total_seconds()

            record_telemetry_system_events(
                connection,
                client["id"],
                recorded_at,
                previous,
                data["system"],
            )
            system = add_system_interface_rates(
                data["system"], previous, elapsed
            )
            connection.execute(
                """
                INSERT INTO client_system_status (
                    client_id, recorded_at, payload_json
                ) VALUES (?, ?, ?)
                ON CONFLICT(client_id) DO UPDATE SET
                    recorded_at = excluded.recorded_at,
                    payload_json = excluded.payload_json
                """,
                (
                    client["id"],
                    recorded_at,
                    json.dumps(system, allow_nan=False),
                ),
            )

        connection.execute(
            """
            INSERT INTO client_telemetry (
                client_id, recorded_at, cpu_percent, memory_percent,
                memory_total_bytes, memory_available_bytes,
                network_rx_bytes, network_tx_bytes, disk_percent
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                client["id"], recorded_at, float(cpu), float(memory),
                memory_total, memory_available, network_rx, network_tx,
                (
                    round(
                        100 * data["system"]["disk"]["used_bytes"]
                        / data["system"]["disk"]["total_bytes"],
                        2,
                    )
                    if (
                        data.get("system")
                        and data["system"].get("disk")
                    )
                    else None
                ),
            ),
        )
        connection.execute(
            "DELETE FROM client_telemetry WHERE recorded_at < ?",
            (cutoff,),
        )
        connection.execute(
            "DELETE FROM client_telemetry_events WHERE recorded_at < ?",
            (cutoff,),
        )
        connection.commit()
    except (sqlite3.Error, json.JSONDecodeError):
        connection.rollback()
        logger.exception(
            "Failed to save telemetry from client %s", client["id"]
        )
        return jsonify({
            "status": "error",
            "message": "Failed to save telemetry",
        }), 500
    finally:
        connection.close()

    return jsonify({"status": "received"}), 200


@app.route(
    "/api/clients/<int:client_id>/telemetry",
    methods=["GET"],
)
@login_required
@role_required(
    ROLE_ADMINISTRATOR,
    ROLE_OPERATOR,
    ROLE_VIEWER,
    permission="clients.view",
)
def client_telemetry(client_id):
    try:
        hours = int(request.args.get("hours", "24"))
    except (TypeError, ValueError):
        return jsonify({"error": "invalid_hours"}), 400

    if not 1 <= hours <= TELEMETRY_MAX_HISTORY_HOURS:
        return jsonify({"error": "invalid_hours"}), 400

    connection = get_connection()
    try:
        client = connection.execute(
            """
            SELECT id, hostname
            FROM clients
            WHERE id = ? AND enabled = 1
            """,
            (client_id,),
        ).fetchone()

        if client is None:
            return jsonify({"error": "client_not_found"}), 404

        rows = telemetry_history_rows(connection, client_id, hours)

        return jsonify({
            "client_id": client_id,
            "hostname": client["hostname"],
            "hours": hours,
            "samples": rows,
        })
    except sqlite3.Error:
        logger.exception(
            "Failed to load telemetry for client %s", client_id
        )
        return jsonify({"error": "telemetry_query_failed"}), 500
    finally:
        connection.close()


@app.route("/api/telemetry/dashboard-settings", methods=["GET", "PUT"])
@login_required
@role_required(
    ROLE_ADMINISTRATOR,
    ROLE_OPERATOR,
    ROLE_VIEWER,
    permission="clients.view",
)
@csrf_required
def telemetry_dashboard_settings():
    connection = get_connection()
    user_id = current_user_id()
    try:
        if request.method == "GET":
            row = connection.execute(
                """
                SELECT settings_json
                FROM user_dashboard_settings
                WHERE user_id = ?
                """,
                (user_id,),
            ).fetchone()
            if row is None:
                return jsonify(default_telemetry_dashboard_settings())
            settings = json.loads(row["settings_json"])
            migrated = migrate_telemetry_dashboard_settings(settings)
            if migrated != settings and validate_telemetry_dashboard_settings(
                migrated
            ):
                settings = migrated
                connection.execute(
                    """
                    UPDATE user_dashboard_settings
                    SET settings_json = ?, updated_at = ?
                    WHERE user_id = ?
                    """,
                    (
                        json.dumps(
                            settings, separators=(",", ":"), allow_nan=False
                        ),
                        datetime.now(timezone.utc).isoformat(),
                        user_id,
                    ),
                )
                connection.commit()
            if not validate_telemetry_dashboard_settings(settings):
                logger.error(
                    "Invalid telemetry dashboard settings for user %s",
                    user_id,
                )
                return jsonify({"error": "dashboard_settings_invalid"}), 500
            return jsonify(settings)

        settings = request.get_json(silent=True)
        if not validate_telemetry_dashboard_settings(settings):
            return jsonify({"error": "invalid_dashboard_settings"}), 400
        connection.execute(
            """
            INSERT INTO user_dashboard_settings (
                user_id, settings_json, updated_at
            ) VALUES (?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                settings_json = excluded.settings_json,
                updated_at = excluded.updated_at
            """,
            (
                user_id,
                json.dumps(settings, separators=(",", ":"), allow_nan=False),
                datetime.now(timezone.utc).isoformat(),
            ),
        )
        connection.commit()
        return jsonify({"status": "saved"})
    except (sqlite3.Error, json.JSONDecodeError):
        connection.rollback()
        logger.exception(
            "Unable to load or save telemetry dashboard settings for user %s",
            user_id,
        )
        return jsonify({"error": "dashboard_settings_failed"}), 500
    finally:
        connection.close()


def telemetry_history_rows(connection, client_id, hours, downsample=True):
    cutoff = (
        datetime.now(timezone.utc) - timedelta(hours=hours)
    ).isoformat()
    rows = connection.execute(
        """
        SELECT recorded_at, cpu_percent, memory_percent,
               memory_total_bytes, memory_available_bytes,
               network_rx_bytes, network_tx_bytes, disk_percent
        FROM client_telemetry
        WHERE client_id = ? AND recorded_at >= ?
        ORDER BY recorded_at ASC
        """,
        (client_id, cutoff),
    ).fetchall()
    rows = add_network_rates(rows)
    if downsample and len(rows) > TELEMETRY_MAX_RESPONSE_POINTS:
        last_index = len(rows) - 1
        denominator = TELEMETRY_MAX_RESPONSE_POINTS - 1
        rows = [
            rows[(index * last_index + denominator // 2) // denominator]
            for index in range(TELEMETRY_MAX_RESPONSE_POINTS)
        ]
    return rows


def telemetry_events_from_rows(rows, thresholds, now=None):
    now = now or datetime.now(timezone.utc)
    events = []
    active = {"cpu": False, "memory": False, "disk": False}
    previous_time = None
    metric_keys = (
        ("cpu", "cpu_percent"),
        ("memory", "memory_percent"),
        ("disk", "disk_percent"),
    )
    for row in rows:
        recorded = parse_telemetry_time(row["recorded_at"])
        if recorded is None:
            continue
        if previous_time is not None:
            gap = (recorded - previous_time).total_seconds()
            if gap > TELEMETRY_STALE_SECONDS:
                events.append({
                    "timestamp": (
                        previous_time
                        + timedelta(seconds=TELEMETRY_STALE_SECONDS)
                    ).isoformat(),
                    "kind": "telemetry_lost",
                    "metric": None,
                    "value": None,
                    "threshold": None,
                })
                events.append({
                    "timestamp": recorded.isoformat(),
                    "kind": "telemetry_restored",
                    "metric": None,
                    "value": None,
                    "threshold": None,
                })
        for metric, key in metric_keys:
            value = row[key]
            exceeded = value is not None and value >= thresholds[metric]
            if exceeded and not active[metric]:
                events.append({
                    "timestamp": recorded.isoformat(),
                    "kind": "threshold_exceeded",
                    "metric": metric,
                    "value": value,
                    "threshold": thresholds[metric],
                })
            elif not exceeded and active[metric]:
                events.append({
                    "timestamp": recorded.isoformat(),
                    "kind": "threshold_recovered",
                    "metric": metric,
                    "value": value,
                    "threshold": thresholds[metric],
                })
            active[metric] = exceeded
        previous_time = recorded

    if previous_time is not None:
        if (now - previous_time).total_seconds() > TELEMETRY_STALE_SECONDS:
            events.append({
                "timestamp": (
                    previous_time
                    + timedelta(seconds=TELEMETRY_STALE_SECONDS)
                ).isoformat(),
                "kind": "telemetry_lost",
                "metric": None,
                "value": None,
                "threshold": None,
            })
    return sorted(events, key=lambda event: event["timestamp"], reverse=True)[:500]


def parse_telemetry_hours():
    try:
        hours = int(request.args.get("hours", "24"))
    except (TypeError, ValueError):
        return None
    return hours if 1 <= hours <= TELEMETRY_MAX_HISTORY_HOURS else None


def csv_response(filename, fieldnames, rows):
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=fieldnames, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(rows)
    return Response(
        output.getvalue(),
        content_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "no-store",
        },
    )


@app.route(
    "/api/clients/<int:client_id>/telemetry/events",
    methods=["GET"],
)
@login_required
@role_required(
    ROLE_ADMINISTRATOR,
    ROLE_OPERATOR,
    ROLE_VIEWER,
    permission="clients.view",
)
def client_telemetry_events(client_id):
    hours = parse_telemetry_hours()
    if hours is None:
        return jsonify({"error": "invalid_hours"}), 400
    connection = get_connection()
    try:
        client = connection.execute(
            "SELECT id, hostname FROM clients WHERE id = ? AND enabled = 1",
            (client_id,),
        ).fetchone()
        if client is None:
            return jsonify({"error": "client_not_found"}), 404
        settings_row = connection.execute(
            """
            SELECT settings_json FROM user_dashboard_settings WHERE user_id = ?
            """,
            (current_user_id(),),
        ).fetchone()
        settings = (
            json.loads(settings_row["settings_json"])
            if settings_row else default_telemetry_dashboard_settings()
        )
        settings = migrate_telemetry_dashboard_settings(settings)
        if not validate_telemetry_dashboard_settings(settings):
            return jsonify({"error": "dashboard_settings_invalid"}), 500
        rows = telemetry_history_rows(
            connection, client_id, hours, downsample=False
        )
        events = telemetry_events_from_rows(
            rows, settings["thresholds"]
        )
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
        persisted_rows = connection.execute(
            """
            SELECT recorded_at, event_type, metric, value
            FROM client_telemetry_events
            WHERE client_id = ? AND recorded_at >= ?
            ORDER BY recorded_at DESC
            LIMIT 500
            """,
            (client_id, cutoff.isoformat()),
        ).fetchall()
        events.extend({
            "timestamp": row["recorded_at"],
            "kind": row["event_type"],
            "metric": row["metric"],
            "value": row["value"],
            "threshold": None,
        } for row in persisted_rows)
        system_row = connection.execute(
            """
            SELECT recorded_at, payload_json
            FROM client_system_status
            WHERE client_id = ?
            """,
            (client_id,),
        ).fetchone()
        if system_row is not None:
            system_time = parse_telemetry_time(system_row["recorded_at"])
            system = json.loads(system_row["payload_json"])
            security = system.get("security_events", {})
            failed_at = parse_telemetry_time(
                security.get("ssh_last_failed_at")
            )
            if failed_at is not None and failed_at >= cutoff:
                if not any(
                    event["kind"] == "ssh_failure"
                    and event["metric"] == "ssh"
                    for event in events
                ):
                    events.append({
                        "timestamp": failed_at.isoformat(),
                        "kind": "ssh_failure",
                        "metric": "ssh",
                        "value": security.get("ssh_failed_24h"),
                        "threshold": None,
                    })
            services = system.get("services", {}).get("items", [])
            if system_time is not None and system_time >= cutoff:
                for service in services:
                    if service.get("state") == "failed":
                        name = service.get("name", "service")
                        if not any(
                            event["kind"] == "service_failed"
                            and event["metric"] == name
                            for event in events
                        ):
                            events.append({
                                "timestamp": system_time.isoformat(),
                                "kind": "service_failed",
                                "metric": name,
                                "value": None,
                                "threshold": None,
                            })
        events = sorted(
            events,
            key=lambda event: event["timestamp"],
            reverse=True,
        )[:500]
        export_format = request.args.get("format", "json").lower()
        if export_format == "csv":
            return csv_response(
                f"telemetry-events-client-{client_id}.csv",
                ("timestamp", "kind", "metric", "value", "threshold"),
                events,
            )
        if export_format != "json":
            return jsonify({"error": "invalid_format"}), 400
        return jsonify({
            "client_id": client_id,
            "hostname": client["hostname"],
            "hours": hours,
            "events": events,
        })
    except (sqlite3.Error, json.JSONDecodeError):
        logger.exception(
            "Failed to load telemetry events for client %s", client_id
        )
        return jsonify({"error": "telemetry_events_query_failed"}), 500
    finally:
        connection.close()


@app.route(
    "/api/clients/<int:client_id>/telemetry/export",
    methods=["GET"],
)
@login_required
@role_required(
    ROLE_ADMINISTRATOR,
    ROLE_OPERATOR,
    ROLE_VIEWER,
    permission="clients.view",
)
def export_client_telemetry(client_id):
    hours = parse_telemetry_hours()
    if hours is None:
        return jsonify({"error": "invalid_hours"}), 400
    export_format = request.args.get("format", "csv").lower()
    if export_format not in ("csv", "json"):
        return jsonify({"error": "invalid_format"}), 400
    connection = get_connection()
    try:
        client = connection.execute(
            "SELECT id, hostname FROM clients WHERE id = ? AND enabled = 1",
            (client_id,),
        ).fetchone()
        if client is None:
            return jsonify({"error": "client_not_found"}), 404
        rows = telemetry_history_rows(
            connection, client_id, hours, downsample=False
        )
        fields = (
            "recorded_at", "cpu_percent", "memory_percent",
            "memory_total_bytes", "memory_available_bytes", "disk_percent",
            "network_rx_bytes_per_second", "network_tx_bytes_per_second",
        )
        samples = [{key: row.get(key) for key in fields} for row in rows]
        if export_format == "csv":
            return csv_response(
                f"telemetry-client-{client_id}-{hours}h.csv",
                fields,
                samples,
            )
        response = jsonify({
            "client_id": client_id,
            "hostname": client["hostname"],
            "hours": hours,
            "samples": samples,
        })
        response.headers["Content-Disposition"] = (
            f'attachment; filename="telemetry-client-{client_id}-{hours}h.json"'
        )
        response.headers["Cache-Control"] = "no-store"
        return response
    except sqlite3.Error:
        logger.exception(
            "Failed to export telemetry for client %s", client_id
        )
        return jsonify({"error": "telemetry_export_failed"}), 500
    finally:
        connection.close()


@app.route("/api/telemetry/overview", methods=["GET"])
@login_required
@role_required(
    ROLE_ADMINISTRATOR,
    ROLE_OPERATOR,
    ROLE_VIEWER,
    permission="clients.view",
)
def telemetry_overview():
    connection = get_connection()
    try:
        clients = connection.execute(
            """
            SELECT id, hostname, last_seen
            FROM clients
            WHERE enabled = 1
            ORDER BY hostname COLLATE NOCASE
            """
        ).fetchall()

        now = datetime.now(timezone.utc)
        result = []
        for client in clients:
            latest_rows = connection.execute(
                """
                SELECT recorded_at, cpu_percent, memory_percent,
                       memory_total_bytes, memory_available_bytes,
                       network_rx_bytes, network_tx_bytes
                FROM client_telemetry
                WHERE client_id = ?
                ORDER BY recorded_at DESC
                LIMIT 2
                """,
                (client["id"],),
            ).fetchall()
            samples = add_network_rates(reversed(latest_rows))
            latest = samples[-1] if samples else None

            age = None
            if latest is not None:
                recorded = parse_telemetry_time(latest["recorded_at"])
                if recorded is not None:
                    age = max(0, int((now - recorded).total_seconds()))

            system_row = connection.execute(
                """
                SELECT recorded_at, payload_json
                FROM client_system_status
                WHERE client_id = ?
                """,
                (client["id"],),
            ).fetchone()
            system_age = None
            system = None
            if system_row is not None:
                system_recorded = parse_telemetry_time(
                    system_row["recorded_at"]
                )
                if system_recorded is not None:
                    system_age = max(
                        0, int((now - system_recorded).total_seconds())
                    )
                system = json.loads(system_row["payload_json"])

            result.append({
                "client_id": client["id"],
                "hostname": client["hostname"],
                "status": classify_health_client(client["last_seen"]),
                "last_seen": client["last_seen"],
                "telemetry_age_seconds": age,
                "telemetry_stale": (
                    age is None or age > TELEMETRY_STALE_SECONDS
                ),
                "system_age_seconds": system_age,
                "system": system,
                "latest": latest,
            })

        return jsonify({"clients": result})
    except (sqlite3.Error, json.JSONDecodeError):
        logger.exception("Failed to load telemetry overview")
        return jsonify({"error": "telemetry_query_failed"}), 500
    finally:
        connection.close()


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

    if not validate_client_report(data):
        return jsonify({
            "status": "error",
            "message": "Invalid client report data",
        }), 400

    try:
        save_client_report(client["id"], data)
    except sqlite3.Error:
        logger.exception(
            "Failed to save report from client %s",
            client["id"],
        )
        return jsonify({
            "status": "error",
            "message": "Failed to save client report",
        }), 500

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
    permission="clients.view",
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
    permission="clients.view",
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
    permission="updates.view",
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
    permission="software.view",
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
@role_required(
    ROLE_ADMINISTRATOR,
    ROLE_OPERATOR,
    permission="packages.search",
)
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
@role_required(
    ROLE_ADMINISTRATOR,
    ROLE_OPERATOR,
    permission="jobs.manage",
)
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

    # Prevent empty whole-system update jobs.
    if action == "UPDATE_SYSTEM":
        cursor.execute("""
            SELECT COUNT(*)
            FROM available_updates
            WHERE client_id = ?
        """, (client_id,))
        available_update_count = cursor.fetchone()[0]

        if available_update_count == 0:
            connection.close()
            return jsonify({
                "status": "error",
                "message": "No system updates are available. No job was created."
            }), 409

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
    permission="updates.view",
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
@role_required(
    ROLE_ADMINISTRATOR,
    ROLE_OPERATOR,
    permission="packages.search",
)
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
    permission="updates.view",
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
    permission="updates.view",
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
    permission="updates.view",
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
