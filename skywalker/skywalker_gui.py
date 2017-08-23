#!/usr/bin/env python
# -*- coding: utf-8 -*-
from os import path
from math import sin, cos, pi

from pswalker.config import homs_system

from pydm import Display
from pydm.PyQt.QtCore import pyqtSlot, QCoreApplication
from pydm.PyQt.QtGui import QDoubleValidator

MAX_MIRRORS = 4

config = homs_system()

system = dict(
    m1h=dict(mirror=config['m1h'],
             imager=config['hx2'],
             slits=config['hx2_slits'],
             rotation=90),
    m2h=dict(mirror=config['m2h'],
             imager=config['dg3'],
             slits=config['dg3_slits'],
             rotation=90),
    mfx=dict(mirror=config['xrtm2'],
             imager=config['mfxdg1'],
             slits=config['mfxdg1_slits'],
             rotation=90)
)

alignments = {'HOMS': [['m1h', 'm2h']],
              'MFX': [['mfx']],
              'HOMS + MFX': [['m1h', 'm2h'], ['mfx']]}


class SkywalkerGui(Display):
    def __init__(self, system=system, alignments=alignments, parent=None,
                 args=None):
        """
        Parameters
        ----------
        system: dict
            Nested dictionary that maps strings to associated dictionaries of
            objects. Each inner dictionary must have a 'mirror' key that maps
            to a mirror object and an 'imager' key that maps to an areadetector
            pim. There may also be an optional 'rotation' key that specifies a
            counterclockwise rotation of the image and centroid in degrees,
            and an optional 'slits' key that maps to an aligned slits object.
            These objects are expected to follow the conventions of the
            pcds-devices module.
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
        self.beam_x_stats = None
        self.imager = None

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
        self.select_system_entry(system_key)

        # When we change the procedure, reinitialize the control portions
        procedure_changed = self.ui.procedure_combo.activated[str]
        procedure_changed.connect(self.select_procedure)

        # When we change the active imager, swap just the imager
        imager_changed = self.ui.image_title_combo.activated[str]
        imager_changed.connect(self.select_imager)

        # When we change the goals, update the deltas
        for goal_value in self.get_widget_set('goal_value'):
            goal_changed = goal_value.editingFinished
            goal_changed.connect(self.update_beam_delta)

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

    @property
    def slits(self):
        return [self.system[act].get('slits') for act in self.active_system]

    @property
    def goals(self):
        vals = []
        for line_edit in self.get_widget_set('goal_value'):
            goal = line_edit.text()
            try:
                goal = float(goal)
            except:
                goal = None
            vals.append(goal)
        return vals

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
        return self.none_pad(self.slits)

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
        for (mirr, img, slit, glabel, gedit, scheck,
             mlabel, mcircle, mrbv, mset) in my_zip:
            # Cache goal values and clear
            old_goal = str(gedit.text())
            if len(old_goal) > 0:
                self.goal_cache[str(glabel.text())] = float(old_goal)
            gedit.clear()

            # Reset all checkboxes and kill pv connections
            scheck.setChecked(False)
            clear_pydm_connection(mcircle)
            clear_pydm_connection(mrbv)
            clear_pydm_connection(mset)

            # If no imager, we hide the unneeded widgets
            if img is None:
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
                glabel.clear()
                glabel.setText(img.name)
                mlabel.setText(mirr.name)
                if slit is None:
                    scheck.hide()
                else:
                    scheck.setText(slit.name)
                    scheck.show()

                # Set up input validation and check cache for value
                # TODO different range for different imager
                gedit.setValidator(QDoubleValidator(0., 1000., 3))
                cached_goal = self.goal_cache.get(img.name)
                if cached_goal is None:
                    gedit.clear()
                else:
                    gedit.setText(str(cached_goal))

                # Connect mirror PVs
                mcircle.channel = 'ca://' + mirr.pitch.motor_done_move.pvname
                # mrbv.channel = 'ca://' + mirr.pitch.user_readback.pvname
                mrbv.setChannel('ca://' + mirr.pitch.user_readback.pvname)
                mset.channel = 'ca://' + mirr.pitch.user_setpoint.pvname

                create_pydm_connection(mcircle)
                create_pydm_connection(mrbv)
                create_pydm_connection(mset)

                # Make sure things are visible
                glabel.show()
                gedit.show()
                mlabel.show()
                mcircle.show()
                mrbv.show()
                mset.show()
        # If we already had set up an imager, update beam delta with new goals
        if self.imager is not None:
            self.update_beam_delta()

    def get_widget_set(self, name, num=MAX_MIRRORS):
        widgets = []
        for n in range(1, num + 1):
            widget = getattr(self.ui, name + "_" + str(n))
            widgets.append(widget)
        return widgets

    @pyqtSlot(str)
    def select_imager(self, imager_name):
        for k, v in self.system.items():
            if imager_name == v['imager'].name:
                return self.select_system_entry(k)

    @pyqtSlot(str)
    def select_system_entry(self, system_key):
        """
        Change on-screen information and displayed image to correspond to the
        selected mirror-imager-slit trio.
        """
        system_entry = self.system[system_key]
        imager = system_entry['imager']
        slits = system_entry.get('slits')
        rotation = system_entry.get('rotation', 0)
        self.imager = imager
        self.slit = slits
        self.rotation = rotation
        try:
            self.procedure_index = self.imagers.index(imager)
        except ValueError:
            # This means we picked an imager not in this procedure
            # This is allowed, but it means there is no goal delta!
            self.procedure_index = None

        # Make sure the combobox matches the image
        index = self.all_imager_names.index(imager.name)
        self.ui.image_title_combo.setCurrentIndex(index)
        self.ui.readback_imager_title.setText(imager.name)

        # Some cleanup
        if self.beam_x_stats is not None:
            self.beam_x_stats.clear_sub(self.update_beam_pos)

        # Set up the imager
        self.initialize_image(imager)

        # Centroid stuff
        stats2 = imager.detector.stats2
        self.beam_x_stats = stats2.centroid.x
        self.beam_y_stats = stats2.centroid.y

        self.beam_x_stats.subscribe(self.update_beam_pos)

        # Slits stuff
        self.ui.readback_slits_title.clear()
        slit_x_widget = self.ui.slit_x_width
        slit_y_widget = self.ui.slit_y_width
        clear_pydm_connection(slit_x_widget)
        clear_pydm_connection(slit_y_widget)
        if slits is not None:
            slit_x_name = slits.xwidth.readback.pvname
            slit_y_name = slits.ywidth.readback.pvname
            self.ui.readback_slits_title.setText(slits.name)
            # slit_x_widget.channel = 'ca://' + slit_x_name
            slit_x_widget.setChannel('ca://' + slit_x_name)
            # slit_y_widget.channel = 'ca://' + slit_y_name
            slit_y_widget.setChannel('ca://' + slit_y_name)
            create_pydm_connection(slit_x_widget)
            create_pydm_connection(slit_y_widget)

    def initialize_image(self, imager):
        # Disconnect image PVs
        clear_pydm_connection(self.ui.image)
        self.ui.image.resetImageChannel()
        self.ui.image.resetWidthChannel()

        # Handle rotation
        self.ui.image.getImageItem().setRotation(self.rotation)
        size_x = imager.detector.cam.array_size.array_size_x.value
        size_y = imager.detector.cam.array_size.array_size_y.value
        pix_x, pix_y = rotate(size_x, size_y, self.rotation)
        self.pix_x = int(round(abs(pix_x)))
        self.pix_y = int(round(abs(pix_y)))

        # Connect image PVs
        image2 = imager.detector.image2
        self.ui.image.setWidthChannel('ca://' + image2.width.pvname)
        self.ui.image.setImageChannel('ca://' + image2.array_data.pvname)
        create_pydm_connection(self.ui.image)

        # TODO figure out how image sizing really works
        self.ui.image.resize(self.pix_x, self.pix_y)

    @pyqtSlot()
    def update_beam_pos(self, *args, **kwargs):
        centroid_x = self.beam_x_stats.value
        centroid_y = self.beam_y_stats.value

        rotation = -self.rotation
        xpos, ypos = rotate(centroid_x, centroid_y, rotation)

        if xpos < 0:
            xpos += self.pix_x
        if ypos < 0:
            ypos += self.pix_y

        self.xpos = xpos
        self.ypos = ypos

        self.ui.beam_x_value.setText(str(xpos))
        self.ui.beam_y_value.setText(str(ypos))

        self.update_beam_delta()

    @pyqtSlot()
    def update_beam_delta(self, *args, **kwargs):
        if self.procedure_index is None:
            self.ui.beam_x_delta.clear()
        else:
            goal = self.goals[self.procedure_index]
            if goal is None:
                self.ui.beam_x_delta.clear()
            else:
                self.ui.beam_x_delta.setText(str(self.xpos - goal))
        # No y delta yet, there isn't a y goal pos!
        self.ui.beam_y_delta.clear()

    def ui_filename(self):
        return 'skywalker_gui.ui'

    def ui_filepath(self):
        return path.join(path.dirname(path.realpath(__file__)),
                         self.ui_filename())


def clear_pydm_connection(widget):
    QApp = QCoreApplication.instance()
    QApp.close_widget_connections(widget)
    widget._channels = None


def create_pydm_connection(widget):
    QApp = QCoreApplication.instance()
    QApp.establish_widget_connections(widget)


def to_rad(deg):
    return deg*pi/180


def sind(deg):
    return sin(to_rad(deg))


def cosd(deg):
    return cos(to_rad(deg))


def rotate(x, y, deg):
    x2 = x * cosd(deg) - y * sind(deg)
    y2 = x * sind(deg) + y * cosd(deg)
    return (x2, y2)

intelclass = SkywalkerGui # NOQA
