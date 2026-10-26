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
    const networkChart = document.getElementById("telemetry-network-chart");
    const fleetBody = document.getElementById("fleet-body");
    const fleetFilter = document.getElementById("fleet-filter");
    const fleetSearch = document.getElementById("fleet-search");
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

    function drawPercentChart(svg, samples, key, label, view) {
        if (view === "donut") {
            drawDonut(svg, samples, key, label);
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
        drawTimeLabels(svg, minTime, maxTime);
    }

    function drawDonut(svg, samples, key, label) {
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
        const level = value >= 90 ? "critical" : value >= 75 ? "warning" : "normal";
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
        drawPercentChart(cpuChart, samples, "cpu_percent", labels.cpu, view);
        drawPercentChart(memoryChart, samples, "memory_percent", labels.memory, view);
        drawNetworkChart(samples, view);

        const latest = samples[samples.length - 1];
        if (!latest) {
            cpuValue.textContent = "—";
            memoryValue.textContent = "—";
            networkValue.textContent = "—";
            lastUpdated.textContent = "";
            return;
        }

        cpuValue.textContent = formatPercent(Number(latest.cpu_percent));
        memoryValue.textContent = formatPercent(Number(latest.memory_percent));
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
            (metrics.cpu ?? 0) >= 90 ||
            (metrics.memory ?? 0) >= 90;
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
        const result = await fetchJson(
            `/api/clients/${encodeURIComponent(clientId)}/telemetry?hours=${encodeURIComponent(hours)}`
        );
        if (sequence !== requestSequence) return;

        const samples = Array.isArray(result.samples) ? result.samples : [];
        renderDetails(samples);
        setStatus(samples.length ? "" : labels.noSamples);
    }

    async function refresh() {
        try {
            await refreshFleet();
            await refreshDetails();
        } catch {
            setStatus(labels.loadError, true);
        }
    }

    function safeRefreshDetails() {
        refreshDetails().catch(() => setStatus(labels.loadError, true));
    }

    clientSelect.addEventListener("change", () => {
        renderFleet();
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
    setStatus(labels.loading);
    refresh();
    timer = window.setInterval(refresh, 5000);

    window.addEventListener("pagehide", () => {
        if (timer !== null) window.clearInterval(timer);
    });
})();
