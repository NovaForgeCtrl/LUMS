#!/usr/bin/env python3

"""
LUMS Execution Watcher

Watcher 1.2.1

Responsibilities:
- Detect pending update jobs.
- Determine local idle state.
- Wait until the configured idle threshold is reached.
- Atomically claim the pending job.
- Execute the claimed update job.
- Send the execution result back to LUMS.

Safety rules:
- Idle state must be supported.
- Client must be idle for the configured threshold.
- Job must be atomically claimed before execution.
- Only the successfully claimed job is executed.
"""

import sys


WATCHER_VERSION = "1.2.1"

AGENT_PATH = "/opt/lums-agent"

if AGENT_PATH not in sys.path:
    sys.path.insert(0, AGENT_PATH)


from agent import (  # noqa: E402
    get_client,
    get_pending_job,
    get_running_job,
    get_idle_status,
    claim_job,
    execute_job,
    status_ok,
    status_warn,
    status_fail,
    c,
    GREEN,
    RED,
    YELLOW,
    CYAN,
    WHITE,
)


def format_duration(seconds):
    seconds = max(0, int(seconds))

    minutes = seconds // 60
    remaining = seconds % 60

    return f"{minutes:02d}:{remaining:02d}"


def print_header():
    print()
    print(c(CYAN, "═" * 64))
    print(
        c(
            CYAN,
            f"LUMS // EXECUTION WATCHER {WATCHER_VERSION}"
        )
    )
    print(c(CYAN, "═" * 64))


def main():
    print_header()

    # ========================================================
    # CLIENT AUTHENTICATION
    # ========================================================

    try:
        client = get_client()

        status_ok(
            f"CLIENT AUTHENTICATED // ID {client['id']}"
        )

    except Exception as error:
        status_fail(
            f"CLIENT LOOKUP FAILED // {error}"
        )
        return 1

    # ========================================================
    # RUNNING JOB RECOVERY
    # ========================================================

    try:
        running_job = get_running_job(client["id"])

    except Exception as error:
        status_fail(
            f"RUNNING JOB LOOKUP FAILED // {error}"
        )
        return 1

    if running_job and running_job.get("status") == "running":
        running_job_id = running_job.get("job_id")
        running_packages = running_job.get(
            "packages",
            []
        )

        print()
        print(
            f"  RUNNING JOB  "
            f"{c(WHITE, '#' + str(running_job_id))}"
        )

        print(
            f"  PACKAGES     "
            f"{c(WHITE, str(len(running_packages)))}"
        )

        print()
        status_warn(
            "RUNNING JOB DETECTED // RESUMING"
        )

        print(
            c(
                CYAN,
                "  NO CLAIM // JOB ALREADY RUNNING"
            )
        )

        print(
            c(
                CYAN,
                "  STARTING UPDATE ENGINE"
            )
        )

        print()

        try:
            execute_job(running_job)

        except Exception as error:
            status_fail(
                f"UPDATE EXECUTION FAILED // {error}"
            )

            print()
            print(
                c(
                    RED,
                    "WATCHER // RECOVERY EXECUTION ABORTED"
                )
            )

            return 1

        print()
        print(
            c(
                GREEN,
                "WATCHER // RECOVERY EXECUTION COMPLETE"
            )
        )

        return 0

    # ========================================================
    # PENDING JOB
    # ========================================================

    try:
        job = get_pending_job(client["id"])

    except Exception as error:
        status_fail(
            f"JOB LOOKUP FAILED // {error}"
        )
        return 1

    if not job or job.get("status") == "no_job":
        status_ok(
            "NO UPDATE JOB // SYSTEM CLEAN"
        )

        print()
        print(
            c(
                GREEN,
                "WATCHER // CYCLE COMPLETE"
            )
        )

        return 0

    job_id = job.get("job_id")

    print()
    print(
        f"  JOB        "
        f"{c(WHITE, '#' + str(job_id))}"
    )

    # ========================================================
    # LOCAL IDLE CHECK
    # ========================================================

    try:
        idle_status = get_idle_status()

    except Exception as error:
        status_fail(
            f"IDLE CHECK FAILED // {error}"
        )
        return 1

    idle_supported = bool(
        idle_status.get("idle_supported")
    )

    idle = bool(
        idle_status.get("idle")
    )

    idle_seconds = max(
        0,
        int(
            idle_status.get(
                "idle_seconds",
                0
            )
        )
    )

    threshold = max(
        1,
        int(
            idle_status.get(
                "threshold_seconds",
                300
            )
        )
    )

    idle_source = str(
        idle_status.get(
            "idle_source",
            "unknown"
        )
    )

    print()
    print(
        f"  IDLE SOURCE   "
        f"{c(CYAN, idle_source)}"
    )

    print(
        f"  IDLE SUPPORT  "
        f"{c(
            GREEN if idle_supported else RED,
            str(idle_supported)
        )}"
    )

    print(
        f"  IDLE TIME     "
        f"{c(
            WHITE,
            format_duration(idle_seconds)
        )}"
    )

    print(
        f"  THRESHOLD     "
        f"{c(
            WHITE,
            format_duration(threshold)
        )}"
    )

    print()

    # ========================================================
    # SAFETY: IDLE NOT SUPPORTED
    # ========================================================

    if not idle_supported:
        status_warn(
            "IDLE STATE UNSUPPORTED"
        )

        print(
            c(
                YELLOW,
                "  NO CLAIM // NO EXECUTION"
            )
        )

        return 0

    # ========================================================
    # SAFETY: CLIENT STILL ACTIVE
    # ========================================================

    if not idle or idle_seconds < threshold:
        remaining = max(
            0,
            threshold - idle_seconds
        )

        status_warn(
            "WAITING FOR IDLE // "
            f"{format_duration(remaining)} remaining"
        )

        print()
        print(
            c(
                YELLOW,
                "  JOB REMAINS PENDING"
            )
        )

        print(
            c(
                YELLOW,
                "  NO CLAIM // NO EXECUTION"
            )
        )

        return 0

    # ========================================================
    # IDLE THRESHOLD REACHED
    # ========================================================

    status_ok(
        "IDLE THRESHOLD REACHED"
    )

    print(
        c(
            CYAN,
            "  CLAIMING UPDATE JOB..."
        )
    )

    # ========================================================
    # ATOMIC CLAIM
    # ========================================================

    try:
        claimed_job = claim_job(
            client["id"],
            job_id
        )

    except Exception as error:
        status_fail(
            f"JOB CLAIM FAILED // {error}"
        )
        return 1

    if not claimed_job:
        status_warn(
            "JOB CLAIMED BY ANOTHER WATCHER"
        )

        print(
            c(
                YELLOW,
                "  NO EXECUTION"
            )
        )

        return 0

    if claimed_job.get("status") != "ok":
        status_warn(
            "JOB CLAIM REJECTED"
        )

        print(
            f"  SERVER STATUS  "
            f"{claimed_job.get('job_status', 'unknown')}"
        )

        print(
            c(
                YELLOW,
                "  NO EXECUTION"
            )
        )

        return 0

    # ========================================================
    # CLAIM SUCCESS
    # ========================================================

    claimed_job_id = claimed_job.get(
        "job_id",
        job_id
    )

    packages = claimed_job.get(
        "packages",
        []
    )

    started_at = claimed_job.get(
        "started_at",
        "unknown"
    )

    status_ok(
        f"JOB CLAIMED // #{claimed_job_id}"
    )

    print()
    print(
        f"  STATE       "
        f"{c(GREEN, 'running')}"
    )

    print(
        f"  STARTED     "
        f"{c(WHITE, str(started_at))}"
    )

    print(
        f"  PACKAGES    "
        f"{c(WHITE, str(len(packages)))}"
    )

    print()

    # ========================================================
    # EXECUTION
    # ========================================================

    print(
        c(
            CYAN,
            "  EXECUTION ENABLED"
        )
    )

    print(
        c(
            CYAN,
            "  STARTING UPDATE ENGINE"
        )
    )

    print()

    try:
        execute_job(claimed_job)

    except Exception as error:
        status_fail(
            f"UPDATE EXECUTION FAILED // {error}"
        )

        print()
        print(
            c(
                RED,
                "WATCHER // EXECUTION ABORTED"
            )
        )

        return 1

    print()
    print(
        c(
            GREEN,
            "WATCHER // EXECUTION COMPLETE"
        )
    )

    return 0


if __name__ == "__main__":
    sys.exit(main())
