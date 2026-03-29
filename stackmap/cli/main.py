import json
import shutil
import subprocess
import tempfile
import threading
import time
import webbrowser
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import typer
from rich.console import Console
from rich.table import Table

from stackmap.parsers.base import BaseParser, StackMapIR
from stackmap.parsers.registry import (
    build_parser as _registry_build_parser,
    detect_source_type as _registry_detect_source_type,
    parse_source as _registry_parse_source,
)
from stackmap.repo_scan import (
    DiscoveredSource,
    build_sam_templates,
    discover_sources,
    merge_sources,
    parse_discovered_sources,
)
from stackmap.webapp import get_preferred_public_dir

app = typer.Typer(
    name="stackmap",
    help="Architecture diagrams that generate themselves from your infrastructure code.",
    no_args_is_help=True,
)
console = Console()


class _LiveGraphState:
    def __init__(self, ir: StackMapIR) -> None:
        self._lock = threading.Lock()
        self._ir: dict[str, Any] = ir.to_dict()
        self._version = 1

    def snapshot(self) -> tuple[int, dict[str, Any]]:
        with self._lock:
            return self._version, self._ir

    def update(self, ir: StackMapIR) -> int:
        with self._lock:
            self._version += 1
            self._ir = ir.to_dict()
            return self._version


def _detect_source_type(source_path: str) -> str:
    """Auto-detect infrastructure source type from file extension or content."""
    return _registry_detect_source_type(source_path)


def _build_parser(source_type: str) -> BaseParser:
    return _registry_build_parser(source_type)


def _parse_source(source_path: str) -> tuple[str, StackMapIR]:
    return _registry_parse_source(source_path)


def _validate_include_types(include: list[str]) -> set[str] | None:
    if not include:
        return None
    normalized = {value.strip().lower() for value in include if value.strip()}
    supported = {"terraform", "cloudformation", "sam"}
    invalid = sorted(normalized - supported)
    if invalid:
        raise typer.BadParameter(
            f"Unsupported include type(s): {', '.join(invalid)}. "
            f"Supported types: {', '.join(sorted(supported))}"
        )
    return normalized


def _pull_remote_terraform_state(target_path: Path, terraform_dir: Path) -> Path:
    """Pull remote Terraform state via `terraform state pull`."""
    try:
        result = subprocess.run(
            ["terraform", "state", "pull"],
            cwd=terraform_dir,
            check=True,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError as exc:
        raise RuntimeError(
            "Terraform CLI is not installed or not on PATH. "
            "Install Terraform to pull remote state."
        ) from exc
    except subprocess.CalledProcessError as exc:
        stderr = (exc.stderr or "").strip()
        stdout = (exc.stdout or "").strip()
        detail = stderr if stderr else stdout
        raise RuntimeError(
            "Failed to pull remote Terraform state with `terraform state pull`.\n"
            f"Directory: {terraform_dir}\n{detail}"
        ) from exc

    target_path.parent.mkdir(parents=True, exist_ok=True)
    target_path.write_text(result.stdout)
    return target_path


def _resolve_source_with_remote_pull(
    source: str,
    terraform_dir: str | None,
    auto_pull_remote: bool,
) -> Path:
    source_path = Path(source)
    if source_path.exists() or not auto_pull_remote:
        return source_path

    looks_like_tfstate = source_path.suffix == ".tfstate" or source_path.name.endswith(".tfstate")
    if not looks_like_tfstate:
        return source_path

    tf_dir = Path(terraform_dir).resolve() if terraform_dir else Path.cwd()
    if not tf_dir.exists():
        raise RuntimeError(f"Terraform directory not found: {tf_dir}")

    should_pull = typer.confirm(
        f"Source file not found: {source_path}\n"
        f"Pull remote Terraform state from {tf_dir} using `terraform state pull`?",
        default=True,
    )
    if not should_pull:
        return source_path

    pulled = _pull_remote_terraform_state(source_path, tf_dir)
    console.print(f"[green]✓[/green] Pulled remote state to [cyan]{pulled}[/cyan]")
    return pulled


def _scan_repository_sources(
    root: Path,
    include_types: set[str] | None,
    max_depth: int,
    strict_linking: bool,
    sam_build: bool,
    terraform_pull_missing: bool,
) -> tuple[StackMapIR, list[DiscoveredSource], list[str], dict[str, int]]:
    discovered, missing_tfstate_dirs = discover_sources(
        root=root,
        include_types=include_types,
        max_depth=max_depth,
    )
    warnings: list[str] = []

    if terraform_pull_missing and (include_types is None or "terraform" in include_types):
        if missing_tfstate_dirs:
            should_pull = typer.confirm(
                f"Found {len(missing_tfstate_dirs)} Terraform directories without state files. "
                "Pull remote state using `terraform state pull`?",
                default=True,
            )
            if should_pull:
                for tf_dir in missing_tfstate_dirs:
                    target = tf_dir / "terraform.tfstate"
                    try:
                        pulled = _pull_remote_terraform_state(target, tf_dir)
                        discovered.append(DiscoveredSource(path=pulled, source_type="terraform"))
                    except Exception as exc:  # pragma: no cover
                        warnings.append(f"{tf_dir}: {exc}")

    if sam_build and (include_types is None or "sam" in include_types):
        discovered, sam_warnings = build_sam_templates(discovered)
        warnings.extend(sam_warnings)

    parsed, parse_errors = parse_discovered_sources(discovered)
    if not parsed:
        raise RuntimeError(
            "No parseable infrastructure sources found in repository scan. "
            "Add Terraform state, CloudFormation, or SAM templates."
        )

    merged = merge_sources(
        parsed,
        strict_linking=strict_linking,
        parse_errors=parse_errors,
    )
    all_warnings = warnings + parse_errors
    return merged.ir, merged.discovered, all_warnings, merged.link_counts


def _write_graph_json(path: Path, ir_data: dict[str, Any]) -> None:
    path.write_text(json.dumps(ir_data, indent=2))


def _has_dev_only_nuxt_entry(public_dir: Path) -> bool:
    index_path = public_dir / "index.html"
    if not index_path.exists():
        return False
    html = index_path.read_text()
    return "@vite/client" in html or "node_modules/nuxt/dist/app/entry.js" in html


def _watch_source_loop(
    source_path: Path,
    state: _LiveGraphState,
    watch_interval: float,
    stop_event: threading.Event,
    static_dir: Path,
    fallback_html: bool,
) -> None:
    last_mtime = source_path.stat().st_mtime_ns
    while not stop_event.is_set():
        time.sleep(watch_interval)
        try:
            current_mtime = source_path.stat().st_mtime_ns
        except FileNotFoundError:
            continue

        if current_mtime == last_mtime:
            continue

        last_mtime = current_mtime
        try:
            _, ir = _parse_source(str(source_path))
            version = state.update(ir)
            _, snapshot = state.snapshot()
            _write_graph_json(static_dir / "sample-data.json", snapshot)
            if fallback_html:
                from stackmap.export import export_ir_to_html

                export_ir_to_html(ir, static_dir / "index.html")
            console.print(
                f"[green]✓[/green] Reloaded graph from {source_path.name} "
                f"(v{version}, {len(ir.nodes)} resources)"
            )
        except Exception as exc:  # pragma: no cover
            console.print(f"[yellow]Watch parse error:[/yellow] {exc}")


class _StackMapRequestHandler(SimpleHTTPRequestHandler):
    def __init__(
        self,
        *args: Any,
        directory: str,
        state: _LiveGraphState,
        source_type: str,
        **kwargs: Any,
    ) -> None:
        self._state = state
        self._source_type = source_type
        super().__init__(*args, directory=directory, **kwargs)

    def _send_json(self, payload: dict[str, Any]) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        if path == "/api/graph":
            _, ir_data = self._state.snapshot()
            self._send_json(ir_data)
            return
        if path == "/api/version":
            version, _ = self._state.snapshot()
            self._send_json({"version": version})
            return
        if path == "/api/health":
            self._send_json({"status": "ok", "source_type": self._source_type})
            return

        if path not in {"/", ""}:
            requested = Path(self.directory) / path.lstrip("/")
            if not requested.exists():
                self.path = "/index.html"
        super().do_GET()

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A003
        return


@app.command()
def scan(
    source: str = typer.Option(
        "terraform.tfstate",
        help="Path to infrastructure source file (default: terraform.tfstate)",
    ),
    terraform_dir: str | None = typer.Option(
        None,
        help="Terraform working directory for remote state pull fallback",
    ),
    auto_pull_remote: bool = typer.Option(
        True,
        "--auto-pull-remote/--no-auto-pull-remote",
        help="When source is missing, offer to run `terraform state pull`",
    ),
    output: str = typer.Option("stackmap-output.json", help="Output file path"),
    format: str = typer.Option("json", help="Output format: json or html"),
) -> None:
    """Scan infrastructure source and generate an architecture map."""
    output_format = format.lower()
    if output_format not in {"json", "html"}:
        console.print(
            f"[red]Error:[/red] Format '{format}' not supported. Use 'json' or 'html'."
        )
        raise typer.Exit(1)

    try:
        source_path = _resolve_source_with_remote_pull(source, terraform_dir, auto_pull_remote)
    except RuntimeError as exc:
        console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(1)

    if not source_path.exists():
        console.print(f"[red]Error:[/red] Source file not found: {source}")
        raise typer.Exit(1)

    with console.status("[bold]Scanning infrastructure...[/bold]"):
        try:
            source_type, ir = _parse_source(source)
        except typer.BadParameter as exc:
            console.print(f"[red]Error:[/red] {exc}")
            raise typer.Exit(1)
        except Exception as exc:
            console.print(f"[red]Error:[/red] {exc}")
            raise typer.Exit(1)

    if output_format == "json":
        ir.write_json(output)
    elif output_format == "html":
        from stackmap.export import export_ir_to_html

        try:
            export_ir_to_html(ir, output)
        except RuntimeError as exc:
            console.print(f"[red]Error:[/red] {exc}")
            raise typer.Exit(1)

    table = Table(title="StackMap Scan Results", show_header=False)
    table.add_column("Metric", style="bold")
    table.add_column("Value", style="cyan")
    table.add_row("Source", source)
    table.add_row("Source type", source_type)
    table.add_row("Resources", str(len(ir.nodes)))
    table.add_row("Connections", str(len(ir.edges)))
    table.add_row("Groups", str(len(ir.groups)))
    table.add_row("Output", output)

    if ir.metadata.get("terraform_version"):
        table.add_row("Terraform", ir.metadata["terraform_version"])

    console.print()
    console.print(table)
    console.print(
        f"\n[green]✓[/green] Scanned {len(ir.nodes)} resources, "
        f"found {len(ir.edges)} connections, {len(ir.groups)} groups."
    )


@app.command("scan-repo")
def scan_repo(
    root: str = typer.Option(".", help="Repository root path"),
    include: list[str] = typer.Option(
        [],
        "--include",
        "-i",
        help="Source types to include (terraform, cloudformation, sam). Can be repeated.",
    ),
    max_depth: int = typer.Option(6, help="Maximum directory depth to scan"),
    strict_linking: bool = typer.Option(
        True,
        "--strict-linking/--loose-linking",
        help="Cross-source link confidence policy (strict=high confidence only).",
    ),
    sam_build: bool = typer.Option(
        False,
        "--sam-build/--no-sam-build",
        help="Run `sam build` for discovered SAM templates before parsing.",
    ),
    terraform_pull_missing: bool = typer.Option(
        False,
        "--terraform-pull-missing/--no-terraform-pull-missing",
        help="When Terraform *.tf exists without state, offer `terraform state pull`.",
    ),
    output: str = typer.Option("stackmap-repo-output.json", help="Output file path"),
    format: str = typer.Option("json", help="Output format: json or html"),
) -> None:
    """Scan a repository for Terraform/CloudFormation/SAM sources and merge into one map."""
    output_format = format.lower()
    if output_format not in {"json", "html"}:
        console.print(
            f"[red]Error:[/red] Format '{format}' not supported. Use 'json' or 'html'."
        )
        raise typer.Exit(1)

    root_path = Path(root).resolve()
    if not root_path.exists() or not root_path.is_dir():
        console.print(f"[red]Error:[/red] Repository root not found: {root_path}")
        raise typer.Exit(1)

    try:
        include_types = _validate_include_types(include)
    except typer.BadParameter as exc:
        console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(1)

    with console.status("[bold]Scanning repository sources...[/bold]"):
        try:
            merged_ir, discovered, warnings, link_counts = _scan_repository_sources(
                root=root_path,
                include_types=include_types,
                max_depth=max_depth,
                strict_linking=strict_linking,
                sam_build=sam_build,
                terraform_pull_missing=terraform_pull_missing,
            )
        except Exception as exc:
            console.print(f"[red]Error:[/red] {exc}")
            raise typer.Exit(1)

    if output_format == "json":
        merged_ir.write_json(output)
    else:
        from stackmap.export import export_ir_to_html

        try:
            export_ir_to_html(merged_ir, output)
        except RuntimeError as exc:
            console.print(f"[red]Error:[/red] {exc}")
            raise typer.Exit(1)

    type_counts: dict[str, int] = {}
    for src in discovered:
        type_counts[src.source_type] = type_counts.get(src.source_type, 0) + 1

    table = Table(title="StackMap Repository Scan Results", show_header=False)
    table.add_column("Metric", style="bold")
    table.add_column("Value", style="cyan")
    table.add_row("Root", str(root_path))
    table.add_row("Discovered sources", str(len(discovered)))
    table.add_row(
        "By type",
        ", ".join(f"{key}={value}" for key, value in sorted(type_counts.items())) or "-",
    )
    table.add_row("Resources", str(len(merged_ir.nodes)))
    table.add_row("Connections", str(len(merged_ir.edges)))
    table.add_row("Groups", str(len(merged_ir.groups)))
    table.add_row(
        "Cross links",
        f"high={link_counts.get('high', 0)}, "
        f"medium={link_counts.get('medium', 0)}, "
        f"low={link_counts.get('low', 0)}",
    )
    table.add_row("Link policy", "strict" if strict_linking else "loose")
    table.add_row("Output", output)
    console.print()
    console.print(table)

    if warnings:
        console.print()
        console.print("[yellow]Warnings:[/yellow]")
        for warning in warnings[:20]:
            console.print(f"- {warning}")
        if len(warnings) > 20:
            console.print(f"- ... and {len(warnings) - 20} more")

    console.print(
        f"\n[green]✓[/green] Repository scan complete: {len(merged_ir.nodes)} resources, "
        f"{len(merged_ir.edges)} connections."
    )


@app.command()
def serve(
    source: str = typer.Option(
        "terraform.tfstate",
        help="Path to infrastructure source file (default: terraform.tfstate)",
    ),
    terraform_dir: str | None = typer.Option(
        None,
        help="Terraform working directory for remote state pull fallback",
    ),
    auto_pull_remote: bool = typer.Option(
        True,
        "--auto-pull-remote/--no-auto-pull-remote",
        help="When source is missing, offer to run `terraform state pull`",
    ),
    host: str = typer.Option("127.0.0.1", help="Host to bind the local server"),
    port: int = typer.Option(3000, help="Port to bind the local server"),
    watch: bool = typer.Option(False, help="Watch the source file and auto-reload graph data"),
    watch_interval: float = typer.Option(1.0, help="Watch interval in seconds"),
    open_browser: bool = typer.Option(True, "--open/--no-open", help="Open browser automatically"),
) -> None:
    """Serve an interactive local StackMap viewer."""
    try:
        source_path = _resolve_source_with_remote_pull(source, terraform_dir, auto_pull_remote)
    except RuntimeError as exc:
        console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(1)

    if not source_path.exists():
        console.print(f"[red]Error:[/red] Source file not found: {source}")
        raise typer.Exit(1)

    with console.status("[bold]Preparing local viewer...[/bold]"):
        try:
            source_type, ir = _parse_source(source)
        except typer.BadParameter as exc:
            console.print(f"[red]Error:[/red] {exc}")
            raise typer.Exit(1)
        except Exception as exc:
            console.print(f"[red]Error:[/red] {exc}")
            raise typer.Exit(1)

    state = _LiveGraphState(ir)
    temp_dir: Path | None = None
    source_public_dir = get_preferred_public_dir()
    public_dir: Path
    fallback_html = False
    fallback_reason: str | None = None

    if source_public_dir is None:
        fallback_reason = "missing"
    elif _has_dev_only_nuxt_entry(source_public_dir):
        fallback_reason = "dev_only"

    if fallback_reason is not None:
        from stackmap.export import export_ir_to_html

        temp_dir = Path(tempfile.mkdtemp(prefix="stackmap-serve-"))
        public_dir = temp_dir
        export_ir_to_html(ir, public_dir / "index.html")
        fallback_html = True
    else:
        temp_dir = Path(tempfile.mkdtemp(prefix="stackmap-serve-"))
        public_dir = temp_dir / "public"
        if source_public_dir is None:
            raise RuntimeError("Internal error: missing static assets directory.")
        shutil.copytree(source_public_dir, public_dir, dirs_exist_ok=True)

    _, snapshot = state.snapshot()
    _write_graph_json(public_dir / "sample-data.json", snapshot)

    handler_cls = partial(
        _StackMapRequestHandler,
        directory=str(public_dir),
        state=state,
        source_type=source_type,
    )
    try:
        server = ThreadingHTTPServer((host, port), handler_cls)
    except OSError as exc:
        console.print(f"[red]Error:[/red] Could not start server on {host}:{port}: {exc}")
        raise typer.Exit(1) from exc

    stop_event = threading.Event()
    watcher: threading.Thread | None = None
    if watch:
        watcher = threading.Thread(
            target=_watch_source_loop,
            args=(source_path, state, watch_interval, stop_event, public_dir, fallback_html),
            daemon=True,
        )
        watcher.start()

    url = f"http://{host}:{port}"
    console.print()
    console.print("[bold]StackMap Serve[/bold]")
    console.print(f"Source: [cyan]{source}[/cyan]")
    console.print(f"Source type: [cyan]{source_type}[/cyan]")
    console.print(f"URL: [cyan]{url}[/cyan]")
    console.print(f"Watch mode: [cyan]{'on' if watch else 'off'}[/cyan]")
    if fallback_html:
        if fallback_reason == "missing":
            console.print(
                "[yellow]Using fallback HTML renderer "
                "(prebuilt frontend not found).[/yellow]"
            )
        elif fallback_reason == "dev_only":
            console.print(
                "[yellow]Using fallback HTML renderer "
                "(Nuxt static output contains dev-only entry references).[/yellow]"
            )

    if open_browser:
        threading.Timer(0.7, lambda: webbrowser.open(url)).start()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        stop_event.set()
        server.server_close()
        if watcher is not None and watcher.is_alive():
            watcher.join(timeout=1.0)
        if temp_dir and temp_dir.exists():
            shutil.rmtree(temp_dir, ignore_errors=True)


@app.command()
def version() -> None:
    """Print the StackMap version."""
    from stackmap import __version__

    console.print(f"stackmap {__version__}")


if __name__ == "__main__":
    app()
