#!/usr/bin/env python3
"""LUMS Polar Office HD preview — recognizable full-colour terminal art.

Renders a 1x2 true-colour pixel canvas using Unicode upper-half blocks.
Each terminal cell therefore carries two independently coloured pixels.
The preview is standalone and does not import or alter the Pytest dashboard.

Run: .venv/bin/python tools/lums_polar_office_preview_hd.py
Stop: Ctrl+C
"""
from __future__ import annotations

import math
import os
import time
from functools import lru_cache

from rich import box
from rich.align import Align
from rich.console import Console, Group
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

RGB = tuple[int, int, int]

SKY_TOP: RGB = (5, 13, 34)
SKY_BOTTOM: RGB = (11, 34, 57)
BODY: RGB = (13, 25, 43)
BODY_LIGHT: RGB = (32, 54, 75)
BODY_EDGE: RGB = (7, 14, 28)
BELLY: RGB = (242, 248, 249)
BELLY_SHADE: RGB = (192, 216, 225)
FACE: RGB = (247, 250, 250)
EYE: RGB = (8, 17, 29)
BEAK: RGB = (255, 171, 49)
BEAK_SHADE: RGB = (206, 103, 30)
FEET: RGB = (246, 139, 43)
SCARF: RGB = (42, 205, 190)
SCARF_DARK: RGB = (20, 133, 139)


def clamp(v: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, v))


def mix(a: RGB, b: RGB, amount: float) -> RGB:
    q = clamp(amount)
    return tuple(round(x + (y - x) * q) for x, y in zip(a, b))  # type: ignore[return-value]


# A deliberately restrained 32-colour xterm palette. The raster remains
# 116x32 pixels; limiting colours reduces ANSI style churn over SSH without
# reducing spatial pixel density or changing the penguin silhouette.
XTERM_PALETTE = (
    16, 17, 18, 20, 21, 22, 23, 24,
    27, 30, 31, 32, 36, 37, 39, 42,
    44, 45, 51, 52, 88, 90, 93, 124,
    130, 166, 172, 175, 198, 213, 250, 254,
)


def _xterm_rgb(index: int) -> RGB:
    if 16 <= index <= 231:
        n = index - 16
        levels = (0, 95, 135, 175, 215, 255)
        return (
            levels[n // 36],
            levels[(n // 6) % 6],
            levels[n % 6],
        )
    value = 8 + (index - 232) * 10
    return (value, value, value)


XTERM_PALETTE_RGB = tuple(_xterm_rgb(index) for index in XTERM_PALETTE)


@lru_cache(maxsize=8192)
def rgb_to_xterm256(rgb: RGB) -> int:
    """Map RGB to a small, stable xterm palette to reduce terminal redraw cost."""
    best = min(
        range(len(XTERM_PALETTE_RGB)),
        key=lambda i: sum(
            (channel - target) ** 2
            for channel, target in zip(rgb, XTERM_PALETTE_RGB[i])
        ),
    )
    return XTERM_PALETTE[best]


@lru_cache(maxsize=2048)
def indexed_style(top_index: int, bottom_index: int) -> str:
    return f"color({top_index}) on color({bottom_index})"


class PixelCanvas:
    """Full-colour raster; two vertical pixels are encoded in each terminal cell."""

    def __init__(self, width: int, height: int, background: RGB = SKY_TOP) -> None:
        self.width = max(1, int(width))
        self.height = max(2, int(height))
        self.pixels: list[list[RGB]] = [
            [background for _ in range(self.width)] for _ in range(self.height)
        ]

    def set(self, x: float, y: float, color: RGB) -> None:
        ix, iy = int(round(x)), int(round(y))
        if 0 <= ix < self.width and 0 <= iy < self.height:
            self.pixels[iy][ix] = color

    def blend(self, x: int, y: int, color: RGB, alpha: float) -> None:
        if 0 <= x < self.width and 0 <= y < self.height:
            self.pixels[y][x] = mix(self.pixels[y][x], color, alpha)

    def ellipse(
        self, cx: float, cy: float, rx: float, ry: float, color: RGB,
        *, fill: bool = True, thickness: float = 1.0,
    ) -> None:
        if rx <= 0 or ry <= 0:
            return
        x0 = max(0, int(math.floor(cx - rx - thickness - 1)))
        x1 = min(self.width - 1, int(math.ceil(cx + rx + thickness + 1)))
        y0 = max(0, int(math.floor(cy - ry - thickness - 1)))
        y1 = min(self.height - 1, int(math.ceil(cy + ry + thickness + 1)))
        for y in range(y0, y1 + 1):
            for x in range(x0, x1 + 1):
                d = ((x - cx) / rx) ** 2 + ((y - cy) / ry) ** 2
                if (d <= 1.0) if fill else (1.0 <= d <= 1.0 + thickness / max(rx, ry)):
                    self.set(x, y, color)

    def line(self, x0: float, y0: float, x1: float, y1: float,
             color: RGB, thickness: float = 1.0) -> None:
        length = max(abs(x1 - x0), abs(y1 - y0))
        steps = max(1, int(length * 2))
        radius = max(0.0, (thickness - 1.0) / 2.0)
        for n in range(steps + 1):
            p = n / steps
            x = x0 + (x1 - x0) * p
            y = y0 + (y1 - y0) * p
            r = max(0, int(math.ceil(radius)))
            for oy in range(-r, r + 1):
                for ox in range(-r, r + 1):
                    if ox * ox + oy * oy <= radius * radius + 0.75:
                        self.set(x + ox, y + oy, color)
            if radius < 0.5:
                self.set(x, y, color)

    def polygon(self, points: list[tuple[float, float]], color: RGB) -> None:
        if len(points) < 3:
            return
        ymin = max(0, int(math.floor(min(y for _, y in points))))
        ymax = min(self.height - 1, int(math.ceil(max(y for _, y in points))))
        for y in range(ymin, ymax + 1):
            intersections: list[float] = []
            for i, (x1, y1) in enumerate(points):
                x2, y2 = points[(i + 1) % len(points)]
                if (y1 <= y < y2) or (y2 <= y < y1):
                    intersections.append(x1 + (y - y1) * (x2 - x1) / (y2 - y1))
            intersections.sort()
            for left, right in zip(intersections[0::2], intersections[1::2]):
                for x in range(max(0, math.floor(left)), min(self.width, math.ceil(right) + 1)):
                    self.set(x, y, color)

    def render(self) -> Text:
        """Map two raster rows to one terminal cell using a coloured upper half block."""
        out = Text(no_wrap=True, overflow="crop")
        rows = (self.height + 1) // 2
        for row in range(rows):
            top_y = row * 2
            bottom_y = min(top_y + 1, self.height - 1)
            run_style: str | None = None
            run = ""
            for x in range(self.width):
                top_index = rgb_to_xterm256(self.pixels[top_y][x])
                bottom_index = rgb_to_xterm256(self.pixels[bottom_y][x])
                style = indexed_style(top_index, bottom_index)
                if run and style != run_style:
                    out.append(run, style=run_style)
                    run = ""
                run_style = style
                run += "▀"
            if run:
                out.append(run, style=run_style)
            if row + 1 < rows:
                out.append("\n")
        return out


def draw_sky(c: PixelCanvas, t: float) -> None:
    w, h = c.width, c.height
    for y in range(h):
        v = y / max(1, h - 1)
        base = mix(SKY_TOP, SKY_BOTTOM, v * 0.90)
        for x in range(w):
            glow = max(0.0, 1.0 - abs(x / max(1, w - 1) - 0.51) * 1.65)
            c.pixels[y][x] = mix(base, (24, 64, 85), glow * 0.16)

    # Soft layered aurora. Multiple translucent bands make it luminous, not blocky.
    aurora = ((48, 220, 179), (65, 169, 225), (143, 126, 238), (224, 111, 190))
    for band, color in enumerate(aurora):
        phase = t * (0.32 + band * 0.045) + band * 1.25
        for x in range(w):
            u = x / max(1, w - 1)
            center = 3.2 + band * 2.6 + math.sin(u * 5.2 + phase) * 2.2
            center += math.sin(u * 10.0 - phase * 0.65) * 1.0
            for y in range(max(0, int(center - 4)), min(int(center + 5), int(h * 0.72))):
                distance = abs(y - center)
                strength = 0.24 * math.exp(-(distance * distance) / 5.2)
                strength *= 0.75 + 0.25 * math.sin(u * 8 + phase + band)
                c.blend(x, y, color, strength)

    # Stars and drifting snow use stable positions with smooth time-based drift.
    for i in range(76):
        base_x = (i * 47 + 13) % w
        speed = 0.45 + (i % 5) * 0.17
        x = int((base_x + t * speed * (1 if i % 2 else -0.35)) % w)
        y = (i * 11 + 3) % max(8, h - 5)
        pulse = 0.52 + 0.48 * math.sin(t * (1.05 + (i % 4) * 0.2) + i * 1.7)
        if i % 4 == 0:
            col = mix((75, 120, 157), (231, 248, 255), pulse)
            c.set(x, y, col)
        if i % 9 == 0:
            c.set(x, y, (220, 240, 250))
            c.set(x + 1, y, (109, 171, 195))

    # Moon with gentle glow and visible craters.
    mx, my = w - 17, 7
    c.ellipse(mx, my, 8.2, 8.2, (28, 62, 88))
    c.ellipse(mx, my, 6.6, 6.6, (185, 218, 234))
    c.ellipse(mx - 1.2, my - 1.2, 5.4, 5.6, (240, 247, 249))
    c.ellipse(mx - 3.0, my - 2.0, 1.2, 0.8, (195, 220, 231))
    c.ellipse(mx + 2.2, my + 1.9, 0.8, 0.7, (203, 224, 233))

    # Distant ridge and foreground snowbanks.
    far = h - 8
    near = h - 5
    for x in range(w):
        u = x / max(1, w - 1)
        y_far = int(far - 3.0 * math.sin(u * 5.6) - 1.5 * math.sin(u * 12.0 + 1.2))
        y_near = int(near - 1.7 * math.sin(u * 5.0 + 1.8) - 0.9 * math.sin(u * 13.0))
        for y in range(max(0, y_far), h):
            c.set(x, y, (22, 57, 84))
        c.set(x, y_far, (117, 176, 199))
        for y in range(max(0, y_near), h):
            c.set(x, y, (12, 39, 65))
        c.set(x, y_near, (117, 174, 193))
        ground = int(h - 2 + math.sin(u * 7.0) * 0.8)
        c.set(x, ground, (197, 226, 236))
        c.set(x, h - 1, (23, 58, 80))

    # Small fir trees with distinct trunks, tiers and snow highlights.
    for tx in (7, 18, w - 30, w - 21, w - 11):
        base = h - 3
        c.line(tx, base - 10, tx, base, (83, 106, 105), 1.0)
        for level in range(3):
            yy = base - 10 + level * 3
            half = 4 - level
            c.polygon([(tx, yy - 2), (tx - half, yy + 3), (tx + half, yy + 3)], (23, 92, 83))
            c.line(tx - half + 1, yy + 2, tx - 1, yy - 1, (112, 184, 171), 1.0)


def draw_penguin(
    c: PixelCanvas,
    t: float,
    *,
    center_x: float | None = None,
    carry_briefcase: bool = False,
) -> tuple[float, float]:
    """Large, high-contrast penguin with an optional homecoming briefcase."""
    w, h = c.width, c.height
    # Keep the character's bounding box anchored. Only the flippers, feet and
    # scarf move; this prevents the apparent body-size pumping seen in SSH.
    beat = t * 1.35
    cx = float(center_x) if center_x is not None else w * 0.49
    cy = h * 0.49
    wing = math.sin(beat * 1.55)
    step = math.sin(beat * 1.75 + 0.7)

    # Ground shadow and feet first, behind the body.
    c.ellipse(cx, cy + 14.0, 20.0, 2.0, (6, 17, 29))
    left_fx = cx - 6.0 + step * 1.5
    right_fx = cx + 6.0 - step * 1.5
    c.ellipse(left_fx, cy + 13.2, 4.9, 1.8, (172, 81, 31))
    c.ellipse(left_fx, cy + 12.8, 4.4, 1.6, FEET)
    c.ellipse(right_fx, cy + 13.2, 4.9, 1.8, (172, 81, 31))
    c.ellipse(right_fx, cy + 12.8, 4.4, 1.6, FEET)
    for fx in (left_fx, right_fx):
        c.line(fx - 2.3, cy + 13.0, fx - 3.8, cy + 14.0, (255, 194, 91), 1.0)
        c.line(fx + 1.3, cy + 13.0, fx + 2.8, cy + 14.0, (255, 194, 91), 1.0)

    # Flippers behind the torso: distinct tapered shapes with changing wing lift.
    left_tip = (cx - 23.0, cy - 5.2 - wing * 2.4)
    right_tip = (cx + 23.0, cy - 5.2 + wing * 2.4)
    c.polygon([
        (cx - 11.0, cy - 5.0), (cx - 17.0, cy - 8.0),
        left_tip, (cx - 20.0, cy + 3.0 - wing * 1.5),
        (cx - 13.0, cy + 4.5),
    ], BODY_EDGE)
    c.polygon([
        (cx - 11.0, cy - 5.0), (cx - 17.0, cy - 7.2),
        (left_tip[0] + 1.0, left_tip[1] + 1.0),
        (cx - 19.0, cy + 2.5 - wing * 0.8), (cx - 13.0, cy + 3.5),
    ], BODY)
    c.polygon([
        (cx + 11.0, cy - 5.0), (cx + 17.0, cy - 8.0),
        right_tip, (cx + 20.0, cy + 3.0 + wing * 1.5),
        (cx + 13.0, cy + 4.5),
    ], BODY_EDGE)
    c.polygon([
        (cx + 11.0, cy - 5.0), (cx + 17.0, cy - 7.2),
        (right_tip[0] - 1.0, right_tip[1] + 1.0),
        (cx + 19.0, cy + 2.5 + wing * 0.8), (cx + 13.0, cy + 3.5),
    ], BODY)
    c.line(cx - 16.0, cy - 4.0, left_tip[0] + 3, left_tip[1] + 2, BODY_LIGHT, 1.0)
    c.line(cx + 16.0, cy - 4.0, right_tip[0] - 3, right_tip[1] + 2, BODY_LIGHT, 1.0)

    # Outer silhouette and smooth shaded body.
    c.ellipse(cx, cy + 2.0, 17.1, 13.0, BODY_EDGE)
    c.ellipse(cx, cy + 1.2, 15.9, 12.2, BODY)
    c.ellipse(cx - 9.0, cy - 1.2, 3.2, 7.4, BODY_LIGHT)
    c.ellipse(cx + 8.4, cy - 0.6, 2.4, 6.9, (21, 40, 60))

    # White oval belly with cool shadow and a narrow highlight.
    c.ellipse(cx + 0.5, cy + 5.0, 11.0, 9.2, BELLY_SHADE)
    c.ellipse(cx, cy + 4.1, 10.1, 8.8, BELLY)
    c.ellipse(cx - 5.1, cy + 2.4, 2.1, 6.3, (255, 255, 252))

    # Round black head, soft rim, and the unmistakable white face patch.
    head_y = cy - 7.0
    c.ellipse(cx, head_y + 0.4, 10.3, 8.6, BODY_EDGE)
    c.ellipse(cx, head_y, 9.6, 8.0, BODY)
    c.ellipse(cx - 6.0, head_y - 1.0, 1.8, 4.4, BODY_LIGHT)
    c.ellipse(cx, head_y + 1.6, 7.1, 4.7, FACE)
    c.ellipse(cx - 5.1, head_y + 2.0, 1.8, 2.5, (231, 242, 244))
    c.ellipse(cx + 5.1, head_y + 2.0, 1.8, 2.5, (231, 242, 244))

    # Eyes: large enough to read at normal SSH zoom, with two catchlights.
    blink = (t % 4.7) < 0.15
    eye_y = head_y + 0.2
    for eye_x in (cx - 3.2, cx + 3.2):
        if blink:
            c.line(eye_x - 1.3, eye_y, eye_x + 1.3, eye_y, EYE, 1.8)
        else:
            c.ellipse(eye_x, eye_y, 1.25, 1.75, EYE)
            c.set(eye_x - 0.35, eye_y - 0.65, (255, 255, 255))
            c.set(eye_x + 0.35, eye_y + 0.55, (112, 180, 203))

    # Cheeks and a triangular orange beak, placed in front of the face patch.
    c.ellipse(cx - 6.5, head_y + 3.3, 1.6, 0.8, (243, 159, 169))
    c.ellipse(cx + 6.5, head_y + 3.3, 1.6, 0.8, (243, 159, 169))
    c.polygon([
        (cx - 2.5, head_y + 2.1), (cx + 2.5, head_y + 2.1),
        (cx, head_y + 5.2),
    ], BEAK)
    c.line(cx - 1.4, head_y + 3.0, cx + 1.4, head_y + 3.0, BEAK_SHADE, 1.0)
    c.set(cx - 1.2, head_y + 2.4, (255, 215, 119))

    # Bright scarf across the neck with a separate waving tail.
    scarf_y = cy - 0.2
    c.line(cx - 8.0, scarf_y, cx + 8.0, scarf_y + 0.4, SCARF_DARK, 4.0)
    c.line(cx - 8.0, scarf_y - 0.7, cx + 7.0, scarf_y - 0.2, SCARF, 2.5)
    c.line(cx + 5.2, scarf_y + 1.0, cx + 9.0, scarf_y + 7.0 + wing * 0.7, SCARF_DARK, 3.5)
    c.line(cx + 6.5, scarf_y + 1.0, cx + 10.0, scarf_y + 5.0 + wing * 0.7, (126, 239, 218), 1.0)
    for n in range(3):
        c.line(cx - 5.0 + n * 3.0, scarf_y - 1.1, cx - 4.2 + n * 3.0, scarf_y + 0.1, (178, 250, 233), 1.0)

    if carry_briefcase:
        # A clearly readable little leather case carried beside the right flipper.
        bx, by = cx + 17.0, cy + 6.8
        c.polygon(
            [(bx - 4.6, by - 3.8), (bx + 4.6, by - 3.8),
             (bx + 4.2, by + 3.8), (bx - 4.2, by + 3.8)],
            (73, 43, 35),
        )
        c.polygon(
            [(bx - 3.7, by - 3.0), (bx + 3.7, by - 3.0),
             (bx + 3.5, by + 3.0), (bx - 3.5, by + 3.0)],
            (159, 103, 56),
        )
        c.line(bx - 2.0, by - 3.1, bx - 1.2, by - 5.2, (91, 61, 43), 1.3)
        c.line(bx - 1.2, by - 5.2, bx + 1.8, by - 5.2, (91, 61, 43), 1.3)
        c.line(bx + 1.8, by - 5.2, bx + 2.2, by - 3.1, (91, 61, 43), 1.3)
        c.line(bx - 3.3, by - 0.2, bx + 3.3, by - 0.2, (224, 177, 108), 1.0)
        c.ellipse(bx, by - 0.2, 0.7, 0.8, (239, 209, 147))

    return cx, cy


def draw_snow(c: PixelCanvas, t: float) -> None:
    w, h = c.width, c.height
    for i in range(25):
        x = int((i * 37 + 9 + math.sin(t * 0.7 + i) * 2.0) % w)
        y = int((i * 13 + t * (1.2 + (i % 4) * 0.22)) % max(1, h - 3))
        c.set(x, y, (203, 232, 245))
        if i % 7 == 0:
            c.set(x + 1, y, (111, 170, 197))


def scene_render(t: float, width: int, height: int) -> Text:
    canvas = PixelCanvas(width, height)
    draw_sky(canvas, t)
    draw_penguin(canvas, t)
    draw_snow(canvas, t)
    return canvas.render()


def homecoming_render(t: float, width: int, height: int, progress: float) -> Text:
    """Calm finale: Pingu walks home with a briefcase; the body scale is fixed."""
    c = PixelCanvas(width, height)
    draw_sky(c, t * 0.24)

    # Warm little cabin at the end of the snowy path.
    hx = width - 8
    ground_y = height - 3
    c.polygon(
        [(hx - 8, ground_y - 10), (hx, ground_y - 17), (hx + 8, ground_y - 10)],
        (48, 71, 91),
    )
    c.polygon(
        [(hx - 7, ground_y - 10), (hx, ground_y - 16), (hx + 7, ground_y - 10)],
        (104, 81, 76),
    )
    c.polygon(
        [(hx - 6, ground_y - 10), (hx + 6, ground_y - 10),
         (hx + 6, ground_y - 1), (hx - 6, ground_y - 1)],
        (111, 130, 143),
    )
    # Snow cap on the roof and a warm, steadily lit window.
    c.line(hx - 8, ground_y - 10, hx, ground_y - 17, (209, 235, 244), 1.8)
    c.line(hx, ground_y - 17, hx + 8, ground_y - 10, (209, 235, 244), 1.8)
    c.ellipse(hx - 2.8, ground_y - 6.3, 1.7, 1.9, (255, 207, 112))
    c.line(hx + 3.5, ground_y - 1, hx + 3.5, ground_y - 7, (64, 43, 39), 1.0)

    # A dotted path leads from the penguin to the cabin.
    for i in range(7):
        px = int(width * 0.40 + i * 2.0)
        py = ground_y - 1 + (i % 2)
        c.set(px, py, (180, 216, 229))
        if i % 2 == 0:
            c.set(px + 1, py, (224, 240, 246))

    # Walk across a short, fixed-size path. No zoom, body bob or scale changes.
    start_x = width * 0.43
    end_x = min(width - 23.5, start_x + 9.0)
    cx = start_x + (end_x - start_x) * clamp(progress)
    draw_penguin(c, t * 0.72, center_x=cx, carry_briefcase=True)
    draw_snow(c, t * 0.20)
    return c.render()


def aquarium_art(t: float, width: int) -> Text:
    height = 8
    c = PixelCanvas(width, height, (5, 43, 76))
    for y in range(height):
        for x in range(width):
            c.pixels[y][x] = mix((5, 36, 68), (7, 91, 112), y / height * 0.75)

    # Water surface and soft moving caustic streaks.
    for x in range(width):
        surface = 1 + math.sin(x * 0.10 + t * 1.4)
        c.set(x, surface, (113, 226, 229))
        if x % 8 < 3:
            c.blend(x, min(height - 1, int(surface) + 1), (37, 150, 178), 0.55)

    # Plants behind the fish.
    for bx in (5, 11, width - 15, width - 8):
        for n in range(4):
            tip_x = bx + math.sin(t * 0.8 + n) * 2.0
            tip_y = height - 2 - n * 1.5
            c.line(bx, height - 1, tip_x, tip_y, (29, 151, 111), 1.0)
            c.line(tip_x, tip_y, tip_x + (2 if n % 2 else -2), tip_y - 1, (78, 196, 139), 1.0)

    # Orange fish, clearly separated body, tail, fin and eye.
    fx = 17 + (t * 8.0) % max(1, width - 38)
    fy = 5.4 + math.sin(t * 1.7) * 0.8
    c.polygon([(fx - 5, fy), (fx - 10, fy - 3), (fx - 10, fy + 3)], (211, 105, 53))
    c.ellipse(fx, fy, 6.5, 3.0, (250, 174, 70))
    c.ellipse(fx + 4.0, fy - 0.5, 0.8, 0.9, (9, 30, 48))
    c.set(fx + 4, fy - 1, (255, 255, 255))
    c.line(fx - 1, fy - 2, fx + 1, fy + 2, (255, 221, 143), 1.0)

    # Small purple fish moves in the opposite direction.
    fx2 = width - 17 - (t * 5.3) % max(1, width - 34)
    fy2 = 3.2 + math.sin(t * 1.5 + 2) * 0.6
    c.polygon([(fx2 + 3, fy2), (fx2 + 8, fy2 - 2), (fx2 + 8, fy2 + 2)], (156, 93, 197))
    c.ellipse(fx2, fy2, 4.1, 2.0, (207, 135, 231))
    c.ellipse(fx2 - 2.2, fy2 - 0.3, 0.55, 0.65, (8, 26, 48))

    for i in range(7):
        bx = (i * 13 + 7) % width
        by = height - 1 - int((t * (1.2 + i % 3 * 0.25) + i * 1.8) % 8)
        c.ellipse(bx, by, 0.7, 0.8, (131, 218, 240), fill=False, thickness=1.0)
    return c.render()


def make_dashboard(console: Console, t: float) -> Group:
    width = max(76, min(console.width, 120))
    pixel_width = width - 4
    # At a 30-row terminal this creates 18 terminal pixels rows = 36 raster pixels.
    scene_height = max(24, min(36, (console.height - 12) * 2))

    title = Text(
        "❄  LUMS POLAR OFFICE  •  PENGUIN WELLBEING DEPARTMENT  ❄",
        style="bold bright_cyan", justify="center",
    )
    header = Panel(
        Align.center(title), box=box.DOUBLE, border_style="bright_cyan",
        padding=(0, 1), width=width,
    )
    scene = Panel(
        scene_render(t, pixel_width, scene_height),
        title="[bold bright_cyan]🐧 Pingu's Polar Playground[/]",
        subtitle="[dim]Aurora · full-colour HD · fröhlicher Freudentanz[/]",
        border_style="bright_blue", padding=(0, 1), width=width,
    )

    desk_text = Text()
    desk_text.append("  📚 Akten  ", style="bold white")
    desk_text.append("☕ Kakao  ", style="bold yellow")
    desk_text.append("🪴 Winterpflanze  ", style="green")
    desk_text.append("✨ Gute Laune", style="bright_magenta")
    desk = Panel(
        desk_text, title="[bold yellow]☕ Pingu's Schreibtisch[/]",
        border_style="yellow", padding=(0, 1), height=6,
    )

    aquarium = Panel(
        aquarium_art(t, max(34, pixel_width // 2 - 3)),
        title="[bold cyan]🐟 Aquarium[/]", border_style="cyan",
        padding=(0, 1), height=6,
    )
    lower = Table.grid(expand=True, padding=(0, 0))
    lower.add_column(ratio=1)
    lower.add_column(ratio=1)
    lower.add_row(desk, aquarium)

    mood = int(97 + 3 * (0.5 + 0.5 * math.sin(t * 0.65)))
    footer = Text(
        f"🐧 Pingu-Laune: {mood}%    ❄ Polarlicht: AKTIV    ☕ Kakao: WARM    Vorschau: STRG+C",
        style="bold bright_white", justify="center",
    )
    return Group(header, scene, lower, Align.center(footer))


def main() -> int:
    # The user's SSH terminal advertises xterm-256color, not truecolor.
    # Use the declared palette to avoid expensive 24-bit escape sequences.
    console = Console(color_system="256", highlight=False)
    if not console.is_terminal:
        console.print("Bitte in einem interaktiven SSH-Terminal starten.")
        return 2

    try:
        fps = int(os.environ.get("LUMS_PREVIEW_FPS", "10"))
    except ValueError:
        fps = 10
    fps = max(6, min(14, fps))
    interval = 1.0 / fps
    start = time.monotonic()

    try:
        with Live(
            make_dashboard(console, 0.0), console=console,
            refresh_per_second=fps, auto_refresh=False,
            screen=True, transient=False, vertical_overflow="crop",
            redirect_stdout=False, redirect_stderr=False,
        ) as live:
            while True:
                tick = time.monotonic()
                live.update(make_dashboard(console, tick - start), refresh=True)
                time.sleep(max(0.0, interval - (time.monotonic() - tick)))
    except KeyboardInterrupt:
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
