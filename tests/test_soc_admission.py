from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest

from server.soc.admission import (
    AdmissionController,
    AdmissionError,
    AdmissionState,
)
from server.soc.crl_validation import (
    CRLPolicy,
    CRLValidationError,
    ValidatedCRL,
)
from server.soc.trusted_time import TrustedTime


UTC = timezone.utc


class FakeClock:
    def __init__(self, value=10_000_000_000):
        self.value = value

    def __call__(self):
        return self.value

    def advance(self, duration):
        self.value += int(duration.total_seconds() * 1_000_000_000)


def make_crl(now, name, *, next_update=None, this_update=None):
    return ValidatedCRL(
        ca_certificate=None,
        crl=None,
        this_update=this_update or now - timedelta(minutes=1),
        next_update=next_update or now + timedelta(hours=2),
        revoked_serial_numbers=frozenset(),
        ca_sha256=f"ca-{name}",
        crl_sha256=f"crl-{name}",
        ca_pem=f"ca-{name}".encode(),
        crl_pem=f"crl-{name}".encode(),
    )


@pytest.fixture
def admission_environment():
    now = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
    clock = FakeClock()
    state = {"now": now}

    policy = CRLPolicy(
        max_age=timedelta(hours=1),
        clock_skew=timedelta(minutes=2),
    )

    def trusted_time_reader():
        return TrustedTime(
            utc_now=state["now"],
            boottime_ns=(
                clock.value + state.get("trusted_boot_offset_ns", 0)
            ),
            sync_age=timedelta(seconds=1),
            source_id="isolated-admission-test",
            offset=timedelta(milliseconds=1),
            uncertainty=timedelta(milliseconds=2),
        )

    known_crls = {}
    active = make_crl(now, "active")
    candidate = make_crl(now, "candidate")
    known_crls[active.ca_pem] = active
    known_crls[candidate.ca_pem] = candidate

    def validator(ca_pem, crl_pem, *, policy, now):
        if ca_pem.startswith(b"invalid") or crl_pem.startswith(b"invalid"):
            raise CRLValidationError("invalid test CRL")

        result = known_crls.get(ca_pem)
        if result is None or result.crl_pem != crl_pem:
            raise CRLValidationError("unknown test CRL")

        if now > result.next_update:
            raise CRLValidationError("expired test CRL")

        if now - result.this_update > policy.max_age:
            raise CRLValidationError("stale test CRL")

        return result

    controller = AdmissionController(
        policy,
        trusted_time_reader,
        safety_margin=timedelta(seconds=10),
        observation_tolerance=timedelta(seconds=2),
        boottime_clock=clock,
        crl_validator=validator,
    )

    return controller, clock, state, active, candidate


def activate_initial(controller, candidate):
    assert controller.state is AdmissionState.BLOCKED
    assert controller.begin_recovery(candidate)
    assert controller.state is AdmissionState.RECOVERY
    assert not controller.admit_new_connection()
    assert controller.complete_recovery(tls_verifier=lambda _crl: True)
    assert controller.state is AdmissionState.READY


def test_starts_blocked(admission_environment):
    controller, *_ = admission_environment
    assert controller.state is AdmissionState.BLOCKED
    assert not controller.admit_new_connection()


def test_initial_recovery_requires_successful_tls_verification(
    admission_environment,
):
    controller, _, _, _, candidate = admission_environment

    assert controller.begin_recovery(candidate)
    assert controller.state is AdmissionState.RECOVERY
    assert not controller.admit_new_connection()

    assert controller.complete_recovery(tls_verifier=lambda _crl: True)
    assert controller.state is AdmissionState.READY
    assert controller.admit_new_connection()


def test_failed_recovery_blocks_even_if_old_active_crl_is_valid(
    admission_environment,
):
    controller, _, _, active, candidate = admission_environment
    activate_initial(controller, active)

    assert controller.begin_update()
    assert controller.begin_recovery(candidate)
    assert controller.state is AdmissionState.RECOVERY

    assert not controller.complete_recovery(
        tls_verifier=lambda _crl: False
    )

    snapshot = controller.snapshot
    assert snapshot.state is AdmissionState.BLOCKED
    assert snapshot.active_crl_sha256 == active.crl_sha256
    assert snapshot.deadline_boottime_ns is None
    assert snapshot.candidate_crl_sha256 is None
    assert not controller.admit_new_connection()


def test_failed_recovery_blocks_if_old_crl_expired(
    admission_environment,
):
    controller, _, time_state, active, candidate = admission_environment
    activate_initial(controller, active)

    assert controller.begin_update()
    assert controller.begin_recovery(candidate)

    time_state["now"] = active.next_update + timedelta(seconds=1)

    assert not controller.complete_recovery(
        tls_verifier=lambda _crl: False
    )

    snapshot = controller.snapshot
    assert snapshot.state is AdmissionState.BLOCKED
    assert snapshot.active_crl_sha256 == active.crl_sha256
    assert snapshot.deadline_boottime_ns is None
    assert snapshot.candidate_crl_sha256 is None
    assert not controller.admit_new_connection()


def test_successful_recovery_restores_active_deadline(
    admission_environment,
):
    controller, _, _, _, candidate = admission_environment

    assert controller.begin_recovery(candidate)
    assert controller.complete_recovery(
        tls_verifier=lambda _crl: True
    )

    snapshot = controller.snapshot
    assert snapshot.state is AdmissionState.READY
    assert snapshot.active_crl_sha256 == candidate.crl_sha256
    assert snapshot.deadline_boottime_ns is not None
    assert snapshot.candidate_crl_sha256 is None


def test_failed_tls_verification_keeps_controller_blocked(
    admission_environment,
):
    controller, _, _, _, candidate = admission_environment

    assert controller.begin_recovery(candidate)
    assert not controller.complete_recovery(tls_verifier=lambda _crl: False)

    snapshot = controller.snapshot
    assert snapshot.state is AdmissionState.BLOCKED
    assert snapshot.active_crl_sha256 is None
    assert snapshot.deadline_boottime_ns is None
    assert snapshot.candidate_crl_sha256 is None
    assert not controller.admit_new_connection()


def test_recovery_verifier_receives_exact_candidate(
    admission_environment,
):
    controller, _, _, _, candidate = admission_environment
    activate_initial(controller, candidate)

    assert controller.begin_update()
    assert controller.begin_recovery(candidate)

    received = []

    def verifier(crl):
        received.append(crl)
        return crl.ca_pem == candidate.ca_pem and crl.crl_pem == candidate.crl_pem

    assert controller.complete_recovery(tls_verifier=verifier)
    assert received == [candidate]


def test_recovery_verifier_cannot_reenter_completion(
    admission_environment,
):
    controller, _, _, _, candidate = admission_environment
    assert controller.begin_recovery(candidate)

    nested_attempts = []

    def verifier(_crl):
        with pytest.raises(
            AdmissionError,
            match="already in progress",
        ):
            controller.complete_recovery(
                tls_verifier=lambda _candidate: True
            )

        nested_attempts.append("rejected")
        return True

    assert controller.complete_recovery(tls_verifier=verifier)
    assert nested_attempts == ["rejected"]
    assert controller.state is AdmissionState.READY
    assert controller.snapshot.active_crl_sha256 == candidate.crl_sha256


def test_recovery_verifier_exception_blocks(admission_environment):
    controller, _, _, _, candidate = admission_environment
    assert controller.begin_recovery(candidate)

    def verifier(_crl):
        raise RuntimeError("staging handshake failed")

    assert not controller.complete_recovery(tls_verifier=verifier)
    assert controller.state is AdmissionState.BLOCKED
    assert not controller.admit_new_connection()

    # The finally block must release the verification guard after failure.
    assert controller.begin_recovery(candidate)
    assert controller.complete_recovery(
        tls_verifier=lambda _crl: True
    )
    assert controller.state is AdmissionState.READY


def test_recovery_rejects_non_callable_verifier(admission_environment):
    controller, _, _, _, candidate = admission_environment
    assert controller.begin_recovery(candidate)

    with pytest.raises(TypeError, match="tls_verifier"):
        controller.complete_recovery(tls_verifier=True)


def test_recovery_requires_literal_true(admission_environment):
    controller, _, _, _, candidate = admission_environment

    assert controller.begin_recovery(candidate)
    assert not controller.complete_recovery(tls_verifier=lambda _crl: 1)
    assert controller.state is AdmissionState.BLOCKED


def test_invalid_candidate_does_not_leave_blocked_state(
    admission_environment,
):
    controller, *_ = admission_environment
    invalid = make_crl(
        datetime(2026, 1, 1, 12, 0, tzinfo=UTC),
        "invalid",
    )
    invalid = replace(invalid, ca_pem=b"invalid-ca")

    assert not controller.begin_recovery(invalid)
    assert controller.state is AdmissionState.BLOCKED


def test_invalid_candidate_during_update_preserves_valid_active_crl(
    admission_environment,
):
    controller, _, _, active, _ = admission_environment
    activate_initial(controller, active)

    invalid = replace(active, ca_pem=b"invalid-ca")

    assert controller.begin_update()
    assert not controller.begin_recovery(invalid)

    assert controller.state is AdmissionState.READY
    assert controller.snapshot.active_crl_sha256 == active.crl_sha256
    assert controller.snapshot.candidate_crl_sha256 is None
    assert controller.admit_new_connection()


def test_invalid_candidate_blocks_if_active_crl_is_expired(
    admission_environment,
):
    controller, _, time_state, active, _ = admission_environment
    activate_initial(controller, active)

    invalid = replace(active, ca_pem=b"invalid-ca")

    assert controller.begin_update()
    time_state["now"] = active.next_update + timedelta(seconds=1)

    assert not controller.begin_recovery(invalid)
    assert controller.state is AdmissionState.BLOCKED
    assert not controller.admit_new_connection()


def test_update_pending_keeps_old_crl_active(admission_environment):
    controller, _, _, active, candidate = admission_environment
    activate_initial(controller, active)

    old_hash = controller.snapshot.active_crl_sha256

    assert controller.begin_update()
    assert controller.state is AdmissionState.UPDATE_PENDING
    assert controller.snapshot.active_crl_sha256 == old_hash
    assert controller.admit_new_connection()

    assert controller.begin_recovery(candidate)
    assert controller.state is AdmissionState.RECOVERY
    assert controller.snapshot.active_crl_sha256 == old_hash
    assert not controller.admit_new_connection()


def test_failed_update_returns_to_ready_if_old_crl_is_valid(
    admission_environment,
):
    controller, _, _, active, _ = admission_environment
    activate_initial(controller, active)

    old_deadline = controller.snapshot.deadline_boottime_ns

    assert controller.begin_update()
    assert controller.fail_update()

    assert controller.state is AdmissionState.READY
    assert controller.snapshot.active_crl_sha256 == active.crl_sha256
    assert controller.snapshot.deadline_boottime_ns <= old_deadline
    assert controller.admit_new_connection()


def test_invalid_transition_is_rejected(admission_environment):
    controller, *_ = admission_environment

    with pytest.raises(AdmissionError, match="READY"):
        controller.begin_update()

    with pytest.raises(AdmissionError, match="UPDATE_PENDING"):
        controller.fail_update()


def test_trusted_time_loss_blocks_new_connections(
    admission_environment,
):
    controller, _, _, active, _ = admission_environment
    activate_initial(controller, active)

    controller._trusted_time_reader = lambda: (_ for _ in ()).throw(
        RuntimeError("time provider unavailable")
    )

    assert not controller.admit_new_connection()
    assert controller.state is AdmissionState.BLOCKED


def test_wall_clock_rollback_never_extends_deadline(
    admission_environment,
):
    controller, clock, time_state, active, _ = admission_environment
    activate_initial(controller, active)

    original_deadline = controller.snapshot.deadline_boottime_ns

    clock.advance(timedelta(seconds=5))
    time_state["now"] -= timedelta(minutes=5)

    assert controller.admit_new_connection()
    assert controller.snapshot.deadline_boottime_ns == original_deadline


def test_forward_wall_clock_correction_shortens_deadline(
    admission_environment,
):
    controller, clock, time_state, active, _ = admission_environment
    activate_initial(controller, active)

    original_deadline = controller.snapshot.deadline_boottime_ns

    clock.advance(timedelta(seconds=5))
    time_state["now"] += timedelta(minutes=10)

    assert controller.admit_new_connection()
    assert controller.snapshot.deadline_boottime_ns < original_deadline


def test_monotonic_deadline_blocks_even_if_revalidation_is_delayed(
    admission_environment,
):
    controller, clock, _, active, _ = admission_environment
    activate_initial(controller, active)

    deadline = controller.snapshot.deadline_boottime_ns
    clock.value = deadline

    assert not controller.admit_new_connection()
    assert controller.state is AdmissionState.BLOCKED


def test_crl_expiry_blocks_admission(admission_environment):
    controller, clock, time_state, active, _ = admission_environment
    activate_initial(controller, active)

    clock.advance(timedelta(minutes=1))
    time_state["now"] = active.next_update + timedelta(seconds=1)

    assert not controller.admit_new_connection()
    assert controller.state is AdmissionState.BLOCKED


def test_trusted_utc_is_advanced_to_local_boottime(admission_environment):
    controller, _, time_state, _, candidate = admission_environment
    observed_times = []

    original_validator = controller._crl_validator

    def recording_validator(ca_pem, crl_pem, *, policy, now):
        observed_times.append(now)
        return original_validator(
            ca_pem,
            crl_pem,
            policy=policy,
            now=now,
        )

    controller._crl_validator = recording_validator

    # The provider's paired observation is 500 ms older than the
    # controller's subsequent local BOOTTIME sample.
    time_state["trusted_boot_offset_ns"] = -500_000_000

    assert controller.begin_recovery(candidate)
    assert observed_times
    assert observed_times[0] == (
        time_state["now"] + timedelta(milliseconds=500)
    )


def test_future_trusted_boottime_reference_blocks(admission_environment):
    controller, _, time_state, _, candidate = admission_environment

    # Even a one-nanosecond future reference is invalid. The tolerance
    # only permits an older provider observation, not a future one.
    time_state["trusted_boot_offset_ns"] = 1

    assert not controller.begin_recovery(candidate)
    assert controller.state is AdmissionState.BLOCKED


def test_inconsistent_boottime_observation_blocks(admission_environment):
    controller, clock, time_state, active, _ = admission_environment
    activate_initial(controller, active)

    clock.advance(timedelta(seconds=10))
    # The provider deliberately returns an observation from ten seconds ago.
    time_state["trusted_boot_offset_ns"] = -10_000_000_000

    assert not controller.admit_new_connection()
    assert controller.state is AdmissionState.BLOCKED


def test_candidate_is_activated_only_after_recovery_completion(
    admission_environment,
):
    controller, _, _, active, candidate = admission_environment
    activate_initial(controller, active)

    assert controller.begin_update()
    assert controller.begin_recovery(candidate)

    assert controller.snapshot.active_crl_sha256 == active.crl_sha256
    assert controller.snapshot.candidate_crl_sha256 == candidate.crl_sha256

    assert controller.complete_recovery(tls_verifier=lambda _crl: True)

    assert controller.snapshot.active_crl_sha256 == candidate.crl_sha256
    assert controller.snapshot.candidate_crl_sha256 is None
    assert controller.state is AdmissionState.READY


def test_candidate_deadline_is_not_extended_during_recovery(
    admission_environment,
):
    controller, clock, time_state, active, candidate = admission_environment
    activate_initial(controller, active)

    assert controller.begin_update()
    assert controller.begin_recovery(candidate)

    original_candidate_deadline = controller._candidate_deadline_ns

    clock.advance(timedelta(seconds=5))
    time_state["now"] -= timedelta(minutes=5)

    assert controller.complete_recovery(tls_verifier=lambda _crl: True)
    assert (
        controller.snapshot.deadline_boottime_ns
        <= original_candidate_deadline
    )


def test_expired_candidate_cannot_recover(admission_environment):
    controller, clock, time_state, active, candidate = admission_environment
    activate_initial(controller, active)

    assert controller.begin_update()
    assert controller.begin_recovery(candidate)

    clock.advance(timedelta(minutes=1))
    time_state["now"] = candidate.next_update + timedelta(seconds=1)

    assert not controller.complete_recovery(tls_verifier=lambda _crl: True)
    assert controller.state is AdmissionState.BLOCKED


def test_gateway_style_controllers_are_independent(admission_environment):
    controller_a, clock, state, active, candidate = admission_environment

    activate_initial(controller_a, active)

    policy = CRLPolicy(
        max_age=timedelta(hours=1),
        clock_skew=timedelta(minutes=2),
    )

    controller_b = AdmissionController(
        policy,
        lambda: (_ for _ in ()).throw(RuntimeError("no backend time")),
        boottime_clock=clock,
        crl_validator=lambda *args, **kwargs: candidate,
    )

    assert controller_a.state is AdmissionState.READY
    assert controller_b.state is AdmissionState.BLOCKED
    assert controller_a.admit_new_connection()
    assert not controller_b.admit_new_connection()
