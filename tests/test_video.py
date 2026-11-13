#---------------------beginning-of-code------------------------#
#--------------------------------------------------------------#

# File: tests/test_video.py
# Purpose: check slideshow videos: timing maths, options, and (if FFmpeg and the browser are
#          installed) real MP4s with the right size, length and audio.
# Usage:   python -m pytest tests/test_video.py -v
#--------------------------------------------------------------#

# Imports Libraries
import json
import shutil
import subprocess

import pytest
from pydantic import ValidationError

from visuals.brand import load_brand
from visuals.render import build_html
from visuals.specs import spec_from_dict
from visuals.video import VideoError, build_filter, make_slideshow, total_seconds
#--------------------------------------------------------------#

# Helpers
BRAND = load_brand("vizcorn")
needs_ffmpeg = pytest.mark.skipif(not shutil.which("ffmpeg") or not shutil.which("ffprobe"),
                                  reason="FFmpeg not installed (brew install ffmpeg)")


def probe(path) -> dict:
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries",
                          "stream=codec_type,width,height:format=duration", "-of", "json", str(path)],
                         capture_output=True, text=True, check=True).stdout
    return json.loads(out)


@pytest.fixture(scope="module")
def renderer():
    try:
        from visuals.render import Renderer
        r = Renderer().__enter__()
    except Exception as e:
        pytest.skip(f"Playwright browser not available: {e}")
    yield r
    r.__exit__(None, None, None)


CAROUSEL = {"template": "carousel", "slides": [{"title": "One"}, {"title": "Two"}, {"title": "Three"}]}
#--------------------------------------------------------------#

# Tests: timing and options (no FFmpeg needed)
def test_total_length_subtracts_transitions():
    assert total_seconds(5, 3.5) == pytest.approx(5 * 3.5 - 4 * 0.5)
    assert total_seconds(1, 4) == 4


def test_filter_has_one_transition_between_each_pair():
    f = build_filter(4, 3.0, 1080, 1350)
    assert f.count("xfade=") == 3 and f.count("zoompan=") == 4
    assert "xfade" not in build_filter(1, 3.0, 1080, 1350)


def test_video_options_are_checked():
    assert spec_from_dict({**CAROUSEL, "video": True}).seconds_per_slide == 3.5
    with pytest.raises(ValidationError):
        spec_from_dict({**CAROUSEL, "video": True, "seconds_per_slide": 30})


def test_video_slides_have_no_swipe_hint():
    spec = spec_from_dict(CAROUSEL)
    assert "Swipe" in build_html(spec, BRAND, "portrait")
    assert "Swipe" not in build_html(spec, BRAND, "portrait", for_video=True)


def test_missing_music_is_a_clear_error(tmp_path):
    with pytest.raises(VideoError, match="Music file not found"):
        make_slideshow([tmp_path / "a.png"], tmp_path / "v.mp4", 1080, 1350,
                       music=tmp_path / "nope.mp3")
#--------------------------------------------------------------#

# Tests: real videos (skipped if FFmpeg or the browser isn't installed)
@needs_ffmpeg
def test_carousel_video_size_and_length(renderer, tmp_path):
    spec = spec_from_dict(CAROUSEL)
    frames = renderer.render(spec, BRAND, "story", tmp_path, "c", for_video=True)
    assert [f.suffix for f in frames] == [".png"] * 3                 # no PDF for video frames
    video = make_slideshow(frames, tmp_path / "c.mp4", 1080, 1920, seconds_per_slide=2)
    info = probe(video)
    v = info["streams"][0]
    assert (v["width"], v["height"]) == (1080, 1920)
    assert float(info["format"]["duration"]) == pytest.approx(total_seconds(3, 2), abs=0.1)


@needs_ffmpeg
def test_music_adds_an_audio_track(renderer, tmp_path):
    tone = tmp_path / "tone.mp3"
    subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "sine=frequency=440:duration=10",
                    str(tone)], check=True)
    spec = spec_from_dict({"template": "quote", "quote": "Clean data first."})
    frames = renderer.render(spec, BRAND, "portrait", tmp_path, "q", for_video=True)
    video = make_slideshow(frames, tmp_path / "q.mp4", 1080, 1350, seconds_per_slide=3, music=tone)
    info = probe(video)
    assert sorted(s["codec_type"] for s in info["streams"]) == ["audio", "video"]
    assert float(info["format"]["duration"]) == pytest.approx(3, abs=0.1)
#--------------------------------------------------------------#
#----------------------End-of-code-----------------------------#
