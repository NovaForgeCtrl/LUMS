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



loadClients();


setInterval(
    loadClients,
    30000
);
