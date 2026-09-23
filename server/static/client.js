const params = new URLSearchParams(window.location.search);
const clientId = params.get("id");

let allPackages = [];
let updates = [];
let updateJobs = [];
let updateHistory = [];

let currentFilter = "system";
let currentSearch = "";


/*
 * HTML sicher ausgeben
 */
function escapeHtml(value) {

    if (value === null || value === undefined) {
        return "";
    }

    return String(value)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}


/*
 * Datum formatieren
 */
function formatDate(value) {

    if (!value) {
        return "–";
    }

    const date = new Date(value);

    if (Number.isNaN(date.getTime())) {
        return value;
    }

    return date.toLocaleString("de-DE");
}


/*
 * Systempakete erkennen
 */
function isSystemPackage(packageName) {

    const name = packageName.toLowerCase();


    const exactSystemPackages = [

        "apt",
        "bash",
        "base-files",
        "base-passwd",
        "coreutils",
        "dash",
        "debconf",
        "debianutils",
        "diffutils",
        "dpkg",
        "findutils",
        "grep",
        "gzip",
        "hostname",
        "init-system-helpers",
        "login",
        "mount",
        "ncurses-base",
        "ncurses-bin",
        "passwd",
        "perl-base",
        "sed",
        "tar",
        "ubuntu-keyring",
        "util-linux"
    ];


    if (exactSystemPackages.includes(name)) {
        return true;
    }


    const libraryPrefixes = [

        "lib",
        "lib32",
        "lib64",
        "libx32"
    ];


    for (const prefix of libraryPrefixes) {

        if (name.startsWith(prefix)) {
            return true;
        }
    }


    const systemPrefixes = [

        "systemd",
        "linux-",
        "linux-image",
        "linux-headers",
        "linux-modules",
        "initramfs",
        "udev",
        "dbus",
        "network-manager",
        "netplan",
        "cloud-init",
        "apparmor",
        "sudo",
        "openssh-client",
        "openssh-sftp-server",
        "python3-minimal",
        "python3.14-minimal",
        "python3-distutils"
    ];


    for (const prefix of systemPrefixes) {

        if (name.startsWith(prefix)) {
            return true;
        }
    }


    const systemTools = [

        "awk",
        "busybox",
        "cron",
        "fdisk",
        "kmod",
        "logrotate",
        "procps",
        "rsyslog",
        "software-properties-common",
        "tzdata",
        "vim-common",
        "vim-runtime"
    ];


    if (systemTools.includes(name)) {
        return true;
    }


    return false;
}


/*
 * Update für Paket finden
 */
function getUpdateForPackage(packageName) {

    return updates.find(update =>
        update.package === packageName
    );
}


/*
 * Paketstatus
 */
function renderPackageStatus(packageName) {

    const update = getUpdateForPackage(packageName);

    if (update) {

        return `
            <span class="package-status update">
                Update verfügbar
            </span>
        `;
    }

    return `
        <span class="package-status current">
            Aktuell
        </span>
    `;
}


/*
 * Pakete filtern
 */
function getFilteredPackages() {

    let result = [...allPackages];


    if (currentFilter === "system") {

        result = result.filter(pkg =>
            isSystemPackage(pkg.package)
        );

    } else if (currentFilter === "additional") {

        result = result.filter(pkg =>
            !isSystemPackage(pkg.package)
        );
    }


    if (currentSearch) {

        const search = currentSearch.toLowerCase();

        result = result.filter(pkg =>
            pkg.package.toLowerCase().includes(search)
        );
    }


    return result;
}


/*
 * Paketliste darstellen
 */
function renderPackages() {

    const table = document.getElementById("packages-table");
    const count = document.getElementById("visible-package-count");

    const packages = getFilteredPackages();


    count.textContent = packages.length;


    if (packages.length === 0) {

        table.innerHTML = `
            <tr>
                <td colspan="3" class="empty-state">
                    Keine Pakete gefunden.
                </td>
            </tr>
        `;

        return;
    }


    table.innerHTML = packages.map(pkg => {

        return `
            <tr>

                <td>
                    <strong>
                        ${escapeHtml(pkg.package)}
                    </strong>
                </td>

                <td class="version">
                    ${escapeHtml(pkg.version)}
                </td>

                <td>
                    ${renderPackageStatus(pkg.package)}
                </td>

            </tr>
        `;

    }).join("");
}


/*
 * Update-Auswahl
 */
function renderUpdates() {

    const container =
        document.getElementById("updates-container");


    if (!container) {
        return;
    }


    /*
     * Systemstatus
     */
    const systemStatus = updates.length
        ? `
            <div class="update-summary">

                <strong>
                    ${updates.length}
                    Update${updates.length === 1 ? "" : "s"}
                    verfügbar
                </strong>

            </div>
        `
        : `
            <div class="success-state">
                ✓ System aktuell
            </div>
        `;


    /*
     * Verfügbare Updates
     *
     * Die Tabelle und Auswahlfunktionen werden
     * nur angezeigt, wenn Updates vorhanden sind.
     */
    const updateList = updates.length
        ? `

            <div class="update-actions">

                <button
                    type="button"
                    id="select-all-updates"
                    class="secondary-button"
                >
                    Alle auswählen
                </button>

                <button
                    type="button"
                    id="clear-all-updates"
                    class="secondary-button"
                >
                    Auswahl aufheben
                </button>

                <button
                    type="button"
                    id="install-selected-updates"
                    class="primary-button"
                >
                    Ausgewählte Updates installieren
                </button>

            </div>


            <div class="table-wrapper">

                <table class="data-table update-table">

                    <thead>

                        <tr>

                            <th style="width: 50px;">
                                <input
                                    type="checkbox"
                                    id="select-all-checkbox"
                                    title="Alle Updates auswählen"
                                >
                            </th>

                            <th>Paket</th>

                            <th>Installiert</th>

                            <th>Verfügbar</th>

                        </tr>

                    </thead>

                    <tbody>

                        ${updates.map((update, index) => `

                            <tr>

                                <td>

                                    <input
                                        type="checkbox"
                                        class="update-checkbox"
                                        data-index="${index}"
                                    >

                                </td>

                                <td>
                                    <strong>
                                        ${escapeHtml(update.package)}
                                    </strong>
                                </td>

                                <td class="version">
                                    ${escapeHtml(
                                        update.installed_version || "–"
                                    )}
                                </td>

                                <td class="version">
                                    ${escapeHtml(
                                        update.available_version || "–"
                                    )}
                                </td>

                            </tr>

                        `).join("")}

                    </tbody>

                </table>

            </div>


            <div
                id="update-selection-info"
                class="package-summary"
            >
                0 Updates ausgewählt
            </div>

        `
        : "";


    /*
     * Systemwartung
     *
     * Dieser Bereich wird unabhängig davon angezeigt,
     * ob einzelne Updates verfügbar sind.
     */
    const systemMaintenance = `

        <div class="update-system-actions">

            <div class="panel-description">
                Systemwartung
            </div>

            <button
                type="button"
                id="update-system-button"
                class="button"
            >
                System vollständig aktualisieren
            </button>

        </div>

    `;


    /*
     * Gesamten Update-Bereich rendern
     */
    container.innerHTML = `

        ${systemStatus}

        ${updateList}

        ${systemMaintenance}

    `;


    /*
     * Event-Handler nach dem Rendern binden
     */
    bindUpdateControls();
}



/*
 * Update-Auswahl aktualisieren
 */
function updateSelectionInfo() {

    const checkboxes =
        document.querySelectorAll(".update-checkbox");

    const selected =
        document.querySelectorAll(
            ".update-checkbox:checked"
        ).length;

    const info =
        document.getElementById("update-selection-info");

    if (info) {

        info.textContent =
            `${selected} Update${selected === 1 ? "" : "s"} ausgewählt`;
    }


    const selectAllCheckbox =
        document.getElementById("select-all-checkbox");

    if (selectAllCheckbox) {

        selectAllCheckbox.checked =
            checkboxes.length > 0 &&
            selected === checkboxes.length;
    }
}


/*
 * Update-Steuerung
 */
function bindUpdateControls() {

    const checkboxes =
        document.querySelectorAll(".update-checkbox");


    checkboxes.forEach(checkbox => {

        checkbox.addEventListener(
            "change",
            updateSelectionInfo
        );

    });


    const selectAllCheckbox =
        document.getElementById("select-all-checkbox");

    if (selectAllCheckbox) {

        selectAllCheckbox.addEventListener(
            "change",
            () => {

                checkboxes.forEach(checkbox => {
                    checkbox.checked =
                        selectAllCheckbox.checked;
                });

                updateSelectionInfo();
            }
        );
    }


    const selectAllButton =
        document.getElementById("select-all-updates");

    if (selectAllButton) {

        selectAllButton.addEventListener(
            "click",
            () => {

                checkboxes.forEach(checkbox => {
                    checkbox.checked = true;
                });

                updateSelectionInfo();
            }
        );
    }


    const clearAllButton =
        document.getElementById("clear-all-updates");

    if (clearAllButton) {

        clearAllButton.addEventListener(
            "click",
            () => {

                checkboxes.forEach(checkbox => {
                    checkbox.checked = false;
                });

                updateSelectionInfo();
            }
        );
    }


    const installButton =
        document.getElementById("install-selected-updates");

    if (installButton) {

        installButton.addEventListener(
            "click",
            createUpdateJob
        );
    }


    const systemUpdateButton =
        document.getElementById("update-system-button");

    if (systemUpdateButton) {

        systemUpdateButton.addEventListener(
            "click",
            createSystemUpdateJob
        );
    }


    updateSelectionInfo();
}


/*
 * Update-Job erstellen
 */
async function createUpdateJob() {

    const checkboxes =
        document.querySelectorAll(
            ".update-checkbox:checked"
        );


    if (checkboxes.length === 0) {

        alert(
            "Bitte mindestens ein Update auswählen."
        );

        return;
    }


    const selectedPackages =
        Array.from(checkboxes)
            .map(checkbox => {

                const index =
                    Number(checkbox.dataset.index);

                return updates[index]?.package;

            })
            .filter(Boolean);


    const installButton =
        document.getElementById(
            "install-selected-updates"
        );


    if (installButton) {

        installButton.disabled = true;
        installButton.textContent =
            "Update-Job wird erstellt...";
    }


    try {

        const response =
            await fetch(
                `/api/clients/${clientId}/update-jobs`,
                {
                    method: "POST",

                    headers: {
                        "Content-Type":
                            "application/json",

                        "X-CSRF-Token":
                            document.querySelector(
                                'meta[name="csrf-token"]'
                            ).content
                    },

                    body: JSON.stringify({
                        packages: selectedPackages
                    })
                }
            );


        const result =
            await response.json();


        if (!response.ok) {

            throw new Error(
                result.error ||
                "Update-Job konnte nicht erstellt werden."
            );
        }


        alert(
            `Update-Job #${result.job_id} wurde erstellt.\n\n` +
            `${result.package_count} Paket` +
            `${result.package_count === 1 ? "" : "e"} ` +
            `wurden ausgewählt.`
        );


        await loadJobs();


    } catch (error) {

        console.error(error);

        alert(
            `Fehler beim Erstellen des Update-Jobs:\n${error.message}`
        );


    } finally {

        if (installButton) {

            installButton.disabled = false;
            installButton.textContent =
                "Ausgewählte Updates installieren";
        }
    }
}


/*
 * System-Update-Job erstellen
 */
async function createSystemUpdateJob() {

    const button =
        document.getElementById(
            "update-system-button"
        );

    if (button) {

        button.disabled = true;
        button.textContent =
            "System-Update wird erstellt...";
    }


    try {

        const response =
            await fetch(
                `/api/clients/${clientId}/update-jobs`,
                {
                    method: "POST",

                    headers: {
                        "Content-Type":
                            "application/json",

                        "X-CSRF-Token":
                            document.querySelector(
                                'meta[name="csrf-token"]'
                            ).content
                    },

                    body: JSON.stringify({
                        action: "UPDATE_SYSTEM"
                    })
                }
            );


        const result =
            await response.json();


        if (!response.ok) {

            throw new Error(
                result.error ||
                "System-Update-Job konnte nicht erstellt werden."
            );
        }


        alert(
            `System-Update-Job #${result.job_id} wurde erstellt.`
        );


        await loadJobs();


    } catch (error) {

        console.error(error);

        alert(
            `Fehler beim Erstellen des System-Update-Jobs:
${error.message}`
        );


    } finally {

        if (button) {

            button.disabled = false;
            button.textContent =
                "System vollständig aktualisieren";
        }
    }
}


/*
 * Update-Jobs laden
 */
async function loadJobs() {

    const container =
        document.getElementById("jobs-container");


    try {

        const response =
            await fetch(
                `/api/clients/${clientId}/update-jobs`
            );


        if (!response.ok) {

            throw new Error(
                "Update-Jobs konnten nicht geladen werden."
            );
        }


        updateJobs =
            await response.json();


        renderJobs();


    } catch (error) {

        console.error(error);

        container.innerHTML = `
            <div class="error-state">
                Update-Jobs konnten nicht geladen werden.
            </div>
        `;
    }
}


/*
 * Status eines Update-Jobs darstellen
 */
function renderJobStatus(status) {

    const normalized =
        String(status || "").toLowerCase();


    if (normalized === "pending") {

        return `
            <span class="package-status update">
                Wartend
            </span>
        `;
    }


    if (normalized === "running") {

        return `
            <span class="package-status update">
                Läuft
            </span>
        `;
    }


    if (normalized === "success") {

        return `
            <span class="package-status current">
                ✓ Erfolgreich
            </span>
        `;
    }


    if (normalized === "failed") {

        return `
            <span class="package-status update">
                ✗ Fehlgeschlagen
            </span>
        `;
    }


    if (normalized === "partial") {

        return `
            <span class="package-status update">
                ⚠ Teilweise erfolgreich
            </span>
        `;
    }


    return `
        <span class="package-status">
            ${escapeHtml(status || "Unbekannt")}
        </span>
    `;
}


/*
 * Update-Jobs darstellen
 */
function renderJobs() {

    const container =
        document.getElementById("jobs-container");


    if (!updateJobs.length) {

        container.innerHTML = `
            <div class="empty-state">
                Keine Update-Jobs vorhanden.
            </div>
        `;

        return;
    }


    container.innerHTML = `

        <div class="table-wrapper">

            <table class="data-table">

                <thead>

                    <tr>
                        <th>Job</th>
                        <th>Status</th>
                        <th>Pakete</th>
                        <th>Erstellt</th>
                        <th>Abgeschlossen</th>
                    </tr>

                </thead>

                <tbody>

                    ${updateJobs.map(job => `

                        <tr>

                            <td>
                                <strong>
                                    #${escapeHtml(job.id)}
                                </strong>
                            </td>

                            <td>
                                ${renderJobStatus(job.status)}
                            </td>

                            <td>
                                ${escapeHtml(
                                    job.package_count ?? "0"
                                )}
                            </td>

                            <td class="version">
                                ${formatDate(job.created_at)}
                            </td>

                            <td class="version">
                                ${formatDate(job.finished_at)}
                            </td>

                        </tr>

                    `).join("")}

                </tbody>

            </table>

        </div>

    `;
}


/*
 * Update-Verlauf laden
 */
async function loadHistory() {

    const container =
        document.getElementById("history-container");


    try {

        const response =
            await fetch(
                `/api/clients/${clientId}/update-history`
            );


        if (!response.ok) {

            throw new Error(
                "Update-Verlauf konnte nicht geladen werden."
            );
        }


        updateHistory =
            await response.json();


        renderHistory();


    } catch (error) {

        console.error(error);

        container.innerHTML = `
            <div class="error-state">
                Update-Verlauf konnte nicht geladen werden.
            </div>
        `;
    }
}


/*
 * Update-Verlauf darstellen
 */
function renderHistory() {

    const container =
        document.getElementById("history-container");


    if (!updateHistory.length) {

        container.innerHTML = `
            <div class="empty-state">
                Noch kein Update-Verlauf vorhanden.
            </div>
        `;

        return;
    }


    container.innerHTML = `

        <div class="table-wrapper">

            <table class="data-table">

                <thead>

                    <tr>
                        <th>Status</th>
                        <th>Pakete</th>
                        <th>Erfolgreich</th>
                        <th>Fehlgeschlagen</th>
                        <th>Neustart</th>
                        <th>Start</th>
                        <th>Ende</th>
                    </tr>

                </thead>

                <tbody>

                    ${updateHistory.map(entry => `

                        <tr>

                            <td>
                                ${renderJobStatus(entry.status)}
                            </td>

                            <td>
                                ${escapeHtml(
                                    entry.package_count ?? "0"
                                )}
                            </td>

                            <td>
                                ${escapeHtml(
                                    entry.successful_count ?? "0"
                                )}
                            </td>

                            <td>
                                ${escapeHtml(
                                    entry.failed_count ?? "0"
                                )}
                            </td>

                            <td>
                                ${
                                    entry.reboot_required
                                        ? "⚠ Ja"
                                        : "Nein"
                                }
                            </td>

                            <td class="version">
                                ${formatDate(entry.started_at)}
                            </td>

                            <td class="version">
                                ${formatDate(entry.finished_at)}
                            </td>

                        </tr>

                    `).join("")}

                </tbody>

            </table>

        </div>

    `;
}


/*
 * Client laden
 */
async function loadClient() {

    try {

        const response =
            await fetch(`/api/clients/${clientId}`);


        if (!response.ok) {

            throw new Error(
                "Client konnte nicht geladen werden."
            );
        }


        const client =
            await response.json();


        document.getElementById("hostname").textContent =
            client.hostname || "–";


        document.getElementById("ip").textContent =
            client.ip || "–";


        document.getElementById("os").textContent =
            client.os || "–";


        document.getElementById("kernel").textContent =
            client.kernel || "–";


        document.getElementById("architecture").textContent =
            client.architecture || "–";


        document.getElementById("agent-version").textContent =
            client.agent_version || "–";


        document.getElementById("last-seen").textContent =
            formatDate(client.last_seen);


        document.getElementById("package-count").textContent =
            client.package_count ?? "–";


        document.getElementById("update-count").textContent =
            client.update_count ?? "–";


        const status =
            document.getElementById("status");


        status.textContent =
            client.status || "UNKNOWN";


        status.className =
            "status-badge " +
            String(
                client.status || ""
            ).toLowerCase();


    } catch (error) {

        console.error(error);

        document.getElementById("hostname").textContent =
            "Fehler";
    }
}


/*
 * Updates laden
 */
async function loadUpdates() {

    try {

        const response =
            await fetch(
                `/api/clients/${clientId}/updates`
            );


        if (!response.ok) {

            throw new Error(
                "Updates konnten nicht geladen werden."
            );
        }


        updates =
            await response.json();


        renderUpdates();
        renderPackages();


    } catch (error) {

        console.error(error);

        document.getElementById(
            "updates-container"
        ).innerHTML = `
            <div class="error-state">
                Updates konnten nicht geladen werden.
            </div>
        `;
    }
}


/*
 * Pakete laden
 */
async function loadPackages() {

    try {

        const response =
            await fetch(
                `/api/clients/${clientId}/packages`
            );


        if (!response.ok) {

            throw new Error(
                "Pakete konnten nicht geladen werden."
            );
        }


        allPackages =
            await response.json();


        renderPackages();


    } catch (error) {

        console.error(error);

        document.getElementById(
            "packages-table"
        ).innerHTML = `
            <tr>
                <td colspan="3" class="empty-state">
                    Pakete konnten nicht geladen werden.
                </td>
            </tr>
        `;
    }
}


/*
 * Tabs
 */
document
    .querySelectorAll(".software-tab")
    .forEach(button => {

        button.addEventListener(
            "click",
            () => {

                document
                    .querySelectorAll(".software-tab")
                    .forEach(tab =>
                        tab.classList.remove("active")
                    );


                button.classList.add("active");


                currentFilter =
                    button.dataset.filter;


                renderPackages();
            }
        );
    });


/*
 * Suche
 */
document
    .getElementById("package-search")
    .addEventListener(
        "input",
        event => {

            currentSearch =
                event.target.value.trim();


            renderPackages();
        }
    );


/*
 * Client-Token rotieren
 */
async function rotateClientToken() {

    const hostname =
        document.getElementById("hostname").textContent.trim();

    const confirmed = window.confirm(
        `Token für Client "${hostname}" wirklich rotieren?\n\n` +
        "Der bisherige Token wird sofort ungültig.\n\n" +
        "Der LUMS-Agent muss anschließend mit dem neuen Token " +
        "konfiguriert werden.\n\n" +
        "Fortfahren?"
    );

    if (!confirmed) {
        return;
    }


    const button =
        document.getElementById(
            "rotate-client-token-button"
        );


    button.disabled = true;
    button.textContent = "Wird rotiert...";


    try {

        const csrfToken =
            document.querySelector(
                'meta[name="csrf-token"]'
            )?.content;


        if (!csrfToken) {

            throw new Error(
                "CSRF-Token konnte nicht gefunden werden."
            );
        }


        const response =
            await fetch(
                `/api/clients/${clientId}/token/rotate`,
                {
                    method: "POST",

                    headers: {
                        "X-CSRF-Token": csrfToken
                    }
                }
            );


        const data =
            await response.json();


        if (!response.ok) {

            throw new Error(
                data.error ||
                "Client-Token konnte nicht rotiert werden."
            );
        }


        const token =
            data.token;


        if (!token) {

            throw new Error(
                "Server hat keinen neuen Token zurückgegeben."
            );
        }


        const tokenResult =
            document.getElementById(
                "token-rotation-result"
            );


        const tokenDisplay =
            document.getElementById(
                "rotated-client-token"
            );


        tokenDisplay.textContent = token;


        tokenResult.hidden = false;


        tokenResult.scrollIntoView({
            behavior: "smooth",
            block: "start"
        });


        button.textContent = "🔐 Token rotiert";


    } catch (error) {

        console.error(error);


        alert(
            "Client-Token konnte nicht rotiert werden.\n\n" +
            error.message
        );


        button.textContent = "🔐 Token rotieren";


    } finally {

        button.disabled = false;
    }
}


const rotateClientTokenButton =
    document.getElementById(
        "rotate-client-token-button"
    );


if (rotateClientTokenButton) {

    rotateClientTokenButton.addEventListener(
        "click",
        rotateClientToken
    );
}


/*
 * Rotierten Client-Token kopieren
 */
const copyRotatedClientTokenButton =
    document.getElementById(
        "copy-rotated-client-token"
    );


if (copyRotatedClientTokenButton) {

    copyRotatedClientTokenButton.addEventListener(
        "click",
        async () => {

            const tokenElement =
                document.getElementById(
                    "rotated-client-token"
                );


            const token =
                tokenElement?.textContent.trim();


            if (!token) {

                alert(
                    "Kein Client-Token zum Kopieren vorhanden."
                );

                return;
            }


            try {

                await navigator.clipboard.writeText(
                    token
                );


                copyRotatedClientTokenButton.textContent =
                    "✓ Token kopiert";


                window.setTimeout(
                    () => {

                        copyRotatedClientTokenButton.textContent =
                            "📋 Token kopieren";

                    },
                    2000
                );


            } catch (error) {

                console.error(error);


                alert(
                    "Token konnte nicht in die Zwischenablage kopiert werden."
                );
            }
        }
    );
}


/*
 * Client entfernen
 */
async function deleteClient() {

    const hostname =
        document.getElementById("hostname").textContent.trim();

    const confirmed = window.confirm(
        `Client "${hostname}" wirklich entfernen?\n\n` +
        "Der Client kann anschließend erneut angelegt werden."
    );

    if (!confirmed) {
        return;
    }

    const button =
        document.getElementById("delete-client-button");

    button.disabled = true;
    button.textContent = "Wird entfernt...";

    try {

        const csrfToken =
            document.querySelector('meta[name="csrf-token"]')?.content;

        if (!csrfToken) {
            throw new Error("CSRF-Token konnte nicht gefunden werden.");
        }

        const response =
            await fetch(`/api/clients/${clientId}`, {
                method: "DELETE",
                headers: {
                    "X-CSRF-Token": csrfToken
                }
            });

        const data =
            await response.json();

        if (!response.ok) {
            throw new Error(
                data.error || "Client konnte nicht entfernt werden."
            );
        }

        window.location.href = "/";

    } catch (error) {

        console.error(error);

        alert(
            "Client konnte nicht entfernt werden.\n\n" +
            error.message
        );

        button.disabled = false;
        button.textContent = "🗑️ Client entfernen";
    }
}


const deleteClientButton =
    document.getElementById("delete-client-button");

if (deleteClientButton) {

    deleteClientButton.addEventListener(
        "click",
        deleteClient
    );
}


/*
 * Start
 */
if (!clientId) {

    document.getElementById("hostname").textContent =
        "Keine Client-ID angegeben.";

} else {

    loadClient();
    loadUpdates();
    loadPackages();
    loadJobs();
    loadHistory();
}
