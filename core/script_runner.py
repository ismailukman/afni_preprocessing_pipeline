"""Script execution utilities for running tcsh scripts"""
import subprocess
import os
import signal
import time
from pathlib import Path
from typing import List, Dict, Optional, Callable
from PyQt6.QtCore import QObject, pyqtSignal, QThread


def _popen_in_new_pgroup(*args, **kwargs):
    """Spawn a subprocess in its own process group on POSIX.

    Putting each tcsh child in a new pgroup lets us kill its *entire* tree
    (recon-all, mri_ca_register, fs_time, tee, etc.) with one os.killpg
    instead of just terminating the direct child and leaving grandchildren
    orphaned.  On Windows we use CREATE_NEW_PROCESS_GROUP for the same effect.
    """
    if os.name == "posix":
        kwargs.setdefault("preexec_fn", os.setsid)
    else:
        creationflags = kwargs.get("creationflags", 0)
        kwargs["creationflags"] = creationflags | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    return subprocess.Popen(*args, **kwargs)


def _kill_process_tree(proc):
    """Best-effort kill of a Popen and every descendant in its group."""
    if proc is None or proc.poll() is not None:
        return
    try:
        if os.name == "posix":
            pgid = os.getpgid(proc.pid)
            os.killpg(pgid, signal.SIGTERM)
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                os.killpg(pgid, signal.SIGKILL)
        else:
            proc.send_signal(signal.CTRL_BREAK_EVENT)
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
    except (ProcessLookupError, PermissionError, OSError):
        try:
            proc.terminate()
            proc.wait(timeout=2)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass


class ScriptRunnerSignals(QObject):
    """Signals for script runner"""
    output_line = pyqtSignal(str)  # Single line of output
    error_line = pyqtSignal(str)  # Single line of error
    finished = pyqtSignal(bool, int)  # success, return_code
    progress = pyqtSignal(int)  # Progress percentage (if available)


class FileTailer(QThread):
    """Tail -f equivalent that emits each new line as a signal.

    Used to stream `recon-all.log` (or any other long-running tool's own log
    file) into the GUI while the launching process itself is mostly silent on
    stdout.  Waits for the file to appear before tailing, then seeks to end
    and polls for new lines.  Stop with ``.stop()``.
    """

    line_emitted = pyqtSignal(str)

    def __init__(self, path: Path, poll_interval: float = 0.5,
                 wait_timeout: float = 600.0, parent=None):
        super().__init__(parent)
        self.path = Path(path)
        self.poll_interval = poll_interval
        self.wait_timeout = wait_timeout    # seconds to wait for the file to appear
        self._should_stop = False

    def stop(self):
        self._should_stop = True

    def run(self):
        # Wait for the file to exist (recon-all takes a moment to create it)
        waited = 0.0
        while not self.path.exists():
            if self._should_stop:
                return
            time.sleep(self.poll_interval)
            waited += self.poll_interval
            if waited >= self.wait_timeout:
                return  # gave up waiting

        try:
            fh = open(self.path, "r", encoding="utf-8", errors="replace")
        except OSError:
            return

        try:
            fh.seek(0, 2)  # jump to end — only emit *new* content
            while not self._should_stop:
                line = fh.readline()
                if line:
                    # readline returns with trailing newline; strip for display
                    self.line_emitted.emit(line.rstrip("\n"))
                else:
                    time.sleep(self.poll_interval)
        finally:
            try:
                fh.close()
            except OSError:
                pass


class ScriptRunner(QThread):
    """Executes a tcsh script with real-time output capture"""

    def __init__(self, script_path: Path, args: List[str], env_vars: Optional[Dict[str, str]] = None):
        super().__init__()
        self.script_path = Path(script_path)
        self.args = args
        self.env_vars = env_vars or {}
        self.signals = ScriptRunnerSignals()
        self.process = None
        self._should_stop = False

    def run(self):
        """Execute the script in a separate thread"""
        try:
            # Build command
            cmd = ['tcsh', str(self.script_path)] + self.args

            # Set up environment
            env = os.environ.copy()
            env.update(self.env_vars)

            # Start process
            self.process = _popen_in_new_pgroup(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=env,
                universal_newlines=True,
                bufsize=1,
            )

            # Read output in real-time
            while True:
                if self._should_stop:
                    _kill_process_tree(self.process)
                    self.signals.finished.emit(False, -1)
                    return

                # Read stdout
                stdout_line = self.process.stdout.readline()
                if stdout_line:
                    line = stdout_line.strip()
                    self.signals.output_line.emit(line)

                # Read stderr
                stderr_line = self.process.stderr.readline()
                if stderr_line:
                    line = stderr_line.strip()
                    self.signals.error_line.emit(line)

                # Check if process has finished
                if stdout_line == '' and stderr_line == '' and self.process.poll() is not None:
                    break

            # Get return code
            return_code = self.process.wait()
            success = return_code == 0
            self.signals.finished.emit(success, return_code)

        except Exception as e:
            self.signals.error_line.emit(f"Exception running script: {str(e)}")
            self.signals.finished.emit(False, -1)

    def stop(self):
        """Stop the running process and ALL its descendants."""
        self._should_stop = True
        _kill_process_tree(self.process)


class DirectScriptRunner(QThread):
    """Executes a generated proc script directly"""

    def __init__(self, proc_script_path: Path):
        super().__init__()
        self.proc_script_path = Path(proc_script_path)
        self.signals = ScriptRunnerSignals()
        self.process = None
        self._should_stop = False

    def run(self):
        """Execute the proc script"""
        try:
            cmd = ['tcsh', '-xef', str(self.proc_script_path)]

            self.process = _popen_in_new_pgroup(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True,
                bufsize=1,
                cwd=self.proc_script_path.parent,
            )

            # Read output in real-time
            while True:
                if self._should_stop:
                    _kill_process_tree(self.process)
                    self.signals.finished.emit(False, -1)
                    return

                stdout_line = self.process.stdout.readline()
                if stdout_line:
                    line = stdout_line.strip()
                    self.signals.output_line.emit(line)

                stderr_line = self.process.stderr.readline()
                if stderr_line:
                    line = stderr_line.strip()
                    self.signals.error_line.emit(line)

                if stdout_line == '' and stderr_line == '' and self.process.poll() is not None:
                    break

            return_code = self.process.wait()
            success = return_code == 0
            self.signals.finished.emit(success, return_code)

        except Exception as e:
            self.signals.error_line.emit(f"Exception running proc script: {str(e)}")
            self.signals.finished.emit(False, -1)

    def stop(self):
        """Stop the running process and ALL its descendants."""
        self._should_stop = True
        _kill_process_tree(self.process)
