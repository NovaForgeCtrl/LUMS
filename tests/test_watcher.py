import importlib.util
import sys
import types
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
WATCHER_MODULE_PATH = REPO_ROOT / "agent" / "watcher.py"


def load_watcher():
    fake_agent = types.ModuleType("agent")

    fake_agent.get_client = lambda: None
    fake_agent.get_pending_job = lambda client_id: None
    fake_agent.get_running_job = lambda client_id: None
    fake_agent.get_idle_status = lambda: None
    fake_agent.claim_job = lambda client_id, job_id: None
    fake_agent.execute_job = lambda job: None

    fake_agent.status_ok = lambda *args, **kwargs: None
    fake_agent.status_warn = lambda *args, **kwargs: None
    fake_agent.status_fail = lambda *args, **kwargs: None
    fake_agent.c = lambda color, text: text

    fake_agent.GREEN = ""
    fake_agent.RED = ""
    fake_agent.YELLOW = ""
    fake_agent.CYAN = ""
    fake_agent.WHITE = ""

    previous_agent = sys.modules.get("agent")
    sys.modules["agent"] = fake_agent

    try:
        spec = importlib.util.spec_from_file_location(
            "lums_watcher",
            WATCHER_MODULE_PATH,
        )

        module = importlib.util.module_from_spec(spec)
        sys.modules["lums_watcher"] = module
        spec.loader.exec_module(module)

        return module

    finally:
        if previous_agent is not None:
            sys.modules["agent"] = previous_agent
        else:
            sys.modules.pop("agent", None)


def test_watcher_accepts_successful_claim_and_executes_job(monkeypatch):
    watcher = load_watcher()

    client = {
        "id": 1,
        "hostname": "test-client",
    }

    pending_job = {
        "status": "pending",
        "job_id": 42,
    }

    claimed_job = {
        "status": "claimed",
        "job_id": 42,
        "client_id": 1,
        "started_at": "2026-09-28T00:00:00+00:00",
        "reboot_required": False,
        "action": "UPDATE",
        "packages": [],
    }

    executed = []

    monkeypatch.setattr(
        watcher,
        "get_client",
        lambda: client,
    )

    monkeypatch.setattr(
        watcher,
        "get_running_job",
        lambda client_id: None,
    )

    monkeypatch.setattr(
        watcher,
        "get_pending_job",
        lambda client_id: pending_job,
    )

    monkeypatch.setattr(
        watcher,
        "get_idle_status",
        lambda: {
            "idle_supported": True,
            "idle": True,
            "idle_seconds": 600,
            "threshold_seconds": 300,
            "idle_source": "test",
        },
    )

    monkeypatch.setattr(
        watcher,
        "claim_job",
        lambda client_id, job_id: claimed_job,
    )

    monkeypatch.setattr(
        watcher,
        "execute_job",
        lambda job: executed.append(job),
    )

    assert watcher.main() == 0
    assert executed == [claimed_job]
