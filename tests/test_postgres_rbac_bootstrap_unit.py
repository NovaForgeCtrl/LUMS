from __future__ import annotations

import pytest

from server import postgres_rbac as rbac


class FakeCursor:
    def __init__(self, *, one=None, many=None):
        self._one = one
        self._many = list(many or [])

    def fetchone(self):
        return self._one

    def fetchall(self):
        return list(self._many)


class FakeConnection:
    def __init__(self, assignment_rows):
        self.assignment_rows = list(assignment_rows)
        self.statements = []
        self.override_inserts = []

    def execute(self, statement, params=None):
        normalized = " ".join(statement.split())
        self.statements.append((normalized, params))

        if normalized.startswith("SELECT COUNT(*) AS total FROM users"):
            return FakeCursor(one={"total": 1})

        if normalized.startswith("SELECT id, enabled, role FROM users"):
            return FakeCursor(
                one={
                    "id": 77,
                    "enabled": True,
                    "role": rbac.ROLE_ADMINISTRATOR,
                }
            )

        if normalized.startswith("SELECT r.role_key"):
            return FakeCursor(many=self.assignment_rows)

        if normalized.startswith("INSERT INTO user_permission_overrides"):
            self.override_inserts.append((normalized, params))
            return FakeCursor()

        raise AssertionError(f"Unexpected SQL: {normalized}")


VALID_SYSTEM_ADMIN_ASSIGNMENT = {
    "role_key": "system-administrator",
    "name": "Administrator",
    "is_system": True,
    "is_migration": False,
}


def prepare_dependencies(monkeypatch, connection, permission_results):
    monkeypatch.setattr(
        rbac,
        "require_transaction",
        lambda conn: None,
    )
    monkeypatch.setattr(
        rbac,
        "_require_rbac_schema",
        lambda conn: None,
    )

    results = iter(permission_results)
    calls = []

    def fake_resolve(conn, user_id):
        assert conn is connection
        assert user_id == 77
        calls.append(user_id)
        return next(results)

    monkeypatch.setattr(
        rbac,
        "resolve_user_permissions",
        fake_resolve,
    )
    return calls


def test_initial_grant_requires_protected_system_administrator_role(
    monkeypatch,
):
    connection = FakeConnection([VALID_SYSTEM_ADMIN_ASSIGNMENT])
    before = frozenset({"users.manage", "clients.view"})
    after = frozenset({
        "users.manage",
        "clients.view",
        "permissions.manage",
    })
    calls = prepare_dependencies(
        monkeypatch,
        connection,
        [before, after],
    )

    timestamp = "2026-11-02T12:00:00+00:00"

    granted = rbac.grant_initial_permission_manager(
        connection,
        77,
        timestamp=timestamp,
    )

    assert granted is True
    assert calls == [77, 77]
    assert len(connection.override_inserts) == 1
    assert connection.override_inserts[0][1] == (77, timestamp)

    assignment_queries = [
        sql
        for sql, _ in connection.statements
        if sql.startswith("SELECT r.role_key")
    ]
    assert len(assignment_queries) == 1
    assert "FOR UPDATE OF ur, r" in assignment_queries[0]


@pytest.mark.parametrize(
    ("assignment_rows", "expected_message"),
    [
        (
            [],
            "exactly one RBAC role assignment",
        ),
        (
            [{
                "role_key": "system-viewer",
                "name": "Viewer",
                "is_system": True,
                "is_migration": False,
            }],
            "protected system-administrator RBAC role",
        ),
        (
            [{
                "role_key": "system-administrator",
                "name": "Administrator",
                "is_system": False,
                "is_migration": False,
            }],
            "protected system-administrator RBAC role",
        ),
        (
            [{
                "role_key": "system-administrator",
                "name": "Administrator",
                "is_system": True,
                "is_migration": True,
            }],
            "protected system-administrator RBAC role",
        ),
        (
            [{
                "role_key": "system-administrator",
                "name": "Manipulated role",
                "is_system": True,
                "is_migration": False,
            }],
            "protected system-administrator RBAC role",
        ),
    ],
)
def test_initial_grant_rejects_invalid_rbac_assignment(
    monkeypatch,
    assignment_rows,
    expected_message,
):
    connection = FakeConnection(assignment_rows)
    calls = prepare_dependencies(
        monkeypatch,
        connection,
        [],
    )

    with pytest.raises(
        rbac.PostgresRBACError,
        match=expected_message,
    ):
        rbac.grant_initial_permission_manager(connection, 77)

    assert calls == []
    assert connection.override_inserts == []


def test_initial_grant_requires_effective_dependency_permissions(
    monkeypatch,
):
    connection = FakeConnection([VALID_SYSTEM_ADMIN_ASSIGNMENT])
    calls = prepare_dependencies(
        monkeypatch,
        connection,
        [frozenset({"users.manage"})],
    )

    with pytest.raises(
        rbac.PostgresRBACError,
        match="delegation prerequisites",
    ):
        rbac.grant_initial_permission_manager(connection, 77)

    assert calls == [77]
    assert connection.override_inserts == []


def test_initial_grant_does_not_rewrite_existing_effective_grant(
    monkeypatch,
):
    connection = FakeConnection([VALID_SYSTEM_ADMIN_ASSIGNMENT])
    calls = prepare_dependencies(
        monkeypatch,
        connection,
        [
            frozenset({
                "users.manage",
                "clients.view",
                "permissions.manage",
            })
        ],
    )

    granted = rbac.grant_initial_permission_manager(
        connection,
        77,
    )

    assert granted is False
    assert calls == [77]
    assert connection.override_inserts == []
