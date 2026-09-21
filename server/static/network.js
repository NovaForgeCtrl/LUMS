(() => {
    "use strict";

    let canvas = null;
    let context = null;
    let animationFrame = null;
    let resizeHandler = null;
    let running = false;

    const nodes = [];
    const packets = [];

    const NODE_COUNT = 32;
    const MAX_DISTANCE = 190;
    const PACKET_COUNT = 14;

    const COLORS = {
        node: "rgba(74, 222, 128, 0.65)",
        line: "rgba(74, 222, 128, 0.12)",
        packet: "rgba(96, 165, 250, 0.95)"
    };

    function createCanvas() {
        if (canvas) {
            return;
        }

        canvas = document.createElement("canvas");
        canvas.id = "lums-network-canvas";
        canvas.setAttribute("aria-hidden", "true");

        document.body.prepend(canvas);

        context = canvas.getContext("2d");

        resizeHandler = resizeCanvas;
        window.addEventListener("resize", resizeHandler);

        resizeCanvas();
        createNodes();
        createPackets();
    }

    function resizeCanvas() {
        if (!canvas) {
            return;
        }

        const pixelRatio = Math.min(
            window.devicePixelRatio || 1,
            2
        );

        canvas.width =
            window.innerWidth * pixelRatio;

        canvas.height =
            window.innerHeight * pixelRatio;

        canvas.style.width =
            `${window.innerWidth}px`;

        canvas.style.height =
            `${window.innerHeight}px`;

        context.setTransform(
            pixelRatio,
            0,
            0,
            pixelRatio,
            0,
            0
        );
    }

    function createNodes() {
        nodes.length = 0;

        for (let i = 0; i < NODE_COUNT; i++) {
            nodes.push({
                x: Math.random() * window.innerWidth,
                y: Math.random() * window.innerHeight,
                vx: (Math.random() - 0.5) * 0.22,
                vy: (Math.random() - 0.5) * 0.22,
                radius: 1.2 + Math.random() * 1.8
            });
        }
    }

    function createPackets() {
        packets.length = 0;

        for (let i = 0; i < PACKET_COUNT; i++) {
            packets.push({
                nodeIndex: Math.floor(
                    Math.random() * nodes.length
                ),
                targetIndex: null,
                progress: Math.random(),
                speed: 0.002 + Math.random() * 0.004
            });
        }
    }

    function chooseTarget(packet) {
        const source = nodes[packet.nodeIndex];

        if (!source) {
            return;
        }

        const possibleTargets = nodes
            .map((node, index) => {
                if (index === packet.nodeIndex) {
                    return null;
                }

                const distance = Math.hypot(
                    node.x - source.x,
                    node.y - source.y
                );

                return distance <= MAX_DISTANCE
                    ? index
                    : null;
            })
            .filter((index) => index !== null);

        if (possibleTargets.length === 0) {
            packet.targetIndex = null;
            return;
        }

        packet.targetIndex =
            possibleTargets[
                Math.floor(
                    Math.random() * possibleTargets.length
                )
            ];

        packet.progress = 0;
    }

    function update() {
        nodes.forEach((node) => {
            node.x += node.vx;
            node.y += node.vy;

            if (
                node.x < 0 ||
                node.x > window.innerWidth
            ) {
                node.vx *= -1;
            }

            if (
                node.y < 0 ||
                node.y > window.innerHeight
            ) {
                node.vy *= -1;
            }
        });

        packets.forEach((packet) => {
            if (packet.targetIndex === null) {
                chooseTarget(packet);
                return;
            }

            packet.progress += packet.speed;

            if (packet.progress >= 1) {
                packet.nodeIndex =
                    packet.targetIndex;

                packet.targetIndex = null;
                packet.progress = 0;
            }
        });
    }

    function draw() {
        if (!context) {
            return;
        }

        context.clearRect(
            0,
            0,
            window.innerWidth,
            window.innerHeight
        );

        nodes.forEach((source, sourceIndex) => {
            nodes.forEach((target, targetIndex) => {
                if (targetIndex <= sourceIndex) {
                    return;
                }

                const distance = Math.hypot(
                    target.x - source.x,
                    target.y - source.y
                );

                if (distance > MAX_DISTANCE) {
                    return;
                }

                const opacity =
                    (1 - distance / MAX_DISTANCE) * 0.18;

                context.beginPath();
                context.moveTo(source.x, source.y);
                context.lineTo(target.x, target.y);

                context.strokeStyle =
                    `rgba(74, 222, 128, ${opacity})`;

                context.lineWidth = 1;
                context.stroke();
            });
        });

        nodes.forEach((node) => {
            context.beginPath();

            context.arc(
                node.x,
                node.y,
                node.radius,
                0,
                Math.PI * 2
            );

            context.fillStyle = COLORS.node;
            context.shadowBlur = 8;
            context.shadowColor = COLORS.node;
            context.fill();
            context.shadowBlur = 0;
        });

        packets.forEach((packet) => {
            if (packet.targetIndex === null) {
                return;
            }

            const source = nodes[packet.nodeIndex];
            const target = nodes[packet.targetIndex];

            if (!source || !target) {
                return;
            }

            const x =
                source.x +
                (target.x - source.x) *
                packet.progress;

            const y =
                source.y +
                (target.y - source.y) *
                packet.progress;

            context.beginPath();

            context.arc(
                x,
                y,
                2.2,
                0,
                Math.PI * 2
            );

            context.fillStyle = COLORS.packet;
            context.shadowBlur = 12;
            context.shadowColor = COLORS.packet;
            context.fill();
            context.shadowBlur = 0;
        });
    }

    function animate() {
        if (!running) {
            return;
        }

        update();
        draw();

        animationFrame =
            window.requestAnimationFrame(animate);
    }

    function start() {
        if (
            running ||
            window.matchMedia(
                "(prefers-reduced-motion: reduce)"
            ).matches
        ) {
            return;
        }

        createCanvas();

        running = true;
        canvas.classList.add("active");

        animate();
    }

    function stop() {
        running = false;

        if (animationFrame !== null) {
            window.cancelAnimationFrame(
                animationFrame
            );

            animationFrame = null;
        }

        if (canvas) {
            canvas.classList.remove("active");
        }
    }

    function destroy() {
        stop();

        if (resizeHandler) {
            window.removeEventListener(
                "resize",
                resizeHandler
            );

            resizeHandler = null;
        }

        if (canvas) {
            canvas.remove();
            canvas = null;
            context = null;
        }

        nodes.length = 0;
        packets.length = 0;
    }

    window.LumsNetwork = {
        start,
        stop,
        destroy
    };
})();
