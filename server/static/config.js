"use strict";

(() => {
    const configElement = document.getElementById("lums-config");

    if (!configElement) {
        return;
    }

    try {
        const config = JSON.parse(configElement.textContent);

        for (const [key, value] of Object.entries(config)) {
            window[key] = value;
        }
    } catch (error) {
        console.error("LUMS configuration could not be parsed.", error);
    }
})();
