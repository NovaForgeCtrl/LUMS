(() => {
    "use strict";

    const root = document.getElementById("telemetry-dashboard");
    if (!root) return;

    const clientSelect = document.getElementById("telemetry-client");
    const rangeSelect = document.getElementById("telemetry-range");
    const viewSelect = document.getElementById("telemetry-view");
    const status = document.getElementById("telemetry-status");
    const lastUpdated = document.getElementById("telemetry-updated");
    const cpuValue = document.getElementById("telemetry-cpu-value");
    const memoryValue = document.getElementById("telemetry-memory-value");
    const networkValue = document.getElementById("telemetry-network-value");
    const cpuChart = document.getElementById("telemetry-cpu-chart");
    const memoryChart = document.getElementById("telemetry-memory-chart");
    const diskValue = document.getElementById("telemetry-disk-value");
    const diskChart = document.getElementById("telemetry-disk-chart");
    const networkChart = document.getElementById("telemetry-network-chart");
    const fleetBody = document.getElementById("fleet-body");
    const fleetFilter = document.getElementById("fleet-filter");
    const fleetSearch = document.getElementById("fleet-search");
    const systemRoot = document.getElementById("system-monitor");
    const systemStatus = document.getElementById("system-monitor-status");
    const customizer = document.getElementById("dashboard-customizer");
    const dashboardGrid = document.getElementById("health-dashboard-grid");
    const dashboardStatus = document.getElementById("dashboard-settings-status");
    const systemLabels = Object.fromEntries(
        [
            "noData", "stale", "cpu", "memory", "load", "disk", "free",
            "uptime", "os", "kernel", "temperatures", "fans", "noSensors",
            "network", "interface", "link", "receive", "send",
            "errorsDropped", "connectivity", "dns", "gateway", "internet",
            "reachable", "unreachable", "runtime", "name", "state",
            "notAvailable", "noItems", "up", "down", "active", "inactive",
            "failed", "unknown", "containerUp", "containerStopped",
            "containerUnhealthy", "containerUnknown", "journalUnavailable",
            "sshUnavailable", "loginUnavailable", "bootUnavailable",
            "securityNoData",
            "resourceHigh", "resourceOk", "cpuLabel", "memoryLabel",
            "timeLabel", "eventLabel", "loginLabel", "logoutLabel",
            "bootStartedLabel", "lastEntryLabel", "noLoginEvents",
            "noBootHistory"
        ].map(key => [key, systemRoot.dataset[key]])
    );
    const filterOptions = Object.fromEntries(
        Array.from(fleetFilter.options).map(option => [option.value, option.textContent])
    );

    const labels = {
        loading: root.dataset.loading,
        noClients: root.dataset.noClients,
        noSamples: root.dataset.noSamples,
        noNetwork: root.dataset.noNetwork,
        noMatch: root.dataset.noMatch,
        loadError: root.dataset.loadError,
        updated: root.dataset.updated,
        cpu: root.dataset.cpu,
        memory: root.dataset.memory,
        disk: root.dataset.disk,
        network: root.dataset.network,
        download: root.dataset.download,
        upload: root.dataset.upload,
        used: root.dataset.used,
        free: root.dataset.free,
        stale: root.dataset.stale,
        current: root.dataset.current,
        online: filterOptions.online,
        offline: filterOptions.offline,
        unknown: root.dataset.unknown
    };
    const dashboardLabels = Object.fromEntries(
        [
            "settingsLoadError", "settingsSaveError", "settingsSaved", "edit",
            "done", "save", "reset", "hideWidget", "showWidget", "moveUp",
            "moveDown", "drag", "width", "widgets", "thresholds",
            "cpuThreshold", "memoryThreshold", "diskThreshold", "integrations",
            "wazuh", "suricata", "integrationHelp", "widthSmall",
            "widthMedium", "widthLarge", "widthFull", "historyCsv",
            "historyJson", "eventsCsv", "eventsJson", "eventsTitle",
            "eventsEmpty", "time", "client", "event", "metric", "value",
            "threshold", "cpuHigh", "cpuRecovered", "memoryHigh",
            "memoryRecovered", "diskHigh", "diskRecovered",
            "telemetryLost", "telemetryRestored", "notConfigured",
            "active", "inactive", "sshFailure", "serviceFailure",
            "serviceRecovered",
            "sshMetric", "serviceMetric"
        ].map(key => [key, customizer.dataset[key]])
    );

    const VIEW_KEY = "lums.telemetry.view";
    const VIEWS = ["line", "area", "donut"];
    const WIDTH = 640;
    const HEIGHT = 220;
    const PLOT = { left: 56, right: 12, top: 14, bottom: 30 };
    const STATUS_ORDER = { offline: 0, unknown: 1, online: 2 };

    let requestSequence = 0;
    let timer = null;
    let fleet = [];
    let knownClientIds = "";
    let sortKey = "status";
    let sortDirection = 1;
    let dashboardSettings = {
        layout: [
            { id: "summary", width: 12, visible: true },
            { id: "clients", width: 4, visible: true },
            { id: "history", width: 8, visible: true },
            { id: "system", width: 12, visible: true },
            { id: "events", width: 12, visible: true },
            { id: "backup", width: 6, visible: true }
        ],
        thresholds: { cpu: 90, memory: 90, disk: 90 },
        integrations: { wazuh: false, suricata: false }
    };
    let dashboardEditing = false;

    function readStoredView() {
        try {
            const stored = window.localStorage.getItem(VIEW_KEY);
            return VIEWS.includes(stored) ? stored : "line";
        } catch {
            return "line";
        }
    }

    function storeView(value) {
        try {
            window.localStorage.setItem(VIEW_KEY, value);
        } catch {
            // Storage can be blocked; the choice then lasts for this page only.
        }
    }

    function setStatus(message, isError = false) {
        status.textContent = message;
        status.classList.toggle("telemetry-error", isError);
    }

    function svgElement(name, attributes = {}) {
        const node = document.createElementNS("http://www.w3.org/2000/svg", name);
        for (const [key, value] of Object.entries(attributes)) {
            node.setAttribute(key, String(value));
        }
        return node;
    }

    function svgText(svg, text, attributes) {
        const node = svgElement("text", attributes);
        node.textContent = text;
        svg.appendChild(node);
    }

    function formatPercent(value) {
        return Number.isFinite(value) ? `${value.toFixed(1)}%` : "—";
    }

    function formatRate(bytesPerSecond) {
        if (!Number.isFinite(bytesPerSecond)) return "—";
        const units = ["B/s", "KB/s", "MB/s", "GB/s"];
        let value = bytesPerSecond;
        let unit = 0;
        while (value >= 1000 && unit < units.length - 1) {
            value /= 1000;
            unit += 1;
        }
        const digits = unit === 0 || value >= 100 ? 0 : value >= 10 ? 1 : 2;
        return `${value.toFixed(digits)} ${units[unit]}`;
    }

    function formatAge(seconds) {
        if (!Number.isFinite(seconds)) return "—";
        if (seconds < 90) return `${seconds}s`;
        if (seconds < 5400) return `${Math.round(seconds / 60)} min`;
        if (seconds < 172800) return `${Math.round(seconds / 3600)} h`;
        return `${Math.round(seconds / 86400)} d`;
    }

    function niceMax(value) {
        if (!(value > 0)) return 1000;
        const exponent = Math.pow(10, Math.floor(Math.log10(value)));
        const fraction = value / exponent;
        const step = fraction <= 1 ? 1 : fraction <= 2 ? 2 : fraction <= 5 ? 5 : 10;
        return step * exponent;
    }

    function numberOrNull(value) {
        return typeof value === "number" && Number.isFinite(value) ? value : null;
    }

    function toSeries(samples, key, maxValue = Infinity) {
        return samples.map(sample => ({
            time: Date.parse(sample.recorded_at),
            value: numberOrNull(sample[key])
        })).filter(point =>
            Number.isFinite(point.time) &&
            (point.value === null || (point.value >= 0 && point.value <= maxValue))
        );
    }

    function drawFrame(svg, label, maxValue, formatTick) {
        svg.replaceChildren();
        svg.setAttribute("viewBox", `0 0 ${WIDTH} ${HEIGHT}`);
        svg.setAttribute("role", "img");
        svg.setAttribute("aria-label", label);

        const plotHeight = HEIGHT - PLOT.top - PLOT.bottom;
        for (const fraction of [0, 0.25, 0.5, 0.75, 1]) {
            const y = PLOT.top + plotHeight * (1 - fraction);
            svg.appendChild(svgElement("line", {
                x1: PLOT.left, y1: y, x2: WIDTH - PLOT.right, y2: y,
                class: "telemetry-gridline"
            }));
            svgText(svg, formatTick(maxValue * fraction), {
                x: PLOT.left - 8, y: y + 4,
                "text-anchor": "end",
                class: "telemetry-axis-label"
            });
        }
    }

    function drawEmpty(svg, message) {
        svgText(svg, message, {
            x: WIDTH / 2,
            y: HEIGHT / 2,
            "text-anchor": "middle",
            class: "telemetry-empty-label"
        });
    }

    function drawTimeLabels(svg, minTime, maxTime) {
        svgText(svg, new Date(minTime).toLocaleTimeString(), {
            x: PLOT.left, y: HEIGHT - 8,
            "text-anchor": "start",
            class: "telemetry-axis-label"
        });
        svgText(svg, new Date(maxTime).toLocaleTimeString(), {
            x: WIDTH - PLOT.right, y: HEIGHT - 8,
            "text-anchor": "end",
            class: "telemetry-axis-label"
        });
    }

    // Gaps (null values) split a series so missing data is never drawn as a line.
    function drawSeries(svg, series, minTime, span, maxValue, lineClass, filled) {
        const plotWidth = WIDTH - PLOT.left - PLOT.right;
        const plotHeight = HEIGHT - PLOT.top - PLOT.bottom;
        const baseline = PLOT.top + plotHeight;
        const segments = [];
        let current = [];

        for (const point of series) {
            if (point.value === null) {
                if (current.length) segments.push(current);
                current = [];
                continue;
            }
            current.push({
                x: PLOT.left + ((point.time - minTime) / span) * plotWidth,
                y: PLOT.top + (1 - Math.min(point.value, maxValue) / maxValue) * plotHeight
            });
        }
        if (current.length) segments.push(current);

        for (const segment of segments) {
            const coordinates = segment.map(point => `${point.x},${point.y}`);
            if (filled && segment.length > 1) {
                const first = segment[0];
                const last = segment[segment.length - 1];
                svg.appendChild(svgElement("polygon", {
                    points: [`${first.x},${baseline}`, ...coordinates, `${last.x},${baseline}`].join(" "),
                    class: `telemetry-area ${lineClass}`
                }));
            }
            if (segment.length === 1) {
                svg.appendChild(svgElement("circle", {
                    cx: segment[0].x, cy: segment[0].y, r: 2.5,
                    class: `telemetry-dot ${lineClass}`
                }));
            } else {
                svg.appendChild(svgElement("polyline", {
                    points: coordinates.join(" "),
                    class: `telemetry-line ${lineClass}`
                }));
            }
        }

        const lastSegment = segments[segments.length - 1];
        if (lastSegment) {
            const end = lastSegment[lastSegment.length - 1];
            svg.appendChild(svgElement("circle", {
                cx: end.x, cy: end.y, r: 4,
                class: `telemetry-point ${lineClass}`
            }));
        }
    }

    function timeBounds(seriesList) {
        const times = seriesList.flat().map(point => point.time);
        const minTime = Math.min(...times);
        const maxTime = Math.max(...times);
        return { minTime, maxTime, span: Math.max(1, maxTime - minTime) };
    }

    function drawPercentChart(svg, samples, key, label, view, threshold) {
        if (view === "donut") {
            drawDonut(svg, samples, key, label, threshold);
            return;
        }

        drawFrame(svg, label, 100, value => `${Math.round(value)}%`);
        const series = toSeries(samples, key, 100).filter(point => point.value !== null);
        if (!series.length) {
            drawEmpty(svg, labels.noSamples);
            return;
        }

        const { minTime, maxTime, span } = timeBounds([series]);
        drawSeries(svg, series, minTime, span, 100, "telemetry-series-primary", view === "area");
        if (Number.isFinite(threshold)) {
            const y = PLOT.top +
                (1 - threshold / 100) * (HEIGHT - PLOT.top - PLOT.bottom);
            svg.appendChild(svgElement("line", {
                x1: PLOT.left,
                y1: y,
                x2: WIDTH - PLOT.right,
                y2: y,
                class: "telemetry-threshold-line"
            }));
        }
        drawTimeLabels(svg, minTime, maxTime);
    }

    function drawDonut(svg, samples, key, label, threshold = 90) {
        svg.replaceChildren();
        svg.setAttribute("viewBox", `0 0 ${WIDTH} ${HEIGHT}`);
        svg.setAttribute("role", "img");

        const latest = samples[samples.length - 1];
        const value = latest ? numberOrNull(latest[key]) : null;
        const centerX = WIDTH / 2;
        const centerY = HEIGHT / 2;
        const radius = 74;
        const circumference = 2 * Math.PI * radius;

        if (value === null || value < 0 || value > 100) {
            svg.setAttribute("aria-label", label);
            drawEmpty(svg, labels.noSamples);
            return;
        }

        svg.setAttribute("aria-label", `${label}: ${formatPercent(value)}`);
        svg.appendChild(svgElement("circle", {
            cx: centerX, cy: centerY, r: radius,
            class: "telemetry-donut-track"
        }));
        const level = value >= threshold
            ? "critical"
            : value >= Math.max(50, threshold - 15) ? "warning" : "normal";
        svg.appendChild(svgElement("circle", {
            cx: centerX, cy: centerY, r: radius,
            "stroke-dasharray": `${(value / 100) * circumference} ${circumference}`,
            transform: `rotate(-90 ${centerX} ${centerY})`,
            class: `telemetry-donut-value telemetry-level-${level}`
        }));
        svgText(svg, formatPercent(value), {
            x: centerX, y: centerY + 2,
            "text-anchor": "middle",
            class: "telemetry-donut-label"
        });
        svgText(svg, `${labels.used} · ${labels.free} ${formatPercent(100 - value)}`, {
            x: centerX, y: centerY + 24,
            "text-anchor": "middle",
            class: "telemetry-axis-label"
        });
    }

    function drawNetworkChart(samples, view) {
        const download = toSeries(samples, "network_rx_bytes_per_second");
        const upload = toSeries(samples, "network_tx_bytes_per_second");
        const hasData = download.concat(upload).some(point => point.value !== null);

        if (!hasData) {
            drawFrame(networkChart, labels.network, 1000, formatRate);
            drawEmpty(networkChart, labels.noNetwork);
            return;
        }

        const peak = Math.max(...download.concat(upload).map(point => point.value ?? 0));
        const maxValue = niceMax(peak);
        drawFrame(networkChart, labels.network, maxValue, formatRate);

        const { minTime, maxTime, span } = timeBounds([download, upload]);
        const filled = view === "area";
        drawSeries(networkChart, download, minTime, span, maxValue, "telemetry-series-rx", filled);
        drawSeries(networkChart, upload, minTime, span, maxValue, "telemetry-series-tx", filled);
        drawTimeLabels(networkChart, minTime, maxTime);
    }

    function latestRates(samples) {
        for (let index = samples.length - 1; index >= 0; index -= 1) {
            const rx = numberOrNull(samples[index].network_rx_bytes_per_second);
            const tx = numberOrNull(samples[index].network_tx_bytes_per_second);
            if (rx !== null && tx !== null) return { rx, tx };
        }
        return null;
    }

    function renderDetails(samples) {
        const view = viewSelect.value;
        drawPercentChart(
            cpuChart, samples, "cpu_percent", labels.cpu, view,
            dashboardSettings.thresholds.cpu
        );
        drawPercentChart(
            memoryChart, samples, "memory_percent", labels.memory, view,
            dashboardSettings.thresholds.memory
        );
        drawPercentChart(
            diskChart, samples, "disk_percent", labels.disk, view,
            dashboardSettings.thresholds.disk
        );
        drawNetworkChart(samples, view);

        const latest = samples[samples.length - 1];
        if (!latest) {
            cpuValue.textContent = "—";
            memoryValue.textContent = "—";
            diskValue.textContent = "—";
            networkValue.textContent = "—";
            lastUpdated.textContent = "";
            return;
        }

        cpuValue.textContent = formatPercent(Number(latest.cpu_percent));
        memoryValue.textContent = formatPercent(Number(latest.memory_percent));
        diskValue.textContent = formatPercent(numberOrNull(latest.disk_percent));
        const rates = latestRates(samples);
        networkValue.textContent = rates
            ? `↓ ${formatRate(rates.rx)}  ↑ ${formatRate(rates.tx)}`
            : "—";
        lastUpdated.textContent =
            `${labels.updated} ${new Date(latest.recorded_at).toLocaleString()}`;
    }

    function clientMetrics(entry) {
        const latest = entry.latest;
        return {
            hostname: entry.hostname.toLowerCase(),
            status: STATUS_ORDER[entry.status] ?? 1,
            cpu: latest ? numberOrNull(latest.cpu_percent) : null,
            memory: latest ? numberOrNull(latest.memory_percent) : null,
            rx: latest ? numberOrNull(latest.network_rx_bytes_per_second) : null,
            tx: latest ? numberOrNull(latest.network_tx_bytes_per_second) : null,
            age: numberOrNull(entry.telemetry_age_seconds)
        };
    }

    function needsAttention(entry, metrics) {
        return entry.status !== "online" ||
            entry.telemetry_stale ||
            (metrics.cpu ?? 0) >= dashboardSettings.thresholds.cpu ||
            (metrics.memory ?? 0) >= dashboardSettings.thresholds.memory ||
            (numberOrNull(entry.latest && entry.latest.disk_percent) ?? 0) >=
                dashboardSettings.thresholds.disk;
    }

    function matchesFilter(entry, metrics) {
        const filter = fleetFilter.value;
        if (filter === "online" || filter === "offline") return entry.status === filter;
        if (filter === "stale") return entry.telemetry_stale;
        if (filter === "attention") return needsAttention(entry, metrics);
        return true;
    }

    function appendCell(row, text, className) {
        const cell = document.createElement("td");
        cell.textContent = text;
        if (className) cell.className = className;
        row.appendChild(cell);
        return cell;
    }

    function formatBytes(bytes) {
        if (!Number.isFinite(bytes) || bytes < 0) return "—";
        const units = ["B", "KB", "MB", "GB", "TB"];
        let value = bytes;
        let unit = 0;
        while (value >= 1000 && unit < units.length - 1) {
            value /= 1000;
            unit += 1;
        }
        return `${value.toFixed(unit === 0 || value >= 100 ? 0 : 1)} ${units[unit]}`;
    }

    function formatUptime(seconds) {
        if (!Number.isFinite(seconds) || seconds < 0) return "—";
        const days = Math.floor(seconds / 86400);
        const hours = Math.floor((seconds % 86400) / 3600);
        const minutes = Math.floor((seconds % 3600) / 60);
        return days ? `${days} d ${hours} h` : `${hours} h ${minutes} min`;
    }

    function reachabilityText(value) {
        if (value === true) return systemLabels.reachable;
        if (value === false) return systemLabels.unreachable;
        return systemLabels.unknown;
    }

    function setSystemValue(id, value) {
        const node = document.getElementById(id);
        if (node) node.textContent = value || "—";
    }

    function renderTableMessage(body, message, columnCount) {
        body.replaceChildren();
        const row = document.createElement("tr");
        const cell = appendCell(row, message);
        cell.colSpan = columnCount;
        body.appendChild(row);
    }

    function localizedDate(value) {
        const date = new Date(value);
        return Number.isNaN(date.getTime()) ? value : date.toLocaleString();
    }

    function renderWidgetControls() {
        const toggles = document.getElementById("dashboard-widget-toggles");
        toggles.replaceChildren();
        for (const widget of dashboardSettings.layout) {
            const node = dashboardGrid.querySelector(
                `[data-widget-id="${widget.id}"]`
            );
            if (!node) continue;
            node.hidden = !widget.visible;
            node.style.setProperty("--widget-span", String(widget.width));
            dashboardGrid.appendChild(node);

            let controls = node.querySelector(".dashboard-widget-controls");
            if (!controls) {
                controls = document.createElement("div");
                controls.className = "dashboard-widget-controls";
                const handle = document.createElement("button");
                handle.type = "button";
                handle.className = "dashboard-drag-handle";
                handle.textContent = dashboardLabels.drag;
                handle.draggable = true;
                controls.appendChild(handle);

                const widthLabel = document.createElement("label");
                widthLabel.textContent = `${dashboardLabels.width}: `;
                const widthSelect = document.createElement("select");
                widthSelect.className = "dashboard-width-select";
                for (const [width, text] of [
                    [4, dashboardLabels.widthSmall],
                    [6, dashboardLabels.widthMedium],
                    [8, dashboardLabels.widthLarge],
                    [12, dashboardLabels.widthFull]
                ]) {
                    const option = document.createElement("option");
                    option.value = String(width);
                    option.textContent = text;
                    widthSelect.appendChild(option);
                }
                widthSelect.addEventListener("change", () => {
                    const current = dashboardSettings.layout.find(
                        item => item.id === widget.id
                    );
                    if (current) current.width = Number(widthSelect.value);
                    node.style.setProperty("--widget-span", widthSelect.value);
                });
                widthLabel.appendChild(widthSelect);
                controls.appendChild(widthLabel);

                const hideButton = document.createElement("button");
                hideButton.type = "button";
                hideButton.textContent = dashboardLabels.hideWidget;
                hideButton.addEventListener("click", () => {
                    const current = dashboardSettings.layout.find(
                        item => item.id === widget.id
                    );
                    if (current) current.visible = false;
                    renderWidgetControls();
                });
                controls.appendChild(hideButton);
                for (const [direction, text] of [
                    [-1, dashboardLabels.moveUp],
                    [1, dashboardLabels.moveDown]
                ]) {
                    const moveButton = document.createElement("button");
                    moveButton.type = "button";
                    moveButton.className = "dashboard-move-button";
                    moveButton.textContent = direction < 0 ? "↑" : "↓";
                    moveButton.setAttribute("aria-label", text);
                    moveButton.addEventListener("click", () =>
                        moveWidget(widget.id, direction)
                    );
                    controls.appendChild(moveButton);
                }
                node.prepend(controls);
                handle.addEventListener("dragstart", event => {
                    event.dataTransfer.setData("text/plain", widget.id);
                    event.dataTransfer.effectAllowed = "move";
                    node.classList.add("is-dragging");
                });
                handle.addEventListener("dragend", () =>
                    node.classList.remove("is-dragging")
                );
                node.addEventListener("dragover", event => {
                    if (dashboardEditing) event.preventDefault();
                });
                node.addEventListener("drop", event => {
                    if (!dashboardEditing) return;
                    event.preventDefault();
                    const sourceId = event.dataTransfer.getData("text/plain");
                    if (sourceId && sourceId !== widget.id) {
                        reorderWidget(sourceId, widget.id);
                    }
                });
            }
            controls.hidden = !dashboardEditing;
            controls.querySelector(".dashboard-width-select").value =
                String(widget.width);

            const toggleLabel = document.createElement("label");
            const toggle = document.createElement("input");
            toggle.type = "checkbox";
            toggle.checked = widget.visible;
            toggle.addEventListener("change", () => {
                const current = dashboardSettings.layout.find(
                    item => item.id === widget.id
                );
                if (current) current.visible = toggle.checked;
                renderWidgetControls();
            });
            toggleLabel.append(toggle, document.createTextNode(
                ` ${node.dataset.widgetLabel}`
            ));
            toggles.appendChild(toggleLabel);
        }
        for (const node of dashboardGrid.querySelectorAll(".dashboard-widget")) {
            node.classList.toggle("is-editing", dashboardEditing);
        }
    }

    function moveWidget(id, direction) {
        const index = dashboardSettings.layout.findIndex(item => item.id === id);
        const next = index + direction;
        if (index < 0 || next < 0 || next >= dashboardSettings.layout.length) return;
        const [widget] = dashboardSettings.layout.splice(index, 1);
        dashboardSettings.layout.splice(next, 0, widget);
        renderWidgetControls();
    }

    function reorderWidget(sourceId, targetId) {
        const sourceIndex = dashboardSettings.layout.findIndex(
            item => item.id === sourceId
        );
        const targetIndex = dashboardSettings.layout.findIndex(
            item => item.id === targetId
        );
        if (sourceIndex < 0 || targetIndex < 0) return;
        const [widget] = dashboardSettings.layout.splice(sourceIndex, 1);
        dashboardSettings.layout.splice(targetIndex, 0, widget);
        renderWidgetControls();
    }

    function applyDashboardSettings(settings) {
        dashboardSettings = settings;
        for (const [key, inputId] of [
            ["cpu", "threshold-cpu"],
            ["memory", "threshold-memory"],
            ["disk", "threshold-disk"]
        ]) {
            document.getElementById(inputId).value = settings.thresholds[key];
        }
        document.getElementById("integration-wazuh").checked =
            settings.integrations.wazuh;
        document.getElementById("integration-suricata").checked =
            settings.integrations.suricata;
        renderWidgetControls();
    }

    function readDashboardControls() {
        const thresholds = {
            cpu: Number(document.getElementById("threshold-cpu").value),
            memory: Number(document.getElementById("threshold-memory").value),
            disk: Number(document.getElementById("threshold-disk").value)
        };
        if (Object.values(thresholds).some(value =>
            !Number.isInteger(value) || value < 50 || value > 99
        )) {
            dashboardStatus.textContent = dashboardLabels.settingsSaveError;
            return false;
        }
        dashboardSettings.thresholds = thresholds;
        dashboardSettings.integrations = {
            wazuh: document.getElementById("integration-wazuh").checked,
            suricata: document.getElementById("integration-suricata").checked
        };
        return true;
    }

    async function saveDashboardSettings() {
        if (!readDashboardControls()) return;
        dashboardStatus.textContent = "";
        try {
            const response = await fetch(customizer.dataset.settingsUrl, {
                method: "PUT",
                credentials: "same-origin",
                headers: {
                    "Content-Type": "application/json",
                    "X-CSRF-Token": customizer.dataset.csrfToken,
                    Accept: "application/json"
                },
                body: JSON.stringify(dashboardSettings),
                cache: "no-store"
            });
            if (!response.ok) throw new Error("Dashboard settings save failed");
            dashboardStatus.textContent = dashboardLabels.settingsSaved;
            renderSystemMonitor();
            refreshDetails().catch(() => setStatus(labels.loadError, true));
        } catch {
            dashboardStatus.textContent = dashboardLabels.settingsSaveError;
        }
    }

    async function loadDashboardSettings() {
        try {
            applyDashboardSettings(
                await fetchJson(customizer.dataset.settingsUrl)
            );
        } catch {
            dashboardStatus.textContent = dashboardLabels.settingsLoadError;
            applyDashboardSettings(dashboardSettings);
        }
    }

    function setDashboardEditing(editing) {
        dashboardEditing = editing;
        document.getElementById("dashboard-edit-button").textContent =
            editing ? customizer.dataset.done : customizer.dataset.edit;
        document.getElementById("dashboard-save-button").hidden = !editing;
        document.getElementById("dashboard-reset-button").hidden = !editing;
        document.getElementById("dashboard-customizer-options").hidden = !editing;
        renderWidgetControls();
    }

    function initializeDashboardCustomizer() {
        document.getElementById("dashboard-edit-button").addEventListener(
            "click",
            () => setDashboardEditing(!dashboardEditing)
        );
        document.getElementById("dashboard-save-button").addEventListener(
            "click",
            saveDashboardSettings
        );
        document.getElementById("dashboard-reset-button").addEventListener(
            "click",
            () => applyDashboardSettings({
                layout: [
                    { id: "summary", width: 12, visible: true },
                    { id: "clients", width: 4, visible: true },
                    { id: "history", width: 8, visible: true },
                    { id: "system", width: 12, visible: true },
                    { id: "events", width: 12, visible: true },
                    { id: "backup", width: 6, visible: true }
                ],
                thresholds: { cpu: 90, memory: 90, disk: 90 },
                integrations: { wazuh: false, suricata: false }
            })
        );
    }

    function renderTelemetryEvents(events) {
        const body = document.getElementById("telemetry-events-body");
        body.replaceChildren();
        if (!events.length) {
            renderTableMessage(body, dashboardLabels.eventsEmpty, 5);
            return;
        }
        const eventText = {
            "cpu:threshold_exceeded": dashboardLabels.cpuHigh,
            "cpu:threshold_recovered": dashboardLabels.cpuRecovered,
            "memory:threshold_exceeded": dashboardLabels.memoryHigh,
            "memory:threshold_recovered": dashboardLabels.memoryRecovered,
            "disk:threshold_exceeded": dashboardLabels.diskHigh,
            "disk:threshold_recovered": dashboardLabels.diskRecovered,
            "null:telemetry_lost": dashboardLabels.telemetryLost,
            "null:telemetry_restored": dashboardLabels.telemetryRestored,
            "ssh:ssh_failure": dashboardLabels.sshFailure,
            "service:service_failed": dashboardLabels.serviceFailure,
            "service:service_recovered": dashboardLabels.serviceRecovered
        };
        for (const item of events) {
            const row = document.createElement("tr");
            row.dataset.kind = item.kind;
            appendCell(row, localizedDate(item.timestamp));
            appendCell(
                row,
                eventText[`${item.metric}:${item.kind}`] ||
                    (item.kind === "service_failed"
                        ? dashboardLabels.serviceFailure
                        : item.kind === "service_recovered"
                            ? dashboardLabels.serviceRecovered
                            : item.kind)
            );
            const metricLabel = item.metric === "cpu" ? labels.cpu
                    : item.metric === "memory" ? labels.memory
                        : item.metric === "disk" ? systemLabels.disk
                            : item.metric === "ssh" ? dashboardLabels.sshMetric
                                : item.metric === "service" ||
                                    (typeof item.metric === "string" &&
                                        item.metric.endsWith(".service"))
                                    ? `${dashboardLabels.serviceMetric}: ${item.metric}`
                                    : "—";
            appendCell(row, metricLabel);
            appendCell(
                row,
                item.value === null ? "—"
                    : ["cpu", "memory", "disk"].includes(item.metric)
                        ? formatPercent(item.value)
                        : String(item.value)
            );
            appendCell(
                row,
                item.threshold === null
                    ? "—"
                    : formatPercent(item.threshold)
            );
            body.appendChild(row);
        }
    }

    function configureExportButtons() {
        const clientId = clientSelect.value;
        if (!clientId) return;
        const hours = rangeSelect.value;
        for (const [id, path, format] of [
            ["export-history-csv", "export", "csv"],
            ["export-history-json", "export", "json"],
            ["export-events-csv", "events", "csv"],
            ["export-events-json", "events", "json"]
        ]) {
            document.getElementById(id).onclick = () => {
                const url =
                    `/api/clients/${encodeURIComponent(clientId)}/telemetry/${path}` +
                    `?hours=${encodeURIComponent(hours)}&format=${format}`;
                window.location.assign(url);
            };
        }
    }

    function renderSystemTables(entry) {
        const interfaceBody = document.getElementById("system-interface-body");
        const serviceBody = document.getElementById("system-service-body");
        const containerBody = document.getElementById("system-container-body");
        const system = entry && entry.system;
        if (!system) {
            renderTableMessage(interfaceBody, "—", 5);
            renderTableMessage(serviceBody, "—", 4);
            renderTableMessage(containerBody, "—", 3);
            return;
        }

        interfaceBody.replaceChildren();
        if (!system.interfaces.length) {
            renderTableMessage(interfaceBody, systemLabels.noItems, 5);
        } else {
            for (const item of system.interfaces) {
                const row = document.createElement("tr");
                appendCell(row, item.name);
                const state = item.state === "up"
                    ? systemLabels.up
                    : item.state === "down" || item.state === "lowerlayerdown"
                        ? systemLabels.down
                        : item.state === "dormant"
                            ? systemLabels.inactive
                            : systemLabels.unknown;
                appendCell(
                    row,
                    state,
                    `monitor-state-${item.state === "up" ? "up" : "down"}`
                );
                const rx = numberOrNull(item.rx_bytes_per_second);
                const tx = numberOrNull(item.tx_bytes_per_second);
                appendCell(
                    row,
                    rx === null ? "—" : `${((rx * 8) / 1_000_000).toFixed(2)} Mbit/s`
                );
                appendCell(
                    row,
                    tx === null ? "—" : `${((tx * 8) / 1_000_000).toFixed(2)} Mbit/s`
                );
                appendCell(
                    row,
                    `RX ${item.rx_errors} / ${item.rx_dropped} · TX ${item.tx_errors} / ${item.tx_dropped}`
                );
                interfaceBody.appendChild(row);
            }
        }

        serviceBody.replaceChildren();
        if (!system.services.available) {
            renderTableMessage(serviceBody, systemLabels.notAvailable, 4);
        } else if (!system.services.items.length) {
            renderTableMessage(serviceBody, systemLabels.noItems, 4);
        } else {
            for (const item of system.services.items) {
                const row = document.createElement("tr");
                appendCell(row, item.name);
                const stateLabels = {
                    active: systemLabels.active,
                    failed: systemLabels.failed,
                    inactive: systemLabels.inactive,
                    unknown: systemLabels.unknown
                };
                appendCell(
                    row,
                    `${stateLabels[item.state] || systemLabels.unknown} · ${item.substate}`,
                    `monitor-state-${item.state}`
                );
                appendCell(row, formatUptime(item.runtime_seconds));
                appendCell(
                    row,
                    Number.isInteger(item.restarts) ? String(item.restarts) : "—"
                );
                serviceBody.appendChild(row);
            }
        }

        containerBody.replaceChildren();
        if (!system.containers.available) {
            renderTableMessage(containerBody, systemLabels.notAvailable, 3);
        } else if (!system.containers.items.length) {
            renderTableMessage(containerBody, systemLabels.noItems, 3);
        } else {
            for (const item of system.containers.items) {
                const row = document.createElement("tr");
                appendCell(row, item.runtime);
                appendCell(row, item.name);
                const state = item.state === "running"
                    ? "up"
                    : item.state === "exited" ? "stopped" : item.state;
                const stateLabels = {
                    up: systemLabels.containerUp,
                    stopped: systemLabels.containerStopped,
                    unhealthy: systemLabels.containerUnhealthy,
                    unknown: systemLabels.containerUnknown
                };
                const stateClass = state === "up" ? "active" :
                    state === "unhealthy" || state === "stopped"
                        ? "failed"
                        : "";
                appendCell(
                    row,
                    stateLabels[state] || systemLabels.containerUnknown,
                    stateClass ? `monitor-state-${stateClass}` : ""
                );
                containerBody.appendChild(row);
            }
        }
    }

    function renderSecurityMonitor(entry) {
        const events = entry && entry.system && entry.system.security_events;
        const statusNode = document.getElementById("security-monitor-status");
        const alert = document.getElementById("resource-alert");
        const loginBody = document.getElementById("security-login-body");
        const bootBody = document.getElementById("security-boot-body");
        const latest = entry && entry.latest;
        const cpu = latest ? numberOrNull(latest.cpu_percent) : null;
        const memory = latest ? numberOrNull(latest.memory_percent) : null;
        const fresh = entry && !entry.telemetry_stale;
        const disk = latest ? numberOrNull(latest.disk_percent) : null;
        const highCpu = fresh && cpu !== null &&
            cpu >= dashboardSettings.thresholds.cpu;
        const highMemory = fresh && memory !== null &&
            memory >= dashboardSettings.thresholds.memory;
        const highDisk = fresh && disk !== null &&
            disk >= dashboardSettings.thresholds.disk;

        alert.classList.toggle("is-high", highCpu || highMemory || highDisk);
        if (highCpu || highMemory || highDisk) {
            const levels = [];
            if (highCpu) levels.push(`${systemLabels.cpuLabel} ${formatPercent(cpu)} (≥ ${dashboardSettings.thresholds.cpu}%)`);
            if (highMemory) levels.push(`${systemLabels.memoryLabel} ${formatPercent(memory)} (≥ ${dashboardSettings.thresholds.memory}%)`);
            if (highDisk) levels.push(`${systemLabels.disk} ${formatPercent(disk)} (≥ ${dashboardSettings.thresholds.disk}%)`);
            alert.textContent = `${systemLabels.resourceHigh} (${levels.join(", ")})`;
        } else if (entry && latest && !entry.telemetry_stale) {
            alert.textContent = systemLabels.resourceOk;
        } else {
            alert.textContent = "";
        }

        if (!events) {
            statusNode.textContent = entry
                ? (entry.system ? systemLabels.securityNoData : systemLabels.noData)
                : labels.noClients;
            for (const id of [
                "security-ssh-failures", "security-ssh-last",
                "security-journal-errors", "security-journal-warnings",
            ]) setSystemValue(id, "—");
            renderTableMessage(loginBody, systemLabels.securityNoData, 2);
            renderTableMessage(bootBody, systemLabels.securityNoData, 2);
            return;
        }

        const unavailable = [];
        setSystemValue(
            "security-ssh-failures",
            events.ssh_available
                ? `${events.ssh_failed_24h}${events.ssh_failed_24h === 500 ? "+" : ""}`
                : "—"
        );
        setSystemValue(
            "security-ssh-last",
            events.ssh_available && events.ssh_last_failed_at
                ? localizedDate(events.ssh_last_failed_at)
                : "—"
        );
        setSystemValue(
            "security-journal-errors",
            events.journal_available
                ? `${events.journal_errors_1h}${events.journal_errors_1h === 500 ? "+" : ""}`
                : "—"
        );
        setSystemValue(
            "security-journal-warnings",
            events.journal_available
                ? `${events.journal_warnings_1h}${events.journal_warnings_1h === 500 ? "+" : ""}`
                : "—"
        );
        if (!events.journal_available) unavailable.push(systemLabels.journalUnavailable);
        else if (!events.ssh_available) unavailable.push(systemLabels.sshUnavailable);
        if (!events.login_history_available) unavailable.push(systemLabels.loginUnavailable);
        if (!events.boot_history_available) unavailable.push(systemLabels.bootUnavailable);
        statusNode.textContent = unavailable.join(" ");

        loginBody.replaceChildren();
        if (!events.login_history_available) {
            renderTableMessage(loginBody, systemLabels.loginUnavailable, 2);
        } else if (!events.login_events.length) {
            renderTableMessage(loginBody, systemLabels.noLoginEvents, 2);
        } else {
            for (const event of events.login_events.slice().reverse()) {
                const row = document.createElement("tr");
                appendCell(row, localizedDate(event.timestamp));
                appendCell(
                    row,
                    event.action === "login"
                        ? systemLabels.loginLabel
                        : systemLabels.logoutLabel
                );
                loginBody.appendChild(row);
            }
        }

        bootBody.replaceChildren();
        if (!events.boot_history_available) {
            renderTableMessage(bootBody, systemLabels.bootUnavailable, 2);
        } else if (!events.boot_history.length) {
            renderTableMessage(bootBody, systemLabels.noBootHistory, 2);
        } else {
            for (const boot of events.boot_history.slice().reverse()) {
                const row = document.createElement("tr");
                appendCell(row, localizedDate(boot.started_at));
                appendCell(row, localizedDate(boot.ended_at));
                bootBody.appendChild(row);
            }
        }
    }

    function renderOptionalIntegrations(system) {
        const services = system && system.services && system.services.items || [];
        const integrationSpecs = [
            {
                id: "wazuh",
                rowId: "wazuh-status-row",
                valueId: "wazuh-status",
                match: /^(wazuh-agent|wazuh-manager|wazuh)$/i
            },
            {
                id: "suricata",
                rowId: "suricata-status-row",
                valueId: "suricata-status",
                match: /^(suricata|suricata-update)$/i
            }
        ];
        let missing = false;
        for (const spec of integrationSpecs) {
            const row = document.getElementById(spec.rowId);
            row.hidden = !dashboardSettings.integrations[spec.id];
            if (!dashboardSettings.integrations[spec.id]) continue;
            const matches = services.filter(item =>
                spec.match.test(item.name.replace(/\.service$/, ""))
            );
            if (!matches.length) {
                setSystemValue(spec.valueId, dashboardLabels.notConfigured);
                missing = true;
                continue;
            }
            setSystemValue(
                spec.valueId,
                matches.map(item =>
                    `${item.name}: ${item.state === "active" || item.state === "running"
                        ? dashboardLabels.active
                        : dashboardLabels.inactive}`
                ).join(" · ")
            );
        }
        document.getElementById("integration-monitor-help").hidden =
            !missing;
    }

    function renderSystemMonitor() {
        const entry = fleet.find(
            item => String(item.client_id) === clientSelect.value
        );
        const system = entry && entry.system;
        if (!system) {
            systemStatus.textContent = entry
                ? systemLabels.noData
                : labels.noClients;
            for (const id of [
                "system-cpu", "system-memory", "system-load", "system-disk",
                "system-uptime", "system-os", "system-kernel",
                "system-temperatures", "system-fans", "system-dns",
                "system-gateway", "system-internet",
            ]) {
                setSystemValue(id, "—");
            }
            renderSystemTables(entry);
            renderSecurityMonitor(entry);
            renderOptionalIntegrations(null);
            return;
        }

        systemStatus.textContent =
            entry.system_age_seconds === null ||
            entry.system_age_seconds > 120
                ? systemLabels.stale
                : "";

        const latest = entry.latest;
        setSystemValue("system-cpu", latest
            ? formatPercent(numberOrNull(latest.cpu_percent))
            : "—");
        setSystemValue("system-memory", latest
            ? `${formatPercent(numberOrNull(latest.memory_percent))} · ${formatBytes(
                latest.memory_total_bytes - latest.memory_available_bytes
            )} / ${formatBytes(latest.memory_total_bytes)}`
            : "—");
        setSystemValue("system-load", Array.isArray(system.load_average)
            ? system.load_average.map(value => Number(value).toFixed(2)).join(" · ")
            : "—");
        setSystemValue("system-disk", system.disk
            ? `${formatBytes(system.disk.used_bytes)} / ${formatBytes(system.disk.total_bytes)} · ${systemLabels.free} ${formatBytes(system.disk.free_bytes)}`
            : "—");
        setSystemValue("system-uptime", formatUptime(system.uptime_seconds));
        setSystemValue("system-os", system.os);
        setSystemValue("system-kernel", system.kernel);
        setSystemValue("system-temperatures", system.temperatures.length
            ? system.temperatures
                .map(item => `${item.name} ${Number(item.celsius).toFixed(1)} °C`)
                .join(" · ")
            : systemLabels.noSensors);
        setSystemValue("system-fans", system.fans.length
            ? system.fans.map(item => `${item.name} ${item.rpm} rpm`).join(" · ")
            : systemLabels.noSensors);

        const dnsServers = system.dns_servers.length
            ? system.dns_servers.join(", ")
            : systemLabels.unknown;
        setSystemValue(
            "system-dns",
            `${dnsServers} · ${reachabilityText(system.dns_reachable)}`
        );
        setSystemValue(
            "system-gateway",
            `${system.gateway || systemLabels.unknown} · ${reachabilityText(system.gateway_reachable)}`
        );
        setSystemValue(
            "system-internet",
            reachabilityText(system.internet_reachable)
        );
        renderSystemTables(entry);
        renderSecurityMonitor(entry);
        renderOptionalIntegrations(system);
    }

    function renderFleet() {
        const term = fleetSearch.value.trim().toLowerCase();
        const rows = fleet
            .map(entry => ({ entry, metrics: clientMetrics(entry) }))
            .filter(({ entry, metrics }) =>
                matchesFilter(entry, metrics) &&
                (!term || metrics.hostname.includes(term)));

        // Missing values always sort last so they never look like the best or worst client.
        rows.sort((a, b) => {
            const left = a.metrics[sortKey];
            const right = b.metrics[sortKey];
            if (left === null && right === null) return 0;
            if (left === null) return 1;
            if (right === null) return -1;
            if (left < right) return -sortDirection;
            if (left > right) return sortDirection;
            return a.metrics.hostname.localeCompare(b.metrics.hostname);
        });

        fleetBody.replaceChildren();
        if (!rows.length) {
            const row = document.createElement("tr");
            const cell = appendCell(row, fleet.length ? labels.noMatch : labels.noClients);
            cell.colSpan = 7;
            fleetBody.appendChild(row);
        }

        for (const { entry, metrics } of rows) {
            const row = document.createElement("tr");
            row.className = "fleet-row";
            row.classList.toggle("fleet-selected", String(entry.client_id) === clientSelect.value);

            const nameCell = document.createElement("td");
            const select = document.createElement("button");
            select.type = "button";
            select.className = "fleet-client";
            select.textContent = entry.hostname;
            select.addEventListener("click", () => {
                clientSelect.value = String(entry.client_id);
                renderFleet();
                safeRefreshDetails();
            });
            nameCell.appendChild(select);
            row.appendChild(nameCell);

            appendCell(row, labels[entry.status] || labels.unknown, `fleet-status fleet-status-${entry.status}`);
            appendCell(row, formatPercent(metrics.cpu), metrics.cpu >= 90 ? "fleet-hot" : "");
            appendCell(row, formatPercent(metrics.memory), metrics.memory >= 90 ? "fleet-hot" : "");
            appendCell(row, formatRate(metrics.rx));
            appendCell(row, formatRate(metrics.tx));
            appendCell(
                row,
                entry.telemetry_stale && metrics.age !== null
                    ? `${formatAge(metrics.age)} · ${labels.stale}`
                    : formatAge(metrics.age),
                entry.telemetry_stale ? "fleet-hot" : ""
            );
            fleetBody.appendChild(row);
        }

        for (const header of document.querySelectorAll(".fleet-table th")) {
            const button = header.querySelector(".fleet-sort");
            header.setAttribute(
                "aria-sort",
                button && button.dataset.sort === sortKey
                    ? (sortDirection === 1 ? "ascending" : "descending")
                    : "none"
            );
        }
    }

    function syncClientOptions() {
        const ids = fleet.map(entry => entry.client_id).join(",");
        if (ids === knownClientIds) return;
        knownClientIds = ids;

        const previous = clientSelect.value;
        clientSelect.replaceChildren();
        for (const entry of fleet) {
            const option = document.createElement("option");
            option.value = String(entry.client_id);
            option.textContent = entry.hostname;
            clientSelect.appendChild(option);
        }
        if (fleet.some(entry => String(entry.client_id) === previous)) {
            clientSelect.value = previous;
        }
    }

    async function fetchJson(url) {
        const response = await fetch(url, {
            credentials: "same-origin",
            headers: { Accept: "application/json" },
            cache: "no-store"
        });
        if (!response.ok) throw new Error("Telemetry API unavailable");
        return response.json();
    }

    async function refreshFleet() {
        const result = await fetchJson("/api/telemetry/overview");
        fleet = Array.isArray(result.clients) ? result.clients : [];
        syncClientOptions();
        renderFleet();
        renderSystemMonitor();
    }

    async function refreshDetails() {
        const clientId = clientSelect.value;
        if (!clientId) {
            renderDetails([]);
            setStatus(labels.noClients);
            return;
        }

        const sequence = ++requestSequence;
        const hours = rangeSelect.value;
        const baseUrl =
            `/api/clients/${encodeURIComponent(clientId)}/telemetry`;
        const [result, eventResult] = await Promise.all([
            fetchJson(`${baseUrl}?hours=${encodeURIComponent(hours)}`),
            fetchJson(`${baseUrl}/events?hours=${encodeURIComponent(hours)}`)
        ]);
        if (sequence !== requestSequence) return;

        const samples = Array.isArray(result.samples) ? result.samples : [];
        const events = Array.isArray(eventResult.events) ? eventResult.events : [];
        renderDetails(samples);
        renderTelemetryEvents(events);
        configureExportButtons();
        setStatus(samples.length ? "" : labels.noSamples);
    }

    async function refresh() {
        try {
            await refreshFleet();
            await refreshDetails();
        } catch {
            setStatus(labels.loadError, true);
            systemStatus.textContent = labels.loadError;
        }
    }

    function safeRefreshDetails() {
        refreshDetails().catch(() => setStatus(labels.loadError, true));
    }

    clientSelect.addEventListener("change", () => {
        renderFleet();
        renderSystemMonitor();
        safeRefreshDetails();
    });
    rangeSelect.addEventListener("change", safeRefreshDetails);
    viewSelect.addEventListener("change", () => {
        storeView(viewSelect.value);
        safeRefreshDetails();
    });
    fleetFilter.addEventListener("change", renderFleet);
    fleetSearch.addEventListener("input", renderFleet);

    for (const button of document.querySelectorAll(".fleet-sort")) {
        button.addEventListener("click", () => {
            const key = button.dataset.sort;
            sortDirection = key === sortKey ? -sortDirection : (key === "cpu" || key === "memory" || key === "rx" || key === "tx" ? -1 : 1);
            sortKey = key;
            renderFleet();
        });
    }

    viewSelect.value = readStoredView();
    initializeDashboardCustomizer();
    setStatus(labels.loading);
    loadDashboardSettings().finally(() => {
        renderFleet();
        renderSystemMonitor();
        refresh();
        timer = window.setInterval(refresh, 5000);
    });

    window.addEventListener("pagehide", () => {
        if (timer !== null) window.clearInterval(timer);
    });
})();
