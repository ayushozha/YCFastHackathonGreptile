# progress

One line per milestone (PRD rule 0.2): run the acceptance check, commit, push,
append here.

| time | milestone | owner | state |
|---|---|---|---|
| — | scaffold | both | tree from PRD section 4 in place; `shared/schema.py` and `demo/sample_run.jsonl` written; `pytest tests -q` green; replay serves the sample run |
| 1:15 | M0 contract frozen | both | pending — confirm `codex exec` flags, agree Appendix C, freeze schema |
| 2:30 | M1 first real hit | A | pending |
| 2:30 | M1' stage plays a full round | B | pending |
| 3:15 | M2 full engine loop | A | pending |
| 3:15 | M2' full arena on sample | B | pending |
| 3:45 | M3 live loop in browser | both | pending |
| 4:40 | M4 demo-proof | both | pending |

## Open before 1:00 pm

- [ ] `codex --version` and `codex exec --help` on the build machine → set
      `CODEX_FLAGS` in `engine/codex.py`.
- [ ] Confirm the Greptile v2 endpoint shapes (`engine/greptile.py`, SCOUT=api).
      SCOUT=app needs nothing but a GitHub token.
- [ ] Confirm the Modal Sandbox signatures before writing `modal_runner.py`.
- [ ] Fixture repo `payments-svc` per PRD section 5: PR #42 + PRs #38, #40, #35.
- [ ] Build machine runs Python 3.9. The Modal image in PRD section 9 pins
      3.11; either install 3.11 locally or accept that the local runner and the
      sandbox differ.
