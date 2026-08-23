"""Modal Sandbox runner (PRD section 9). Behind RUNNER=modal; stretch for A.

Shape, per the PRD -- confirm every signature against the current Modal docs
before wiring this up, do not guess:

    image = modal.Image.debian_slim(python_version="3.11") \
        .pip_install_from_requirements(f"{workdir}/requirements.txt") \
        .add_local_dir(workdir, "/repo")
    sb = modal.Sandbox.create(app=app, image=image, timeout=120)
    p = sb.exec("bash", "-lc", cmd, workdir="/repo")
    for line in p.stdout: ...
    p.wait() -> exit code

Rules:
  * build the image ONCE per arena in prepare(), not per attack
  * record boot time so the orchestrator can emit sandbox_up {boot_ms}
  * if the first image build exceeds 90 s, the caller falls back to
    RUNNER=local and the ticker says "Running locally" (PRD 11)
"""

import time

from engine.runner.base import DEFAULT_TIMEOUT, Runner

IMAGE_BUILD_BUDGET_S = 90


class ModalRunner(Runner):
    name = "modal"

    def __init__(self):
        self._image = None
        self._app = None
        self.last_boot_ms = None
        self.last_sandbox_id = None

    def prepare(self, workdir):
        raise NotImplementedError(
            "engine/runner/modal_runner.py: build the image once per arena. "
            "Confirm the Sandbox API against the Modal docs first (PRD 9)."
        )

    def run(self, workdir, cmd, timeout=DEFAULT_TIMEOUT):
        started = time.monotonic()
        raise NotImplementedError(
            "engine/runner/modal_runner.py: create the sandbox, exec, stream "
            "stdout, return (exit_code, lines). Set self.last_boot_ms / "
            "self.last_sandbox_id so the orchestrator can emit sandbox_up."
        )
