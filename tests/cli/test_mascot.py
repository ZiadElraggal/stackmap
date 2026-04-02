from __future__ import annotations

import io

from rich.console import Console

from stackmap.cli.mascot import detect_cli_mascot_capabilities, render_cli_mascot


def test_detect_cli_mascot_capabilities_disables_for_non_tty(monkeypatch) -> None:
    monkeypatch.delenv("STACKMAP_NO_MASCOT", raising=False)
    monkeypatch.delenv("CI", raising=False)
    monkeypatch.setattr("sys.stdout.isatty", lambda: False)

    console = Console(file=io.StringIO(), force_terminal=False, width=100)
    capabilities = detect_cli_mascot_capabilities(console)

    assert capabilities.enabled is False
    assert capabilities.reason == "non-tty"


def test_detect_cli_mascot_capabilities_respects_disable_env(monkeypatch) -> None:
    monkeypatch.setenv("STACKMAP_NO_MASCOT", "1")
    monkeypatch.setattr("sys.stdout.isatty", lambda: True)

    console = Console(file=io.StringIO(), force_terminal=True, width=100)
    capabilities = detect_cli_mascot_capabilities(console)

    assert capabilities.enabled is False
    assert capabilities.reason == "disabled by env"


def test_render_cli_mascot_includes_status_and_label() -> None:
    console = Console(file=io.StringIO(), force_terminal=True, width=100, color_system="truecolor")
    console.print(render_cli_mascot("Scanning infrastructure...", state="scanning", tick=2))

    output = console.file.getvalue()
    assert "Scanning infrastructure..." in output


def test_render_cli_mascot_happy_state_renders_without_crashing() -> None:
    console = Console(file=io.StringIO(), force_terminal=True, width=100, color_system="truecolor")
    console.print(render_cli_mascot("Done", state="happy", tick=2))

    output = console.file.getvalue()
    assert "Done" in output
