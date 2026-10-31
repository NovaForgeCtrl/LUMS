(() => {
    "use strict";

    const root = document.getElementById("alerts-dashboard");
    if (!root) return;

    const lumsT = window.lumsT || {};
    function t(key) {
        return lumsT[key] || key;
    }


    const body = document.getElementById("alerts-table-body");
    const feedback = document.getElementById("alerts-feedback");
    const connection = document.getElementById("alerts-connection-status");
    const connectionContainer = connection.closest(".lums-pagebar-status");
    const refreshButton = document.getElementById("alerts-refresh");
    const csrf = root.dataset.csrf;
    const allowedTabs = new Set([
        "dashboard", "overview", "history", "rules",
        "integrations", "webhooks", "logs"
    ]);
    const requestedTab = window.location.hash.slice(1);
    let currentTab = allowedTabs.has(requestedTab)
        ? requestedTab
        : "dashboard";
    let loading = false;
    let lastAlerts = [];

    const labels = {
        critical: root.dataset.critical,
        warning: root.dataset.warning,
        info: root.dataset.info,
        triggered: root.dataset.triggered,
        acknowledged: root.dataset.acknowledged,
        resolved: root.dataset.resolved,
        escalated: root.dataset.escalated
    };

    function text(value) {
        return String(value ?? "");
    }

    function setConnectionState(state, label) {
        connection.textContent = label;
        connectionContainer.dataset.state = state;
    }

    function cell(value) {
        const td = document.createElement("td");
        td.textContent = text(value);
        return td;
    }

    function button(label, action, id) {
        const el = document.createElement("button");
        el.type = "button";
        el.textContent = label;
        el.dataset.action = action;
        el.dataset.alertId = id;
        return el;
    }

    function renderAlerts(alerts) {
        lastAlerts = Array.isArray(alerts) ? alerts : [];

        document.getElementById("alerts-last-updated").textContent =
            new Date().toLocaleTimeString();

        body.replaceChildren();

        if (!lastAlerts.length) {
            const tr = document.createElement("tr");
            const td = cell(root.dataset.empty);
            td.colSpan = 6;
            tr.append(td);
            body.append(tr);
            return;
        }

        for (const alert of lastAlerts) {
            const tr = document.createElement("tr");
            tr.append(cell(alert.message));
            tr.append(cell(alert.source));

            const severity = document.createElement("td");
            const badge = document.createElement("span");
            badge.className = `severity-${alert.severity}`;
            badge.textContent = labels[alert.severity] || text(alert.severity);
            severity.append(badge);
            tr.append(severity);

            tr.append(cell(labels[alert.status] || alert.status));
            tr.append(cell(alert.triggered_at));

            const actions = document.createElement("td");
            if (alert.status !== "resolved") {
                if (alert.status === "triggered" || alert.status === "escalated") {
                    actions.append(button(root.dataset.acknowledge, "acknowledge", alert.alert_id));
                }
                actions.append(button(root.dataset.resolve, "resolve", alert.alert_id));
            } else {
                actions.textContent = "—";
            }
            tr.append(actions);
            body.append(tr);
        }
    }

    async function requestJson(url, options = {}) {
        const response = await fetch(url, {
            credentials: "same-origin",
            cache: "no-store",
            ...options
        });

        let data;
        try {
            data = await response.json();
        } catch (_) {
            data = {};
        }

        if (!response.ok) {
            throw new Error(root.dataset.apiError || root.dataset.loadError);
        }
        return data;
    }

    async function refresh() {
        if (document.hidden) return;
        if (currentTab === "rules" || currentTab === "integrations"
            || currentTab === "webhooks" || currentTab === "soc"
            || currentTab === "logs") return;
        if (loading) return;
        loading = true;
        refreshButton.disabled = true;

        try {
            const url = currentTab === "history"
                ? `${root.dataset.historyUrl}?limit=100`
                : root.dataset.currentUrl;
            const data = await requestJson(url);
            renderAlerts(data.alerts || []);
            setConnectionState("connected", root.dataset.connected);
            feedback.textContent = "";
        } catch (error) {
            setConnectionState("offline", root.dataset.offline);
            feedback.textContent = error.message || root.dataset.loadError;
        } finally {
            loading = false;
            refreshButton.disabled = false;
        }
    }


    const tableWrap = root.querySelector(".alerts-table-wrap");
    const rulesPanel = document.getElementById("alerts-rules-panel");
    const integrationsPanel = document.getElementById("alerts-integrations-panel");
    const webhooksPanel = document.getElementById("alerts-webhooks-panel");
    const logsPanel = document.getElementById("alerts-logs-panel");
    const logsBody = document.getElementById("alerts-logs-body");
    const logsFeedback = document.getElementById("alerts-logs-feedback");
    const logsFilters = document.getElementById("alerts-logs-filters");
    const socPanel = document.getElementById("alerts-soc-panel");

    function logFilterParams() {
        const params = new URLSearchParams(new FormData(logsFilters));
        for (const [key, value] of [...params.entries()]) {
            if (!String(value).trim()) params.delete(key);
        }
        return params;
    }

    async function loadLogs() {
        logsFeedback.textContent = t("Log data is loading…");
        logsBody.replaceChildren();

        try {
            const params = logFilterParams();
            const response = await requestJson(`/alerts/api/logs?${params.toString()}`);
            const logs = Array.isArray(response.logs) ? response.logs : [];

            if (!logs.length) {
                const tr = document.createElement("tr");
                tr.append(cell(t("No matching log entries found.")));
                tr.firstElementChild.colSpan = 6;
                logsBody.append(tr);
            } else {
                for (const log of logs) {
                    const tr = document.createElement("tr");
                    tr.append(
                        cell(log.timestamp),
                        cell(log.source === "soc" ? t("SOC event") : t("Audit")),
                        cell(log.actor),
                        cell(log.event),
                        cell(log.status),
                        cell(log.details || log.payload || "—")
                    );
                    logsBody.append(tr);
                }
            }

            logsFeedback.textContent =
                `${response.count ?? logs.length} ${t("entries")}` +
                (response.truncated ? ` — ${t("Display limited; export contains up to 5000 entries.")}` : "");
        } catch (error) {
            logsFeedback.textContent = error.message || t("Logs could not be loaded.");
            const tr = document.createElement("tr");
            tr.append(cell(t("Error loading logs.")));
            tr.firstElementChild.colSpan = 6;
            logsBody.append(tr);
        }
    }

    logsFilters.addEventListener("submit", (event) => {
        event.preventDefault();
        void loadLogs();
    });

    document.querySelectorAll("[data-log-export]").forEach((exportButton) => {
        exportButton.addEventListener("click", () => {
            const params = logFilterParams();
            params.set("format", exportButton.dataset.logExport);
            window.location.assign(`/alerts/api/logs/export?${params.toString()}`);
        });
    });
    const rulesBody = document.getElementById("alerts-rules-body");
    const ruleForm = document.getElementById("alerts-rule-form");
    const ruleCreate = document.getElementById("alerts-rule-create");
    const ruleSave = document.getElementById("alerts-rule-save");
    const canManageRules = root.dataset.canManage === "true";

    function ruleField(id) {
        return document.getElementById(id);
    }

    function ruleApiUrl(ruleId) {
        return ruleId
            ? `${root.dataset.rulesUrl}/${encodeURIComponent(ruleId)}`
            : root.dataset.rulesUrl;
    }

    function ruleCell(value) {
        const td = document.createElement("td");
        td.textContent = text(value);
        return td;
    }

    function actionButton(label, action, ruleId) {
        const el = document.createElement("button");
        el.type = "button";
        el.textContent = label;
        el.dataset.ruleAction = action;
        el.dataset.ruleId = ruleId;
        el.disabled = !canManageRules;
        return el;
    }

    function renderRules(rules) {
        rulesBody.replaceChildren();

        if (!rules.length) {
            const tr = document.createElement("tr");
            const td = ruleCell(root.dataset.rulesEmpty);
            td.colSpan = 6;
            tr.append(td);
            rulesBody.append(tr);
            return;
        }

        for (const rule of rules) {
            const tr = document.createElement("tr");
            tr.append(ruleCell(rule.name));
            tr.append(ruleCell(rule.condition));

            let threshold;
            try {
                threshold = typeof rule.threshold === "string"
                    ? rule.threshold
                    : JSON.stringify(rule.threshold);
            } catch (_) {
                threshold = String(rule.threshold ?? "");
            }
            tr.append(ruleCell(threshold));
            tr.append(ruleCell(labels[rule.severity] || rule.severity));
            tr.append(ruleCell(rule.enabled ? root.dataset.ruleEnabled : root.dataset.ruleDisabled));

            const actions = document.createElement("td");
            if (canManageRules) {
                actions.append(actionButton(root.dataset.ruleEdit, "edit", rule.rule_id));
                actions.append(actionButton(
                    rule.enabled ? root.dataset.ruleDisable : root.dataset.ruleEnable,
                    "toggle",
                    rule.rule_id
                ));
                actions.append(actionButton(root.dataset.ruleDelete, "delete", rule.rule_id));
            } else {
                actions.textContent = root.dataset.ruleEnabled;
                actions.textContent = "—";
            }
            tr.append(actions);
            rulesBody.append(tr);
        }
    }

    async function loadRules() {
        rulesBody.replaceChildren();
        const row = document.createElement("tr");
        const loadingCell = ruleCell(root.dataset.loading);
        loadingCell.colSpan = 6;
        row.append(loadingCell);
        rulesBody.append(row);

        try {
            const data = await requestJson(root.dataset.rulesUrl);
            renderRules(data.rules || []);
            feedback.textContent = "";
        } catch (error) {
            rulesBody.replaceChildren();
            const tr = document.createElement("tr");
            const td = ruleCell(error.message || root.dataset.loadError);
            td.colSpan = 6;
            tr.append(td);
            rulesBody.append(tr);
        }
    }

    function resetRuleForm() {
        ruleForm.reset();
        ruleField("alerts-rule-id").value = "";
        ruleField("alerts-rule-enabled").checked = true;
        ruleField("alerts-rule-group").checked = true;
        ruleField("alerts-rule-deduplicate").checked = true;
        ruleField("alerts-rule-threshold").value = "80";
        ruleField("alerts-rule-escalation").value = "[]";
        ruleSave.textContent = root.dataset.ruleCreate;
        ruleForm.hidden = true;
    }

    function editRule(rule) {
        ruleField("alerts-rule-id").value = rule.rule_id;
        ruleField("alerts-rule-name").value = rule.name || "";
        ruleField("alerts-rule-description").value = rule.description || "";
        ruleField("alerts-rule-condition").value = rule.condition || "";
        ruleField("alerts-rule-severity").value = rule.severity || "warning";
        ruleField("alerts-rule-threshold").value = JSON.stringify(rule.threshold ?? 80, null, 2);
        ruleField("alerts-rule-escalation").value = JSON.stringify(rule.escalation_path || [], null, 2);
        ruleField("alerts-rule-enabled").checked = Boolean(rule.enabled);
        ruleField("alerts-rule-group").checked = Boolean(rule.group_similar);
        ruleField("alerts-rule-deduplicate").checked = Boolean(rule.deduplicate);
        ruleSave.textContent = root.dataset.ruleEdit;
        ruleForm.hidden = false;
        ruleField("alerts-rule-name").focus();
    }

    ruleCreate.hidden = !canManageRules;
    ruleCreate.addEventListener("click", () => {
        resetRuleForm();
        ruleForm.hidden = false;
        ruleField("alerts-rule-name").focus();
    });
    ruleField("alerts-rule-cancel").addEventListener("click", resetRuleForm);

    ruleForm.addEventListener("submit", async (event) => {
        event.preventDefault();
        if (!canManageRules) return;

        let threshold;
        let escalationPath;

        try {
            threshold = JSON.parse(ruleField("alerts-rule-threshold").value);
        } catch (_) {
            feedback.textContent = root.dataset.ruleThresholdError;
            return;
        }

        try {
            escalationPath = JSON.parse(ruleField("alerts-rule-escalation").value);
            if (!Array.isArray(escalationPath) ||
                escalationPath.some((item) => typeof item !== "string" || !item.trim())) {
                throw new Error("Invalid escalation path");
            }
        } catch (_) {
            feedback.textContent = root.dataset.ruleEscalationError;
            return;
        }

        const ruleId = ruleField("alerts-rule-id").value;
        const payload = {
            name: ruleField("alerts-rule-name").value.trim(),
            description: ruleField("alerts-rule-description").value,
            condition: ruleField("alerts-rule-condition").value.trim(),
            severity: ruleField("alerts-rule-severity").value,
            threshold,
            escalation_path: escalationPath,
            enabled: ruleField("alerts-rule-enabled").checked,
            group_similar: ruleField("alerts-rule-group").checked,
            deduplicate: ruleField("alerts-rule-deduplicate").checked
        };

        ruleSave.disabled = true;
        feedback.textContent = "";
        try {
            await requestJson(ruleApiUrl(ruleId), {
                method: ruleId ? "PUT" : "POST",
                headers: {
                    "Content-Type": "application/json",
                    "X-CSRF-Token": csrf
                },
                body: JSON.stringify(payload)
            });
            resetRuleForm();
            await loadRules();
        } catch (error) {
            feedback.textContent = error.message || root.dataset.confirmError;
        } finally {
            ruleSave.disabled = false;
        }
    });

    rulesBody.addEventListener("click", async (event) => {
        const target = event.target.closest("button[data-rule-action]");
        if (!target || !canManageRules) return;

        const ruleId = target.dataset.ruleId;
        const action = target.dataset.ruleAction;
        target.disabled = true;
        feedback.textContent = "";

        try {
            const data = await requestJson(root.dataset.rulesUrl);
            const rule = (data.rules || []).find((item) => item.rule_id === ruleId);
            if (!rule) throw new Error(root.dataset.loadError);

            if (action === "edit") {
                editRule(rule);
                return;
            }

            if (action === "delete") {
                if (!window.confirm(root.dataset.ruleDelete + ": " + rule.name + "?")) {
                    return;
                }
                await requestJson(ruleApiUrl(ruleId), {
                    method: "DELETE",
                    headers: { "X-CSRF-Token": csrf }
                });
            } else if (action === "toggle") {
                await requestJson(ruleApiUrl(ruleId), {
                    method: "PUT",
                    headers: {
                        "Content-Type": "application/json",
                        "X-CSRF-Token": csrf
                    },
                    body: JSON.stringify({ enabled: !rule.enabled })
                });
            }
            await loadRules();
        } catch (error) {
            feedback.textContent = error.message || root.dataset.confirmError;
        } finally {
            target.disabled = false;
        }
    });

    body.addEventListener("click", async (event) => {
        const target = event.target.closest("button[data-action]");
        if (!target) return;

        const action = target.dataset.action;
        const alertId = target.dataset.alertId;
        const template = action === "acknowledge"
            ? root.dataset.ackTemplate
            : root.dataset.resolveTemplate;
        const url = template.replace("__ALERT_ID__", encodeURIComponent(alertId));

        target.disabled = true;
        feedback.textContent = "";

        try {
            await requestJson(url, {
                method: "POST",
                headers: { "X-CSRF-Token": csrf }
            });
            await refresh();
        } catch (error) {
            feedback.textContent = error.message || root.dataset.confirmError;
            target.disabled = false;
        }
    });

    const socFeedback = document.getElementById("alerts-soc-feedback");
    const socResult = document.getElementById("alerts-soc-result");
    const socRunButtons = document.querySelectorAll("[data-soc-scenario]");

    function setSocMetric(id, value) {
        const element = document.getElementById(id);
        if (element) element.textContent = text(value);
    }

    const socSvgNamespace = "http://www.w3.org/2000/svg";

    function socSvgElement(name, attributes = {}, label = null) {
        const element = document.createElementNS(socSvgNamespace, name);
        Object.entries(attributes).forEach(([key, value]) => {
            element.setAttribute(key, String(value));
        });
        if (label !== null) element.textContent = String(label);
        return element;
    }

    function socChartBase(containerId, title, width = 720, height = 250) {
        const container = document.getElementById(containerId);
        if (!container) return null;

        container.replaceChildren();

        const svg = socSvgElement("svg", {
            viewBox: `0 0 ${width} ${height}`,
            role: "img",
            "aria-label": title,
            focusable: "false"
        });

        svg.appendChild(socSvgElement("title", {}, title));
        svg.appendChild(socSvgElement("rect", {
            x: 0, y: 0, width, height, rx: 10,
            fill: "currentColor", opacity: 0.025
        }));
        container.appendChild(svg);
        return {container, svg, width, height};
    }

    function socSvgText(svg, x, y, value, options = {}) {
        const textNode = socSvgElement("text", {
            x, y,
            fill: "currentColor",
            "font-size": options.size || 12,
            "font-weight": options.weight || 400,
            "text-anchor": options.anchor || "start",
            opacity: options.opacity ?? 0.9
        }, value);
        svg.appendChild(textNode);
        return textNode;
    }

    function socSvgLine(svg, x1, y1, x2, y2, options = {}) {
        svg.appendChild(socSvgElement("line", {
            x1, y1, x2, y2,
            stroke: options.color || "currentColor",
            "stroke-width": options.width || 1,
            opacity: options.opacity ?? 0.2,
            "stroke-dasharray": options.dash || ""
        }));
    }

    function socSvgRect(svg, x, y, width, height, options = {}) {
        svg.appendChild(socSvgElement("rect", {
            x, y, width: Math.max(0, width), height: Math.max(0, height),
            rx: options.radius ?? 4,
            fill: options.color || "currentColor",
            opacity: options.opacity ?? 0.8
        }));
    }

    function socRenderTimeline(result) {
        const chart = socChartBase(
            "soc-chart-timeline", t("Event timeline distribution")
        );
        if (!chart) return;

        const {svg} = chart;
        const events = Array.isArray(result.events) ? result.events : [];
        const detections = Array.isArray(result.detections) ? result.detections : [];
        const correlations = Array.isArray(result.correlations) ? result.correlations : [];

        if (!events.length) {
            socSvgText(svg, 24, 45, t("No events in this scenario."));
            return;
        }

        const parsed = events.map((event, index) => ({
            event,
            index,
            time: Date.parse(event.timestamp || "")
        })).filter(item => Number.isFinite(item.time));

        if (!parsed.length) {
            socSvgText(svg, 24, 45, "Keine gültigen Zeitstempel verfügbar.");
            return;
        }

        const minTime = Math.min(...parsed.map(item => item.time));
        const maxTime = Math.max(...parsed.map(item => item.time));
        const span = Math.max(1, maxTime - minTime);
        const left = 65;
        const right = 690;
        const axisY = 155;
        const rows = [
            {name: t("Events"), key: "events", items: parsed, y: 75, color: "#60a5fa"},
            {name: t("Detections"), key: "detections", items: detections, y: 112, color: "#fbbf24"},
            {name: t("Correlations"), key: "correlations", items: correlations, y: 149, color: "#a78bfa"}
        ];

        rows.forEach(row => {
            socSvgText(svg, 14, row.y + 4, row.name, {size: 10});
            socSvgLine(svg, left, row.y, right, row.y, {opacity: 0.12});
            row.items.forEach((item, index) => {
                let x;
                if (row.key === "events") {
                    x = left + ((item.time - minTime) / span) * (right - left);
                } else {
                    const eventId = item.event_id;
                    const matching = parsed.find(entry =>
                        entry.event.event_id === eventId
                    );
                    const time = Date.parse(
                        item.event_timestamp || item.timestamp || ""
                    );
                    x = matching
                        ? left + ((matching.time - minTime) / span) * (right - left)
                        : Number.isFinite(time)
                            ? left + ((time - minTime) / span) * (right - left)
                            : left + ((index + 1) / (row.items.length + 1)) * (right - left);
                }

                svg.appendChild(socSvgElement("circle", {
                    cx: x, cy: row.y, r: row.key === "events" ? 5 : 6,
                    fill: row.color,
                    stroke: "currentColor",
                    "stroke-width": 0.5
                }));

                const title = socSvgElement("title", {}, [
                    row.name,
                    item.event_id || item.rule_id || item.correlation_id || t("Entry")
                ].join(": "));
                svg.lastChild.appendChild(title);
            });
        });

        socSvgLine(svg, left, axisY + 12, right, axisY + 12, {opacity: 0.35});
        const startLabel = new Date(minTime).toLocaleTimeString();
        const endLabel = new Date(maxTime).toLocaleTimeString();
        socSvgText(svg, left, axisY + 30, startLabel, {size: 10});
        socSvgText(svg, right, axisY + 30, endLabel, {size: 10, anchor: "end"});
        socSvgText(svg, 14, 225, `${events.length} ${t("events")}`, {weight: 600});
    }

    function socRenderSeverity(result) {
        const chart = socChartBase(
            "soc-chart-severity", t("Severity and incident distribution"), 720, 270
        );
        if (!chart) return;

        const {svg} = chart;
        const detections = Array.isArray(result.detections) ? result.detections : [];
        const incidents = Array.isArray(result.incidents) ? result.incidents : [];
        const severities = [
            {name: t("Info"), key: "info", color: "#60a5fa"},
            {name: t("Warning"), key: "warning", color: "#fbbf24"},
            {name: t("Critical"), key: "critical", color: "#f87171"}
        ];

        socSvgText(svg, 20, 25, t("Detections by severity"), {weight: 600});
        const detectionCounts = severities.map(severity =>
            detections.filter(item =>
                String(item.severity || "info").toLowerCase() === severity.key
            ).length
        );
        const maxDetection = Math.max(1, ...detectionCounts);

        severities.forEach((severity, index) => {
            const y = 45 + index * 43;
            socSvgText(svg, 20, y + 14, severity.name);
            socSvgRect(svg, 105, y, 440 * detectionCounts[index] / maxDetection, 23, {
                color: severity.color
            });
            socSvgText(svg, 565, y + 16, detectionCounts[index], {weight: 600});
        });

        socSvgLine(svg, 20, 181, 700, 181, {opacity: 0.2});
        socSvgText(svg, 20, 202, t("Incidents by status"), {weight: 600});

        const statuses = [
            {name: t("Open"), key: "open", color: "#f87171"},
            {name: t("In progress"), key: "investigating", color: "#fbbf24"},
            {name: t("Resolved"), key: "resolved", color: "#34d399"}
        ];
        statuses.forEach((status, index) => {
            const count = incidents.filter(item =>
                String(item.status || "open").toLowerCase() === status.key
            ).length;
            const x = 20 + index * 225;
            socSvgRect(svg, x, 216, 190, 30, {color: status.color, opacity: 0.2});
            socSvgText(svg, x + 9, 235, `${status.name}: ${count}`, {weight: 600});
        });
    }

    function socRenderPipeline(result) {
        const chart = socChartBase(
            "soc-chart-pipeline", t("SOC pipeline results"), 900, 270
        );
        if (!chart) return;

        const {svg} = chart;
        const nodes = [
            {label: t("Events"), count: result.event_count ?? 0, color: "#60a5fa"},
            {label: t("Detections"), count: result.detection_count ?? 0, color: "#fbbf24"},
            {label: t("Correlations"), count: result.correlation_count ?? 0, color: "#a78bfa"},
            {label: t("Incidents"), count: Array.isArray(result.incidents) ? result.incidents.length : 0, color: "#f87171"}
        ];

        const xPositions = [20, 245, 470, 695];
        nodes.forEach((node, index) => {
            const x = xPositions[index];
            socSvgRect(svg, x, 42, 180, 88, {color: node.color, opacity: 0.16, radius: 9});
            socSvgRect(svg, x, 42, 180, 5, {color: node.color, radius: 2});
            socSvgText(svg, x + 90, 70, node.label, {
                size: 13, weight: 600, anchor: "middle"
            });
            socSvgText(svg, x + 90, 105, node.count, {
                size: 25, weight: 700, anchor: "middle"
            });

            if (index < nodes.length - 1) {
                socSvgLine(svg, x + 185, 86, xPositions[index + 1] - 8, 86, {
                    width: 2, opacity: 0.7
                });
                svg.appendChild(socSvgElement("path", {
                    d: `M ${xPositions[index + 1] - 14} 80 L ${xPositions[index + 1] - 7} 86 L ${xPositions[index + 1] - 14} 92`,
                    fill: "none",
                    stroke: "currentColor",
                    "stroke-width": 2
                }));
            }
        });

        const duplicateCount = result.duplicate_count ?? 0;
        socSvgText(svg, 22, 171, t("Duplicates removed"), {size: 13, weight: 600});
        socSvgRect(svg, 22, 187, 390, 22, {
            color: "#34d399",
            opacity: 0.2
        });
        socSvgRect(svg, 22, 187, 390 * Math.min(1, duplicateCount / Math.max(1, result.event_count ?? 0)), 22, {
            color: "#34d399"
        });
        socSvgText(svg, 430, 203, duplicateCount, {weight: 600});

        const incidents = Array.isArray(result.incidents) ? result.incidents : [];
        const critical = incidents.filter(item =>
            String(item.severity || "").toLowerCase() === "critical"
        ).length;
        const warning = incidents.filter(item =>
            String(item.severity || "").toLowerCase() === "warning"
        ).length;

        socSvgText(svg, 22, 238, `${t("Critical")}: ${critical}   ${t("Warning")}: ${warning}   ${t("Total")}: ${incidents.length}`, {
            size: 13, weight: 600
        });
    }

    function renderSocVisualizations(result) {
        socRenderTimeline(result);
        socRenderSeverity(result);
        socRenderPipeline(result);
    }

    async function runSocScenario(buttonElement) {
        const scenario = buttonElement.dataset.socScenario;
        if (!["auth", "duplicates", "privilege"].includes(scenario)) return;

        socRunButtons.forEach((button) => {
            button.disabled = true;
        });
        socFeedback.textContent = t("Python SOC pipeline is running…");

        try {
            const response = await fetch("/alerts/api/soc/run", {
                method: "POST",
                credentials: "same-origin",
                headers: {
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                    "X-CSRF-Token": csrf
                },
                body: JSON.stringify({scenario})
            });
            const data = await response.json().catch(() => ({}));

            if (!response.ok) {
                const message = data.error === "csrf_validation_failed"
                    ? t("CSRF validation failed. Please reload the page.")
                    : data.error === "invalid_scenario"
                        ? t("Unknown SOC scenario.")
                        : data.error === "soc_processing_failed"
                            ? t("The Python SOC pipeline could not execute the scenario.")
                            : t("SOC request failed (HTTP {status}).").replace("{status}", String(response.status));
                throw new Error(message);
            }

            const result = data.result || {};
            setSocMetric("soc-count-events", result.event_count ?? 0);
            setSocMetric("soc-count-detections", result.detection_count ?? 0);
            setSocMetric("soc-count-correlations", result.correlation_count ?? 0);
            setSocMetric("soc-count-duplicates", result.duplicate_count ?? 0);
            setSocMetric(
                "soc-count-incidents",
                Array.isArray(result.incidents) ? result.incidents.length : 0
            );
            socResult.textContent = JSON.stringify({
                scenario: data.scenario,
                ...result
            }, null, 2);
            renderSocVisualizations(result);
            socFeedback.textContent =
                t("Scenario completed: {scenario}. Result provided by the Python pipeline.").replace("{scenario}", scenario);
        } catch (error) {
            socFeedback.textContent = error.message || t("SOC request failed.");
        } finally {
            socRunButtons.forEach((button) => {
                button.disabled = false;
            });
        }
    }

    socRunButtons.forEach((button) => {
        button.addEventListener("click", () => {
            void runSocScenario(button);
        });
    });

    function activateTab(tabName, { load = true } = {}) {
        if (!allowedTabs.has(tabName)) {
            tabName = "dashboard";
        }

        currentTab = tabName;

        document.querySelectorAll("[data-alert-tab]").forEach((link) => {
            const selected = link.dataset.alertTab === currentTab;
            link.classList.toggle("is-active", selected);
            if (selected) {
                link.setAttribute("aria-current", "page");
            } else {
                link.removeAttribute("aria-current");
            }
        });

        tableWrap.hidden = currentTab === "dashboard"
            || currentTab === "rules"
            || currentTab === "integrations"
            || currentTab === "webhooks"
            || currentTab === "logs";
        rulesPanel.hidden = currentTab !== "rules";
        integrationsPanel.hidden = currentTab !== "integrations";
        webhooksPanel.hidden = currentTab !== "webhooks";
        logsPanel.hidden = currentTab !== "logs";
        socPanel.hidden = currentTab !== "dashboard";
        feedback.textContent = "";

        if (!load) return;

        if (currentTab === "dashboard"
            || currentTab === "overview"
            || currentTab === "history") {
            void refresh();
        } else if (currentTab === "rules") {
            void loadRules();
        } else if (currentTab === "logs") {
            void loadLogs();
        }
    }

    const alertsNavToggle = document.getElementById(
        "lums-sidebar-alerts-toggle"
    );
    const alertsSubnav = document.getElementById(
        "lums-sidebar-alerts-subnav"
    );

    if (alertsNavToggle && alertsSubnav) {
        alertsNavToggle.addEventListener("click", () => {
            const expanded =
                alertsNavToggle.getAttribute("aria-expanded") === "true";
            alertsNavToggle.setAttribute("aria-expanded", String(!expanded));
            alertsSubnav.hidden = expanded;
        });
    }

    window.addEventListener("hashchange", () => {
        activateTab(window.location.hash.slice(1));
    });

    refreshButton.addEventListener("click", refresh);

    document.addEventListener("visibilitychange", () => {
        if (!document.hidden) void refresh();
    });

    setConnectionState("connecting", root.dataset.loading);
    activateTab(currentTab);
    window.setInterval(() => {
        if (!document.hidden) void refresh();
    }, 5000);
})();
