"""Fail-closed TLS admission state machine for one SOC component.

This module controls admission decisions. It does not create TLS listeners,
perform staging handshakes, fetch CRLs, or implement a trusted-time provider.

The trusted_time_reader must return a value produced by read_trusted_time().
Recovery completes only after an injected verifier performs a real
isolated staging TLS check.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Callable

from server.soc.crl_validation import (
    CRLPolicy,
    CRLValidationError,
    ValidatedCRL,
    validate_direct_crl,
)
from server.soc.trusted_time import TrustedTime


UTC = timezone.utc
_NS_PER_SECOND = 1_000_000_000
_NS_PER_MICROSECOND = 1_000


class AdmissionError(RuntimeError):
    """Raised when an admission state transition is invalid."""


class AdmissionState(str, Enum):
    BLOCKED = "BLOCKED"
    READY = "READY"
    UPDATE_PENDING = "UPDATE_PENDING"
    RECOVERY = "RECOVERY"


@dataclass(frozen=True)
class AdmissionSnapshot:
    state: AdmissionState
    deadline_boottime_ns: int | None
    active_crl_sha256: str | None
    candidate_crl_sha256: str | None


def _duration_ns(value: timedelta) -> int:
    return (
        (value.days * 86_400 + value.seconds) * _NS_PER_SECOND
        + value.microseconds * _NS_PER_MICROSECOND
    )


class AdmissionController:
    """Thread-safe fail-closed admission controller.

    Each controller represents exactly one TLS component and one CRL trust
    role. Gateway and backend must use independent controller instances.

    The monotonic deadline is established from the earlier of:
      * CRL nextUpdate
      * CRL thisUpdate + configured maximum age

    A safety margin is subtracted. Revalidation can shorten an established
    deadline but can never extend it.

    New connections must call admit_new_connection() at the actual TLS
    admission boundary. Existing TLS connections are not revoked by this
    class and require a separately implemented drain/termination policy.
    """

    def __init__(
        self,
        policy: CRLPolicy,
        trusted_time_reader: Callable[[], TrustedTime],
        *,
        safety_margin: timedelta = timedelta(seconds=30),
        observation_tolerance: timedelta = timedelta(seconds=2),
        boottime_clock: Callable[[], int],
        crl_validator: Callable[..., ValidatedCRL] = validate_direct_crl,
    ) -> None:
        if not isinstance(policy, CRLPolicy):
            raise TypeError("policy must be a CRLPolicy instance")

        if not callable(trusted_time_reader):
            raise TypeError("trusted_time_reader must be callable")

        if not callable(boottime_clock):
            raise TypeError("boottime_clock must be callable")

        if not callable(crl_validator):
            raise TypeError("crl_validator must be callable")

        if (
            not isinstance(safety_margin, timedelta)
            or safety_margin < timedelta(0)
        ):
            raise ValueError("safety_margin must be a non-negative timedelta")

        if (
            not isinstance(observation_tolerance, timedelta)
            or observation_tolerance < timedelta(0)
        ):
            raise ValueError(
                "observation_tolerance must be a non-negative timedelta"
            )

        self._policy = policy
        self._trusted_time_reader = trusted_time_reader
        self._safety_margin = safety_margin
        self._observation_tolerance_ns = _duration_ns(
            observation_tolerance
        )
        self._boottime_clock = boottime_clock
        self._crl_validator = crl_validator

        self._lock = threading.RLock()
        self._state = AdmissionState.BLOCKED
        self._active_crl: ValidatedCRL | None = None
        self._candidate_crl: ValidatedCRL | None = None
        self._deadline_ns: int | None = None
        self._candidate_deadline_ns: int | None = None
        self._recovery_verification_in_progress = False

    @property
    def state(self) -> AdmissionState:
        with self._lock:
            return self._state

    @property
    def snapshot(self) -> AdmissionSnapshot:
        with self._lock:
            return AdmissionSnapshot(
                state=self._state,
                deadline_boottime_ns=self._deadline_ns,
                active_crl_sha256=(
                    self._active_crl.crl_sha256
                    if self._active_crl is not None
                    else None
                ),
                candidate_crl_sha256=(
                    self._candidate_crl.crl_sha256
                    if self._candidate_crl is not None
                    else None
                ),
            )

    def _block_locked(self) -> None:
        self._state = AdmissionState.BLOCKED
        self._deadline_ns = None
        self._candidate_crl = None
        self._candidate_deadline_ns = None

    def _read_observation(self) -> tuple[TrustedTime, int, datetime]:
        trusted = self._trusted_time_reader()

        if not isinstance(trusted, TrustedTime):
            raise AdmissionError("Trusted time is missing or invalid")

        if (
            not isinstance(trusted.utc_now, datetime)
            or trusted.utc_now.tzinfo is None
            or trusted.utc_now.utcoffset() is None
        ):
            raise AdmissionError("Trusted UTC time is invalid")

        if type(trusted.boottime_ns) is not int or trusted.boottime_ns < 0:
            raise AdmissionError("Trusted BOOTTIME reference is invalid")

        if (
            not isinstance(trusted.source_id, str)
            or not trusted.source_id.strip()
        ):
            raise AdmissionError("Trusted time source identity is missing")

        if (
            not isinstance(trusted.sync_age, timedelta)
            or trusted.sync_age < timedelta(0)
        ):
            raise AdmissionError("Trusted time synchronization age is invalid")

        if (
            not isinstance(trusted.offset, timedelta)
            or not isinstance(trusted.uncertainty, timedelta)
            or trusted.uncertainty < timedelta(0)
        ):
            raise AdmissionError("Trusted time quality metadata is invalid")

        try:
            now_boot = self._boottime_clock()
        except Exception as exc:
            raise AdmissionError("BOOTTIME cannot be read") from exc

        if type(now_boot) is not int or now_boot < 0:
            raise AdmissionError("BOOTTIME returned an invalid value")

        # The local BOOTTIME sample is taken after the provider's
        # UTC/BOOTTIME pair. Never accept a provider reference that lies
        # in the future relative to this later local sample.
        if now_boot < trusted.boottime_ns:
            raise AdmissionError(
                "Trusted BOOTTIME reference is ahead of local BOOTTIME"
            )

        elapsed_ns = now_boot - trusted.boottime_ns
        if elapsed_ns > self._observation_tolerance_ns:
            raise AdmissionError(
                "Trusted-time and local BOOTTIME observations disagree"
            )

        # Round elapsed time up to the next microsecond. This avoids
        # understating elapsed time when converting nanoseconds to the
        # datetime resolution used by the CRL validator.
        elapsed_microseconds = (
            elapsed_ns + _NS_PER_MICROSECOND - 1
        ) // _NS_PER_MICROSECOND

        try:
            effective_utc = (
                trusted.utc_now.astimezone(UTC)
                + timedelta(microseconds=elapsed_microseconds)
            )
        except (OverflowError, TypeError, ValueError) as exc:
            raise AdmissionError(
                "Effective trusted UTC time is invalid"
            ) from exc

        return trusted, now_boot, effective_utc

    def _validate_crl(
        self,
        crl: ValidatedCRL,
        now_utc: datetime,
    ) -> ValidatedCRL:
        if not isinstance(crl, ValidatedCRL):
            raise AdmissionError("CRL material is invalid")

        try:
            result = self._crl_validator(
                crl.ca_pem,
                crl.crl_pem,
                policy=self._policy,
                now=now_utc,
            )
        except Exception as exc:
            raise AdmissionError("CRL validation failed") from exc

        if not isinstance(result, ValidatedCRL):
            raise AdmissionError("CRL validator returned an invalid result")

        return result

    def _calculate_deadline(
        self,
        crl: ValidatedCRL,
        now_utc: datetime,
        now_boot: int,
    ) -> int:
        try:
            now_utc = now_utc.astimezone(UTC)
            latest_allowed = min(
                crl.next_update,
                crl.this_update + self._policy.max_age,
            )
            remaining = latest_allowed - now_utc - self._safety_margin
            remaining_ns = _duration_ns(remaining)
        except (AttributeError, OverflowError, TypeError, ValueError) as exc:
            raise AdmissionError("CRL admission deadline is invalid") from exc

        if remaining_ns <= 0:
            raise AdmissionError("CRL admission deadline has been reached")

        deadline = now_boot + remaining_ns
        if deadline <= now_boot:
            raise AdmissionError("CRL admission deadline overflowed")

        return deadline

    def _refresh_active_locked(self) -> None:
        if self._active_crl is None:
            raise AdmissionError("No active CRL is installed")

        trusted, now_boot, effective_utc = self._read_observation()
        validated = self._validate_crl(self._active_crl, effective_utc)
        proposed_deadline = self._calculate_deadline(
            validated,
            effective_utc,
            now_boot,
        )

        if self._deadline_ns is None:
            self._deadline_ns = proposed_deadline
        else:
            # A wall-clock rollback or delayed revalidation must never
            # extend a deadline already established in this process.
            self._deadline_ns = min(
                self._deadline_ns,
                proposed_deadline,
            )

        self._active_crl = validated

        if now_boot >= self._deadline_ns:
            raise AdmissionError("Monotonic CRL admission deadline reached")

    def admit_new_connection(self) -> bool:
        """Return whether a new TLS handshake may be admitted.

        This method must be called at the actual handshake boundary, not
        merely when an HTTP request reaches the Flask application.
        """
        with self._lock:
            if self._state not in (
                AdmissionState.READY,
                AdmissionState.UPDATE_PENDING,
            ):
                return False

            try:
                self._refresh_active_locked()
            except Exception:
                self._block_locked()
                return False

            return True

    def begin_update(self) -> bool:
        """Enter UPDATE_PENDING while retaining the active CRL."""
        with self._lock:
            if self._state is not AdmissionState.READY:
                raise AdmissionError(
                    "CRL update can only begin from READY"
                )

            try:
                self._refresh_active_locked()
            except Exception:
                self._block_locked()
                return False

            self._state = AdmissionState.UPDATE_PENDING
            return True

    def fail_update(self) -> bool:
        """Reject a candidate update and retain the old CRL if still valid."""
        with self._lock:
            if self._state is not AdmissionState.UPDATE_PENDING:
                raise AdmissionError(
                    "CRL update failure requires UPDATE_PENDING"
                )

            try:
                self._refresh_active_locked()
            except Exception:
                self._block_locked()
                return False

            self._state = AdmissionState.READY
            return True

    def begin_recovery(self, candidate: ValidatedCRL) -> bool:
        """Preflight a candidate and enter RECOVERY without admitting TLS."""
        with self._lock:
            if self._state not in (
                AdmissionState.BLOCKED,
                AdmissionState.UPDATE_PENDING,
            ):
                raise AdmissionError(
                    "Recovery requires BLOCKED or UPDATE_PENDING"
                )

            previous_state = self._state

            try:
                trusted, now_boot, effective_utc = self._read_observation()
                validated = self._validate_crl(candidate, effective_utc)
                deadline = self._calculate_deadline(
                    validated,
                    effective_utc,
                    now_boot,
                )
            except Exception:
                # A rejected update candidate must not unnecessarily
                # invalidate an otherwise usable active CRL.
                if previous_state is AdmissionState.UPDATE_PENDING:
                    try:
                        self._refresh_active_locked()
                    except Exception:
                        self._block_locked()
                    else:
                        self._candidate_crl = None
                        self._candidate_deadline_ns = None
                        self._state = AdmissionState.READY
                else:
                    self._block_locked()

                return False

            self._candidate_crl = validated
            self._candidate_deadline_ns = deadline
            self._state = AdmissionState.RECOVERY
            return True

    def _fail_recovery_locked(self) -> None:
        # Once RECOVERY has been entered, any activation or verification
        # failure must keep admission blocked. The old CRL is retained
        # for diagnostics, but must not silently restore READY.
        self._block_locked()

    def complete_recovery(
        self,
        *,
        tls_verifier: Callable[[ValidatedCRL], bool],
    ) -> bool:
        """Activate only after the supplied staging TLS verifier succeeds.

        The verifier must be bounded, must not re-enter this controller, and
        must not trigger admission state transitions. Reentrant completion
        attempts are rejected. The lock remains held during verification.
        """
        if not callable(tls_verifier):
            raise TypeError("tls_verifier must be callable")

        with self._lock:
            if self._state is not AdmissionState.RECOVERY:
                raise AdmissionError(
                    "Recovery completion requires RECOVERY"
                )

            if self._recovery_verification_in_progress:
                raise AdmissionError(
                    "Recovery verification is already in progress"
                )

            if (
                self._candidate_crl is None
                or self._candidate_deadline_ns is None
            ):
                self._block_locked()
                return False

            self._recovery_verification_in_progress = True
            try:
                try:
                    verification_result = tls_verifier(self._candidate_crl)
                    if verification_result is not True:
                        raise AdmissionError(
                            "Staging TLS verification did not succeed"
                        )

                    trusted, now_boot, effective_utc = self._read_observation()
                    validated = self._validate_crl(
                        self._candidate_crl,
                        effective_utc,
                    )
                    proposed_deadline = self._calculate_deadline(
                        validated,
                        effective_utc,
                        now_boot,
                    )

                    # Do not extend the candidate's deadline while recovery
                    # verification is in progress.
                    deadline = min(
                        self._candidate_deadline_ns,
                        proposed_deadline,
                    )

                    if now_boot >= deadline:
                        raise AdmissionError(
                            "Candidate CRL deadline expired during recovery"
                        )

                except Exception:
                    self._fail_recovery_locked()
                    return False

                self._active_crl = validated
                self._deadline_ns = deadline
                self._candidate_crl = None
                self._candidate_deadline_ns = None
                self._state = AdmissionState.READY
                return True
            finally:
                self._recovery_verification_in_progress = False
