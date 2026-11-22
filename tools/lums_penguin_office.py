#!/usr/bin/env python3
"""LUMS Penguin Office – Aurora dashboard for real pytest runs.

Das Dashboard läuft in einem EIGENEN PROZESS und zeichnet direkt auf das
echte Terminal (ein beim Start duplizierter Dateideskriptor). Dadurch

  * friert die Animation nicht ein, wenn ein Test lange läuft,
  * blockieren rechenintensive Tests (GIL) das Bild nicht,
  * kosten die Animationen die Tests keine Rechenzeit.

Flackerfrei: Es werden nur geänderte Zeilen neu geschrieben, jedes Bild ist
in "synchronized output" (DEC 2026) eingepackt und der Zeilenumbruch ist
währenddessen abgeschaltet.

Finale: Ist der Lauf durch, bekommt Pingu einen Aktenkoffer und macht
Feierabend (Igloo). Der Abschlussbericht öffnet per Mausklick auf den Button
oder mit Enter / Leertaste (q überspringt die Animation).

Aufruf:
    python tools/lums_test_show.py [pytest-Argumente]
    python tools/lums_test_show.py --demo       # nur das Dashboard, ohne Tests
    python tools/lums_test_show.py --demo-ok    # Demo mit grünem Finale

Umgebungsvariablen:
    LUMS_FPS=30              Bilder pro Sekunde (bei zäher SSH-Verbindung senken)
    LUMS_FINALE=0            kein Warten auf Klick/Enter, Bericht sofort
    LUMS_FINALE_TIMEOUT=300  nach so vielen Sekunden kommt der Bericht von selbst
    LUMS_NO_FORK=1           Dashboard als Thread statt als Prozess (Notfall)
"""

import math
import multiprocessing
import os
import queue
import random
import re
import select
import signal
import sys
import threading
import time
import warnings

try:                                   # nur Unix: Tasten/Maus im Finale
    import termios
    import tty as _ttymod
except ImportError:                    # pragma: no cover
    termios = None
    _ttymod = None

import pytest
from rich import box
from rich.align import Align
from rich.console import Console, Group
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text


def _env_int(name, default, lo=1, hi=60):
    try:
        return max(lo, min(hi, int(os.environ.get(name, default))))
    except ValueError:
        return default


AURORA = [
    (125, 211, 252), (167, 139, 250),
    (244, 114, 182), (110, 231, 183),
    (125, 211, 252),
]
GREEN = (52, 211, 120)
RED = (239, 83, 80)
YELLOW = (250, 204, 21)
TRACK = (36, 48, 56)

STATUS = {
    "passed": ("✅", "green"),
    "failed": ("🚨", "red"),
    "skipped": ("⏩", "yellow"),
}

SCENE_H = 11
PENGUIN_W = 11
STAGES = [
    ("setup", "Vorbereiten"),
    ("call", "Prüfen"),
    ("teardown", "Archivieren"),
]
STAGE_INDEX = {"setup": 0, "call": 1, "teardown": 2, "done": 3}

DANCE_ARMS = (
    r"  \     /  ",
    r" \       / ",
    r"   \   /   ",
    r"    \ /    ",
    r"    / \    ",
    r"   /   \   ",
    r"  /     \  ",
    r" /       \ ",
    r"  \     /  ",
    r"   \   /   ",
    r"  /     \  ",
    r" \       / ",
)
FEET = (r"/'\_   _/`\ ", r"/`\_   _/'\ ")
BOB = (0, -1, -1, 0, 1, 0, -1, -1, 0, 1, 0, 0)

# Igloo (12 breit, 5 hoch); die Tür liegt in den Zeilen 3-4, Spalten 4-7
IGLOO = (
    r"   _.--._   ",
    r" .'      '. ",
    "/   .--.   \\",
    r"|  /    \  |",
    r"|__|____|__|",
)
IGLOO_W = 12
_MIRROR = str.maketrans("/\\()<>[]{}`'", "\\/)(><][}{'`")

_MOUSE = re.compile(rb"\x1b\[<(\d+);(\d+);(\d+)([Mm])")
_CSI = re.compile(rb"\x1b\[[0-9;?<>]*[A-Za-z~]")
_PARTIAL = re.compile(rb"\x1b(\[[0-9;?<>]*)?$")

RESET_TERMINAL = "\x1b[?1003l\x1b[?1006l\x1b[?25h\x1b[?7h"


# --------------------------------------------------------------------------
# Kleine Helfer
# --------------------------------------------------------------------------
def mix(c1, c2, f):
    f = max(0.0, min(1.0, f))
    return tuple(int(a + (b - a) * f) for a, b in zip(c1, c2))


def quant(c, step=12):
    return tuple(min(255, int(v) // step * step) for v in c)


def rgb(c):
    return f"rgb({c[0]},{c[1]},{c[2]})"


def aurora_color(pos):
    pos %= 1.0
    last = len(AURORA) - 1
    p = pos * last
    i = min(int(p), last - 1)
    return mix(AURORA[i], AURORA[i + 1], p - i)


def gradient_text(text, t=0.0):
    out = Text(no_wrap=True)
    n = max(len(text), 1)
    for i, ch in enumerate(text):
        out.append(ch, style="bold " + rgb(aurora_color(i / n + t * 0.22)))
    return out


def fmt_dur(seconds):
    return f"{seconds * 1000:.0f} ms" if seconds < 1 else f"{seconds:.2f} s"


def fmt_span(seconds, decimals=1):
    if seconds < 60:
        return f"{seconds:.{decimals}f} s"
    minutes, secs = divmod(int(seconds), 60)
    return f"{minutes}m {secs:02d}s"


def split_nodeid(nodeid):
    parts = nodeid.split("::")
    return parts[0].rsplit("/", 1)[-1], "::".join(parts[1:]) or parts[0]


def skip_text(report):
    """Skip-Grund lesbar machen (pytest liefert Tupel: Datei, Zeile, Text)."""
    lr = report.longrepr
    if isinstance(lr, tuple) and len(lr) == 3:
        reason = str(lr[2])
        if reason.startswith("Skipped: "):
            reason = reason[len("Skipped: "):]
        return f"{reason}\n{lr[0]}:{lr[1]}"
    return str(lr)


def mirror(line):
    """ASCII-Art spiegeln (für Laufrichtung nach links)."""
    return line[::-1].translate(_MIRROR)


def runs_to_text(cells):
    """[(zeichen, style), ...] -> Text mit zusammengefassten Style-Läufen."""
    line = Text(no_wrap=True, overflow="crop")
    buf, current = "", None
    for ch, st in cells:
        if st != current and buf:
            line.append(buf, style=current or None)
            buf = ""
        current = st
        buf += ch
    if buf:
        line.append(buf, style=current or None)
    return line


def compose(width, height, sprites):
    grid = [[(" ", "") for _ in range(width)] for _ in range(height)]

    for x, y, art, style, opaque in sprites:
        if not 0 <= y < height:
            continue
        if opaque:
            stripped = art.lstrip(" ")
            x += len(art) - len(stripped)
            art = stripped.rstrip(" ")

        for i, ch in enumerate(art):
            px = x + i
            if 0 <= px < width and (opaque or ch != " "):
                st = style(ch) if callable(style) else style
                grid[y][px] = (ch, st)

    return Text("\n").join([runs_to_text(row) for row in grid])


def penguin_lines(mode, t):
    phase = int(t * (16 if mode == "party" else 10)) % 12
    blink = (t % 3.5) < 0.12

    if mode == "sleep":
        eyes = "-_-"
        arms = r" //   \ \ "
        feet = FEET[int(t / 1.6) % 2]
    elif mode == "coffee":
        eyes = "-_-" if blink else "o_o"
        arms = r" //   \ \ "
        feet = FEET[int(t / 0.8) % 2]
    elif mode == "walk":
        eyes = "-_-" if blink else "^_^"
        arms = r" //   \ \ "
        feet = FEET[int(t * 4) % 2]
    else:
        eyes = "-_-" if blink else "^_^"
        arms = DANCE_ARMS[phase]
        feet = FEET[(phase // 3) % 2]

    return [
        "   .--.   ",
        f"  |{eyes} |  ",
        r"  | \_/ |  ",
        arms,
        "(|     | )",
        feet,
        r"\___)=(___/",
    ]


def penguin_style(line):
    def style(ch):
        if line >= 5:
            return "bold yellow"
        if ch in ("o", "^"):
            return "bold bright_cyan"
        if ch == ":":
            return "bold yellow"
        return "bold white"
    return style


def bubble_pos(px, n, lo, hi):
    """Sprechblase (Länge n) im freien Bereich [lo, hi): rechts, links oder oben."""
    if px + 15 + n <= hi:
        return px + 15, 5
    if px - n - 1 >= lo:
        return px - n - 1, 5
    return max(lo, min(hi - n, px + 5 - n // 2)), 1


def finale_pose(tf, x0, x1):
    """Feierabend-Choreografie -> (x, Richtung, sichtbar, Tür_hell, Phase)."""
    intro = 1.8
    if tf < intro:
        return x0, 1, True, False, "intro"
    speed = 9.0
    walk = max(1.0, (x1 - x0) / speed)
    inside = 3.4
    c = (tf - intro) % (2 * walk + inside)
    if c < walk:
        return x0 + (x1 - x0) * c / walk, 1, True, False, "home"
    c -= walk
    if c < inside:
        return x1, 1, False, True, "inside"
    c -= inside
    return x1 - (x1 - x0) * c / walk, -1, True, False, "back"


# Feine Balken: 8 Teilschritte pro Zelle -> der Fortschritt "fließt".
PARTIAL = " ▏▎▍▌▋▊▉█"


def smooth_bar(width, segs, total, t, running):
    """segs: [(wert, (r, g, b)), ...] – Werte dürfen Kommazahlen sein."""
    if total <= 0:
        return Text(" " * width, style=f"on {rgb(TRACK)}", no_wrap=True)

    lens = []
    for val, col in segs:
        n = val / total * width * 8
        if val >= 0.5:
            n = max(n, 8.0)          # Rot/Gelb immer mindestens 1 Zelle
        lens.append((n, col))
    used = sum(n for n, _ in lens)
    if used > width * 8:
        n0, c0 = lens[0]
        lens[0] = (max(0.0, n0 - (used - width * 8)), c0)

    bounds, acc = [], 0.0
    for n, col in lens:
        acc += n
        bounds.append((acc, col))

    def color_at(pos):
        for end, col in bounds:
            if pos < end - 1e-9:
                return col
        return None

    sweep = (t * 32) % (width + 14) - 7
    cells = []
    for i in range(width):
        left = i * 8
        a = color_at(left)
        if a is None:
            cells.append((" ", f"on {rgb(TRACK)}"))
            continue
        if running and a == GREEN:
            d = abs(i - sweep)
            if d < 4:
                a = mix(a, (235, 255, 240), (1 - d / 4) * 0.6)
        end = next(e for e, c in bounds if left < e - 1e-9)
        if end >= left + 8 - 1e-9:
            cells.append(("█", rgb(quant(a))))
        else:
            k = max(1, min(7, int(round(end - left))))
            b = color_at(end + 1e-6) or TRACK
            cells.append((PARTIAL[k], f"{rgb(quant(a))} on {rgb(quant(b))}"))
    return runs_to_text(cells)


def wait_bar(width, t):
    """Unbestimmter Balken: zeigt 'ich lebe noch', auch wenn ein Test hängt."""
    length = max(4, width // 4)
    span = max(1, width - length)
    p = (t * 16) % (2 * span)
    pos = int(p if p <= span else 2 * span - p)
    cells = []
    for i in range(width):
        if pos <= i < pos + length:
            col = aurora_color((i - pos) / length * 0.6 + t * 0.2)
            cells.append(("━", "bold " + rgb(quant(col))))
        else:
            cells.append(("─", "grey27"))
    return runs_to_text(cells)


def sparkline(history, width):
    blocks = "▁▂▃▄▅▆▇█"
    window = history[-width:]
    out = Text(no_wrap=True)
    peak = max((d for _, d in window), default=0) or 1e-9
    for status, duration in window:
        idx = min(7, int((duration / peak) ** 0.5 * 7.999))
        out.append(blocks[idx], style=STATUS[status][1])
    return out


# --------------------------------------------------------------------------
# Das Dashboard selbst (läuft im Kindprozess – kennt pytest nicht)
# --------------------------------------------------------------------------
class Dash:
    def __init__(self, t0):
        self.t0 = t0
        self.total = 0
        self.done = 0
        self.counts = {"passed": 0, "failed": 0, "skipped": 0}
        self.current_id = None
        self.stage = None
        self.test_started = 0.0
        self.events = []
        self.history = []
        self.slowest = []
        self.warn_count = 0
        self.started = None
        self.end_time = None
        self.ended = False
        self.aborted = False
        self.success = None       # verbindliches Pytest-Endergebnis
        self.finale_wait = False      # wartet das Finale auf Klick/Taste?
        self.action = None            # "open" | "skip"
        self.hover = False
        self.btn = None               # (Zeile im Bild, Spalte von, bis, Höhe)
        self.inbuf = b""
        self.disp = {"done": 0.0, "passed": 0.0, "failed": 0.0, "skipped": 0.0}
        self.px = None
        self.last_t = 0.0
        self.bubble_text = ""
        self.bubble_style = ""
        self.bubble_until = 0.0
        self.milestones = set()

    # ---- Ereignisse aus dem pytest-Prozess --------------------------------
    def handle(self, msg, now):
        kind = msg[0]
        t = now - self.t0
        if kind == "total":
            self.total = msg[1]
            self.started = now
        elif kind == "begin":
            self.current_id = msg[1]
            self.stage = "setup"
            self.test_started = now
        elif kind == "stage":
            self.stage = msg[1]
        elif kind == "done":
            _, status, nodeid, duration = msg
            self.counts[status] += 1
            self.done += 1
            stem, name = split_nodeid(nodeid)
            self.events = (self.events + [(status, name, stem, duration)])[-6:]
            self.history = (self.history + [(status, duration)])[-200:]
            self.slowest = sorted(
                self.slowest + [(duration, nodeid)], reverse=True
            )[:6]
            self.current_id = None
            self.stage = None
            if status == "failed":
                self._say("Autsch! Akte rot", "bold white on red", t, 3.5)
            elif self.total >= 8:
                for frac, text in (
                    (0.25, "Viertel geschafft!"),
                    (0.5, "Halbzeit!"),
                    (0.75, "Fast geschafft!"),
                ):
                    if frac not in self.milestones and self.done >= self.total * frac:
                        self.milestones.add(frac)
                        self._say(text, "bold bright_magenta", t, 3.0)
        elif kind == "warn":
            self.warn_count = msg[1]
        elif kind == "result":
            self.success = bool(msg[1])
        elif kind == "end":
            self.ended = True
            self.aborted = bool(msg[1])
            self.finale_wait = bool(msg[2]) if len(msg) > 2 else False
            self.end_time = now
        elif kind == "skip":
            self.action = "skip"

    def is_success(self):
        return (
            self.ended
            and not self.aborted
            and self.success is True
        )

    def _say(self, text, style, t, seconds):
        self.bubble_text, self.bubble_style = text, style
        self.bubble_until = t + seconds

    # ---- Eingaben im Finale (Maus / Tastatur) -------------------------------
    def _hit(self, x, y, top_row):
        if not self.btn or top_row is None:
            return False
        line, lo, hi, rows = self.btn
        row = top_row + line
        return row <= y < row + rows and lo <= x <= hi

    def handle_input(self, data, top_row):
        buf = self.inbuf + data
        action = None
        for m in _MOUSE.finditer(buf):
            b, x, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
            inside = self._hit(x, y, top_row)
            self.hover = inside
            # linke Taste gedrückt (kein Bewegungs-Ereignis)
            if m.group(4) == b"M" and (b & 35) == 0 and inside:
                action = "open"
        rest = _CSI.sub(b"", _MOUSE.sub(b"", buf))
        tail = _PARTIAL.search(rest)
        self.inbuf = tail.group(0) if tail else b""
        if tail:
            rest = rest[:tail.start()]
        for byte in rest:
            if byte in b"\r\n rR":
                action = action or "open"
            elif byte in b"qQ":
                action = action or "skip"
        return action

    # ---- Zeichnen -----------------------------------------------------------
    def render(self, now, width, height):
        t = now - self.t0
        frame = int(t * 30)
        dt = max(0.0, min(0.25, t - self.last_t))
        self.last_t = t

        total = self.total
        counts = self.counts
        collecting = self.started is None
        running = bool(total) and self.done < total and not self.ended
        finale = self.ended and not self.aborted

        # Zahlen "rollen" lassen statt zu springen
        actual = {"done": self.done, **counts}
        if self.ended:
            self.disp = {k: float(v) for k, v in actual.items()}
        else:
            k = 1 - math.exp(-dt * 9)
            for key, val in actual.items():
                d = self.disp[key]
                d += (val - d) * k
                self.disp[key] = val if abs(val - d) < 0.02 else d
        shown = {k: int(round(v)) for k, v in self.disp.items()}

        pending = max(0, total - shown["done"] - (1 if running else 0))
        percent = int(self.disp["done"] * 100 / total) if total else 0
        end = self.end_time if self.end_time else now
        elapsed = end - self.started if self.started else 0.0
        eta = elapsed / self.done * (total - self.done) if self.done and running else 0.0
        rate = self.done / elapsed if elapsed > 0 else 0.0
        cur_elapsed = now - self.test_started if self.current_id else 0.0

        if finale:
            mode = "finale"
        elif self.current_id and cur_elapsed > 6.0:
            mode = "sleep"
        elif self.current_id and cur_elapsed > 1.5:
            mode = "coffee"
        else:
            mode = "dance"

        header = Panel(
            Align.center(gradient_text(
                "❄  LUMS POLAR OFFICE  •  PENGUIN TEST ENGINE  ❄", t
            )),
            box=box.DOUBLE,
            border_style=rgb(quant(aurora_color(t * 0.08))),
            padding=(0, 1),
        )
        parts = [header]
        self.btn = None

        if height >= 25:
            parts.append(self._scene_row(
                width, now, t, frame, dt, mode, collecting, running,
                cur_elapsed, elapsed, eta, rate,
            ))

        # ---------------- Bürostatistik ----------------
        roomy = height >= 33
        gap = [Text("")] if roomy else []
        bar_width = max(10, width - 6)
        bar = smooth_bar(
            bar_width,
            [
                (self.disp["passed"], GREEN),
                (self.disp["failed"], RED),
                (self.disp["skipped"], YELLOW),
            ],
            total, t, running,
        )
        cells = [
            ("📥", pending, "Eingang", "bold yellow"),
            ("📝", 1 if running else 0, "In Arbeit", "bold bright_cyan"),
            ("✅", shown["passed"], "Archiv", "bold green"),
            ("🚨", shown["failed"], "Problemablage", "bold red"),
            ("⏩", shown["skipped"], "Vermerke", "bold yellow"),
        ]
        counters = Table.grid(expand=True)
        for _ in cells:
            counters.add_column(justify="center", ratio=1)
        counters.add_row(*[
            Text.assemble((f"{icon} ", ""), (str(n), style))
            for icon, n, _label, style in cells
        ])
        counters.add_row(*[
            Text(label, style="dim") for _i, _n, label, _s in cells
        ])

        spark = Text(no_wrap=True)
        spark.append("Rhythmus  ", style="dim")
        spark.append_text(sparkline(self.history, max(8, bar_width - 10)))

        subtitle = f"[bold white]{percent}%[/] · {shown['done']}/{total} Akten erledigt"
        if self.warn_count:
            subtitle += f" · 🔔 {self.warn_count}"
        if finale and self.finale_wait and height < 25:
            subtitle += " · Enter = Bericht"
        parts.append(Panel(
            Group(bar, *gap, counters, *gap, spark),
            title="[bold green]📊 Bürostatistik[/]",
            subtitle=subtitle, border_style="green", padding=(0, 1),
        ))

        if height >= 40:
            parts.append(self._aquarium(width, frame))
        if height >= 29:
            parts.append(self._bottom(roomy))
        return Group(*parts)

    # ---- Szene + Schreibtisch-Akte ------------------------------------------
    def _scene_row(self, width, now, t, frame, dt, mode, collecting, running,
                   cur_elapsed, elapsed, eta, rate):
        inner = max(24, int((width - 1) * 5 / 11) - 4)
        finale = mode == "finale"
        tf = (now - self.end_time) if finale else 0.0
        sprites = []

        # Polarlicht (oberste drei Zeilen) – im Finale kräftiger
        boost = 1.3 if finale else 1.0
        for x in range(inner):
            for y in range(3):
                v = (
                    math.sin(x / 7 + t * 0.9 + y * 0.8)
                    + math.sin(x / 13 - t * 0.55)
                    + math.sin((x + y * 5) / 4.5 + t * 1.7) * 0.4
                )
                v = (v + 2.4) / 4.8
                if v < 0.6:
                    continue
                level = min(1, int((v - 0.6) / 0.4 * 2))
                glow = mix(
                    (0, 0, 0), aurora_color(x / inner + t * 0.05),
                    (0.5, 0.75)[level] * (1 - y * 0.25) * boost,
                )
                sprites.append((x, y, "░▒"[level], rgb(quant(glow)), False))

        # Sterne (Feierabend = Nacht)
        if finale:
            for i in range(max(4, inner // 4)):
                x = (i * 5351 + 3) % inner
                y = (i * 7) % 3
                bright = math.sin(t * 2.2 + i) > 0.6
                sprites.append((
                    x, y, "✦" if bright else "·",
                    "bright_yellow" if bright else "grey62", False,
                ))

        # Schnee
        for i in range(max(6, inner // 3)):
            x = (i * 7919 + 13) % inner
            x += int(round(math.sin((frame + i * 7) / 36) * 1.5))
            y = (i * 5 + (frame * (1 + i % 3)) // 16) % SCENE_H
            sprites.append((
                x, y, "·*•∙"[i % 4],
                "bright_white" if i % 2 else "bright_cyan", False,
            ))

        sprites.append((0, SCENE_H - 1, "▄" * inner, "bright_cyan", False))

        max_pad = max(0, inner - PENGUIN_W)
        text, style = None, "bold bright_magenta"

        if finale:
            success = self.is_success()
            igloo_x = max(PENGUIN_W + 2, inner - IGLOO_W)
            for i, row in enumerate(IGLOO):
                sprites.append((igloo_x, 5 + i, row, "bold bright_white", True))

            x0 = 2 + max_pad // 6
            x1 = max(x0 + 1, igloo_x + 1)
            fx, facing, visible, lit, phase = finale_pose(tf, float(x0), float(x1))

            if lit:                                   # Licht in der Tür
                glow = "bold bright_yellow" if int(t * 3) % 2 else "bold yellow"
                for y in (8, 9):
                    sprites.append((igloo_x + 4, y, "▓▓▓▓", glow, False))
                for k in range(3):                    # Zzz über dem Igloo
                    age = (t * 0.5 + k / 3) % 1.0
                    sprites.append((
                        igloo_x + 7 + int(age * 4), 4 - int(age * 4), "zZz"[k],
                        "bold bright_cyan", False,
                    ))

            if success and tf < 3.5:                  # Konfetti
                colors = ("bright_magenta", "bright_yellow", "bright_cyan",
                          "bright_green", "bright_red")
                for i in range(max(8, inner // 2)):
                    x = (i * 6151 + 5) % inner
                    y = (i * 5 + int(t * (4 + i % 4))) % (SCENE_H - 1)
                    sprites.append((x, y, "▪•*+"[i % 4], colors[i % 5], False))

            px = int(round(fx))
            if visible:
                walking = phase in ("home", "back")
                bob = (0, -1)[int(t * 6) % 2] if walking else BOB[(frame // 3) % 12]
                art = penguin_lines("walk" if walking else "party", t)
                if facing < 0:
                    art = [mirror(line) for line in art]
                for i, line in enumerate(art):
                    sprites.append((px, 3 + bob + i, line, penguin_style(i), True))
                if tf >= 0.7:                         # Aktenkoffer
                    cx = px + 11 if facing > 0 else px - 3
                    sprites.append((cx, 3 + bob + 3, "┌─┐", "grey70", False))
                    sprites.append((cx, 3 + bob + 4, "███", "rgb(150,95,45)", False))
                    sprites.append((cx, 3 + bob + 5, "▀▀▀", "rgb(110,70,30)", False))

            if phase == "intro":
                text = "Feierabend!" if success else "Puh ... geschafft?"
            elif phase == "home":
                text = "Ab nach Hause!" if success else "Morgen räume ich auf"
            elif phase == "inside":
                text = "Gute Nacht, LUMS!"
            else:
                text = "Schlüssel vergessen ..."
            style = "bold bright_magenta" if success else "bold bright_yellow"
            label = f" {text} "
            if phase == "inside":
                bx, by = max(0, igloo_x - len(label) - 1), 3
            else:
                bx, by = bubble_pos(px, len(label), 0, igloo_x - 1)
            sprites.append((bx, by, label, style, True))
        else:
            # Pinguin: sanft zur Zielposition gleiten
            if mode == "dance":
                patrol_range = min(8, max_pad // 2)
                target = max_pad // 2 + int(round(
                    math.sin(frame * math.tau / 90) * patrol_range
                ))
            else:
                target = max_pad // 2
            if self.px is None:
                self.px = float(target)
            self.px += (target - self.px) * min(1.0, dt * 6)
            px = max(0, min(max_pad, int(round(self.px))))
            bob = BOB[(frame // 3) % 12] if mode == "dance" else 0

            for i, art in enumerate(penguin_lines(mode, t)):
                sprites.append((px, 3 + bob + i, art, penguin_style(i), True))

            if mode == "coffee":
                sprites.append((px + 11, 6, "c[_]", "bold yellow", False))
                sprites.append((px + 12, 5, ("(", ")")[int(t * 3) % 2], "bright_white", False))
                sprites.append((px + 13, 4, (")", "(")[int(t * 3) % 2], "white", False))
            elif mode == "sleep":
                for k in range(3):
                    age = (t * 0.6 + k / 3) % 1.0
                    sprites.append((
                        px + 9 + int(age * 6), 3 - int(age * 3), "zZz"[k],
                        "bold bright_cyan", False,
                    ))
            else:
                cheer = "♪♫♥✦"[int(t * 3.3) % 4]
                cheer_x = px + 9 if px + 9 < inner else max(0, px + 1)
                sprites.append((cheer_x, max(0, 2 + bob), cheer, "bold bright_magenta", False))

            if t < self.bubble_until:
                text, style = self.bubble_text, self.bubble_style
            elif mode == "sleep":
                text = "Zzz ... dicke Akte"
            elif mode == "coffee":
                text = "Kaffeepause ..."
            if text:
                label = f" {text} "
                bx, by = bubble_pos(px, len(label), 0, inner)
                sprites.append((bx, by, label, style, True))

        scene_panel = Panel(
            compose(inner, SCENE_H, sprites),
            title="[bold cyan]🐧 Sachbearbeiter Pingu[/]",
            border_style=rgb(quant(aurora_color(t * 0.08 + 0.3))),
            padding=(0, 1), height=SCENE_H + 2,
        )

        if finale:
            case = self._finale_case(width, t, elapsed)
        else:
            case = self._case(width, t, collecting, running, cur_elapsed,
                              elapsed, eta, rate)
        case_panel = Panel(
            case, title="[bold yellow]📂 Schreibtisch-Akte[/]",
            border_style="yellow", padding=(0, 1), height=SCENE_H + 2,
        )

        row = Table.grid(expand=True, padding=(0, 1))
        row.add_column(ratio=5)
        row.add_column(ratio=6)
        row.add_row(scene_panel, case_panel)
        return row

    def _case(self, width, t, collecting, running, cur_elapsed, elapsed, eta, rate):
        counts = self.counts
        total = self.total
        spin = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"[int(t * 8) % 10]
        case = Text(no_wrap=True, overflow="ellipsis")
        case.append("📄 AKTUELLE TESTAKTE\n\n", style="bold cyan")

        if self.current_id:
            stem, name = split_nodeid(self.current_id)
            case.append(f"{spin} ", style="bold bright_cyan")
            case.append(name + "\n", style="bold white")
            case.append(f"  {stem}\n\n", style="dim")
        elif collecting:
            case.append("📚 Akten werden gesammelt ...\n\n\n", style="bold cyan")
        elif self.ended:
            case.append("🛑 Lauf vorzeitig beendet\n\n\n", style="bold red")
        else:
            case.append("💤 Greife nach der nächsten Testakte ...\n\n\n", style="dim")

        stage_idx = STAGE_INDEX.get(self.stage, -1)
        for i, (_key, label) in enumerate(STAGES):
            if i:
                case.append("  ─  ", style="dim")
            if stage_idx == i:
                case.append("● " + label, style="bold yellow")
            elif stage_idx > i:
                case.append("✔ " + label, style="green")
            else:
                case.append("○ " + label, style="grey50")
        case.append("\n\n")

        eta_txt = "~" + fmt_span(eta, 0) if self.done and running else "–"
        case.append("⏳ Laufzeit ", style="dim")
        case.append(fmt_span(elapsed), style="white")
        case.append("   ETA ", style="dim")
        case.append(eta_txt + "\n", style="white")

        slow_style = "bold red" if cur_elapsed > 6 else "bold yellow" if cur_elapsed > 1.5 else "white"
        case.append("⚡ Tempo ", style="dim")
        case.append(f"{rate:.1f} Akten/s", style="white")
        case.append("   Akte seit ", style="dim")
        case.append(f"{cur_elapsed:.2f} s\n", style=slow_style)

        if self.current_id and cur_elapsed > 0.6:
            bar_w = max(8, min(40, int((width - 1) * 6 / 11) - 8))
            case.append_text(wait_bar(bar_w, t))
        case.append("\n")

        case.append("📌 Pinguin-Stempel: ", style="dim")
        if counts["failed"]:
            case.append(" MIT PROBLEMEN ", style="bold white on red")
        elif self.ended:
            case.append(" ABGEBROCHEN ", style="bold white on red")
        else:
            blink = "bold black on yellow" if int(t * 0.7) % 2 else "bold yellow"
            case.append(" IN BEARBEITUNG ", style=blink)
        return case

    def _finale_case(self, width, t, elapsed):
        """Lauf beendet: Zusammenfassung + klickbarer Button (11 Zeilen)."""
        c = self.counts
        inner_r = max(20, int((width - 1) * 6 / 11) - 4)
        ok = self.is_success()
        case = Text(no_wrap=True, overflow="ellipsis")
        case.append("🏁 LAUF BEENDET\n\n", style="bold green" if ok else "bold red")
        case.append(f"✅ {c['passed']}   ", style="green")
        case.append(f"🚨 {c['failed']}   ", style="red")
        case.append(f"⏩ {c['skipped']}\n", style="yellow")
        case.append("⏳ Laufzeit ", style="dim")
        case.append(fmt_span(elapsed) + "\n\n", style="white")

        label = "ABSCHLUSSBERICHT ÖFFNEN" if inner_r >= 36 else "BERICHT ÖFFNEN"
        if self.action == "open":
            label = "BERICHT WIRD GEÖFFNET"[: len(label)].ljust(len(label))
        face = f"»  {label}  «"
        bw = len(face)
        pad = " " * max(0, (inner_r - bw) // 2)
        if self.action == "open":
            bg = (110, 231, 183)
        elif self.hover:
            bg = (255, 214, 102)
        else:
            bg = mix(AURORA[0], AURORA[2], 0.5 + 0.5 * math.sin(t * 2.0))
        fg = rgb(quant(bg))
        case.append(pad + "▄" * bw + "\n", style=fg)
        case.append(pad)
        case.append(face + "\n", style=f"bold rgb(18,24,33) on {fg}")
        case.append(pad + "▀" * bw + "\n\n", style=fg)

        if self.finale_wait:
            case.append("Klick · Enter · Leertaste   (q = überspringen)\n", style="dim")
        else:
            case.append("Bericht folgt gleich ...\n", style="dim")
        case.append("📌 Pinguin-Stempel: ", style="dim")
        if ok:
            case.append(" ABGELEGT ", style="bold black on green")
        else:
            case.append(" MIT PROBLEMEN ", style="bold white on red")

        # Trefferfläche des Buttons (Zeile im Bild, Spalten) – mit Toleranz
        left_w = int((width - 1) * 5 / 11)
        start = left_w + 4 + len(pad)
        self.btn = (3 + 1 + 5, start - 2, start + bw + 1, 3)
        return case

    def _aquarium(self, width, frame):
        aw = max(16, width - 4)
        wave_off = (frame // 16) % 2
        aq = [
            (0, 0, ("≈~" * aw)[wave_off:wave_off + aw], "blue", False),
            (0, 4, "▒" * aw, "dim blue", False),
        ]
        for i in range(max(1, aw // 14)):
            aq.append((i * 14 + 4, 3, "ψ", "green", False))
            aq.append((i * 14 + 9, 3, "Ψ", "green", False))

        aq.append(((frame // 6) % (aw + 16) - 8, 1, "><(((°>", "bright_yellow", False))
        aq.append((aw + 8 - (frame // 8) % (aw + 16), 2, "<°)))><", "bright_magenta", False))
        aq.append((
            (frame // 8 + aw // 3) % (aw + 4) - 3, 3, "><>", "bright_green", False,
        ))
        for i in range(4):
            by = 3 - ((frame // 16 + i * 2) % 3)
            aq.append((i * (aw // 4) + 5, by, "o" if i % 2 else "°", "bright_blue", False))

        return Panel(
            compose(aw, 5, aq),
            title="[bold cyan]🐟 Pinguins Aquarium[/]",
            border_style="bright_blue", padding=(0, 1),
        )

    def _bottom(self, roomy):
        rows = 6 if roomy else 4

        log = Table.grid(expand=True, padding=(0, 1))
        log.add_column(width=2, no_wrap=True)
        log.add_column(ratio=1, no_wrap=True, overflow="ellipsis")
        log.add_column(justify="right", no_wrap=True, width=9)
        if self.events:
            for status, name, stem, duration in self.events[-rows:]:
                icon, color = STATUS[status]
                log.add_row(
                    icon,
                    Text.assemble((name, color), (f"  {stem}", "dim")),
                    Text(fmt_dur(duration), style="dim"),
                )
        else:
            log.add_row("📥", Text("Die erste Akte wartet ...", style="dim"), "")

        archive = Panel(
            log, title="[bold magenta]📚 Letzte Aktenbewegungen[/]",
            border_style="magenta", padding=(0, 1), height=rows + 2,
        )

        slow = Table.grid(expand=True, padding=(0, 1))
        slow.add_column(width=2, no_wrap=True, style="dim")
        slow.add_column(ratio=1, no_wrap=True, overflow="ellipsis")
        slow.add_column(justify="right", no_wrap=True, width=9)
        if self.slowest:
            for rank, (duration, nodeid) in enumerate(self.slowest[:rows], 1):
                _stem, name = split_nodeid(nodeid)
                style = "bold red" if rank == 1 else "white"
                slow.add_row(
                    f"{rank}.", Text(name, style=style),
                    Text(fmt_dur(duration), style=style),
                )
        else:
            slow.add_row("", Text("Noch keine Messwerte ...", style="dim"), "")

        slow_panel = Panel(
            slow, title="[bold yellow]🐢 Langsamste Akten[/]",
            border_style="yellow", padding=(0, 1), height=rows + 2,
        )

        bottom = Table.grid(expand=True, padding=(0, 1))
        bottom.add_column(ratio=6)
        bottom.add_column(ratio=5)
        bottom.add_row(archive, slow_panel)
        return bottom


# --------------------------------------------------------------------------
# Flackerfreier Zeichner: nur geänderte Zeilen, synchronisiert, ohne Umbruch
# --------------------------------------------------------------------------
class FrameWriter:
    def __init__(self, console, tty):
        self.console = console
        self.tty = tty
        self.prev = None          # zuletzt gezeichnete Zeilen
        self.size = None
        self.top_row = None       # 1-basierte Bildschirmzeile der ersten Bildzeile

    def _w(self, s):
        try:
            self.tty.write(s)
            self.tty.flush()
        except (OSError, ValueError):
            pass

    def start(self):
        self._w("\x1b[?25l\x1b[?7l")             # Cursor aus, Zeilenumbruch aus

    def stop(self):
        self._w(RESET_TERMINAL)

    def mouse(self, on):
        self._w("\x1b[?1003h\x1b[?1006h" if on else "\x1b[?1003l\x1b[?1006l")

    def lines_of(self, renderable, height):
        with self.console.capture() as cap:
            self.console.print(renderable, end="")
        text = cap.get()
        if text.endswith("\n"):             # Rich hängt am Ende ein \n an
            text = text[:-1]
        return text.split("\n")[: max(1, height - 1)]

    def draw(self, renderable, width, height):
        """Zeichnet ein Bild. Gibt True zurück, wenn komplett neu gezeichnet wurde."""
        lines = self.lines_of(renderable, height)
        out = ["\x1b[?2026h"]
        full = False
        if self.prev is None:
            full = True
            out += [ln + "\x1b[0m\r\n" for ln in lines]
        elif (width, height) != self.size or len(lines) != len(self.prev):
            full = True
            out.append(f"\x1b[{len(self.prev)}A\r\x1b[J")
            out += [ln + "\x1b[0m\r\n" for ln in lines]
        else:
            out.append(f"\x1b[{len(lines)}A\r")
            for ln, old in zip(lines, self.prev):
                if ln != old:
                    out.append(ln + "\x1b[0m")
                out.append("\r\n")
        out.append("\x1b[?2026l")
        self._w("".join(out))
        self.prev = lines
        self.size = (width, height)
        return full

    def query_cursor(self, fd, timeout=0.3):
        """Wo steht der Cursor? -> Bildschirmzeile des Bildanfangs (für Mausklicks)."""
        self._w("\x1b[6n")
        buf = b""
        end = time.monotonic() + timeout
        self.top_row = None
        while time.monotonic() < end:
            try:
                ready, _, _ = select.select([fd], [], [], max(0.0, end - time.monotonic()))
                if not ready:
                    continue
                buf += os.read(fd, 64)
            except (OSError, ValueError):
                return
            m = re.search(rb"\x1b\[(\d+);(\d+)R", buf)
            if m and self.prev is not None:
                self.top_row = int(m.group(1)) - len(self.prev)
                return


# --------------------------------------------------------------------------
# Zeichen-Schleife (Kindprozess oder Thread) + Kommunikation
# --------------------------------------------------------------------------
class _ConnInbox:
    def __init__(self, conn, tty_in=None):
        self.conn = conn
        self.tty_in = tty_in
        self.eof = False

    def poll(self, timeout, want_input=False):
        if self.eof:
            raise EOFError
        fds = [self.conn.fileno()]
        if want_input and self.tty_in is not None:
            fds.append(self.tty_in)
        try:
            ready, _, _ = select.select(fds, [], [], timeout)
        except (OSError, ValueError):
            ready = []
        msgs, data = [], b""
        if self.conn.fileno() in ready:
            try:
                while self.conn.poll(0):
                    msgs.append(self.conn.recv())
            except (EOFError, OSError):
                self.eof = True
        if want_input and self.tty_in in ready:
            try:
                data = os.read(self.tty_in, 4096)
            except OSError:
                data = b""
        if self.eof and not msgs:
            raise EOFError
        return msgs, data


class _QueueInbox:
    def __init__(self, q):
        self.q = q

    def poll(self, timeout, want_input=False):
        try:
            msg = self.q.get(timeout=timeout) if timeout > 0 else self.q.get_nowait()
        except queue.Empty:
            return [], b""
        return [msg], b""


def _sync_size(console, tty):
    """Terminalgröße selbst lesen: Rich sähe unter pytests Capture nur 80x25."""
    try:
        size = os.get_terminal_size(tty.fileno())
        console.size = (size.columns, size.lines)
    except (OSError, ValueError, AttributeError):
        pass


def _enter_raw(fd):
    saved = None
    try:
        saved = termios.tcgetattr(fd)
        _ttymod.setcbreak(fd)
        termios.tcflush(fd, termios.TCIFLUSH)    # Vorab-Getipptes verwerfen
        return saved
    except (termios.error, OSError, ValueError, AttributeError):
        # Falls cbreak bereits aktiv wurde, den ursprünglichen Zustand
        # auch bei einem späteren Fehler zuverlässig wiederherstellen.
        if saved is not None:
            _restore_raw(fd, saved)
        return None


def _restore_raw(fd, saved):
    try:
        termios.tcsetattr(fd, termios.TCSADRAIN, saved)
    except (termios.error, OSError, ValueError, AttributeError):
        pass


def dash_loop(inbox, tty, fps, tty_in=None, finale_timeout=300.0):
    console = Console(file=tty, force_terminal=True)
    _sync_size(console, tty)
    writer = FrameWriter(console, tty)
    t0 = time.monotonic()
    dash = Dash(t0)
    interval = 1.0 / fps
    saved_attrs = None
    deadline = None
    need_dsr = False
    mouse_on = False

    writer.start()
    try:
        writer.draw(dash.render(t0, console.width, console.height),
                    console.width, console.height)
        next_frame = time.monotonic()
        while True:
            try:
                msgs, data = inbox.poll(
                    max(0.0, next_frame - time.monotonic()),
                    want_input=saved_attrs is not None,
                )
            except EOFError:                 # pytest-Prozess ist verschwunden
                msgs, data = [], b""
                if not dash.ended:
                    dash.handle(("end", True, False), time.monotonic())
            now = time.monotonic()
            for msg in msgs:
                dash.handle(msg, now)
            if data:
                act = dash.handle_input(data, writer.top_row)
                if act:
                    dash.action = act

            if dash.ended and deadline is None:
                if dash.finale_wait and tty_in is not None and termios is not None:
                    saved_attrs = _enter_raw(tty_in)
                    need_dsr = saved_attrs is not None
                    deadline = now + finale_timeout
                    if saved_attrs is None:
                        dash.finale_wait = False
                        deadline = now + 3.0
                elif not dash.aborted:
                    deadline = now + 3.0     # kurze Feierabend-Szene
                else:
                    deadline = now

            if dash.ended or now >= next_frame:
                _sync_size(console, tty)
                w, h = console.width, console.height
                full = writer.draw(dash.render(now, w, h), w, h)
                if saved_attrs is not None and (need_dsr or full):
                    writer.query_cursor(tty_in)
                    need_dsr = False
                    if writer.top_row is not None and not mouse_on:
                        writer.mouse(True)
                        mouse_on = True
                next_frame = now + interval if now - next_frame > interval else next_frame + interval

            if dash.ended and (now >= deadline or dash.action):
                break
    finally:
        if saved_attrs is not None:
            _restore_raw(tty_in, saved_attrs)
        writer.stop()


def _log_crash():
    """Fehler im Dashboard-Prozess landen hier statt im Nichts."""
    import traceback
    try:
        with open("/tmp/lums_dashboard_error.log", "a", encoding="utf-8") as fh:
            fh.write(time.strftime("%Y-%m-%d %H:%M:%S\n"))
            fh.write(traceback.format_exc() + "\n")
    except OSError:
        pass


def _process_main(recv, send, tty, tty_in, fps, finale_timeout):
    send.close()                             # sonst käme nie ein EOF an
    signal.signal(signal.SIGINT, signal.SIG_IGN)   # Ctrl+C regelt der Elternteil
    try:
        dash_loop(_ConnInbox(recv, tty_in), tty, fps, tty_in, finale_timeout)
    except Exception:
        _log_crash()


def _thread_main(inbox, tty, fps):
    try:
        dash_loop(inbox, tty, fps)
    except Exception:
        _log_crash()


def _dup_terminal():
    """Das ECHTE Terminal merken, BEVOR pytest fd 1 umleitet."""
    try:
        fd = os.dup(sys.__stdout__.fileno())
        return os.fdopen(fd, "w", encoding="utf-8", errors="replace", buffering=1)
    except (AttributeError, OSError, ValueError):
        return None


def _dup_terminal_in():
    """Eingabe-Terminal merken (pytest lenkt fd 0 sonst nach /dev/null)."""
    try:
        if os.isatty(0):
            return os.dup(0)
    except OSError:
        pass
    try:
        return os.open("/dev/tty", os.O_RDONLY)
    except OSError:
        return None


# --------------------------------------------------------------------------
# pytest-Plugin (Elternprozess): sammelt Daten, schickt Ereignisse, druckt Bericht
# --------------------------------------------------------------------------
class LUMSPolarOffice:
    def __init__(self):
        self.tty = _dup_terminal()
        self.console = Console(file=self.tty) if self.tty else Console()
        self.interactive = bool(self.tty and self.tty.isatty())

        # Finale mit Klick/Enter nur mit Terminal-Eingabe (Unix)
        self.tty_in = None
        self.saved_attrs = None
        self.finale_ok = False
        self.finale_timeout = _env_int("LUMS_FINALE_TIMEOUT", 300, 5, 86400)
        if (self.interactive and termios is not None
                and os.environ.get("LUMS_FINALE", "1") != "0"):
            self.tty_in = _dup_terminal_in()
            if self.tty_in is not None:
                try:
                    self.saved_attrs = termios.tcgetattr(self.tty_in)
                    self.finale_ok = True
                except (termios.error, OSError, ValueError):
                    pass

        self.mode = None            # "process" | "thread" | None
        self.proc = None
        self.thread = None
        self.conn = None
        self.q = None
        self.stopped = False
        self.reported = False

        self.total = 0
        self.done = 0
        self.counts = {"passed": 0, "failed": 0, "skipped": 0}
        self.phases = {}
        self.slowest = []
        self.failures = []
        self.skips = []
        self.warnings = {}
        self.collection_errors = []
        self.started = 0.0

    # ---- Worker -------------------------------------------------------------
    def _start_worker(self):
        if not self.interactive or self.mode:
            return
        fps = _env_int("LUMS_FPS", 30)

        if os.environ.get("LUMS_NO_FORK") != "1":
            try:
                ctx = multiprocessing.get_context("fork")
                recv, send = ctx.Pipe(duplex=False)
                proc = ctx.Process(
                    target=_process_main,
                    args=(recv, send, self.tty,
                          self.tty_in if self.finale_ok else None,
                          fps, float(self.finale_timeout)),
                    daemon=True,
                )
                proc.start()
                recv.close()
                self.conn, self.proc, self.mode = send, proc, "process"
                return
            except (ValueError, OSError):
                pass                         # kein fork verfügbar -> Thread

        self.finale_ok = False
        self.q = queue.Queue()
        self.thread = threading.Thread(
            target=_thread_main, args=(_QueueInbox(self.q), self.tty, fps),
            daemon=True,
        )
        self.thread.start()
        self.mode = "thread"

    def _emit(self, *msg):
        if self.mode == "process":
            try:
                self.conn.send(msg)
            except (OSError, ValueError):
                self.mode = None
        elif self.mode == "thread":
            self.q.put(msg)

    def _reset_terminal(self):
        if not self.interactive:
            return
        try:
            self.tty.write(RESET_TERMINAL)
            self.tty.flush()
        except (OSError, ValueError):
            pass
        if self.tty_in is not None and self.saved_attrs is not None and termios:
            _restore_raw(self.tty_in, self.saved_attrs)

    def shutdown(self, aborted=False):
        if self.stopped:
            return
        self.stopped = True
        waiting = False
        if self.mode:
            waiting = self.finale_ok and self.mode == "process" and not aborted
            self._emit("end", aborted, waiting)
        if self.proc is not None:
            limit = self.finale_timeout + 15 if waiting else 5
            try:
                self.proc.join(timeout=limit)
            except KeyboardInterrupt:        # Ctrl+C im Finale: weiter zum Bericht
                self._emit("skip")
                self.proc.join(timeout=5)
            if self.proc.is_alive():
                self.proc.terminate()
            try:
                self.conn.close()
            except OSError:
                pass
        if self.thread is not None:
            self.thread.join(timeout=5)
        self._reset_terminal()

    # ---- pytest-Hooks ---------------------------------------------------------
    def pytest_sessionstart(self, session):
        self._start_worker()

    def pytest_collection_finish(self, session):
        self.total = len(session.items)
        self.started = time.monotonic()
        if self.mode:
            self._emit("total", self.total)
        elif not self.interactive:
            self.console.print(f"🐧 Penguin Office – {self.total} Akten geladen")

    def pytest_runtest_logstart(self, nodeid, location):
        self.phases[nodeid] = []
        self._emit("begin", nodeid)

    def pytest_runtest_logreport(self, report):
        self.phases.setdefault(report.nodeid, []).append(report)
        self._emit("stage", {
            "setup": "call", "call": "teardown", "teardown": "done",
        }.get(report.when, "done"))

    def pytest_runtest_logfinish(self, nodeid, location):
        reports = self.phases.pop(nodeid, [])
        failed = next((r for r in reports if r.failed), None)
        skipped = next((r for r in reports if r.skipped), None)
        duration = sum(r.duration for r in reports)

        if failed:
            status = "failed"
            self.failures.append((
                nodeid, failed.when,
                getattr(failed, "longreprtext", str(failed.longrepr)),
            ))
        elif skipped:
            status = "skipped"
            self.skips.append((nodeid, skip_text(skipped)))
        else:
            status = "passed"

        self.counts[status] += 1
        self.done += 1
        self.slowest = sorted(
            self.slowest + [(duration, nodeid)], reverse=True
        )[:6]
        self._emit("done", status, nodeid, duration)

    def pytest_collectreport(self, report):
        if report.failed:
            self.collection_errors.append(str(report.longrepr))

    def pytest_warning_recorded(self, warning_message, when, nodeid, location):
        key = (
            warning_message.category.__name__,
            str(warning_message.message),
        )
        self.warnings[key] = self.warnings.get(key, 0) + 1
        self._emit("warn", sum(self.warnings.values()))

    def pytest_unconfigure(self, config):
        self.shutdown(aborted=True)

    # ---- Abschlussbericht ---------------------------------------------------
    def pytest_sessionfinish(self, session, exitstatus):
        if self.reported:
            return
        self.reported = True

        # Eine einzige verbindliche Erfolgsentscheidung für Bericht und UI.
        success = (
            int(exitstatus) == 0
            and self.total > 0
            and self.done == self.total
            and not self.counts["failed"]
            and not self.counts["skipped"]
            and not self.collection_errors
        )
        if self.mode:
            self._emit("result", success)

        # Das Ergebnis muss vor dem Endereignis beim Dashboard ankommen.
        self.shutdown(aborted=self.done < self.total)
        if self.tty:
            _sync_size(self.console, self.tty)

        elapsed = time.monotonic() - self.started if self.started else 0
        total = self.total or 1

        result = Table(
            title=gradient_text("🐧 Abschlussbericht – Personalakte Pingu"),
            box=box.ROUNDED, border_style="bright_cyan",
            header_style="bold cyan", title_justify="center", padding=(0, 2),
        )
        result.add_column("Ergebnis")
        result.add_column("Anzahl", justify="right")
        result.add_column("Anteil", justify="right")
        for label, key, color in (
            ("✅ Bestanden", "passed", "green"),
            ("🚨 Fehlgeschlagen", "failed", "red"),
            ("⏩ Übersprungen", "skipped", "yellow"),
        ):
            n = self.counts[key]
            result.add_row(
                Text(label, style=color),
                Text(str(n), style=f"bold {color}"),
                Text(f"{n * 100 / total:.0f} %", style="dim"),
            )
        warn_count = sum(self.warnings.values())
        if warn_count:
            result.add_row(
                Text("🔔 Warnungen", style="yellow"),
                Text(str(warn_count), style="bold yellow"), Text(""),
            )
        result.add_section()
        result.add_row("📊 Abgeschlossen", f"{self.done}/{self.total}", "")
        result.add_row("⏳ Laufzeit", f"{elapsed:.2f} Sekunden", "")
        self.console.print(Align.center(result))

        if self.slowest:
            slow = Table(
                title="🐢 Die langsamsten Akten", box=box.SIMPLE_HEAD,
                border_style="yellow", header_style="bold yellow",
            )
            slow.add_column("#", justify="right", style="dim")
            slow.add_column("Test", overflow="fold")
            slow.add_column("Dauer", justify="right")
            for rank, (duration, nodeid) in enumerate(self.slowest[:5], 1):
                slow.add_row(str(rank), Text(nodeid), fmt_dur(duration))
            self.console.print(Align.center(slow))

        # Text(...) statt str: Tracebacks enthalten oft [eckige Klammern],
        # die Rich sonst als Markup deuten würde.
        for nodeid, when, detail in self.failures:
            where = "" if when == "call" else f" ({when})"
            self.console.print(Panel(
                Text(str(detail)[:12000]),
                title=Text.assemble(
                    (f"🚨 Fehlerakte{where}: ", "bold red"), (nodeid, "white"),
                ),
                border_style="red",
            ))

        for nodeid, detail in self.skips:
            self.console.print(Panel(
                Text(str(detail)[:3000]),
                title=Text.assemble(
                    ("⏩ Prüfvermerk: ", "bold yellow"), (nodeid, "white"),
                ),
                border_style="yellow",
            ))

        if self.warnings:
            body = Text()
            ranked = sorted(self.warnings.items(), key=lambda kv: -kv[1])
            for (category, message), count in ranked[:8]:
                body.append(f"{count}× ", style="bold yellow")
                body.append(f"{category}: ", style="yellow")
                body.append(message.strip()[:300] + "\n")
            body.rstrip()
            if len(ranked) > 8:
                body.append(f"\n… und {len(ranked) - 8} weitere", style="dim")
            self.console.print(Panel(
                body, title="🔔 Warnungen", border_style="yellow",
            ))

        for detail in self.collection_errors:
            self.console.print(Panel(
                Text(str(detail)[:12000]),
                title="🚨 Fehler bei der Testsuche", border_style="red",
            ))

        if success:
            self.console.print(Panel(
                Align.center(gradient_text(
                    "🎉 ALLE AKTEN ERFOLGREICH ABGELEGT! 🐧🐟"
                )),
                box=box.DOUBLE, border_style="green",
            ))
            if self.interactive:
                self.show_farewell()
        else:
            self.console.print(Panel(
                Align.center(Text(
                    "🚧 Das Büro hat noch offene Vorgänge.", style="bold red",
                )),
                box=box.DOUBLE, border_style="red",
            ))

    def show_farewell(self):
        frames = (
            "🐧   ☕\n\nFeierabend! Alle Akten sind erledigt.",
            "🐧 💤\n\nZ z z ...",
            "😴🐧\n\n🌙 Gute Nacht, LUMS!",
        )
        with Live(console=self.console, refresh_per_second=4, transient=False) as finale:
            for frame in frames:
                finale.update(Panel(
                    Align.center(Text(
                        frame, justify="center", style="bold bright_cyan"
                    )),
                    title="[bold green]🌙 Pinguins Feierabend[/]",
                    border_style="green", padding=(1, 2),
                ))
                time.sleep(0.7)


# --------------------------------------------------------------------------
# Demo: nur das Dashboard, ohne echte Tests
# --------------------------------------------------------------------------
class _DemoReport:
    def __init__(self, nodeid, when, outcome, duration, longrepr=None):
        self.nodeid, self.when, self.duration = nodeid, when, duration
        self.failed = outcome == "failed"
        self.skipped = outcome == "skipped"
        self.passed = outcome == "passed"
        self.longrepr = longrepr
        self.longreprtext = str(longrepr)


class _DemoSession:
    def __init__(self, n):
        self.items = list(range(n))


def run_demo(ok=False):
    rnd = random.Random(7)
    plugin = LUMSPolarOffice()
    mods = ["alerts", "auth", "worker", "rules", "audit", "postgres"]
    verbs = ["creates", "deletes", "updates", "rejects", "audits", "returns"]
    nodeids = [
        f"tests/test_{mods[i % 6]}_unit.py::test_{verbs[(i * 5) % 6]}_{mods[(i * 7) % 6]}_{i}"
        for i in range(90)
    ]
    fail_at, skip_at = (-1, -1) if ok else (33, 41)
    long_tests = {22: 3.4, 58: 7.5}          # Kaffeepause / Nickerchen

    plugin.pytest_sessionstart(None)
    time.sleep(1.2)                          # "Akten werden gesammelt"
    plugin.pytest_collection_finish(_DemoSession(len(nodeids)))
    time.sleep(0.5)

    for i, nid in enumerate(nodeids):
        d = long_tests.get(i, rnd.uniform(0.01, 0.09))
        plugin.pytest_runtest_logstart(nid, None)
        time.sleep(d * 0.1)
        plugin.pytest_runtest_logreport(_DemoReport(nid, "setup", "passed", d * 0.1))
        outcome = "failed" if i == fail_at else "skipped" if i == skip_at else "passed"
        lr = (
            "AssertionError: erwartet [200], bekommen [500]" if outcome == "failed"
            else ("tests/test_rules_unit.py", 41, "Skipped: kein Netz im Demo-Modus")
            if outcome == "skipped" else None
        )
        time.sleep(d * 0.8)
        plugin.pytest_runtest_logreport(_DemoReport(nid, "call", outcome, d * 0.8, lr))
        time.sleep(d * 0.1)
        plugin.pytest_runtest_logreport(_DemoReport(nid, "teardown", "passed", d * 0.1))
        plugin.pytest_runtest_logfinish(nid, None)
        if i == 30:
            plugin.pytest_warning_recorded(
                warnings.WarningMessage(
                    DeprecationWarning("datetime.utcnow() ist veraltet"),
                    DeprecationWarning, "demo.py", 1,
                ), "runtest", nid, None,
            )

    time.sleep(0.8)
    plugin.pytest_sessionfinish(None, 0 if ok else 1)
    plugin.pytest_unconfigure(None)
    return 0 if ok else 1


if __name__ == "__main__":
    args = sys.argv[1:]
    if "--demo" in args or "--demo-ok" in args:
        raise SystemExit(run_demo(ok="--demo-ok" in args))
    raise SystemExit(pytest.main(
        ["-p", "no:terminal", "-o", "addopts=", "--assert=plain", *args],
        plugins=[LUMSPolarOffice()],
    ))
