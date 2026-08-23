# AGENTS.md

Read `PRD.md`. Follow section 0. The current milestone is in `progress.md`.

## Non-negotiables (PRD section 0)

1. **Codex is the primary coding agent for this build** — hackathon eligibility.
   The product also calls Codex at runtime; every runtime `codex exec` is logged
   to `logs/codex_calls.jsonl` with prompt, exit code, duration.
2. At each milestone in section 10: run the acceptance check, commit, push,
   append one line to `progress.md`.
3. **Never fabricate a number that reaches the screen.** Every count comes from
   an event; every event comes from a subprocess exit code or an API response.
   No score out of 100.
4. Loop first, skin last. Nothing in section 8 starts until M1 is green.
5. When a stage cannot work in time, degrade to the labeled fallback in section
   11. Never silently stub a stage and present it as live.
6. Do not build: performance attacker, marketplace, memory or snapshots, user
   auth, multi-repo, sound, 3D, particle effects, hand-seeded leaderboard.
7. Prefer boring choices: FastAPI, JSONL files, vanilla HTML/JS, subprocess.
   No database. No build step.

## The seam

The event file is the only interface.

```
engine  ->  runs/<arena_id>/events.jsonl  ->  arena
```

* `arena/` must never import `engine/`; `engine/` must never import `arena/`.
* The arena launches `scripts/run_pr.py` with `subprocess.Popen` and reads only
  `runs/<id>/events.jsonl`, `runs/<id>/state.json`, `runs/<id>/repo/seed.json`.
* An unknown event type is a log line, not an error.

## Frozen at M0 (1:15 pm) — do not edit alone

* `shared/schema.py`
* `demo/sample_run.jsonl`
* the CLI flags in `scripts/run_pr.py` (PRD Appendix C)

## Ownership (PRD 15.1)

| A: engine | B: arena and fixture |
|---|---|
| `engine/`, `prompts/`, `scripts/run_pr.py`, `tests/test_engine_events.py`, `logs/` | `arena/`, `static/`, `demo/`, `scripts/make_cache.py`, `tests/test_arena_replay.py`, `README.md` |

Paths are disjoint. A conflict means someone edited the other's directory:
revert and talk.

## Before you touch anything with a TODO

`engine/codex.py` (flag names), `engine/greptile.py` (SCOUT=api endpoints) and
`engine/runner/modal_runner.py` (Sandbox API) all carry TODOs that say *confirm
against the docs, do not guess*. That instruction is load-bearing — the flags
and signatures differ by version.
