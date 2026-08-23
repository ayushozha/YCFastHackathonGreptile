"""Owner: B. Replaying demo/sample_run.jsonl folds to result == "survived".

Acceptance criterion, PRD section 12. No engine import anywhere in this file.
"""

import json
import os
import time

import pytest

from arena import leaderboard as leaderboard_mod
from arena import paths, replay
from arena.fold import fold

SAMPLE = os.path.join("demo", "sample_run.jsonl")


def read_sample():
    return [json.loads(l) for l in open(SAMPLE, encoding="utf-8") if l.strip()]


def test_fold_reaches_survived():
    state = fold(read_sample())
    assert state["final"]["result"] == "survived"
    assert state["counts"]["launched"] == 3
    assert state["counts"]["landed_r1"] == 3
    assert state["counts"]["landed_r2"] == 0
    assert state["hp"] == 100
    assert all(h["status"] == "blocked" for h in state["hypotheses"])


def test_fold_tracks_health_through_round_one():
    events = read_sample()
    upto = events[: [e["type"] for e in events].index("round_over") + 1]
    assert fold(upto)["hp"] == 10


def test_fold_ignores_unknown_event_types():
    """Appendix C: a new event from A cannot break the UI."""
    events = read_sample() + [
        {"type": "victory_dance", "ts": "2026-08-23T21:20:00.000+00:00",
         "arena_id": "sample", "round": 2, "seq": 999}
    ]
    assert fold(events)["final"]["result"] == "survived"


def test_replay_writes_events_under_a_new_arena_id(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "RUNS_DIR", str(tmp_path / "runs"))
    monkeypatch.setattr(replay, "MAX_GAP_S", 0.0)
    info = replay.start("rp1", SAMPLE)
    assert info["events"] == len(read_sample())

    out = paths.events_path("rp1")
    deadline = time.time() + 10
    while time.time() < deadline:
        lines = paths.read_jsonl(out)
        if lines and lines[-1]["type"] == "final":
            break
        time.sleep(0.05)

    events = paths.read_jsonl(out)
    assert events[-1]["type"] == "final"
    assert all(e["arena_id"] == "rp1" for e in events)
    assert all(e["replay"] is True for e in events)
    assert fold(events)["replay"] is True


def test_replay_rejects_a_missing_file(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "RUNS_DIR", str(tmp_path / "runs"))
    with pytest.raises(FileNotFoundError):
        replay.start("rp2", "demo/does_not_exist.jsonl")


def test_leaderboard_is_derived_from_finished_runs(tmp_path, monkeypatch):
    runs = tmp_path / "runs"
    monkeypatch.setattr(paths, "RUNS_DIR", str(runs))
    monkeypatch.setattr(leaderboard_mod, "RUNS_DIR", str(runs))
    for arena_id in ("a", "b"):
        d = runs / arena_id
        d.mkdir(parents=True)
        (d / "events.jsonl").write_text(
            "\n".join(json.dumps(dict(e, arena_id=arena_id)) for e in read_sample())
        )
    board = leaderboard_mod.leaderboard()
    assert len(board["prs"]) == 2
    assert board["streak"] == 2
    assert {a["attacker"] for a in board["attackers"]} == {"bug_hunter", "security", "ledger"}
    assert all(a["hits"] == 2 and a["swings"] == 2 for a in board["attackers"])


def test_leaderboard_skips_unfinished_runs(tmp_path, monkeypatch):
    runs = tmp_path / "runs"
    monkeypatch.setattr(paths, "RUNS_DIR", str(runs))
    monkeypatch.setattr(leaderboard_mod, "RUNS_DIR", str(runs))
    d = runs / "half"
    d.mkdir(parents=True)
    events = [e for e in read_sample() if e["type"] != "final"]
    (d / "events.jsonl").write_text("\n".join(json.dumps(e) for e in events))
    assert leaderboard_mod.leaderboard()["prs"] == []
