function t(message, values = {}) {
    const translated = window.lumsT?.[message] || message;
    return Object.entries(values).reduce(
        (text, [key, value]) =>
            text.split(`{${key}}`).join(String(value)),
        translated
    );
}

const params = new URLSearchParams(window.location.search);
const clientId = params.get("id");

let allPackages = [];
let updates = [];
let updateJobs = [];
let updateHistory = [];

let currentFilter = "system";
let currentSearch = "";

function userHasPermission(permission) {
    return (window.lumsUserPermissions || []).includes(permission);
}


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

    return date.toLocaleString(window.lumsLocale);
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
                ${t("Update available")}
            </span>
        `;
    }

    return `
        <span class="package-status current">
            ${t("Up to date")}
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

    if (!table || !count) {
        return;
    }

    const packages = getFilteredPackages();


    count.textContent = packages.length;


    if (packages.length === 0) {

        table.innerHTML = `
            <tr>
                <td colspan="3" class="empty-state">
                    ${t("No packages found.")}
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

    const canManageJobs = userHasPermission("jobs.manage");

    /*
     * Systemstatus
     */
    const systemStatus = updates.length
        ? `
            <div class="update-summary">

                <strong>
                    ${t("{count} updates available", {
                        count: new Intl.NumberFormat(window.lumsLocale).format(
                            updates.length
                        ),
                    })}
                </strong>

            </div>
        `
        : `
            <div class="success-state">
                ✓ ${t("System is up to date")}
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

            ${canManageJobs ? `
            <div class="update-actions">

                <button
                    type="button"
                    id="select-all-updates"
                    class="secondary-button"
                >
                    ${t("Select all")}
                </button>

                <button
                    type="button"
                    id="clear-all-updates"
                    class="secondary-button"
                >
                    ${t("Clear selection")}
                </button>

                <button
                    type="button"
                    id="install-selected-updates"
                    class="primary-button"
                >
                    ${t("Install selected updates")}
                </button>

            </div>
            ` : ""}


            <div class="table-wrapper">

                <table class="data-table update-table">

                    <thead>

                        <tr>

                            ${canManageJobs ? `
                            <th class="update-select-column">
                                <input
                                    type="checkbox"
                                    id="select-all-checkbox"
                                    title="${t("Select all updates")}"
                                >
                            </th>
                            ` : ""}

                            <th>${t("Package")}</th>

                            <th>${t("Installed")}</th>

                            <th>${t("Available")}</th>

                        </tr>

                    </thead>

                    <tbody>

                        ${updates.map((update, index) => `

                            <tr>

                                ${canManageJobs ? `
                                <td>

                                    <input
                                        type="checkbox"
                                        class="update-checkbox"
                                        data-index="${index}"
                                    >

                                </td>
                                ` : ""}

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


            ${canManageJobs ? `<div
                id="update-selection-info"
                class="package-summary"
            >
                ${t("{count} updates selected", { count: 0 })}
            </div>` : ""}

        `
        : "";


    /*
     * Systemwartung
     *
     * Dieser Bereich wird unabhängig davon angezeigt,
     * ob einzelne Updates verfügbar sind.
     */
    const systemMaintenance =
        !canManageJobs
            ? ""
            : `

        <div class="update-system-actions">

            <div class="panel-description">
                ${t("System maintenance")}
            </div>

            <button
                type="button"
                id="update-system-button"
                class="button"
            >
                ${t("Update the entire system")}
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

        info.textContent = t("{count} updates selected", {
            count: new Intl.NumberFormat(window.lumsLocale).format(selected),
        });
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
            t("Select at least one update.")
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
            t("Creating update job...");
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
                t("Could not create update job.")
            );
        }


        alert(
            t("Update job #{jobId} created; {count} selected.", {
                jobId: result.job_id,
                count: new Intl.NumberFormat(window.lumsLocale).format(
                    result.package_count
                ),
            })
        );


        await loadJobs();


    } catch (error) {

        console.error(error);

        alert(
            t("Error creating update job:\n{error}", {
                error: error.message,
            })
        );


    } finally {

        if (installButton) {

            installButton.disabled = false;
            installButton.textContent =
                t("Install selected updates");
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
            t("Creating system update...");
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
                t("Could not create system update job.")
            );
        }


        alert(
            t("System update job #{jobId} created.", {
                jobId: result.job_id,
            })
        );


        await loadJobs();


    } catch (error) {

        console.error(error);

        alert(
            t("Error creating system update job:\n{error}", {
                error: error.message,
            })
        );


    } finally {

        if (button) {

            button.disabled = false;
            button.textContent =
                t("Update the entire system");
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
                t("Could not load update jobs.")
            );
        }


        updateJobs =
            await response.json();


        renderJobs();


    } catch (error) {

        console.error(error);

        container.innerHTML = `
            <div class="error-state">
                ${t("Could not load update jobs.")}
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
                ${t("Pending")}
            </span>
        `;
    }


    if (normalized === "running") {

        return `
            <span class="package-status update">
                ${t("Running")}
            </span>
        `;
    }


    if (normalized === "success") {

        return `
            <span class="package-status current">
                ✓ ${t("Successful")}
            </span>
        `;
    }


    if (normalized === "failed") {

        return `
            <span class="package-status update">
                ✗ ${t("Failed")}
            </span>
        `;
    }


    if (normalized === "partial") {

        return `
            <span class="package-status update">
                ⚠ ${t("Partially successful")}
            </span>
        `;
    }


    return `
        <span class="package-status">
            ${escapeHtml(status || t("Unknown"))}
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
                ${t("No update jobs available.")}
            </div>
        `;

        return;
    }


    container.innerHTML = `

        <div class="table-wrapper">

            <table class="data-table">

                <thead>

                    <tr>
                        <th>${t("Job")}</th>
                        <th>${t("Status")}</th>
                        <th>${t("Packages")}</th>
                        <th>${t("Created")}</th>
                        <th>${t("Completed")}</th>
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
                t("Could not load update history.")
            );
        }


        updateHistory =
            await response.json();


        renderHistory();


    } catch (error) {

        console.error(error);

        container.innerHTML = `
            <div class="error-state">
                ${t("Could not load update history.")}
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
                ${t("No update history yet.")}
            </div>
        `;

        return;
    }


    container.innerHTML = `

        <div class="table-wrapper">

            <table class="data-table">

                <thead>

                    <tr>
                        <th>${t("Status")}</th>
                        <th>${t("Packages")}</th>
                        <th>${t("Successful")}</th>
                        <th>${t("Failed")}</th>
                        <th>${t("Reboot required")}</th>
                        <th>${t("Start")}</th>
                        <th>${t("End")}</th>
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
                                        ? `⚠ ${t("Yes")}`
                                        : t("No")
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
                t("Could not load client.")
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


        const packageCount =
            document.getElementById("package-count");

        if (packageCount) {
            packageCount.textContent =
                client.package_count ?? "–";
        }

        const updateCount =
            document.getElementById("update-count");

        if (updateCount) {
            updateCount.textContent =
                client.update_count ?? "–";
        }


        const status =
            document.getElementById("status");


        status.textContent =
            ({
                online: t("Online"),
                offline: t("Offline"),
            })[String(client.status || "").toLowerCase()] ||
            t("Unknown");


        status.className =
            "status-badge " +
            String(
                client.status || ""
            ).toLowerCase();


    } catch (error) {

        console.error(error);

        document.getElementById("hostname").textContent =
            t("Error");
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
                t("Could not load updates.")
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
                ${t("Could not load updates.")}
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
                t("Could not load packages.")
            );
        }


        allPackages =
            await response.json();


        renderPackages();


    } catch (error) {

        console.error(error);

        const table = document.getElementById("packages-table");
        if (table) {
            table.innerHTML = `
                <tr>
                    <td colspan="3" class="empty-state">
                        ${t("Could not load packages.")}
                    </td>
                </tr>
            `;
        }
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
    ?.addEventListener(
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
        `${t('Are you sure you want to rotate the token for client "{hostname}"?', {
            hostname,
        })}\n\n` +
        `${t("The current token will be invalidated immediately.")}\n\n` +
        `${t("Reconfigure the LUMS agent with the new token.")}\n\n` +
        t("Continue?")
    );

    if (!confirmed) {
        return;
    }


    const button =
        document.getElementById(
            "rotate-client-token-button"
        );


    button.disabled = true;
    button.textContent = t("Rotating token...");


    try {

        const csrfToken =
            document.querySelector(
                'meta[name="csrf-token"]'
            )?.content;


        if (!csrfToken) {

            throw new Error(
                t("CSRF token could not be found.")
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
                t("Could not rotate client token.")
            );
        }


        const token =
            data.token;


        if (!token) {

            throw new Error(
                t("The server did not return a new token.")
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


        button.textContent = `🔐 ${t("Token rotated")}`;


    } catch (error) {

        console.error(error);


        alert(
            `${t("Could not rotate client token.")}\n\n` +
            error.message
        );


        button.textContent = `🔐 ${t("Rotate token")}`;


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
                    t("No client token is available to copy.")
                );

                return;
            }


            try {

                await navigator.clipboard.writeText(
                    token
                );


                copyRotatedClientTokenButton.textContent =
                    `✓ ${t("Token copied")}`;


                window.setTimeout(
                    () => {

                        copyRotatedClientTokenButton.textContent =
                            `📋 ${t("Copy token")}`;

                    },
                    2000
                );


            } catch (error) {

                console.error(error);


                alert(
                    t("Could not copy token to the clipboard.")
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
        `${t('Are you sure you want to remove client "{hostname}"?', {
            hostname,
        })}\n\n` +
        t("The client can be registered again.")
    );

    if (!confirmed) {
        return;
    }

    const button =
        document.getElementById("delete-client-button");

    button.disabled = true;
    button.textContent = t("Removing...");

    try {

        const csrfToken =
            document.querySelector('meta[name="csrf-token"]')?.content;

        if (!csrfToken) {
            throw new Error(t("CSRF token could not be found."));
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
                data.error || t("Could not remove client.")
            );
        }

        window.location.href = "/";

    } catch (error) {

        console.error(error);

        alert(
            `${t("Could not remove client.")}\n\n` +
            error.message
        );

        button.disabled = false;
        button.textContent = `🗑️ ${t("Remove client")}`;
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
        t("No client ID provided.");

} else {

    loadClient();

    if (userHasPermission("software.view")) {
        loadPackages();
    }

    if (userHasPermission("updates.view")) {
        loadUpdates();
        loadJobs();
        loadHistory();
    }
}


/*
 * Paketverwaltung
 *
 * Serverseitige Paketsuche auf dem ausgewählten Client.
 *
 * Ablauf:
 *
 * Browser
 *   -> POST package-search
 *   -> search_id
 *   -> GET package-search/<search_id>
 *   -> pending / running / completed / failed
 *   -> Ergebnisse darstellen
 *
 * Paketaktionen verwenden bewusst den normalen
 * Update-Job-Endpunkt:
 *
 *   INSTALL_PACKAGE
 *   REMOVE_PACKAGE
 *   UPDATE_PACKAGE
 *
 * Dadurch bleiben CSRF, RBAC, Validierung, Agent-Dispatch,
 * Job-Historie und Recovery zentral im bestehenden System.
 */

const packageManagementSearchInput =
    document.getElementById(
        "package-management-search"
    );

const packageManagementSearchButton =
    document.getElementById(
        "package-management-search-button"
    );

const packageManagementStatus =
    document.getElementById(
        "package-management-status"
    );

const packageManagementResults =
    document.getElementById(
        "package-management-results"
    );


/*
 * Status anzeigen
 */
function setPackageManagementStatus(message) {

    if (!packageManagementStatus) {
        return;
    }

    packageManagementStatus.textContent =
        message;
}


/*
 * Installationsstatus eines Pakets bestimmen.
 *
 * allPackages:
 *     bereits installierte Pakete des Clients
 *
 * updates:
 *     aktuell verfügbare Updates
 */
function getPackageManagementState(packageName) {

    const installedPackage =
        Array.isArray(allPackages)
            ? allPackages.find(packageInfo =>
                packageInfo?.package === packageName ||
                packageInfo?.name === packageName
            )
            : null;


    const availableUpdate =
        Array.isArray(updates)
            ? updates.find(update =>
                update?.package === packageName
            )
            : null;


    if (installedPackage) {

        if (availableUpdate) {

            return {
                type: "update",
                label: t("Update available")
            };
        }


        return {
            type: "installed",
            label: t("Installed")
        };
    }


    return {
        type: "available",
        label: t("Not installed")
    };
}


/*
 * Status-Badge erzeugen
 */
function createPackageManagementStatusBadge(
    state
) {

    const badge =
        document.createElement("span");

    badge.className =
        "package-management-status-badge " +
        `package-management-status-${state.type}`;

    badge.textContent =
        state.label;

    return badge;
}


/*
 * Paket-Job erstellen
 */
async function createPackageManagementJob(
    action,
    packageName,
    button
) {

    if (!packageName) {
        return;
    }


    if (action === "REMOVE_PACKAGE") {

        const confirmed =
            window.confirm(
                t('Are you sure you want to remove package "{packageName}"?', {
                    packageName,
                })
            );


        if (!confirmed) {
            return;
        }
    }


    const originalText =
        button?.textContent || t("Action");


    if (button) {

        button.disabled = true;

        if (action === "INSTALL_PACKAGE") {

            button.textContent =
                t("Installing...");

        } else if (action === "REMOVE_PACKAGE") {

            button.textContent =
                t("Removing...");

        } else if (action === "UPDATE_PACKAGE") {

            button.textContent =
                t("Updating...");
        }
    }


    try {

        const csrfToken =
            document.querySelector(
                'meta[name="csrf-token"]'
            )?.content;


        if (!csrfToken) {

            throw new Error(
                t("CSRF token could not be found.")
            );
        }


        const response =
            await fetch(
                `/api/clients/${clientId}/update-jobs`,
                {
                    method: "POST",

                    headers: {
                        "Content-Type":
                            "application/json",

                        "X-CSRF-Token":
                            csrfToken,

                        "Accept":
                            "application/json"
                    },

                    body: JSON.stringify({
                        action: action,
                        packages: [packageName]
                    })
                }
            );


        let data = null;

        try {
            data = await response.json();
        } catch {
            data = null;
        }


        if (!response.ok) {

            throw new Error(
                data?.error ||
                t("Could not create package job.")
            );
        }


        setPackageManagementStatus(
            t('Job #{jobId} created for "{packageName}".', {
                jobId: data.job_id,
                packageName,
            })
        );


        /*
         * Bestehende Job-Anzeige aktualisieren.
         */
        await loadJobs();


    } catch (error) {

        console.error(
            "Package management job failed:",
            error
        );


        setPackageManagementStatus(
            t("Error: {error}", { error: error.message })
        );


    } finally {

        if (button) {

            button.disabled = false;
            button.textContent =
                originalText;
        }
    }
}


/*
 * Aktionsbutton erzeugen
 */
function createPackageManagementActionButton(
    action,
    packageName,
    label,
    className
) {

    const button =
        document.createElement("button");

    button.type = "button";
    button.className = className;
    button.textContent = label;


    button.addEventListener(
        "click",
        () => createPackageManagementJob(
            action,
            packageName,
            button
        )
    );


    return button;
}


/*
 * Aktionen für ein Paket darstellen
 */
function renderPackageManagementActions(
    packageName,
    state
) {

    const container =
        document.createElement("div");

    container.className =
        "package-management-actions";

    if (!userHasPermission("jobs.manage")) {
        container.textContent = t("View only");
        return container;
    }


    if (state.type === "available") {

        container.appendChild(
            createPackageManagementActionButton(
                "INSTALL_PACKAGE",
                packageName,
                t("Install"),
                "button button-primary"
            )
        );

        return container;
    }


    if (state.type === "update") {

        container.appendChild(
            createPackageManagementActionButton(
                "UPDATE_PACKAGE",
                packageName,
                t("Update"),
                "button button-primary"
            )
        );
    }


    /*
     * Installierte Pakete können entfernt werden.
     */
    container.appendChild(
        createPackageManagementActionButton(
            "REMOVE_PACKAGE",
            packageName,
            t("Remove"),
            "button button-danger"
        )
    );


    return container;
}


/*
 * Ergebnisse darstellen
 */
function renderPackageManagementResults(results) {

    if (!packageManagementResults) {
        return;
    }


    packageManagementResults.innerHTML = "";


    if (
        !Array.isArray(results) ||
        results.length === 0
    ) {

        packageManagementResults.innerHTML = `
            <tr>
                <td
                    colspan="5"
                    class="empty-state"
                >
                    ${t("No matching packages found.")}
                </td>
            </tr>
        `;

        return;
    }


    results.forEach(packageInfo => {

        const packageName =
            packageInfo?.package || "–";

        const version =
            packageInfo?.version || "–";

        const description =
            packageInfo?.description || "–";


        const state =
            getPackageManagementState(
                packageName
            );


        const row =
            document.createElement("tr");


        const packageCell =
            document.createElement("td");

        const packageNameElement =
            document.createElement("strong");

        packageNameElement.textContent =
            packageName;

        packageCell.appendChild(
            packageNameElement
        );


        const versionCell =
            document.createElement("td");

        versionCell.className =
            "version";

        versionCell.textContent =
            version;


        const statusCell =
            document.createElement("td");

        statusCell.appendChild(
            createPackageManagementStatusBadge(
                state
            )
        );


        const descriptionCell =
            document.createElement("td");

        descriptionCell.textContent =
            description;


        const actionCell =
            document.createElement("td");

        actionCell.appendChild(
            renderPackageManagementActions(
                packageName,
                state
            )
        );


        row.appendChild(packageCell);
        row.appendChild(versionCell);
        row.appendChild(statusCell);
        row.appendChild(descriptionCell);
        row.appendChild(actionCell);


        packageManagementResults.appendChild(
            row
        );
    });
}


/*
 * Suchstatus abfragen
 */
async function getPackageManagementSearchStatus(
    searchId
) {

    const response =
        await fetch(
            `/api/clients/${clientId}/package-search/${searchId}`,
            {
                method: "GET",

                headers: {
                    "Accept":
                        "application/json"
                }
            }
        );


    let data = null;

    try {
        data = await response.json();
    } catch {
        data = null;
    }


    if (!response.ok) {

        throw new Error(
            data?.error ||
            t("Could not retrieve package search status.")
        );
    }


    return data;
}


/*
 * Auf Abschluss der Paketsuche warten
 */
async function waitForPackageManagementSearch(
    searchId
) {

    const maxAttempts = 1200;
    const pollInterval = 500;


    for (
        let attempt = 0;
        attempt < maxAttempts;
        attempt++
    ) {

        const data =
            await getPackageManagementSearchStatus(
                searchId
            );


        if (data.status === "completed") {

            const results =
                Array.isArray(data.results)
                    ? data.results
                    : [];


            renderPackageManagementResults(
                results
            );


            setPackageManagementStatus(
                t("{count} packages found.", {
                    count: new Intl.NumberFormat(window.lumsLocale).format(
                        results.length
                    ),
                })
            );


            return;
        }


        if (data.status === "failed") {

            throw new Error(
                data.error_message ||
                t("Package search failed.")
            );
        }


        if (
            data.status !== "pending" &&
            data.status !== "running"
        ) {

            throw new Error(
                t("Unknown search status: {status}", {
                    status: data.status,
                })
            );
        }


        setPackageManagementStatus(
            data.status === "pending"
                ? t("Search is waiting for the client...")
                : t("The client is searching for packages...")
        );


        await new Promise(resolve =>
            setTimeout(
                resolve,
                pollInterval
            )
        );
    }


    throw new Error(
        t("Package search timed out.")
    );
}


/*
 * Paketsuche starten
 */
async function startPackageManagementSearch() {

    if (
        !packageManagementSearchInput ||
        !packageManagementSearchButton
    ) {
        return;
    }


    const query =
        packageManagementSearchInput.value.trim();


    if (!query) {

        setPackageManagementStatus(
            t("Enter a package name or search term.")
        );

        packageManagementSearchInput.focus();

        return;
    }


    packageManagementSearchButton.disabled =
        true;

    packageManagementSearchButton.textContent =
        t("Searching...");


    setPackageManagementStatus(
        t("Starting package search...")
    );


    try {

        const csrfToken =
            document.querySelector(
                'meta[name="csrf-token"]'
            )?.content;


        if (!csrfToken) {

            throw new Error(
                t("CSRF token could not be found.")
            );
        }


        const response =
            await fetch(
                `/api/clients/${clientId}/package-search`,
                {
                    method: "POST",

                    headers: {
                        "Content-Type":
                            "application/json",

                        "X-CSRF-Token":
                            csrfToken,

                        "Accept":
                            "application/json"
                    },

                    body: JSON.stringify({
                        query: query
                    })
                }
            );


        let data = null;

        try {
            data = await response.json();
        } catch {
            data = null;
        }


        if (!response.ok) {

            throw new Error(
                data?.error ||
                t("Could not start package search.")
            );
        }


        if (!data?.search_id) {

            throw new Error(
                t("The server did not return a search ID.")
            );
        }


        setPackageManagementStatus(
            t("Package search started...")
        );


        await waitForPackageManagementSearch(
            data.search_id
        );


    } catch (error) {

        console.error(
            "Package management search failed:",
            error
        );


        setPackageManagementStatus(
            t("Error: {error}", { error: error.message })
        );


    } finally {

        packageManagementSearchButton.disabled =
            false;

        packageManagementSearchButton.textContent =
            t("Search");
    }
}


/*
 * Suchbutton
 */
if (packageManagementSearchButton) {

    packageManagementSearchButton.addEventListener(
        "click",
        startPackageManagementSearch
    );
}


/*
 * Enter im Suchfeld
 */
if (packageManagementSearchInput) {

    packageManagementSearchInput.addEventListener(
        "keydown",
        event => {

            if (event.key === "Enter") {

                event.preventDefault();

                startPackageManagementSearch();
            }
        }
    );
}
