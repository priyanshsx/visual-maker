#---------------------beginning-of-code------------------------#
#--------------------------------------------------------------#

# File: visuals/web/app.py
# Purpose: the visual-maker web app (API + the page in remotion/web-dist).
#   Start it:  python -m visuals web            -> http://127.0.0.1:8000
#   From anywhere later: run it behind a secure tunnel with a password set in .env:
#     WEBAPP_USER=...  WEBAPP_PASSWORD=...   (required whenever it listens beyond this Mac)
#
#   The app adds no new storage for drafts: a draft IS a YAML file in inputs/<client>/,
#   so the command line and the app always see the same work. Renders are queued (jobs.py).
#
#   API (all JSON):
#     GET  /api/clients                         brands + buckets (formats, templates, status)
#     GET  /api/templates                       per template: video/image, allowed sizes
#     GET  /api/files/{client}                  attachable files in inputs/<client>/
#     POST /api/files/{client}                  upload a file (never overwrites)
#     POST /api/ideas                           idea -> draft YAML (LLM)
#     GET  /api/specs/{client}                  library: all spec files, newest first
#     GET  /api/specs/{client}/{file}           one file: header notes, entries, raw YAML
#     PUT  /api/specs/{client}/{file}/{item}    save one entry (checked first)
#     PUT  /api/specs/{client}/{file}           save the raw YAML (checked first)
#     POST /api/preview                         what the browser needs to preview a spec
#     POST /api/render, GET /api/jobs[/{id}]    queue a render, follow it
#     GET  /files/{client}/{name}, /outputs/... the files themselves
#--------------------------------------------------------------#

# Imports Libraries
import base64
import os
import re
import secrets
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import get_args

import yaml
from fastapi import FastAPI, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ValidationError

from visuals.brand import load_brand
from visuals.buckets import load_buckets
from visuals.paths import BRANDS_DIR, INPUTS_DIR, OUTPUTS_DIR, ROOT
from visuals.specs import SIZES, SPEC_CLASSES, load_batch, spec_from_dict
from visuals.web import jobs
#--------------------------------------------------------------#

# Global variables
WEB_DIST = ROOT / "remotion" / "web-dist"
VIDEO_TEMPLATES = {"device_demo", "explainer", "talking_head", "quote_motion", "stat_motion"}
FILE_KINDS = {
    "image": {".png", ".jpg", ".jpeg", ".webp", ".svg"},
    "video": {".mp4", ".mov", ".m4v", ".webm"},
    "audio": {".mp3", ".wav", ".m4a", ".aac"},
    "data": {".csv"},
    "text": {".txt", ".md", ".srt", ".vtt", ".json"},
}
#--------------------------------------------------------------#

# Request bodies
class IdeaIn(BaseModel):
    client: str
    bucket: str
    idea: str
    files: list[str] = []
    format: str | None = None
    template: str | None = None
    model: str | None = None


class SpecIn(BaseModel):
    spec: dict


class YamlIn(BaseModel):
    text: str


class PreviewIn(BaseModel):
    client: str
    spec: dict
    size: str


class RenderIn(BaseModel):
    client: str
    file: str
    item: int = 0
    sizes: list[str] | None = None
#--------------------------------------------------------------#

# Safety: names from the browser may only point inside the right folder
_SAFE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 ._()-]*$")


def client_dir(client: str) -> Path:
    if not _SAFE.match(client) or not (BRANDS_DIR / client / "brand.yaml").exists():
        raise HTTPException(404, f"Unknown client: {client}")
    folder = INPUTS_DIR / client
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def inside(folder: Path, name: str) -> Path:
    path = (folder / name).resolve()
    if folder.resolve() not in path.parents and path != folder.resolve():
        raise HTTPException(400, "Bad file name")
    return path


def spec_path(client: str, file: str) -> Path:
    if not _SAFE.match(file) or not file.endswith((".yaml", ".yml")):
        raise HTTPException(400, "Spec files end in .yaml")
    path = inside(client_dir(client), file)
    if not path.exists():
        raise HTTPException(404, f"No spec file {file}")
    return path


def file_kind(name: str) -> str | None:
    ext = Path(name).suffix.lower()
    return next((k for k, exts in FILE_KINDS.items() if ext in exts), None)


def friendly(e: ValidationError) -> list[str]:
    from visuals.cli import friendly_errors
    return [line.strip() for line in friendly_errors(e).splitlines() if line.strip()]
#--------------------------------------------------------------#

# Spec files: header comments (where a draft came from, NOTE, CHECK) + the entries
def read_spec_file(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    header = []
    for line in text.splitlines():
        if not line.startswith("#"):
            break
        header.append(line[1:].strip())
    info = {"bucket": None, "format": None, "from_idea": bool(header) and header[0].startswith("Draft from the idea")}
    for line in header:
        m = re.search(r"bucket: (\w+).*\| (video|image) \|", line)
        if m:
            info["bucket"], info["format"] = m.group(1), m.group(2)
    try:
        items = yaml.safe_load(text) or []
        items = items if isinstance(items, list) else [items]
        error = None
    except yaml.YAMLError as e:
        items, error = [], str(e)
    sizes = []                                   # each entry's sizes, template defaults included
    for item in items:
        try:
            sizes.append(list(spec_from_dict(item).sizes))
        except (ValidationError, ValueError, TypeError, AttributeError):
            sizes.append([])
    return {
        "file": path.name,
        "modified": datetime.fromtimestamp(path.stat().st_mtime).isoformat(timespec="seconds"),
        "sizes": sizes,
        "notes": [h[5:].strip() for h in header if h.startswith("NOTE:")],
        "checks": [h[6:].strip() for h in header if h.startswith("CHECK:")],
        "header": header,
        "items": items,
        "yaml": text,
        "yaml_error": error,
        **info,
    }


def write_items(path: Path, items: list[dict]) -> None:
    """Rewrite the entries, keeping the comment block at the top of the file."""
    header = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.startswith("#"):
            break
        header.append(line)
    body = yaml.safe_dump(items, sort_keys=False, allow_unicode=True, width=100)
    path.write_text(("\n".join(header) + "\n\n" if header else "") + body, encoding="utf-8")


def check_spec(client: str, data: dict):
    """Validate one entry and make sure its files exist. Raises HTTPException(422) with readable errors."""
    from visuals.cli import resolve_files
    try:
        spec = spec_from_dict(data)
        return resolve_files(client, spec)
    except ValidationError as e:
        raise HTTPException(422, {"errors": friendly(e)})
    except (FileNotFoundError, ValueError) as e:
        raise HTTPException(422, {"errors": [str(e)]})
#--------------------------------------------------------------#

# Which sizes each template accepts (read from its spec class)
def allowed_sizes(template: str) -> list[str]:
    annotation = SPEC_CLASSES[template].model_fields["sizes"].annotation   # list[Literal[...]]
    (inner,) = get_args(annotation)
    values = get_args(inner)
    return [v for v in values if v in SIZES] or list(SIZES)


def template_info() -> dict:
    return {t: {"kind": "video" if t in VIDEO_TEMPLATES else "image", "sizes": allowed_sizes(t)}
            for t in SPEC_CLASSES}
#--------------------------------------------------------------#

# What the browser needs to preview a spec: Remotion props (played live in the page) or HTML
def preview(client: str, data: dict, size: str) -> dict:
    from visuals.remotion_bridge import (COMPOSITIONS, FPS, RECAP_SECONDS, RemotionError,
                                         build_props, total_seconds)
    from visuals.render import build_html
    from visuals.specs import scene_total
    if size not in SIZES:
        raise HTTPException(400, f"Unknown size {size}")
    spec = check_spec(client, data)
    brand = load_brand(client)
    width, height = SIZES[size]
    if spec.template in COMPOSITIONS:
        try:
            props = build_props(spec, brand, size)
        except RemotionError as e:
            raise HTTPException(422, {"errors": [str(e)]})
        if spec.template == "talking_head":
            props["footage"] = f"/files/{client}/{props['footage']}"
            frames = props["durationFrames"]
        elif spec.template == "explainer":
            frames = round(scene_total(spec.scenes) * FPS)
        elif spec.template == "event_recap":
            frames = round(RECAP_SECONDS * FPS)
        else:
            frames = round(total_seconds(spec) * FPS)
        return {"kind": "remotion", "composition": COMPOSITIONS[spec.template], "props": props,
                "durationInFrames": frames, "fps": FPS, "width": props["width"], "height": props["height"]}
    return {"kind": "html", "html": build_html(spec, brand, size), "width": width, "height": height}
#--------------------------------------------------------------#

# The app
def create_app() -> FastAPI:
    @asynccontextmanager
    async def lifespan(app):
        jobs.start_worker()                       # the render queue runs while the app runs
        yield

    app = FastAPI(title="Visual maker", docs_url=None, redoc_url=None, lifespan=lifespan)
    user = os.environ.get("WEBAPP_USER", "admin")
    password = os.environ.get("WEBAPP_PASSWORD")

    @app.middleware("http")
    async def require_password(request: Request, call_next):
        if password:
            expected = "Basic " + base64.b64encode(f"{user}:{password}".encode()).decode()
            given = request.headers.get("authorization", "")
            if not secrets.compare_digest(given.encode(), expected.encode()):
                return Response("Login required", status_code=401,
                                headers={"WWW-Authenticate": 'Basic realm="visual-maker"'})
        return await call_next(request)

    # ---- clients, buckets, templates ----
    @app.get("/api/clients")
    def clients():
        out = []
        for folder in sorted(p for p in BRANDS_DIR.iterdir() if (p / "brand.yaml").exists()):
            brand = load_brand(folder.name)
            buckets = load_buckets(folder.name)
            out.append({
                "name": folder.name, "display_name": brand.display_name,
                "colors": brand.colors.model_dump(), "logo": brand.logo_data_uri,
                "buckets": {k: {**b.model_dump(), "status_note": b.status_note()} for k, b in buckets.items()},
            })
        return out

    @app.get("/api/templates")
    def templates():
        return template_info()

    # ---- files ----
    @app.get("/api/files/{client}")
    def list_files(client: str):
        folder = client_dir(client)
        files = [p for p in folder.iterdir() if p.is_file() and file_kind(p.name)]
        files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
        return [{"name": p.name, "kind": file_kind(p.name), "bytes": p.stat().st_size,
                 "url": f"/files/{client}/{p.name}"} for p in files]

    @app.post("/api/files/{client}")
    async def upload(client: str, file: UploadFile):
        folder = client_dir(client)
        stem = re.sub(r"[^A-Za-z0-9._-]+", "-", Path(file.filename or "upload").stem).strip("-.") or "upload"
        ext = Path(file.filename or "").suffix.lower()
        if not file_kind(f"{stem}{ext}"):
            raise HTTPException(400, f"Can't use {ext or 'this'} files: images, videos, audio, CSV or text only")
        path, n = folder / f"{stem}{ext}", 2
        while path.exists():
            path, n = folder / f"{stem}-{n}{ext}", n + 1
        path.write_bytes(await file.read())
        return {"name": path.name, "kind": file_kind(path.name), "url": f"/files/{client}/{path.name}"}

    @app.get("/files/{client}/{name}")
    def get_file(client: str, name: str):
        path = inside(client_dir(client), name)
        if not path.is_file():
            raise HTTPException(404, "Not found")
        return FileResponse(path)

    @app.get("/outputs/{rel:path}")
    def get_output(rel: str):
        path = inside(OUTPUTS_DIR, rel)
        if not path.is_file():
            raise HTTPException(404, "Not found")
        return FileResponse(path)

    # ---- ideas -> drafts ----
    @app.post("/api/ideas")
    def ideas(body: IdeaIn):
        from visuals.ideas import make_spec
        from visuals.llm import LLMError
        client_dir(body.client)
        try:
            path, warnings = make_spec(body.client, body.bucket, body.idea, body.files,
                                       body.format, body.template, body.model)
        except ValidationError as e:
            raise HTTPException(422, {"errors": friendly(e)})
        except (FileNotFoundError, ValueError, LLMError) as e:
            raise HTTPException(400, {"errors": [str(e)]})
        return {"file": path.name, "warnings": warnings}

    # ---- spec files (the library) ----
    @app.get("/api/specs/{client}")
    def library(client: str):
        folder = client_dir(client)
        files = sorted(folder.glob("*.y*ml"), key=lambda p: p.stat().st_mtime, reverse=True)
        out = []
        for p in files:
            info = read_spec_file(p)
            out.append({k: info[k] for k in ("file", "modified", "bucket", "format", "from_idea", "notes", "checks")}
                       | {"entries": [{"name": i.get("name"), "template": i.get("template")}
                                      for i in info["items"] if isinstance(i, dict)],
                          "yaml_error": info["yaml_error"]})
        return out

    @app.get("/api/specs/{client}/{file}")
    def get_spec(client: str, file: str):
        return read_spec_file(spec_path(client, file))

    @app.put("/api/specs/{client}/{file}/{item}")
    def save_item(client: str, file: str, item: int, body: SpecIn):
        path = spec_path(client, file)
        items = read_spec_file(path)["items"]
        if not 0 <= item < len(items):
            raise HTTPException(404, "No such entry")
        check_spec(client, body.spec)
        items[item] = body.spec
        write_items(path, items)
        return read_spec_file(path)

    @app.put("/api/specs/{client}/{file}")
    def save_yaml(client: str, file: str, body: YamlIn):
        path = spec_path(client, file)
        try:
            items = yaml.safe_load(body.text) or []
        except yaml.YAMLError as e:
            raise HTTPException(422, {"errors": [f"Not valid YAML: {e}"]})
        for data in items if isinstance(items, list) else [items]:
            check_spec(client, data)
        path.write_text(body.text, encoding="utf-8")
        return read_spec_file(path)

    @app.post("/api/preview")
    def preview_spec(body: PreviewIn):
        client_dir(body.client)
        return preview(body.client, body.spec, body.size)

    # ---- renders ----
    @app.post("/api/render")
    def render(body: RenderIn):
        path = spec_path(body.client, body.file)
        items = read_spec_file(path)["items"]
        if not 0 <= body.item < len(items):
            raise HTTPException(404, "No such entry")
        data = dict(items[body.item])
        if body.sizes:
            data["sizes"] = body.sizes
        check_spec(body.client, data)
        job_id = jobs.add_job(body.client, body.file, body.item, data.get("name"), body.sizes)
        return with_urls(jobs.get_job(job_id))

    @app.get("/api/jobs")
    def list_jobs(client: str | None = None):
        return [with_urls(j) for j in jobs.list_jobs(client)]

    @app.get("/api/jobs/{job_id}")
    def get_job(job_id: int):
        job = jobs.get_job(job_id)
        if not job:
            raise HTTPException(404, "No such job")
        return with_urls(job)

    # ---- the page ----
    if (WEB_DIST / "index.html").exists():
        app.mount("/assets", StaticFiles(directory=WEB_DIST / "assets"), name="assets")

        @app.get("/{path:path}", include_in_schema=False)
        def page(path: str):
            if path.startswith(("api/", "files/", "outputs/")) or "." in path.rsplit("/", 1)[-1]:
                raise HTTPException(404, "Not found")      # only app pages fall back to the page
            return FileResponse(WEB_DIST / "index.html")
    else:
        @app.get("/", include_in_schema=False)
        def not_built():
            return HTMLResponse("<h2>The page isn't built yet.</h2><p>Run: <code>cd remotion && npm install "
                                "&& npm run build:web</code>, then restart <code>python -m visuals web</code>.</p>")

    @app.exception_handler(HTTPException)
    async def errors(request: Request, exc: HTTPException):
        detail = exc.detail if isinstance(exc.detail, dict) else {"errors": [str(exc.detail)]}
        return JSONResponse(detail, status_code=exc.status_code, headers=getattr(exc, "headers", None))

    return app


def with_urls(job: dict) -> dict:
    return {**job, "urls": [f"/outputs/{rel}" for rel in job.get("made") or []]}
#--------------------------------------------------------------#

# Command line: python -m visuals web [--host 127.0.0.1] [--port 8000]
def main(argv: list[str]) -> int:
    import argparse
    import uvicorn
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
    p = argparse.ArgumentParser(prog="visuals web")
    p.add_argument("--host", default="127.0.0.1", help="127.0.0.1 = this Mac only (default)")
    p.add_argument("--port", type=int, default=8000)
    args = p.parse_args(argv[1:])
    if args.host not in ("127.0.0.1", "localhost") and not os.environ.get("WEBAPP_PASSWORD"):
        print("Refusing to listen beyond this Mac without a password: set WEBAPP_PASSWORD in .env")
        return 2
    if not (WEB_DIST / "index.html").exists():
        print("Note: the page isn't built yet (cd remotion && npm install && npm run build:web)")
    print(f"Visual maker: http://{args.host}:{args.port}")
    uvicorn.run(create_app(), host=args.host, port=args.port, log_level="warning")
    return 0
#--------------------------------------------------------------#
#----------------------End-of-code-----------------------------#
