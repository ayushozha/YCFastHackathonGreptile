"""Fold an event list into UI state (GET /arena/{id}, PRD section 7).

Rule 0.3: every number here comes from an event. Nothing is invented, and an
unknown event type is a log line, not an error (Appendix C).
"""

STARTING_HP = 100


def fold(events):
    state = {
        "arena_id": None,
        "pr": None,
        "repo": None,
        "hp": STARTING_HP,
        "round": 1,
        "hypotheses": [],
        "scout": None,
        "log": [],
        "counts": {"launched": 0, "landed_r1": 0, "missed": 0, "landed_r2": 0, "blocked": 0},
        "fix": None,
        "final": None,
        "error": None,
        "replay": False,
        "last_seq": -1,
    }
    by_id = {}

    for e in events:
        etype = e.get("type")
        state["arena_id"] = e.get("arena_id", state["arena_id"])
        state["round"] = e.get("round", state["round"])
        state["last_seq"] = max(state["last_seq"], e.get("seq", -1))
        if e.get("replay"):
            state["replay"] = True

        if etype == "arena_created":
            state["pr"] = e["pr"]
            state["repo"] = e["repo"]
        elif etype == "scout_report":
            state["scout"] = {"source": e["source"], "count": len(e["items"] or [])}
        elif etype == "attacker_intro":
            h = dict(e["hypothesis"])
            h["damage"] = e["damage"]
            h["status"] = "ready"
            by_id[h["id"]] = h
            state["hypotheses"].append(h)
            state["counts"]["launched"] += 1
        elif etype == "exploit_written":
            _set(by_id, e, "running")
        elif etype == "test_output":
            state["log"].append(e["line"])
        elif etype == "hit":
            state["hp"] = e["hp_after"]
            _set(by_id, e, "hit")
            state["counts"]["landed_r1"] += 1
        elif etype == "miss":
            _set(by_id, e, "missed", reason=e.get("reason"))
            state["counts"]["missed"] += 1
        elif etype == "round_over":
            state["hp"] = e["hp"]
        elif etype == "fix_start":
            for h in state["hypotheses"]:
                if h["status"] == "hit":
                    h["status"] = "rerunning"
        elif etype == "fix_diff":
            state["fix"] = dict(state["fix"] or {}, files=e["files"])
        elif etype == "fix_result":
            state["fix"] = dict(state["fix"] or {}, **{
                k: e[k] for k in
                ("suite_passed", "suite_failed", "exploits_blocked", "exploits_still_landed")
            })
        elif etype == "fix_rejected":
            state["fix"] = dict(state["fix"] or {}, rejected=e["failing_tests"])
        elif etype == "blocked":
            state["hp"] = e["hp_after"]
            _set(by_id, e, "blocked")
            state["counts"]["blocked"] += 1
        elif etype == "still_landed":
            _set(by_id, e, "still_landed")
            state["counts"]["landed_r2"] += 1
        elif etype == "final":
            state["final"] = {k: e[k] for k in (
                "launched", "landed_r1", "landed_r2", "suite_passed",
                "files_changed", "result") if k in e}
        elif etype == "error":
            state["error"] = {"stage": e["stage"], "message": e["message"]}
        # unknown types fall through to the log, never an error

    return state


def _set(by_id, event, status, **extra):
    h = by_id.get(event.get("hypothesis_id"))
    if h is not None:
        h["status"] = status
        h.update(extra)
