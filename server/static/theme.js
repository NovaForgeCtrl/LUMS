(() => {
    "use strict";

    const STORAGE_KEY = "lums-theme";

    const THEMES = [
        "standard",
        "nfl",
        "golf",
        "nerd",
        "geek",
        "admin"
    ];

    function applyTheme(theme) {
        if (!THEMES.includes(theme)) {
            theme = "standard";
        }

        document.documentElement.dataset.theme = theme;

        const selector = document.getElementById("login-theme-select");

        if (selector) {
            selector.value = theme;
        }

        const dashboardSelector = document.getElementById("theme-select");

        if (dashboardSelector) {
            dashboardSelector.value = theme;
        }

        localStorage.setItem(STORAGE_KEY, theme);
    }

    function loadTheme() {
        const savedTheme = localStorage.getItem(STORAGE_KEY);

        applyTheme(
            THEMES.includes(savedTheme)
                ? savedTheme
                : "standard"
        );
    }

    function initializeThemeSelectors() {
        const selectors = [
            document.getElementById("login-theme-select"),
            document.getElementById("theme-select")
        ].filter(Boolean);

        selectors.forEach((selector) => {
            selector.addEventListener("change", (event) => {
                applyTheme(event.target.value);
            });
        });

        loadTheme();
    }

    if (document.readyState === "loading") {
        document.addEventListener(
            "DOMContentLoaded",
            initializeThemeSelectors
        );
    } else {
        initializeThemeSelectors();
    }
})();
