#!/usr/bin/env python3
"""Copy runs/<arena_id>/events.jsonl to demo/cached_run.jsonl (Appendix B).

M4: the cached run is what plays with the Wi-Fi off.
"""

import os
import shutil
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main(argv):
    if len(argv) < 2:
        print("usage: python scripts/make_cache.py <arena_id> [dest]", file=sys.stderr)
        return 2
    arena_id = argv[1]
    src = os.path.join(ROOT, "runs", arena_id, "events.jsonl")
    dest = argv[2] if len(argv) > 2 else os.path.join(ROOT, "demo", "cached_run.jsonl")
    if not os.path.exists(src):
        print(f"no such run: {src}", file=sys.stderr)
        return 1

    with open(src, "r", encoding="utf-8") as fh:
        lines = [l for l in fh if l.strip()]
    if not any('"final"' in l for l in lines):
        print("warning: this run has no final event -- replay will stop early", file=sys.stderr)

    os.makedirs(os.path.dirname(dest), exist_ok=True)
    shutil.copyfile(src, dest)
    print(f"cached {len(lines)} events -> {os.path.relpath(dest, ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
