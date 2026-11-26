#---------------------beginning-of-code------------------------#
#--------------------------------------------------------------#

# File: tests/test_ideas.py
# Purpose: checks for buckets and the idea -> spec flow. The LLM is replaced by a fake, so
#          these run offline and cost nothing.
# Usage:   python -m pytest tests/test_ideas.py -v
#--------------------------------------------------------------#

# Imports Libraries
import json
import shutil

import pytest
import yaml
from pydantic import ValidationError

from visuals import ideas, llm
from visuals.buckets import Bucket, load_buckets
from visuals.cli import main
from visuals.ideas import build_prompt, choose, make_check, make_spec, numbers_in
from visuals.paths import INPUTS_DIR
from visuals.specs import spec_from_dict
#--------------------------------------------------------------#

# Helpers
CHART = INPUTS_DIR / "quartermaster" / "correlations-chart.png"


@pytest.fixture
def inbox(tmp_path, monkeypatch):
    """A temporary inputs folder with one screenshot, so tests never write into the repo."""
    (tmp_path / "quartermaster").mkdir()
    shutil.copy(CHART, tmp_path / "quartermaster" / "heatmap.png")
    monkeypatch.setattr(ideas, "INPUTS_DIR", tmp_path)
    monkeypatch.setenv("LLM_MODEL_FAST", "fake-fast")
    monkeypatch.setenv("LLM_MODEL_SMART", "fake-smart")
    monkeypatch.setattr(llm, "LOG_FILE", tmp_path / "llm_calls.csv")
    return tmp_path


def fake_llm(monkeypatch, replies: list[dict]):
    """Each call returns the next reply; records which model was asked."""
    calls = []

    def send(model, system, messages, max_tokens):
        calls.append(model)
        return json.dumps(replies[len(calls) - 1]), 100, 50
    monkeypatch.setattr(llm, "_send", send)
    return calls


DEMO = {"template": "device_demo", "name": "heatmap-launch", "kicker": "New in Quartermaster",
        "title": "Sector heatmap", "image": "heatmap.png", "cta": "app.quartermasterlabs.com",
        "steps": [{"caption": "Every sector at a glance"},
                  {"caption": "Spot the 11 sectors moving most", "focus": [0.3, 0.3], "zoom": 2}]}
#--------------------------------------------------------------#

# Buckets
def test_client_buckets_load():
    qm, vz = load_buckets("quartermaster"), load_buckets("vizcorn")
    assert set(qm) == {"feature_launch", "explainer", "talking_head"}
    assert set(vz) == {"linkedin_image", "generic_video"}
    assert qm["explainer"].status == "draft" and "Basic draft" in qm["explainer"].status_note()
    assert vz["generic_video"].status == "samples_needed"
    assert qm["feature_launch"].formats["video"].defaults["text_style"] == "plain"
    assert set(qm["feature_launch"].formats) == {"video", "image"}


def test_bucket_rules():
    base = {"label": "x", "brief": "y", "formats": {"video": {"templates": ["explainer"]}}}
    Bucket.model_validate(base)
    with pytest.raises(ValidationError):
        Bucket.model_validate({**base, "formats": {"video": {"templates": ["nope"]}}})
    with pytest.raises(ValidationError):                    # default that isn't a field
        Bucket.model_validate({**base, "formats": {"video": {"templates": ["explainer"], "defaults": {"colour": 1}}}})
    with pytest.raises(ValidationError):
        Bucket.model_validate({**base, "formats": {"audio": {"templates": ["explainer"]}}})


def test_choose_format_and_template():
    b = load_buckets("quartermaster")["feature_launch"]
    assert choose(b, None, None) == ("video", "device_demo")
    assert choose(b, "image", None) == ("image", "title")
    with pytest.raises(ValueError):
        choose(load_buckets("quartermaster")["talking_head"], "image", None)
    with pytest.raises(ValueError):
        choose(b, "video", "stat")
#--------------------------------------------------------------#

# Number and file checks
def test_numbers_are_normalised():
    assert numbers_in("~5,000 people, 57% and 0.2280 and −1") == {"5000", "57", "0.228", "1"}


def test_check_flags_invented_numbers_and_files():
    check = make_check("Attendance was 5,000. Correlation 0.228", {"heatmap.png": "image"})
    good = spec_from_dict({**DEMO, "steps": [{"caption": "About 5,000 people, correlation 0.228"}]})
    assert check(good) == []
    bad = spec_from_dict({**DEMO, "image": "other.png", "steps": [{"caption": "Up 42% this year"}]})
    problems = check(bad)
    assert any("other.png" in p for p in problems)
    assert any("42" in p for p in problems)


def test_prompt_is_complete():
    b = load_buckets("quartermaster")["feature_launch"]
    text = build_prompt("Quartermaster", b, "video", "device_demo", "Announce X", "- heatmap.png (image)")
    assert "{{" not in text and "Announce X" in text and "text_style: plain" in text
#--------------------------------------------------------------#

# The whole flow, with a fake LLM
def test_make_spec_writes_reviewable_yaml(inbox, monkeypatch):
    calls = fake_llm(monkeypatch, [DEMO])
    path, warnings = make_spec("quartermaster", "feature_launch",
                               "Announce the sector heatmap. It covers 11 sectors.", ["heatmap.png"])
    assert calls == ["fake-fast"] and warnings == []
    text = path.read_text()
    assert text.startswith("# Draft from the idea command")
    data = yaml.safe_load(text)[0]
    assert data["look"] == "cinematic" and data["text_style"] == "plain"      # bucket defaults win
    assert data["sizes"] == ["portrait", "landscape"]
    assert path.name == "heatmap-launch.yaml"


def test_invented_number_is_sent_back_and_fixed(inbox, monkeypatch):
    invented = {**DEMO, "steps": [{"caption": "Up 42% this year"}]}
    calls = fake_llm(monkeypatch, [invented, DEMO])
    path, warnings = make_spec("quartermaster", "feature_launch", "Heatmap of 11 sectors", ["heatmap.png"])
    assert len(calls) == 2 and warnings == []


def test_problem_left_after_retries_is_flagged(inbox, monkeypatch):
    invented = {**DEMO, "steps": [{"caption": "Up 42% this year"}]}
    fake_llm(monkeypatch, [invented] * 3)
    path, warnings = make_spec("quartermaster", "feature_launch", "Heatmap of 11 sectors", ["heatmap.png"])
    assert warnings and "# CHECK: numbers 42" in path.read_text()


def test_draft_bucket_is_labelled_and_uses_smart_model(inbox, monkeypatch):
    calls = fake_llm(monkeypatch, [{"template": "explainer", "name": "corr",
                                    "scenes": [{"kind": "hook", "text": "Do stocks move with Bitcoin?"},
                                               {"kind": "cta", "text": "Try it", "url": "app.quartermasterlabs.com"}]}])
    path, _ = make_spec("quartermaster", "explainer", "Explain correlation", [])
    assert calls == ["fake-smart"]
    assert "# NOTE: Basic draft template" in path.read_text()
    assert yaml.safe_load(path.read_text())[0]["sizes"] == ["story"]


def test_never_overwrites(inbox, monkeypatch):
    fake_llm(monkeypatch, [DEMO, DEMO])
    first, _ = make_spec("quartermaster", "feature_launch", "Heatmap of 11 sectors", ["heatmap.png"])
    second, _ = make_spec("quartermaster", "feature_launch", "Heatmap of 11 sectors", ["heatmap.png"])
    assert first.name == "heatmap-launch.yaml" and second.name == "heatmap-launch-2.yaml"
    assert yaml.safe_load(second.read_text())[0]["name"] == "heatmap-launch-2"


def test_template_needing_a_file(inbox, monkeypatch):
    fake_llm(monkeypatch, [DEMO])
    with pytest.raises(ValueError, match="needs an attached image"):
        make_spec("quartermaster", "feature_launch", "Heatmap", [])


def test_command_line(inbox, monkeypatch, capsys):
    fake_llm(monkeypatch, [DEMO])
    assert main(["buckets", "--client", "quartermaster"]) == 0
    assert "feature_launch" in capsys.readouterr().out
    assert main(["idea", "--client", "quartermaster", "--bucket", "feature_launch",
                 "--files", "heatmap.png", "--idea", "Heatmap of 11 sectors"]) == 0
    assert "Wrote" in capsys.readouterr().out
    assert main(["idea", "--client", "quartermaster", "--bucket", "nope", "--idea", "x"]) == 2


def test_missing_model_setting(monkeypatch):
    monkeypatch.delenv("LLM_MODEL_FAST", raising=False)
    monkeypatch.delenv("LLM_MODEL", raising=False)
    with pytest.raises(llm.LLMError, match="LLM_MODEL_FAST"):
        llm.settings("fast")
#--------------------------------------------------------------#
#----------------------End-of-code-----------------------------#


# Screenshots are sent to the model so it can see them
def test_screenshots_are_sent_to_the_model(inbox, monkeypatch):
    seen = []

    def send(model, system, messages, max_tokens):
        seen.append(messages[0])
        return json.dumps(DEMO), 100, 50
    monkeypatch.setattr(llm, "_send", send)
    make_spec("quartermaster", "feature_launch", "Heatmap of 11 sectors", ["heatmap.png"])
    first = seen[0]
    assert len(first["images"]) == 1 and first["images"][0][0] == "image/png"
    assert "heatmap.png (attached image 1" in first["content"]


def test_both_api_shapes_carry_the_image():
    msgs = [{"role": "user", "content": "hi", "images": [("image/png", "AAAA")]}]
    gw = llm._to_api("gateway", msgs)[0]["content"]
    assert gw[0] == {"type": "text", "text": "hi"} and gw[1]["image_url"]["url"] == "data:image/png;base64,AAAA"
    an = llm._to_api("anthropic", msgs)[0]["content"]
    assert an[0]["source"]["data"] == "AAAA" and an[-1] == {"type": "text", "text": "hi"}
    assert llm._to_api("gateway", [{"role": "user", "content": "x"}]) == [{"role": "user", "content": "x"}]


def test_falls_back_to_text_if_images_are_refused(inbox, monkeypatch):
    calls = []

    def send(model, system, messages, max_tokens):
        calls.append(bool(messages[0]["images"]))
        if messages[0]["images"]:
            raise RuntimeError("image input not supported")
        return json.dumps(DEMO), 100, 50
    monkeypatch.setattr(llm, "_send", send)
    path, warnings = make_spec("quartermaster", "feature_launch", "Heatmap of 11 sectors", ["heatmap.png"])
    assert calls == [True, False]
    assert any("could not take the screenshots" in w for w in warnings)
    assert "# CHECK: the model could not take the screenshots" in path.read_text()


def test_big_images_are_scaled_down(tmp_path):
    from PIL import Image
    big = tmp_path / "big.png"
    Image.new("RGB", (4000, 1000), "white").save(big)
    import base64, io
    mt, data = llm.encode_image(big)
    with Image.open(io.BytesIO(base64.b64decode(data))) as img:
        assert img.size == (1568, 392)
