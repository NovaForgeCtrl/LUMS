(() => {
    "use strict";

    const root = document.getElementById("infrastructure-topology");
    if (!root) return;

    const apiUrl = root.dataset.apiUrl;
    const nodesUrl = root.dataset.nodesUrl;
    const relationsUrl = root.dataset.relationsUrl;
    const canEdit = root.dataset.canEdit === "true";
    const csrfToken = root.dataset.csrfToken;
    const status = document.getElementById("topology-status");
    const inventoryBody = document.getElementById("topology-inventory-body");
    const relationsBody = document.getElementById("topology-relations-body");
    const map = document.getElementById("topology-map");
    const messages = {
        loading: "Loading infrastructure data…",
        loadError: "Infrastructure data could not be loaded.",
        saveError: "The change could not be saved.",
        saved: "Infrastructure data updated.",
        empty: "No infrastructure items are registered yet.",
        emptyRelations: "No relationships have been recorded yet.",
        clients: "LUMS client",
        manual: "Managed item",
        online: "Online",
        offline: "Offline",
        unknown: "Unknown",
        disabled: "Disabled",
        client: "Client",
        sourceClient: "Automatically imported",
        sourceManual: "Manually managed",
        name: "Name",
        nodeType: "Type",
        hostname: "Hostname",
        ip: "IP address",
        role: "Role",
        location: "Location",
        actions: "Actions",
        edit: "Edit",
        delete: "Delete",
        confirmDelete: "Delete this infrastructure item and its relationships?",
        confirmDeleteRelation: "Delete this relationship?",
        addNode: "Add infrastructure item",
        updateNode: "Save changes",
        addItem: "Add item",
        cancel: "Cancel",
        addRelation: "Add relationship",
        relationDuplicate: "This relationship already exists.",
        invalidIp: "Enter a valid IPv4 or IPv6 address.",
        networkDevice: "Network device",
        server: "Server",
        vm: "Virtual machine",
        container: "Container",
        service: "Service",
        storage: "Storage",
        dependsOn: "Depends on",
        hosts: "Hosts",
        connectsTo: "Connects to",
        runsOn: "Runs on",
        central: "Shared dependency",
        emptyMap: "Add systems and relationships to build the topology.",
        httpError: "Request failed (HTTP {status})."
    };
    const t = key => window.lumsT && window.lumsT[key] || key;
    const labels = Object.fromEntries(
        Object.entries(messages).map(([key, value]) => [key, t(value)])
    );
    const typeLabels = {
        client: labels.client,
        server: labels.server,
        vm: labels.vm,
        container: labels.container,
        network_device: labels.networkDevice,
        service: labels.service,
        storage: labels.storage
    };
    const relationLabels = {
        depends_on: labels.dependsOn,
        hosts: labels.hosts,
        connects_to: labels.connectsTo,
        runs_on: labels.runsOn
    };
    let topology = { nodes: [], relations: [] };

    function setStatus(message, isError = false) {
        status.textContent = message;
        status.classList.toggle("is-error", isError);
    }

    async function request(url, method = "GET", body = null) {
        const options = {
            method,
            credentials: "same-origin",
            cache: "no-store",
            headers: { Accept: "application/json" }
        };
        if (body !== null) {
            options.headers["Content-Type"] = "application/json";
            options.headers["X-CSRF-Token"] = csrfToken;
            options.body = JSON.stringify(body);
        }
        const response = await fetch(url, options);
        let data = null;
        try {
            data = await response.json();
        } catch (error) {
            if (response.ok) throw error;
        }
        if (!response.ok) {
            if (data && data.error === "relation_exists") {
                throw new Error(labels.relationDuplicate);
            }
            if (data && data.error === "invalid_ip_address") {
                throw new Error(labels.invalidIp);
            }
            throw new Error(labels.httpError.replace("{status}", response.status));
        }
        return data;
    }

    function entityKey(reference) {
        return `${reference.type}:${reference.id}`;
    }

    function displayAddress(node) {
        return [node.hostname, node.ip_address].filter(Boolean).join(" · ") || "—";
    }

    function displayRoleLocation(node) {
        return [node.role, node.location].filter(Boolean).join(" · ") || "—";
    }

    function nodeName(reference) {
        const node = topology.nodes.find(item => item.id === entityKey(reference));
        return node ? node.name : "—";
    }

    function renderSummary() {
        document.getElementById("topology-client-count").textContent =
            topology.nodes.filter(node => node.entity_type === "client").length;
        document.getElementById("topology-node-count").textContent =
            topology.nodes.filter(node => node.entity_type === "node").length;
        document.getElementById("topology-relation-count").textContent =
            topology.relations.length;

        const dependencyCounts = new Map();
        for (const relation of topology.relations) {
            if (relation.relation_type !== "depends_on") continue;
            const key = entityKey(relation.target);
            dependencyCounts.set(key, (dependencyCounts.get(key) || 0) + 1);
        }
        const sharedCount = Array.from(dependencyCounts.values())
            .filter(count => count >= 2).length;
        document.getElementById("topology-central-count").textContent = sharedCount;
        topology.nodes.forEach(node => {
            node.central_dependency = (dependencyCounts.get(node.id) || 0) >= 2;
        });
    }

    function svgElement(name, attributes = {}) {
        const element = document.createElementNS("http://www.w3.org/2000/svg", name);
        for (const [key, value] of Object.entries(attributes)) {
            element.setAttribute(key, String(value));
        }
        return element;
    }

    function groupFor(node) {
        if (node.node_type === "network_device") return 0;
        if (node.node_type === "server" || node.node_type === "client") return 1;
        if (node.node_type === "vm" || node.node_type === "container") return 2;
        return 3;
    }

    function renderMap() {
        const title = map.querySelector("#topology-map-title");
        const description = map.querySelector("#topology-map-description");
        map.replaceChildren(title, description);
        map.setAttribute("viewBox", "0 0 1000 280");
        if (!topology.nodes.length) {
            const empty = svgElement("text", {
                x: 500, y: 145, "text-anchor": "middle", class: "topology-map-empty"
            });
            empty.textContent = labels.emptyMap;
            map.appendChild(empty);
            return;
        }

        const grouped = [[], [], [], []];
        topology.nodes.forEach(node => grouped[groupFor(node)].push(node));
        const positions = new Map();
        const nodeWidth = 210;
        const nodeHeight = 78;
        let rows = 0;
        grouped.forEach((nodes, groupIndex) => {
            rows = Math.max(rows, nodes.length);
            nodes.forEach((node, rowIndex) => {
                positions.set(node.id, {
                    x: 20 + groupIndex * 245,
                    y: 24 + rowIndex * 112,
                    width: nodeWidth,
                    height: nodeHeight
                });
            });
        });
        const height = Math.max(240, 48 + rows * 112);
        map.setAttribute("viewBox", `0 0 1000 ${height}`);

        const defs = svgElement("defs");
        const marker = svgElement("marker", {
            id: "topology-arrow",
            markerWidth: 8,
            markerHeight: 8,
            refX: 7,
            refY: 4,
            orient: "auto",
            markerUnits: "strokeWidth"
        });
        marker.appendChild(svgElement("path", { d: "M0,0 L8,4 L0,8 z" }));
        defs.appendChild(marker);
        map.appendChild(defs);

        for (const relation of topology.relations) {
            const source = positions.get(entityKey(relation.source));
            const target = positions.get(entityKey(relation.target));
            if (!source || !target) continue;
            const line = svgElement("line", {
                x1: source.x + source.width / 2,
                y1: source.y + source.height / 2,
                x2: target.x + target.width / 2,
                y2: target.y + target.height / 2,
                class: "topology-edge",
                "marker-end": "url(#topology-arrow)"
            });
            const edgeTitle = svgElement("title");
            edgeTitle.textContent =
                `${nodeName(relation.source)} ${relationLabels[relation.relation_type] || relation.relation_type} ${nodeName(relation.target)}`;
            line.appendChild(edgeTitle);
            map.appendChild(line);
        }

        for (const node of topology.nodes) {
            const position = positions.get(node.id);
            const group = svgElement("g", {
                class: `topology-node${node.central_dependency ? " is-central" : ""}`
            });
            group.appendChild(svgElement("rect", {
                x: position.x,
                y: position.y,
                width: position.width,
                height: position.height,
                rx: 8
            }));
            const type = svgElement("text", {
                x: position.x + 12, y: position.y + 19, class: "topology-node-type"
            });
            type.textContent = typeLabels[node.node_type] || node.node_type;
            group.appendChild(type);
            const name = svgElement("text", {
                x: position.x + 12, y: position.y + 42, class: "topology-node-name"
            });
            name.textContent = node.name.length > 25
                ? `${node.name.slice(0, 22)}…`
                : node.name;
            group.appendChild(name);
            const address = svgElement("text", {
                x: position.x + 12, y: position.y + 62, class: "topology-node-address"
            });
            address.textContent = (node.ip_address || node.hostname || "—").slice(0, 28);
            group.appendChild(address);
            const cardTitle = svgElement("title");
            cardTitle.textContent = [
                node.name,
                typeLabels[node.node_type] || node.node_type,
                displayAddress(node),
                node.central_dependency ? labels.central : ""
            ].filter(Boolean).join(" · ");
            group.appendChild(cardTitle);
            map.appendChild(group);
        }
    }

    function addActionCell(row, action, id, text) {
        const cell = document.createElement("td");
        const button = document.createElement("button");
        button.type = "button";
        button.dataset.action = action;
        button.dataset.id = String(id);
        button.textContent = text;
        cell.appendChild(button);
        row.appendChild(cell);
    }

    function renderInventory() {
        inventoryBody.replaceChildren();
        if (!topology.nodes.length) {
            const row = document.createElement("tr");
            const cell = document.createElement("td");
            cell.colSpan = canEdit ? 7 : 6;
            cell.textContent = labels.empty;
            row.appendChild(cell);
            inventoryBody.appendChild(row);
        }
        for (const node of topology.nodes) {
            const row = document.createElement("tr");
            if (node.central_dependency) row.classList.add("is-central");
            const name = document.createElement("td");
            name.textContent = node.central_dependency
                ? `${node.name} · ${labels.central}`
                : node.name;
            row.appendChild(name);
            const type = document.createElement("td");
            type.textContent = typeLabels[node.node_type] || node.node_type;
            row.appendChild(type);
            const address = document.createElement("td");
            address.textContent = displayAddress(node);
            row.appendChild(address);
            const role = document.createElement("td");
            role.textContent = displayRoleLocation(node);
            row.appendChild(role);
            const state = document.createElement("td");
            state.textContent = labels[node.status] || labels.unknown;
            row.appendChild(state);
            const source = document.createElement("td");
            source.textContent = node.entity_type === "client"
                ? labels.sourceClient
                : labels.sourceManual;
            row.appendChild(source);
            if (canEdit) {
                if (node.editable) {
                    addActionCell(row, "edit-node", node.entity_id, labels.edit);
                    const actionCell = row.lastElementChild;
                    const remove = document.createElement("button");
                    remove.type = "button";
                    remove.dataset.action = "delete-node";
                    remove.dataset.id = String(node.entity_id);
                    remove.textContent = labels.delete;
                    actionCell.appendChild(remove);
                } else {
                    const cell = document.createElement("td");
                    cell.textContent = "—";
                    row.appendChild(cell);
                }
            }
            inventoryBody.appendChild(row);
        }
    }

    function fillEndpointSelect(select) {
        const selected = select.value;
        select.replaceChildren();
        for (const node of topology.nodes) {
            const option = document.createElement("option");
            option.value = node.id;
            option.textContent =
                `${node.name} · ${typeLabels[node.node_type] || node.node_type}`;
            select.appendChild(option);
        }
        if (Array.from(select.options).some(option => option.value === selected)) {
            select.value = selected;
        }
    }

    function renderRelations() {
        relationsBody.replaceChildren();
        if (!topology.relations.length) {
            const row = document.createElement("tr");
            const cell = document.createElement("td");
            cell.colSpan = canEdit ? 5 : 4;
            cell.textContent = labels.emptyRelations;
            row.appendChild(cell);
            relationsBody.appendChild(row);
        }
        for (const relation of topology.relations) {
            const row = document.createElement("tr");
            for (const text of [
                nodeName(relation.source),
                relationLabels[relation.relation_type] || relation.relation_type,
                nodeName(relation.target),
                relation.details || "—"
            ]) {
                const cell = document.createElement("td");
                cell.textContent = text;
                row.appendChild(cell);
            }
            if (canEdit) {
                addActionCell(row, "delete-relation", relation.id, labels.delete);
            }
            relationsBody.appendChild(row);
        }
        if (canEdit) {
            fillEndpointSelect(document.getElementById("topology-relation-source"));
            fillEndpointSelect(document.getElementById("topology-relation-target"));
        }
    }

    function render() {
        renderSummary();
        renderMap();
        renderInventory();
        renderRelations();
    }

    async function loadTopology(showLoading = true) {
        if (showLoading) setStatus(labels.loading);
        try {
            const response = await request(apiUrl);
            if (!Array.isArray(response.nodes) || !Array.isArray(response.relations)) {
                throw new Error(labels.loadError);
            }
            topology = response;
            render();
            setStatus(labels.saved);
        } catch (error) {
            setStatus(error.message || labels.loadError, true);
        }
    }

    function resetNodeForm() {
        const form = document.getElementById("topology-node-form");
        form.reset();
        document.getElementById("topology-node-id").value = "";
        document.getElementById("topology-node-form-heading").textContent =
            labels.addNode;
        document.getElementById("topology-node-submit").textContent =
            labels.addItem;
        document.getElementById("topology-node-cancel").hidden = true;
    }

    function startEditingNode(nodeId) {
        const node = topology.nodes.find(
            item => item.entity_type === "node" &&
                String(item.entity_id) === String(nodeId)
        );
        if (!node) return;
        document.getElementById("topology-node-id").value = node.entity_id;
        document.getElementById("topology-node-name").value = node.name;
        document.getElementById("topology-node-type").value = node.node_type;
        document.getElementById("topology-node-hostname").value = node.hostname;
        document.getElementById("topology-node-ip").value = node.ip_address;
        document.getElementById("topology-node-role").value = node.role;
        document.getElementById("topology-node-location").value = node.location;
        document.getElementById("topology-node-notes").value = node.notes || "";
        document.getElementById("topology-node-form-heading").textContent =
            `${labels.edit}: ${node.name}`;
        document.getElementById("topology-node-submit").textContent =
            labels.updateNode;
        document.getElementById("topology-node-cancel").hidden = false;
        document.getElementById("topology-node-name").focus();
    }

    if (canEdit) {
        const nodeForm = document.getElementById("topology-node-form");
        nodeForm.addEventListener("submit", async event => {
            event.preventDefault();
            const name = document.getElementById("topology-node-name").value.trim();
            const ip = document.getElementById("topology-node-ip").value.trim();
            const payload = {
                name,
                node_type: document.getElementById("topology-node-type").value,
                hostname: document.getElementById("topology-node-hostname").value,
                ip_address: ip,
                role: document.getElementById("topology-node-role").value,
                location: document.getElementById("topology-node-location").value,
                notes: document.getElementById("topology-node-notes").value
            };
            const nodeId = document.getElementById("topology-node-id").value;
            try {
                await request(
                    nodeId ? `${nodesUrl}/${encodeURIComponent(nodeId)}` : nodesUrl,
                    nodeId ? "PUT" : "POST",
                    payload
                );
                resetNodeForm();
                await loadTopology(false);
            } catch (error) {
                setStatus(error.message || labels.saveError, true);
            }
        });

        document.getElementById("topology-node-cancel").addEventListener(
            "click", resetNodeForm
        );

        const relationForm = document.getElementById("topology-relation-form");
        relationForm.addEventListener("submit", async event => {
            event.preventDefault();
            const source = document.getElementById("topology-relation-source").value;
            const target = document.getElementById("topology-relation-target").value;
            if (!source || !target || source === target) {
                setStatus(labels.saveError, true);
                return;
            }
            const [sourceType, sourceId] = source.split(":");
            const [targetType, targetId] = target.split(":");
            try {
                await request(relationsUrl, "POST", {
                    source_type: sourceType,
                    source_id: Number(sourceId),
                    target_type: targetType,
                    target_id: Number(targetId),
                    relation_type: document.getElementById("topology-relation-type").value,
                    details: document.getElementById("topology-relation-details").value
                });
                document.getElementById("topology-relation-details").value = "";
                await loadTopology(false);
            } catch (error) {
                setStatus(error.message || labels.saveError, true);
            }
        });

        root.addEventListener("click", async event => {
            const button = event.target.closest("button[data-action]");
            if (!button) return;
            const id = encodeURIComponent(button.dataset.id);
            if (button.dataset.action === "edit-node") {
                startEditingNode(id);
                return;
            }
            const isNode = button.dataset.action === "delete-node";
            if (!window.confirm(
                isNode ? labels.confirmDelete : labels.confirmDeleteRelation
            )) return;
            const url = isNode
                ? `${nodesUrl}/${id}`
                : `${relationsUrl}/${id}`;
            try {
                await request(url, "DELETE", {});
                await loadTopology(false);
            } catch (error) {
                setStatus(error.message || labels.saveError, true);
            }
        });
    }

    document.getElementById("topology-refresh").addEventListener(
        "click", () => loadTopology()
    );
    loadTopology();
})();
