"""Owner: A. Every event the engine emits validates against shared/schema.py.

Acceptance criterion, PRD section 12.
"""

import json
import os

import pytest

from engine import events as ev
from engine.events import Emitter
from shared.schema import EVENT_SCHEMA, SchemaError, damage_for, validate

SAMPLE = os.path.join("demo", "sample_run.jsonl")


@pytest.fixture
def arena(tmp_path, monkeypatch):
    monkeypatch.setattr(ev, "RUNS_DIR", str(tmp_path / "runs"))
    return "t1"


def test_emit_writes_one_json_line_per_event(arena):
    emit = Emitter(arena, echo=False)
    emit("fix_start")
    emit("blocked", hypothesis_id="h1", hp_after=40)
    lines = open(ev.events_path(arena), encoding="utf-8").read().strip().splitlines()
    assert len(lines) == 2
    assert [json.loads(l)["type"] for l in lines] == ["fix_start", "blocked"]


def test_seq_is_monotonic_from_zero_and_survives_resume(arena):
    first = Emitter(arena, echo=False)
    for _ in range(3):
        first("fix_start")
    resumed = Emitter(arena, round_no=2, echo=False)   # a --fix-only process
    resumed("still_landed", hypothesis_id="h1")
    seqs = [json.loads(l)["seq"] for l in open(ev.events_path(arena), encoding="utf-8")]
    assert seqs == [0, 1, 2, 3]


def test_common_fields_are_present_on_every_event(arena):
    emit = Emitter(arena, round_no=2, echo=False)
    e = emit("miss", hypothesis_id="h2", reason="exploit did not pass")
    assert e["arena_id"] == arena and e["round"] == 2 and e["seq"] == 0
    assert e["ts"].startswith("20")
    validate(e)


def test_missing_payload_field_is_rejected(arena):
    emit = Emitter(arena, echo=False)
    with pytest.raises(SchemaError):
        emit("hit", hypothesis_id="h1")           # no damage / hp_after
    assert not os.path.exists(ev.events_path(arena)) or \
        open(ev.events_path(arena), encoding="utf-8").read() == ""


def test_unknown_event_type_is_rejected(arena):
    emit = Emitter(arena, echo=False)
    with pytest.raises(SchemaError):
        emit("victory_dance")


def test_state_round_trip(arena):
    ev.write_state(arena, {"pr": {"number": 42}, "hypotheses": [], "round1": {"hp": 10}})
    assert ev.read_state(arena)["round1"]["hp"] == 10


@pytest.mark.parametrize("line", open(SAMPLE, encoding="utf-8").read().strip().splitlines())
def test_sample_run_lines_validate(line):
    """The frozen contract fixture is itself schema-clean (PRD 15.2)."""
    validate(json.loads(line))


def test_sample_run_shape():
    events = [json.loads(l) for l in open(SAMPLE, encoding="utf-8") if l.strip()]
    assert events[0]["type"] == "arena_created"
    assert events[-1]["type"] == "final"
    assert [e["seq"] for e in events] == list(range(len(events)))


def test_damage_is_capped_at_100():
    hyps = [{"severity": "critical"}] * 4
    assert sum(damage_for(hyps)) == 100


def test_every_documented_event_type_has_a_schema_entry():
    documented = {
        "arena_created", "index_status", "scout_report", "attacker_intro",
        "exploit_written", "sandbox_up", "test_output", "hit", "miss",
        "round_over", "fix_start", "fix_diff", "fix_result", "fix_rejected",
        "blocked", "still_landed", "final", "error",
    }
    assert set(EVENT_SCHEMA) == documented
