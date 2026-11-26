#---------------------beginning-of-code------------------------#
#--------------------------------------------------------------#

# File: tests/test_remotion.py
# Purpose: checks for the 3D device_demo template (Remotion). The fast tests check the
#          rules and the props Python sends to Remotion. The real render takes minutes,
#          so it only runs when you ask for it:
#            RUN_REMOTION=1 python -m pytest tests/test_remotion.py -v
# Usage:   python -m pytest tests/test_remotion.py -v
#--------------------------------------------------------------#

# Imports Libraries
import os
import subprocess

import pytest
from pydantic import ValidationError

from visuals import remotion_bridge
from visuals.brand import load_brand
from visuals.cli import friendly_errors, main
from visuals.paths import INPUTS_DIR
from visuals.remotion_bridge import RemotionError, build_props, render_remotion, step_seconds, total_seconds
from visuals.specs import _batch, load_batch, spec_from_dict
#--------------------------------------------------------------#

# Helpers
CHART = str(INPUTS_DIR / "quartermaster" / "correlations-chart.png")


def demo(**overrides) -> dict:
    data = {
        "template": "device_demo",
        "title": "Correlations. *Now live.*",
        "image": CHART,
        "steps": [{"caption": "Overview"}, {"caption": "Legend", "focus": [0.2, 0.2], "zoom": 2}],
    }
    data.update(overrides)
    return data
#--------------------------------------------------------------#

# Rules
def test_defaults():
    spec = spec_from_dict(demo())
    assert spec.steps[0].focus == (0.5, 0.5)
    assert spec.steps[0].zoom == 1 and spec.steps[0].marker is False
    assert spec.sizes == ["portrait"]
    assert spec.look == "clean"


def test_look_must_be_known():
    assert spec_from_dict(demo(look="cinematic")).look == "cinematic"
    with pytest.raises(ValidationError):
        spec_from_dict(demo(look="noir"))


@pytest.mark.parametrize("step", [
    {"caption": "x", "focus": [1.2, 0.5]},      # focus is 0..1
    {"caption": "x", "zoom": 4},                # zoom is 1..3
    {"caption": "x", "zoom": 0.5},
    {"caption": "x" * 91},                      # caption too long
    {"caption": "x", "colour": "red"},          # typo / unknown field
])
def test_bad_steps_are_refused(step):
    with pytest.raises(ValidationError):
        spec_from_dict(demo(steps=[step]))


def test_step_count_limits():
    with pytest.raises(ValidationError):
        spec_from_dict(demo(steps=[]))
    with pytest.raises(ValidationError):
        spec_from_dict(demo(steps=[{"caption": "x"}] * 7))


def test_duration_must_leave_time_for_every_step():
    with pytest.raises(ValidationError, match="too short"):
        spec_from_dict(demo(duration=6))        # 2.2 + 3.0 + 2 steps x 2.0 = 9.2s minimum
    spec = spec_from_dict(demo(duration=15.2))
    assert step_seconds(spec) == 5.0
    assert total_seconds(spec) == pytest.approx(15.2)


def test_default_length():
    assert total_seconds(spec_from_dict(demo())) == pytest.approx(2.2 + 2 * 3.0 + 3.0)


def test_friendly_error_names_the_step():
    with pytest.raises(ValidationError) as caught:
        _batch.validate_python([demo(steps=[{"caption": "ok"}, {"caption": "x", "zoom": 9}])])
    text = friendly_errors(caught.value)
    assert "step 2" in text and "zoom" in text


def test_example_file_is_valid():
    specs = load_batch(INPUTS_DIR / "quartermaster" / "correlations-demo.yaml")
    assert specs[0].template == "device_demo"


def test_command_line_points_to_yaml():
    assert main(["--client", "quartermaster", "--template", "device_demo"]) == 2
#--------------------------------------------------------------#

# Props sent to Remotion
def test_props_shape():
    props = build_props(spec_from_dict(demo()), load_brand("quartermaster"), "landscape")
    assert (props["width"], props["height"]) == (1200, 676)       # even height for H.264
    assert props["look"] == "clean"
    assert props["brand"]["colors"]["primary"] == "#34D399"
    assert props["brand"]["fontCss"].startswith("@font-face")
    assert props["images"][0]["src"].startswith("data:image/png;base64,")
    assert props["images"][0]["aspect"] == pytest.approx(1135 / 500, rel=1e-3)
    assert props["steps"][1] == {"image": 0, "caption": "Legend", "focus": [0.2, 0.2],
                                 "zoom": 2, "marker": False}


def test_extra_screenshots_are_listed_once():
    other = str(INPUTS_DIR / "quartermaster" / "correlations-chart.png")
    spec = spec_from_dict(demo(steps=[{"caption": "a"}, {"caption": "b", "image": other}]))
    props = build_props(spec, load_brand("quartermaster"), "portrait")
    assert len(props["images"]) == 1                # same file as the main image
    assert [s["image"] for s in props["steps"]] == [0, 0]
#--------------------------------------------------------------#

# Missing tools give a clear message instead of a crash
def test_missing_node(monkeypatch, tmp_path):
    monkeypatch.setattr(remotion_bridge.shutil, "which", lambda name: None)
    with pytest.raises(RemotionError, match="Node.js"):
        render_remotion(spec_from_dict(demo()), load_brand("quartermaster"), "portrait", tmp_path, "x")


def test_missing_packages(monkeypatch, tmp_path):
    monkeypatch.setattr(remotion_bridge, "REMOTION_DIR", tmp_path / "nowhere")
    monkeypatch.setattr(remotion_bridge.shutil, "which", lambda name: "/usr/bin/npx")
    with pytest.raises(RemotionError, match="npm install"):
        render_remotion(spec_from_dict(demo()), load_brand("quartermaster"), "portrait", tmp_path, "x")
#--------------------------------------------------------------#

# The real thing (slow): a short landscape demo renders to an MP4 + poster
@pytest.mark.skipif(not os.environ.get("RUN_REMOTION"), reason="slow: set RUN_REMOTION=1")
def test_render_device_demo(tmp_path):
    spec = spec_from_dict(demo(steps=[{"caption": "Overview"}]))
    made = render_remotion(spec, load_brand("quartermaster"), "landscape", tmp_path, "demo")
    video, poster = made
    probe = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=width,height",
                            "-of", "csv=p=0", str(video)], capture_output=True, text=True).stdout
    assert probe.strip().startswith("1200,676")
    assert poster.stat().st_size > 20_000          # not a blank frame
#--------------------------------------------------------------#
#----------------------End-of-code-----------------------------#


# ---- event_recap (infographic image) ----
def recap(**overrides) -> dict:
    data = {
        "template": "event_recap",
        "title": "On the ground.",
        "intro": "Short intro.",
        "cards": [{"icon": "flask", "name": "A", "topic": "T", "body": "B"},
                  {"icon": "leaf", "name": "C", "topic": "T", "body": "B"}],
        "big_picture": {"title": "One line."},
        "closing": "Bye.",
    }
    data.update(overrides)
    return data


def test_recap_defaults_and_example_file():
    spec = spec_from_dict(recap())
    assert spec.sizes == ["portrait"] and spec.video is False
    assert spec.big_picture.label == "The bigger picture"
    specs = load_batch(INPUTS_DIR / "vizcorn" / "lubricant-expo-recap.yaml")
    assert specs[0].template == "event_recap" and len(specs[0].cards) == 4


@pytest.mark.parametrize("change", [
    {"cards": [{"icon": "flask", "name": "A", "topic": "T", "body": "B"}]},          # too few cards
    {"cards": [{"icon": "flask", "name": "A", "topic": "T", "body": "B"}] * 5},      # too many
    {"cards": [{"icon": "rocket", "name": "A", "topic": "T", "body": "B"}] * 2},     # unknown icon
    {"cards": [{"icon": "flask", "name": "A", "topic": "T", "body": "x" * 176}] * 2},
    {"sizes": ["landscape"]},                                                        # portrait only
    {"stats": [{"value": "1", "label": "a"}] * 4},
])
def test_recap_limits(change):
    with pytest.raises(ValidationError):
        spec_from_dict(recap(**change))


def test_recap_props_shape():
    props = build_props(spec_from_dict(recap(title_accent="Accent")), load_brand("vizcorn"), "portrait")
    assert (props["width"], props["height"]) == (1080, 1350)
    assert props["titleAccent"] == "Accent"
    assert props["bigPicture"] == {"label": "The bigger picture", "title": "One line.",
                                   "pointsLabel": None, "points": []}
    assert props["cards"][0] == {"icon": "flask", "name": "A", "org": None, "topic": "T", "body": "B"}


# ---- explainer and talking_head (basic templates) ----
def test_explainer_rules_and_props():
    hook = {"kind": "hook", "text": "Why?"}
    with pytest.raises(ValidationError):                  # a chart needs a source
        spec_from_dict({"template": "explainer", "scenes": [hook, {"kind": "chart", "image": CHART, "caption": "c"}]})
    with pytest.raises(ValidationError, match="60 seconds"):
        spec_from_dict({"template": "explainer", "scenes": [{**hook, "seconds": 10}] * 7})
    spec = spec_from_dict({"template": "explainer", "scenes": [
        hook, {"kind": "chart", "image": CHART, "caption": "c", "source": "s", "zoom": 1.5}]})
    props = build_props(spec, load_brand("quartermaster"), "story")
    assert (props["width"], props["height"]) == (1080, 1920)
    assert [s["frames"] for s in props["scenes"]] == [90, 150]          # 3s hook, 5s chart
    assert props["scenes"][1]["image"]["src"].startswith("data:image/png")


def test_talking_head_rules():
    base = {"template": "talking_head", "footage": "talk.mp4"}
    title = {"kind": "title", "text": "Name", "at": 1, "seconds": 4}
    spec_from_dict({**base, "overlays": [title, {**title, "at": 5}]})
    with pytest.raises(ValidationError, match="overlap"):
        spec_from_dict({**base, "overlays": [title, {**title, "at": 3}]})
    with pytest.raises(ValidationError, match="time order"):
        spec_from_dict({**base, "overlays": [{**title, "at": 9}, title]})
    with pytest.raises(ValidationError):
        spec_from_dict({**base, "overlays": [{"kind": "stat", "at": 1, "value": "1", "label": "x"}]})  # no source


def test_talking_head_props_use_original_timestamps(monkeypatch):
    monkeypatch.setattr(remotion_bridge, "media_seconds", lambda path: 20.0)
    spec = spec_from_dict({"template": "talking_head", "footage": "/x/talk.mp4", "start": 2,
                           "overlays": [{"kind": "title", "text": "Name", "at": 3, "seconds": 4}]})
    props = build_props(spec, load_brand("quartermaster"), "story")
    assert props["footage"] == "talk.mp4" and props["startFrame"] == 60
    assert props["durationFrames"] == 540                                 # 2s..20s
    assert props["overlays"][0]["from"] == 30 and props["overlays"][0]["frames"] == 120
    bad = spec_from_dict({"template": "talking_head", "footage": "/x/talk.mp4",
                          "overlays": [{"kind": "title", "text": "Name", "at": 18, "seconds": 4}]})
    with pytest.raises(RemotionError, match="outside the video"):
        build_props(bad, load_brand("quartermaster"), "story")


def test_errors_show_the_message_not_the_stack_trace():
    from visuals.remotion_bridge import error_summary, render_flags
    out = "Rendering frames 10/300\nError: Browser crashed\n    at a (x.js:1)\n    at b (y.js:2)"
    assert error_summary(out).endswith("Error: Browser crashed")
    assert "--concurrency=2" in render_flags("device_demo")
    assert not any(f.startswith("--concurrency") for f in render_flags("explainer"))
