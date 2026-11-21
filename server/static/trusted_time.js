(() => {
    "use strict";

    const root = document.getElementById("trusted-time-dashboard");
    if (!root) return;

    const apiUrl = root.dataset.apiUrl;
    const ids = [
        "trusted-time-status",
        "trusted-time-source",
        "trusted-time-age",
        "trusted-time-offset",
        "trusted-time-uncertainty",
        "trusted-time-authentication",
        "trusted-time-observed",
        "trusted-time-updated"
    ];

    const setText = (id, value) => {
        const element = document.getElementById(id);
        if (element) element.textContent = String(value);
    };

    const formatMs = (value) => {
        if (typeof value !== "number" || !Number.isFinite(value)) {
            return "—";
        }
        return new Intl.NumberFormat(
            document.documentElement.dataset.locale || undefined,
            { maximumFractionDigits: 3 }
        ).format(value) + " ms";
    };

    const formatDate = (value) => {
        if (typeof value !== "string") return "—";
        const date = new Date(value);
        if (Number.isNaN(date.getTime())) return "—";
        return new Intl.DateTimeFormat(
            document.documentElement.dataset.locale || undefined,
            { dateStyle: "medium", timeStyle: "medium" }
        ).format(date);
    };

    const unavailable = (message) => {
        setText("trusted-time-status", message);
        setText("trusted-time-source", "Source: unavailable");
        setText("trusted-time-age", "—");
        setText("trusted-time-offset", "—");
        setText("trusted-time-uncertainty", "—");
        setText(
            "trusted-time-authentication",
            "No validated host status is currently available."
        );
        setText("trusted-time-observed", "Last observation: —");

        const status = document.getElementById("trusted-time-status");
        if (status) status.dataset.state = "error";
    };

    const load = async () => {
        try {
            const response = await fetch(apiUrl, {
                method: "GET",
                credentials: "same-origin",
                headers: { "Accept": "application/json" },
                cache: "no-store"
            });

            const payload = await response.json();

            if (!response.ok || payload.status !== "synchronized") {
                const reason = payload.error === "trusted_time_not_configured"
                    ? "Host monitor not configured"
                    : "Trusted Time unavailable";
                unavailable(reason);
                setText(
                    "trusted-time-updated",
                    "API response: " + response.status
                );
                return;
            }

            setText("trusted-time-status", "Synchronized and validated");
            setText("trusted-time-source", "Quorum: " + payload.source_id);
            setText(
                "trusted-time-age",
                formatMs(payload.sync_age_upper_bound_ms)
            );
            setText("trusted-time-offset", formatMs(payload.offset_ms));
            setText(
                "trusted-time-uncertainty",
                formatMs(payload.uncertainty_ms)
            );
            setText(
                "trusted-time-authentication",
                payload.authentication_basis
            );
            setText(
                "trusted-time-observed",
                "Observed UTC: " + formatDate(payload.observed_utc)
            );
            setText(
                "trusted-time-updated",
                "Policy: " + payload.policy.name
            );

            const status = document.getElementById("trusted-time-status");
            if (status) status.dataset.state = "ready";
        } catch (error) {
            console.error("Trusted-Time API request failed:", error);
            unavailable("Trusted Time API request failed");
            setText("trusted-time-updated", "No response from the API.");
        }
    };

    for (const id of ids) setText(id, "—");
    load();
    window.setInterval(load, 15000);
})();
