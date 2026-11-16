"""Central PostgreSQL connection factory for LUMS."""

from __future__ import annotations

import os
from collections.abc import Mapping
from pathlib import Path
from urllib.parse import urlsplit

import psycopg
from psycopg import Connection
from psycopg.conninfo import conninfo_to_dict
from psycopg.rows import dict_row

if __package__:
    from .db_errors import DatabaseConfigurationError
else:
    from db_errors import DatabaseConfigurationError


DEFAULT_CONNECT_TIMEOUT = 5
DEFAULT_APPLICATION_NAME = "lums"


def _validate_database_url(value: str) -> str:
    """Validate a PostgreSQL URL without exposing credentials."""
    if not isinstance(value, str) or not value.strip():
        raise DatabaseConfigurationError(
            "DATABASE_URL is missing or empty."
        )

    value = value.strip()

    if "\x00" in value:
        raise DatabaseConfigurationError(
            "DATABASE_URL contains an invalid null character."
        )

    try:
        parsed = urlsplit(value)
    except ValueError as exc:
        raise DatabaseConfigurationError(
            "DATABASE_URL is malformed."
        ) from exc

    if parsed.scheme.lower() not in {"postgresql", "postgres"}:
        raise DatabaseConfigurationError(
            "DATABASE_URL must use postgresql:// or postgres://."
        )

    if not parsed.netloc and not parsed.path:
        raise DatabaseConfigurationError(
            "DATABASE_URL does not identify a database."
        )

    if parsed.fragment:
        raise DatabaseConfigurationError(
            "DATABASE_URL must not contain a URI fragment."
        )

    try:
        parameters = conninfo_to_dict(value)
    except psycopg.ProgrammingError as exc:
        raise DatabaseConfigurationError(
            "DATABASE_URL is not a valid PostgreSQL connection string."
        ) from exc

    # libpq supports comma-separated ports for multiple hosts.
    # Empty entries select the PostgreSQL default port.
    raw_ports = parameters.get("port")

    if raw_ports not in (None, ""):
        for raw_port in str(raw_ports).split(","):
            if not raw_port:
                continue

            if not raw_port.isascii() or not raw_port.isdecimal():
                raise DatabaseConfigurationError(
                    "DATABASE_URL contains a non-numeric port."
                )

            port = int(raw_port)

            if not 1 <= port <= 65535:
                raise DatabaseConfigurationError(
                    "DATABASE_URL port must be between 1 and 65535."
                )

    return value


def get_database_url(
    environ: Mapping[str, str] | None = None,
) -> str:
    """Return a validated PostgreSQL URL from the environment or secret file."""
    source = os.environ if environ is None else environ

    if not isinstance(source, Mapping):
        raise TypeError("environ must be a mapping")

    database_url = source.get("DATABASE_URL")
    database_url_file = source.get("DATABASE_URL_FILE")

    has_database_url = (
        isinstance(database_url, str) and bool(database_url.strip())
    )
    has_database_url_file = (
        isinstance(database_url_file, str) and bool(database_url_file.strip())
    )

    if has_database_url and has_database_url_file:
        raise DatabaseConfigurationError(
            "Configure only one of DATABASE_URL or DATABASE_URL_FILE."
        )

    if has_database_url_file:
        try:
            database_url = Path(database_url_file.strip()).read_text(
                encoding="utf-8"
            ).strip()
        except (OSError, UnicodeError, ValueError) as exc:
            raise DatabaseConfigurationError(
                "DATABASE_URL_FILE could not be read."
            ) from exc

    return _validate_database_url(database_url)


def connect(
    database_url: str | None = None,
    *,
    connect_timeout: int = DEFAULT_CONNECT_TIMEOUT,
    application_name: str = DEFAULT_APPLICATION_NAME,
) -> Connection:
    """Open one independent PostgreSQL connection.

    Connections use autocommit for ordinary statements. Callers must
    explicitly open transaction blocks for atomic operations.

    The caller owns the connection lifecycle and must close the connection.
    No global connection or connection pool is created here.
    """
    if database_url is None:
        database_url = get_database_url()
    else:
        database_url = _validate_database_url(database_url)

    if (
        isinstance(connect_timeout, bool)
        or not isinstance(connect_timeout, int)
        or not 1 <= connect_timeout <= 60
    ):
        raise ValueError(
            "connect_timeout must be an integer from 1 to 60"
        )

    if (
        not isinstance(application_name, str)
        or not application_name.strip()
        or "\x00" in application_name
        or len(application_name.encode("utf-8")) > 63
    ):
        raise ValueError(
            "application_name must contain 1 to 63 UTF-8 bytes"
        )

    return psycopg.connect(
        database_url,
        autocommit=True,
        row_factory=dict_row,
        connect_timeout=connect_timeout,
        application_name=application_name,
    )


__all__ = [
    "connect",
    "get_database_url",
]
