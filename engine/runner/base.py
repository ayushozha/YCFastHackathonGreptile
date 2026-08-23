"""Runner.run(workdir, cmd) -> (exit_code, stdout_iter).

Two implementations behind RUNNER: local.py (subprocess) and modal_runner.py
(Modal Sandbox, PRD section 9). Callers stream the iterator as test_output
events, then read the exit code.
"""

import abc

DEFAULT_TIMEOUT = 120  # PRD 6.3: a timeout counts as a miss


class Runner(abc.ABC):
    name = "base"

    @abc.abstractmethod
    def run(self, workdir, cmd, timeout=DEFAULT_TIMEOUT):
        """Execute `cmd` in `workdir`. Returns (exit_code, iterable_of_stdout_lines).

        Implementations must stream: the iterator yields lines as the process
        produces them, and the exit code is only final once it is exhausted.
        """

    def prepare(self, workdir):
        """Optional per-arena setup (Modal builds its image here, once)."""
        return None


class TimeoutExpired(Exception):
    pass


def get_runner(name):
    if name == "modal":
        from engine.runner.modal_runner import ModalRunner

        return ModalRunner()
    from engine.runner.local import LocalRunner

    return LocalRunner()
