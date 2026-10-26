function t(message) {
    return window.lumsT?.[message] || message;
}

const statusElement = document.getElementById("system-update-status");
const currentVersionElement = document.getElementById("update-current-version");
const targetVersionElement = document.getElementById("update-target-version");
const targetCommitElement = document.getElementById("update-target-commit");
const agentStatusElement = document.getElementById("update-agent-status");
const compatibilityElement = document.getElementById("update-compatibility");
const releaseNotesElement = document.getElementById("update-release-notes");
const releaseLink = document.getElementById("update-release-link");
const installButton = document.getElementById("start-system-update");
const refreshButton = document.getElementById("refresh-system-update");
const historyBody = document.getElementById("update-history-body");
const historyStatus = document.getElementById("update-history-status");
const stepList = document.getElementById("update-step-list");
const csrfToken = document.querySelector('meta[name="csrf-token"]').content;

let currentRelease = null;
let requestInProgress = false;

function setStatus(message, state) {
    statusElement.textContent = message || "";
    statusElement.dataset.state = state || "";
}

function isActive(job) {
    return ["queued", "running", "rolling_back"].includes(job.status);
}

function translateStatus(value) {
    const labels = {
        queued: "Queued",
        running: "Running",
        rolling_back: "Rolling back",
        completed: "Completed",
        failed: "Failed",
        rolled_back: "Rolled back",
        rollback_failed: "Rollback failed",
        preflight: "Check prerequisites",
        backup: "Create verified backup",
        prepare: "Prepare and test release",
        switch: "Switch application",
        verify: "Verify application and database",
        result: "Record result or rollback",
    };
    return t(labels[value] || value || "Unknown");
}

function renderSteps(job) {
    const progress = new Map(
        (job?.progress || []).map((item) => [item.step, item])
    );
    for (const item of stepList.querySelectorAll("[data-step]")) {
        const current = progress.get(item.dataset.step);
        item.dataset.state = current?.status || "";
        if (current?.message) {
            item.title = current.message;
        } else {
            item.removeAttribute("title");
        }
        const label = item.dataset.label || item.textContent.trim();
        item.dataset.label = label;
        item.textContent = current
            ? `${label} — ${translateStatus(current.status)}`
            : label;
    }
}

function renderHistory(history) {
    historyBody.replaceChildren();
    if (!history.length) {
        historyStatus.textContent = t("No update attempts have been recorded yet.");
        return;
    }

    historyStatus.textContent = "";
    for (const job of history) {
        const row = document.createElement("tr");
        const values = [
            job.requested_at,
            job.requested_by,
            job.target_tag,
            translateStatus(job.step),
            translateStatus(job.status),
            job.error || job.rollback_status || job.details?.summary || "",
        ];
        for (const value of values) {
            const cell = document.createElement("td");
            cell.textContent = value || "—";
            row.append(cell);
        }
        historyBody.append(row);
    }
}

async function loadSystemUpdates() {
    if (requestInProgress) {
        return;
    }
    requestInProgress = true;
    refreshButton.disabled = true;
    try {
        const response = await fetch("/api/system-updates", {
            headers: { Accept: "application/json" },
            cache: "no-store",
        });
        const data = await response.json();
        if (!response.ok) {
            throw new Error(data.error || t("Could not load update status."));
        }

        const agentOnline = Boolean(data.agent?.online);
        currentVersionElement.textContent =
            data.agent?.current_version || t("Not reported");
        agentStatusElement.textContent = agentOnline
            ? t("Connected")
            : t("Not connected");
        compatibilityElement.textContent = agentOnline
            ? t("Release is CI-tested; host checks are required before switching.")
            : t("Host checks unavailable until the host service is connected.");

        currentRelease = data.release;
        targetVersionElement.textContent = data.release
            ? `${data.release.name} (${data.release.tag})`
            : "—";
        targetCommitElement.textContent = data.release?.commit || "—";
        releaseNotesElement.textContent = data.release?.notes
            || (data.release_error
                ? data.release_error
                : t("No release information loaded."));
        if (data.release?.url) {
            releaseLink.href = data.release.url;
            releaseLink.hidden = false;
        } else {
            releaseLink.removeAttribute("href");
            releaseLink.hidden = true;
        }

        const activeJob = data.history.find(isActive);
        renderSteps(activeJob);
        renderHistory(data.history);
        installButton.disabled = !(
            agentOnline && currentRelease && !activeJob
        );
        if (activeJob) {
            setStatus(
                `${t("Update in progress")}: ${activeJob.target_tag} — ${translateStatus(activeJob.step)}`,
                "loading"
            );
        } else if (!agentOnline) {
            setStatus(
                data.agent?.status_message
                    || t("The host update service is not connected. No update can be started."),
                "warning"
            );
        } else if (data.release_error) {
            setStatus(data.release_error, "error");
        } else {
            setStatus(t("Release information is current."), "success");
        }
    } catch (error) {
        currentRelease = null;
        installButton.disabled = true;
        setStatus(error.message || t("Could not load update status."), "error");
    } finally {
        refreshButton.disabled = false;
        requestInProgress = false;
    }
}

async function requestSystemUpdate() {
    if (!currentRelease || installButton.disabled) {
        return;
    }
    const confirmed = window.confirm(
        `${t("Install this release?")} ${currentRelease.tag}\n\n${t("The host service will create a verified backup and will attempt rollback if any step fails.")}`
    );
    if (!confirmed) {
        return;
    }

    installButton.disabled = true;
    setStatus(t("Submitting update request..."), "loading");
    try {
        const response = await fetch("/api/system-updates", {
            method: "POST",
            headers: {
                Accept: "application/json",
                "Content-Type": "application/json",
                "X-CSRF-Token": csrfToken,
            },
            body: "{}",
        });
        const data = await response.json();
        if (!response.ok) {
            throw new Error(data.error || t("The update request was rejected."));
        }
        setStatus(
            `${t("Update request accepted")}: ${data.target_tag}`,
            "loading"
        );
        await loadSystemUpdates();
    } catch (error) {
        setStatus(error.message || t("The update request was rejected."), "error");
        installButton.disabled = false;
    }
}

refreshButton.addEventListener("click", loadSystemUpdates);
installButton.addEventListener("click", requestSystemUpdate);
loadSystemUpdates();
window.setInterval(loadSystemUpdates, 15000);
