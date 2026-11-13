#---------------------beginning-of-code------------------------#
#--------------------------------------------------------------#

# File: visuals/render.py
# Purpose: turn (words + template + brand) into finished images.
#   1. build_html: fill the HTML template with the words and the brand
#   2. Renderer:   open the HTML in a headless browser (Playwright), fit the text,
#                  screenshot every slide as PNG; carousels also get one PDF
#                  (LinkedIn carousels are uploaded as PDF documents)
# Text that can't fit even at 55% of its size stops with a clear error, never a cut-off image.
#--------------------------------------------------------------#

# Imports Libraries
import re
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined, select_autoescape

from visuals.brand import Brand, font_css_url, font_face_css
from visuals.paths import TEMPLATES_DIR
from visuals.specs import SIZES
#--------------------------------------------------------------#

# Global variables
_env = Environment(
    loader=FileSystemLoader(TEMPLATES_DIR),
    autoescape=select_autoescape(["html"]),      # your words are shown as text, never as HTML
    undefined=StrictUndefined,                   # a typo in a template fails loudly
    trim_blocks=True, lstrip_blocks=True,
)
FONT_TIMEOUT_MS = 30_000
_HYPHEN = re.compile(r"(?<=\w)-(?=\w)")


# Keep hyphenated words together ("go-live" never splits across lines)
def nobreak(text: str) -> str:
    return _HYPHEN.sub("\u2011", text or "")


_env.filters["nobreak"] = nobreak


class TextOverflowError(Exception):
    pass
#--------------------------------------------------------------#

# Fill a template with the words and the brand; returns the full HTML page
def build_html(spec, brand: Brand, size: str) -> str:
    width, height = SIZES[size]
    scale = round(min(width, height) / 1080, 4)  # 1 for square/portrait, smaller for landscape
    return _env.get_template(f"{spec.template}.html").render(
        spec=spec, brand=brand, w=width, h=height, s=scale, size=size,
        css=(TEMPLATES_DIR / "base.css").read_text(encoding="utf-8"),
        font_url=font_css_url(brand),
        font_css=font_face_css(brand),
    )
#--------------------------------------------------------------#

# Headless browser that renders specs to files. Use as: with Renderer() as r: r.render(...)
class Renderer:
    def __enter__(self):
        from playwright.sync_api import sync_playwright
        self._pw = sync_playwright().start()
        self._browser = self._pw.chromium.launch()
        return self

    def __exit__(self, *exc):
        self._browser.close()
        self._pw.stop()

    def render(self, spec, brand: Brand, size: str, out_dir: Path, base_name: str,
               keep_html: bool = False) -> list[Path]:
        width, height = SIZES[size]
        html = build_html(spec, brand, size)
        out_dir.mkdir(parents=True, exist_ok=True)
        if keep_html:
            (out_dir / f"{base_name}_{size}.html").write_text(html, encoding="utf-8")

        page = self._browser.new_page(viewport={"width": width, "height": height},
                                      device_scale_factor=1)
        try:
            page.set_content(html, wait_until="networkidle", timeout=FONT_TIMEOUT_MS)
            overflow = page.evaluate("async () => { await document.fonts.ready; return fitAll(); }")
            if overflow:
                raise TextOverflowError(
                    f"{base_name} ({size}): text too long for {', '.join(overflow)}. Shorten it.")

            slides = page.query_selector_all(".slide")
            paths = []
            if len(slides) == 1:
                path = out_dir / f"{base_name}_{size}.png"
                slides[0].screenshot(path=str(path))
                paths.append(path)
            else:
                for i, slide in enumerate(slides, start=1):
                    path = out_dir / f"{base_name}_{size}_{i:02d}.png"
                    slide.screenshot(path=str(path))
                    paths.append(path)
                pdf = out_dir / f"{base_name}_{size}.pdf"
                page.pdf(path=str(pdf), width=f"{width}px", height=f"{height}px",
                         print_background=True, prefer_css_page_size=True)
                paths.append(pdf)
            return paths
        finally:
            page.close()
#--------------------------------------------------------------#
#----------------------End-of-code-----------------------------#
