# Code Arena

**AI code reviewers become attackers, and a hit only counts if the exploit runs
against your PR.**

Every AI reviewer makes claims and most are noise. In the arena a reviewer
scores only when it writes an exploit test that *executes and passes* against
the PR. Attackers that swing and miss lose rank. Fixes are verified by
re-running the same exploits.

Built for The Fast Hackathon (Greptile x YC), 23 Aug 2026. Spec: `PRD.md`.

## The loop

```
PR url ──▶ Greptile scouts ──▶ Recon writes hypotheses ──▶ Codex writes an
exploit per hypothesis ──▶ pytest runs it in a sandbox ──▶ it passes? that's a
hit ──▶ Codex fixes ──▶ the same exploits re-run ──▶ they fail? blocked.
```

`failed = blocked` is the whole pitch: the exploit that landed thirty seconds
ago no longer works.

## Run it

```bash
pip install -r requirements.txt
cp .env.example .env          # GITHUB_TOKEN, OPENAI_API_KEY, GREPTILE_API_KEY, ...
make demo                     # arena on http://localhost:8000
```

Then paste a PR url and click **Enter the arena**, or click **Replay** to play
a cached run with the network off.

Engine only, no UI:

```bash
python scripts/run_pr.py https://github.com/<owner>/payments-svc/pull/42 --arena-id m1
python scripts/run_pr.py --arena-id m1 --fix-only
```

## Architecture

Two halves that never share a Python object.

```
engine/   a CLI that runs the pipeline and appends events to a file
                    │
     runs/<arena_id>/events.jsonl        ← the whole interface
                    │
arena/    a FastAPI service that spawns the engine, tails the file over SSE,
          and serves static/index.html
```

Every number on screen traces to a line in `events.jsonl`. You can grep it.

| path | what |
|---|---|
| `engine/orchestrator.py` | stages 0–5 (PRD section 6) |
| `engine/events.py` | `emit()` — append one JSON line, flush, `seq` monotonic |
| `engine/runner/` | `local.py` subprocess, `modal_runner.py` Modal Sandbox |
| `arena/api.py` | the routes in PRD section 7 |
| `arena/fold.py` | events → UI state |
| `arena/leaderboard.py` | derived from `runs/*/events.jsonl`, never seeded |
| `shared/schema.py` | the frozen event contract |
| `demo/sample_run.jsonl` | the contract fixture both halves build against |

## Fixture

The thing under attack is `payments-svc`: a small FastAPI payments service with
an open PR #42 that adds refunds and carries three planted, executable bugs —
no idempotency guard, no ownership check, and no refundable limit. Spec is
PRD section 5. It lives in its own repo so the Greptile app can review it.

## Tests

```bash
pytest tests -q
```

* `test_engine_events.py` — every event the engine emits validates against
  `shared/schema.py`.
* `test_arena_replay.py` — replaying `demo/sample_run.jsonl` folds to
  `result == "survived"`.

## Sponsors

* **Greptile** — the scout. Its PR review becomes the attack hypotheses.
* **OpenAI Codex** — writes every exploit and every fix at runtime, and built
  the product.
* **Modal** — the arena floor. Each exploit runs in an isolated sandbox.
* **Stripe** — the thing under attack. A landed double-refund exploit produces
  two refund objects in the Stripe test dashboard.
