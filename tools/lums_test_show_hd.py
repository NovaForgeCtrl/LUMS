#!/usr/bin/env python3
"""LUMS Polar Office HD – calm real-Pytest dashboard with a homecoming finale.

Uses the existing lums_test_show.LUMSPolarOffice adapter for all real Pytest
lifecycle events and statistics. It replaces only the terminal presentation.

Run from the repository root:
    .venv/bin/python tools/lums_test_show_hd.py

The display re-reads terminal dimensions on each render and reflows panels
when the terminal is resized. Set LUMS_FPS=3..5 to tune refresh rate; default 4.
"""
from __future__ import annotations

import os
import shutil
import sys
import threading
import time

import pytest
from rich import box
from rich.console import Console, Group
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

import lums_test_show as legacy
from lums_polar_office_preview_hd import aquarium_art, homecoming_render, scene_render


def _fps() -> int:
    try:
        return max(3, min(5, int(os.environ.get("LUMS_FPS", "4"))))
    except ValueError:
        return 4


FPS = _fps()


class LUMSPolarOfficeHD(legacy.LUMSPolarOffice):
    """Keep the real Pytest plugin; provide a stable HD screen and finale."""

    def __init__(self) -> None:
        super().__init__()
        # Keep width/height unset: Rich then queries the real TTY dimensions
        # on every render, including after a live terminal resize.
        self.console = Console(color_system="256", highlight=False)
        # Read the real output TTY once, then debounce subsequent resize events.
        # Windows terminals can report transient intermediate sizes while the
        # window is being dragged; adopting every sample makes the whole layout
        # jump between two geometries.
        self._stable_terminal_size = self._read_terminal_size()
        self._candidate_terminal_size = None
        self._candidate_terminal_since = 0.0
        self._resize_debounce_seconds = 0.85
        self.render_width, self.render_height = self._stable_terminal_size
        self.final_elapsed = 0.0
        self.final_success = False
        self.final_animation_started = 0.0

    @staticmethod
    def _bounded_size(columns: int, lines: int) -> tuple[int, int]:
        return (
            max(40, min(240, int(columns))),
            max(16, min(80, int(lines))),
        )

    def _read_terminal_size(self) -> tuple[int, int]:
        """Read geometry from the actual output TTY, with a safe fallback."""
        try:
            columns, lines = os.get_terminal_size(self.console.file.fileno())
        except (AttributeError, OSError, ValueError, TypeError):
            size = shutil.get_terminal_size(fallback=(120, 30))
            columns, lines = size.columns, size.lines
        if columns <= 0 or lines <= 0:
            fallback = shutil.get_terminal_size(fallback=(120, 30))
            columns = columns or fallback.columns
            lines = lines or fallback.lines
        return self._bounded_size(columns, lines)

    def _sync_terminal_size(self) -> tuple[int, int]:
        """Apply a resize only after the TTY reports it steadily for 0.85 s."""
        observed = self._read_terminal_size()
        now = time.monotonic()
        stable = self._stable_terminal_size

        if observed == stable:
            self._candidate_terminal_size = None
            self._candidate_terminal_since = 0.0
        elif observed != self._candidate_terminal_size:
            self._candidate_terminal_size = observed
            self._candidate_terminal_since = now
        elif now - self._candidate_terminal_since >= self._resize_debounce_seconds:
            # Commit one settled geometry. Ignore short-lived intermediate sizes.
            self._stable_terminal_size = observed
            self._candidate_terminal_size = None
            self._candidate_terminal_since = 0.0

        self.render_width, self.render_height = self._stable_terminal_size
        return self._stable_terminal_size

    def pytest_collection_finish(self, session) -> None:
        self.total = len(session.items)
        self.started = time.monotonic()

        if self.console.is_terminal:
            self.live = Live(
                self.render(),
                console=self.console,
                refresh_per_second=FPS,
                auto_refresh=False,
                # Alternate screen keeps the dashboard isolated from scrollback.
                # Geometry is re-read from the TTY at each render after resizing.
                screen=True,
                transient=False,
                vertical_overflow="crop",
                redirect_stdout=False,
                redirect_stderr=False,
            )
            self.live.start()
            self.thread = threading.Thread(target=self.animate, daemon=True)
            self.thread.start()
        else:
            self.console.print(
                f"🐧 LUMS Polar Office HD – {self.total} echte Testakten geladen"
            )

    def animate(self) -> None:
        interval = 1.0 / FPS
        deadline = time.monotonic()
        while not self.stop.is_set():
            now = time.monotonic()
            elapsed = max(0.0, now - self.started) if self.started else 0.0
            with self.lock:
                self.frame = int(elapsed * FPS)

            live = self.live
            if live is not None:
                live.update(self.render(), refresh=True)

            # Skip missed deadlines; never burst several redraws after a pause.
            deadline += interval
            delay = deadline - time.monotonic()
            if delay <= 0:
                deadline += (int((-delay) // interval) + 1) * interval
                delay = max(0.0, deadline - time.monotonic())
            if self.stop.wait(delay):
                break

    def render(self):
        with self.lock:
            frame = self.frame
            done = self.done
            total = self.total
            counts = dict(self.counts)
            current_id = self.current_id
            stage = self.stage
            events = list(self.events)
            history = list(self.history)
            slowest = list(self.slowest)
            test_started = self.test_started
            started = self.started
            warnings_present = bool(self.warnings)

        now = time.monotonic()
        elapsed = max(0.0, now - started) if started else 0.0
        running = done < total
        pending = max(0, total - done - (1 if running else 0))
        percent = int(done * 100 / total) if total else 0
        eta = elapsed / done * (total - done) if done and running else 0.0
        rate = done / elapsed if elapsed > 0 else 0.0
        current_elapsed = max(0.0, now - test_started) if current_id and test_started else 0.0

        width, terminal_height = self._sync_terminal_size()
        # 26 raster rows -> 13 terminal rows using upper-half block pixels.
        # Combined with panel title/subtitle/borders this is exactly 17 rows.
        if terminal_height >= 24:
            # Use the available vertical space for the landscape as well.
            # Keep the dashboard strip at 10 rows and the headline at one row.
            scene_panel_height = max(17, min(60, terminal_height - 11))
        else:
            scene_panel_height = max(5, terminal_height - 7)
        scene_pixel_height = max(16, (scene_panel_height - 4) * 2)
        if width >= 72 and terminal_height >= 24:
            scene_content = scene_render(elapsed * 0.18, width - 4, scene_pixel_height)
            scene_subtitle = "[dim]Aurora · ruhige HD-Ansicht · unabhängige Animation[/]"
        else:
            scene_content = Text(
                "🐧  Pingu braucht etwas mehr Platz – empfohlen: mindestens 72 × 24 Zeichen",
                style="bold bright_cyan", justify="center", no_wrap=True,
                overflow="ellipsis",
            )
            scene_subtitle = "[dim]Kompaktansicht[/]"
        scene = Panel(
            scene_content,
            title="[bold bright_cyan]🐧 Pingu's Polar Playground[/]",
            subtitle=scene_subtitle,
            border_style="bright_blue",
            padding=(0, 1),
            width=width,
            height=scene_panel_height,
        )

        headline = Text(
            "❄  LUMS POLAR OFFICE  •  PENGUIN TEST ENGINE  ❄",
            style="bold bright_cyan",
            justify="center",
            no_wrap=True,
        )

        # Every value in this panel is fed by the real Pytest lifecycle hooks.
        case = Text(no_wrap=True, overflow="ellipsis")
        case.append("📄 AKTUELLE TESTAKTE\n", style="bold cyan")
        if current_id:
            stem, name = legacy.split_nodeid(current_id)
            case.append(f"● {name}\n", style="bold white")
            case.append(f"{stem}\n", style="dim")
        elif total and done >= total:
            case.append("🎉 Alle Akten bearbeitet\n", style="bold green")
            case.append("Pingu darf Feierabend machen.\n", style="dim")
        else:
            case.append("💤 Warte auf die nächste Testakte\n", style="dim")
            case.append("Die Verarbeitung läuft unabhängig weiter\n", style="dim")

        stage_idx = legacy.STAGE_INDEX.get(stage, -1)
        stage_text = Text()
        for i, (_key, label) in enumerate(legacy.STAGES):
            if i:
                stage_text.append("  ", style="dim")
            if stage_idx == i:
                stage_text.append("● " + label, style="bold yellow")
            elif stage_idx > i:
                stage_text.append("✔ " + label, style="green")
            else:
                stage_text.append("○ " + label, style="grey50")
        case.append(stage_text)
        case.append("\n")
        eta_text = f"~{eta:.0f} s" if done and running else "–"
        case.append(f"⏱ Gesamt {elapsed:.1f} s  ·  ETA {eta_text}\n", style="white")
        case.append(
            f"⚡ {rate:.1f} Tests/s  ·  Testdauer {current_elapsed:.2f} s\n",
            style="white",
        )

        if counts["failed"]:
            case.append("🚨 MIT FEHLERN\n", style="bold white on red")
        elif total and done >= total:
            case.append("✅ ALLE AKTEN ABGELEGT\n", style="bold black on green")
        else:
            case.append("🐧 PINGU BLEIBT DRAN\n", style="bold yellow")

        if events:
            status, name, _stem, duration = events[-1]
            icon, color = legacy.STATUS[status]
            case.append(f"Zuletzt: {icon} {name} · {legacy.fmt_dur(duration)}", style=color)
        else:
            case.append("Zuletzt: Noch keine abgeschlossene Akte", style="dim")

        lower_height = max(5, min(10, terminal_height - scene_panel_height - 1))
        case_panel = Panel(
            case,
            title="[bold yellow]📂 Teststeuerung[/]",
            border_style="yellow",
            padding=(0, 1),
            height=lower_height,
        )

        # Real counters + a compact view of recent and slow tests.
        stat_parts = [
            legacy.segmented_bar(
                max(18, width // 3 - 10),
                counts["passed"], counts["failed"], counts["skipped"],
                total, frame, running,
            )
        ]
        counters = Text(no_wrap=True)
        counters.append(f"📥 {pending}  ", style="bold yellow")
        counters.append(f"📝 {1 if running else 0}  ", style="bold bright_cyan")
        counters.append(f"✅ {counts['passed']}  ", style="bold green")
        counters.append(f"🚨 {counts['failed']}  ", style="bold red")
        counters.append(f"⏩ {counts['skipped']}", style="bold yellow")
        stat_parts.append(counters)

        spark = Text(no_wrap=True)
        spark.append("Rhythmus ", style="dim")
        blocks = "▁▂▃▄▅▆▇█"
        sample = history[-14:]
        peak = max((d for _, d in sample), default=0.0) or 1e-9
        for status, duration in sample:
            idx = min(7, int((duration / peak) ** 0.5 * 7.999))
            spark.append(blocks[idx], style=legacy.STATUS[status][1])
        stat_parts.append(spark)

        if events:
            status, name, _stem, duration = events[-1]
            icon, color = legacy.STATUS[status]
            stat_parts.append(Text(f"Letzte Akte: {icon} {name[:25]} · {legacy.fmt_dur(duration)}", style=color, no_wrap=True))
        for rank, (duration, nodeid) in enumerate(slowest[:2], 1):
            _stem, name = legacy.split_nodeid(nodeid)
            style = "bold red" if rank == 1 else "white"
            stat_parts.append(Text(f"Langsam {rank}: {name} · {legacy.fmt_dur(duration)}", style=style, no_wrap=True, overflow="ellipsis"))

        subtitle = f"{percent}% · {done}/{total} erledigt"
        if warnings_present:
            subtitle += f" · 🔔 {self.warning_count()} Warnungen"
        stats_panel = Panel(
            Group(*stat_parts),
            title="[bold green]📊 Bürostatistik & Akten[/]",
            subtitle=subtitle,
            border_style="green",
            padding=(0, 1),
            height=lower_height,
        )

        aquarium_width = max(12, width // 4 - 7)
        aquarium_panel = Panel(
            Group(
                aquarium_art(elapsed * 0.18, aquarium_width),
                Text("🐠 Fische ziehen ruhig ihre Runden", style="bright_cyan", no_wrap=True),
            ),
            title="[bold cyan]🐟 Aquarium[/]",
            border_style="cyan",
            padding=(0, 1),
            height=lower_height,
        )

        # Reflow columns as the user resizes the terminal. The aquarium gets
        # its own column only when there is enough horizontal room; otherwise
        # the two important live panels keep readable widths.
        lower = Table.grid(expand=True, padding=(0, 0))
        if width >= 108:
            lower.add_column(ratio=5)
            lower.add_column(ratio=5)
            lower.add_column(ratio=4)
            lower.add_row(case_panel, stats_panel, aquarium_panel)
            lower_content = lower
        elif width >= 76:
            lower.add_column(ratio=1)
            lower.add_column(ratio=1)
            lower.add_row(case_panel, stats_panel)
            lower_content = lower
        else:
            compact = Text(no_wrap=True, overflow="ellipsis")
            compact.append(f"🐧 {done}/{total} Tests · {percent}%  ", style="bold bright_cyan")
            compact.append(
                f"✅ {counts['passed']}  🚨 {counts['failed']}  ⏩ {counts['skipped']}\n",
                style="white",
            )
            if current_id:
                _stem, current_name = legacy.split_nodeid(current_id)
                compact.append(current_name, style="bold yellow")
            else:
                compact.append("Warte auf Testaktivität", style="dim")
            lower_content = Panel(compact, title="[bold green]Status[/]", height=lower_height)

        return Group(headline, scene, lower_content)

    def _final_success(self, exitstatus: int) -> bool:
        return (
            int(exitstatus) == 0
            and self.done == self.total
            and not self.counts["failed"]
            and not self.counts["skipped"]
            and not self.collection_errors
        )

    def _finale(self, progress: float, success: bool, elapsed: float):
        width, terminal_height = self._sync_terminal_size()
        panel_height = max(12, min(60, terminal_height - 2))
        phase = (
            "Pingu packt seine Aktentasche ..." if progress < 0.18 else
            "Pingu stapft durch den Schnee nach Hause ..." if progress < 0.78 else
            "Nur noch ein paar Schritte bis zum warmen Licht ..." if progress < 1.0 else
            "Zuhause angekommen – Feierabend! ☕"
        )
        side_by_side = width >= 108
        left_width = width // 2 if side_by_side else width
        left_height = panel_height if side_by_side else max(10, min(17, panel_height - 8))
        report_height = panel_height if side_by_side else max(8, panel_height - left_height)
        if width >= 72 and terminal_height >= 24 and left_height >= 16:
            finale_visual = homecoming_render(
                t=max(0.0, time.monotonic() - self.final_animation_started) * 1.65,
                width=max(44, left_width - 4),
                height=max(24, (left_height - 4) * 2),
                progress=progress,
            )
        else:
            finale_visual = Text("🐧   💼   →   🏠", style="bold bright_cyan", justify="center")
        left_content = Group(
            finale_visual,
            Text("🐧 " + phase, style="bold bright_cyan", justify="center", no_wrap=True),
        )
        left_panel = Panel(
            left_content,
            title="[bold bright_cyan]🌙 Pingu macht Feierabend[/]",
            subtitle="[dim]Mit Aktentasche auf dem Heimweg[/]",
            border_style="bright_blue",
            padding=(0, 1),
            width=left_width,
            height=left_height,
        )

        counts = dict(self.counts)
        result_table = Table.grid(expand=True, padding=(0, 0))
        result_table.add_column(ratio=1)
        result_table.add_column(justify="right", width=12)
        result_table.add_row(
            Text("Ergebnis", style="bold"),
            Text("ERFOLGREICH" if success else "PRÜFEN", style="bold green" if success else "bold red"),
        )
        result_table.add_row(Text("Bestanden", style="green"), Text(str(counts["passed"]), style="bold green"))
        result_table.add_row(Text("Fehlgeschlagen", style="red"), Text(str(counts["failed"]), style="bold red"))
        result_table.add_row(Text("Übersprungen", style="yellow"), Text(str(counts["skipped"]), style="bold yellow"))
        result_table.add_row(Text("Abgeschlossen"), Text(f"{self.done}/{self.total}"))
        result_table.add_row(Text("Laufzeit"), Text(f"{elapsed:.2f} s"))
        result_table.add_row(Text("Warnungen"), Text(str(self.warning_count())))

        slow_rows = [Text("🐢 LANGSAMSTE AKTEN", style="bold yellow")]
        visible_slowest = 6 if side_by_side else max(1, min(3, report_height - 10))
        for rank, (duration, nodeid) in enumerate(self.slowest[:visible_slowest], 1):
            _stem, name = legacy.split_nodeid(nodeid)
            slow_rows.append(
                Text(f"{rank}. {name} · {legacy.fmt_dur(duration)}", no_wrap=True, overflow="ellipsis")
            )
        if not self.slowest:
            slow_rows.append(Text("Noch keine Laufzeitdaten", style="dim"))

        result_footer = Text(
            "Alle Vorgänge abgeschlossen. Pingu darf nach Hause."
            if success else
            "Pingu nimmt offene Prüfvermerke mit nach Hause.",
            style="green" if success else "yellow",
            no_wrap=True,
            overflow="ellipsis",
        )
        right_panel = Panel(
            Group(result_table, Text(""), *slow_rows, Text(""), result_footer),
            title="[bold green]📋 Abschlussbericht[/]",
            subtitle=f"{self.done}/{self.total} Tests · {elapsed:.2f} Sekunden",
            border_style="green" if success else "yellow",
            padding=(0, 1),
            width=(width - width // 2) if side_by_side else width,
            height=report_height,
        )

        if side_by_side:
            row = Table.grid(expand=True, padding=(0, 0))
            row.add_column(width=width // 2)
            row.add_column(width=width - width // 2)
            row.add_row(left_panel, right_panel)
            return Group(row)
        return Group(left_panel, right_panel)

    def _print_details(self) -> None:
        # Keep the full diagnostics that the legacy report showed after its table.
        for nodeid, detail in self.failures:
            self.console.print(Panel(
                Text(str(detail)[:12000]),
                title=Text.assemble(("🚨 Fehlerakte: ", "bold red"), (nodeid, "white")),
                border_style="red",
            ))
        for nodeid, detail in self.skips:
            self.console.print(Panel(
                Text(str(detail)[:3000]),
                title=Text.assemble(("⏩ Prüfvermerk: ", "bold yellow"), (nodeid, "white")),
                border_style="yellow",
            ))
        if self.warnings:
            body = Text()
            ranked = sorted(self.warnings.items(), key=lambda item: -item[1])
            for (category, message), count in ranked[:8]:
                body.append(f"{count}× ", style="bold yellow")
                body.append(f"{category}: ", style="yellow")
                body.append(message.strip()[:300] + "\n")
            if len(ranked) > 8:
                body.append(f"\n… und {len(ranked) - 8} weitere", style="dim")
            self.console.print(Panel(body, title="🔔 Warnungen", border_style="yellow"))
        for detail in self.collection_errors:
            self.console.print(Panel(
                Text(str(detail)[:12000]),
                title="🚨 Fehler bei der Testsuche",
                border_style="red",
            ))

    def pytest_sessionfinish(self, session, exitstatus) -> None:
        """Finish with a visible walk-home animation and a persistent report."""
        if self.reported:
            return
        self.reported = True
        self.stop.set()
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=3)

        elapsed = max(0.0, time.monotonic() - self.started) if self.started else 0.0
        self.final_elapsed = elapsed
        self.final_success = self._final_success(int(exitstatus))
        self.final_animation_started = time.monotonic()
        live = self.live

        if live is not None:
            # Slow, deliberate final sequence: 7 walking stages, then a longer
            # hold at the lit house. The report remains visible throughout.
            for step in range(7):
                progress = step / 6
                live.update(self._finale(progress, self.final_success, elapsed), refresh=True)
                time.sleep(0.72)
            live.update(self._finale(1.0, self.final_success, elapsed), refresh=True)
            time.sleep(2.2)
            live.stop()
            self.live = None

        # Live's alternate screen is now closed. Print the same final tableau
        # into the normal scrollback so it remains visible after the animation.
        self.console.print(self._finale(1.0, self.final_success, elapsed))
        self._print_details()


def main() -> int:
    args = sys.argv[1:]
    return int(pytest.main(
        ["-p", "no:terminal", "-o", "addopts=", *args],
        plugins=[LUMSPolarOfficeHD()],
    ))


if __name__ == "__main__":
    raise SystemExit(main())
