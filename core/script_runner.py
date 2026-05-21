"""Script execution utilities for running tcsh scripts"""
import subprocess
import os
from pathlib import Path
from typing import List, Dict, Optional, Callable
from PyQt6.QtCore import QObject, pyqtSignal, QThread


class ScriptRunnerSignals(QObject):
    """Signals for script runner"""
    output_line = pyqtSignal(str)  # Single line of output
    error_line = pyqtSignal(str)  # Single line of error
    finished = pyqtSignal(bool, int)  # success, return_code
    progress = pyqtSignal(int)  # Progress percentage (if available)


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
            self.process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=env,
                universal_newlines=True,
                bufsize=1
            )

            # Read output in real-time
            while True:
                if self._should_stop:
                    self.process.kill()
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
        """Stop the running process"""
        self._should_stop = True
        if self.process and self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()


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

            self.process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True,
                bufsize=1,
                cwd=self.proc_script_path.parent
            )

            # Read output in real-time
            while True:
                if self._should_stop:
                    self.process.kill()
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
        """Stop the running process"""
        self._should_stop = True
        if self.process and self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
