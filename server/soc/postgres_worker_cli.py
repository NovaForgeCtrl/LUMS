"""Explicit PostgreSQL SOC worker command-line entry point.

This process is independent from Flask and the SQLite SOC worker.
It only connects with the configured PostgreSQL worker credentials.
It never creates or migrates database objects.
"""

from __future__ import annotations

import argparse
import json
import os
import signal
import sys
import threading
from pathlib import Path
from typing import Any

if __package__:
    from ..db import connect
    from .postgres_worker import (
        DEFAULT_BATCH_SIZE,
        DEFAULT_HISTORY_LIMIT,
        DEFAULT_MAX_ATTEMPTS,
        DEFAULT_STALE_SECONDS,
        PostgresSOCWorker,
        _DEFAULT_RULES_PATH,
        run_continuous,
    )
    from .rule_catalog import load_catalog
else:
    from db import connect
    from soc.postgres_worker import (
        DEFAULT_BATCH_SIZE,
        DEFAULT_HISTORY_LIMIT,
        DEFAULT_MAX_ATTEMPTS,
        DEFAULT_STALE_SECONDS,
        PostgresSOCWorker,
        _DEFAULT_RULES_PATH,
        run_continuous,
    )
    from soc.rule_catalog import load_catalog


DEFAULT_RULES_PATH = _DEFAULT_RULES_PATH


def _get_worker_database_url() -> str:
    """Read the mandatory, dedicated PostgreSQL SOC worker secret."""
    secret_file = os.environ.get("LUMS_SOC_DATABASE_URL_FILE")
    if not isinstance(secret_file, str) or not secret_file.strip():
        raise RuntimeError(
            "LUMS_SOC_DATABASE_URL_FILE is missing or empty."
        )

    try:
        database_url = Path(secret_file.strip()).read_text(
            encoding="utf-8"
        ).strip()
    except (OSError, UnicodeError, ValueError) as exc:
        raise RuntimeError(
            "LUMS_SOC_DATABASE_URL_FILE could not be read."
        ) from exc

    if not database_url:
        raise RuntimeError(
            "LUMS_SOC_DATABASE_URL_FILE is empty."
        )

    return database_url


def main(argv: list[str] | None = None) -> int:
    """Run one bounded PostgreSQL SOC batch or the continuous worker."""
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--once",
        action="store_true",
        help="Process one bounded batch and exit (the default).",
    )
    mode.add_argument(
        "--continuous",
        action="store_true",
        help="Run until SIGINT or SIGTERM.",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=DEFAULT_BATCH_SIZE,
    )
    parser.add_argument(
        "--max-attempts",
        type=int,
        default=DEFAULT_MAX_ATTEMPTS,
    )
    parser.add_argument(
        "--stale-after-seconds",
        type=int,
        default=DEFAULT_STALE_SECONDS,
    )
    parser.add_argument(
        "--history-limit",
        type=int,
        default=DEFAULT_HISTORY_LIMIT,
    )
    parser.add_argument(
        "--poll-interval",
        type=float,
        default=5.0,
        help="Seconds between continuous batches (0.1-3600).",
    )
    args = parser.parse_args(argv)

    for name, value, low, high in (
        ("--batch-size", args.batch_size, 1, 500),
        ("--max-attempts", args.max_attempts, 1, 100),
        ("--stale-after-seconds", args.stale_after_seconds, 1, 86400),
        ("--history-limit", args.history_limit, 1, 50000),
    ):
        if not low <= value <= high:
            parser.error(f"{name} must be between {low} and {high}")

    if not 0.1 <= args.poll_interval <= 3600:
        parser.error("--poll-interval must be between 0.1 and 3600 seconds")

    rules_path = os.environ.get(
        "LUMS_SOC_RULES_PATH",
        str(DEFAULT_RULES_PATH),
    )

    connection = None
    stop_event = threading.Event()
    previous_handlers: dict[int, Any] = {}
    exit_code = 1

    try:
        catalog = load_catalog(Path(rules_path))

        worker_database_url = _get_worker_database_url()
        connection = connect(
            database_url=worker_database_url,
            application_name="lums-postgres-soc-worker",
        )

        worker = PostgresSOCWorker(
            connection,
            catalog,
            batch_size=args.batch_size,
            max_attempts=args.max_attempts,
            stale_after_seconds=args.stale_after_seconds,
            history_limit=args.history_limit,
        )

        if args.continuous:
            def request_stop(signum: int, frame: Any) -> None:
                # Defer shutdown until the current worker operation completes.
                stop_event.set()

            for signum in (signal.SIGINT, signal.SIGTERM):
                previous_handlers[signum] = signal.signal(
                    signum,
                    request_stop,
                )

            run_continuous(
                worker,
                stop_event,
                args.poll_interval,
            )
        else:
            result = worker.run_once()
            print(
                json.dumps(result.to_dict(), sort_keys=True),
                flush=True,
            )

        exit_code = 0

    except Exception as exc:
        print(
            f"[ERROR] PostgreSQL SOC worker stopped safely: "
            f"{type(exc).__name__}: {exc}",
            file=sys.stderr,
        )

    finally:
        for signum, handler in previous_handlers.items():
            try:
                signal.signal(signum, handler)
            except Exception as exc:
                print(
                    f"[ERROR] Could not restore signal handler "
                    f"{signum}: {type(exc).__name__}: {exc}",
                    file=sys.stderr,
                )
                exit_code = 1

        if connection is not None:
            try:
                connection.close()
            except Exception as exc:
                print(
                    "[ERROR] Could not close PostgreSQL worker connection: "
                    f"{type(exc).__name__}: {exc}",
                    file=sys.stderr,
                )
                exit_code = 1

    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["main"]
