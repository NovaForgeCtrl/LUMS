"""Shared database error types for LUMS PostgreSQL access."""

from psycopg import (
    Error as DatabaseDriverError,
    IntegrityError as DatabaseIntegrityError,
    InterfaceError as DatabaseInterfaceError,
    OperationalError as DatabaseOperationalError,
    ProgrammingError as DatabaseProgrammingError,
)


class DatabaseConfigurationError(ValueError):
    """Raised when PostgreSQL connection configuration is invalid."""


class DatabaseConnectionStateError(RuntimeError):
    """Raised when a database connection is not usable."""


class DatabaseTransactionStateError(RuntimeError):
    """Raised when a transaction operation violates the LUMS contract."""


__all__ = [
    "DatabaseDriverError",
    "DatabaseIntegrityError",
    "DatabaseInterfaceError",
    "DatabaseOperationalError",
    "DatabaseProgrammingError",
    "DatabaseConfigurationError",
    "DatabaseConnectionStateError",
    "DatabaseTransactionStateError",
]
