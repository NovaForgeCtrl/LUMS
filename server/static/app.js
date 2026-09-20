async function loadClients() {

    try {

        const response = await fetch("/api/clients");

        if (!response.ok) {

            throw new Error("API-Fehler");

        }

        const clients = await response.json();

        updateDashboard(clients);

        renderClients(clients);

    } catch (error) {

        console.error(error);

        document.getElementById(
            "clients-table"
        ).innerHTML = `

            <tr>

                <td colspan="6"
                    class="loading">

                    Fehler beim Laden der Clients

                </td>

            </tr>

        `;

    }

}



function updateDashboard(clients) {

    const clientCount = clients.length;


    const onlineCount = clients.filter(
        client => client.status === "online"
    ).length;


    document.getElementById(
        "client-count"
    ).textContent = clientCount;


    document.getElementById(
        "online-count"
    ).textContent = onlineCount;


    loadUpdateCount(clients);

}



function formatIdleStatus(client) {

    if (!client.idle) {

        return `
            <span class="idle-status idle-active">
                ● Aktiv
            </span>
        `;

    }


    const idleSeconds =
        Math.max(
            0,
            Number(client.idle_seconds) || 0
        );


    const thresholdSeconds =
        Math.max(
            1,
            Number(client.idle_threshold_seconds) || 300
        );


    return `
        <span class="idle-status idle-ready">
            ◷ Idle
            ${formatDuration(idleSeconds)}
            / ${formatDuration(thresholdSeconds)}
        </span>
    `;

}



function formatDuration(seconds) {

    const totalSeconds =
        Math.max(
            0,
            Math.floor(Number(seconds) || 0)
        );


    const minutes =
        Math.floor(totalSeconds / 60);


    const remainingSeconds =
        totalSeconds % 60;


    return `${String(minutes).padStart(2, "0")}:${String(
        remainingSeconds
    ).padStart(2, "0")}`;

}



async function loadUpdateCount(clients) {

    let totalUpdates = 0;


    for (const client of clients) {

        try {

            const response = await fetch(
                `/api/clients/${client.id}/updates`
            );


            if (!response.ok) {

                continue;

            }


            const updates = await response.json();

            totalUpdates += updates.length;

        } catch (error) {

            console.error(
                `Fehler bei Client ${client.id}:`,
                error
            );

        }

    }


    document.getElementById(
        "update-count"
    ).textContent = totalUpdates;

}



function renderClients(clients) {

    const table =
        document.getElementById("clients-table");


    table.innerHTML = "";


    if (clients.length === 0) {

        table.innerHTML = `

            <tr>

                <td colspan="6"
                    class="loading">

                    Keine Clients registriert

                </td>

            </tr>

        `;

        return;

    }



    for (const client of clients) {

        const row =
            document.createElement("tr");


        let statusClass =
            "status-offline";


        if (client.status === "online") {

            statusClass =
                "status-online";

        }


        if (client.status === "unknown") {

            statusClass =
                "status-unknown";

        }



        row.innerHTML = `

            <td>

                <a
                    class="client-link"
                    href="/client?id=${client.id}"
                >

                    <strong>
                        ${escapeHtml(client.hostname)}
                    </strong>

                </a>

            </td>


            <td>

                ${escapeHtml(client.ip ?? "-")}

            </td>


            <td>

                <span class="status ${statusClass}">

                    <span class="status-indicator"></span>

                    ${escapeHtml(client.status)}

                </span>

                <div class="idle-state">

                    ${formatIdleStatus(client)}

                </div>

            </td>


            <td id="updates-${client.id}">

                Lade...

            </td>


            <td>

                ${escapeHtml(
                    client.agent_version ?? "-"
                )}

            </td>


            <td>

                ${formatDate(client.last_seen)}

            </td>

        `;


        table.appendChild(row);


        loadClientUpdates(client.id);

    }

}



async function loadClientUpdates(clientId) {

    try {

        const response = await fetch(
            `/api/clients/${clientId}/updates`
        );


        if (!response.ok) {

            throw new Error("API-Fehler");

        }


        const updates = await response.json();


        const element =
            document.getElementById(
                `updates-${clientId}`
            );


        if (!element) {

            return;

        }



        if (updates.length === 0) {

            element.innerHTML =
                `<span class="updates-none">
                    Keine
                </span>`;

        } else {

            element.innerHTML =
                `<span class="updates-warning">
                    ${updates.length}
                </span>`;

        }

    } catch (error) {

        console.error(error);

    }

}



function formatDate(dateString) {

    const date =
        new Date(dateString);


    return date.toLocaleString(
        "de-DE"
    );

}



function escapeHtml(value) {

    const div =
        document.createElement("div");


    div.textContent =
        value;


    return div.innerHTML;

}



/* =========================================================
   LUMS Client Management
   ========================================================= */

function openAddClientDialog() {

    const dialog =
        document.getElementById("add-client-dialog");

    const form =
        document.getElementById("add-client-form");

    const error =
        document.getElementById("add-client-error");

    const tokenResult =
        document.getElementById("client-token-result");


    dialog.hidden = false;

    form.hidden = false;
    tokenResult.hidden = true;

    error.hidden = true;
    error.textContent = "";

    document
        .getElementById("client-ip")
        .focus();
}



function closeAddClientDialog() {

    const dialog =
        document.getElementById("add-client-dialog");

    const form =
        document.getElementById("add-client-form");

    const error =
        document.getElementById("add-client-error");

    const tokenResult =
        document.getElementById("client-token-result");

    const token =
        document.getElementById("client-token");

    dialog.hidden = true;

    form.hidden = false;

    tokenResult.hidden = true;

    error.hidden = true;
    error.textContent = "";

    token.textContent = "";

    form.reset();
}



function showAddClientError(message) {

    const error =
        document.getElementById("add-client-error");

    error.textContent = message;
    error.hidden = false;
}



async function createClient(event) {

    event.preventDefault();

    const ip =
        document
            .getElementById("client-ip")
            .value
            .trim();

    if (!ip) {

        showAddClientError(
            "Bitte eine IP-Adresse eingeben."
        );

        return;

    }

    const csrfToken =
        document.querySelector(
            'meta[name="csrf-token"]'
        )?.content;

    if (!csrfToken) {

        showAddClientError(
            "CSRF-Token konnte nicht gefunden werden."
        );

        return;

    }

    const submitButton =
        document.querySelector(
            "#add-client-form button[type='submit']"
        );

    submitButton.disabled = true;
    submitButton.textContent = "Wird angelegt...";

    try {

        const response =
            await fetch(
                "/api/clients",
                {
                    method: "POST",

                    headers: {
                        "Content-Type": "application/json",
                        "X-CSRF-Token": csrfToken
                    },

                    body: JSON.stringify({
                        ip: ip
                    })
                }
            );

        const data =
            await response.json();

        if (!response.ok) {

            if (
                response.status === 409 ||
                data.error === "client_already_exists"
            ) {

                throw new Error(
                    "Ein Client mit diesen Daten existiert bereits."
                );

            }

            throw new Error(
                data.error ||
                "Client konnte nicht angelegt werden."
            );

        }

        document.getElementById(
            "client-token"
        ).textContent = data.token;

        document.getElementById(
            "add-client-form"
        ).hidden = true;

        document.getElementById(
            "client-token-result"
        ).hidden = false;

        document.getElementById(
            "add-client-error"
        ).hidden = true;

    } catch (error) {

        console.error(error);

        showAddClientError(
            error.message
        );

    } finally {

        submitButton.disabled = false;
        submitButton.textContent = "Client anlegen";

    }
}



async function copyClientToken() {

    const token =
        document
            .getElementById("client-token")
            .textContent
            .trim();


    if (!token) {

        return;

    }


    try {

        await navigator.clipboard.writeText(token);

        alert(
            "Client-Token wurde in die Zwischenablage kopiert."
        );

    } catch (error) {

        console.error(error);

        alert(
            "Token konnte nicht automatisch kopiert werden."
        );

    }

}



const addClientForm =
    document.getElementById("add-client-form");


if (addClientForm) {

    addClientForm.addEventListener(
        "submit",
        createClient
    );

}


const addClientButton =
    document.getElementById("add-client-button");

if (addClientButton) {

    addClientButton.addEventListener(
        "click",
        openAddClientDialog
    );

}


const refreshClientsButton =
    document.getElementById("refresh-clients-button");

if (refreshClientsButton) {

    refreshClientsButton.addEventListener(
        "click",
        loadClients
    );

}


const closeAddClientButton =
    document.getElementById("close-add-client-button");

if (closeAddClientButton) {

    closeAddClientButton.addEventListener(
        "click",
        closeAddClientDialog
    );

}


const cancelAddClientButton =
    document.getElementById("cancel-add-client-button");

if (cancelAddClientButton) {

    cancelAddClientButton.addEventListener(
        "click",
        closeAddClientDialog
    );

}


const copyTokenButton =
    document.getElementById("copy-client-token-button");

if (copyTokenButton) {

    copyTokenButton.addEventListener(
        "click",
        copyClientToken
    );

}


const finishAddClientButton =
    document.getElementById("finish-add-client-button");

if (finishAddClientButton) {

    finishAddClientButton.addEventListener(
        "click",
        () => {
            closeAddClientDialog();
            loadClients();
        }
    );

}


loadClients();


setInterval(
    loadClients,
    30000
);
