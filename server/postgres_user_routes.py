"""PostgreSQL-native user and permission management routes."""

from __future__ import annotations

import json
from datetime import datetime, timezone

from flask import current_app, jsonify, render_template, request, session
from psycopg.errors import UniqueViolation

if __package__:
    from .db_errors import DatabaseDriverError
    from .db_transactions import transaction
    from .i18n import browser_language, normalize_language, translate
    from .postgres_audit import audit_log
    from .postgres_flask_security import (
        csrf_required,
        current_user_id,
        current_user_permissions,
        current_user_role,
        get_csrf_token,
        login_required,
        role_required,
    )
    from .postgres_rbac import (
        PostgresRBACError,
        resolve_user_permissions,
        store_user_permissions,
    )
    from .rbac_lock import acquire_rbac_write_lock
    from .security import (
        PERMISSIONS,
        PERMISSION_DEPENDENCIES,
        ROLE_ADMINISTRATOR,
        ROLE_DEFAULT_PERMISSIONS,
        ROLE_DESCRIPTIONS,
        VALID_ROLES,
        hash_password,
    )
else:
    from db_errors import DatabaseDriverError
    from db_transactions import transaction
    from i18n import browser_language, normalize_language, translate
    from postgres_audit import audit_log
    from postgres_flask_security import (
        csrf_required,
        current_user_id,
        current_user_permissions,
        current_user_role,
        get_csrf_token,
        login_required,
        role_required,
    )
    from postgres_rbac import (
        PostgresRBACError,
        resolve_user_permissions,
        store_user_permissions,
    )
    from rbac_lock import acquire_rbac_write_lock
    from security import (
        PERMISSIONS,
        PERMISSION_DEPENDENCIES,
        ROLE_ADMINISTRATOR,
        ROLE_DEFAULT_PERMISSIONS,
        ROLE_DESCRIPTIONS,
        VALID_ROLES,
        hash_password,
    )


ADMIN_NOTE_MAX_LENGTH = 2000
USERNAME_MAX_LENGTH = 64
PASSWORD_MIN_LENGTH = 12
FUNCTION_NAME_MAX_LENGTH = 100


class _UserTransactionAbort(Exception):
    """Abort a transaction and return a controlled HTTP response."""

    def __init__(self, payload: dict, status_code: int):
        super().__init__("User-management transaction aborted")
        self.payload = payload
        self.status_code = status_code


def _get_connection():
    factory = current_app.config.get("LUMS_POSTGRES_GET_CONNECTION")
    if not callable(factory):
        raise RuntimeError("PostgreSQL connection factory is not configured")
    return factory()


def _database_error(operation: str):
    current_app.logger.exception(
        "PostgreSQL user-management operation failed: %s",
        operation,
    )
    return jsonify({"error": "database_unavailable"}), 500


def _permission_ui_context():
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


def _json_object():
    data = request.get_json(silent=True)
    return data if isinstance(data, dict) else None


def _validate_permission_input(value):
    """Validate JSON permission values before set conversion."""
    if not isinstance(value, list):
        raise ValueError("Permissions must be a list")

    if any(not isinstance(item, str) for item in value):
        raise ValueError("Permission names must be strings")

    if len(value) != len(set(value)):
        raise ValueError("Duplicate permissions are not allowed")

    selected = set(value)
    unknown = selected - set(PERMISSIONS)
    if unknown:
        raise ValueError("Unknown permissions")

    for permission in selected:
        missing = PERMISSION_DEPENDENCIES.get(permission, set()) - selected
        if missing:
            raise ValueError("Permission dependencies are missing")

    return selected


def _active_users_with_permission(connection, permission: str) -> int:
    """Count enabled users using their effective, fail-closed RBAC state."""
    rows = connection.execute(
        "SELECT id FROM users WHERE enabled IS TRUE ORDER BY id"
    ).fetchall()

    count = 0
    for row in rows:
        permissions = resolve_user_permissions(connection, row["id"])
        if permission in permissions:
            count += 1
    return count


def _active_permission_managers(connection) -> int:
    """Count enabled users holding the complete permission-manager set."""
    required = {
        "permissions.manage",
        "users.manage",
        "clients.view",
    }
    rows = connection.execute(
        "SELECT id FROM users WHERE enabled IS TRUE ORDER BY id"
    ).fetchall()

    count = 0
    for row in rows:
        permissions = resolve_user_permissions(connection, row["id"])
        if required.issubset(permissions):
            count += 1
    return count


def _abort(payload: dict, status_code: int):
    raise _UserTransactionAbort(payload, status_code)


def _require_actor_permissions(connection, required_permissions):
    """Revalidate the acting user inside the locked RBAC write transaction."""
    actor_id = current_user_id()
    actor = connection.execute(
        """
        SELECT id, enabled
        FROM users
        WHERE id = %s
        FOR UPDATE
        """,
        (actor_id,),
    ).fetchone()

    if actor is None or actor["enabled"] is not True:
        _abort({"error": "authentication_required"}, 401)

    permissions = resolve_user_permissions(connection, actor_id)
    if not set(required_permissions).issubset(permissions):
        _abort({"error": "authorization_required"}, 403)

    return actor_id


def register_postgres_user_routes(app):
    """Register PostgreSQL-backed user-management routes."""

    @app.get("/users", endpoint="postgres_users_page")
    @login_required
    @role_required(permission="users.manage")
    def users_page():
        return render_template(
            "users.html",
            csrf_token=get_csrf_token(),
            user_role=current_user_role(),
            **_permission_ui_context(),
        )

    @app.get("/api/users", endpoint="postgres_list_users")
    @login_required
    @role_required(permission="users.manage")
    def list_users():
        connection = None
        try:
            connection = _get_connection()
            rows = connection.execute(
                """
                SELECT
                    u.id,
                    u.username,
                    u.role,
                    u.enabled,
                    u.created_at,
                    u.admin_note,
                    u.first_name,
                    u.last_name,
                    u.department,
                    u.function_id,
                    f.name AS function_name
                FROM users AS u
                LEFT JOIN user_functions AS f
                  ON f.id = u.function_id
                ORDER BY lower(u.username), u.id
                """
            ).fetchall()

            users = []
            for row in rows:
                user = dict(row)
                user["permissions"] = sorted(
                    resolve_user_permissions(connection, row["id"])
                )
                users.append(user)

            return jsonify(users)
        except (DatabaseDriverError, PostgresRBACError):
            return _database_error("list users")
        finally:
            if connection is not None:
                connection.close()

    @app.get("/api/user-functions", endpoint="postgres_list_user_functions")
    @login_required
    @role_required(permission="users.manage")
    def list_user_functions():
        connection = None
        try:
            connection = _get_connection()
            rows = connection.execute(
                """
                SELECT
                    f.id,
                    f.name,
                    f.created_at,
                    f.created_by,
                    COUNT(u.id)::BIGINT AS user_count
                FROM user_functions AS f
                LEFT JOIN users AS u
                  ON u.function_id = f.id
                GROUP BY f.id
                ORDER BY lower(f.name), f.id
                """
            ).fetchall()
            return jsonify([dict(row) for row in rows])
        except DatabaseDriverError:
            return _database_error("list user functions")
        finally:
            if connection is not None:
                connection.close()

    @app.post("/api/user-functions", endpoint="postgres_create_user_function")
    @login_required
    @role_required(permission="users.manage")
    @csrf_required
    def create_user_function():
        data = _json_object()
        if data is None:
            return jsonify({"error": "invalid_request"}), 400

        name = data.get("name")
        if not isinstance(name, str):
            return jsonify({"error": "invalid_user_function"}), 400

        name = name.strip()
        if not name or len(name) > FUNCTION_NAME_MAX_LENGTH:
            return jsonify({"error": "invalid_user_function"}), 400

        connection = None
        try:
            connection = _get_connection()
            with transaction(connection):
                row = connection.execute(
                    """
                    INSERT INTO user_functions (name, created_at, created_by)
                    VALUES (%s, %s, %s)
                    RETURNING id, name
                    """,
                    (
                        name,
                        datetime.now(timezone.utc).isoformat(),
                        current_user_id(),
                    ),
                ).fetchone()

                audit_log(
                    connection,
                    actor_type="user",
                    actor_id=current_user_id(),
                    action="user_function.create",
                    target=f"user_function:{row['id']}",
                    details=json.dumps({"name": row["name"]}),
                )

            return jsonify({
                "status": "created",
                "function": dict(row),
            }), 201
        except UniqueViolation:
            return jsonify({"error": "function_already_exists"}), 409
        except DatabaseDriverError:
            return _database_error("create user function")
        finally:
            if connection is not None:
                connection.close()

    @app.delete(
        "/api/user-functions/<int:function_id>",
        endpoint="postgres_delete_user_function",
    )
    @login_required
    @role_required(permission="users.manage")
    @csrf_required
    def delete_user_function(function_id):
        connection = None
        try:
            connection = _get_connection()
            with transaction(connection):
                row = connection.execute(
                    """
                    SELECT id, name
                    FROM user_functions
                    WHERE id = %s
                    FOR UPDATE
                    """,
                    (function_id,),
                ).fetchone()

                if row is None:
                    _abort({"error": "user_function_not_found"}, 404)

                connection.execute(
                    "DELETE FROM user_functions WHERE id = %s",
                    (function_id,),
                )
                audit_log(
                    connection,
                    actor_type="user",
                    actor_id=current_user_id(),
                    action="user_function.delete",
                    target=f"user_function:{function_id}",
                    details=json.dumps({"name": row["name"]}),
                )

            return jsonify({"status": "deleted", "id": function_id})
        except _UserTransactionAbort as abort:
            return jsonify(abort.payload), abort.status_code
        except DatabaseDriverError:
            return _database_error("delete user function")
        finally:
            if connection is not None:
                connection.close()

    @app.put(
        "/api/users/<int:user_id>/profile",
        endpoint="postgres_update_user_profile",
    )
    @login_required
    @role_required(permission="users.manage")
    @csrf_required
    def update_user_profile(user_id):
        data = _json_object()
        if data is None:
            return jsonify({"error": "invalid_request"}), 400

        limits = {
            "first_name": 100,
            "last_name": 100,
            "department": 120,
        }
        values = {}
        for field, maximum in limits.items():
            value = data.get(field, "")
            if not isinstance(value, str):
                return jsonify({"error": "invalid_user_profile"}), 400
            value = value.strip()
            if len(value) > maximum:
                return jsonify({"error": "invalid_user_profile"}), 400
            values[field] = value

        function_id = data.get("function_id")
        if function_id in ("", None):
            function_id = None
        elif (
            isinstance(function_id, bool)
            or not isinstance(function_id, int)
            or function_id < 1
        ):
            return jsonify({"error": "invalid_user_function"}), 400

        connection = None
        try:
            connection = _get_connection()
            with transaction(connection):
                user = connection.execute(
                    "SELECT id, username FROM users WHERE id = %s FOR UPDATE",
                    (user_id,),
                ).fetchone()
                if user is None:
                    _abort({"error": "user_not_found"}, 404)

                if function_id is not None:
                    function = connection.execute(
                        "SELECT id FROM user_functions WHERE id = %s",
                        (function_id,),
                    ).fetchone()
                    if function is None:
                        _abort({"error": "user_function_not_found"}, 400)

                connection.execute(
                    """
                    UPDATE users
                    SET first_name = %s,
                        last_name = %s,
                        department = %s,
                        function_id = %s
                    WHERE id = %s
                    """,
                    (
                        values["first_name"],
                        values["last_name"],
                        values["department"],
                        function_id,
                        user_id,
                    ),
                )
                audit_log(
                    connection,
                    actor_type="user",
                    actor_id=current_user_id(),
                    action="user.profile.update",
                    target=f"user:{user_id}",
                    details=json.dumps({
                        "username": user["username"],
                        "function_id": function_id,
                    }),
                )

            return jsonify({
                "status": "updated",
                "user_id": user_id,
                **values,
                "function_id": function_id,
            })
        except _UserTransactionAbort as abort:
            return jsonify(abort.payload), abort.status_code
        except DatabaseDriverError:
            return _database_error("update user profile")
        finally:
            if connection is not None:
                connection.close()

    @app.post("/api/users", endpoint="postgres_create_user")
    @login_required
    @role_required(permission="users.manage")
    @csrf_required
    def create_user():
        data = _json_object()
        if data is None:
            data = {}

        username = data.get("username", "")
        password = data.get("password", "")
        role = data.get("role", "")

        if not isinstance(username, str) or not isinstance(password, str):
            return jsonify({"error": "invalid_request"}), 400

        username = username.strip()
        if not username:
            return jsonify({"error": "username_required"}), 400
        if len(username) > USERNAME_MAX_LENGTH:
            return jsonify({"error": "username_too_long"}), 400
        if not password:
            return jsonify({"error": "password_required"}), 400
        if len(password) < PASSWORD_MIN_LENGTH:
            return jsonify({"error": "password_too_short"}), 400
        if not isinstance(role, str) or role not in VALID_ROLES:
            return jsonify({"error": "invalid_user_role"}), 400

        if "permissions" in data:
            try:
                permissions = _validate_permission_input(data["permissions"])
            except ValueError:
                return jsonify({"error": "invalid_user_permissions"}), 400
        else:
            permissions = set(ROLE_DEFAULT_PERMISSIONS[role])

        if permissions and "permissions.manage" not in current_user_permissions():
            return jsonify({
                "error": "permission_delegation_required"
            }), 403

        password_hash = hash_password(password)
        connection = None
        try:
            connection = _get_connection()
            with transaction(connection):
                acquire_rbac_write_lock(connection)

                required_permissions = {"users.manage"}
                if permissions:
                    required_permissions.add("permissions.manage")
                actor_id = _require_actor_permissions(
                    connection,
                    required_permissions,
                )

                row = connection.execute(
                    """
                    INSERT INTO users (
                        username,
                        password_hash,
                        created_at,
                        enabled,
                        role
                    )
                    VALUES (%s, %s, %s, TRUE, %s)
                    RETURNING id, username, role, enabled
                    """,
                    (
                        username,
                        password_hash,
                        datetime.now(timezone.utc).isoformat(),
                        role,
                    ),
                ).fetchone()

                store_user_permissions(
                    connection,
                    row["id"],
                    role,
                    permissions,
                    actor_id=actor_id,
                )

                audit_log(
                    connection,
                    actor_type="user",
                    actor_id=actor_id,
                    action="user.create",
                    target=f"user:{row['id']}",
                    details=json.dumps({
                        "username": username,
                        "role": role,
                        "permissions": sorted(permissions),
                    }),
                )

            user = dict(row)
            user["permissions"] = sorted(permissions)
            return jsonify({"status": "created", "user": user}), 201
        except _UserTransactionAbort as abort:
            return jsonify(abort.payload), abort.status_code
        except UniqueViolation:
            return jsonify({"error": "user_already_exists"}), 409
        except (DatabaseDriverError, PostgresRBACError, ValueError):
            return _database_error("create user")
        finally:
            if connection is not None:
                connection.close()

    @app.put(
        "/api/users/<int:user_id>/permissions",
        endpoint="postgres_update_user_permissions",
    )
    @login_required
    @role_required(permission="users.manage")
    @role_required(permission="permissions.manage")
    @csrf_required
    def update_user_permissions(user_id):
        data = _json_object()
        if data is None:
            return jsonify({"error": "invalid_request"}), 400

        role = data.get("role")
        if not isinstance(role, str) or role not in VALID_ROLES:
            return jsonify({"error": "invalid_user_role"}), 400

        try:
            permissions = _validate_permission_input(data.get("permissions"))
        except ValueError:
            return jsonify({"error": "invalid_user_permissions"}), 400

        connection = None
        try:
            connection = _get_connection()
            with transaction(connection):
                acquire_rbac_write_lock(connection)

                actor_id = _require_actor_permissions(
                    connection,
                    {"users.manage", "permissions.manage"},
                )

                target = connection.execute(
                    """
                    SELECT id, username, role, enabled
                    FROM users
                    WHERE id = %s
                    FOR UPDATE
                    """,
                    (user_id,),
                ).fetchone()

                if target is None:
                    _abort({"error": "user_not_found"}, 404)

                old_permissions = resolve_user_permissions(
                    connection,
                    user_id,
                )

                loses_user_management = (
                    target["enabled"] is True
                    and "users.manage" in old_permissions
                    and "users.manage" not in permissions
                )
                if (
                    loses_user_management
                    and _active_users_with_permission(
                        connection,
                        "users.manage",
                    ) <= 1
                ):
                    _abort(
                        {"error": "last_enabled_administrator"},
                        409,
                    )

                manager_set = {
                    "permissions.manage",
                    "users.manage",
                    "clients.view",
                }
                loses_permission_management = (
                    target["enabled"] is True
                    and manager_set.issubset(old_permissions)
                    and not manager_set.issubset(permissions)
                )
                if (
                    loses_permission_management
                    and _active_permission_managers(connection) <= 1
                ):
                    _abort(
                        {"error": "last_enabled_permission_manager"},
                        409,
                    )

                connection.execute(
                    "UPDATE users SET role = %s WHERE id = %s",
                    (role, user_id),
                )
                store_user_permissions(
                    connection,
                    user_id,
                    role,
                    permissions,
                    actor_id=actor_id,
                )
                audit_log(
                    connection,
                    actor_type="user",
                    actor_id=actor_id,
                    action="user.permissions.update",
                    target=f"user:{user_id}",
                    details=json.dumps({
                        "username": target["username"],
                        "role": role,
                        "permissions": sorted(permissions),
                    }),
                )

            return jsonify({
                "status": "updated",
                "user": {
                    "id": user_id,
                    "username": target["username"],
                    "role": role,
                    "permissions": sorted(permissions),
                },
            })
        except _UserTransactionAbort as abort:
            return jsonify(abort.payload), abort.status_code
        except (DatabaseDriverError, PostgresRBACError, ValueError):
            return _database_error("update user permissions")
        finally:
            if connection is not None:
                connection.close()

    @app.put(
        "/api/users/<int:user_id>/note",
        endpoint="postgres_update_user_note",
    )
    @login_required
    @role_required(permission="users.manage")
    @csrf_required
    def update_user_note(user_id):
        data = _json_object()
        if data is None:
            return jsonify({"error": "invalid_request"}), 400

        note = data.get("note")
        if not isinstance(note, str) or len(note) > ADMIN_NOTE_MAX_LENGTH:
            return jsonify({"error": "invalid_admin_note"}), 400
        note = note.strip()

        connection = None
        try:
            connection = _get_connection()
            with transaction(connection):
                user = connection.execute(
                    """
                    SELECT id, username
                    FROM users
                    WHERE id = %s
                    FOR UPDATE
                    """,
                    (user_id,),
                ).fetchone()
                if user is None:
                    _abort({"error": "user_not_found"}, 404)

                connection.execute(
                    "UPDATE users SET admin_note = %s WHERE id = %s",
                    (note, user_id),
                )
                audit_log(
                    connection,
                    actor_type="user",
                    actor_id=current_user_id(),
                    action="user.admin_note.update",
                    target=f"user:{user_id}",
                    details=json.dumps({
                        "username": user["username"],
                        "note_length": len(note),
                    }),
                )

            return jsonify({
                "status": "updated",
                "user_id": user_id,
                "note": note,
            })
        except _UserTransactionAbort as abort:
            return jsonify(abort.payload), abort.status_code
        except DatabaseDriverError:
            return _database_error("update user note")
        finally:
            if connection is not None:
                connection.close()

    @app.delete("/api/users/<int:user_id>", endpoint="postgres_delete_user")
    @login_required
    @role_required(permission="users.manage")
    @csrf_required
    def delete_user(user_id):
        actor_id = current_user_id()
        if actor_id == user_id:
            return jsonify({"error": "cannot_delete_self"}), 400

        connection = None
        try:
            connection = _get_connection()
            with transaction(connection):
                acquire_rbac_write_lock(connection)

                actor_id = _require_actor_permissions(
                    connection,
                    {"users.manage"},
                )

                target = connection.execute(
                    """
                    SELECT id, username, role, enabled
                    FROM users
                    WHERE id = %s
                    FOR UPDATE
                    """,
                    (user_id,),
                ).fetchone()

                if target is None:
                    _abort({"error": "user_not_found"}, 404)

                permissions = resolve_user_permissions(
                    connection,
                    user_id,
                )

                if (
                    target["enabled"] is True
                    and "users.manage" in permissions
                    and _active_users_with_permission(
                        connection,
                        "users.manage",
                    ) <= 1
                ):
                    _abort(
                        {"error": "last_enabled_administrator"},
                        409,
                    )

                manager_set = {
                    "permissions.manage",
                    "users.manage",
                    "clients.view",
                }
                if (
                    target["enabled"] is True
                    and manager_set.issubset(permissions)
                    and _active_permission_managers(connection) <= 1
                ):
                    _abort(
                        {"error": "last_enabled_permission_manager"},
                        409,
                    )

                connection.execute(
                    "DELETE FROM users WHERE id = %s",
                    (user_id,),
                )
                audit_log(
                    connection,
                    actor_type="user",
                    actor_id=actor_id,
                    action="user.delete",
                    target=f"user:{user_id}",
                    details=json.dumps({
                        "username": target["username"],
                        "role": target["role"],
                    }),
                )

            return jsonify({
                "status": "deleted",
                "user_id": user_id,
            })
        except _UserTransactionAbort as abort:
            return jsonify(abort.payload), abort.status_code
        except (DatabaseDriverError, PostgresRBACError, ValueError):
            return _database_error("delete user")
        finally:
            if connection is not None:
                connection.close()


__all__ = ["register_postgres_user_routes"]
