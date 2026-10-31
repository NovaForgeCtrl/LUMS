(() => {
    "use strict";

    const root = document.getElementById("soc-dashboard");
    if (!root) return;

    const message = document.getElementById("soc-dashboard-message");
    const notice = document.getElementById("soc-dashboard-notice");
    const apiUrl = root.dataset.apiUrl;

    const setText = (id, value) => {
        const element = document.getElementById(id);
        if (element) element.textContent = String(value);
    };

    const sourceAvailable = (source) =>
        Boolean(source && source.available === true);

    const sourceLabel = (id, source) => {
        setText(
            id,
            sourceAvailable(source) ? "Verfügbar" : "Nicht bereit"
        );
    };

    const setMetrics = (prefix, keys, values, available) => {
        for (const key of keys) {
            const value = available ? values?.[key] : undefined;
            setText(
                `${prefix}-${key}`,
                value === undefined || value === null ? "—" : value
            );
        }
    };

    const formatTimestamp = (value) => {
        if (!value) return "—";

        const date = new Date(value);
        if (Number.isNaN(date.getTime())) return "—";

        return new Intl.DateTimeFormat(
            document.documentElement.dataset.locale || undefined,
            { dateStyle: "short", timeStyle: "short" }
        ).format(date);
    };

    const renderIncidents = (items, available) => {
        const body = document.getElementById("soc-recent-incidents");
        if (!body) return;

        body.replaceChildren();

        const row = document.createElement("tr");
        const cell = document.createElement("td");
        cell.colSpan = 4;

        if (!available) {
            cell.textContent = "Datenquelle nicht verfügbar.";
            row.appendChild(cell);
            body.appendChild(row);
            return;
        }

        if (!Array.isArray(items) || items.length === 0) {
            cell.textContent = "Keine Incidents vorhanden.";
            row.appendChild(cell);
            body.appendChild(row);
            return;
        }

        for (const incident of items) {
            const incidentRow = document.createElement("tr");
            const values = [
                incident.title,
                incident.severity,
                incident.status,
                formatTimestamp(incident.updated_at)
            ];

            for (const value of values) {
                const incidentCell = document.createElement("td");
                incidentCell.textContent =
                    value == null ? "—" : String(value);
                incidentRow.appendChild(incidentCell);
            }

            body.appendChild(incidentRow);
        }
    };

    const render = (data) => {
        const sources = data.sources || {};

        const eventsAvailable = sourceAvailable(sources.events);
        const sensorsAvailable = sourceAvailable(sources.sensors);
        const incidentsAvailable = sourceAvailable(sources.incidents);

        sourceLabel("soc-events-source", sources.events);
        sourceLabel("soc-sensors-source", sources.sensors);
        sourceLabel("soc-incidents-source", sources.incidents);

        setMetrics(
            "soc-events",
            ["pending", "processing", "processed", "failed"],
            data.events,
            eventsAvailable
        );

        setMetrics(
            "soc-sensors",
            ["active", "revoked"],
            data.sensors,
            sensorsAvailable
        );

        setMetrics(
            "soc-incidents",
            ["open", "investigating", "resolved"],
            data.incidents?.status,
            incidentsAvailable
        );

        setMetrics(
            "soc-severity",
            ["info", "warning", "critical"],
            data.incidents?.severity,
            incidentsAvailable
        );

        renderIncidents(data.recent_incidents, incidentsAvailable);

        setText(
            "soc-incidents-updated",
            incidentsAvailable
                ? `Stand: ${formatTimestamp(data.generated_at)}`
                : "Datenquelle nicht verfügbar"
        );

        const unavailable = [
            eventsAvailable,
            sensorsAvailable,
            incidentsAvailable
        ].filter((available) => !available).length;

        if (unavailable === 0) {
            message.textContent =
                "Alle drei SOC-Datenquellen sind verfügbar.";
            notice.dataset.state = "ready";
        } else {
            message.textContent =
                `${unavailable} von 3 Datenquellen sind nicht verfügbar. ` +
                "Für diese Quellen werden keine Zählerstände angezeigt.";
            notice.dataset.state = "partial";
        }
    };

    const load = async () => {
        try {
            const response = await fetch(apiUrl, {
                method: "GET",
                credentials: "same-origin",
                headers: { "Accept": "application/json" },
                cache: "no-store"
            });

            if (!response.ok) {
                throw new Error(
                    `Dashboard-API antwortete mit HTTP ${response.status}`
                );
            }

            const data = await response.json();
            render(data);
        } catch (error) {
            console.error(
                "SOC dashboard could not be loaded:",
                error
            );

            message.textContent =
                "Dashboard-Daten konnten nicht geladen werden. " +
                "Bitte Anmeldung und Datenbankverbindung prüfen.";

            notice.dataset.state = "error";

            setText("soc-events-source", "Fehler");
            setText("soc-sensors-source", "Fehler");
            setText("soc-incidents-source", "Fehler");

            for (const id of [
                "soc-events-pending",
                "soc-events-processing",
                "soc-events-processed",
                "soc-events-failed",
                "soc-sensors-active",
                "soc-sensors-revoked",
                "soc-incidents-open",
                "soc-incidents-investigating",
                "soc-incidents-resolved",
                "soc-severity-info",
                "soc-severity-warning",
                "soc-severity-critical"
            ]) {
                setText(id, "—");
            }

            renderIncidents([], false);
            setText(
                "soc-incidents-updated",
                "Datenquelle nicht verfügbar"
            );
        }
    };

    load();
})();
