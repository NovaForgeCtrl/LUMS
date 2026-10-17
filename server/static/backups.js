function t(message) {
    return window.lumsT?.[message] || message;
}

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
    return `${t("Backups")}: ${new Intl.NumberFormat(window.lumsLocale).format(count)}`;
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

    return `${new Intl.NumberFormat(window.lumsLocale, {
        maximumFractionDigits: 1,
    }).format(size)} ${units[unitIndex]}`;
}


function renderBackups(backups) {
    backupListBody.replaceChildren();

    if (backups.length === 0) {
        const row = document.createElement("tr");
        const cell = document.createElement("td");
        cell.colSpan = 5;
        cell.textContent = t("No backups yet.");
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
            ? t("Compressed SQLite (.db.gz)")
            : t("SQLite (.db)");
        createdCell.textContent = new Intl.DateTimeFormat(
            window.lumsLocale,
            {
                dateStyle: "medium",
                timeStyle: "medium",
                timeZone: "UTC",
            }
        ).format(new Date(backup.created_at)) + " UTC";
        sizeCell.textContent = formatBackupSize(backup.size_bytes);
        deleteButton.type = "button";
        deleteButton.className = "backup-delete-button";
        deleteButton.textContent = t("Delete");
        deleteButton.setAttribute(
            "aria-label",
            `${t("Delete backup")} ${backup.filename}`
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
    backupListStatus.textContent = t("Loading backups...");
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
                t("Backup folder is missing or not writable by LUMS.")
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
            t("CSRF token could not be found.");
        backupStatus.dataset.state = "error";
        return;
    }

    createBackupButton.disabled = true;
    refreshBackupsButton.disabled = true;
    createBackupButton.textContent = t("Creating backup...");
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
                    t("Choose a valid subfolder in backup storage."),
                invalid_backup_format:
                    t("Choose a supported file format."),
                backup_storage_unavailable:
                    result.message ||
                    t("Backup destination is missing or not writable."),
                backup_failed:
                    t("Database backup failed. Check the server log."),
                backup_audit_failed:
                    `Backup ${result.backup?.filename || ""} wurde erstellt, ` +
                    `${t("but its audit entry could not be saved. Check the server log.")}`,
                csrf_validation_failed:
                    t("CSRF validation failed. Reload the page."),
            };
            throw new Error(
                messages[result.error] ||
                `${t("Could not create backup")} (HTTP ${response.status}).`
            );
        }

        backupStatus.textContent =
            `${t("Backup created")}: ${result.backup.filename} ` +
            `(${formatBackupSize(result.backup.size_bytes)}).`;
        backupStatus.dataset.state = "success";
        await loadBackups();
    } catch (error) {
        console.error(error);
        backupStatus.textContent = error.message;
        backupStatus.dataset.state = "error";
    } finally {
        createBackupButton.disabled = false;
        createBackupButton.textContent = t("Create backup now");
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
            ? t("CSRF token could not be found.")
            : t("No backup selected for deletion.");
        deleteBackupError.hidden = false;
        return;
    }

    confirmDeleteBackupButton.disabled = true;
    cancelDeleteBackupButton.disabled = true;
    confirmDeleteBackupButton.textContent = t("Deleting...");

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
                    result.message || t("Invalid backup path."),
                backup_not_found:
                    t("Backup no longer exists. Refresh the list."),
                backup_storage_unavailable:
                    result.message || t("Backup storage is unavailable."),
                backup_delete_failed:
                    t("Could not delete backup. Check the server log."),
                backup_audit_failed:
                    t("Backup was deleted, but its audit entry failed. Check the server log."),
                csrf_validation_failed:
                    t("CSRF validation failed. Reload the page."),
            };
            throw new Error(
                messages[result.error] ||
                `${t("Could not delete backup")} (HTTP ${response.status}).`
            );
        }

        deleteBackupDialog.close();
        selectedBackupFilename = null;
        backupStatus.textContent = `${t("Backup deleted")}: ${result.filename}`;
        backupStatus.dataset.state = "success";
        await loadBackups();
    } catch (error) {
        console.error(error);
        deleteBackupError.textContent = error.message;
        deleteBackupError.hidden = false;
    } finally {
        confirmDeleteBackupButton.disabled = false;
        cancelDeleteBackupButton.disabled = false;
        confirmDeleteBackupButton.textContent = t("Delete backup");
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
            t("Enter a relative subfolder without '..' or backslashes.");
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
