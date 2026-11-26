#---------------------beginning-of-code------------------------#
#--------------------------------------------------------------#

# File: tests/test_web.py
# Purpose: checks for the web app's API. Everything runs in a temporary folder with a fake
#          LLM and a fake renderer, so nothing in inputs/ or outputs/ changes and it's free.
# Usage:   python -m pytest tests/test_web.py -v
#--------------------------------------------------------------#

# Imports Libraries
import base64
import json
import shutil
import time

import pytest
import yaml
from fastapi.testclient import TestClient

from visuals import cli, ideas, llm, paths
from visuals.web import app as webapp
from visuals.web import jobs
#--------------------------------------------------------------#

# Helpers
CHART = paths.INPUTS_DIR / "quartermaster" / "correlations-chart.png"

DEMO = {"template": "device_demo", "name": "heatmap-launch", "kicker": "New in Quartermaster",
        "title": "Sector heatmap", "image": "heatmap.png", "cta": "app.quartermasterlabs.com",
        "steps": [{"caption": "Every sector at a glance"},
                  {"caption": "The 11 sectors side by side", "focus": [0.3, 0.3], "zoom": 2}]}
QUOTE = {"template": "quote", "name": "q1", "quote": "Data first.", "author": "Someone"}


@pytest.fixture
def api(tmp_path, monkeypatch):
    inputs, outputs = tmp_path / "inputs", tmp_path / "outputs"
    (inputs / "quartermaster").mkdir(parents=True)
    shutil.copy(CHART, inputs / "quartermaster" / "heatmap.png")
    for module in (webapp, cli, ideas, paths):
        monkeypatch.setattr(module, "INPUTS_DIR", inputs)
    for module in (webapp, jobs, paths):
        monkeypatch.setattr(module, "OUTPUTS_DIR", outputs)
    monkeypatch.setattr(jobs, "DB_PATH", tmp_path / "web.db")
    monkeypatch.setattr(llm, "LOG_FILE", tmp_path / "llm.csv")
    monkeypatch.setenv("LLM_MODEL_FAST", "fake")
    monkeypatch.setenv("LLM_MODEL_SMART", "fake")
    monkeypatch.setattr(llm, "_send", lambda *a: (json.dumps(DEMO), 10, 10))
    monkeypatch.delenv("WEBAPP_PASSWORD", raising=False)
    with TestClient(webapp.create_app()) as client:
        client.tmp = tmp_path
        yield client


def write_spec(api, name: str, items: list[dict]) -> None:
    (api.tmp / "inputs" / "quartermaster" / name).write_text(yaml.safe_dump(items))
#--------------------------------------------------------------#

# Clients, templates, files
def test_clients_and_templates(api):
    clients = {c["name"]: c for c in api.get("/api/clients").json()}
    assert {"quartermaster", "vizcorn"} <= set(clients)
    qm = clients["quartermaster"]
    assert qm["colors"]["primary"] == "#34D399"
    assert set(qm["buckets"]["feature_launch"]["formats"]) == {"video", "image"}
    t = api.get("/api/templates").json()
    assert t["device_demo"]["kind"] == "video" and t["event_recap"]["sizes"] == ["portrait"]
    assert t["quote"]["kind"] == "image" and "landscape" in t["quote"]["sizes"]


def test_upload_and_list_files(api):
    r = api.post("/api/files/quartermaster", files={"file": ("My Chart.png", CHART.read_bytes(), "image/png")})
    assert r.json()["name"] == "My-Chart.png"
    r2 = api.post("/api/files/quartermaster", files={"file": ("My Chart.png", b"x", "image/png")})
    assert r2.json()["name"] == "My-Chart-2.png"                       # never overwrites
    names = [f["name"] for f in api.get("/api/files/quartermaster").json()]
    assert {"heatmap.png", "My-Chart.png", "My-Chart-2.png"} <= set(names)
    assert api.get("/files/quartermaster/heatmap.png").status_code == 200
    bad = api.post("/api/files/quartermaster", files={"file": ("x.exe", b"x", "application/octet-stream")})
    assert bad.status_code == 400


def test_paths_cannot_escape(api):
    for url in ("/files/quartermaster/..%2F..%2Fpyproject.toml", "/api/specs/quartermaster/..%2Fx.yaml",
                "/outputs/..%2Fpyproject.toml", "/files/quartermaster/../../pyproject.toml"):
        r = api.get(url)
        assert r.status_code >= 400 and b"[project]" not in r.content, url
    assert api.get("/api/files/nobody").status_code == 404
#--------------------------------------------------------------#

# Idea -> draft -> edit -> preview
def test_idea_creates_draft_in_library(api):
    r = api.post("/api/ideas", json={"client": "quartermaster", "bucket": "feature_launch",
                                     "idea": "Heatmap of 11 sectors", "files": ["heatmap.png"]})
    assert r.status_code == 200, r.text
    assert r.json()["file"] == "heatmap-launch.yaml"
    lib = api.get("/api/specs/quartermaster").json()
    assert lib[0]["file"] == "heatmap-launch.yaml" and lib[0]["bucket"] == "feature_launch"
    assert lib[0]["format"] == "video" and lib[0]["from_idea"]
    spec = api.get("/api/specs/quartermaster/heatmap-launch.yaml").json()
    assert spec["items"][0]["text_style"] == "plain"
    assert spec["sizes"] == [["portrait", "landscape"]]
    write_spec(api, "nosizes.yaml", [QUOTE])                      # no sizes written: template default
    assert api.get("/api/specs/quartermaster/nosizes.yaml").json()["sizes"] == [["portrait"]]


def test_idea_errors_are_readable(api):
    r = api.post("/api/ideas", json={"client": "quartermaster", "bucket": "nope", "idea": "x"})
    assert r.status_code == 400 and "No bucket" in r.json()["errors"][0]


def test_save_checks_and_keeps_header(api):
    (api.tmp / "inputs" / "quartermaster" / "d.yaml").write_text("# Draft from the idea command\n# NOTE: hi\n\n"
                                                                + yaml.safe_dump([DEMO]))
    bad = api.put("/api/specs/quartermaster/d.yaml/0", json={"spec": {**DEMO, "title": "x" * 200}})
    assert bad.status_code == 422 and any("title" in e for e in bad.json()["errors"])
    missing = api.put("/api/specs/quartermaster/d.yaml/0", json={"spec": {**DEMO, "image": "nope.png"}})
    assert missing.status_code == 422 and "nope.png" in missing.json()["errors"][0]
    ok = api.put("/api/specs/quartermaster/d.yaml/0", json={"spec": {**DEMO, "title": "Better title"}})
    assert ok.status_code == 200 and ok.json()["notes"] == ["hi"]
    assert ok.json()["items"][0]["title"] == "Better title"


def test_save_raw_yaml(api):
    write_spec(api, "r.yaml", [QUOTE])
    r = api.put("/api/specs/quartermaster/r.yaml", json={"text": "# mine\n- template: quote\n  quote: New\n"})
    assert r.status_code == 200 and r.json()["items"][0]["quote"] == "New"
    assert api.put("/api/specs/quartermaster/r.yaml", json={"text": "- : ["}).status_code == 422


def test_preview_remotion_and_html(api):
    r = api.post("/api/preview", json={"client": "quartermaster", "spec": DEMO, "size": "landscape"}).json()
    assert r["kind"] == "remotion" and r["composition"] == "DeviceDemo"
    assert (r["width"], r["height"]) == (1200, 676) and r["durationInFrames"] == round((2.2 + 6 + 3) * 30)
    assert r["props"]["textStyle"] == "animated" and r["props"]["images"][0]["src"].startswith("data:")
    h = api.post("/api/preview", json={"client": "quartermaster", "spec": QUOTE, "size": "square"}).json()
    assert h["kind"] == "html" and "Data first." in h["html"]
    bad = api.post("/api/preview", json={"client": "quartermaster", "spec": {**QUOTE, "quote": ""}, "size": "square"})
    assert bad.status_code == 422
#--------------------------------------------------------------#

# Renders go through the queue
def test_render_job_runs_in_background(api, monkeypatch):
    out = api.tmp / "outputs" / "quartermaster" / "today"

    def fake_render(client, brand, specs, out_dir, keep=False):
        out.mkdir(parents=True, exist_ok=True)
        f = out / f"{specs[0].name}_{specs[0].sizes[0]}.png"
        f.write_bytes(b"png")
        return [f], []
    monkeypatch.setattr(cli, "render_specs", fake_render)
    write_spec(api, "q.yaml", [QUOTE])
    job = api.post("/api/render", json={"client": "quartermaster", "file": "q.yaml", "sizes": ["square"]}).json()
    assert job["status"] in ("queued", "running", "done")
    for _ in range(50):
        job = api.get(f"/api/jobs/{job['id']}").json()
        if job["status"] in ("done", "failed"):
            break
        time.sleep(0.1)
    assert job["status"] == "done", job
    assert job["urls"] == ["/outputs/quartermaster/today/q1_square.png"]
    assert api.get(job["urls"][0]).content == b"png"
    assert api.get("/api/jobs?client=quartermaster").json()[0]["id"] == job["id"]


def test_render_refuses_invalid_spec(api):
    write_spec(api, "bad.yaml", [{**QUOTE, "quote": ""}])
    assert api.post("/api/render", json={"client": "quartermaster", "file": "bad.yaml"}).status_code == 422
#--------------------------------------------------------------#

# Password
def test_password_when_set(monkeypatch, tmp_path):
    monkeypatch.setenv("WEBAPP_PASSWORD", "s3cret")
    monkeypatch.setattr(jobs, "DB_PATH", tmp_path / "web.db")
    client = TestClient(webapp.create_app())
    assert client.get("/api/templates").status_code == 401
    good = "Basic " + base64.b64encode(b"admin:s3cret").decode()
    assert client.get("/api/templates", headers={"Authorization": good}).status_code == 200


def test_refuses_open_network_without_password(monkeypatch):
    monkeypatch.delenv("WEBAPP_PASSWORD", raising=False)
    monkeypatch.setattr(webapp, "load_dotenv", lambda *a: None, raising=False)
    assert webapp.main(["web", "--host", "0.0.0.0"]) == 2
#--------------------------------------------------------------#
#----------------------End-of-code-----------------------------#
