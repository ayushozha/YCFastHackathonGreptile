# progress

One line per milestone (PRD rule 0.2): run the acceptance check, commit, push,
append here.

| time | milestone | owner | state |
|---|---|---|---|
| — | scaffold | both | tree from PRD section 4 in place; `shared/schema.py` and `demo/sample_run.jsonl` written; `pytest tests -q` green (62); replay serves the sample run end to end |
| — | toolchain | both | Python 3.11.16 (brew `python@3.11`), all of `requirements.txt` installed and pinned to verified versions, `codex-cli 0.149.0` live-tested, `modal 1.5.4` client present |
| — | fixture | (A, B's lane) | `payments-svc` built per PRD section 5, pushed public, PR #1 open with B1/B2/B3 planted. 39 tests green on `main`, 46 on `feat/refunds`. All three reference exploits confirmed passing. |
| 1:15 | M0 contract frozen | both | pending — agree Appendix C at one screen, then freeze `shared/schema.py` and `demo/sample_run.jsonl` |
| **2:30** | **M1 first real hit** | **A** | **GREEN** — `run_pr.py <pr1> --arena-id m1` wrote 3 real hits to `runs/m1/events.jsonl`, HP 100 → 0 |
| **2:30** | **M1' stage plays a full round** | **B** | **GREEN** — `POST /arena/replay` on `demo/sample_run.jsonl` drives the browser data path arena_created → round_over; verified via live HTTP/SSE against a running `uvicorn arena.api:app` |
| **3:15** | **M2 full engine loop** | **A** | **GREEN** — `--fix-only` ended `final.result == "survived"`, suite 46 passed, 3 exploits blocked, HP back to 100 |
| **3:15** | **M2' full arena on sample** | **B** | **GREEN** — replayed A's real 152-event `demo/cached_run.jsonl` end to end: `final == {launched:3, landed_r1:3, landed_r2:0, suite_passed:46, result:"survived"}`, all 3 hypotheses folded to `blocked`; `/leaderboard` derives correctly from the run; full suite 76 passed |
| 3:45 | M3 live loop in browser | both | pending — B's routes (`/arena`, `/fix`) already spawn `run_pr.py` per Appendix C, ready to wire live |
| 4:40 | M4 demo-proof | both | offline replay of `demo/cached_run.jsonl` verified (no network calls in the replay path); leaderboard has 4 real fixture PRs open now (see below) |

## B's fixture work (this session)

- Confirmed A's `payments-svc` (PR #1) already has all three planted bugs
  reproducing exactly per PRD 5's reference exploits — no changes needed.
- Installed/installing the Greptile app on `ayushozha/payments-svc` (was the
  last blocker on the scout stage).
- Opened the three extra fixture PRs so the leaderboard has four real rows:
  [#2 webhooks](https://github.com/ayushozha/payments-svc/pull/2),
  [#3 csv-export](https://github.com/ayushozha/payments-svc/pull/3),
  [#4 rate-limiter](https://github.com/ayushozha/payments-svc/pull/4) — the
  rate-limiter PR plants a shared-bucket bug (global instead of per-user) as
  the "hard to fix cleanly" row.

## Toolchain, verified 23 Aug 2026

```
brew install python@3.11          # 3.11.16, matches the Modal image in PRD 9
python3.11 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m pytest tests -q
```

* `codex-cli 0.149.0` is on PATH. `CODEX_FLAGS` in `engine/codex.py` is
  `--sandbox workspace-write --color never`, read off `codex exec --help` and
  confirmed with a live call: exit 0, file written inside the workdir,
  `--output-last-message` captured, one line appended to
  `logs/codex_calls.jsonl`.
* `openai` had to move to 3.3.1 — the Responses API that `engine/recon.py`
  uses does not exist in the 1.x line.
* Every module under `engine/` and `arena/` imports cleanly on 3.11.

## A's end-to-end proof, run for real

Target: <https://github.com/ayushozha/payments-svc/pull/1>

```
run_pr.py <pr1> --arena-id m1              ->  3 launched, 3 landed, hp 0
run_pr.py --arena-id m1 --fix-only         ->  survived, 0 landed r2, suite 46, hp 100
```

152 events in `runs/m1/events.jsonl`, cached to `demo/cached_run.jsonl`. Every
section 12 criterion for the engine checked green against that file: schema
validity, `arena_created` first / `final` last, seq monotonic from 0, verbatim
pytest output in both rounds, every round-2 block was a round-1 hit, and
`logs/codex_calls.jsonl` holds `{recon: 1, exploit: 3, fix: 1}`.

Recon found all three planted bugs from the diff alone — the scouting report
was empty (the Greptile app is not installed on the fixture yet) and the ticker
says so rather than pretending. The fix Codex wrote is 6 lines in
`app/refunds.py`: it reaches for the repo's own `require_role("finance")` and
adds a cumulative refundable check, which blocks all three exploits at once.

## Two decisions left for the team

1. **`-q` vs `-v` in the battle log.** PRD 6.3 specifies `pytest -q`, which
   prints `.`; PRD section 2 says the judge sees `PASSED`, which only `-v`
   prints. Left on the spec'd `-q`; `PYTEST_VERBOSITY=-v` flips it.
2. **Recon transport.** With no `OPENAI_API_KEY` on the box, Recon ran through
   `codex exec --output-schema` (same prompt, same enforced schema, read-only
   sandbox) and the run reports `recon-codex` in `index_status`. Set the key to
   restore the OpenAI Responses path the PRD names; `RECON=openai|codex` forces
   either.

## Open before 1:00 pm

- [ ] Install the Greptile app on `ayushozha/payments-svc` so PR #1 gets review
      comments — SCOUT=app returns an empty report until then (labeled, not faked).
- [ ] Confirm the Greptile v2 endpoint shapes (`engine/greptile.py`, SCOUT=api).
- [ ] Confirm the Modal Sandbox signatures against the docs, then write
      `engine/runner/modal_runner.py`. Client 1.5.4 is installed.
- [ ] Three more fixture PRs so the leaderboard has four real rows (A's 4:15
      block). One should carry a bug that cannot be fixed in time, so a row
      reads Knocked out.
- [ ] Fill `.env` from `.env.example` — `OPENAI_API_KEY` restores the Recon
      path the PRD specifies, `STRIPE_SECRET_KEY` enables the cut-in card.
- [ ] Watch the UI play a replay once in a browser — the data path is verified
      but nobody has looked at the animations yet.
