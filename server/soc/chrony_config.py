"""Strict validation of the protected LUMS Chrony configuration."""

from __future__ import annotations

import hashlib
import os
import stat
from collections import Counter
from dataclasses import dataclass
from pathlib import Path


DEFAULT_CONFIG_PATH = Path("/etc/chrony/chrony.conf")
MAX_CONFIG_SIZE = 64 * 1024

EXPECTED_DIRECTIVES = (
    ("authselectmode", "require"),
    ("server", "time.cloudflare.com", "iburst", "nts"),
    ("server", "nts.netnod.se", "iburst", "nts"),
    ("minsources", "2"),
    ("driftfile", "/var/lib/chrony/chrony.drift"),
    ("ntsdumpdir", "/var/lib/chrony"),
    ("maxupdateskew", "100.0"),
    ("rtcsync",),
    ("makestep", "1", "3"),
    ("leapseclist", "/usr/share/zoneinfo/leap-seconds.list"),
)

_EXPECTED_COUNTS = Counter(EXPECTED_DIRECTIVES)

_EXPECTED_SOURCE_NAMES = (
    "time.cloudflare.com",
    "nts.netnod.se",
)

_FORBIDDEN_INCLUDE_DIRECTIVES = {
    "include",
    "confdir",
    "sourcedir",
}


class ChronyConfigError(ValueError):
    """Raised when Chrony's active configuration is not trusted."""


@dataclass(frozen=True)
class ValidatedChronyConfig:
    path: Path
    sha256: str
    source_names: tuple[str, ...]


def parse_chrony_config(payload: str) -> ValidatedChronyConfig:
    """Accept only the exact approved LUMS NTS configuration.

    Chrony directives are case-insensitive. Their arguments are deliberately
    checked exactly. Only complete comment lines are ignored.
    """
    if not isinstance(payload, str) or not payload:
        raise ChronyConfigError("Chrony configuration is empty or invalid")

    try:
        encoded = payload.encode("utf-8", errors="strict")
    except UnicodeError as exc:
        raise ChronyConfigError(
            "Chrony configuration is not valid UTF-8"
        ) from exc

    if len(encoded) > MAX_CONFIG_SIZE:
        raise ChronyConfigError("Chrony configuration is too large")

    if "\x00" in payload:
        raise ChronyConfigError("Chrony configuration contains NUL bytes")

    seen: Counter[tuple[str, ...]] = Counter()

    for line_number, raw_line in enumerate(payload.splitlines(), start=1):
        line = raw_line.strip()

        if not line or line[0] in "!;#%":
            continue

        tokens = line.split()
        if not tokens:
            continue

        normalized = (tokens[0].lower(), *tokens[1:])

        if normalized not in _EXPECTED_COUNTS:
            directive = tokens[0].lower()

            if directive in _FORBIDDEN_INCLUDE_DIRECTIVES:
                raise ChronyConfigError(
                    f"configuration includes are forbidden (line {line_number})"
                )

            raise ChronyConfigError(
                f"unapproved or modified directive on line {line_number}"
            )

        seen[normalized] += 1

        if seen[normalized] > _EXPECTED_COUNTS[normalized]:
            raise ChronyConfigError(
                f"duplicate directive on line {line_number}"
            )

    if seen != _EXPECTED_COUNTS:
        missing = list((_EXPECTED_COUNTS - seen).elements())
        raise ChronyConfigError(
            f"required Chrony directives are missing: {missing!r}"
        )

    return ValidatedChronyConfig(
        path=DEFAULT_CONFIG_PATH,
        sha256=hashlib.sha256(encoded).hexdigest(),
        source_names=_EXPECTED_SOURCE_NAMES,
    )


def _require_protected_directory(path: Path) -> None:
    try:
        info = path.lstat()
    except OSError as exc:
        raise ChronyConfigError(
            f"cannot inspect trusted directory: {path}"
        ) from exc

    if not stat.S_ISDIR(info.st_mode):
        raise ChronyConfigError(
            f"trusted directory is not a real directory: {path}"
        )

    if info.st_uid != 0:
        raise ChronyConfigError(
            f"trusted directory is not root-owned: {path}"
        )

    if info.st_mode & 0o022:
        raise ChronyConfigError(
            f"trusted directory is group/world writable: {path}"
        )


def _require_protected_file(info: os.stat_result) -> None:
    if not stat.S_ISREG(info.st_mode):
        raise ChronyConfigError(
            "Chrony configuration is not a regular file"
        )

    if info.st_uid != 0:
        raise ChronyConfigError(
            "Chrony configuration is not root-owned"
        )

    if info.st_mode & 0o022:
        raise ChronyConfigError(
            "Chrony configuration is group/world writable"
        )

    if info.st_mode & 0o7000:
        raise ChronyConfigError(
            "Chrony configuration has special permission bits"
        )

    if not info.st_mode & stat.S_IROTH:
        raise ChronyConfigError(
            "Chrony configuration is not readable by the monitor"
        )

    if info.st_nlink != 1:
        raise ChronyConfigError(
            "Chrony configuration must not have additional hardlinks"
        )

    if info.st_size > MAX_CONFIG_SIZE:
        raise ChronyConfigError("Chrony configuration is too large")


def load_protected_chrony_config(
    path: str | os.PathLike[str] = DEFAULT_CONFIG_PATH,
) -> ValidatedChronyConfig:
    """Read and validate the single root-protected Chrony config file.

    This validates the default configuration path and its filesystem
    protection. It does not independently prove which arguments a running
    chronyd process was started with; that is a separate runtime check.
    """
    try:
        supplied_path = os.fspath(path)
    except TypeError as exc:
        raise ChronyConfigError("invalid Chrony configuration path") from exc

    if supplied_path != str(DEFAULT_CONFIG_PATH):
        raise ChronyConfigError(
            "only /etc/chrony/chrony.conf is approved"
        )

    for directory in (
        Path("/"),
        Path("/etc"),
        Path("/etc/chrony"),
    ):
        _require_protected_directory(directory)

    try:
        before = DEFAULT_CONFIG_PATH.lstat()
    except OSError as exc:
        raise ChronyConfigError(
            "Chrony configuration cannot be inspected"
        ) from exc

    _require_protected_file(before)

    flags = os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW

    try:
        fd = os.open(DEFAULT_CONFIG_PATH, flags)
    except OSError as exc:
        raise ChronyConfigError(
            "Chrony configuration cannot be opened safely"
        ) from exc

    try:
        opened = os.fstat(fd)
        _require_protected_file(opened)

        if (opened.st_dev, opened.st_ino) != (before.st_dev, before.st_ino):
            raise ChronyConfigError(
                "Chrony configuration changed during inspection"
            )

        chunks: list[bytes] = []
        total = 0

        while True:
            chunk = os.read(fd, min(8192, MAX_CONFIG_SIZE + 1 - total))
            if not chunk:
                break

            chunks.append(chunk)
            total += len(chunk)

            if total > MAX_CONFIG_SIZE:
                raise ChronyConfigError(
                    "Chrony configuration is too large"
                )

        raw = b"".join(chunks)

    finally:
        os.close(fd)

    try:
        text = raw.decode("utf-8", errors="strict")
    except UnicodeError as exc:
        raise ChronyConfigError(
            "Chrony configuration is not valid UTF-8"
        ) from exc

    return parse_chrony_config(text)
