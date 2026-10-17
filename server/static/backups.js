const backupForm = document.getElementById("backup-create-form");
const backupStatus = document.getElementById("backup-status");
const backupListStatus = document.getElementById("backup-list-status");
const backupListBody = document.getElementById("backup-list-body");
const createBackupButton = document.getElementById("create-backup-button");
const refreshBackupsButton = document.getElementById(
    "refresh-backups-button"
);


function formatBackupSize(bytes) {
    if (bytes < 1024) {
        return `${bytes} B`;
    }

    const units = ["KB", "MB", "GB", "TB"];
    let size = bytes / 1024;
    let unitIndex = 0;

    while (size >= 1024 && unitIndex < units.length - 1) {
        size /= 1024;
        unitIndex += 1;
    }

    return `${size.toFixed(1)} ${units[unitIndex]}`;
}


function renderBackups(backups) {
    backupListBody.replaceChildren();

    if (backups.length === 0) {
        const row = document.createElement("tr");
        const cell = document.createElement("td");
        cell.colSpan = 4;
        cell.textContent = "Noch keine Backups vorhanden.";
        row.appendChild(cell);
        backupListBody.appendChild(row);
        return;
    }

    for (const backup of backups) {
        const row = document.createElement("tr");
        const filenameCell = document.createElement("td");
        const formatCell = document.createElement("td");
        const createdCell = document.createElement("td");
        const sizeCell = document.createElement("td");

        filenameCell.textContent = backup.filename;
        formatCell.textContent = backup.format === "db.gz"
            ? "SQLite (.db.gz)"
            : "SQLite (.db)";
        createdCell.textContent = backup.created_at
            .replace("T", " ")
            .replace("+00:00", " UTC");
        sizeCell.textContent = formatBackupSize(backup.size_bytes);

        row.append(
            filenameCell,
            formatCell,
            createdCell,
            sizeCell
        );
        backupListBody.appendChild(row);
    }
}


async function loadBackups() {
    backupListStatus.textContent = "Backups werden geladen …";
    backupListStatus.dataset.state = "";
    refreshBackupsButton.disabled = true;

    try {
        const response = await fetch("/api/backups");
        const result = await response.json();

        if (!response.ok) {
            throw new Error(
                result.message ||
                "Backup-Ordner fehlt oder ist für LUMS nicht beschreibbar."
            );
        }

        renderBackups(result.backups);
        backupListStatus.textContent =
            `${result.backups.length} aktuelle Backups angezeigt.`;
    } catch (error) {
        console.error(error);
        backupListStatus.textContent = error.message;
        backupListStatus.dataset.state = "error";
        backupListBody.replaceChildren();
    } finally {
        refreshBackupsButton.disabled = false;
    }
}


async function createBackup(event) {
    event.preventDefault();

    const csrfToken = document.querySelector(
        'meta[name="csrf-token"]'
    )?.content;

    if (!csrfToken) {
        backupStatus.textContent =
            "CSRF-Token konnte nicht gefunden werden.";
        backupStatus.dataset.state = "error";
        return;
    }

    createBackupButton.disabled = true;
    refreshBackupsButton.disabled = true;
    createBackupButton.textContent = "Backup wird erstellt …";
    backupStatus.textContent = "";
    backupStatus.dataset.state = "";

    try {
        const response = await fetch("/api/backups", {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "X-CSRF-Token": csrfToken,
            },
            body: JSON.stringify({
                format: document.getElementById("backup-format").value,
            }),
        });
        const result = await response.json();

        if (!response.ok) {
            const messages = {
                invalid_backup_format:
                    "Bitte wähle ein unterstütztes Dateiformat.",
                backup_storage_unavailable:
                    result.message ||
                    "Backup-Zielordner fehlt oder ist nicht beschreibbar.",
                backup_failed:
                    "Die Datenbanksicherung ist fehlgeschlagen. Serverprotokoll prüfen.",
                backup_audit_failed:
                    `Backup ${result.backup?.filename || ""} wurde erstellt, ` +
                    "aber der Audit-Eintrag konnte nicht gespeichert werden. Serverprotokoll prüfen.",
                csrf_validation_failed:
                    "CSRF-Prüfung fehlgeschlagen. Bitte Seite neu laden.",
            };
            throw new Error(
                messages[result.error] ||
                `Backup konnte nicht erstellt werden (HTTP ${response.status}).`
            );
        }

        backupStatus.textContent =
            `Backup erstellt: ${result.backup.filename} ` +
            `(${formatBackupSize(result.backup.size_bytes)}).`;
        backupStatus.dataset.state = "success";
        await loadBackups();
    } catch (error) {
        console.error(error);
        backupStatus.textContent = error.message;
        backupStatus.dataset.state = "error";
    } finally {
        createBackupButton.disabled = false;
        createBackupButton.textContent = "Backup jetzt erstellen";
        refreshBackupsButton.disabled = false;
    }
}


backupForm.addEventListener("submit", createBackup);
refreshBackupsButton.addEventListener("click", loadBackups);
loadBackups();
