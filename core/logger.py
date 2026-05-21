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
