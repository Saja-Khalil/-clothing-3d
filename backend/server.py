"""Local server for the clothing module: serves the viewer and turns two
flat-lay photos (from the camera or from a file) into a draped GLB.

  python backend/server.py            then open http://127.0.0.1:8010/viewer/

Routes:
  GET  /viewer/, /output/..., /jobs/<id>/...   static files
  POST /api/jobs   JSON {front, back: data URLs (image/jpeg|png),
                         lengthCm, shoulderCm, hemCm?, sleeveCm?, sleeveFrom?}
                   -> {id}; the job is queued
  GET  /api/jobs/<id> -> {status: queued|running|done|failed, error?, glb?, info?}

Every job has its own folder jobs/<uuid>/ (photos, GLBs, JSON), so requests
never share a file. Jobs run one at a time: a drape takes a few minutes and
most of the machine's memory.
"""

import base64
import binascii
import json
import re
import subprocess
import sys
import threading
import uuid
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from io import BytesIO
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]  # the clothing folder
JOBS = ROOT / "jobs"
AVATAR = ROOT / "output" / "avatar.glb"
PYTHON = Path(sys.executable)
MAX_BODY_BYTES = 40 * 1024 * 1024
DATA_URL = re.compile(r"^data:image/(jpeg|png);base64,(.+)$", re.S)
JOB_ID = re.compile(r"^[0-9a-f]{32}$")
# Accepted measurement ranges, cm.
RANGES = {"lengthCm": (40, 200), "shoulderCm": (20, 80), "hemCm": (30, 400), "sleeveCm": (10, 100)}

jobs = {}  # id -> state dict
jobs_lock = threading.Lock()
run_lock = threading.Lock()  # one drape at a time


class BadRequest(ValueError):
    pass


def decode_photo(data_url):
    match = DATA_URL.match(data_url or "") if isinstance(data_url, str) else None
    if not match:
        raise BadRequest("Each photo must be a JPEG or PNG data URL.")
    try:
        raw = base64.b64decode(match.group(2), validate=True)
        Image.open(BytesIO(raw)).verify()
    except (binascii.Error, OSError, SyntaxError):
        raise BadRequest("A photo could not be read as an image.")
    return raw


def number(body, key, required):
    value = body.get(key)
    if value in (None, ""):
        if required:
            raise BadRequest(f"{key} is required.")
        return None
    try:
        value = float(value)
    except (TypeError, ValueError):
        raise BadRequest(f"{key} must be a number.")
    lo, hi = RANGES[key]
    if not lo <= value <= hi:
        raise BadRequest(f"{key} must be between {lo} and {hi} cm.")
    return value


def run_job(job_id, args):
    folder = JOBS / job_id
    with run_lock:
        with jobs_lock:
            jobs[job_id]["status"] = "running"
        result = subprocess.run(
            [str(PYTHON), str(ROOT / "backend" / "flat_dress.py"), *args],
            cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace",
        )
    (folder / "log.txt").write_text(result.stdout + "\n" + result.stderr, encoding="utf-8")
    state = {"status": "failed"}
    if result.returncode == 0 and (folder / "dress.glb").exists():
        state = {"status": "done", "glb": f"/jobs/{job_id}/dress.glb",
                 "info": json.loads((folder / "dress.json").read_text(encoding="utf-8"))}
    else:
        lines = [l for l in (result.stderr + result.stdout).splitlines() if l.strip()]
        photo = [l for l in lines if l.startswith("PHOTO_ERROR")]
        state["error"] = photo[-1][len("PHOTO_ERROR "):] if photo else (lines[-1] if lines else "unknown error")
        state["photoProblem"] = bool(photo)
    with jobs_lock:
        jobs[job_id].update(state)


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def send_json(self, code, payload):
        data = json.dumps(payload).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_POST(self):
        if self.path != "/api/jobs":
            return self.send_json(404, {"error": "not found"})
        length = int(self.headers.get("Content-Length") or 0)
        if not 0 < length <= MAX_BODY_BYTES:
            return self.send_json(413, {"error": "Photos too large (40 MB at most)."})
        try:
            body = json.loads(self.rfile.read(length))
            measures = {k: number(body, k, k in ("lengthCm", "shoulderCm")) for k in RANGES}
            sleeve_from = body.get("sleeveFrom") or "shoulder"
            if sleeve_from not in ("shoulder", "neck"):
                raise BadRequest("sleeveFrom must be shoulder or neck.")
            front, back = decode_photo(body.get("front")), decode_photo(body.get("back"))
        except json.JSONDecodeError:
            return self.send_json(400, {"error": "The request is not JSON."})
        except BadRequest as error:
            return self.send_json(400, {"error": str(error)})

        job_id = uuid.uuid4().hex
        folder = JOBS / job_id
        folder.mkdir(parents=True)
        (folder / "front.jpg").write_bytes(front)
        (folder / "back.jpg").write_bytes(back)
        args = ["--avatar", str(AVATAR), "--front", str(folder / "front.jpg"), "--back", str(folder / "back.jpg"),
                "--length-cm", str(measures["lengthCm"]), "--shoulder-cm", str(measures["shoulderCm"]),
                "--out", str(folder), "--name", "dress"]
        if measures["hemCm"]:
            args += ["--hem-cm", str(measures["hemCm"])]
        if measures["sleeveCm"]:
            args += ["--sleeve-cm", str(measures["sleeveCm"]), "--sleeve-from", sleeve_from]
        with jobs_lock:
            jobs[job_id] = {"status": "queued"}
        threading.Thread(target=run_job, args=(job_id, args), daemon=True).start()
        self.send_json(202, {"id": job_id})

    def do_GET(self):
        if self.path.startswith("/api/jobs/"):
            job_id = self.path.rsplit("/", 1)[-1]
            with jobs_lock:
                state = dict(jobs.get(job_id, {})) if JOB_ID.match(job_id) else {}
            return self.send_json(200 if state else 404, state or {"error": "no such job"})
        return super().do_GET()


def main():
    JOBS.mkdir(exist_ok=True)
    server = ThreadingHTTPServer(("127.0.0.1", 8010), Handler)
    print("Serving on http://127.0.0.1:8010/viewer/", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
