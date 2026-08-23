"""FastAPI service: spawns the engine, tails the event file over SSE, serves the UI.

The arena never imports engine code. It launches scripts/run_pr.py with
subprocess.Popen (detached, cwd at repo root, never waited on) and reads only
runs/<id>/{events.jsonl,state.json,repo/seed.json}. See Appendix C.
"""

import asyncio
import json
import os
import subprocess
import sys
import uuid

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from arena import leaderboard as leaderboard_mod
from arena import replay as replay_mod
from arena import stripe_view
from arena.fold import fold
from arena.paths import ROOT, STATIC_DIR, events_path, read_jsonl, run_dir

app = FastAPI(title="Code Arena")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

POLL_S = 0.2  # Appendix C / section 7: tail poll interval
TERMINAL = ("final", "error")
RUN_PR = os.path.join("scripts", "run_pr.py")


def new_arena_id():
    return uuid.uuid4().hex[:8]


def _spawn(args):
    """Detached, cwd at repo root, never waited on (Appendix C)."""
    return subprocess.Popen(
        [sys.executable, RUN_PR, *args],
        cwd=ROOT,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )


@app.get("/")
def index():
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))


@app.post("/arena")
async def create_arena(request: Request):
    body = await request.json()
    pr_url = (body or {}).get("pr_url", "").strip()
    if not pr_url:
        raise HTTPException(400, "pr_url is required")
    arena_id = new_arena_id()
    os.makedirs(run_dir(arena_id), exist_ok=True)
    args = [pr_url, "--arena-id", arena_id]
    if os.environ.get("RUNNER"):
        args += ["--runner", os.environ["RUNNER"]]
    if os.environ.get("SCOUT"):
        args += ["--scout", os.environ["SCOUT"]]
    _spawn(args)
    return {"arena_id": arena_id}


@app.post("/arena/{arena_id}/fix", status_code=202)
def start_fix(arena_id: str):
    if not os.path.exists(events_path(arena_id)):
        raise HTTPException(404, "unknown arena")
    _spawn(["--arena-id", arena_id, "--fix-only"])
    return {"arena_id": arena_id, "status": "fixing"}


@app.post("/arena/replay")
async def start_replay(request: Request):
    try:
        body = await request.json()
    except Exception:
        body = {}
    arena_id = new_arena_id()
    try:
        info = replay_mod.start(arena_id, (body or {}).get("file"))
    except FileNotFoundError as exc:
        raise HTTPException(404, f"no such cache file: {exc}")
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    return info


@app.get("/arena/{arena_id}")
def arena_state(arena_id: str):
    path = events_path(arena_id)
    if not os.path.exists(path):
        raise HTTPException(404, "unknown arena")
    return fold(read_jsonl(path))


@app.get("/arena/{arena_id}/stripe")
def arena_stripe(arena_id: str):
    return stripe_view.refunds(arena_id)


@app.get("/leaderboard")
def get_leaderboard():
    return leaderboard_mod.leaderboard()


@app.get("/arena/{arena_id}/events")
async def stream_events(arena_id: str, after: int = -1):
    """SSE: replay everything already on disk from `after`, then tail the file."""
    path = events_path(arena_id)

    async def gen():
        sent = after
        idle = 0.0
        # the engine creates the file a beat after POST /arena returns
        while not os.path.exists(path) and idle < 30:
            await asyncio.sleep(POLL_S)
            idle += POLL_S
        if not os.path.exists(path):
            yield _sse({"type": "error", "stage": "arena", "message": "no event file"})
            return
        while True:
            fresh = [e for e in read_jsonl(path) if e.get("seq", -1) > sent]
            for e in fresh:
                sent = e.get("seq", sent)
                yield _sse(e)
                if e.get("type") in TERMINAL:
                    return
            if not fresh:
                idle += POLL_S
                if idle > 900:
                    return
                yield ": keepalive\n\n" if idle % 15 < POLL_S else ""
            else:
                idle = 0.0
            await asyncio.sleep(POLL_S)

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


def _sse(event):
    return f"data: {json.dumps(event, ensure_ascii=False)}\n\n"


@app.exception_handler(FileNotFoundError)
def _missing(request, exc):
    return JSONResponse({"detail": str(exc)}, status_code=404)
