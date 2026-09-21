(() => {
    "use strict";

    const STORAGE_KEY = "lums-theme";

    const THEMES = [
        "standard",
        "LUMSStadium",
        "golf",
        "nerd",
        "geek",
        "admin"
    ];

    let matrixTimer = null;
    let matrixLayer = null;

    function removeMatrixEffect() {
        if (matrixTimer) {
            clearTimeout(matrixTimer);
            matrixTimer = null;
        }

        if (matrixLayer) {
            matrixLayer.remove();
            matrixLayer = null;
        }
    }

    function createMatrixEffect() {
        if (document.documentElement.dataset.theme !== "nerd") {
            return;
        }

        removeMatrixEffect();

        matrixLayer = document.createElement("div");
        matrixLayer.id = "lums-matrix-layer";
        matrixLayer.setAttribute("aria-hidden", "true");

        const columns = Math.max(
            12,
            Math.floor(window.innerWidth / 22)
        );

        for (let i = 0; i < columns; i++) {
            const column = document.createElement("span");

            column.className = "lums-matrix-column";

            column.style.left =
                `${(i / columns) * 100}%`;

            column.style.animationDelay =
                `${Math.random() * -2.5}s`;

            column.style.animationDuration =
                `${1.4 + Math.random() * 2.2}s`;

            let text = "";

            const length =
                10 + Math.floor(Math.random() * 18);

            for (let j = 0; j < length; j++) {
                const chars =
                    "01ABCDEFGHIJKLMNOPQRSTUVWXYZ#$%";

                text +=
                    chars.charAt(
                        Math.floor(
                            Math.random() * chars.length
                        )
                    ) + "<br>";
            }

            column.innerHTML = text;

            matrixLayer.appendChild(column);
        }

        document.body.appendChild(matrixLayer);

        window.setTimeout(() => {
            if (matrixLayer) {
                matrixLayer.classList.add("active");
            }
        }, 30);

        window.setTimeout(() => {
            if (matrixLayer) {
                matrixLayer.classList.remove("active");
            }
        }, 4200);

        matrixTimer = window.setTimeout(
            createMatrixEffect,
            25000 + Math.random() * 25000
        );
    }

    function startMatrixEffect() {
        removeMatrixEffect();

        matrixTimer = window.setTimeout(
            createMatrixEffect,
            25000 + Math.random() * 25000
        );
    }

    function updateMatrixEffect(theme) {
        if (theme === "nerd") {
            startMatrixEffect();
        } else {
            removeMatrixEffect();
        }
    }

    function applyTheme(theme) {
        if (!THEMES.includes(theme)) {
            theme = "standard";
        }

        document.documentElement.dataset.theme = theme;

        const selector =
            document.getElementById(
                "login-theme-select"
            );

        if (selector) {
            selector.value = theme;
        }

        const dashboardSelector =
            document.getElementById(
                "theme-select"
            );

        if (dashboardSelector) {
            dashboardSelector.value = theme;
        }

        localStorage.setItem(
            STORAGE_KEY,
            theme
        );

        updateMatrixEffect(theme);

        if (window.LumsNetwork) {
            if (theme === "geek") {
                window.LumsNetwork.start();
            } else {
                window.LumsNetwork.stop();
            }
        }
    }

    function loadTheme() {
        const savedTheme =
            localStorage.getItem(
                STORAGE_KEY
            );

        applyTheme(
            THEMES.includes(savedTheme)
                ? savedTheme
                : "standard"
        );
    }

    function initializeThemeSelectors() {
        const selectors = [
            document.getElementById(
                "login-theme-select"
            ),
            document.getElementById(
                "theme-select"
            )
        ].filter(Boolean);

        selectors.forEach((selector) => {
            selector.addEventListener(
                "change",
                (event) => {
                    applyTheme(
                        event.target.value
                    );
                }
            );
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
