#---------------------beginning-of-code------------------------#
#--------------------------------------------------------------#

# File: tests/test_motion.py
# Purpose: check the motion templates (stat_motion, quote_motion): what counts up, *emphasis*,
#          input rules, and (if FFmpeg and the browser are installed) real MP4s + posters.
# Usage:   python -m pytest tests/test_motion.py -v
#--------------------------------------------------------------#

# Imports Libraries
import json
import shutil
import struct
import subprocess

import pytest
from pydantic import ValidationError

from visuals.brand import load_brand
from visuals.render import build_html, emphasis
from visuals.specs import spec_from_dict, split_stat
#--------------------------------------------------------------#

# Helpers
BRAND = load_brand("vizcorn")
needs_ffmpeg = pytest.mark.skipif(not shutil.which("ffmpeg") or not shutil.which("ffprobe"),
                                  reason="FFmpeg not installed (brew install ffmpeg)")
STAT = {"template": "stat_motion", "stat": "75%", "headline": "of delays start with data"}
QUOTE = {"template": "quote_motion", "quote": "Fix the *data* first, then migrate.", "author": "VizCorn"}


def probe(path) -> dict:
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries",
                          "stream=codec_type,width,height:format=duration", "-of", "json", str(path)],
                         capture_output=True, text=True, check=True).stdout
    return json.loads(out)


def png_size(path) -> tuple[int, int]:
    with open(path, "rb") as f:
        return struct.unpack(">II", f.read(24)[16:24])


@pytest.fixture(scope="module")
def renderer():
    try:
        from visuals.render import Renderer
        r = Renderer().__enter__()
    except Exception as e:
        pytest.skip(f"Playwright browser not available: {e}")
    yield r
    r.__exit__(None, None, None)
#--------------------------------------------------------------#

# Tests: which stats count up
@pytest.mark.parametrize("stat, value, decimals", [
    ("75%", 75, 0), ("€1.2M", 1.2, 1), ("1,250", 1250, 0), ("$4.5B", 4.5, 1), ("40+", 40, 0)])
def test_countable_stats(stat, value, decimals):
    s = split_stat(stat)
    assert s["value"] == value and s["decimals"] == decimals


@pytest.mark.parametrize("stat", ["3 in 4", "24/7", "Q3", "FY24", "2025", "A+"])
def test_stats_that_just_fade_in(stat):
    assert split_stat(stat) is None


def test_count_keeps_prefix_suffix_and_thousands():
    s = split_stat("€1,250+")
    assert (s["prefix"], s["thousands"], s["suffix"]) == ("€", ",", "+")
#--------------------------------------------------------------#

# Tests: *emphasis* and safety
def test_emphasis_marks_words():
    assert str(emphasis("Fix the *data* first")) == 'Fix the <span class="em">data</span> first'


def test_emphasis_never_lets_html_through():
    out = str(emphasis("<script>x</script> *ok*"))
    assert "<script>" not in out and '<span class="em">ok</span>' in out


def test_static_quote_supports_emphasis_too():
    html = build_html(spec_from_dict({"template": "quote", "quote": "Fix the *data*"}), BRAND, "portrait")
    assert '<span class="em">data</span>' in html
#--------------------------------------------------------------#

# Tests: input rules
def test_motion_has_no_slideshow_options():
    with pytest.raises(ValidationError):
        spec_from_dict({**STAT, "video": True})
    with pytest.raises(ValidationError):
        spec_from_dict({**STAT, "duration": 60})              # max 30 seconds


def test_stat_html_carries_count_data():
    html = build_html(spec_from_dict(STAT), BRAND, "portrait")
    assert 'data-value="75.0"' in html and 'data-final="75%"' in html
    plain = build_html(spec_from_dict({**STAT, "stat": "3 in 4"}), BRAND, "portrait")
    assert "data-value" not in plain
#--------------------------------------------------------------#

# Tests: real videos (skipped if FFmpeg or the browser isn't installed)
@needs_ffmpeg
def test_stat_motion_makes_video_and_poster(renderer, tmp_path):
    video, poster = renderer.render_motion(spec_from_dict(STAT), BRAND, "portrait", tmp_path, "s")
    info = probe(video)
    assert (info["streams"][0]["width"], info["streams"][0]["height"]) == (1080, 1350)
    assert float(info["format"]["duration"]) == pytest.approx(3.2 + 2.5, abs=0.1)   # end + hold
    assert png_size(poster) == (1080, 1350)


@needs_ffmpeg
def test_quote_motion_landscape_and_fixed_duration(renderer, tmp_path):
    spec = spec_from_dict({**QUOTE, "duration": 7})
    video, _ = renderer.render_motion(spec, BRAND, "landscape", tmp_path, "q")
    info = probe(video)
    assert (info["streams"][0]["width"], info["streams"][0]["height"]) == (1200, 676)  # even size
    assert float(info["format"]["duration"]) == pytest.approx(7, abs=0.1)


@needs_ffmpeg
def test_motion_text_too_long_stops(renderer, tmp_path):
    from visuals.render import TextOverflowError
    spec = spec_from_dict({**STAT, "headline": "word " * 22, "body": "x" * 240})
    with pytest.raises(TextOverflowError):
        renderer.render_motion(spec, BRAND, "landscape", tmp_path, "long")
#--------------------------------------------------------------#
#----------------------End-of-code-----------------------------#
