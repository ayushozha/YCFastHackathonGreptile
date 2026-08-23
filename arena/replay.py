"""Replay a cached event log under a new arena_id (Appendix B).

Original inter-event gaps, capped at 1.5 s, every line tagged replay: true so
the UI can show the tag. The SSE route then serves it like any other arena.
Never cut (PRD 10).
"""

import json
import os
import threading
import time
from datetime import datetime

from arena.paths import DEMO_DIR, ROOT, events_path, read_jsonl, run_dir

MAX_GAP_S = 1.5
DEFAULT_FILE = os.path.join("demo", "cached_run.jsonl")


def _resolve(file_arg):
    path = file_arg or DEFAULT_FILE
    if not os.path.isabs(path):
        path = os.path.join(ROOT, path)
    if not os.path.exists(path):
        alt = os.path.join(DEMO_DIR, os.path.basename(path))
        if os.path.exists(alt):
            return alt
        raise FileNotFoundError(path)
    return path


def _gap(prev, cur):
    try:
        a = datetime.fromisoformat(prev["ts"])
        b = datetime.fromisoformat(cur["ts"])
        return max(0.0, min(MAX_GAP_S, (b - a).total_seconds()))
    except Exception:
        return 0.15


def start(arena_id, file_arg=None):
    """Spawn a thread that writes the replay into runs/<arena_id>/events.jsonl."""
    source = _resolve(file_arg)
    events = read_jsonl(source)
    if not events:
        raise ValueError(f"no events in {source}")
    os.makedirs(run_dir(arena_id), exist_ok=True)
    out = events_path(arena_id)
    open(out, "w", encoding="utf-8").close()

    def pump():
        prev = None
        for e in events:
            if prev is not None:
                time.sleep(_gap(prev, e))
            prev = e
            line = dict(e, arena_id=arena_id, replay=True)
            with open(out, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(line, ensure_ascii=False) + "\n")
                fh.flush()

    t = threading.Thread(target=pump, daemon=True)
    t.start()
    return {"arena_id": arena_id, "source": os.path.relpath(source, ROOT), "events": len(events)}
