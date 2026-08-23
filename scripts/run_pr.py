#!/usr/bin/env python3
"""Engine CLI. The only interface between the two halves -- frozen at M0.

    python scripts/run_pr.py <pr_url> --arena-id <id> [--runner local|modal] [--scout app|api|none]
        Stages 0-3, stops after round_over. Exit 0 on round_over, 1 on error.

    python scripts/run_pr.py --arena-id <id> --fix-only
        Stages 4-5 from runs/<id>/state.json, ends in final.

    python scripts/run_pr.py <pr_url> --arena-id <id> --fix
        Both in one process (A's M2 proof; B never calls this form).

See PRD.md Appendix C.
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

from engine import orchestrator  # noqa: E402


def main(argv=None):
    p = argparse.ArgumentParser(prog="run_pr.py", description=__doc__)
    p.add_argument("pr_url", nargs="?", help="https://github.com/<owner>/<repo>/pull/<n>")
    p.add_argument("--arena-id", required=True)
    p.add_argument("--runner", choices=["local", "modal"], default=os.environ.get("RUNNER", "local"))
    p.add_argument("--scout", choices=["app", "api", "none"], default=os.environ.get("SCOUT", "app"))
    p.add_argument("--fix", action="store_true", help="attack round, then fix and rematch")
    p.add_argument("--fix-only", action="store_true", help="resume stages 4-5 from state.json")
    args = p.parse_args(argv)

    if args.fix_only:
        if args.pr_url:
            p.error("--fix-only resumes from state.json; do not pass a pr_url")
        return orchestrator.run_fix(args.arena_id, runner_name=args.runner)

    if not args.pr_url:
        p.error("pr_url is required unless --fix-only")

    code = orchestrator.run_attack(
        args.pr_url, args.arena_id, runner_name=args.runner, scout_source=args.scout
    )
    if code != 0 or not args.fix:
        return code
    return orchestrator.run_fix(args.arena_id, runner_name=args.runner)


if __name__ == "__main__":
    sys.exit(main())
