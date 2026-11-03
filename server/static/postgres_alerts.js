(() => {
    "use strict";

    const root = document.getElementById("alerts-dashboard");
    if (!root) return;

    const $ = (id) => document.getElementById(id);
    const canManage = root.dataset.canManage === "true";
    const csrfToken = root.dataset.csrfToken;
    const locale = root.dataset.locale || undefined;

    const urls = {
        current: root.dataset.currentUrl,
        history: root.dataset.historyUrl,
        rules: root.dataset.rulesUrl,
        acknowledge: root.dataset.ackUrl,
        resolve: root.dataset.resolveUrl,
        escalate: root.dataset.escalateUrl,
        createRule: root.dataset.ruleCreateUrl,
        updateRule: root.dataset.ruleUpdateUrl,
        deleteRule: root.dataset.ruleDeleteUrl
    };

    const labels = {
        acknowledge: root.dataset.labelAcknowledge || "Acknowledge",
        resolve: root.dataset.labelResolve || "Resolve",
        escalate: root.dataset.labelEscalate || "Escalate",
        edit: root.dataset.labelEdit || "Edit",
        delete: root.dataset.labelDelete || "Delete",
        enabled: root.dataset.labelEnabled || "Enabled",
        disabled: root.dataset.labelDisabled || "Disabled",
        noAlerts: root.dataset.labelNoAlerts || "No alerts found.",
        noRules: root.dataset.labelNoRules || "No alert rules found.",
        loading: root.dataset.labelLoading || "Loading…",
        loadFailed: root.dataset.messageLoadFailed || "Unable to load alerts data.",
        actionFailed: root.dataset.messageActionFailed || "The requested action failed.",
        deleteConfirm: root.dataset.messageDeleteConfirm || "Delete alert rule",
        ruleCreated: root.dataset.messageRuleCreated || "Rule created successfully",
        ruleUpdated: root.dataset.messageRuleUpdated || "Rule updated successfully",
        ruleDeleted: root.dataset.messageRuleDeleted || "Rule deleted successfully",
        thresholdInvalid: root.dataset.messageThresholdJsonInvalid || "Threshold must be valid JSON.",
        escalationInvalid: root.dataset.messageEscalationJsonInvalid || "Escalation path must be a valid JSON array of non-empty strings.",
        connecting: root.dataset.labelConnecting || "Connecting…",
        connected: root.dataset.labelConnected || "Connected",
        offline: root.dataset.labelOffline || "Alerts could not be loaded.",
        status: {
            triggered: root.dataset.statusTriggered || "Alert triggered",
            acknowledged: root.dataset.statusAcknowledged || "Acknowledged",
            resolved: root.dataset.statusResolved || "Alert resolved",
            escalated: root.dataset.statusEscalated || "Alert escalated"
        },
        severity: {
            critical: root.dataset.severityCritical || "Critical",
            warning: root.dataset.severityWarning || "Warning",
            info: root.dataset.severityInfo || "Info"
        }
    };

    let cachedRules = [];

    function setFeedback(message, isError = false) {
        const target = $("alerts-feedback");
        if (!target) return;
        target.textContent = message || "";
        target.dataset.state = isError ? "error" : "normal";
    }

    function setConnection(state) {
        const indicator = $("alerts-connection");
        const label = $("alerts-connection-label");
        if (!indicator || !label) return;

        indicator.dataset.state = state;
        label.textContent = state === "connected"
            ? labels.connected
            : state === "offline" ? labels.offline : labels.connecting;
    }

    function endpoint(template, id) {
        return template.replace(
            "__ALERT_ID__",
            encodeURIComponent(id)
        ).replace(
            "__RULE_ID__",
            encodeURIComponent(id)
        );
    }

    async function request(url, options = {}) {
        const method = (options.method || "GET").toUpperCase();
        const headers = { Accept: "application/json" };

        if (method !== "GET") {
            headers["X-CSRF-Token"] = csrfToken;
        }

        const fetchOptions = {
            method,
            headers,
            credentials: "same-origin",
            cache: "no-store"
        };

        if (options.body !== undefined) {
            headers["Content-Type"] = "application/json";
            fetchOptions.body = JSON.stringify(options.body);
        }

        const response = await fetch(url, fetchOptions);
        let data = {};

        try {
            data = await response.json();
        } catch (_) {
            data = {};
        }

        if (!response.ok) {
            throw new Error(data.error || `HTTP ${response.status}`);
        }

        return data;
    }

    function addCell(row, value) {
        const cell = document.createElement("td");
        cell.textContent = value === null || value === undefined
            ? "—"
            : String(value);
        row.appendChild(cell);
        return cell;
    }

    function addButton(parent, label, action, id) {
        const button = document.createElement("button");
        button.type = "button";
        button.textContent = label;
        button.dataset.action = action;
        button.dataset.id = id;
        parent.appendChild(button);
        return button;
    }

    function formatTimestamp(value) {
        if (!value) return "—";

        const date = new Date(value);
        if (Number.isNaN(date.getTime())) return "—";

        try {
            return new Intl.DateTimeFormat(locale, {
                dateStyle: "medium",
                timeStyle: "short"
            }).format(date);
        } catch (_) {
            return date.toISOString();
        }
    }

    function addSeverityCell(row, severity) {
        const cell = document.createElement("td");
        const badge = document.createElement("span");
        const allowed = ["critical", "warning", "info"];
        const value = allowed.includes(severity) ? severity : "info";

        badge.className = `severity-${value}`;
        badge.textContent = labels.severity[value] || value;
        cell.appendChild(badge);
        row.appendChild(cell);
    }

    function renderAlerts(body, alerts, includeActions) {
        body.replaceChildren();

        const colspan = includeActions && canManage ? 7 : 6;
        if (!alerts.length) {
            const row = document.createElement("tr");
            const cell = document.createElement("td");
            cell.colSpan = colspan;
            cell.textContent = labels.noAlerts;
            row.appendChild(cell);
            body.appendChild(row);
            return;
        }

        for (const alert of alerts) {
            const row = document.createElement("tr");

            addCell(row, formatTimestamp(alert.triggered_at));
            addCell(row, alert.source);
            addCell(row, alert.message);
            addSeverityCell(row, alert.severity);
            addCell(row, labels.status[alert.status] || alert.status);
            addCell(row, alert.escalation_count);

            if (includeActions && canManage) {
                const cell = document.createElement("td");
                const status = alert.status;

                if (status === "triggered" || status === "escalated") {
                    addButton(
                        cell,
                        labels.acknowledge,
                        "acknowledge",
                        alert.alert_id
                    );
                }

                if (
                    status === "triggered" ||
                    status === "acknowledged" ||
                    status === "escalated"
                ) {
                    addButton(
                        cell,
                        labels.escalate,
                        "escalate",
                        alert.alert_id
                    );
                    addButton(
                        cell,
                        labels.resolve,
                        "resolve",
                        alert.alert_id
                    );
                }

                row.appendChild(cell);
            }

            body.appendChild(row);
        }
    }

    function renderRules(body, rules) {
        body.replaceChildren();

        if (!rules.length) {
            const row = document.createElement("tr");
            const cell = document.createElement("td");
            cell.colSpan = canManage ? 5 : 4;
            cell.textContent = labels.noRules;
            row.appendChild(cell);
            body.appendChild(row);
            return;
        }

        for (const rule of rules) {
            const row = document.createElement("tr");

            addCell(row, rule.name);
            addCell(row, rule.condition);
            addSeverityCell(row, rule.severity);
            addCell(row, rule.enabled ? labels.enabled : labels.disabled);

            if (canManage) {
                const cell = document.createElement("td");
                addButton(cell, labels.edit, "edit-rule", rule.rule_id);
                addButton(cell, labels.delete, "delete-rule", rule.rule_id);
                row.appendChild(cell);
            }

            body.appendChild(row);
        }
    }

    function updateMetrics(alerts) {
        $("alerts-metric-active").textContent = alerts.length;
        $("alerts-metric-critical").textContent = alerts.filter(
            (item) => item.severity === "critical"
        ).length;
        $("alerts-metric-triggered").textContent = alerts.filter(
            (item) => item.status === "triggered"
        ).length;
        $("alerts-metric-warning").textContent = alerts.filter(
            (item) => item.severity === "warning"
        ).length;
    }

    async function loadCurrent() {
        const data = await request(urls.current);
        if (!Array.isArray(data.alerts)) {
            throw new Error("Invalid current-alert response");
        }

        renderAlerts($("alerts-current-body"), data.alerts, true);
        updateMetrics(data.alerts);
    }

    async function loadHistory() {
        const data = await request(urls.history);
        if (!Array.isArray(data.alerts)) {
            throw new Error("Invalid alert-history response");
        }

        renderAlerts($("alerts-history-body"), data.alerts, false);
    }

    async function loadRules() {
        const data = await request(urls.rules);
        if (!Array.isArray(data.rules)) {
            throw new Error("Invalid alert-rules response");
        }

        cachedRules = data.rules;
        renderRules($("alerts-rules-body"), cachedRules);
    }

    async function refreshAll() {
        setConnection("connecting");

        try {
            await Promise.all([
                loadCurrent(),
                loadHistory(),
                loadRules()
            ]);
            setConnection("connected");
        } catch (error) {
            setConnection("offline");
            setFeedback(labels.loadFailed, true);
        }
    }

    function setRuleForm(rule = null) {
        const form = $("alerts-rule-form");
        if (!form) return;

        form.hidden = false;
        $("alerts-rule-id").value = rule?.rule_id || "";
        $("alerts-rule-name").value = rule?.name || "";
        $("alerts-rule-condition").value = rule?.condition || "";
        $("alerts-rule-description").value = rule?.description || "";
        $("alerts-rule-threshold").value = JSON.stringify(
            rule ? rule.threshold : null,
            null,
            2
        );
        $("alerts-rule-severity").value = rule?.severity || "warning";
        $("alerts-rule-escalation").value = JSON.stringify(
            rule?.escalation_path || [],
            null,
            2
        );
        $("alerts-rule-enabled").checked = rule?.enabled ?? true;
        $("alerts-rule-group").checked = rule?.group_similar ?? true;
        $("alerts-rule-deduplicate").checked = rule?.deduplicate ?? true;

        form.scrollIntoView({ behavior: "smooth", block: "nearest" });
    }

    function hideRuleForm() {
        const form = $("alerts-rule-form");
        if (form) form.hidden = true;
    }

    async function saveRule(event) {
        event.preventDefault();

        let threshold;
        let escalationPath;

        try {
            threshold = JSON.parse($("alerts-rule-threshold").value);
        } catch (_) {
            setFeedback(labels.thresholdInvalid, true);
            return;
        }

        try {
            escalationPath = JSON.parse(
                $("alerts-rule-escalation").value
            );
        } catch (_) {
            setFeedback(labels.escalationInvalid, true);
            return;
        }

        if (!Array.isArray(escalationPath)) {
            setFeedback(labels.escalationInvalid, true);
            return;
        }

        const ruleId = $("alerts-rule-id").value;
        const payload = {
            name: $("alerts-rule-name").value.trim(),
            condition: $("alerts-rule-condition").value.trim(),
            description: $("alerts-rule-description").value,
            threshold,
            severity: $("alerts-rule-severity").value,
            escalation_path: escalationPath,
            enabled: $("alerts-rule-enabled").checked,
            group_similar: $("alerts-rule-group").checked,
            deduplicate: $("alerts-rule-deduplicate").checked
        };

        const submit = $("alerts-rule-submit");
        submit.disabled = true;

        try {
            const url = ruleId
                ? endpoint(urls.updateRule, ruleId)
                : urls.createRule;

            await request(url, {
                method: ruleId ? "PUT" : "POST",
                body: payload
            });

            hideRuleForm();
            setFeedback(ruleId ? labels.ruleUpdated : labels.ruleCreated);
            await refreshAll();
        } catch (error) {
            setFeedback(labels.actionFailed, true);
        } finally {
            submit.disabled = false;
        }
    }

    async function handleAction(event) {
        const button = event.target.closest("button[data-action]");
        if (!button || !root.contains(button)) return;

        const action = button.dataset.action;
        const id = button.dataset.id;

        if (action === "edit-rule") {
            const rule = cachedRules.find((item) => item.rule_id === id);
            if (rule) setRuleForm(rule);
            return;
        }

        if (action === "delete-rule") {
            if (!window.confirm(labels.deleteConfirm)) return;

            button.disabled = true;
            try {
                await request(
                    endpoint(urls.deleteRule, id),
                    { method: "DELETE" }
                );
                setFeedback(labels.ruleDeleted);
                await refreshAll();
            } catch (error) {
                setFeedback(labels.actionFailed, true);
            } finally {
                button.disabled = false;
            }
            return;
        }

        const actionUrls = {
            acknowledge: urls.acknowledge,
            resolve: urls.resolve,
            escalate: urls.escalate
        };

        if (!actionUrls[action]) return;

        button.disabled = true;
        try {
            await request(
                endpoint(actionUrls[action], id),
                { method: "POST" }
            );
            setFeedback({
                acknowledge: labels.status.acknowledged,
                resolve: labels.status.resolved,
                escalate: labels.status.escalated
            }[action]);
            await refreshAll();
        } catch (error) {
            setFeedback(labels.actionFailed, true);
        } finally {
            button.disabled = false;
        }
    }

    $("alerts-refresh").addEventListener("click", refreshAll);
    $("alerts-history-refresh").addEventListener("click", refreshAll);
    root.addEventListener("click", handleAction);

    const newRuleButton = $("alerts-rule-new");
    if (newRuleButton) {
        newRuleButton.addEventListener("click", () => setRuleForm());
    }

    const cancelRuleButton = $("alerts-rule-cancel");
    if (cancelRuleButton) {
        cancelRuleButton.addEventListener("click", hideRuleForm);
    }

    const ruleForm = $("alerts-rule-form");
    if (ruleForm) {
        ruleForm.addEventListener("submit", saveRule);
    }

    refreshAll();
})();
