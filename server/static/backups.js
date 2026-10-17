const backupForm = document.getElementById("backup-create-form");
const backupStatus = document.getElementById("backup-status");
const backupListStatus = document.getElementById("backup-list-status");
const backupListBody = document.getElementById("backup-list-body");
const createBackupButton = document.getElementById("create-backup-button");
const backupLocationSelectButton = document.getElementById(
    "change-backup-location-button"
);
const refreshBackupsButton = document.getElementById(
    "refresh-backups-button"
);
const backupRoot = document.getElementById("backup-root").textContent.trim();
const backupCurrentPath = document.getElementById("backup-current-path");
const changeBackupLocationButton = document.getElementById(
    "change-backup-location-button"
);
const backupLocationDialog = document.getElementById(
    "backup-location-dialog"
);
const backupLocationForm = document.getElementById(
    "backup-location-form"
);
const backupRelativePathInput = document.getElementById(
    "backup-relative-path"
);
const backupLocationError = document.getElementById(
    "backup-location-error"
);
const cancelBackupLocationButton = document.getElementById(
    "cancel-backup-location-button"
);
const deleteBackupDialog = document.getElementById("delete-backup-dialog");
const deleteBackupForm = document.getElementById("delete-backup-form");
const deleteBackupFilename = document.getElementById(
    "delete-backup-filename"
);
const deleteBackupError = document.getElementById("delete-backup-error");
const confirmDeleteBackupButton = document.getElementById(
    "confirm-delete-backup-button"
);
const cancelDeleteBackupButton = document.getElementById(
    "cancel-delete-backup-button"
);
let backupRelativePath = "";
let selectedBackupFilename = null;


function updateBackupLocationLabel() {
    backupCurrentPath.textContent = backupRelativePath
        ? `${backupRoot}/${backupRelativePath}`
        : backupRoot;
}


function formatBackupCount(count) {
    if (count === 1) {
        return "1 Backup wird angezeigt.";
    }

    return `${count} Backups werden angezeigt.`;
}


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
        cell.colSpan = 5;
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
        const actionCell = document.createElement("td");
        const deleteButton = document.createElement("button");

        filenameCell.textContent = backup.filename;
        formatCell.textContent = backup.format === "db.gz"
            ? "SQLite (.db.gz)"
            : "SQLite (.db)";
        createdCell.textContent = backup.created_at
            .replace("T", " ")
            .replace("+00:00", " UTC");
        sizeCell.textContent = formatBackupSize(backup.size_bytes);
        deleteButton.type = "button";
        deleteButton.className = "backup-delete-button";
        deleteButton.textContent = "Löschen";
        deleteButton.setAttribute(
            "aria-label",
            `Backup ${backup.filename} löschen`
        );
        deleteButton.addEventListener("click", () => {
            selectedBackupFilename = backup.filename;
            deleteBackupFilename.textContent = backup.filename;
            deleteBackupError.hidden = true;
            deleteBackupError.textContent = "";
            deleteBackupDialog.showModal();
        });
        actionCell.appendChild(deleteButton);

        row.append(
            filenameCell,
            formatCell,
            createdCell,
            sizeCell,
            actionCell
        );
        backupListBody.appendChild(row);
    }
}


async function loadBackups() {
    backupListStatus.textContent = "Backups werden geladen …";
    backupListStatus.dataset.state = "";
    refreshBackupsButton.disabled = true;

    try {
        const query = new URLSearchParams({
            path: backupRelativePath,
        });
        const response = await fetch(`/api/backups?${query}`);
        const result = await response.json();

        if (!response.ok) {
            throw new Error(
                result.message ||
                "Backup-Ordner fehlt oder ist für LUMS nicht beschreibbar."
            );
        }

        renderBackups(result.backups);
        backupListStatus.textContent = formatBackupCount(
            result.backups.length
        );
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
                path: backupRelativePath,
            }),
        });
        const result = await response.json();

        if (!response.ok) {
            const messages = {
                invalid_backup_path:
                    result.message ||
                    "Bitte wähle einen gültigen Unterordner im Backup-Speicher.",
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


async function deleteBackup(event) {
    event.preventDefault();
    const csrfToken = document.querySelector(
        'meta[name="csrf-token"]'
    )?.content;

    if (!csrfToken || !selectedBackupFilename) {
        deleteBackupError.textContent = !csrfToken
            ? "CSRF-Token konnte nicht gefunden werden."
            : "Es wurde kein Backup zum Löschen ausgewählt.";
        deleteBackupError.hidden = false;
        return;
    }

    confirmDeleteBackupButton.disabled = true;
    cancelDeleteBackupButton.disabled = true;
    confirmDeleteBackupButton.textContent = "Wird gelöscht …";

    try {
        const query = new URLSearchParams({
            path: backupRelativePath,
        });
        const response = await fetch(
            `/api/backups/${encodeURIComponent(selectedBackupFilename)}?${query}`,
            {
                method: "DELETE",
                headers: {
                    "X-CSRF-Token": csrfToken,
                },
            }
        );
        const result = await response.json();

        if (!response.ok) {
            const messages = {
                invalid_backup_path:
                    result.message || "Ungültiger Backup-Pfad.",
                backup_not_found:
                    "Das Backup ist nicht mehr vorhanden. Aktualisiere die Liste.",
                backup_storage_unavailable:
                    result.message || "Backup-Speicher ist nicht verfügbar.",
                backup_delete_failed:
                    "Backup konnte nicht gelöscht werden. Serverprotokoll prüfen.",
                backup_audit_failed:
                    "Backup wurde gelöscht, aber der Audit-Eintrag schlug fehl. Serverprotokoll prüfen.",
                csrf_validation_failed:
                    "CSRF-Prüfung fehlgeschlagen. Bitte Seite neu laden.",
            };
            throw new Error(
                messages[result.error] ||
                `Backup konnte nicht gelöscht werden (HTTP ${response.status}).`
            );
        }

        deleteBackupDialog.close();
        selectedBackupFilename = null;
        backupStatus.textContent = `Backup gelöscht: ${result.filename}`;
        backupStatus.dataset.state = "success";
        await loadBackups();
    } catch (error) {
        console.error(error);
        deleteBackupError.textContent = error.message;
        deleteBackupError.hidden = false;
    } finally {
        confirmDeleteBackupButton.disabled = false;
        cancelDeleteBackupButton.disabled = false;
        confirmDeleteBackupButton.textContent = "Backup löschen";
    }
}


backupForm.addEventListener("submit", createBackup);
refreshBackupsButton.addEventListener("click", loadBackups);
backupLocationSelectButton.addEventListener("click", () => {
    backupLocationError.hidden = true;
    backupLocationError.textContent = "";
    backupRelativePathInput.value = backupRelativePath;
    backupLocationDialog.showModal();
    backupRelativePathInput.focus();
});
cancelBackupLocationButton.addEventListener("click", () => {
    backupLocationDialog.close();
});
backupLocationForm.addEventListener("submit", event => {
    event.preventDefault();
    const relativePath = backupRelativePathInput.value.trim();
    const pathParts = relativePath.split("/");

    if (
        relativePath.startsWith("/") ||
        relativePath.includes("\\") ||
        pathParts.includes("..")
    ) {
        backupLocationError.textContent =
            "Bitte einen relativen Unterordner ohne „..“ oder Backslashes angeben.";
        backupLocationError.hidden = false;
        return;
    }

    backupRelativePath = relativePath;
    updateBackupLocationLabel();
    backupLocationDialog.close();
    loadBackups();
});
deleteBackupForm.addEventListener("submit", deleteBackup);
cancelDeleteBackupButton.addEventListener("click", () => {
    selectedBackupFilename = null;
    deleteBackupDialog.close();
});
updateBackupLocationLabel();
loadBackups();
