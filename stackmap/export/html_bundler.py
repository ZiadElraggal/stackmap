"""Single-file HTML export for StackMap IR."""

# ruff: noqa: E501

from __future__ import annotations

import base64
import json
import mimetypes
import posixpath
import re
import subprocess
from pathlib import Path

from stackmap.parsers.base import StackMapIR
from stackmap.webapp import get_dev_frontend_dir, get_packaged_public_dir

_SCRIPT_SRC_RE = re.compile(
    r'(?P<tag><script(?P<attrs>[^>]*?)\s+src=(?P<q>["\'])(?P<src>[^"\']+)(?P=q)(?P<tail>[^>]*)>\s*</script>)',
    re.IGNORECASE,
)
_STYLESHEET_RE = re.compile(
    r'(?P<tag><link(?P<attrs>[^>]*?)rel=(?P<q1>["\'])stylesheet(?P=q1)(?P<attrs2>[^>]*?)href=(?P<q2>["\'])(?P<href>[^"\']+)(?P=q2)(?P<tail>[^>]*)/?>)',
    re.IGNORECASE,
)
_MODULEPRELOAD_RE = re.compile(
    r"<link[^>]*rel=(?P<q>[\"'])modulepreload(?P=q)[^>]*>",
    re.IGNORECASE,
)
_URL_RE = re.compile(r"url\((?P<q>['\"]?)(?P<path>[^)\"']+)(?P=q)\)")

_DYNAMIC_IMPORT_RE = re.compile(
    r'(?P<prefix>\bimport\s*\(\s*)(?P<q>["\'])(?P<spec>[^"\']+)(?P=q)(?P<suffix>\s*\))'
)
_FROM_IMPORT_RE = re.compile(
    r'(?P<prefix>\bfrom\s+)(?P<q>["\'])(?P<spec>[^"\']+)(?P=q)'
)
_SIDE_EFFECT_IMPORT_RE = re.compile(
    r'(?P<prefix>\bimport\s+)(?!\()(?P<q>["\'])(?P<spec>[^"\']+)(?P=q)'
)
_EMPTY_JS_DATA_URL = "data:text/javascript;base64,ZXhwb3J0IHt9Ow=="


def export_ir_to_html(
    ir: StackMapIR,
    output_path: str | Path,
    frontend_dir: str | Path | None = None,
) -> None:
    """Export IR to a single self-contained HTML file."""
    generate_error: RuntimeError | None = None
    public_dir: Path | None = None

    if frontend_dir:
        frontend = Path(frontend_dir).resolve()
        public_dir = _resolve_static_public_dir(frontend)
        if not (public_dir / "index.html").exists():
            try:
                _run_nuxt_generate(frontend)
            except RuntimeError as exc:
                generate_error = exc
            public_dir = _resolve_static_public_dir(frontend)
    else:
        public_dir = get_packaged_public_dir()
        if public_dir is None:
            dev_frontend = get_dev_frontend_dir()
            if dev_frontend is not None:
                public_dir = _resolve_static_public_dir(dev_frontend)
                if not (public_dir / "index.html").exists():
                    try:
                        _run_nuxt_generate(dev_frontend)
                    except RuntimeError as exc:
                        generate_error = exc
                    public_dir = _resolve_static_public_dir(dev_frontend)

    if public_dir is None:
        fallback = _render_fallback_html(
            ir,
            "No packaged frontend bundle found and no local frontend project is available.",
        )
        Path(output_path).write_text(fallback)
        return

    index_path = public_dir / "index.html"
    if not index_path.exists():
        fallback = _render_fallback_html(ir, str(generate_error) if generate_error else None)
        Path(output_path).write_text(fallback)
        return

    html = index_path.read_text()
    # Some Nuxt versions emit dev-style entry references in static output.
    # If detected, use the fallback renderer for a reliable single-file export.
    if "@vite/client" in html or "node_modules/nuxt/dist/app/entry.js" in html:
        fallback = _render_fallback_html(
            ir,
            "Generated frontend index uses dev-only entry references; "
            "using fallback renderer for standalone export.",
        )
        Path(output_path).write_text(fallback)
        return

    try:
        inlined = _inline_html_assets(html, public_dir)
    except Exception as exc:
        fallback = _render_fallback_html(
            ir,
            f"Static asset inlining failed ({exc.__class__.__name__}); using fallback renderer.",
        )
        Path(output_path).write_text(fallback)
        return
    payload = json.dumps(ir.to_dict(), separators=(",", ":"))
    inject = f"<script>window.__STACKMAP_DATA__={payload};</script>"
    inlined = inlined.replace("</head>", f"{inject}</head>", 1)
    Path(output_path).write_text(inlined)


def _render_fallback_html(ir: StackMapIR, reason: str | None = None) -> str:
    payload = json.dumps(ir.to_dict(), separators=(",", ":"))
    banner = ""
    if reason:
        safe_reason = reason.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        banner = (
            "<div class='banner'>Frontend static bundle unavailable. "
            f"Showing fallback renderer. {safe_reason}</div>"
        )

    return f"""<!doctype html>
<html>
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width,initial-scale=1" />
  <title>StackMap Export</title>
  <style>
    body {{ margin: 0; background: #0a0a0f; color: #d1d5db; font-family: ui-monospace, SFMono-Regular, Menlo, monospace; }}
    .wrap {{ display: grid; grid-template-columns: 1fr 340px; height: 100vh; }}
    .canvas {{ position: relative; overflow: hidden; }}
    .panel {{ border-left: 1px solid rgba(255,255,255,0.08); background: #12121a; padding: 12px; overflow: auto; }}
    .muted {{ color: #6b7280; font-size: 12px; }}
    .banner {{ padding: 8px 10px; background: #3f2b17; color: #fed7aa; font-size: 12px; border-bottom: 1px solid #7c2d12; }}
    svg {{ width: 100%; height: 100%; background: radial-gradient(circle at 1px 1px, rgba(255,255,255,0.05) 1px, transparent 0); background-size: 28px 28px; }}
    .node rect {{ fill: #1a1a2e; stroke: rgba(255,255,255,0.14); rx: 9; ry: 9; }}
    .node text {{ pointer-events: none; font-size: 11px; fill: #e5e7eb; }}
    .node:hover rect {{ stroke: #93c5fd; }}
    .edge {{ stroke: rgba(156,163,175,0.5); stroke-width: 1.5; fill: none; marker-end: url(#arrow); }}
    .row {{ border-bottom: 1px solid rgba(255,255,255,0.08); padding: 8px 0; }}
    .k {{ color: #9ca3af; }}
    .v {{ color: #f3f4f6; word-break: break-word; }}
    @media (max-width: 900px) {{ .wrap {{ grid-template-columns: 1fr; }} .panel {{ height: 42vh; }} }}
  </style>
</head>
<body>
  {banner}
  <div class="wrap">
    <div class="canvas">
      <svg id="svg" viewBox="0 0 1800 1100" preserveAspectRatio="xMidYMid meet">
        <defs>
          <marker id="arrow" viewBox="0 0 10 7" refX="10" refY="3.5" markerWidth="8" markerHeight="6" orient="auto-start-reverse">
            <polygon points="0 0,10 3.5,0 7" fill="#6b7280"></polygon>
          </marker>
        </defs>
        <g id="viewport"></g>
      </svg>
    </div>
    <aside class="panel">
      <h2 style="margin: 0 0 8px 0;">StackMap Export</h2>
      <div class="muted" id="meta"></div>
      <div id="detail" style="margin-top: 12px;">
        <p class="muted">Click a node to inspect details.</p>
      </div>
    </aside>
  </div>
  <script>
    window.__STACKMAP_DATA__ = {payload};
    const data = window.__STACKMAP_DATA__;
    const svg = document.getElementById("svg");
    const viewport = document.getElementById("viewport");
    const detail = document.getElementById("detail");
    const meta = document.getElementById("meta");

    meta.textContent = `${{data.nodes.length}} resources • ${{data.edges.length}} connections` +
      (data.metadata?.terraform_version ? ` • Terraform v${{data.metadata.terraform_version}}` : "");

    const tierY = {{ frontend: 110, api: 320, backend: 580, data: 860 }};
    const tiers = new Map();
    for (const node of data.nodes) {{
      const tier = node.position_hint?.tier || "backend";
      if (!tiers.has(tier)) tiers.set(tier, []);
      tiers.get(tier).push(node);
    }}
    const positions = new Map();
    for (const [tier, nodes] of tiers.entries()) {{
      nodes.forEach((node, i) => {{
        const spacing = 180;
        const rowWidth = Math.max(1, nodes.length - 1) * spacing;
        const startX = 900 - rowWidth / 2;
        positions.set(node.id, {{ x: startX + i * spacing, y: tierY[tier] || 580 }});
      }});
    }}

    function el(name, attrs = {{}}, parent = viewport) {{
      const n = document.createElementNS("http://www.w3.org/2000/svg", name);
      for (const [k, v] of Object.entries(attrs)) n.setAttribute(k, String(v));
      parent.appendChild(n);
      return n;
    }}

    for (const edge of data.edges) {{
      const s = positions.get(edge.source);
      const t = positions.get(edge.target);
      if (!s || !t) continue;
      el("line", {{ x1: s.x, y1: s.y, x2: t.x, y2: t.y, class: "edge" }});
    }}

    for (const node of data.nodes) {{
      const p = positions.get(node.id);
      if (!p) continue;
      const g = el("g", {{ class: "node", transform: `translate(${{p.x}},${{p.y}})` }});
      const w = 140 + ((node.position_hint?.weight || 2) * 8);
      el("rect", {{ x: -w/2, y: -20, width: w, height: 40 }}, g);
      const name = document.createElementNS("http://www.w3.org/2000/svg", "text");
      name.setAttribute("x", String(-w / 2 + 10));
      name.setAttribute("y", "-2");
      name.textContent = node.name.length > 24 ? node.name.slice(0, 23) + "…" : node.name;
      g.appendChild(name);
      const type = document.createElementNS("http://www.w3.org/2000/svg", "text");
      type.setAttribute("x", String(-w / 2 + 10));
      type.setAttribute("y", "12");
      type.setAttribute("fill", "#6b7280");
      type.setAttribute("font-size", "9");
      type.textContent = node.resource_type;
      g.appendChild(type);
      g.addEventListener("click", () => showNode(node));
    }}

    function showNode(node) {{
      const conn = data.edges.filter(e => e.source === node.id || e.target === node.id);
      const top = Object.entries(node.properties || {{}}).slice(0, 12);
      detail.innerHTML =
        `<h3 style="margin:0 0 6px 0;">${{node.name}}</h3>` +
        `<div class="muted" style="margin-bottom:8px;">${{node.resource_type}} • ${{node.category}}</div>` +
        `<div class="row"><div class="k">Connections</div><div class="v">${{conn.length}}</div></div>` +
        top.map(([k,v]) => `<div class="row"><div class="k">${{k}}</div><div class="v">${{String(v)}}</div></div>`).join("");
    }}

    let scale = 1, tx = 0, ty = 0, dragging = false, sx = 0, sy = 0;
    function apply() {{
      viewport.setAttribute("transform", `translate(${{tx}},${{ty}}) scale(${{scale}})`);
    }}
    svg.addEventListener("wheel", (e) => {{
      e.preventDefault();
      const delta = e.deltaY > 0 ? 0.9 : 1.1;
      scale = Math.max(0.2, Math.min(4, scale * delta));
      apply();
    }}, {{ passive: false }});
    svg.addEventListener("mousedown", (e) => {{ dragging = true; sx = e.clientX - tx; sy = e.clientY - ty; }});
    window.addEventListener("mouseup", () => {{ dragging = false; }});
    window.addEventListener("mousemove", (e) => {{
      if (!dragging) return;
      tx = e.clientX - sx; ty = e.clientY - sy; apply();
    }});
  </script>
</body>
</html>"""


def _resolve_static_public_dir(frontend_dir: Path) -> Path:
    candidates = [
        frontend_dir / ".output" / "public",
        frontend_dir / "dist",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[0]


def _run_nuxt_generate(frontend_dir: Path) -> None:
    try:
        subprocess.run(
            ["npm", "run", "generate"],
            cwd=frontend_dir,
            check=True,
            capture_output=True,
            text=True,
        )
    except (FileNotFoundError, subprocess.CalledProcessError) as exc:
        if isinstance(exc, FileNotFoundError):
            raise RuntimeError(
                "npm is required for HTML export generation but was not found on PATH."
            ) from exc
        stderr = (exc.stderr or "").strip()
        stdout = (exc.stdout or "").strip()
        detail = stderr if stderr else stdout
        raise RuntimeError(f"Nuxt static generation failed:\n{detail}") from exc


def _inline_html_assets(html: str, public_dir: Path) -> str:
    js_cache: dict[str, str] = {}

    def replace_stylesheet(match: re.Match[str]) -> str:
        href = match.group("href")
        if not _is_local_asset(href):
            return match.group("tag")
        css_path = _asset_path(public_dir, href)
        css = css_path.read_text()
        css = _inline_css_urls(css, css_path.parent, public_dir)
        return f"<style>{css}</style>"

    html = _STYLESHEET_RE.sub(replace_stylesheet, html)
    html = _MODULEPRELOAD_RE.sub("", html)

    def replace_script(match: re.Match[str]) -> str:
        src = match.group("src")
        attrs = f'{match.group("attrs")}{match.group("tail")}'
        if not _is_local_asset(src):
            return match.group("tag")

        src_path = _asset_path(public_dir, src)
        src_key = _to_web_path(public_dir, src_path)
        data_url = _js_data_url(src_key, public_dir, js_cache)
        cleaned_attrs = re.sub(r"\s+src=(['\"]).*?\1", "", attrs)
        return f"<script{cleaned_attrs} src=\"{data_url}\"></script>"

    return _SCRIPT_SRC_RE.sub(replace_script, html)


def _js_data_url(js_key: str, public_dir: Path, cache: dict[str, str]) -> str:
    if js_key in cache:
        return cache[js_key]
    js_path = public_dir / js_key.lstrip("/")
    code = js_path.read_text()
    rewritten = _rewrite_js_imports(code, js_key, public_dir, cache)
    encoded = base64.b64encode(rewritten.encode("utf-8")).decode("ascii")
    data_url = f"data:text/javascript;base64,{encoded}"
    cache[js_key] = data_url
    return data_url


def _rewrite_js_imports(
    code: str,
    current_key: str,
    public_dir: Path,
    cache: dict[str, str],
) -> str:
    def replace(match: re.Match[str]) -> str:
        spec = match.group("spec")
        resolved = _resolve_import_specifier(spec, current_key)
        if resolved is None:
            return match.group(0)
        target = public_dir / resolved.lstrip("/")
        if not target.exists() or target.suffix not in {".js", ".mjs"}:
            new_spec = _EMPTY_JS_DATA_URL
        else:
            new_spec = _js_data_url(resolved, public_dir, cache)
        suffix = match.groupdict().get("suffix") or ""
        return f'{match.group("prefix")}"{new_spec}"{suffix}'

    updated = _DYNAMIC_IMPORT_RE.sub(replace, code)
    updated = _FROM_IMPORT_RE.sub(replace, updated)
    updated = _SIDE_EFFECT_IMPORT_RE.sub(replace, updated)
    return updated


def _resolve_import_specifier(spec: str, current_key: str) -> str | None:
    if spec.startswith(("http://", "https://", "data:", "#")):
        return None
    clean = spec.split("?", 1)[0].split("#", 1)[0]
    if clean.startswith("/"):
        return clean
    if clean.startswith("."):
        base = posixpath.dirname(current_key)
        resolved = posixpath.normpath(posixpath.join(base, clean))
        if not resolved.startswith("/"):
            resolved = "/" + resolved.lstrip("/")
        return resolved
    return None


def _inline_css_urls(css: str, base_dir: Path, public_dir: Path) -> str:
    def replace(match: re.Match[str]) -> str:
        path = match.group("path").strip()
        if path.startswith(("data:", "http://", "https://", "#")):
            return match.group(0)
        asset = (
            (base_dir / path).resolve()
            if path.startswith(".")
            else _asset_path(public_dir, path)
        )
        if not asset.exists():
            return match.group(0)
        mime, _ = mimetypes.guess_type(asset.name)
        if not mime:
            mime = "application/octet-stream"
        encoded = base64.b64encode(asset.read_bytes()).decode("ascii")
        return f'url("data:{mime};base64,{encoded}")'

    return _URL_RE.sub(replace, css)


def _is_local_asset(path: str) -> bool:
    return path.startswith(("/", "./", "../")) and not path.startswith("//")


def _asset_path(public_dir: Path, path: str) -> Path:
    clean = path.split("?", 1)[0].split("#", 1)[0]
    if clean.startswith("/"):
        clean = clean.lstrip("/")
    return public_dir / clean


def _to_web_path(public_dir: Path, path: Path) -> str:
    rel = "/" + str(path.resolve().relative_to(public_dir.resolve())).replace("\\", "/")
    return rel
