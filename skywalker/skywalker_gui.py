#!/usr/bin/env python
# -*- coding: utf-8 -*-
from os import path
from pydm import Display
from pydm.PyQt.QtCore import pyqtSlot
from pydm.PyQt.QtGui import QDoubleValidator

MAX_MIRRORS = 4


class SkywalkerGui(Display):
    def __init__(self, system, alignments, parent=None, args=None):
        """
        Parameters
        ----------
        system: dict
            Nested dictionary that maps strings to associated dictionaries of
            objects. Each inner dictionary must have a 'mirror' key that maps
            to a mirror object and an 'imager' key that maps to an areadetector
            pim. There may also be an optional 'rotation' key that specifies a
            clockwise rotation of the image and centroid in degrees, and an
            optional 'slits' key that maps to an aligned slits object. These
            objects are expected to follow the conventions of the pcds-devices
            module.
            For example, a valid system entry might be:
                {'m1h': {'mirror': m1h, 'imager': hx2,
                         'rotation': -90, 'slits': hx2_slits}}

        alignments: dict
            Mapping of alignment procedure name to a list of lists of keys from
            system, where the innermost lists are associated with skywalker
            inputs.
            For example, a valid alignments entry might be:
                {'HOMS + MFX': [['m1h', 'm2h'], ['m2mfx']]}
        """
        super().__init__(parent=parent, args=args)
        self.system = system
        self.alignments = alignments

        self.goal_cache = {}

        # Populate image title combo box
        self.ui.image_title_combo.clear()
        self.all_imager_names = [entry['imager'].name for
                                 entry in system.values()]
        for imager_name in self.all_imager_names:
            self.ui.image_title_combo.addItem(imager_name)

        # Populate procedures combo box
        self.ui.procedure_combo.clear()
        for align in alignments.keys():
            self.ui.procedure_combo.addItem(align)

        # Initialize the screen with whatever the first procedure is
        self.select_procedure(self.ui.procedure_combo.currentText())

        # Initialize the screen with the first camera in the first procedure
        system_key = alignments[self.procedure][0][0]
        self.select_imager(system_key)

        # When we change the procedure, reinitialize the control portions
        procedure_changed = self.ui.procedure_combo.activated[str]
        procedure_changed.connect(self.select_procedure)

        # When we change the active imager, swap just the imager
        imager_changed = self.ui.image_title_combo.activated[str]
        imager_changed.connect(self.select_imager)

    @property
    def active_system(self):
        active_system = []
        for part in self.alignments[self.procedure]:
            active_system.extend(part)
        return active_system

    @property
    def mirrors(self):
        return [self.system[act]['mirror'] for act in self.active_system]

    @property
    def imagers(self):
        return [self.system[act]['imager'] for act in self.active_system]

    def none_pad(self, obj_list):
        padded = []
        padded.extend(obj_list)
        while len(padded) < MAX_MIRRORS:
            padded.append(None)
        return padded

    @property
    def mirrors_padded(self):
        return self.none_pad(self.mirrors)

    @property
    def imagers_padded(self):
        return self.none_pad(self.imagers)

    @property
    def slits_padded(self):
        # TODO get slits that correspond with imagers or are None when no slit
        raise NotImplementedError

    @pyqtSlot(str)
    def select_procedure(self, procedure):
        """
        Change on-screen labels and pv connections to match the current
        procedure.
        """
        # Set the procedure member that will be used elsewhere
        self.procedure = procedure

        # Set text, pvs in the Goals and Mirrors areas
        goal_labels = self.get_widget_set('goal_name')
        goal_line_edits = self.get_widget_set('goal_value')
        slit_checkboxes = self.get_widget_set('slit_check')
        mirror_labels = self.get_widget_set('mirror_name')
        mirror_circles = self.get_widget_set('mirror_circle')
        mirror_rbvs = self.get_widget_set('mirror_readback')
        mirror_sets = self.get_widget_set('mirror_setpos')

        my_zip = zip(self.mirrors_padded,
                     self.imagers_padded,
                     self.slits_padded,
                     goal_labels,
                     goal_line_edits,
                     slit_checkboxes,
                     mirror_labels,
                     mirror_circles,
                     mirror_rbvs,
                     mirror_sets)
        for mirr, img, slit, glabel, gedit, scheck, mlabel, mcircle, mrbv, mset in my_zip:
            # Cache goal values and clear
            old_goal = str(gedit.text())
            if len(old_goal) > 0:
                self.goal_cache[str(glabel.text())] = float(old_goal)
            gedit.clear()

            # If no imager, we hide/dc the unneeded widgets
            if img is None:
                mcircle.channel = ''
                mrbv.channel = ''
                mset.channel = ''

                glabel.hide()
                gedit.hide()
                scheck.hide()
                mlabel.hide()
                mcircle.hide()
                mrbv.hide()
                mset.hide()

            # Otherwise, make sure the widgets are visible and set parameters
            else:
                # Basic labels for goals, mirrors, and slits
                glabel.setText(img.name)
                mlabel.setText(mirr.name)
                if slit is None:
                    scheck.clear()
                    scheck.hide()
                else:
                    scheck.setText(slit.name)
                    scheck.show()

                # Set up input validation and check cache for value
                # TODO different range for different imager
                gedit.setValidator(QDoubleValidator(0., 480., 3))
                cached_goal = self.goal_cache.get(img.name)
                if cached_goal is not None:
                    gedit.setText(str(cached_goal))

                # Connect mirror PVs
                mcircle.channel = 'ca://' + mirr.pitch.motor_done_move.pvname
                mrbv.channel = 'ca://' + mirr.pitch.user_readback.pvname
                mset.channel = 'ca://' + mirr.pitch.user_setpoint.pvname

                # Make sure things are visible
                glabel.show()
                gedit.show()
                mlabel.show()
                mcircle.show()
                mrbv.show()
                mset.show()

    def get_widget_set(self, name, num=MAX_MIRRORS):
        widgets = []
        for n in range(1, num + 1):
            widget = getattr(self.ui, name + "_" + str(n))
            widgets.append(widget)
        return widgets

    @pyqtSlot(str)
    def select_imager(self, system_key):
        """
        Change on-screen information and displayed image to correspond to the
        selected mirror-imager-slit trio.
        """
        system_entry = self.system[system_key]
        imager = system_entry['imager']

        # Make sure the combobox matches the image
        index = self.all_imager_names.index(imager.name)
        self.ui.image_title_combo.setCurrentIndex(index)

    def ui_filename(self):
        return 'skywalker_gui.ui'

    def ui_filepath(self):
        return path.join(path.dirname(path.realpath(__file__)),
                         self.ui_filename())

intelclass = SkywalkerGui # NOQA
