from dataclasses import replace
from decimal import Decimal

import pytest

from server.soc.chrony_status import (
    ChronyStatusError,
    FULL_REACHABILITY,
    parse_chrony_status,
    parse_sources_csv,
    parse_tracking_csv,
)


TRACKING = (
    "CFC5577C,time.cloudflare.com,4,"
    "1795254866.549786796,"
    "0.000108656,0.000021184,0.000616593,"
    "25.752,0.011,0.668,0.018273009,0.000537179,"
    "64.4,Normal"
)

SOURCES = (
    "^,*,time.cloudflare.com,3,6,377,107,"
    "-0.000570636,-0.000549452,0.009808195\n"
    "^,+,nts.netnod.se,1,6,377,105,"
    "0.000300855,0.000300855,0.018632518\n"
)


def test_parses_real_chrony_tracking_csv():
    result = parse_tracking_csv(TRACKING)

    assert result.reference_id == "CFC5577C"
    assert result.reference_address == "time.cloudflare.com"
    assert result.stratum == 4
    assert result.leap_status == "Normal"
    assert result.root_delay == Decimal("0.018273009")
    assert result.root_dispersion == Decimal("0.000537179")


def test_parses_real_chrony_sources_csv():
    sources = parse_sources_csv(SOURCES)

    assert len(sources) == 2
    assert sources[0].name == "time.cloudflare.com"
    assert sources[0].state == "*"
    assert sources[0].reach == FULL_REACHABILITY
    assert sources[1].name == "nts.netnod.se"
    assert sources[1].state == "+"
    assert sources[1].reach == FULL_REACHABILITY


def test_accepts_two_selected_fully_reachable_sources():
    result = parse_chrony_status(TRACKING, SOURCES)

    assert result.source_id == (
        "time.cloudflare.com+nts.netnod.se"
    )
    assert result.offset.total_seconds() == pytest.approx(0.000109)
    assert result.uncertainty.total_seconds() == pytest.approx(0.009783)
    assert {source.state for source in result.sources} == {"*", "+"}



def test_rejects_tracking_reference_not_matching_best_source():
    mismatched = TRACKING.replace(
        "CFC5577C,time.cloudflare.com,4,",
        "CFC5577C,nts.netnod.se,4,",
        1,
    )

    with pytest.raises(
        ChronyStatusError,
        match="reference does not match",
    ):
        parse_chrony_status(mismatched, SOURCES)


@pytest.mark.parametrize(
    "tracking, sources, message",
    [
        (
            TRACKING.replace(",Normal", ",Not synchronised"),
            SOURCES,
            "leap status",
        ),
        (
            TRACKING.replace(",4,", ",16,", 1),
            SOURCES,
            "stratum",
        ),
        (
            TRACKING.replace("0.018273009", "-0.018273009"),
            SOURCES,
            "root delay",
        ),
        (
            TRACKING.replace("0.000537179", "-0.000537179"),
            SOURCES,
            "root dispersion",
        ),
        (
            TRACKING.replace("0.018273009", "NaN"),
            SOURCES,
            "finite",
        ),
        (
            TRACKING + "\n" + TRACKING,
            SOURCES,
            "exactly one",
        ),
        (
            TRACKING.rsplit(",", 1)[0],
            SOURCES,
            "14-field",
        ),
        (
            TRACKING,
            SOURCES.replace("time.cloudflare.com", "unknown.example"),
            "unknown or missing",
        ),
        (
            TRACKING,
            SOURCES.replace("^,+,nts.netnod.se", "^,-,nts.netnod.se"),
            "selected",
        ),
        (
            TRACKING,
            SOURCES.replace("^,+,nts.netnod.se", "^,*,nts.netnod.se"),
            "selected",
        ),
        (
            TRACKING,
            SOURCES.replace(",377,107,", ",376,107,"),
            "full reachability",
        ),
        (
            TRACKING,
            SOURCES.replace(",377,105,", ",000,105,"),
            "full reachability",
        ),
        (
            TRACKING,
            SOURCES.replace(",105,", ",200,"),
            "too old",
        ),
        (
            TRACKING,
            SOURCES.replace("0.018632518", "0.060000000"),
            "error margin",
        ),
        (
            TRACKING,
            SOURCES + SOURCES.splitlines()[0] + "\n",
            "exactly the two",
        ),
        (
            TRACKING,
            SOURCES.replace("nts.netnod.se", "time.cloudflare.com"),
            "duplicate",
        ),
    ],
)
def test_rejects_untrusted_or_incomplete_status(
    tracking,
    sources,
    message,
):
    with pytest.raises(ChronyStatusError, match=message):
        parse_chrony_status(tracking, sources)


@pytest.mark.parametrize(
    "payload",
    [
        "",
        "not,csv",
        "a,b,c",
    ],
)
def test_rejects_invalid_tracking_csv(payload):
    with pytest.raises(ChronyStatusError):
        parse_tracking_csv(payload)


def test_rejects_invalid_source_csv():
    with pytest.raises(ChronyStatusError):
        parse_sources_csv("^,*,time.cloudflare.com")


def test_rejects_invalid_reachability_not_octal():
    invalid = SOURCES.replace(",377,107,", ",388,107,")

    with pytest.raises(ChronyStatusError, match="octal"):
        parse_sources_csv(invalid)


def test_rejects_non_decimal_source_metrics():
    invalid = SOURCES.replace("0.009808195", "Infinity")

    with pytest.raises(ChronyStatusError, match="finite"):
        parse_sources_csv(invalid)


def test_source_order_does_not_change_source_identity():
    reversed_sources = "\n".join(reversed(SOURCES.strip().splitlines()))

    result = parse_chrony_status(TRACKING, reversed_sources)

    assert result.source_id == (
        "time.cloudflare.com+nts.netnod.se"
    )


def test_accepts_sources_with_slow_chrony_poll_interval():
    tracking = TRACKING.replace(
        ",64.4,Normal",
        ",520.8,Normal",
    )

    sources = (
        SOURCES
        .replace(",3,6,377,107,", ",3,9,377,443,")
        .replace(",1,6,377,105,", ",1,9,377,513,")
    )

    result = parse_chrony_status(tracking, sources)

    assert len(result.sources) == 2
    assert result.sources[0].last_rx == Decimal("443")
    assert result.sources[1].last_rx == Decimal("513")


def test_rejects_sources_beyond_absolute_age_limit():
    tracking = TRACKING.replace(
        ",64.4,Normal",
        ",700.0,Normal",
    )

    sources = (
        SOURCES
        .replace(",3,6,377,107,", ",3,10,377,1201,")
        .replace(",1,6,377,105,", ",1,10,377,1201,")
    )

    with pytest.raises(ChronyStatusError, match="too old"):
        parse_chrony_status(tracking, sources)


def test_rejects_invalid_source_error_policy():
    with pytest.raises(ValueError, match="positive Decimal"):
        parse_chrony_status(
            TRACKING,
            SOURCES,
            max_source_error_seconds=Decimal("0"),
        )
