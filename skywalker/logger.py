#!/usr/bin/env python
# -*- coding: utf-8 -*-
import logging

from pydm.PyQt.QtCore import QPoint


class GuiHandler(logging.Handler):
    """
    Logging handler that logs to a scrolling text widget.
    """
    terminator = '\n'

    def __init__(self, text_widget, level=logging.NOTSET):
        super().__init__(level=level)
        self.text_widget = text_widget

    def emit(self, record):
        if self.text_widget is not None:
            try:
                all_msg = self.format(record)
                split_msg = all_msg.split(self.terminator)
                for msg in reversed(split_msg):
                    cursor = self.text_widget.cursorForPosition(QPoint(0, 0))
                    cursor.insertText(msg + self.terminator)
            except Exception:
                self.handleError(record)

    def close(self):
        self.text_widget = None
