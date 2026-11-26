#---------------------beginning-of-code------------------------#
#--------------------------------------------------------------#

# File: visuals/web/jobs.py
# Purpose: the web app's render queue. A render can take minutes (3D video), so the app
#          adds a job here and returns at once; one background worker renders jobs in order.
#          Jobs live in data/web.db (SQLite), so the history survives restarts.
#
#   add_job(client, file, index, sizes) -> job id
#   get_job(id), list_jobs(client=None)
#   start_worker()   (called once when the app starts)
#--------------------------------------------------------------#

# Imports Libraries
import json
import sqlite3
import threading
import traceback
from datetime import date, datetime
from pathlib import Path

from visuals.paths import OUTPUTS_DIR, ROOT
#--------------------------------------------------------------#

# Global variables
DB_PATH = ROOT / "data" / "web.db"
_lock = threading.Lock()
_wake = threading.Event()
_worker: threading.Thread | None = None

SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    client TEXT NOT NULL,
    file TEXT NOT NULL,            -- spec file name in inputs/<client>/
    item INTEGER NOT NULL,         -- which entry in that file (0 = first)
    name TEXT,
    sizes TEXT,                    -- JSON list, or null = the spec's own sizes
    status TEXT NOT NULL,          -- queued | running | done | failed
    made TEXT,                     -- JSON list of output paths, relative to outputs/
    errors TEXT,                   -- JSON list of messages
    created TEXT NOT NULL,
    finished TEXT
);
"""
#--------------------------------------------------------------#

# Database helpers (one short connection per call: safe across threads)
def _connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute(SCHEMA)
    return conn


def _row(r: sqlite3.Row | None) -> dict | None:
    if r is None:
        return None
    d = dict(r)
    for key in ("sizes", "made", "errors"):
        d[key] = json.loads(d[key]) if d[key] else ([] if key != "sizes" else None)
    return d


def now() -> str:
    return datetime.now().isoformat(timespec="seconds")
#--------------------------------------------------------------#

# Public functions
def add_job(client: str, file: str, item: int, name: str | None, sizes: list[str] | None) -> int:
    with _lock, _connect() as conn:
        cur = conn.execute(
            "INSERT INTO jobs (client, file, item, name, sizes, status, created) VALUES (?,?,?,?,?,?,?)",
            (client, file, item, name, json.dumps(sizes) if sizes else None, "queued", now()))
        job_id = cur.lastrowid
    _wake.set()
    return job_id


def get_job(job_id: int) -> dict | None:
    with _connect() as conn:
        return _row(conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone())


def list_jobs(client: str | None = None, limit: int = 100) -> list[dict]:
    with _connect() as conn:
        if client:
            rows = conn.execute("SELECT * FROM jobs WHERE client = ? ORDER BY id DESC LIMIT ?", (client, limit))
        else:
            rows = conn.execute("SELECT * FROM jobs ORDER BY id DESC LIMIT ?", (limit,))
        return [_row(r) for r in rows.fetchall()]


def _update(job_id: int, **fields) -> None:
    sets = ", ".join(f"{k} = ?" for k in fields)
    values = [json.dumps(v) if isinstance(v, list) else v for v in fields.values()]
    with _lock, _connect() as conn:
        conn.execute(f"UPDATE jobs SET {sets} WHERE id = ?", (*values, job_id))


def _next_queued() -> dict | None:
    with _connect() as conn:
        return _row(conn.execute("SELECT * FROM jobs WHERE status = 'queued' ORDER BY id LIMIT 1").fetchone())
#--------------------------------------------------------------#

# Do one job: load the spec fresh from its file (so the latest edits are rendered), render it
def run_job(job: dict) -> tuple[list[str], list[str]]:
    from visuals.brand import load_brand
    from visuals.cli import render_specs, resolve_files
    from visuals.paths import INPUTS_DIR
    from visuals.specs import load_batch

    specs = load_batch(INPUTS_DIR / job["client"] / job["file"])
    spec = specs[job["item"]]
    if job["sizes"]:
        spec = type(spec).model_validate({**spec.model_dump(), "sizes": job["sizes"]})
    spec = resolve_files(job["client"], spec)
    if not spec.name:
        spec = spec.model_copy(update={"name": Path(job["file"]).stem + (f"-{job['item'] + 1}" if job["item"] else "")})
    out_dir = OUTPUTS_DIR / job["client"] / date.today().isoformat()
    made, failed = render_specs(job["client"], load_brand(job["client"]), [spec], out_dir)
    return [str(Path(p).resolve().relative_to(OUTPUTS_DIR.resolve())) for p in made], failed


def _work_forever() -> None:
    while True:
        job = _next_queued()
        if job is None:
            _wake.wait(timeout=5)
            _wake.clear()
            continue
        _update(job["id"], status="running")
        try:
            made, failed = run_job(job)
            _update(job["id"], status="failed" if failed and not made else "done",
                    made=made, errors=failed, finished=now())
        except Exception as e:                          # never let one bad job stop the queue
            detail = str(e) or type(e).__name__
            _update(job["id"], status="failed", made=[], finished=now(),
                    errors=[detail, traceback.format_exc(limit=3)[-1500:]])


def start_worker() -> None:
    """Start the background worker once. Jobs left 'running' by a crash are marked failed."""
    global _worker
    if _worker and _worker.is_alive():
        return
    with _lock, _connect() as conn:
        conn.execute("UPDATE jobs SET status = 'failed', errors = ?, finished = ? WHERE status = 'running'",
                     (json.dumps(["The app stopped while this was rendering. Render it again."]), now()))
    _worker = threading.Thread(target=_work_forever, name="render-worker", daemon=True)
    _worker.start()
#--------------------------------------------------------------#
#----------------------End-of-code-----------------------------#
