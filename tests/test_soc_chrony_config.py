from pathlib import Path

import pytest

from server.soc.chrony_config import (
    DEFAULT_CONFIG_PATH,
    EXPECTED_DIRECTIVES,
    ChronyConfigError,
    load_protected_chrony_config,
    parse_chrony_config,
)


VALID_CONFIG = """\
# LUMS Trusted Time - NTS only
# No unauthenticated NTP fallback.

authselectmode require

server time.cloudflare.com iburst nts
server nts.netnod.se iburst nts

# Require both authenticated sources before synchronizing.
minsources 2

driftfile /var/lib/chrony/chrony.drift
ntsdumpdir /var/lib/chrony

maxupdateskew 100.0
rtcsync
makestep 1 3

leapseclist /usr/share/zoneinfo/leap-seconds.list
"""


def test_accepts_exact_approved_configuration():
    result = parse_chrony_config(VALID_CONFIG)

    assert result.path == DEFAULT_CONFIG_PATH
    assert result.source_names == (
        "time.cloudflare.com",
        "nts.netnod.se",
    )
    assert len(result.sha256) == 64


def test_accepts_whitespace_and_complete_comment_lines():
    content = (
        "  # comment\n"
        "\n"
        + VALID_CONFIG.replace("authselectmode require", "  authselectmode   require  ")
    )

    result = parse_chrony_config(content)

    assert result.source_names == (
        "time.cloudflare.com",
        "nts.netnod.se",
    )


def test_directive_names_are_case_insensitive():
    content = VALID_CONFIG.replace(
        "authselectmode require",
        "AUTHSELECTMODE require",
    )

    assert parse_chrony_config(content).source_names


@pytest.mark.parametrize(
    "extra_line",
    [
        "pool pool.ntp.org iburst",
        "server pool.ntp.org iburst",
        "peer 192.0.2.1",
        "refclock SHM 0",
        "local stratum 10",
        "manual",
        "allow 192.0.2.0/24",
        "cmdallow 192.0.2.0/24",
        "include /etc/chrony/extra.conf",
        "confdir /etc/chrony/conf.d",
        "sourcedir /run/chrony-dhcp",
        "sourcedir /etc/chrony/sources.d",
    ],
)
def test_rejects_additional_sources_and_includes(extra_line):
    with pytest.raises(ChronyConfigError):
        parse_chrony_config(VALID_CONFIG + "\n" + extra_line + "\n")


@pytest.mark.parametrize(
    "old, new",
    [
        ("authselectmode require", "authselectmode ignore"),
        ("authselectmode require", "authselectmode mix"),
        ("authselectmode require", "authselectmode prefer"),
        ("minsources 2", "minsources 1"),
        (
            "server time.cloudflare.com iburst nts",
            "server time.cloudflare.com iburst",
        ),
        (
            "server nts.netnod.se iburst nts",
            "server nts.netnod.se iburst",
        ),
        (
            "server time.cloudflare.com iburst nts",
            "server 192.0.2.10 iburst nts",
        ),
        (
            "server nts.netnod.se iburst nts",
            "server time.cloudflare.com iburst nts",
        ),
        (
            "maxupdateskew 100.0",
            "maxupdateskew 1000000.0",
        ),
        ("rtcsync", "rtcfile /var/lib/chrony/rtc"),
        ("makestep 1 3", "makestep 10 100"),
    ],
)
def test_rejects_modified_security_directives(old, new):
    content = VALID_CONFIG.replace(old, new, 1)

    with pytest.raises(ChronyConfigError):
        parse_chrony_config(content)


def test_rejects_missing_required_directive():
    content = VALID_CONFIG.replace("minsources 2\n", "")

    with pytest.raises(ChronyConfigError, match="missing"):
        parse_chrony_config(content)


def test_rejects_duplicate_source_directive():
    content = (
        VALID_CONFIG
        + "\nserver time.cloudflare.com iburst nts\n"
    )

    with pytest.raises(ChronyConfigError, match="duplicate"):
        parse_chrony_config(content)


def test_rejects_inline_comments_and_extra_arguments():
    content = VALID_CONFIG.replace(
        "minsources 2",
        "minsources 2 # unexpected",
    )

    with pytest.raises(ChronyConfigError, match="unapproved"):
        parse_chrony_config(content)


@pytest.mark.parametrize(
    "payload",
    [
        "",
        "\x00",
        "authselectmode require\n\x00",
    ],
)
def test_rejects_empty_or_nul_configuration(payload):
    with pytest.raises(ChronyConfigError):
        parse_chrony_config(payload)


def test_rejects_oversized_configuration():
    payload = VALID_CONFIG + ("# extra\n" * 10000)

    with pytest.raises(ChronyConfigError, match="too large"):
        parse_chrony_config(payload)


def test_only_the_default_config_path_is_accepted():
    with pytest.raises(ChronyConfigError, match="only"):
        load_protected_chrony_config(Path("/tmp/chrony.conf"))


def test_expected_directive_set_has_no_duplicate_entries():
    assert len(EXPECTED_DIRECTIVES) == 10
    assert len(set(EXPECTED_DIRECTIVES)) == 10
