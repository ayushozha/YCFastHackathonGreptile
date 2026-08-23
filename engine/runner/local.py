"""Subprocess runner. The default, and the fallback whenever Modal is slow."""

import os
import shlex
import subprocess
import time

from engine.runner.base import DEFAULT_TIMEOUT, Runner


class LocalRunner(Runner):
    name = "local"

    def run(self, workdir, cmd, timeout=DEFAULT_TIMEOUT):
        args = shlex.split(cmd) if isinstance(cmd, str) else list(cmd)
        env = dict(os.environ, PYTHONUNBUFFERED="1")
        proc = subprocess.Popen(
            args,
            cwd=workdir,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
        lines = []
        deadline = time.monotonic() + timeout
        timed_out = False
        for line in proc.stdout:
            lines.append(line.rstrip("\n"))
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
        if timed_out:
            lines.append(f"[arena] timed out after {timeout}s")
            return 124, iter(lines)
        return proc.returncode, iter(lines)
