"""subprocess wrapper for `codex exec` (PRD section 9 + rule 0.1).

Rule 0.1: every runtime codex invocation is logged to logs/codex_calls.jsonl
with prompt, exit code and duration. Acceptance criterion in section 12 greps
this file for one exploit call per hypothesis and one fix call per run.

Flags below were read off `codex exec --help` on the build machine, not guessed
(codex-cli 0.149.0). Re-check them if the CLI is upgraded before the hack.
"""

import json
import os
import subprocess
import tempfile
import time

LOG_PATH = os.environ.get("CODEX_LOG", "logs/codex_calls.jsonl")
TIMEOUT_S = 180  # PRD 9
CODEX_BIN = os.environ.get("CODEX_BIN", "codex")

# `codex exec` is already non-interactive; workspace-write is what gives it
# permission to create tests/exploits/ and edit app/ inside the clone. Plain
# stdout (no --json) keeps the battle log verbatim and readable.
DEFAULT_FLAGS = ["--sandbox", "workspace-write", "--color", "never"]
CODEX_FLAGS = os.environ.get("CODEX_FLAGS", "").split() or DEFAULT_FLAGS

# Recon only reads; it must not be able to touch the clone.
READONLY_FLAGS = ["--sandbox", "read-only", "--color", "never", "--skip-git-repo-check"]


def _log(record):
    os.makedirs(os.path.dirname(LOG_PATH) or ".", exist_ok=True)
    with open(LOG_PATH, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False) + "\n")
        fh.flush()


def exec(prompt, workdir, kind="exploit", timeout=TIMEOUT_S, on_line=None,
         extra_flags=None, output_schema=None):
    """Run `codex exec` non-interactively with write access to workdir.

    Returns {"exit_code", "stdout", "last_message", "duration_ms", "timed_out"}.
    `on_line` is called with each stdout line so the caller can stream it.

    `--output-last-message` gives us the agent's final message on its own,
    which is what the fix prompt (A.3) asks to be one line per changed file.
    """
    last_fd, last_path = tempfile.mkstemp(prefix="codex_last_", suffix=".txt")
    os.close(last_fd)
    schema_path = None
    flags = list(extra_flags) if extra_flags else list(CODEX_FLAGS)
    if output_schema is not None:
        schema_fd, schema_path = tempfile.mkstemp(prefix="codex_schema_", suffix=".json")
        with os.fdopen(schema_fd, "w", encoding="utf-8") as fh:
            json.dump(output_schema, fh)
        flags += ["--output-schema", schema_path]
    cmd = [CODEX_BIN, "exec", *flags, "--output-last-message", last_path, prompt]
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
    try:
        with open(last_path, "r", encoding="utf-8", errors="replace") as fh:
            last_message = fh.read()
    except OSError:
        last_message = ""
    finally:
        for path in (last_path, schema_path):
            if path:
                try:
                    os.unlink(path)
                except OSError:
                    pass
    _log(
        {
            "kind": kind,
            "cwd": workdir,
            "prompt": prompt,
            "exit_code": exit_code,
            "duration_ms": duration_ms,
            "timed_out": timed_out,
            "stdout_tail": stdout[-2000:],
            "last_message": last_message[-2000:],
        }
    )
    return {
        "exit_code": exit_code,
        "stdout": stdout,
        "last_message": last_message,
        "duration_ms": duration_ms,
        "timed_out": timed_out,
    }


def parse_file_summaries(text):
    """Fix prompt (A.3) asks for one line per changed file: `<path>  <summary>`.

    Pass the agent's last message when you have it; the whole stdout works too.
    Returns [{"path", "summary"}]; the orchestrator falls back to `git diff
    --stat` lines when this comes back empty (PRD 6.4).
    """
    files = []
    for raw in (text or "").splitlines():
        line = raw.strip()
        if not line or line.startswith(("#", "$", ">")):
            continue
        parts = line.split(None, 1)
        if len(parts) != 2:
            continue
        path, summary = parts
        path = path.rstrip(":")
        if _looks_like_a_path(path):
            files.append({"path": path, "summary": summary.strip()})
    return files


SOURCE_SUFFIXES = (
    ".py", ".js", ".ts", ".tsx", ".jsx", ".go", ".rb", ".rs", ".java", ".php",
    ".sql", ".html", ".css", ".toml", ".cfg", ".ini", ".json", ".yaml", ".yml",
)


def _looks_like_a_path(token):
    """A top-level `main.py` is as valid a changed file as `app/refunds.py`."""
    if token.endswith(":"):
        token = token[:-1]
    if token.endswith(SOURCE_SUFFIXES):
        return True
    return "/" in token and "." in token.rsplit("/", 1)[-1]


def load_prompt(name, **fields):
    """prompts/<name>.txt rendered with str.format (A.2, A.3)."""
    path = os.path.join("prompts", f"{name}.txt")
    with open(path, "r", encoding="utf-8") as fh:
        template = fh.read()
    return template.format(**fields) if fields else template
