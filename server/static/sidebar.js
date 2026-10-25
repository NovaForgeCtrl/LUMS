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
})();
