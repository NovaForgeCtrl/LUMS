"""Add PostgreSQL SOC permissions to protected system roles."""

from ..migration_runner import Migration


SOC_RBAC_MIGRATION = Migration(
    version="010-soc-rbac",
    description="Add PostgreSQL SOC permissions to protected system roles",
    statements=(
        """
        DO $lums$
        BEGIN
            IF EXISTS (
                SELECT role_key, name, is_system, is_migration
                FROM roles
                WHERE role_key IN (
                    'system-administrator',
                    'system-operator',
                    'system-viewer'
                )
                EXCEPT
                SELECT *
                FROM (
                    VALUES
                        (
                            'system-administrator',
                            'Administrator',
                            TRUE,
                            FALSE
                        ),
                        (
                            'system-operator',
                            'Operator',
                            TRUE,
                            FALSE
                        ),
                        (
                            'system-viewer',
                            'Viewer',
                            TRUE,
                            FALSE
                        )
                ) AS expected(role_key, name, is_system, is_migration)
            )
            OR EXISTS (
                SELECT role_key, name, is_system, is_migration
                FROM (
                    VALUES
                        (
                            'system-administrator',
                            'Administrator',
                            TRUE,
                            FALSE
                        ),
                        (
                            'system-operator',
                            'Operator',
                            TRUE,
                            FALSE
                        ),
                        (
                            'system-viewer',
                            'Viewer',
                            TRUE,
                            FALSE
                        )
                ) AS expected(role_key, name, is_system, is_migration)
                EXCEPT
                SELECT role_key, name, is_system, is_migration
                FROM roles
                WHERE role_key IN (
                    'system-administrator',
                    'system-operator',
                    'system-viewer'
                )
            ) THEN
                RAISE EXCEPTION
                    'SOC RBAC precondition failed: system role mismatch';
            END IF;

            IF EXISTS (
                SELECT expected.role_key, expected.permission
                FROM (
                    VALUES
                        ('system-administrator', 'alerts.manage'),
                        ('system-administrator', 'alerts.view'),
                        ('system-administrator', 'backups.manage'),
                        ('system-administrator', 'clients.manage'),
                        ('system-administrator', 'clients.view'),
                        ('system-administrator', 'infrastructure.manage'),
                        ('system-administrator', 'jobs.manage'),
                        ('system-administrator', 'packages.search'),
                        ('system-administrator', 'software.view'),
                        ('system-administrator', 'system.update'),
                        ('system-administrator', 'updates.view'),
                        ('system-administrator', 'users.manage'),
                        ('system-operator', 'clients.view'),
                        ('system-operator', 'jobs.manage'),
                        ('system-operator', 'packages.search'),
                        ('system-operator', 'software.view'),
                        ('system-operator', 'updates.view'),
                        ('system-viewer', 'clients.view'),
                        ('system-viewer', 'software.view')
                ) AS expected(role_key, permission)
                EXCEPT
                SELECT roles.role_key, role_permissions.permission
                FROM roles
                JOIN role_permissions
                  ON role_permissions.role_id = roles.id
                WHERE roles.role_key IN (
                    'system-administrator',
                    'system-operator',
                    'system-viewer'
                )
            )
            OR EXISTS (
                SELECT roles.role_key, role_permissions.permission
                FROM roles
                JOIN role_permissions
                  ON role_permissions.role_id = roles.id
                WHERE roles.role_key IN (
                    'system-administrator',
                    'system-operator',
                    'system-viewer'
                )
                EXCEPT
                SELECT expected.role_key, expected.permission
                FROM (
                    VALUES
                        ('system-administrator', 'alerts.manage'),
                        ('system-administrator', 'alerts.view'),
                        ('system-administrator', 'backups.manage'),
                        ('system-administrator', 'clients.manage'),
                        ('system-administrator', 'clients.view'),
                        ('system-administrator', 'infrastructure.manage'),
                        ('system-administrator', 'jobs.manage'),
                        ('system-administrator', 'packages.search'),
                        ('system-administrator', 'software.view'),
                        ('system-administrator', 'system.update'),
                        ('system-administrator', 'updates.view'),
                        ('system-administrator', 'users.manage'),
                        ('system-operator', 'clients.view'),
                        ('system-operator', 'jobs.manage'),
                        ('system-operator', 'packages.search'),
                        ('system-operator', 'software.view'),
                        ('system-operator', 'updates.view'),
                        ('system-viewer', 'clients.view'),
                        ('system-viewer', 'software.view')
                ) AS expected(role_key, permission)
            ) THEN
                RAISE EXCEPTION
                    'SOC RBAC precondition failed: frozen migration 004 permissions differ';
            END IF;
        END;
        $lums$
        """,
        """
        INSERT INTO role_permissions (role_id, permission)
        SELECT roles.id, expected.permission
        FROM roles
        JOIN (
            VALUES
                ('system-administrator', 'soc.view'),
                ('system-administrator', 'soc.incidents.manage'),
                ('system-administrator', 'soc.collectors.manage'),
                ('system-operator', 'soc.view'),
                ('system-operator', 'soc.incidents.manage'),
                ('system-viewer', 'soc.view')
        ) AS expected(role_key, permission)
          ON expected.role_key = roles.role_key
        ON CONFLICT (role_id, permission) DO NOTHING
        """,
        """
        DO $lums$
        BEGIN
            IF EXISTS (
                SELECT role_key, name, is_system, is_migration
                FROM roles
                WHERE role_key IN (
                    'system-administrator',
                    'system-operator',
                    'system-viewer'
                )
                EXCEPT
                SELECT *
                FROM (
                    VALUES
                        (
                            'system-administrator',
                            'Administrator',
                            TRUE,
                            FALSE
                        ),
                        (
                            'system-operator',
                            'Operator',
                            TRUE,
                            FALSE
                        ),
                        (
                            'system-viewer',
                            'Viewer',
                            TRUE,
                            FALSE
                        )
                ) AS expected(role_key, name, is_system, is_migration)
            )
            OR EXISTS (
                SELECT role_key, name, is_system, is_migration
                FROM (
                    VALUES
                        (
                            'system-administrator',
                            'Administrator',
                            TRUE,
                            FALSE
                        ),
                        (
                            'system-operator',
                            'Operator',
                            TRUE,
                            FALSE
                        ),
                        (
                            'system-viewer',
                            'Viewer',
                            TRUE,
                            FALSE
                        )
                ) AS expected(role_key, name, is_system, is_migration)
                EXCEPT
                SELECT role_key, name, is_system, is_migration
                FROM roles
                WHERE role_key IN (
                    'system-administrator',
                    'system-operator',
                    'system-viewer'
                )
            ) THEN
                RAISE EXCEPTION
                    'SOC RBAC postcondition failed: system role mismatch';
            END IF;

            IF EXISTS (
                SELECT expected.role_key, expected.permission
                FROM (
                    VALUES
                        ('system-administrator', 'alerts.manage'),
                        ('system-administrator', 'alerts.view'),
                        ('system-administrator', 'backups.manage'),
                        ('system-administrator', 'clients.manage'),
                        ('system-administrator', 'clients.view'),
                        ('system-administrator', 'infrastructure.manage'),
                        ('system-administrator', 'jobs.manage'),
                        ('system-administrator', 'packages.search'),
                        ('system-administrator', 'software.view'),
                        ('system-administrator', 'system.update'),
                        ('system-administrator', 'updates.view'),
                        ('system-administrator', 'users.manage'),
                        ('system-administrator', 'soc.view'),
                        ('system-administrator', 'soc.incidents.manage'),
                        ('system-administrator', 'soc.collectors.manage'),
                        ('system-operator', 'clients.view'),
                        ('system-operator', 'jobs.manage'),
                        ('system-operator', 'packages.search'),
                        ('system-operator', 'software.view'),
                        ('system-operator', 'updates.view'),
                        ('system-operator', 'soc.view'),
                        ('system-operator', 'soc.incidents.manage'),
                        ('system-viewer', 'clients.view'),
                        ('system-viewer', 'software.view'),
                        ('system-viewer', 'soc.view')
                ) AS expected(role_key, permission)
                EXCEPT
                SELECT roles.role_key, role_permissions.permission
                FROM roles
                JOIN role_permissions
                  ON role_permissions.role_id = roles.id
                WHERE roles.role_key IN (
                    'system-administrator',
                    'system-operator',
                    'system-viewer'
                )
            )
            OR EXISTS (
                SELECT roles.role_key, role_permissions.permission
                FROM roles
                JOIN role_permissions
                  ON role_permissions.role_id = roles.id
                WHERE roles.role_key IN (
                    'system-administrator',
                    'system-operator',
                    'system-viewer'
                )
                EXCEPT
                SELECT expected.role_key, expected.permission
                FROM (
                    VALUES
                        ('system-administrator', 'alerts.manage'),
                        ('system-administrator', 'alerts.view'),
                        ('system-administrator', 'backups.manage'),
                        ('system-administrator', 'clients.manage'),
                        ('system-administrator', 'clients.view'),
                        ('system-administrator', 'infrastructure.manage'),
                        ('system-administrator', 'jobs.manage'),
                        ('system-administrator', 'packages.search'),
                        ('system-administrator', 'software.view'),
                        ('system-administrator', 'system.update'),
                        ('system-administrator', 'updates.view'),
                        ('system-administrator', 'users.manage'),
                        ('system-administrator', 'soc.view'),
                        ('system-administrator', 'soc.incidents.manage'),
                        ('system-administrator', 'soc.collectors.manage'),
                        ('system-operator', 'clients.view'),
                        ('system-operator', 'jobs.manage'),
                        ('system-operator', 'packages.search'),
                        ('system-operator', 'software.view'),
                        ('system-operator', 'updates.view'),
                        ('system-operator', 'soc.view'),
                        ('system-operator', 'soc.incidents.manage'),
                        ('system-viewer', 'clients.view'),
                        ('system-viewer', 'software.view'),
                        ('system-viewer', 'soc.view')
                ) AS expected(role_key, permission)
            ) THEN
                RAISE EXCEPTION
                    'SOC RBAC postcondition failed: permission set differs';
            END IF;
        END;
        $lums$
        """,
    ),
)


__all__ = ["SOC_RBAC_MIGRATION"]
