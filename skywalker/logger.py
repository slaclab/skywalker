#!/usr/bin/env python
# -*- coding: utf-8 -*-
import threading
import logging

from pydm.PyQt.QtCore import QPoint, pyqtSlot, pyqtSignal


class GuiHandler(logging.Handler):
    """
    Logging handler that logs to a scrolling text widget.
    """
    def __init__(self, text_widget, level=logging.NOTSET):
        super().__init__(level=level)
        self.log_writer = LogWriter(text_widget)
        self.log_signal = pyqtSignal(str)
        self.log_signal.connect(self.log_writer.write_log)
        self.lock = threading.RLock()

    def emit(self, record):
        with self.lock:
            if self.log_writer is not None:
                all_msg = self.format(record)
                self.log_signal.emit(all_msg)

    def close(self):
        with self.lock:
            self.log_writer.log_close()
            self.log_signal.disconnect()
            self.log_signal = None
            self.log_writer = None


class LogWriter(QObject):
    """
    QObject to do the writing
    """
    terminator = '\n'

    def __init__(self, text_widget):
        super().__init__(parent=text_widget)
        self.text_widget = text_widget

    @pyqtSlot(str)
    def write_log(self, all_msg):
        if self.text_widget is not None:
            split_msg = all_msg.split(self.terminator)
            for msg in reversed(split_msg):
                cursor = self.text_widget.cursorForPosition(QPoint(0, 0))
                cursor.insertText(msg + self.terminator)

    def log_close(self):
        self.text_widget = None
