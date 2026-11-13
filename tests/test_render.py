#---------------------beginning-of-code------------------------#
#--------------------------------------------------------------#

# File: tests/test_render.py
# Purpose: check the HTML is built correctly, and (if the browser is installed) that real
#          PNG/PDF files come out at the right size and over-long text stops with an error.
# Usage:   python -m pytest tests/test_render.py -v
#--------------------------------------------------------------#

# Imports Libraries
import struct

import pytest

from visuals.brand import load_brand
from visuals.render import build_html, nobreak
from visuals.specs import spec_from_dict
#--------------------------------------------------------------#

# Helpers
def png_size(path) -> tuple[int, int]:
    """Width and height straight from the PNG header (no image library needed)."""
    with open(path, "rb") as f:
        head = f.read(24)
    return struct.unpack(">II", head[16:24])


@pytest.fixture(scope="module")
def renderer():
    try:
        from visuals.render import Renderer
        r = Renderer().__enter__()
    except Exception as e:                                    # browser not installed yet
        pytest.skip(f"Playwright browser not available: {e}. Run: playwright install chromium")
    yield r
    r.__exit__(None, None, None)


BRAND = load_brand("vizcorn")
#--------------------------------------------------------------#

# Tests: HTML building (no browser needed)
def test_html_has_words_brand_and_size():
    html = build_html(spec_from_dict({"template": "quote", "quote": "Clean data first.",
                                      "author": "VizCorn"}), BRAND, "landscape")
    assert "Clean data first." in html and "#155EEF" in html
    assert "width: 1200px; height: 675px" in html


def test_words_are_shown_as_text_not_html():
    html = build_html(spec_from_dict({"template": "quote", "quote": "<b>bold</b>"}), BRAND, "portrait")
    assert "&lt;b&gt;bold&lt;/b&gt;" in html


def test_css_is_not_escaped():
    html = build_html(spec_from_dict({"template": "quote", "quote": "x"}), BRAND, "portrait")
    assert "&#34;" not in html.split("</style>")[0]          # quotes in CSS must stay quotes


def test_hyphenated_words_stay_together():
    assert nobreak("go-live and S/4HANA") == "go‑live and S/4HANA"
    assert nobreak("a - b") == "a - b"                        # spaced dashes are untouched
#--------------------------------------------------------------#

# Tests: real rendering (skipped if the browser isn't installed)
def test_quote_png_has_exact_size(renderer, tmp_path):
    spec = spec_from_dict({"template": "quote", "quote": "Clean data first."})
    paths = renderer.render(spec, BRAND, "portrait", tmp_path, "q")
    assert [p.name for p in paths] == ["q_portrait.png"]
    assert png_size(paths[0]) == (1080, 1350)


def test_carousel_gives_one_png_per_slide_and_a_pdf(renderer, tmp_path):
    spec = spec_from_dict({"template": "carousel",
                           "slides": [{"title": "One"}, {"title": "Two"}, {"title": "Three"}]})
    paths = renderer.render(spec, BRAND, "square", tmp_path, "c")
    assert [p.name for p in paths] == ["c_square_01.png", "c_square_02.png", "c_square_03.png",
                                       "c_square.pdf"]
    assert png_size(paths[0]) == (1080, 1080)
    assert paths[-1].read_bytes()[:4] == b"%PDF"


def test_text_that_cannot_fit_stops_with_error(renderer, tmp_path):
    from visuals.render import TextOverflowError
    spec = spec_from_dict({"template": "stat", "stat": "42%",
                           "headline": "word " * 22, "body": "x" * 240})
    with pytest.raises(TextOverflowError, match="Shorten it"):
        renderer.render(spec, BRAND, "landscape", tmp_path, "too-long")
#--------------------------------------------------------------#
#----------------------End-of-code-----------------------------#
