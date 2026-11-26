#---------------------beginning-of-code------------------------#
#--------------------------------------------------------------#

# File: visuals/render.py
# Purpose: turn (words + template + brand) into finished images.
#   1. build_html: fill the HTML template with the words and the brand
#   2. Renderer:   open the HTML in a headless browser (Playwright), fit the text,
#                  screenshot every slide as PNG; carousels also get one PDF
#                  (LinkedIn carousels are uploaded as PDF documents)
#   3. Renderer.render_motion: for motion templates, step the animation frame by frame
#                  and stream every frame into FFmpeg -> MP4 (+ a poster PNG of the last frame)
# Text that can't fit even at 55% of its size stops with a clear error, never a cut-off image.
#--------------------------------------------------------------#

# Imports Libraries
import base64
import re
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined, select_autoescape
from markupsafe import Markup, escape

from visuals.brand import Brand, font_css_url, font_face_css
from visuals.paths import TEMPLATES_DIR
from visuals.specs import SIZES, split_stat
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


# *words in asterisks* -> shown in brand colour. Everything else stays plain text.
_EMPHASIS = re.compile(r"\*([^*]+)\*")


def emphasis(text: str) -> Markup:
    return Markup(_EMPHASIS.sub(r'<span class="em">\1</span>', str(escape(text or ""))))


HOLD_SECONDS = 2.5          # motion: how long the finished frame stays on screen

_env.filters["nobreak"] = nobreak
_env.filters["emphasis"] = emphasis
_env.globals["split_stat"] = split_stat


class TextOverflowError(Exception):
    pass
#--------------------------------------------------------------#

# An image file as a data URI, so the page needs no file paths (None if no image)
IMAGE_TYPES = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
               ".webp": "image/webp", ".svg": "image/svg+xml"}


def image_data_uri(path: str | None) -> str | None:
    if not path:
        return None
    file = Path(path)
    mime = IMAGE_TYPES.get(file.suffix.lower())
    if mime is None:
        raise ValueError(f"Image {file.name}: use one of {sorted(IMAGE_TYPES)}")
    if not file.exists():
        raise FileNotFoundError(f"Image not found: {file}")
    return f"data:{mime};base64," + base64.b64encode(file.read_bytes()).decode()
#--------------------------------------------------------------#

# Fill a template with the words and the brand; returns the full HTML page
def build_html(spec, brand: Brand, size: str, for_video: bool = False) -> str:
    width, height = SIZES[size]
    scale = round(min(width, height) / 1080, 4)  # 1 for square/portrait, smaller for landscape
    return _env.get_template(f"{spec.template}.html").render(
        spec=spec, brand=brand, w=width, h=height, s=scale, size=size, for_video=for_video,
        image=image_data_uri(getattr(spec, "image", None)),
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
               keep_html: bool = False, for_video: bool = False) -> list[Path]:
        """for_video: slides for a video (no "Swipe" hint, no PDF)."""
        width, height = SIZES[size]
        html = build_html(spec, brand, size, for_video)
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
                if not for_video:
                    pdf = out_dir / f"{base_name}_{size}.pdf"
                    page.pdf(path=str(pdf), width=f"{width}px", height=f"{height}px",
                             print_background=True, prefer_css_page_size=True)
                    paths.append(pdf)
            return paths
        finally:
            page.close()

    def render_motion(self, spec, brand: Brand, size: str, out_dir: Path, base_name: str,
                      music: Path | None = None, keep_html: bool = False) -> list[Path]:
        from visuals.video import FPS, finish_encoder, start_encoder
        width, height = SIZES[size]
        html = build_html(spec, brand, size)
        out_dir.mkdir(parents=True, exist_ok=True)
        if keep_html:
            (out_dir / f"{base_name}_{size}.html").write_text(html, encoding="utf-8")

        page = self._browser.new_page(viewport={"width": width, "height": height},
                                      device_scale_factor=1)
        clip = {"x": 0, "y": 0, "width": width, "height": height}
        try:
            page.set_content(html, wait_until="networkidle", timeout=FONT_TIMEOUT_MS)
            result = page.evaluate("""async () => {
                await document.fonts.ready;
                if (window.motionSetup) motionSetup();
                const overflow = fitAll();
                return overflow.length ? { overflow } : { end: prepareMotion() };
            }""")
            if "overflow" in result:
                raise TextOverflowError(f"{base_name} ({size}): text too long for "
                                        f"{', '.join(result['overflow'])}. Shorten it.")

            end = result["end"]
            length = max(spec.duration, end + 0.5) if spec.duration else end + HOLD_SECONDS
            video = out_dir / f"{base_name}_{size}.mp4"
            encoder = start_encoder(video, length, music)
            try:
                for frame in range(round(length * FPS)):
                    page.evaluate("t => renderAt(t)", frame / FPS)
                    encoder.stdin.write(page.screenshot(type="png", clip=clip))
            except BrokenPipeError:
                pass                                   # FFmpeg stopped: finish_encoder says why
            finish_encoder(encoder)

            poster = out_dir / f"{base_name}_{size}_poster.png"
            page.screenshot(path=str(poster), clip=clip)   # last frame = the finished design
            return [video, poster]
        finally:
            page.close()
#--------------------------------------------------------------#
#----------------------End-of-code-----------------------------#
