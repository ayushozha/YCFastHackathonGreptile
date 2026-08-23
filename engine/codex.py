"""subprocess wrapper for `codex exec` (PRD section 9 + rule 0.1).

Rule 0.1: every runtime codex invocation is logged to logs/codex_calls.jsonl
with prompt, exit code and duration. Acceptance criterion in section 12 greps
this file for one exploit call per hypothesis and one fix call per run.

TODO at 1:00 pm: run `codex --version` and `codex exec --help` on the build
machine and set CODEX_FLAGS. Sandbox/approval flag names differ by version --
do not guess them.
"""

import json
import os
import subprocess
import time

LOG_PATH = os.environ.get("CODEX_LOG", "logs/codex_calls.jsonl")
TIMEOUT_S = 180  # PRD 9
CODEX_BIN = os.environ.get("CODEX_BIN", "codex")

# Verified against `codex exec --help` at 1:00 pm. Keep it minimal.
CODEX_FLAGS = os.environ.get("CODEX_FLAGS", "").split()


def _log(record):
    os.makedirs(os.path.dirname(LOG_PATH) or ".", exist_ok=True)
    with open(LOG_PATH, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False) + "\n")
        fh.flush()


def exec(prompt, workdir, kind="exploit", timeout=TIMEOUT_S, on_line=None):
    """Run `codex exec` non-interactively with write access to workdir.

    Returns {"exit_code", "stdout", "duration_ms", "timed_out"}.
    `on_line` is called with each stdout line so the caller can stream it.
    """
    cmd = [CODEX_BIN, "exec", *CODEX_FLAGS, prompt]
    started = time.monotonic()
    timed_out = False
    lines = []
    try:
        proc = subprocess.Popen(
            cmd,
            cwd=workdir,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            env=dict(os.environ, PYTHONUNBUFFERED="1"),
        )
    except FileNotFoundError as exc:
        record = {
            "kind": kind,
            "prompt": prompt,
            "exit_code": 127,
            "duration_ms": 0,
            "error": str(exc),
        }
        _log(record)
        raise

    deadline = started + timeout
    for line in proc.stdout:
        line = line.rstrip("\n")
        lines.append(line)
        if on_line:
            on_line(line)
        if time.monotonic() > deadline:
            timed_out = True
            proc.kill()
            break
    try:
        proc.wait(timeout=max(1, deadline - time.monotonic()))
    except subprocess.TimeoutExpired:
        timed_out = True
        proc.kill()
        proc.wait()

    duration_ms = int((time.monotonic() - started) * 1000)
    exit_code = 124 if timed_out else proc.returncode
    stdout = "\n".join(lines)
    _log(
        {
            "kind": kind,
            "cwd": workdir,
            "prompt": prompt,
            "exit_code": exit_code,
            "duration_ms": duration_ms,
            "timed_out": timed_out,
            "stdout_tail": stdout[-2000:],
        }
    )
    return {
        "exit_code": exit_code,
        "stdout": stdout,
        "duration_ms": duration_ms,
        "timed_out": timed_out,
    }


def parse_file_summaries(stdout):
    """Fix prompt (A.3) asks for one line per changed file: `<path>  <summary>`.

    Returns [{"path", "summary"}]; the orchestrator falls back to `git diff
    --stat` lines when this comes back empty (PRD 6.4).
    """
    files = []
    for raw in stdout.splitlines():
        line = raw.strip()
        if not line or line.startswith(("#", "$", ">")):
            continue
        parts = line.split(None, 1)
        if len(parts) != 2:
            continue
        path, summary = parts
        if "/" in path and path.endswith((".py", ".js", ".ts", ".go", ".rb")):
            files.append({"path": path, "summary": summary.strip()})
    return files


def load_prompt(name, **fields):
    """prompts/<name>.txt rendered with str.format (A.2, A.3)."""
    path = os.path.join("prompts", f"{name}.txt")
    with open(path, "r", encoding="utf-8") as fh:
        template = fh.read()
    return template.format(**fields) if fields else template
