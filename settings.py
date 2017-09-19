#!/usr/bin/env python
# -*- coding: utf-8 -*-
from pydm.PyQt.QtGui import (QMainWindow, QFormLayout, QHBoxLayout,
                             QLineEdit, QComboBox, QCheckBox,
                             QIntValidator, QDoubleValidator)


class Setting:
    """
    Abstraction of a Single user input setting. Handles what the ui should look
    like for just this setting and keeps the input value and display values in
    sync.

    Widgets are held in the "layout" attribute.

    Supports several different kinds of configurations and associated values:
        -Just a checkbox:
            Can be True (checked) or False (unchecked)
            Chosen if default is a boolean
        -Just a line edit:
            Can be any value the same type as default
            Chosen if required=True and no enum provided
        -Just a combo box
            Can be any value in the enum argument
            Chosen if required=True and enum list provided
        -A checkbox and a line edit or combo box
            Chosen if required=False and default is non-boolean
            If the checkbox is unchecked, the value is None
    """
    CHECK = 1
    LINE = 2
    COMBO = 4

    def __init__(self, name, default, required=True, enum=None):
        self.name = name
        self.default = default
        self.required = required
        self.enum = enum
        self.layout = QHBoxLayout()
        self.data_type = type(default)

        if required:
            self.check = None
        elif not required or default is in (True, False):
            self.check = QCheckBox()
            self.layout.add(self.check)
        if default is not in (True, False):
            if enum is None:
                self.data = QLineEdit()
                if self.data_type == int:
                    self.data.setValidator(QIntValidator)
                elif self.data_type == float:
                    self.data.setValidator(QDoubleValidator)
            else:
                self.data = QComboBox()
                for value in enum:
                    self.data.addItem(str(value))
            self.layout.add(self.data)

    @property
    def value(self):
        if self.check is not None:
            if self.default is in (True, False):
                return self.check.isChecked()
            elif not self.check.isChecked():
                return None
        try:
            raw = self.data.text()
        except AttributeError:
            raw = self.data.currentText()
        try:
            return self.data_type(raw)
        except Exception:
            return raw

    @value.setter
    def value(self, val):
        if self.default is in (True, False):
            self.check.setChecked(bool(val))
            return
        elif not self.required:
            if val is None:
                self.check.setChecked(False)
                return
            else:
                self.check.setChecked(True)
        try:
            val = self.data_type(val)
        except Exception:
            pass
        finally:
            txt = str(val)
        try:
            self.data.setText(txt)
        except AttributeError:
            try:
                index = self.enum.index(val)
                self.data.setCurrentIndex(index)
            except Exception:
                pass


class SettingsGroup:
    def __init__(self, **kwargs):
        pass
