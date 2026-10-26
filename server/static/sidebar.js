(() => {
    "use strict";

    const body = document.body;
    const toggle = document.getElementById("lums-sidebar-toggle");
    const sidebar = document.getElementById("lums-sidebar");
    const scrim = document.getElementById("lums-sidebar-scrim");
    const storageKey = "lums-sidebar-collapsed";
    const mobile = () => window.matchMedia("(max-width: 760px)").matches;

    if (!toggle || !sidebar || !scrim) return;

    try {
        if (localStorage.getItem(storageKey) === "true" && !mobile()) {
            body.classList.add("lums-sidebar-collapsed");
        }
    } catch (_) {
        // Navigation still works if local storage is unavailable.
    }

    function syncState() {
        const expanded = mobile()
            ? body.classList.contains("lums-sidebar-drawer-open")
            : !body.classList.contains("lums-sidebar-collapsed");

        toggle.setAttribute("aria-expanded", String(expanded));
        scrim.hidden = !mobile() || !body.classList.contains("lums-sidebar-drawer-open");
    }

    toggle.addEventListener("click", () => {
        if (mobile()) {
            body.classList.toggle("lums-sidebar-drawer-open");
        } else {
            body.classList.toggle("lums-sidebar-collapsed");
            try {
                localStorage.setItem(
                    storageKey,
                    String(body.classList.contains("lums-sidebar-collapsed"))
                );
            } catch (_) {}
        }
        syncState();
    });

    scrim.addEventListener("click", () => {
        body.classList.remove("lums-sidebar-drawer-open");
        syncState();
    });

    document.addEventListener("keydown", (event) => {
        if (event.key === "Escape") {
            body.classList.remove("lums-sidebar-drawer-open");
            syncState();
        }
    });

    window.addEventListener("resize", syncState);
    sidebar.querySelectorAll("a").forEach((link) => {
        link.addEventListener("click", () => {
            body.classList.remove("lums-sidebar-drawer-open");
            syncState();
        });
    });

    syncState();

    const nav = document.getElementById("lums-sidebar-nav");
    const customizer = document.getElementById("lums-sidebar-customizer");
    const editToggle = document.getElementById("lums-sidebar-edit-toggle");
    const editor = document.getElementById("lums-sidebar-editor");
    const editorList = document.getElementById("lums-sidebar-editor-list");
    const saveButton = document.getElementById("lums-sidebar-save");
    const resetButton = document.getElementById("lums-sidebar-reset");
    const editorStatus = document.getElementById("lums-sidebar-editor-status");

    if (!nav || !customizer || !editToggle || !editor || !editorList ||
        !saveButton || !resetButton || !editorStatus) return;

    const links = Array.from(nav.querySelectorAll("[data-nav-id]"));
    const linkById = new Map(links.map(link => [link.dataset.navId, link]));
    const preferenceKey = `lums-sidebar-preferences:${nav.dataset.userId}`;
    const labels = customizer.dataset;
    let preferences = { order: links.map(link => link.dataset.navId), hidden: [] };

    function readPreferences() {
        try {
            const saved = JSON.parse(localStorage.getItem(preferenceKey) || "null");
            if (!saved || !Array.isArray(saved.order) || !Array.isArray(saved.hidden)) {
                return;
            }
            const knownIds = new Set(linkById.keys());
            const order = saved.order.filter(id => knownIds.has(id));
            for (const id of knownIds) {
                if (!order.includes(id)) order.push(id);
            }
            preferences = {
                order,
                hidden: saved.hidden.filter(id => knownIds.has(id))
            };
        } catch (_) {
            // Navigation still works if local storage is unavailable or invalid.
        }
    }

    function applyPreferences() {
        for (const id of preferences.order) {
            const link = linkById.get(id);
            if (link) nav.appendChild(link);
        }
        for (const [id, link] of linkById) {
            link.hidden = preferences.hidden.includes(id);
        }
    }

    function renderEditor() {
        editorList.replaceChildren();
        for (const [index, id] of preferences.order.entries()) {
            const link = linkById.get(id);
            const item = document.createElement("li");
            const label = document.createElement("label");
            const checkbox = document.createElement("input");
            checkbox.type = "checkbox";
            checkbox.checked = !preferences.hidden.includes(id);
            checkbox.addEventListener("change", () => {
                preferences.hidden = checkbox.checked
                    ? preferences.hidden.filter(hiddenId => hiddenId !== id)
                    : [...preferences.hidden, id];
                applyPreferences();
            });
            label.append(checkbox, document.createTextNode(
                link.querySelector(".lums-sidebar-label")?.textContent.trim() || id
            ));

            const controls = document.createElement("span");
            controls.className = "lums-sidebar-order-controls";
            for (const [offset, text, ariaLabel] of [
                [-1, "↑", labels.moveUp],
                [1, "↓", labels.moveDown]
            ]) {
                const button = document.createElement("button");
                button.type = "button";
                button.textContent = text;
                button.setAttribute("aria-label", ariaLabel);
                button.disabled = index + offset < 0 ||
                    index + offset >= preferences.order.length;
                button.addEventListener("click", () => {
                    const newIndex = index + offset;
                    const reordered = [...preferences.order];
                    [reordered[index], reordered[newIndex]] =
                        [reordered[newIndex], reordered[index]];
                    preferences.order = reordered;
                    renderEditor();
                    applyPreferences();
                });
                controls.appendChild(button);
            }
            item.append(label, controls);
            editorList.appendChild(item);
        }
    }

    function setEditing(editing) {
        editor.hidden = !editing;
        editToggle.setAttribute("aria-expanded", String(editing));
        editToggle.querySelector(".lums-sidebar-label").textContent =
            editing ? labels.done : labels.edit;
        editorStatus.textContent = "";
        if (editing) {
            renderEditor();
            editor.querySelector("input")?.focus();
        }
    }

    readPreferences();
    applyPreferences();
    editToggle.addEventListener("click", () => setEditing(editor.hidden));
    saveButton.addEventListener("click", () => {
        try {
            localStorage.setItem(preferenceKey, JSON.stringify(preferences));
            editorStatus.textContent = labels.saved;
        } catch (_) {
            editorStatus.textContent = labels.error;
        }
    });
    resetButton.addEventListener("click", () => {
        try {
            localStorage.removeItem(preferenceKey);
        } catch (_) {
            editorStatus.textContent = labels.error;
            return;
        }
        preferences = {
            order: links.map(link => link.dataset.navId),
            hidden: []
        };
        applyPreferences();
        renderEditor();
        editorStatus.textContent = labels.saved;
    });
})();
