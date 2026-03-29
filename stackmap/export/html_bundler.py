from __future__ import annotations

import base64
import json
import re
import subprocess
from pathlib import Path

from stackmap.parsers.base import StackMapIR

_CSS_LINK_RE = re.compile(r'<link[^>]+href="(/_nuxt/[^"]+\.css)"[^>]*>', re.IGNORECASE)
_SCRIPT_SRC_RE = re.compile(
    r'<script[^>]+src="(/_nuxt/[^"]+\.js)"[^>]*>\s*</script>',
    re.IGNORECASE,
)
_IMPORT_RE = re.compile(r'^\s*import\s+[^"\n]+\s+from\s+"(\./[^"]+)";\s*$', re.MULTILINE)


def _run_nuxt_generate(frontend_dir: Path) -> None:
    subprocess.run(["npm", "run", "generate"], cwd=frontend_dir, check=True)


def _inline_css(html: str, public_dir: Path) -> str:
    def repl(match: re.Match[str]) -> str:
        href = match.group(1).lstrip("/")
        css_path = public_dir / href
        if not css_path.exists():
            return match.group(0)
        css = css_path.read_text()
        return f"<style>{css}</style>"

    return _CSS_LINK_RE.sub(repl, html)


def _resolve_js_module(js_path: Path) -> str:
    content = js_path.read_text()

    def import_repl(match: re.Match[str]) -> str:
        rel = match.group(1)
        child = (js_path.parent / rel).resolve()
        if not child.exists():
            return ""
        return _resolve_js_module(child)

    return _IMPORT_RE.sub(import_repl, content)


def _inline_js(html: str, public_dir: Path) -> str:
    def repl(match: re.Match[str]) -> str:
        src = match.group(1).lstrip("/")
        js_path = public_dir / src
        if not js_path.exists():
            return match.group(0)
        bundled = _resolve_js_module(js_path)
        encoded = base64.b64encode(bundled.encode()).decode()
        return f'<script type="module" src="data:text/javascript;base64,{encoded}"></script>'

    return _SCRIPT_SRC_RE.sub(repl, html)


def _inject_payload(html: str, payload: dict) -> str:
    script = (
        "<script>"
        f"window.__STACKMAP_DATA__ = {json.dumps(payload)};"
        "</script>"
    )
    if "</body>" in html:
        return html.replace("</body>", f"{script}</body>")
    return f"{html}{script}"


def export_ir_to_html(
    ir: StackMapIR,
    output_path: str | Path,
    frontend_dir: str | Path | None = None,
) -> None:
    frontend = Path(frontend_dir) if frontend_dir else Path("frontend")
    public_dir = frontend / ".output" / "public"
    index_path = public_dir / "index.html"

    if not index_path.exists():
        _run_nuxt_generate(frontend)
    if not index_path.exists():
        raise RuntimeError(f"Nuxt index not found at {index_path}")

    html = index_path.read_text()
    html = _inline_css(html, public_dir)
    html = _inline_js(html, public_dir)
    html = _inject_payload(html, ir.to_dict())
    Path(output_path).write_text(html)
