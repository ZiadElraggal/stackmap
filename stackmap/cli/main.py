from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

app = typer.Typer(
    name="stackmap",
    help="Architecture diagrams that generate themselves from your infrastructure code.",
    no_args_is_help=True,
)
console = Console()


def _detect_source_type(source_path: str) -> str:
    """Auto-detect infrastructure source type from file extension or content."""
    path = Path(source_path)
    if path.suffix == ".tfstate" or "terraform" in path.name.lower():
        return "terraform"
    # Try reading the file to detect format
    try:
        import json

        data = json.loads(path.read_text())
        if "terraform_version" in data:
            return "terraform"
    except Exception:
        pass
    raise typer.BadParameter(
        f"Cannot auto-detect source type for {source_path}. "
        "Supported formats: Terraform state (.tfstate)"
    )


@app.command()
def scan(
    source: str = typer.Option(
        ..., help="Path to infrastructure source file (e.g. terraform.tfstate)"
    ),
    output: str = typer.Option("stackmap-output.json", help="Output file path"),
    format: str = typer.Option("json", help="Output format: json or html"),
) -> None:
    """Scan infrastructure source and generate an architecture map."""
    source_path = Path(source)
    if not source_path.exists():
        console.print(f"[red]Error:[/red] Source file not found: {source}")
        raise typer.Exit(1)

    with console.status("[bold]Scanning infrastructure...[/bold]"):
        source_type = _detect_source_type(source)

        if source_type == "terraform":
            from stackmap.parsers.terraform import TerraformParser

            parser = TerraformParser()
        else:
            console.print(f"[red]Error:[/red] Unsupported source type: {source_type}")
            raise typer.Exit(1)

        ir = parser.parse(source)

    if format == "json":
        ir.write_json(output)
    else:
        console.print(f"[red]Error:[/red] Format '{format}' not yet supported. Use 'json'.")
        raise typer.Exit(1)

    # Summary table
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
def version() -> None:
    """Print the StackMap version."""
    from stackmap import __version__

    console.print(f"stackmap {__version__}")


if __name__ == "__main__":
    app()
