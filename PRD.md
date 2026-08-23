# Code Arena PRD

Build spec for The Fast Hackathon (Greptile x YC), Sunday Aug 23, 2026. Hacking 1:00 pm to 5:00 pm PT, judging 5:00 to 5:45, roughly two minutes per team.

This file is the single source of truth. Drop it in the repo root as `PRD.md` and reference it from `AGENTS.md` (or `CLAUDE.md`). Build exactly this. Where it says cut, cut.

---

## 0. Agent operating rules

1. Codex is the primary coding agent for this build (hackathon eligibility requirement). The product also calls Codex at runtime; log every runtime `codex exec` invocation to `logs/codex_calls.jsonl` with prompt, exit code, duration.
2. Milestones in section 10 are hard. At each milestone: run the acceptance check, commit, push, append one line to `progress.md`.
3. Never fabricate a number that reaches the screen. Every count comes from an event. Every event comes from a subprocess exit code or an API response. No score out of 100.
4. Loop first, skin last. Nothing in section 8 starts until milestone M1 is green.
5. When a stage cannot work in time, degrade to the labeled fallback in section 11. Never silently stub a stage and present it as live.
6. Do not build: performance attacker, marketplace, memory or snapshots, user auth, multi-repo, sound, 3D, particle effects, leaderboard seeding by hand.
7. Prefer boring choices: FastAPI, JSONL files, vanilla HTML/JS, subprocess. No database. No framework that needs a build step unless Codex generates it in one shot.

---

## 1. One-liner and thesis

Code Arena: AI code reviewers become attackers, and a hit only counts if the exploit runs against your PR.

Thesis: every AI reviewer makes claims and most are noise. In the arena, a reviewer scores only when it writes an exploit test that executes and passes against the PR. Attackers that swing and miss lose rank. Fixes are verified by re-running the same exploits.

Sponsor mapping (each has a visible beat in the demo):

- Greptile: the scout. Its review of the PR is the scouting report; each comment becomes an attack hypothesis.
- OpenAI Codex: writes every exploit and every fix at runtime, and built the product.
- Modal: the arena floor. Each exploit runs in an isolated sandbox.
- Stripe: the thing under attack. The fixture PR is a real Stripe test-mode refund integration; a landed double-refund exploit produces two refund objects in the Stripe dashboard.

---

## 2. Demo script (90 seconds; this is the definition of done)

| # | Judge sees | Driven by |
|---|---|---|
| 1 | Paste PR URL, click Enter the arena | `POST /arena` |
| 2 | Stage goes dark, gate opens, PR walks in with full health, "Indexing with Greptile: 2,314 lines" | `arena_created`, `index_status` |
| 3 | Scouting report scrolls on the ticker; three attackers drop in, one per hypothesis | `scout_report`, `attacker_intro` x3 |
| 4 | Bug hunter: "Writing exploit", then pytest output streams in the terminal, `PASSED`, projectile hits the PR, `-30`, screen shake, health 100 to 70 | `exploit_written`, `test_output`, `hit` |
| 5 | Security and Ledger repeat. Health ends at 10. "Round over: 3 launched, 3 landed" | `hit`, `round_over` |
| 6 | Cut to Stripe test dashboard: two refunds on one payment (optional cut-in card in the UI) | `GET /arena/{id}/stripe` |
| 7 | Click Fix and rematch. Terminal shows `codex exec`, three file edits, suite 41 passed, exploits 3 failed, "failed = blocked". Health refills green. Attackers show Blocked | `fix_start`, `fix_diff`, `fix_result`, `blocked` x3 |
| 8 | Victory card: 3 launched, 3 landed round 1, 0 landed round 2, suite green. Leaderboard row for PR #42 flips to Survived, repo streak 4 to 5 | `final` |

Pitch line to say at step 7: "Failed means blocked. The same exploit that landed thirty seconds ago no longer works."

---

## 3. Scope

In scope:

- One PR at a time, from a GitHub URL, public repo or a repo the token can read.
- Three attackers: bug_hunter, security, ledger. Each hypothesis is owned by one attacker.
- Round 1 (attack), Fix, Round 2 (rematch).
- Battle log streaming real subprocess output.
- Leaderboard derived from the event logs of real prior runs.
- Replay mode from a cached event log for demo resilience.

Out of scope: everything in rule 0.6, plus GitHub app installation flow, multi-user, any database, any non-Python fixture.

---

## 4. Architecture

Two repositories:

- `code-arena/` (the product). Two halves that never share a Python object: the engine (a CLI that runs the pipeline and appends events to a file) and the arena (a FastAPI service that spawns the engine, tails the file over SSE, and serves the UI).
- `payments-svc/` (the fixture). Small FastAPI payments service with an open PR #42 containing three planted, executable bugs. Separate GitHub repo so the Greptile app can review it.

The event bus is a file. The engine appends one JSON line per event to `runs/<arena_id>/events.jsonl`; the arena tails that file. Integration between the two halves is a subprocess call plus a file path (section 7 and Appendix C), which is what lets two people build end to end without blocking each other (section 15).

```
code-arena/
  engine/                                   owner: A
    orchestrator.py   runs stages 0..5 for one arena_id, emits events
    events.py         emit(): append JSON line with seq and ts to runs/<id>/events.jsonl
    github.py         PR metadata, diff, clone, comments, post review
    greptile.py       scout report via app comments or Greptile API
    recon.py          OpenAI structured call -> hypotheses
    codex.py          subprocess wrapper for `codex exec`
    runner/
      base.py         Runner.run(workdir, cmd) -> (exit_code, stdout_iter)
      local.py        subprocess runner
      modal_runner.py Modal Sandbox runner
  arena/                                    owner: B
    api.py            FastAPI app: routes in section 7; spawns the engine; SSE tails events.jsonl
    leaderboard.py    derives PR and attacker boards by scanning runs/*/events.jsonl
    stripe_view.py    lists refunds for the fixture's seeded payment intent (test mode)
    replay.py         streams demo/*.jsonl under a new arena_id with original timing
  static/                                   owner: B
    index.html        the arena UI (single file, no build step)
    portraits/        generated attacker portraits (fallback: icons)
  shared/                                   frozen at 1:15 pm, edited only together
    schema.py         required fields per event type (section 6.7), used by both halves' tests
  demo/                                     owner: B
    sample_run.jsonl  hand-written full run, the contract fixture (B writes, A must reproduce)
    cached_run.jsonl  real full run saved by make_cache.py, for replay during judging
  prompts/                                  owner: A
    recon.txt exploit.txt fix.txt
  scripts/
    run_pr.py         owner: A. CLI contract in Appendix C
    make_cache.py     owner: B. copies runs/<id>/events.jsonl to demo/cached_run.jsonl
  tests/
    test_engine_events.py   owner: A. every emitted event validates against shared/schema.py
    test_arena_replay.py    owner: B. replaying demo/sample_run.jsonl reaches final
  progress.md  PRD.md  AGENTS.md  README.md  Makefile  requirements.txt  .env.example
```

Runtime data: `runs/<arena_id>/repo` (clone at PR head), `runs/<arena_id>/events.jsonl` (the bus), `runs/<arena_id>/state.json` (hypotheses and round 1 results, written by the engine so `--fix-only` can resume).

Environment (`.env.example`): `GITHUB_TOKEN`, `OPENAI_API_KEY`, `GREPTILE_API_KEY`, `STRIPE_SECRET_KEY` (test key), `RUNNER=local|modal`, `SCOUT=app|api|none`, `MODAL_TOKEN_ID`, `MODAL_TOKEN_SECRET`.

---

## 5. Fixture repo spec: `payments-svc`

Stack: FastAPI, SQLite via SQLAlchemy (or raw sqlite3), pytest, httpx TestClient, stripe SDK.

Data model:

- `users(id, role)` roles: `customer`, `finance`, `admin`.
- `payments(id, user_id, amount, refundable, stripe_payment_intent, refunded)`.
- `refunds(id, payment_id, amount, stripe_refund_id)`.

Auth convention: header `X-User-Id`. Dependency `require_role(role)` in `app/auth.py`, already used by admin routes on the base branch (`POST /admin/users`, `GET /admin/payments`). This is deliberate: it gives Greptile and Recon a convention to cite when the refund route ignores it.

Base branch endpoints: `POST /payments` (creates a payment; in Stripe test mode, creates and confirms a PaymentIntent with `pm_card_visa`), `GET /payments/{id}`, `GET /accounts/{user_id}` (balance and refund totals), admin routes above.

PR #42, branch `feat/refunds`, title "Add payment refunds", adds `POST /refunds {payment_id, amount}` in `app/refunds.py` with three planted bugs:

| id | bug | what a passing exploit shows | fix Codex should find |
|---|---|---|---|
| B1 | no `payment.refunded` guard and no idempotency key; two partial refunds of 50 on a 100 payment both return 200 | two refund rows (and two Stripe refund objects) for one payment | guard on `refunded`, or idempotency key on `Refund.create` |
| B2 | handler never checks `payment.user_id == caller` and does not use `require_role("finance")` | user B refunds user A's payment, 200 | ownership check or `Depends(require_role("finance"))` |
| B3 | uses request `amount` and ignores `payment.refundable` (partial-refund limit) | refund of 100 on a payment with `refundable=50` returns 200 | clamp or reject when `amount > payment.refundable` |

Stripe integration: `STRIPE_MODE=stub|test`. `test` uses the real SDK with the test key: `PaymentIntent.create(amount, currency="usd", payment_method="pm_card_visa", confirm=True, automatic_payment_methods={"enabled": True, "allow_redirects": "never"})` and `Refund.create(payment_intent=..., amount=...)`. `stub` is an in-memory fake with the same three calls. Default is `stub` unless `STRIPE_SECRET_KEY` is set. Both bugs B1 and B3 reproduce against real Stripe because partial refunds within the charge are accepted; that is why B3 is an over-limit bug rather than a negative-amount bug (Stripe rejects negatives itself).

Tests: `tests/conftest.py` provides `client`, `seed_payment(user_id, amount=100, refundable=50)`, `as_user(user_id)` (sets the header). Existing suite is about 40 tests and is green on both branches. `tests/exploits/` does not exist on either branch; the arena creates it in the working copy.

Reference exploits (for the human to sanity-check Codex output; do not commit these to the fixture):

```python
def test_refund_twice(client, seed_payment, as_user):
    p = seed_payment(user_id=1, amount=100, refundable=50)
    as_user(1)
    assert client.post("/refunds", json={"payment_id": p.id, "amount": 50}).status_code == 200
    assert client.post("/refunds", json={"payment_id": p.id, "amount": 50}).status_code == 200
    assert client.get(f"/accounts/1").json()["refunded_total"] == 100

def test_other_users_payment(client, seed_payment, as_user):
    p = seed_payment(user_id=1)
    as_user(2)
    assert client.post("/refunds", json={"payment_id": p.id, "amount": 10}).status_code == 200

def test_amount_over_limit(client, seed_payment, as_user):
    p = seed_payment(user_id=1, amount=100, refundable=50)
    as_user(1)
    assert client.post("/refunds", json={"payment_id": p.id, "amount": 100}).status_code == 200
```

Fixture prep checklist (before 1:00 pm is allowed; this is test data, not the product):

- [ ] Repo created, base branch green, `feat/refunds` pushed, PR #42 open with a two-paragraph description.
- [ ] Greptile GitHub app installed on the repo and its review comments present on PR #42.
- [ ] `scripts/seed_stripe.py` creates one confirmed test PaymentIntent and writes its id into the seed data.
- [ ] Three more small PRs (#38 webhooks, #40 CSV export, #35 rate limiter) exist so the leaderboard can be populated by real runs before judging. #35 should contain one unfixable-in-time bug so one row reads Knocked out.

---

## 6. Pipeline stages and contracts

All stages emit events (section 6.7). Stage functions are pure with respect to the event bus: they take an `emit` callback and return their result.

### 6.0 Ingest

Input: `pr_url`. Parse `owner/repo/number`. GitHub API: PR metadata (title, author, head sha, base ref, changed files count, additions), diff with `Accept: application/vnd.github.diff`. Clone at head sha into `runs/<arena_id>/repo` (shallow). Emit `arena_created`.

### 6.1 Scout (Greptile)

`SCOUT=app`: read PR review comments and issue comments via GitHub API, filter authors matching `greptile` (bot login). Each comment becomes `{path, line, body}`.

`SCOUT=api`: Greptile API. Index `POST /v2/repositories {remote: "github", repository: "owner/repo", branch}` with `Authorization: Bearer` and `X-GitHub-Token`; poll `GET /v2/repositories/{id}` until ready, emitting `index_status` each poll; then `POST /v2/query` with two questions: "How is authorization enforced on routes in this repo, and which routes skip it?" and "Is there an idempotency or double-execution guard pattern for money movement in this repo?" Confirm endpoint shapes against the Greptile docs at 1:00 pm.

Output: `scout_report {source, items: [{path, line, body}]}`. Emit `scout_report`.

Pick whichever source returns first; if both fail, `SCOUT=none` passes an empty report and the UI ticker says "No scouting report".

### 6.2 Recon (OpenAI)

Input: diff, scout report, and a conventions snippet (contents of `app/auth.py` and one admin route). One call to the OpenAI Responses API with the prompt in Appendix A.1, JSON output enforced.

Output schema:

```json
[{
  "id": "h1",
  "attacker": "bug_hunter | security | ledger",
  "title": "Refund runs twice for the same payment",
  "claim": "POST /refunds accepts a second refund for a payment that is already refunded",
  "file": "app/refunds.py",
  "line": 31,
  "exploit_plan": "seed payment 100 refundable 50; refund 50 twice as owner; expect both 200 and refunded_total 100",
  "severity": "critical | high | medium"
}]
```

Rules: 1 to 4 hypotheses. Attacker assignment: `security` for auth, authz, ownership, tenancy; `ledger` for amounts, limits, idempotency of money movement; `bug_hunter` for everything else. Damage map: critical 40, high 30, medium 20. Cap total damage at 100. Emit one `attacker_intro` per hypothesis.

### 6.3 Attack (Codex + runner)

For each hypothesis, in order (parallelize only if M2 is reached early):

1. `codex exec` with the prompt in Appendix A.2, `cwd = workdir`. Codex may write only `tests/exploits/test_<slug>.py`. Emit `exploit_written {path}`.
2. Validate: file exists and contains `def test_`. Otherwise emit `miss {reason: "no exploit produced"}` and continue.
3. `runner.run(workdir, "pytest tests/exploits/test_<slug>.py -q -p no:cacheprovider")`. Stream each stdout line as `test_output`. For `RUNNER=modal` emit `sandbox_up {sandbox_id, boot_ms}` before the first line.
4. Exit code 0 means the exploit passed, the bug is demonstrated: emit `hit {hypothesis_id, damage, hp_after}`. Nonzero: emit `miss {reason: "exploit did not pass"}`. Timeout 120 s counts as a miss.

After the loop: emit `round_over {launched, landed, missed, hp}`.

### 6.4 Fix (Codex)

`codex exec` with the prompt in Appendix A.3. Then:

- `runner.run(workdir, "pytest tests -q --ignore=tests/exploits -p no:cacheprovider")` for the existing suite.
- `runner.run(workdir, "pytest tests/exploits -q -p no:cacheprovider")` for the exploits.
- `git diff --stat` for the change summary.

Emit `fix_start`, `fix_diff {files: [{path, summary}]}` (summary is Codex's one-line-per-file output, or the stat line if absent), `fix_result {suite_passed, suite_failed, exploits_blocked, exploits_still_landed}`.

If `suite_failed > 0`: emit `fix_rejected {failing_tests}` and keep HP where it was. One retry with the failing test names appended to the prompt. If it fails again, the run ends as Knocked out with the fix shown but not accepted. That outcome is legitimate and demoable; do not hide it.

### 6.5 Rematch

Re-run each exploit individually. Per hypothesis emit `blocked {hypothesis_id, hp_after}` (HP restored by its damage) or `still_landed {hypothesis_id}`. Then emit `final {launched, landed_r1, landed_r2, suite_passed, files_changed, result: "survived | knocked_out"}`.

The engine writes nothing else. The leaderboard is derived by `arena/leaderboard.py`, which scans every `runs/*/events.jsonl` that contains a `final` event: PR row `{pr, title, result, health}` from `arena_created` and `final`; attacker rows `swings` = hypotheses owned (`attacker_intro`), `hits` = round 1 hits (`hit`); repo streak = consecutive survived results ordered by `arena_created.ts`.

### 6.6 Post review (optional, only after M3)

Push `tests/exploits/` and the fix to branch `arena/pr-<n>-<arena_id>`; post one PR review comment with a table of hypotheses, hit or miss, blocked or not, and a link to the branch.

### 6.7 Event schema

Events are JSON objects, one per line, written to `runs/<arena_id>/events.jsonl` and pushed over SSE. Common fields: `type`, `ts` (ISO), `arena_id`, `round` (1 or 2), `seq` (monotonic int).

| type | payload |
|---|---|
| arena_created | pr {number, title, author, files, additions}, repo |
| index_status | source, status, lines, files |
| scout_report | source, items[] |
| attacker_intro | hypothesis (full object), damage |
| exploit_written | hypothesis_id, path |
| sandbox_up | hypothesis_id, sandbox_id, boot_ms |
| test_output | hypothesis_id, line |
| hit | hypothesis_id, damage, hp_after |
| miss | hypothesis_id, reason |
| round_over | launched, landed, missed, hp |
| fix_start | |
| fix_diff | files[{path, summary}] |
| fix_result | suite_passed, suite_failed, exploits_blocked, exploits_still_landed |
| fix_rejected | failing_tests[] |
| blocked | hypothesis_id, hp_after |
| still_landed | hypothesis_id |
| final | launched, landed_r1, landed_r2, suite_passed, files_changed, result |
| error | stage, message |

---

## 7. API

| method | path | purpose |
|---|---|---|
| POST | `/arena` | body `{pr_url}`; generates `arena_id`, spawns `python scripts/run_pr.py <pr_url> --arena-id <id>` as a detached subprocess, returns `{arena_id}` immediately |
| GET | `/arena/{id}/events` | SSE; sends every line already in `runs/<id>/events.jsonl` from `seq=0` (or `?after=seq`), then tails the file (poll 200 ms) until `final` or `error` |
| POST | `/arena/{id}/fix` | spawns `python scripts/run_pr.py --arena-id <id> --fix-only`, returns 202 |
| GET | `/arena/{id}` | state folded from the event file: hp, hypotheses with status, counts |
| GET | `/arena/{id}/stripe` | refunds on the fixture's seeded payment intent, read from `runs/<id>/repo/seed.json` (test mode only) |
| POST | `/arena/replay` | body `{file}` default `demo/cached_run.jsonl`; writes the events under a new `arena_id` with original inter-event timing capped at 1.5 s, each tagged `replay: true`; the SSE route serves it like any other arena |
| GET | `/leaderboard` | `{prs: [...], attackers: [...], streak}` from `arena/leaderboard.py` |
| GET | `/` | serves `static/index.html` |

The arena never imports the engine. Everything it knows about a run comes from the event file. The engine's CLI contract is Appendix C; it is the M1 and M2 test surface and it works with no UI at all.

---

## 8. UI spec (`static/index.html`, one file, no build step)

Built by B from 1:35 pm against `demo/sample_run.jsonl` through the replay route. It must never depend on the engine being finished; the first time it sees real events is the 2:30 sync (section 15).

Layout (top to bottom):

1. Top bar: product name with a swords icon, `repo · round N`, repo streak with a flame icon.
2. Stage, 300 px tall, dark flat background (`#2C2C2A`), 12 px radius. Left: PR shield (teal circle), PR number, title, author, files, additions, health label, 12 px health bar (red fill, green when restored). Right: attacker column, three rows, each a portrait circle (generated image or icon), name, status pill. Overlays: projectile dot, damage popup, centered round banner, monospace ticker along the bottom.
3. Controls: PR URL input and Enter the arena button (before a run), Fix and rematch button (after round 1), Replay button (always).
4. Two columns: Battle log (monospace terminal, real subprocess output, always visible) and Leaderboard (PRs this week: rank, PR, result, health; Attackers: hits / swings, accuracy).
5. Victory card replaces the controls after `final`: four counts (launched, landed r1, landed r2, suite), files changed, buttons Post review to PR and Open diff.

Event to animation map (every animation fires on an event, nothing runs on a timer):

| event | animation |
|---|---|
| arena_created | stage fades in, shield slides in from left, health fills to 100 |
| index_status | ticker text updates |
| scout_report | ticker scrolls report summary |
| attacker_intro | attacker row drops in from above, status Ready |
| exploit_written | status Writing exploit, then Running |
| sandbox_up | floor tile under the attacker lights up, ticker shows boot time |
| test_output | line appended to battle log and ticker |
| hit | projectile flies attacker to shield (350 ms), damage number pops (800 ms), stage shakes (300 ms), health drains (400 ms), status Hit · -N |
| miss | projectile flies and fades before the shield, status Missed |
| round_over | banner Round over (1.1 s), ticker shows counts |
| fix_start | banner Round 2, all statuses Re-running |
| fix_diff | three file lines appended to the log |
| fix_result | log lines for suite and exploits with the "failed = blocked" note |
| blocked | status Blocked, health refills by damage |
| still_landed | status Still landed |
| final | banner PR survived or Knocked out, victory card, leaderboard row and streak update |
| error | red line in the log with the stage name |

Style rules: flat colors only, no gradients or glows, two font weights (400, 500), no text under 11 px, terminal never hidden, all animations under 400 ms except the banner. Portraits: three images generated once via the OpenAI image API (prompt: "flat pixel-art fighter portrait, [bug catcher | lock breaker | coin counter], dark background, no text"), saved to `static/portraits/`; fallback is an outline icon in a colored circle.

---

## 9. Integrations

Codex: `codex exec` in non-interactive mode with write access to the workdir. Verify flags with `codex exec --help` at 1:00 pm (sandbox and approval flags differ by version). Timeout 180 s per call. Capture stdout to the log; the "one line per changed file" summary is parsed from stdout.

Greptile: section 6.1. The app route is faster to demo on the fixture repo; the API route generalizes to any repo. Ship whichever works first, keep the other behind `SCOUT`.

Modal (`runner/modal_runner.py`): image = `debian_slim(python_version="3.11")` plus `pip_install_from_requirements(workdir/requirements.txt)`, plus the repo added at `/repo`. Create a sandbox with `timeout=120`, exec the pytest command, stream stdout lines, return exit code. Record boot time for `sandbox_up`. Build the image once per arena, not per attack. If the image build exceeds 90 s on first run, fall back to `RUNNER=local` for the demo and mention Modal as the isolation layer in the pitch. Confirm the current Sandbox API against Modal docs; do not guess signatures.

Stripe: lives in the fixture (section 5) plus `stripe_view.py` in the product, which lists refunds for the seeded payment intent so the UI can show the cut-in card after a landed B1 hit and again after the fix.

OpenAI: Recon (one structured call), portraits (three image calls, once).

---

## 10. Build order and milestones (hacking window 1:00 to 5:00 pm)

Milestones are defined here; who does what by when is section 15. Each milestone has one owner and one command that proves it.

| milestone | time | owner | proof |
|---|---|---|---|
| M0 contract frozen | 1:15 | both | `shared/schema.py` and `demo/sample_run.jsonl` committed; `run_pr.py` flags agreed (Appendix C) |
| M1 first real hit | 2:30 | A | `python scripts/run_pr.py <pr42> --arena-id m1` writes at least one `hit` with verbatim pytest output to `runs/m1/events.jsonl` |
| M1' stage plays a full round | 2:30 | B | `POST /arena/replay {file: demo/sample_run.jsonl}` drives the browser from arena_created through round_over with every animation in section 8 |
| M2 full engine loop | 3:15 | A | `run_pr.py <pr42> --arena-id m2 --fix` ends with `final.result == "survived"`, suite green, exploits blocked |
| M2' full arena on sample | 3:15 | B | replay of `sample_run.jsonl` reaches the victory card; leaderboard renders from `runs/` |
| M3 live loop in browser | 3:45 | both | paste URL, watch round 1, click Fix, victory card, no manual step |
| M4 demo-proof | 4:40 | both | `demo/cached_run.jsonl` replays with Wi-Fi off; leaderboard has four real rows; demo runs twice in a row |

Cut order if behind: Modal, then Stripe cut-in card, then portraits, then Scout via API (keep app comments), then Ledger attacker (keep two attackers). Never cut: real exploit execution, replay mode.

---

## 11. Fallbacks (label them in the UI, never fake)

| failure | fallback | UI label |
|---|---|---|
| Greptile unavailable | `SCOUT=none`, Recon from diff plus conventions snippet | ticker: "No scouting report" |
| Codex produces no exploit file | miss with reason | status Missed, log line "no exploit produced" |
| Exploit times out | miss | status Missed, log line "timed out" |
| Modal image build slow or failing | `RUNNER=local` | ticker: "Running locally" |
| Fix breaks the suite twice | Knocked out result with the diff shown | banner Knocked out, victory card shows suite red |
| Stripe test API slow | `STRIPE_MODE=stub` in the fixture; no cut-in card | none |
| Any network failure during judging | Replay from `demo/cached_run.jsonl` | small "Replay" tag in the top bar |

---

## 12. Acceptance criteria

- [ ] From a fresh clone with `.env` filled, `make demo` starts the service and `python scripts/run_pr.py <pr42> --fix` completes in under 4 minutes with `final.result == "survived"`.
- [ ] Every number on screen traces to an event in `events.jsonl`; a reviewer can grep the count.
- [ ] The battle log contains verbatim pytest output for each exploit in both rounds.
- [ ] `logs/codex_calls.jsonl` shows at least one exploit call per hypothesis and one fix call per run.
- [ ] Round 2 exploits that fail were passing in round 1 (the run log shows both results for the same file).
- [ ] Replay mode reproduces the full UI sequence with the network disabled.
- [ ] Leaderboard rows are derived from `runs/*/events.jsonl` by real runs, not seed data.
- [ ] `pytest tests/test_engine_events.py` passes: every event the engine emits validates against `shared/schema.py`.
- [ ] `pytest tests/test_arena_replay.py` passes: replaying `demo/sample_run.jsonl` folds to a state with `result == "survived"`.
- [ ] The arena package has no import from `engine/`; the engine has no import from `arena/`.
- [ ] Commits at M1, M2, M3, M4 with `progress.md` updated.

---

## 13. Prep before 1:00 pm (allowed: accounts, keys, fixture data, planning)

- [ ] GitHub token with repo scope; OpenAI key with credits; Greptile key; Modal tokens; Stripe test key.
- [ ] Fixture repo done per section 5 with PR #42 and three extra PRs.
- [ ] Greptile app installed on the fixture repo; confirm it commented on PR #42.
- [ ] `codex --version` and `codex exec --help` checked on the build machine.
- [ ] Empty product repo created with this file as `PRD.md` and an `AGENTS.md` that says: "Read PRD.md. Follow section 0. Current milestone is in progress.md."
- [ ] Ask at 12:30 opening remarks whether sponsor-specific prizes exist; if yes, the Greptile, Modal, and Stripe beats in section 2 are the entries.

---

## 14. Pitch and Q&A

Thirty seconds: "Every AI code reviewer makes claims. Most are noise. In Code Arena, reviewers are attackers, and a hit only counts if the exploit runs against your PR. Three attacks, three landed. Fix. Rematch. Zero landed. Every number on this screen is pytest output."

Likely questions:

- Versus Greptile: "Greptile finds it. We prove it, fix it, and only score what we can prove. It's the verification layer under a reviewer, and Greptile is the scout in our demo."
- Versus CodeQL or Semgrep: "They need a written query and match syntax. We derive the attack from one review comment, write an executable exploit, and confirm the fix by re-running it."
- False positives: "Structurally zero for landed hits. A landed hit is an executed test. Misses are shown too, and attackers that miss lose rank."
- Beyond Python: "Anything with a test runner. The exploit is a test."
- How is the score computed: "It isn't a score. It's counts: launched, landed, blocked."

---

## 15. Two-person split

Two people, two end-to-end tracks, one seam. The seam is the event file. A builds everything that produces `runs/<id>/events.jsonl`; B builds everything that consumes it, plus the fixture the engine attacks. Neither track needs the other to run its own end-to-end proof: A proves in the terminal with `run_pr.py`, B proves in the browser with `demo/sample_run.jsonl` through replay. They meet three times.

### 15.1 Ownership

| | A: engine | B: arena and fixture |
|---|---|---|
| End-to-end proof | `run_pr.py <pr42> --fix` prints events through `final` | browser plays `sample_run.jsonl` from gate to victory card |
| Owns (product repo) | `engine/`, `prompts/`, `scripts/run_pr.py`, `tests/test_engine_events.py`, `logs/` | `arena/`, `static/`, `demo/`, `scripts/make_cache.py`, `tests/test_arena_replay.py`, `README.md` |
| Owns (other) | `.env` keys: GitHub, OpenAI, Greptile, Modal | fixture repo `payments-svc`, PR #42 and the three extra PRs, Greptile app install, Stripe seeding, portraits |
| Sponsor beats | Codex at runtime, Greptile scout, Modal sandbox | Stripe cut-in card, leaderboard, replay |
| Stretch, in order | Modal runner, Scout via API, parallel attacks | portraits, Stripe cut-in, post review comment (6.6, needs A's branch push helper) |

Shared and frozen at M0: `shared/schema.py`, `demo/sample_run.jsonl`, the CLI flags in Appendix C. Changing any of these after 1:15 requires both people at one screen; do not edit them alone.

### 15.2 The contract, in three parts

1. `shared/schema.py`: a dict of event type to required payload fields, straight from section 6.7. A's test asserts every emitted event has them; B's UI reads only these fields.
2. `demo/sample_run.jsonl`: B writes it by hand at 1:15 for PR #42 with realistic values: arena_created, index_status x2, scout_report, attacker_intro x3, then per hypothesis exploit_written, four test_output lines, hit; round_over; fix_start, fix_diff, fix_result, blocked x3, final survived. About 40 lines. This file is B's test data and A's target: at 2:30, A's real log must play in B's UI with no code change on B's side.
3. `scripts/run_pr.py` flags (Appendix C): B's API only ever calls the CLI with these flags and reads the file; it never imports engine code.

### 15.3 Sync points (the only scheduled conversations)

| when | what | duration |
|---|---|---|
| 1:00 to 1:15 | M0: confirm fixture state, B drafts `sample_run.jsonl` and `schema.py` while A confirms `codex exec` flags, agree Appendix C, commit, split | 15 min |
| 2:30 | A hands over `runs/m1/events.jsonl`; B replays it. Every payload mismatch is fixed on the side that deviated from `schema.py` | 10 min |
| 3:30 to 3:45 | Live wiring: B's `POST /arena` spawns A's CLI; B's `POST /fix` spawns `--fix-only`; run the loop once together. That is M3 | 15 min |
| 4:15 | A runs PRs #38, #40, #35 through the engine for the leaderboard while B runs `make_cache.py` on the best PR #42 run and tests replay offline; then rehearse twice | shared |

Outside these windows: async only, small commits on `main`, `git pull --rebase` before every push. Paths are disjoint, so conflicts mean someone edited the other's directory; revert and talk.

### 15.4 A: engine schedule

| time | build | proof |
|---|---|---|
| 1:15 to 1:45 | `engine/events.py` (emit with seq, ts, arena_id, round), `engine/codex.py`, `engine/runner/local.py`, `run_pr.py` skeleton honoring Appendix C. Clone the fixture at `feat/refunds` by hand, hardcode hypothesis B1, get Codex to write one exploit and pytest to run it | one `hit` event in a file |
| 1:45 to 2:30 | `github.py` ingest (diff, clone), `recon.py` (OpenAI JSON, Appendix A.1), attack loop over hypotheses with validation, timeouts, `round_over`, `state.json` | M1 |
| 2:30 to 2:40 | sync: hand log to B | |
| 2:40 to 3:15 | fix stage with retry, rematch, `final`, `--fix-only` resume from `state.json` | M2 |
| 3:15 to 3:30 | `greptile.py` with `SCOUT=app` (comments via GitHub API); API route only if the app route took under 10 minutes | scout_report event with real comments |
| 3:30 to 3:45 | sync: live wiring | M3 |
| 3:45 to 4:15 | Modal runner behind `RUNNER=modal` if M2 landed by 3:15; otherwise robustness: kill hung Codex calls, clearer miss reasons, second run of PR #42 clean from a fresh workdir | two consecutive clean runs |
| 4:15 to 4:40 | run #38, #40, #35 for the leaderboard; `tests/test_engine_events.py` green; `progress.md` | M4 (engine side) |
| 4:40 to 5:00 | freeze, no engine changes; stand by for the live demo run | |

### 15.5 B: arena and fixture schedule

| time | build | proof |
|---|---|---|
| 1:15 to 1:35 | fixture final check: PR #42 open with all three bugs, Greptile comments present, `seed.json` with the Stripe payment intent id committed on the PR branch, extra PRs exist. If the fixture was not prepped before 1:00, this block runs to 1:50 and Codex generates it from section 5 in one shot | `pytest` green on both fixture branches |
| 1:35 to 2:30 | `arena/api.py` with `/`, `/arena/replay`, `/arena/{id}/events` tailing a file; `static/index.html` top bar, stage, attacker rows, health bar, battle log, driven by replaying `sample_run.jsonl`. Hit animation, damage popup, shake, ticker | M1' |
| 2:30 to 2:40 | sync: replay A's real log | |
| 2:40 to 3:15 | round 2 states, fix diff lines in the log, blocked refill, victory card, `arena/leaderboard.py` scanning `runs/`, leaderboard panel, controls (URL input, Fix button, Replay button), `GET /arena/{id}` fold | M2' |
| 3:15 to 3:30 | `POST /arena` and `POST /arena/{id}/fix` spawning the CLI per Appendix C, tested against A's M1 log directory layout; `tests/test_arena_replay.py` | routes return before the engine finishes |
| 3:30 to 3:45 | sync: live wiring | M3 |
| 3:45 to 4:15 | `arena/stripe_view.py` and the cut-in card after a landed B1 hit and after the fix; portraits via the image API; section 8 timing polish | cut-in shows two refunds, then one |
| 4:15 to 4:40 | `make_cache.py`, replay tag in the top bar, test with Wi-Fi off, README with screenshot and pitch, rehearsal script with a timer | M4 (arena side) |
| 4:40 to 5:00 | freeze; drive the demo; A watches the terminal | |

### 15.6 If one side is late

- A is late at 2:30: B keeps building on `sample_run.jsonl`. The demo can run on replay of whatever real log A has at 4:15, even a partial one, labeled Replay. Never fake the missing half.
- B is late at 3:30: A's terminal is the fallback demo. `run_pr.py` with colored event lines and the pytest output is still real, and the pitch does not change.
- Both late: cut Ledger, run two attackers, skip Stripe and Modal, ship replay. The event contract makes every cut a deletion, not a rewrite.

---

## Appendix A. Prompts

### A.1 Recon (system prompt, `prompts/recon.txt`)

```
You are Recon for Code Arena. You receive a pull request diff, a scouting report (reviewer comments, possibly empty), and a snippet showing the repo's conventions.

Produce 1 to 4 attack hypotheses. A hypothesis must be demonstrable by a single pytest test that calls the application through the fixtures in tests/conftest.py (client, seed_payment, as_user) and PASSES only while the bug exists. Prefer behaviors observable through HTTP status codes or through state read back via the API. Do not propose style issues, performance claims, or anything that cannot be asserted in a test.

Assign each hypothesis to exactly one attacker:
- security: authentication, authorization, ownership, tenancy
- ledger: amounts, limits, idempotency of money movement
- bug_hunter: everything else (double execution, state, validation)

Severity: critical (money or data loss, privilege escalation), high (incorrect behavior reachable by a normal user), medium (edge case).

Output JSON only, an array of objects with keys: id, attacker, title, claim, file, line, exploit_plan, severity.
```

### A.2 Exploit (`prompts/exploit.txt`, rendered per hypothesis, passed to `codex exec`)

```
Write ONE pytest file at tests/exploits/test_{slug}.py that demonstrates this bug.

Claim: {claim}
Where: {file}:{line}
Plan: {exploit_plan}

Rules:
- Use the fixtures from tests/conftest.py: client, seed_payment, as_user.
- The test must PASS while the bug exists and FAIL once the bug is fixed.
- Assert on HTTP status codes or on state read back through the API. No mocks that bypass the app.
- Do not modify any file outside tests/exploits/.
- Keep it under 30 lines. One test function.
```

### A.3 Fix (`prompts/fix.txt`, passed to `codex exec`)

```
The files in tests/exploits/ are exploit tests that currently PASS because of bugs in the application.

Fix the application so that every test in tests/exploits/ FAILS and every test under tests/ outside tests/exploits/ still PASSES. Make the minimal change. Follow the repo's existing conventions (for example the require_role dependency used by admin routes, and the refundable limit on payments).

Do not edit anything under tests/. When finished, print exactly one line per changed file in the form: <path>  <one-line summary of the change>
```

Retry suffix when the suite breaks: `The previous attempt broke these tests: {failing_tests}. Keep them passing.`

## Appendix B. Cached run and replay

`scripts/make_cache.py <arena_id>` copies `runs/<arena_id>/events.jsonl` to `demo/cached_run.jsonl`. Replay streams those events in order, sleeping the original gap between events capped at 1.5 s, under a new arena_id, with a `replay: true` field on every event so the UI can show the tag. The demo runs live first; replay is the backup if anything hangs during judging.

## Appendix C. Engine CLI contract (`scripts/run_pr.py`)

This is the only interface between the two halves. B calls it; A implements it. Frozen at M0.

```
python scripts/run_pr.py <pr_url> --arena-id <id> [--runner local|modal] [--scout app|api|none]
    Runs stages 0 to 3 (ingest, scout, recon, attack) and stops after round_over.
    Creates runs/<id>/, appends events to runs/<id>/events.jsonl, writes runs/<id>/state.json.
    Also prints each event line to stdout for terminal use.
    Exit 0 on round_over, 1 on an error event.

python scripts/run_pr.py --arena-id <id> --fix-only
    Resumes from runs/<id>/state.json and runs stages 4 and 5 (fix, rematch), ending in final.
    Appends to the same events.jsonl; seq continues from the last line.

python scripts/run_pr.py <pr_url> --arena-id <id> --fix
    Both of the above in one process (A's own M2 proof; B never calls this form).
```

Guarantees the engine makes:

- `events.jsonl` is append-only, one JSON object per line, `seq` strictly increasing from 0, each line flushed before the next stage starts.
- The first line is always `arena_created`; the last line of a completed run is `final`; an aborted run ends with `error`.
- `state.json` contains `{pr, hypotheses: [...], round1: {hits: [...], misses: [...], hp}}` and is complete before `round_over` is written.
- The engine never reads or writes anything under `arena/`, `static/`, or `demo/`.

Guarantees the arena makes:

- It launches the CLI with `subprocess.Popen`, detached, cwd at repo root, and never waits on it.
- It reads only `runs/<id>/events.jsonl`, `runs/<id>/state.json`, and `runs/<id>/repo/seed.json`.
- It treats an unknown event type as a log line, not an error, so a new event from A cannot break the UI.
