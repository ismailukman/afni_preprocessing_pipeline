"""Logging utilities for the AFNI preprocessing pipeline"""
import logging
import sys
from pathlib import Path
from datetime import datetime
from PyQt6.QtCore import QObject, pyqtSignal


class LogHandler(logging.Handler):
    """Custom logging handler that emits signals for GUI updates"""

    def __init__(self, signal_emitter):
        super().__init__()
        self.signal_emitter = signal_emitter

    def emit(self, record):
        msg = self.format(record)
        self.signal_emitter.log_message.emit(msg, record.levelname)


class LogSignals(QObject):
    """Signals for log messages"""
    log_message = pyqtSignal(str, str)  # message, level


class _TeeStream:
    """File-like wrapper that writes to a real stream AND emits each line
    via a Qt signal.  Used to mirror sys.stdout / sys.stderr into the GUI's
    Pipeline tab so the terminal and GUI show the same content.
    """

    def __init__(self, original, signal_emitter, level: str = "INFO"):
        self._original = original
        self._signals = signal_emitter
        self._level = level
        self._buffer = ""

    def write(self, data):
        if data:
            try:
                self._original.write(data)
            except Exception:
                pass
            self._buffer += data
            while "\n" in self._buffer:
                line, self._buffer = self._buffer.split("\n", 1)
                if line.strip():
                    try:
                        self._signals.log_message.emit(line, self._level)
                    except RuntimeError:
                        # signal target deleted (e.g. during shutdown)
                        pass
        return len(data) if data else 0

    def flush(self):
        try:
            self._original.flush()
        except Exception:
            pass
        if self._buffer.strip():
            try:
                self._signals.log_message.emit(self._buffer.rstrip("\n"), self._level)
            except RuntimeError:
                pass
        self._buffer = ""

    def isatty(self):
        try:
            return self._original.isatty()
        except Exception:
            return False

    def fileno(self):
        return self._original.fileno()


def install_stdout_stderr_capture(signals: "LogSignals"):
    """Tee sys.stdout/sys.stderr through the GUI signal emitter.

    Safe to call once at startup.  Returns the originals so they can be
    restored on shutdown if needed.
    """
    original_out, original_err = sys.stdout, sys.stderr
    sys.stdout = _TeeStream(original_out, signals, "INFO")
    sys.stderr = _TeeStream(original_err, signals, "ERROR")
    return original_out, original_err


class PipelineLogger:
    """Logger for pipeline operations"""

    def __init__(self, log_dir=None):
        self.signals = LogSignals()
        self.log_dir = Path(log_dir) if log_dir else Path.home() / ".afni_gui_preprocessing" / "logs"
        self.log_dir.mkdir(parents=True, exist_ok=True)

        # Create logger
        self.logger = logging.getLogger("AFNIPipeline")
        self.logger.setLevel(logging.DEBUG)

        # Remove existing handlers
        self.logger.handlers = []

        # Console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        console_formatter = logging.Formatter(
            '%(asctime)s - %(levelname)s - %(message)s',
            datefmt='%H:%M:%S'
        )
        console_handler.setFormatter(console_formatter)
        self.logger.addHandler(console_handler)

        # File handler
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file = self.log_dir / f"pipeline_{timestamp}.log"
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(logging.DEBUG)
        file_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        file_handler.setFormatter(file_formatter)
        self.logger.addHandler(file_handler)

        # GUI handler
        gui_handler = LogHandler(self.signals)
        gui_handler.setLevel(logging.INFO)
        gui_formatter = logging.Formatter('[%(asctime)s] %(message)s', datefmt='%H:%M:%S')
        gui_handler.setFormatter(gui_formatter)
        self.logger.addHandler(gui_handler)

    def debug(self, msg):
        self.logger.debug(msg)

    def info(self, msg):
        self.logger.info(msg)

    def warning(self, msg):
        self.logger.warning(msg)

    def error(self, msg):
        self.logger.error(msg)

    def critical(self, msg):
        self.logger.critical(msg)

    def get_log_file(self):
        """Get the current log file path"""
        for handler in self.logger.handlers:
            if isinstance(handler, logging.FileHandler):
                return handler.baseFilename
        return None
