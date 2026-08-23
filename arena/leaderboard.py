"""Derived from runs/*/events.jsonl. No seed data (PRD 6.5, acceptance 12)."""

import os

from arena.paths import RUNS_DIR, events_path, read_jsonl


def _finished_runs():
    if not os.path.isdir(RUNS_DIR):
        return []
    runs = []
    for arena_id in sorted(os.listdir(RUNS_DIR)):
        events = read_jsonl(events_path(arena_id))
        if not events:
            continue
        if any(e.get("type") == "final" for e in events):
            runs.append((arena_id, events))
    # ordered by arena_created.ts, per PRD 6.5
    runs.sort(key=lambda pair: _created_ts(pair[1]))
    return runs


def _created_ts(events):
    for e in events:
        if e.get("type") == "arena_created":
            return e.get("ts", "")
    return ""


def leaderboard():
    prs, attackers, results = [], {}, []
    for arena_id, events in _finished_runs():
        created = next((e for e in events if e.get("type") == "arena_created"), None)
        final = next((e for e in events if e.get("type") == "final"), None)
        if not created or not final:
            continue
        hp = final.get("hp")
        if hp is None:  # fold back from the last hp-bearing event
            hp = next(
                (e.get("hp_after", e.get("hp")) for e in reversed(events)
                 if e.get("type") in ("blocked", "hit", "round_over")),
                0,
            )
        prs.append({
            "arena_id": arena_id,
            "pr": created["pr"].get("number"),
            "title": created["pr"].get("title"),
            "repo": created.get("repo"),
            "result": final.get("result"),
            "health": hp,
            "ts": created.get("ts"),
        })
        results.append(final.get("result"))

        for e in events:
            if e.get("type") == "attacker_intro":
                name = e["hypothesis"].get("attacker", "unknown")
                row = attackers.setdefault(name, {"attacker": name, "swings": 0, "hits": 0})
                row["swings"] += 1
            elif e.get("type") == "hit" and e.get("round") == 1:
                owner = _owner_of(events, e.get("hypothesis_id"))
                if owner:
                    row = attackers.setdefault(owner, {"attacker": owner, "swings": 0, "hits": 0})
                    row["hits"] += 1

    for row in attackers.values():
        row["accuracy"] = round(row["hits"] / row["swings"], 2) if row["swings"] else 0.0

    prs.sort(key=lambda r: (r["result"] != "survived", -(r["health"] or 0)))
    for i, row in enumerate(prs, start=1):
        row["rank"] = i

    return {
        "prs": prs,
        "attackers": sorted(attackers.values(), key=lambda r: (-r["hits"], r["attacker"])),
        "streak": _streak(results),
    }


def _owner_of(events, hypothesis_id):
    for e in events:
        if e.get("type") == "attacker_intro" and e["hypothesis"].get("id") == hypothesis_id:
            return e["hypothesis"].get("attacker")
    return None


def _streak(results):
    """Consecutive survived results, most recent first (PRD 6.5)."""
    n = 0
    for r in reversed(results):
        if r == "survived":
            n += 1
        else:
            break
    return n
