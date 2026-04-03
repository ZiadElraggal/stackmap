from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

MascotState = Literal["idle", "scanning", "happy"]

WORKING_NAME = "Prism"
DISPLAY_LABEL = "Prism"
ALT_NAMES = (
    "Luma",
    "Pico",
    "Glyph",
    "Beacon",
    "Facet",
    "Nova",
    "Ping",
    "Nori",
    "Pixel",
    "Scout",
)
STATES: tuple[MascotState, ...] = ("idle", "scanning", "happy")


@dataclass(frozen=True)
class MascotSizing:
    cli_width: int = 24
    cli_min_terminal_width: int = 40
    app_loader_size: int = 72
    empty_state_size: int = 84
    hero_size: int = 128


@dataclass(frozen=True)
class MascotMotionPolicy:
    allow_default_animation: bool = True
    reduced_motion_disables_animation: bool = True
    terminal_success_hold_ms: int = 180
    terminal_frame_interval_ms: int = 180


SIZING = MascotSizing()
MOTION = MascotMotionPolicy()
