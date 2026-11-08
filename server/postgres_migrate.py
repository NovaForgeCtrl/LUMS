"""Explicit command-line entry point for PostgreSQL schema migrations."""

from __future__ import annotations

import argparse
import sys

if __package__:
    from .db import connect
    from .migration_runner import (
        MigrationRunnerError,
        run_migrations,
    )
    from .migrations import MIGRATIONS
else:
    from db import connect
    from migration_runner import MigrationRunnerError, run_migrations
    from migrations import MIGRATIONS


def main(argv: list[str] | None = None) -> int:
    """Run all pending PostgreSQL migrations and close the connection."""
    parser = argparse.ArgumentParser(
        description="Apply pending LUMS PostgreSQL database migrations."
    )
    parser.parse_args(argv)

    connection = None
    exit_code = 1

    try:
        connection = connect(
            application_name="lums-postgres-migrate"
        )

        result = run_migrations(
            connection,
            MIGRATIONS,
        )

        print("PostgreSQL migrations completed successfully.")

        if result.applied:
            print("Newly applied migrations:")
            for version in result.applied:
                print(f"  + {version}")
        else:
            print("Newly applied migrations: none")

        if result.already_applied:
            print("Previously applied migrations:")
            for version in result.already_applied:
                print(f"  = {version}")

        exit_code = 0

    except MigrationRunnerError as exc:
        print(
            f"ERROR: PostgreSQL migration failed: {exc}",
            file=sys.stderr,
        )

    except Exception as exc:
        print(
            f"ERROR: Could not execute PostgreSQL migrations: {exc}",
            file=sys.stderr,
        )

    finally:
        if connection is not None:
            try:
                if not connection.closed:
                    connection.close()
            except Exception as exc:
                print(
                    f"ERROR: Could not close PostgreSQL connection: {exc}",
                    file=sys.stderr,
                )
                exit_code = 1

    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["main"]
