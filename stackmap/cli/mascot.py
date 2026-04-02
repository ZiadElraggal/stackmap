from __future__ import annotations

import os
import sys
import threading
import time
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Iterator

from rich.align import Align
from rich.console import Console, Group, RenderableType
from rich.live import Live

from rich.text import Text

from stackmap.mascot import DISPLAY_LABEL, MOTION, SIZING

MASCOT_FRAME_INTERVAL = MOTION.terminal_frame_interval_ms / 1000
SUCCESS_HOLD_SECONDS = MOTION.terminal_success_hold_ms / 1000


_BASE_ROWS = [
    "......hhhhhhhh......",  # row 0:  antenna glow
    ".......hhhhhh.......",  # row 1:  antenna tip
    "........aa..........",  # row 2:  antenna mast
    "......cccccccc......",  # row 3:  head top (diamond taper)
    ".....cccccccccc.....",  # row 4:  head upper
    "....cccccccccccc....",  # row 5:  head mid
    "...ccvvvvvvvvvvcc...",  # row 6:  visor top
    "R..ccvvee..eevvcc..r",  # row 7:  eyes row (R/r = ray emitter dots)
    "R..ccvvee..eevvcc..r",  # row 8:  eyes bottom
    "...ccvvvvvvvvvvcc...",  # row 9:  visor bottom / scan target
    "....cccccccccccc....",  # row 10: head bottom
    "....bbblllllllbb....",  # row 11: belt with LEDs
    "...bbccccccccccbb...",  # row 12: torso top + arm shoulders
    "..ga.cccccccccc.ag..",  # row 13: arms out + torso
    "..g..cccccccccc..g..",  # row 14: arm glow tips + torso bottom
    ".....cc.tt.tt.cc....",  # row 15: hip joints + leg tops
    ".....cc.tt.tt.cc....",  # row 16: legs
    "....ccc.tt.tt.ccc...",  # row 17: feet (wider)
]




@dataclass(frozen=True)
class MascotCapabilities:
    enabled: bool
    animated: bool
    reason: str | None = None


def detect_cli_mascot_capabilities(console: Console) -> MascotCapabilities:
    env_disable = os.getenv("STACKMAP_NO_MASCOT", "").strip().lower()
    if env_disable in {"1", "true", "yes", "on"}:
        return MascotCapabilities(enabled=False, animated=False, reason="disabled by env")
    if os.getenv("CI"):
        return MascotCapabilities(enabled=False, animated=False, reason="ci environment")
    if not console.is_terminal or not sys.stdout.isatty():
        return MascotCapabilities(enabled=False, animated=False, reason="non-tty")
    if console.options.ascii_only:
        return MascotCapabilities(enabled=False, animated=False, reason="ascii-only terminal")
    if console.size.width < SIZING.cli_min_terminal_width:
        return MascotCapabilities(enabled=False, animated=False, reason="narrow terminal")
    return MascotCapabilities(enabled=True, animated=True)


def _row_with_scan(row: str, phase: int) -> str:
    if phase < 0 or phase >= len(row):
        return row
    chars = list(row)
    if chars[phase] in {".", " "}:
        chars[phase] = "s"
    return "".join(chars)


def _rows_for_state(state: str, tick: int) -> list[str]:
    rows = list(_BASE_ROWS)

    # --- Blink (idle only, every 16th tick for 1 frame) ---
    blink = state == "idle" and tick % 20 in {14, 15}
    if blink:
        rows[7] = rows[7].replace("ee", "..")
        rows[8] = rows[8].replace("ee", "..")

    # --- Happy: squint eyes (remove bottom eye row), add mouth ---
    if state == "happy":
        rows[7] = "R..ccvvee..eevvcc..r"  # eyes stay
        rows[8] = "R..ccvv......vvcc..r"  # bottom eye row cleared (squint)
        rows[9] = "...ccvv..mm..vvcc..."  # mouth pixels

    # --- Scan line: sweep a highlight across visor rows ---
    visor_indices = [6, 7, 8, 9]
    if state == "scanning":
        scan_col = (tick % 12) + 3  # sweep columns 3..14
    else:
        scan_col = (tick % 16) + 2  # slower idle sweep

    for vi in visor_indices:
        row_chars = list(rows[vi])
        col = scan_col + (vi - 7)  # offset per row for diagonal sweep
        if 0 <= col < len(row_chars) and row_chars[col] in {"v", "."}:
            row_chars[col] = "s"
        rows[vi] = "".join(row_chars)

    # --- Ray emitter dots: pulse on/off with tick ---
    if state == "scanning":
        show_rays = True  # always visible when scanning
    elif state == "happy":
        show_rays = tick % 6 < 3  # slow blink
    else:
        show_rays = tick % 8 < 4  # medium blink

    if not show_rays:
        rows[7] = rows[7].replace("R", ".").replace("r", ".")
        rows[8] = rows[8].replace("R", ".").replace("r", ".")

    return rows



def _palette_for(state: str, tick: int) -> dict[str, str]:
    scanning = state == "scanning"
    led_phase = tick % 6  # for chase animation

    return {
        "c": "#1e2436",        # chassis
        "h": "rgb(123 142 168 / 0.30)",  # antenna glow
        "a": "#252a3a",        # arm/joint
        "v": "#0d1018",        # visor screen
        "e": "#4ADE80",        # eyes
        "s": "rgb(111 255 176 / 0.85)" if scanning else "rgb(74 222 128 / 0.40)",  # scan highlight
        "l": "#4ADE80" if scanning else "rgb(74 222 128 / 0.35)",  # belt LEDs
        "b": "#252a3a",        # belt frame
        "t": "#1a1f2e",        # legs
        "g": "rgb(74 222 128 / 0.30)",  # arm glow tips
        "m": "rgb(123 142 168 / 0.40)",  # mouth (happy state)
        "R": "#4ADE80" if scanning else "rgb(74 222 128 / 0.50)",  # left ray emitter
        "r": "#4ADE80" if scanning else "rgb(74 222 128 / 0.50)",  # right ray emitter
    }



def _render_pixel_row(row: str, palette: dict[str, str]) -> Text:
    line = Text(no_wrap=True)
    for cell in row:
        if cell == ".":
            line.append("  ")
            continue
        if cell == " ":
            line.append("  ")
            continue
        line.append("██", style=palette.get(cell, "#1e2436"))
    return line

def _render_dots(state: str, tick: int) -> Text:
    text = Text(justify="center")
    count = 5
    for index in range(count):
        active = False
        if state == "scanning":
            # chase pattern: one dot lights at a time
            active = index == tick % count
        elif state == "happy":
            # all lit
            active = True
        else:
            # idle: center always lit, others pulse
            active = index == 2 or (tick + index) % 6 == 0
        style = "#4ADE80" if active else "rgb(74 222 128 / 0.20)"
        text.append("●", style=style)
        if index < count - 1:
            text.append("  ")
    return text


def render_cli_mascot(label: str, state: str = "scanning", tick: int = 0) -> RenderableType:
    palette = _palette_for(state, tick)
    rows = [_render_pixel_row(row, palette) for row in _rows_for_state(state, tick)]
    dots = _render_dots(state, tick)
    status = Text(label, style="bold #d1d5db", justify="center")
    return Align.center(
        Group(
            *rows,
            Text(""),
            dots,
            Text(""),
            status,
            Text(DISPLAY_LABEL, style="dim", justify="center"),
        )
    )


class _MascotStatus:
    def __init__(self, console: Console, label: str, capabilities: MascotCapabilities) -> None:
        self.console = console
        self.label = Text.from_markup(label).plain
        self.capabilities = capabilities
        self._tick = 0
        self._state = "scanning"
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._live: Live | None = None

    def __enter__(self) -> "_MascotStatus":
        if not self.capabilities.enabled:
            self.console.print(f"[bold]{self.label}[/bold]")
            return self
        self._live = Live(
            render_cli_mascot(self.label, self._state, self._tick),
            console=self.console,
            refresh_per_second=max(1, int(1 / MASCOT_FRAME_INTERVAL)),
            transient=True,
        )
        self._live.start()
        self._thread = threading.Thread(target=self._run, name="stackmap-mascot", daemon=True)
        self._thread.start()
        return self

    def _run(self) -> None:
        while not self._stop_event.wait(MASCOT_FRAME_INTERVAL):
            self._tick += 1
            if self._live is not None:
                self._live.update(render_cli_mascot(self.label, self._state, self._tick), refresh=True)

    def set_label(self, label: str) -> None:
        self.label = Text.from_markup(label).plain
        if self._live is not None:
            self._live.update(render_cli_mascot(self.label, self._state, self._tick), refresh=True)

    def set_state(self, state: str) -> None:
        self._state = state
        if self._live is not None:
            self._live.update(render_cli_mascot(self.label, self._state, self._tick), refresh=True)

    def __exit__(self, exc_type, exc, tb) -> None:  # type: ignore[no-untyped-def]
        if self.capabilities.enabled and self._live is not None and exc_type is None:
            self.set_state("happy")
            time.sleep(SUCCESS_HOLD_SECONDS)
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=0.5)
        if self._live is not None:
            self._live.stop()


@contextmanager
def mascot_status(console: Console, label: str) -> Iterator[_MascotStatus]:
    status = _MascotStatus(console, label, detect_cli_mascot_capabilities(console))
    try:
        yield status.__enter__()
    except BaseException as exc:
        status.__exit__(type(exc), exc, exc.__traceback__)
        raise
    else:
        status.__exit__(None, None, None)