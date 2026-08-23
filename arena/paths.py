"""The arena reads three files and nothing else (Appendix C, guarantees):

    runs/<id>/events.jsonl      the bus
    runs/<id>/state.json        hypotheses + round 1 results
    runs/<id>/repo/seed.json    the fixture's seeded Stripe payment intent

It never imports engine code. These paths are duplicated here on purpose.
"""

import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RUNS_DIR = os.environ.get("ARENA_RUNS_DIR", os.path.join(ROOT, "runs"))
STATIC_DIR = os.path.join(ROOT, "static")
DEMO_DIR = os.path.join(ROOT, "demo")


def run_dir(arena_id):
    return os.path.join(RUNS_DIR, arena_id)


def events_path(arena_id):
    return os.path.join(run_dir(arena_id), "events.jsonl")


def state_path(arena_id):
    return os.path.join(run_dir(arena_id), "state.json")


def seed_path(arena_id):
    return os.path.join(run_dir(arena_id), "repo", "seed.json")


def read_jsonl(path):
    if not os.path.exists(path):
        return []
    out = []
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except ValueError:
                continue
    return out
