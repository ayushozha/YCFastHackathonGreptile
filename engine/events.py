"""The event bus is a file (PRD section 4).

emit() appends one JSON object per line to runs/<arena_id>/events.jsonl and
flushes. Nothing else in the system shares state: the arena tails this file.

Guarantees the engine makes (Appendix C):
  * append-only, one JSON object per line
  * seq strictly increasing from 0, continuing across a --fix-only resume
  * each line flushed before the next stage starts
  * first line is always arena_created; a completed run ends with final;
    an aborted run ends with error
"""

import json
import os
import sys
from datetime import datetime, timezone

from shared.schema import validate

RUNS_DIR = os.environ.get("ARENA_RUNS_DIR", "runs")


def run_dir(arena_id):
    return os.path.join(RUNS_DIR, arena_id)


def events_path(arena_id):
    return os.path.join(run_dir(arena_id), "events.jsonl")


def state_path(arena_id):
    return os.path.join(run_dir(arena_id), "state.json")


def workdir(arena_id):
    return os.path.join(run_dir(arena_id), "repo")


def _next_seq(path):
    """Resume-safe: seq continues from the last line already on disk."""
    if not os.path.exists(path):
        return 0
    last = -1
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                last = json.loads(line)["seq"]
            except (ValueError, KeyError):
                continue
    return last + 1


class Emitter:
    """Callable passed into every stage. Stages stay pure w.r.t. the bus (PRD 6)."""

    def __init__(self, arena_id, round_no=1, echo=True):
        self.arena_id = arena_id
        self.round = round_no
        self.echo = echo
        self.path = events_path(arena_id)
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        self.seq = _next_seq(self.path)

    def __call__(self, type, **payload):
        event = {
            "type": type,
            "ts": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
            "arena_id": self.arena_id,
            "round": self.round,
            "seq": self.seq,
            **payload,
        }
        validate(event)
        line = json.dumps(event, ensure_ascii=False)
        with open(self.path, "a", encoding="utf-8") as fh:
            fh.write(line + "\n")
            fh.flush()
            os.fsync(fh.fileno())
        self.seq += 1
        if self.echo:
            # run_pr.py also prints each event line for terminal use (Appendix C)
            print(line, file=sys.stdout, flush=True)
        return event


def read_events(arena_id):
    path = events_path(arena_id)
    if not os.path.exists(path):
        return []
    out = []
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                try:
                    out.append(json.loads(line))
                except ValueError:
                    continue
    return out


def write_state(arena_id, state):
    """state.json is complete before round_over is written (Appendix C)."""
    path = state_path(arena_id)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(state, fh, indent=2)
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, path)


def read_state(arena_id):
    path = state_path(arena_id)
    if not os.path.exists(path):
        raise FileNotFoundError(
            f"{path} not found -- run the attack round before --fix-only"
        )
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)
