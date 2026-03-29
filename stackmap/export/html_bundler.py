from __future__ import annotations

import html
import json
from pathlib import Path

from stackmap.parsers.base import StackMapIR


def export_ir_to_html(ir: StackMapIR, output_path: str | Path) -> None:
    """Write a lightweight standalone HTML view for an IR payload."""
    payload = json.dumps(ir.to_dict(), indent=2)
    escaped = html.escape(payload)

    html_doc = f"""<!doctype html>
<html lang=\"en\">
  <head>
    <meta charset=\"utf-8\" />
    <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
    <title>StackMap Export</title>
    <style>
      body {{ margin: 0; font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace; background: #0a0a0f; color: #e5e7eb; }}
      .wrap {{ max-width: 1100px; margin: 0 auto; padding: 24px; }}
      .meta {{ display: flex; gap: 16px; color: #94a3b8; font-size: 12px; margin-bottom: 16px; }}
      .card {{ border: 1px solid rgba(255,255,255,.12); border-radius: 10px; background: #12121a; padding: 12px; }}
      pre {{ margin: 0; white-space: pre-wrap; word-break: break-word; font-size: 12px; line-height: 1.45; }}
      h1 {{ font-size: 16px; margin: 0 0 12px; }}
    </style>
  </head>
  <body>
    <div class=\"wrap\">
      <h1>StackMap HTML Export</h1>
      <div class=\"meta\">
        <span>{len(ir.nodes)} resources</span>
        <span>{len(ir.edges)} connections</span>
        <span>{len(ir.groups)} groups</span>
      </div>
      <div class=\"card\">
        <pre>{escaped}</pre>
      </div>
    </div>
  </body>
</html>
"""

    Path(output_path).write_text(html_doc)
