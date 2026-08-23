"""Runs stages 0..5 for one arena_id and emits events (PRD section 6).

The engine never imports anything under arena/, static/ or demo/, and it never
writes anything except runs/<arena_id>/. Its whole interface to the other half
is the event file plus the CLI in Appendix C.
"""

import os
import time

from engine import codex, github, greptile, recon
from engine.events import (
    Emitter,
    read_state,
    workdir as workdir_for,
    write_state,
)
from engine.runner.base import DEFAULT_TIMEOUT, get_runner
from shared.schema import STARTING_HP, damage_for

EXPLOIT_DIR = "tests/exploits"
SUITE_CMD = "python -m pytest tests -q --ignore=tests/exploits -p no:cacheprovider"
EXPLOITS_CMD = "python -m pytest tests/exploits -q -p no:cacheprovider"


def exploit_cmd(path):
    return f"python -m pytest {path} -q -p no:cacheprovider"


# ---------------------------------------------------------------- stage 0..3


def run_attack(pr_url, arena_id, runner_name="local", scout_source="app"):
    """Stages 0-3. Stops after round_over. Writes state.json first."""
    emit = Emitter(arena_id, round_no=1)
    try:
        # 6.0 ingest
        owner, repo, number = github.parse_pr_url(pr_url)
        pr = github.get_pr(owner, repo, number)
        wd = workdir_for(arena_id)
        github.clone_at(pr["clone_url"], pr["head_sha"], wd)
        emit(
            "arena_created",
            pr={
                "number": pr["number"],
                "title": pr["title"],
                "author": pr["author"],
                "files": pr["files"],
                "additions": pr["additions"],
            },
            repo=f"{owner}/{repo}",
            pr_url=pr_url,
        )

        # 6.1 scout
        report = greptile.scout(scout_source, owner, repo, number, pr["head_ref"], emit)
        emit("scout_report", source=report["source"], items=report["items"])

        # 6.2 recon
        diff = github.get_diff(owner, repo, number)
        conventions = github.read_conventions(wd)
        hyps = recon.hypotheses(diff, report, conventions)
        damages = damage_for(hyps)
        for h, dmg in zip(hyps, damages):
            h["damage"] = dmg
            h["slug"] = recon.slug(h)
            emit("attacker_intro", hypothesis=h, damage=dmg)

        # 6.3 attack
        runner = get_runner(runner_name)
        try:
            runner.prepare(wd)
        except NotImplementedError:
            raise
        except Exception as exc:  # image build failed -> local (PRD 11)
            emit("error", stage="runner", message=f"{runner.name} prepare failed: {exc}")
            runner = get_runner("local")

        hp = STARTING_HP
        hits, misses = [], []
        for h in hyps:
            landed = _attack_one(emit, runner, wd, h)
            if landed:
                hp = max(0, hp - h["damage"])
                emit("hit", hypothesis_id=h["id"], damage=h["damage"], hp_after=hp)
                hits.append(h["id"])
            else:
                misses.append(h["id"])

        write_state(
            arena_id,
            {
                "pr": {**pr, "url": pr_url, "repo": f"{owner}/{repo}"},
                "hypotheses": hyps,
                "round1": {"hits": hits, "misses": misses, "hp": hp},
                "runner": runner.name,
            },
        )
        emit(
            "round_over",
            launched=len(hyps),
            landed=len(hits),
            missed=len(misses),
            hp=hp,
        )
        return 0
    except Exception as exc:
        emit("error", stage="attack", message=f"{type(exc).__name__}: {exc}")
        return 1


def _attack_one(emit, runner, wd, h):
    """One hypothesis: write the exploit, run it, return True if it landed."""
    rel_path = f"{EXPLOIT_DIR}/test_{h['slug']}.py"
    os.makedirs(os.path.join(wd, EXPLOIT_DIR), exist_ok=True)

    prompt = codex.load_prompt(
        "exploit",
        slug=h["slug"],
        claim=h["claim"],
        file=h["file"],
        line=h["line"],
        exploit_plan=h["exploit_plan"],
    )
    codex.exec(prompt, wd, kind="exploit")

    abs_path = os.path.join(wd, rel_path)
    if not os.path.exists(abs_path):
        emit("miss", hypothesis_id=h["id"], reason="no exploit produced")
        return False
    with open(abs_path, "r", encoding="utf-8", errors="replace") as fh:
        if "def test_" not in fh.read():
            emit("miss", hypothesis_id=h["id"], reason="no exploit produced")
            return False
    emit("exploit_written", hypothesis_id=h["id"], path=rel_path)

    if runner.name == "modal" and runner.last_boot_ms is not None:
        emit(
            "sandbox_up",
            hypothesis_id=h["id"],
            sandbox_id=runner.last_sandbox_id,
            boot_ms=runner.last_boot_ms,
        )

    code, lines = runner.run(wd, exploit_cmd(rel_path), timeout=DEFAULT_TIMEOUT)
    for line in lines:
        emit("test_output", hypothesis_id=h["id"], line=line)
    if code == 0:
        return True
    emit(
        "miss",
        hypothesis_id=h["id"],
        reason="timed out" if code == 124 else "exploit did not pass",
    )
    return False


# ---------------------------------------------------------------- stage 4..5


def run_fix(arena_id, runner_name=None):
    """Stages 4-5. Resumes from state.json, ends in final.

    Event order is the contract in PRD 15.2:
    fix_start, fix_diff, fix_result, blocked/still_landed per hypothesis, final.
    """
    emit = Emitter(arena_id, round_no=2)
    try:
        state = read_state(arena_id)
        wd = workdir_for(arena_id)
        hyps = state["hypotheses"]
        landed_r1 = [h["id"] for h in hyps if h["id"] in set(state["round1"]["hits"])]
        hp = state["round1"]["hp"]
        runner = get_runner(runner_name or state.get("runner", "local"))

        emit("fix_start")
        outcome = _fix_with_retry(emit, runner, wd)
        if outcome is None:
            # the fix broke the suite twice: Knocked out, diff shown, not hidden (6.4)
            return _finish(emit, hyps, landed_r1, hp, suite_passed=0, files_changed=0,
                           result="knocked_out", landed_r2=len(landed_r1))
        suite_passed, files = outcome

        # aggregate exploit run: failed == blocked, this is the "failed = blocked" beat
        _, lines = runner.run(wd, EXPLOITS_CMD, timeout=DEFAULT_TIMEOUT)
        exploit_lines = list(lines)
        for line in exploit_lines:
            emit("test_output", hypothesis_id=None, line=line)
        still, blocked, _ = _parse_pytest(exploit_lines)
        emit(
            "fix_result",
            suite_passed=suite_passed,
            suite_failed=0,
            exploits_blocked=blocked,
            exploits_still_landed=still,
        )

        # 6.5 rematch: re-run each exploit individually
        landed_r2 = []
        for h in hyps:
            if h["id"] not in landed_r1:
                continue
            rel_path = f"{EXPLOIT_DIR}/test_{h['slug']}.py"
            code, lines = runner.run(wd, exploit_cmd(rel_path), timeout=DEFAULT_TIMEOUT)
            for line in lines:
                emit("test_output", hypothesis_id=h["id"], line=line)
            if code == 0:
                landed_r2.append(h["id"])
                emit("still_landed", hypothesis_id=h["id"])
            else:
                hp = min(STARTING_HP, hp + h["damage"])
                emit("blocked", hypothesis_id=h["id"], hp_after=hp)

        return _finish(
            emit, hyps, landed_r1, hp,
            suite_passed=suite_passed,
            files_changed=len({f["path"] for f in files}),
            result="survived" if not landed_r2 else "knocked_out",
            landed_r2=len(landed_r2),
        )
    except Exception as exc:
        emit("error", stage="fix", message=f"{type(exc).__name__}: {exc}")
        return 1


def _fix_with_retry(emit, runner, wd, attempts=2):
    """codex exec, then the existing suite. One retry with the failing names (6.4)."""
    failing = []
    for _ in range(attempts):
        prompt = codex.load_prompt("fix")
        if failing:
            prompt += (
                f"\n\nThe previous attempt broke these tests: {', '.join(failing)}. "
                "Keep them passing."
            )
        out = codex.exec(prompt, wd, kind="fix")

        files = codex.parse_file_summaries(out["stdout"])
        if not files:
            files = [{"path": l, "summary": ""} for l in github.diff_stat(wd)]
        emit("fix_diff", files=files)

        code, lines = runner.run(wd, SUITE_CMD, timeout=DEFAULT_TIMEOUT)
        suite_lines = list(lines)
        for line in suite_lines:
            emit("test_output", hypothesis_id=None, line=line)
        passed, failed, failing = _parse_pytest(suite_lines)
        if failed == 0 and code == 0:
            return passed, files
        emit("fix_rejected", failing_tests=failing)
    return None


def _parse_pytest(lines):
    """(passed, failed, failing_test_names) from `pytest -q` output."""
    passed = failed = 0
    failing = []
    for line in lines:
        s = line.strip()
        if s.startswith("FAILED "):
            failing.append(s.split()[1])
        if " passed" in s or " failed" in s:
            for token, word in ((" passed", "passed"), (" failed", "failed")):
                if token in s:
                    chunk = s.split(word)[0].split()
                    if chunk and chunk[-1].isdigit():
                        if word == "passed":
                            passed = int(chunk[-1])
                        else:
                            failed = int(chunk[-1])
    return passed, failed, failing


def _finish(emit, hyps, landed_r1, hp, suite_passed, files_changed, result, landed_r2):
    emit(
        "final",
        launched=len(hyps),
        landed_r1=len(landed_r1),
        landed_r2=landed_r2,
        suite_passed=suite_passed,
        files_changed=files_changed,
        result=result,
        hp=hp,
    )
    return 0
