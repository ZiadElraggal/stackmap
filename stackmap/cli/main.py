import json
import shutil
import subprocess
import tempfile
import threading
import time
import webbrowser
from pathlib import Path
from typing import Any

import typer
from rich.console import Console
from rich.table import Table

from stackmap.parsers.base import BaseParser, StackMapIR
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
    path = Path(source_path)
    if path.suffix == ".tfstate" or "terraform" in path.name.lower():
        return "terraform"
    if path.suffix.lower() in {".template", ".cfn"}:
        return "cloudformation"
    if path.suffix.lower() in {".yaml", ".yml", ".json"}:
        try:
            raw = path.read_text()
            if path.suffix.lower() in {".yaml", ".yml"}:
                if "AWS::Serverless-2016-10-31" in raw:
                    return "sam"
                return "cloudformation"
            data = json.loads(raw)
            if isinstance(data, dict) and (
                "AWSTemplateFormatVersion" in data
                or "Resources" in data
            ):
                transform = data.get("Transform")
                if transform == "AWS::Serverless-2016-10-31" or (
                    isinstance(transform, list) and "AWS::Serverless-2016-10-31" in transform
                ):
                    return "sam"
                return "cloudformation"
        except Exception:
            pass
    try:
        data = json.loads(path.read_text())
        if "terraform_version" in data:
            return "terraform"
    except Exception:
        pass
    raise typer.BadParameter(
        f"Cannot auto-detect source type for {source_path}. "
        "Supported formats: Terraform state (.tfstate), CloudFormation template (.json/.yaml/.yml), "
        "SAM template (.json/.yaml/.yml with AWS::Serverless transform)"
    )


def _build_parser(source_type: str) -> BaseParser:
    if source_type == "terraform":
        from stackmap.parsers.terraform import TerraformParser

        return TerraformParser()
    if source_type == "cloudformation":
        from stackmap.parsers.cloudformation import CloudFormationParser

        return CloudFormationParser()
    if source_type == "sam":
        from stackmap.parsers.sam import SamParser

        return SamParser()
    raise typer.BadParameter(f"Unsupported source type: {source_type}")


def _parse_source(source_path: str) -> tuple[str, StackMapIR]:
    source_type = _detect_source_type(source_path)
    parser = _build_parser(source_type)
    return source_type, parser.parse(source_path)


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

    try:
        import uvicorn
        from fastapi import FastAPI
        from fastapi.responses import JSONResponse
        from fastapi.staticfiles import StaticFiles
    except Exception as exc:  # pragma: no cover
        console.print(
            "[red]Error:[/red] Missing serve dependencies. "
            "Install `fastapi` and `uvicorn`."
        )
        raise typer.Exit(1) from exc

    app_server = FastAPI(title="stackmap-local")

    @app_server.get("/api/graph")
    def api_graph() -> JSONResponse:
        _, ir_data = state.snapshot()
        return JSONResponse(ir_data)

    @app_server.get("/api/version")
    def api_version() -> dict[str, int]:
        version, _ = state.snapshot()
        return {"version": version}

    @app_server.get("/api/health")
    def api_health() -> dict[str, str]:
        return {"status": "ok", "source_type": source_type}

    app_server.mount("/", StaticFiles(directory=str(public_dir), html=True), name="static")

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
        uvicorn.run(app_server, host=host, port=port, log_level="warning")
    finally:
        stop_event.set()
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
