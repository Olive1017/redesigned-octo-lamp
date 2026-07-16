import logging
from PySide6.QtCore import QObject, Signal


class _Signals(QObject):
    日志信号 = Signal(str)


class QtLogHandler(logging.Handler):
    """A logging.Handler that emits log records to a Qt signal for thread-safe UI appending.

    Usage: create an instance and add it to the root logger. The handler will emit
    `signals.日志信号` with the formatted record string. Connect that signal to a
    slot in the main thread which updates a QPlainTextEdit.
    """

    def __init__(self, level=logging.NOTSET):
        super().__init__(level)
        self.signals = _Signals()

    def emit(self, record: logging.LogRecord) -> None:
        try:
            msg = self.format(record)
        except Exception:
            msg = record.getMessage()
        # Emit via Qt signal so main thread can update the UI
        try:
            self.signals.日志信号.emit(msg)
        except Exception:
            # Swallow errors to avoid crashing logging path
            pass
