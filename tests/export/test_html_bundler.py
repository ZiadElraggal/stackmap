from pathlib import Path

from stackmap.export.html_bundler import export_ir_to_html
from stackmap.parsers.base import ResourceCategory, StackMapIR, StackMapNode


def _sample_ir() -> StackMapIR:
    return StackMapIR(
        metadata={"source_type": "terraform"},
        nodes=[
            StackMapNode(
                id="aws_lambda_function.demo",
                name="demo-fn",
                resource_type="aws_lambda_function",
                provider="aws",
                category=ResourceCategory.COMPUTE,
            )
        ],
        edges=[],
        groups=[],
    )


def test_export_ir_to_html_inlines_assets_and_embeds_data(tmp_path: Path) -> None:
    frontend = tmp_path / "frontend"
    public = frontend / ".output" / "public"
    nuxt = public / "_nuxt"
    nuxt.mkdir(parents=True)

    (public / "index.html").write_text(
        """
<!doctype html>
<html>
<head>
  <meta charset="utf-8" />
  <link rel="stylesheet" href="/_nuxt/app.css" />
</head>
<body>
  <div id="__nuxt"></div>
  <script type="module" src="/_nuxt/app.js"></script>
</body>
</html>
""".strip()
    )
    (nuxt / "app.css").write_text("body{background:#000}")
    (nuxt / "chunk.js").write_text("export const ready = true;")
    (nuxt / "app.js").write_text('import { ready } from "./chunk.js"; window.__READY__ = ready;')

    out = tmp_path / "map.html"
    export_ir_to_html(_sample_ir(), out, frontend_dir=frontend)

    html = out.read_text()
    assert "window.__STACKMAP_DATA__" in html
    assert "data:text/javascript;base64" in html
    assert "<style>body{background:#000}</style>" in html
    assert '/_nuxt/app.css' not in html
    assert '/_nuxt/app.js' not in html


def test_export_runs_generate_when_missing_index(tmp_path: Path, monkeypatch) -> None:
    frontend = tmp_path / "frontend"
    public = frontend / ".output" / "public"
    nuxt = public / "_nuxt"
    nuxt.mkdir(parents=True)

    def fake_generate(frontend_dir: Path) -> None:
        assert frontend_dir == frontend
        (public / "index.html").write_text(
            "<html><head></head><body>"
            '<script type="module" src="/_nuxt/app.js"></script>'
            "</body></html>"
        )
        (nuxt / "app.js").write_text("window.__BOOTED__ = true;")

    monkeypatch.setattr("stackmap.export.html_bundler._run_nuxt_generate", fake_generate)

    out = tmp_path / "map.html"
    export_ir_to_html(_sample_ir(), out, frontend_dir=frontend)
    assert out.exists()
