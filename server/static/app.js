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


    if ((window.lumsUserPermissions || []).includes("updates.view")) {
        loadUpdateCount(clients);
    }

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



function showCreateUserError(message) {

    const error =
        document.getElementById("create-user-error");

    error.textContent = message;
    error.hidden = false;
}



// Liest eine API-Antwort, ohne ungültiges JSON nach außen zu werfen.
async function readDeleteResponse(response) {
    let body = "";

    try {
        body = await response.text();
    } catch (error) {
        return {
            result: null,
            readError: true,
            invalidJson: false
        };
    }

    if (!body.trim()) {
        return {
            result: null,
            readError: false,
            invalidJson: false
        };
    }

    try {
        return {
            result: JSON.parse(body),
            readError: false,
            invalidJson: false
        };
    } catch (error) {
        return {
            result: null,
            readError: false,
            invalidJson: true
        };
    }
}

function renderPermissionOptions(container, selectedPermissions) {
    container.replaceChildren();

    for (const permission of window.lumsPermissionDefinitions || []) {
        const label = document.createElement("label");
        label.className = "permission-option";

        const checkbox = document.createElement("input");
        checkbox.type = "checkbox";
        checkbox.value = permission.key;
        checkbox.checked = selectedPermissions.includes(permission.key);
        checkbox.addEventListener("change", () => {
            syncPermissionDependencies(container, checkbox);
        });

        const text = document.createElement("span");
        text.textContent = permission.label;

        label.append(checkbox, text);
        container.appendChild(label);
    }
}


function syncPermissionDependencies(container, changedCheckbox) {
    const checkboxes = new Map(
        Array.from(
            container.querySelectorAll('input[type="checkbox"]')
        ).map(checkbox => [checkbox.value, checkbox])
    );

    const clientView = checkboxes.get("clients.view");
    const updatesView = checkboxes.get("updates.view");
    const jobsManage = checkboxes.get("jobs.manage");

    if (changedCheckbox.checked) {
        if (changedCheckbox.value !== "users.manage" && clientView) {
            clientView.checked = true;
        }

        if (changedCheckbox.value === "jobs.manage" && updatesView) {
            updatesView.checked = true;
        }

        return;
    }

    if (changedCheckbox.value === "clients.view") {
        for (const checkbox of checkboxes.values()) {
            if (checkbox.value !== "users.manage") {
                checkbox.checked = false;
            }
        }
    } else if (
        changedCheckbox.value === "updates.view" &&
        jobsManage
    ) {
        jobsManage.checked = false;
    }
}


function selectedPermissions(container) {
    return Array.from(
        container.querySelectorAll('input[type="checkbox"]:checked')
    ).map(checkbox => checkbox.value);
}


function applyRolePermissionPreset(role, container) {
    const permissions =
        window.lumsRoleDefaultPermissions?.[role] || [];
    renderPermissionOptions(container, permissions);
}

function roleTemplateDescription(role) {
    return window.lumsRoleDescriptions?.[role] ||
        "Keine Beschreibung für diese Vorlage verfügbar.";
}


function createPermissionEditorRow(user) {
    const row = document.createElement("tr");
    row.className = "permission-editor-row";

    const cell = document.createElement("td");
    cell.colSpan = 5;

    const editor = document.createElement("div");
    editor.className = "permission-editor";

    const heading = document.createElement("h3");
    heading.textContent = `Berechtigungen für ${user.username}`;
    editor.appendChild(heading);

    const roleLabel = document.createElement("label");
    roleLabel.textContent = "Rollen-Vorlage ";

    const roleSelect = document.createElement("select");
    roleSelect.setAttribute("aria-label", "Rollen-Vorlage");
    for (const [value, labelText] of [
        ["viewer", "Viewer"],
        ["operator", "Operator"],
        ["administrator", "Administrator"],
    ]) {
        const option = document.createElement("option");
        option.value = value;
        option.textContent = labelText;
        option.selected = user.role === value;
        roleSelect.appendChild(option);
    }
    roleLabel.appendChild(roleSelect);
    editor.appendChild(roleLabel);

    const roleDescription = document.createElement("p");
    roleDescription.className = "role-template-description";
    roleDescription.setAttribute("aria-live", "polite");
    roleDescription.textContent =
        roleTemplateDescription(roleSelect.value);
    editor.appendChild(roleDescription);

    const roleTemplateList = document.createElement("ul");
    roleTemplateList.className = "role-template-list";
    for (const [role, description] of Object.entries(
        window.lumsRoleDescriptions || {}
    )) {
        const item = document.createElement("li");
        const label = document.createElement("strong");
        label.textContent = {
            administrator: "Administrator",
            operator: "Operator",
            viewer: "Viewer",
        }[role] || role;
        const detail = document.createElement("span");
        detail.textContent = description;
        item.append(label, detail);
        roleTemplateList.appendChild(item);
    }
    editor.appendChild(roleTemplateList);

    const fieldset = document.createElement("fieldset");
    fieldset.className = "permission-picker";
    const legend = document.createElement("legend");
    legend.textContent = "Berechtigungen";
    fieldset.appendChild(legend);

    const options = document.createElement("div");
    options.className = "permission-options";
    renderPermissionOptions(options, user.permissions || []);
    fieldset.appendChild(options);
    editor.appendChild(fieldset);

    roleSelect.addEventListener("change", () => {
        roleDescription.textContent =
            roleTemplateDescription(roleSelect.value);
    });

    const applyTemplateButton = document.createElement("button");
    applyTemplateButton.type = "button";
    applyTemplateButton.className = "button";
    applyTemplateButton.textContent = "Vorlage übernehmen";
    applyTemplateButton.addEventListener("click", () => {
        applyRolePermissionPreset(roleSelect.value, options);
    });
    editor.appendChild(applyTemplateButton);

    const error = document.createElement("p");
    error.className = "permission-editor-error";
    error.hidden = true;
    editor.appendChild(error);

    const actions = document.createElement("div");
    actions.className = "permission-editor-actions";

    const saveButton = document.createElement("button");
    saveButton.type = "button";
    saveButton.className = "button-primary";
    saveButton.textContent = "Berechtigungen speichern";

    const cancelButton = document.createElement("button");
    cancelButton.type = "button";
    cancelButton.className = "button";
    cancelButton.textContent = "Abbrechen";
    cancelButton.addEventListener("click", () => row.remove());

    const noteSection = document.createElement("section");
    noteSection.className = "admin-note-section";

    const noteLabel = document.createElement("label");
    noteLabel.textContent = "Interne Admin-Notiz";
    noteLabel.htmlFor = `admin-note-${user.id}`;
    noteSection.appendChild(noteLabel);

    const noteHelp = document.createElement("p");
    noteHelp.className = "panel-description";
    noteHelp.textContent =
        "Nur für Benutzer mit users.manage sichtbar; der Benutzer selbst sieht diese Notiz nicht.";
    noteSection.appendChild(noteHelp);

    const noteInput = document.createElement("textarea");
    noteInput.id = `admin-note-${user.id}`;
    noteInput.maxLength = 2000;
    noteInput.rows = 4;
    noteInput.value = user.admin_note || "";
    noteInput.setAttribute(
        "aria-label",
        `Interne Admin-Notiz für ${user.username}`
    );
    noteSection.appendChild(noteInput);

    const noteStatus = document.createElement("p");
    noteStatus.className = "admin-note-status";
    noteStatus.setAttribute("aria-live", "polite");
    noteSection.appendChild(noteStatus);

    const saveNoteButton = document.createElement("button");
    saveNoteButton.type = "button";
    saveNoteButton.className = "button";
    saveNoteButton.textContent = "Notiz speichern";
    saveNoteButton.addEventListener("click", async () => {
        const csrfToken = document.querySelector(
            'meta[name="csrf-token"]'
        )?.content;

        if (!csrfToken) {
            noteStatus.textContent =
                "CSRF-Token konnte nicht gefunden werden.";
            noteStatus.dataset.state = "error";
            return;
        }

        saveNoteButton.disabled = true;
        saveNoteButton.textContent = "Wird gespeichert …";
        noteStatus.textContent = "";

        try {
            const response = await fetch(
                `/api/users/${encodeURIComponent(user.id)}/note`,
                {
                    method: "PUT",
                    headers: {
                        "Content-Type": "application/json",
                        "X-CSRF-Token": csrfToken,
                    },
                    body: JSON.stringify({
                        note: noteInput.value,
                    }),
                }
            );
            const result = await response.json();

            if (!response.ok) {
                const messages = {
                    invalid_admin_note:
                        "Die Notiz darf höchstens 2.000 Zeichen enthalten.",
                    user_not_found:
                        "Der Benutzer wurde nicht gefunden.",
                    csrf_validation_failed:
                        "CSRF-Prüfung fehlgeschlagen.",
                    authorization_required:
                        "Dafür fehlen die Berechtigungen.",
                };
                throw new Error(
                    messages[result.error] ||
                    `Notiz konnte nicht gespeichert werden (HTTP ${response.status}).`
                );
            }

            user.admin_note = result.note;
            noteInput.value = result.note;
            noteStatus.textContent = "Interne Notiz gespeichert.";
            noteStatus.dataset.state = "success";
        } catch (saveError) {
            console.error(saveError);
            noteStatus.textContent = saveError.message;
            noteStatus.dataset.state = "error";
        } finally {
            saveNoteButton.disabled = false;
            saveNoteButton.textContent = "Notiz speichern";
        }
    });
    noteSection.appendChild(saveNoteButton);
    editor.appendChild(noteSection);

    saveButton.addEventListener("click", async () => {
        const csrfToken = document.querySelector(
            'meta[name="csrf-token"]'
        )?.content;

        if (!csrfToken) {
            error.textContent = "CSRF-Token konnte nicht gefunden werden.";
            error.hidden = false;
            return;
        }

        saveButton.disabled = true;
        saveButton.textContent = "Wird gespeichert …";
        error.hidden = true;

        try {
            const response = await fetch(
                `/api/users/${encodeURIComponent(user.id)}/permissions`,
                {
                    method: "PUT",
                    headers: {
                        "Content-Type": "application/json",
                        "X-CSRF-Token": csrfToken,
                    },
                    body: JSON.stringify({
                        role: roleSelect.value,
                        permissions: selectedPermissions(options),
                    }),
                }
            );
            const result = await response.json();

            if (!response.ok) {
                const messages = {
                    invalid_user_role:
                        "Die ausgewählte Rollen-Vorlage ist ungültig.",
                    invalid_user_permissions:
                        "Die Auswahl enthält ungültige Rechte oder erforderliche Basisrechte fehlen.",
                    last_enabled_administrator:
                        "Mindestens ein aktiver Benutzer muss Benutzer verwalten dürfen.",
                    user_not_found:
                        "Der Benutzer wurde nicht gefunden.",
                    csrf_validation_failed:
                        "CSRF-Prüfung fehlgeschlagen.",
                    authorization_required:
                        "Dafür fehlen die Berechtigungen.",
                };

                throw new Error(
                    messages[result.error] ||
                    `Berechtigungen konnten nicht gespeichert werden (HTTP ${response.status}).`
                );
            }

            await loadUsers();
            const status = document.getElementById("users-list-status");
            status.textContent =
                `Berechtigungen für "${user.username}" wurden gespeichert.`;
        } catch (saveError) {
            console.error(saveError);
            error.textContent = saveError.message;
            error.hidden = false;
            saveButton.disabled = false;
            saveButton.textContent = "Berechtigungen speichern";
        }
    });

    actions.append(saveButton, cancelButton);
    editor.appendChild(actions);
    cell.appendChild(editor);
    row.appendChild(cell);

    return row;
}


async function loadUsers(focusUserId = null) {

    const status =
        document.getElementById("users-list-status");

    const container =
        document.getElementById("users-list-container");

    const body =
        document.getElementById("users-list-body");

    if (!status || !container || !body) {

        return;

    }

    status.textContent =
        "Benutzer werden geladen …";

    container.hidden = true;

    try {

        const response =
            await fetch("/api/users");

        const data =
            await response.json();

        if (!response.ok) {

            throw new Error(
                data.error ||
                "Benutzer konnten nicht geladen werden."
            );

        }

        body.innerHTML = "";

        if (!Array.isArray(data) || data.length === 0) {

            status.textContent =
                "Keine Benutzer vorhanden.";

            return;

        }

        for (const user of data) {

            const row =
                document.createElement("tr");

            const usernameCell =
                document.createElement("td");

            usernameCell.textContent =
                user.username;

            const roleCell =
                document.createElement("td");

            const roleBadge =
                document.createElement("span");
            roleBadge.className =
                `user-role-badge user-role-badge--${user.role}`;
            roleBadge.textContent = {
                administrator: "Administrator",
                operator: "Operator",
                viewer: "Viewer",
            }[user.role] || user.role;
            roleCell.appendChild(roleBadge);

            const defaultPermissions =
                window.lumsRoleDefaultPermissions?.[user.role] || [];
            const actualPermissions =
                [...(user.permissions || [])].sort();
            const isCustomized =
                JSON.stringify(actualPermissions) !==
                JSON.stringify([...defaultPermissions].sort());

            if (isCustomized) {
                const customizedBadge =
                    document.createElement("span");
                customizedBadge.className =
                    "user-role-customized";
                customizedBadge.textContent = "Angepasst";
                roleCell.appendChild(customizedBadge);
            }

            const permissionsCell =
                document.createElement("td");
            const permissionList =
                document.createElement("div");
            permissionList.className =
                "permission-chip-list";

            const permissionLabels = new Map(
                (window.lumsPermissionDefinitions || [])
                    .map(permission => [
                        permission.key,
                        permission.label,
                    ])
            );
            const knownPermissions = actualPermissions
                .map(permission => permissionLabels.get(permission))
                .filter(Boolean);

            if (knownPermissions.length) {
                for (const label of knownPermissions) {
                    const chip =
                        document.createElement("span");
                    chip.className = "permission-chip";
                    chip.textContent = label;
                    permissionList.appendChild(chip);
                }
            } else {
                const emptyPermissions =
                    document.createElement("span");
                emptyPermissions.className =
                    "permission-empty";
                emptyPermissions.textContent = "Keine";
                permissionList.appendChild(emptyPermissions);
            }
            permissionsCell.appendChild(permissionList);

            const statusCell =
                document.createElement("td");

            const statusBadge =
                document.createElement("span");
            statusBadge.className = user.enabled
                ? "user-status-badge user-status-badge--active"
                : "user-status-badge user-status-badge--disabled";
            statusBadge.textContent = user.enabled
                ? "Aktiv"
                : "Deaktiviert";
            statusCell.appendChild(statusBadge);

            const actionCell =
                document.createElement("td");

            const editButton =
                document.createElement("button");

            editButton.type = "button";
            editButton.className = "button";
            editButton.textContent = "Rechte";
            editButton.setAttribute(
                "aria-label",
                `Berechtigungen für ${user.username} bearbeiten`
            );
            editButton.addEventListener("click", () => {
                const nextRow = row.nextElementSibling;
                if (nextRow?.classList.contains("permission-editor-row")) {
                    nextRow.remove();
                    editButton.setAttribute("aria-expanded", "false");
                    return;
                }

                body.querySelectorAll(".permission-editor-row")
                    .forEach(editorRow => editorRow.remove());
                body.querySelectorAll('[aria-expanded="true"]')
                    .forEach(button => button.setAttribute("aria-expanded", "false"));
                row.after(createPermissionEditorRow(user));
                editButton.setAttribute("aria-expanded", "true");
            });
            editButton.setAttribute("aria-expanded", "false");

            const deleteButton =
                document.createElement("button");

            deleteButton.type = "button";
            deleteButton.className = "button-danger";
            deleteButton.textContent = "Löschen";
            deleteButton.setAttribute(
                "aria-label",
                `Benutzer ${user.username} löschen`
            );

            deleteButton.addEventListener("click", async () => {
                if (!window.confirm(
                    `Soll der Benutzer "${user.username}" wirklich gelöscht werden?`
                )) {
                    return;
                }

                const csrfToken = document.querySelector(
                    'meta[name="csrf-token"]'
                )?.content;

                if (!csrfToken) {
                    status.textContent =
                        "CSRF-Token konnte nicht gefunden werden.";
                    return;
                }

                deleteButton.disabled = true;
                deleteButton.textContent = "Wird gelöscht …";

                try {
                    const deleteResponse = await fetch(
                        `/api/users/${encodeURIComponent(user.id)}`,
                        {
                            method: "DELETE",
                            headers: {
                                "X-CSRF-Token": csrfToken
                            }
                        }
                    );

                    const {
                        result,
                        readError,
                        invalidJson
                    } = await readDeleteResponse(deleteResponse);

                    if (readError) {
                        console.warn(
                            "Serverantwort konnte nicht gelesen werden."
                        );
                    }

                    if (invalidJson) {
                        console.warn(
                            "Serverantwort war kein gültiges JSON."
                        );
                    }

                    if (!deleteResponse.ok) {
                        const messages = {
                            cannot_delete_self:
                                "Das eigene Benutzerkonto kann nicht gelöscht werden.",
                            last_enabled_administrator:
                                "Der letzte aktive Administrator kann nicht gelöscht werden.",
                            user_not_found:
                                "Der Benutzer wurde nicht gefunden.",
                            csrf_validation_failed:
                                "CSRF-Prüfung fehlgeschlagen.",
                            authorization_required:
                                "Dafür fehlen die Berechtigungen."
                        };

                        if (result?.error && messages[result.error]) {
                            throw new Error(messages[result.error]);
                        }

                        if (
                            deleteResponse.status === 401 ||
                            deleteResponse.status === 403
                        ) {
                            throw new Error(
                                "Die Löschanfrage wurde nicht autorisiert."
                            );
                        }

                        throw new Error(
                            `Benutzer konnte nicht gelöscht werden ` +
                            `(HTTP ${deleteResponse.status}). ` +
                            "Bitte die Benutzerliste aktualisieren und den Status prüfen."
                        );
                    }

                    if (!result || result.status !== "deleted") {
                        await loadUsers();

                        status.textContent =
                            "Keine gültige Löschbestätigung vom Server. " +
                            "Bitte prüfen, ob der Benutzer noch in der Liste steht.";

                        return;
                    }

                    await loadUsers();
                    status.textContent =
                        `Benutzer "${user.username}" wurde gelöscht.`;

                } catch (error) {
                    console.error(error);
                    status.textContent = error.message;
                    deleteButton.disabled = false;
                    deleteButton.textContent = "Löschen";
                }
            });

            actionCell.append(editButton, deleteButton);
            row.appendChild(usernameCell);
            row.appendChild(roleCell);
            row.appendChild(permissionsCell);
            row.appendChild(statusCell);
            row.appendChild(actionCell);

            body.appendChild(row);

            if (
                focusUserId !== null &&
                String(user.id) === String(focusUserId)
            ) {
                const editorRow =
                    createPermissionEditorRow(user);
                row.after(editorRow);
                editButton.setAttribute("aria-expanded", "true");
                editorRow
                    .querySelector('input[type="checkbox"]')
                    ?.focus();
                row.scrollIntoView({
                    behavior: window.matchMedia(
                        "(prefers-reduced-motion: reduce)"
                    ).matches
                        ? "auto"
                        : "smooth",
                    block: "center",
                });
            }

        }

        status.textContent = focusUserId === null
            ? `${data.length} Benutzer`
            : `${data.length} Benutzer · Vorlage prüfen und Rechte für den neuen Benutzer manuell zuweisen.`;

        container.hidden = false;

    } catch (error) {

        console.error(error);

        status.textContent =
            "Benutzer konnten nicht geladen werden.";

    }

}



async function createUser(event) {

    event.preventDefault();

    const username =
        document
            .getElementById("create-user-username")
            .value
            .trim();

    const password =
        document
            .getElementById("create-user-password")
            .value;

    const role =
        document
            .getElementById("create-user-role")
            .value;

    const error =
        document.getElementById("create-user-error");

    error.hidden = true;
    error.textContent = "";

    const csrfToken =
        document.querySelector(
            'meta[name="csrf-token"]'
        )?.content;

    if (!csrfToken) {

        showCreateUserError(
            "CSRF-Token konnte nicht gefunden werden."
        );

        return;

    }

    const submitButton =
        document.getElementById(
            "create-user-button"
        );

    submitButton.disabled = true;
    submitButton.textContent = "Wird angelegt...";

    try {

        const response =
            await fetch(
                "/api/users",
                {
                    method: "POST",

                    headers: {
                        "Content-Type": "application/json",
                        "X-CSRF-Token": csrfToken
                    },

                    body: JSON.stringify({
                        username: username,
                        password: password,
                        role: role,
                        permissions: [],
                    })
                }
            );

        const data =
            await response.json();

        if (!response.ok) {

            const messages = {
                username_required:
                    "Bitte einen Benutzernamen eingeben.",

                username_too_long:
                    "Der Benutzername darf höchstens 64 Zeichen lang sein.",

                password_required:
                    "Bitte ein Passwort eingeben.",

                password_too_short:
                    "Das Passwort muss mindestens 12 Zeichen lang sein.",

                invalid_user_role:
                    "Die ausgewählte Benutzerrolle ist ungültig.",

                invalid_user_permissions:
                    "Die Auswahl enthält ungültige Rechte oder erforderliche Basisrechte fehlen.",

                user_already_exists:
                    "Dieser Benutzername existiert bereits.",

                csrf_validation_failed:
                    "CSRF-Prüfung fehlgeschlagen."
            };

            throw new Error(
                messages[data.error] ||
                "Benutzer konnte nicht angelegt werden."
            );

        }

        document
            .getElementById("create-user-form")
            .reset();

        error.hidden = true;
        error.textContent = "";

        await loadUsers(data.user.id);

    } catch (error) {

        console.error(error);

        showCreateUserError(
            error.message
        );

    } finally {

        submitButton.disabled = false;
        submitButton.textContent = "Benutzer anlegen";

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


const createUserForm =
    document.getElementById("create-user-form");


if (createUserForm) {
    const createUserRole =
        document.getElementById("create-user-role");
    const createUserRoleDescription =
        document.getElementById("create-user-role-description");

    const updateCreateUserRoleDescription = () => {
        createUserRoleDescription.textContent =
            roleTemplateDescription(createUserRole.value);
    };

    updateCreateUserRoleDescription();
    createUserRole.addEventListener(
        "change",
        updateCreateUserRoleDescription
    );

    createUserForm.addEventListener(
        "submit",
        createUser
    );

    loadUsers();

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


const clientsTable =
    document.getElementById("clients-table");


if (clientsTable) {

    loadClients();

    setInterval(
        loadClients,
        30000
    );

}
