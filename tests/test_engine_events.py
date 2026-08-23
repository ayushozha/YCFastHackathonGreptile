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


# ---- codex stdout parsing (fix prompt A.3 asks for `<path>  <summary>`) ----

@pytest.mark.parametrize("line,expected", [
    ("app/refunds.py  guard on payment.refunded", "app/refunds.py"),
    ("main.py  added the ownership check", "main.py"),
    ("app/refunds.py:  clamp the amount", "app/refunds.py"),
])
def test_parse_file_summaries_finds_changed_files(line, expected):
    from engine.codex import parse_file_summaries

    assert parse_file_summaries(line) == [
        {"path": expected, "summary": line.split(None, 1)[1].strip()}
    ]


@pytest.mark.parametrize("line", [
    "Here is what I changed:",
    "I updated the refund handler so that it works",
    "",
])
def test_parse_file_summaries_ignores_prose(line):
    from engine.codex import parse_file_summaries

    assert parse_file_summaries(line) == []


def test_codex_flags_match_the_installed_cli():
    """Read off `codex exec --help`, not guessed (PRD section 9)."""
    from engine.codex import CODEX_FLAGS

    assert "--sandbox" in CODEX_FLAGS and "workspace-write" in CODEX_FLAGS


# ---- CLI dispatch (Appendix C is the frozen interface B calls) ----

def test_cli_attack_only(monkeypatch):
    import scripts.run_pr as run_pr

    seen = {}

    def record(name):
        def call(*a, **k):
            seen[name] = (a, k)
            return 0
        return call

    monkeypatch.setattr(run_pr.orchestrator, "run_attack", record("attack"))
    monkeypatch.setattr(run_pr.orchestrator, "run_fix", record("fix"))
    assert run_pr.main(["https://github.com/o/r/pull/1", "--arena-id", "x"]) == 0
    assert "attack" in seen and "fix" not in seen


def test_cli_fix_runs_both_stages(monkeypatch):
    import scripts.run_pr as run_pr

    order = []
    monkeypatch.setattr(run_pr.orchestrator, "run_attack",
                        lambda *a, **k: order.append("attack") or 0)
    monkeypatch.setattr(run_pr.orchestrator, "run_fix",
                        lambda *a, **k: order.append("fix") or 0)
    assert run_pr.main(["https://github.com/o/r/pull/1", "--arena-id", "x", "--fix"]) == 0
    assert order == ["attack", "fix"]


def test_cli_fix_does_not_run_when_the_attack_round_errored(monkeypatch):
    import scripts.run_pr as run_pr

    order = []
    monkeypatch.setattr(run_pr.orchestrator, "run_attack", lambda *a, **k: 1)
    monkeypatch.setattr(run_pr.orchestrator, "run_fix",
                        lambda *a, **k: order.append("fix") or 0)
    assert run_pr.main(["https://github.com/o/r/pull/1", "--arena-id", "x", "--fix"]) == 1
    assert order == []


def test_cli_fix_only_skips_the_attack_round(monkeypatch):
    import scripts.run_pr as run_pr

    order = []
    monkeypatch.setattr(run_pr.orchestrator, "run_attack",
                        lambda *a, **k: order.append("attack") or 0)
    monkeypatch.setattr(run_pr.orchestrator, "run_fix",
                        lambda *a, **k: order.append("fix") or 0)
    assert run_pr.main(["--arena-id", "x", "--fix-only"]) == 0
    assert order == ["fix"]


def test_cli_rejects_fix_only_with_a_pr_url():
    import scripts.run_pr as run_pr

    with pytest.raises(SystemExit):
        run_pr.main(["https://github.com/o/r/pull/1", "--arena-id", "x", "--fix-only"])


def test_cli_requires_a_pr_url_for_an_attack_round():
    import scripts.run_pr as run_pr

    with pytest.raises(SystemExit):
        run_pr.main(["--arena-id", "x"])


# ---- pytest commands must not depend on a bare `python` being on PATH ----

def test_pytest_commands_use_a_real_interpreter():
    from engine.orchestrator import SUITE_CMD, EXPLOITS_CMD, exploit_cmd

    for cmd in (SUITE_CMD, EXPLOITS_CMD, exploit_cmd("tests/exploits/test_a.py")):
        assert not cmd.startswith("python "), "bare `python` is not on PATH on macOS"
        assert "-m pytest" in cmd and "-p no:cacheprovider" in cmd
    assert "--ignore=tests/exploits" in SUITE_CMD


# ---- recon backend selection (PRD rule 0.5: labeled fallback, never a stub) ----

@pytest.mark.parametrize("env,expected", [
    ({"OPENAI_API_KEY": "sk-x"}, "openai"),
    ({}, "codex"),
    ({"OPENAI_API_KEY": "sk-x", "RECON": "codex"}, "codex"),
    ({"RECON": "openai"}, "openai"),
])
def test_recon_backend_selection(monkeypatch, env, expected):
    from engine import recon

    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("RECON", raising=False)
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    assert recon.backend() == expected


@pytest.mark.parametrize("text", [
    '{"hypotheses": []}',
    '```json\n{"hypotheses": []}\n```',
    'Here is the result: {"hypotheses": []} -- done',
])
def test_recon_extracts_json_from_a_final_message(text):
    from engine.recon import _extract

    assert _extract(text) == {"hypotheses": []}
