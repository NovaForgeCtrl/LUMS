(() => {
    "use strict";

    const root = document.getElementById("telemetry-dashboard");
    if (!root) return;

    const clientSelect = document.getElementById("telemetry-client");
    const rangeSelect = document.getElementById("telemetry-range");
    const status = document.getElementById("telemetry-status");
    const lastUpdated = document.getElementById("telemetry-updated");
    const cpuValue = document.getElementById("telemetry-cpu-value");
    const memoryValue = document.getElementById("telemetry-memory-value");
    const cpuChart = document.getElementById("telemetry-cpu-chart");
    const memoryChart = document.getElementById("telemetry-memory-chart");

    const labels = {
        loading: root.dataset.loading,
        noClients: root.dataset.noClients,
        noSamples: root.dataset.noSamples,
        loadError: root.dataset.loadError,
        updated: root.dataset.updated,
        cpu: root.dataset.cpu,
        memory: root.dataset.memory
    };

    let requestSequence = 0;
    let timer = null;

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

    function drawChart(svg, samples, key, label) {
        svg.replaceChildren();

        const width = 640;
        const height = 220;
        const left = 42;
        const right = 12;
        const top = 14;
        const bottom = 30;
        const plotWidth = width - left - right;
        const plotHeight = height - top - bottom;

        svg.setAttribute("viewBox", `0 0 ${width} ${height}`);
        svg.setAttribute("role", "img");
        svg.setAttribute("aria-label", label);

        for (const percent of [0, 25, 50, 75, 100]) {
            const y = top + plotHeight * (1 - percent / 100);
            svg.appendChild(svgElement("line", {
                x1: left, y1: y, x2: width - right, y2: y,
                class: "telemetry-gridline"
            }));

            const text = svgElement("text", {
                x: left - 8, y: y + 4,
                "text-anchor": "end",
                class: "telemetry-axis-label"
            });
            text.textContent = `${percent}%`;
            svg.appendChild(text);
        }

        if (!samples.length) {
            const text = svgElement("text", {
                x: width / 2,
                y: height / 2,
                "text-anchor": "middle",
                class: "telemetry-empty-label"
            });
            text.textContent = labels.noSamples;
            svg.appendChild(text);
            return;
        }

        const values = samples.map(sample => ({
            time: Date.parse(sample.recorded_at),
            value: Number(sample[key])
        })).filter(point =>
            Number.isFinite(point.time) &&
            Number.isFinite(point.value) &&
            point.value >= 0 &&
            point.value <= 100
        );

        if (!values.length) return;

        const minTime = values[0].time;
        const maxTime = values[values.length - 1].time;
        const span = Math.max(1, maxTime - minTime);

        const points = values.map(point => {
            const x = left + ((point.time - minTime) / span) * plotWidth;
            const y = top + (1 - point.value / 100) * plotHeight;
            return `${x},${y}`;
        }).join(" ");

        svg.appendChild(svgElement("polyline", {
            points,
            class: "telemetry-line"
        }));

        const latest = values[values.length - 1];
        const latestX = left + ((latest.time - minTime) / span) * plotWidth;
        const latestY = top + (1 - latest.value / 100) * plotHeight;

        svg.appendChild(svgElement("circle", {
            cx: latestX, cy: latestY, r: 4,
            class: "telemetry-point"
        }));

        const startLabel = svgElement("text", {
            x: left, y: height - 8,
            "text-anchor": "start",
            class: "telemetry-axis-label"
        });
        startLabel.textContent = new Date(minTime).toLocaleTimeString();
        svg.appendChild(startLabel);

        const endLabel = svgElement("text", {
            x: width - right, y: height - 8,
            "text-anchor": "end",
            class: "telemetry-axis-label"
        });
        endLabel.textContent = new Date(maxTime).toLocaleTimeString();
        svg.appendChild(endLabel);
    }

    async function loadClients() {
        setStatus(labels.loading);

        try {
            const response = await fetch("/api/clients", {
                credentials: "same-origin",
                headers: { Accept: "application/json" }
            });
            if (!response.ok) throw new Error("Client API unavailable");

            const clients = await response.json();
            clientSelect.replaceChildren();

            for (const client of clients) {
                const option = document.createElement("option");
                option.value = String(client.id);
                option.textContent = client.hostname;
                clientSelect.appendChild(option);
            }

            if (!clients.length) {
                setStatus(labels.noClients);
                drawChart(cpuChart, [], "cpu_percent", labels.cpu);
                drawChart(memoryChart, [], "memory_percent", labels.memory);
                cpuValue.textContent = "—";
                memoryValue.textContent = "—";
                return;
            }

            await refresh();
        } catch {
            setStatus(labels.loadError, true);
        }
    }

    async function refresh() {
        const clientId = clientSelect.value;
        if (!clientId) return;

        const sequence = ++requestSequence;
        const hours = rangeSelect.value;

        try {
            const response = await fetch(
                `/api/clients/${encodeURIComponent(clientId)}/telemetry?hours=${encodeURIComponent(hours)}`,
                {
                    credentials: "same-origin",
                    headers: { Accept: "application/json" },
                    cache: "no-store"
                }
            );

            if (!response.ok) throw new Error("Telemetry API unavailable");

            const result = await response.json();
            if (sequence !== requestSequence) return;

            const samples = Array.isArray(result.samples) ? result.samples : [];
            drawChart(cpuChart, samples, "cpu_percent", labels.cpu);
            drawChart(memoryChart, samples, "memory_percent", labels.memory);

            if (samples.length) {
                const latest = samples[samples.length - 1];
                cpuValue.textContent = `${Number(latest.cpu_percent).toFixed(1)}%`;
                memoryValue.textContent = `${Number(latest.memory_percent).toFixed(1)}%`;
                lastUpdated.textContent =
                    `${labels.updated} ${new Date(latest.recorded_at).toLocaleString()}`;
                setStatus("");
            } else {
                cpuValue.textContent = "—";
                memoryValue.textContent = "—";
                lastUpdated.textContent = "";
                setStatus(labels.noSamples);
            }
        } catch {
            if (sequence === requestSequence) {
                setStatus(labels.loadError, true);
            }
        }
    }

    clientSelect.addEventListener("change", refresh);
    rangeSelect.addEventListener("change", refresh);

    loadClients();
    timer = window.setInterval(refresh, 5000);

    window.addEventListener("pagehide", () => {
        if (timer !== null) window.clearInterval(timer);
    });
})();
