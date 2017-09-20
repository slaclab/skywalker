#!/usr/bin/env python
# -*- coding: utf-8 -*-
import logging

from pydm.PyQt.QtGui import (QMainWindow,
                             QFormLayout, QHBoxLayout, QVBoxLayout,
                             QLabel, QLineEdit, QComboBox, QCheckBox,
                             QIntValidator, QDoubleValidator)

logger = logging.getLogger(__name__)


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
    NO_CONFIG = 0
    CHECK = 1
    LINE = 2
    COMBO = 4

    def __init__(self, name, default, required=True, enum=None):
        self.name = name
        self.data_type = type(default)
        self.config = self.NO_CONFIG

        if not required or default in (True, False):
            self.config += self.CHECK
        if default not in (True, False):
            if enum is None:
                self.config += self.LINE
            else:
                self.config += self.COMBO

        self.layout = QHBoxLayout()
        if self.config & self.CHECK:
            self.check = QCheckBox()
            self.layout.add(self.check)
        else:
            self.check = None
        if self.config == self.CHECK:
            self.check.setText('Enabled')
        if self.config & self.LINE:
            self.data = QLineEdit()
            if self.data_type == int:
                self.data.setValidator(QIntValidator)
            elif self.data_type == float:
                self.data.setValidator(QDoubleValidator)
        elif self.config & self.COMBO:
            self.data = QComboBox()
            for value in enum:
                self.data.addItem(str(value))
            if default is not None:
                pass  # TODO: pick correct default combo box item
        else:
            self.data = None

        if self.check is not None and self.data is not None:
            self.check.toggled.connect(self.data.setEnabled)
        if self.check is not None:
            if default in (None, False):
                self.check.setChecked(False)
            else:
                self.check.setChecked(True)

    @property
    def value(self):
        if self.config == self.CHECK:
            return self.check.isChecked()
        elif self.config & self.CHECK:
            if not self.check.isChecked():
                return None
        if self.config & self.LINE:
            raw = self.data.text()
        elif self.config & self.COMBO:
            raw = self.data.currentText()
        else:
            raw = None
        try:
            return self.data_type(raw)
        except Exception:
            return raw

    @value.setter
    def value(self, val):
        if self.config == self.CHECK:
            self.check.setChecked(bool(val))
            return
        elif self.config & self.CHECK and val is None:
            self.check.setChecked(False)
            return
        else:
            try:
                val = self.data_type(val)
            except Exception:
                logger.exception('Invalid data type')
                return
            finally:
                txt = str(val)
            if self.config & self.LINE:
                self.data.setText(txt)
            elif self.config & self.COMBO:
                index = self.enum.index(txt)
                self.data.setCurrentIndex(index)


class SettingsGroup:
    def __init__(self, collumns=None, **settings):
        """
        Parameters
        ----------
        collumns: list, optional
            List of lists of headers included in each collumn
            The list at index 0 will be the first collumn, etc.

        settings: kwargs
            Mapping of header to list of Setting objects
        """
        self.settings = {}
        self.window = QMainWindow()
        layout = QHBoxLayout()
        self.window.setLayout(layout)
        if collumns is None:
            collumns = [list(settings.keys())]
        for col in collumns:
            col_layout = QVBoxLayout()
            layout.addWidget(col_layout)
            for header in col:
                title = QLabel()
                title.setText(header.capitalize())
                col_layout.addWidget(title)
                form = QFormLayout()
                col_layout.addWidget(form)
                for setting in settings[header]:
                    self.settings[setting.name] = setting
                    label = QLabel()
                    label.setText(setting.name.capitalize())
                    form.addRow(label, setting.layout)

    @property
    def values(self):
        return {n: s.value for n, s in self.settings.items()}

    @values.setter
    def values(self, set_dict):
        for k, v in set_dict.items():
            if k in self.settings:
                self.settings[k].value = v

    def show(self):
        self.window.show()
