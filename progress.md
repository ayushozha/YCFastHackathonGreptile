# progress

One line per milestone (PRD rule 0.2): run the acceptance check, commit, push,
append here.

| time | milestone | owner | state |
|---|---|---|---|
| — | scaffold | both | tree from PRD section 4 in place; `shared/schema.py` and `demo/sample_run.jsonl` written; `pytest tests -q` green (62); replay serves the sample run end to end |
| — | toolchain | both | Python 3.11.16 (brew `python@3.11`), all of `requirements.txt` installed and pinned to verified versions, `codex-cli 0.149.0` live-tested, `modal 1.5.4` client present |
| 1:15 | M0 contract frozen | both | pending — agree Appendix C at one screen, then freeze `shared/schema.py` and `demo/sample_run.jsonl` |
| 2:30 | M1 first real hit | A | pending |
| 2:30 | M1' stage plays a full round | B | pending |
| 3:15 | M2 full engine loop | A | pending |
| 3:15 | M2' full arena on sample | B | pending |
| 3:45 | M3 live loop in browser | both | pending |
| 4:40 | M4 demo-proof | both | pending |

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

## Open before 1:00 pm

- [ ] Confirm the Greptile v2 endpoint shapes (`engine/greptile.py`, SCOUT=api).
      SCOUT=app (bot comments via the GitHub API) needs only `GITHUB_TOKEN`.
- [ ] Confirm the Modal Sandbox signatures against the docs, then write
      `engine/runner/modal_runner.py`. Client 1.5.4 is installed.
- [ ] Fixture repo `payments-svc` per PRD section 5: PR #42 plus #38, #40, #35.
- [ ] Greptile app installed on the fixture repo, commenting on PR #42.
- [ ] Fill `.env` from `.env.example`.
- [ ] Watch the UI play a replay once in a browser — the data path is verified
      but nobody has looked at the animations yet.
