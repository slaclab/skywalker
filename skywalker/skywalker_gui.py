#!/usr/bin/env python
# -*- coding: utf-8 -*-
import logging
from os import path
from math import sin, cos, pi
from functools import partial
from threading import RLock

from bluesky import RunEngine
from bluesky.utils import install_qt_kicker

from pydm import Display
from pydm.PyQt.QtCore import pyqtSlot, QCoreApplication, QPoint
from pydm.PyQt.QtGui import QDoubleValidator, QScrollArea

from pcdsdevices import sim
from pswalker.examples import patch_pims

from pswalker.config import homs_system
from pswalker.plan_stubs import slit_scan_fiducialize
from pswalker.skywalker import lcls_RE, skywalker

logger = logging.getLogger(__name__)
MAX_MIRRORS = 4


def sim_system():
    s = sim.source.Undulator('test_undulator')
    m1 = sim.mirror.OffsetMirror('test_m1h', 'test_m1h_xy',
                                 z=90.510, alpha=0.0014)
    m2 = sim.mirror.OffsetMirror('test_m2h', 'test_m2h_xy',
                                 x=0.0317324, z=101.843, alpha=0.0014)
    xrtm2 = sim.mirror.OffsetMirror('test_xrtm2', 'test_xrtm2_xy',
                                    x=0.0317324, z=200, alpha=0.0014)
    y1 = sim.pim.PIM('test_p3h', x=0.0317324, z=103.660,
                     zero_outside_yag=True)
    y2 = sim.pim.PIM('test_dg3', x=0.0317324, z=375.000,
                     zero_outside_yag=True)
    mecy1 = sim.pim.PIM('test_mecy1', x=0.0317324, z=350,
                        zero_outside_yag=True)
    mfxdg1 = mecy1
    patch_pims([y1, y2], mirrors=[m1, m2], source=s)
    patch_pims([mecy1], mirrors=[xrtm2], source=s)

    config = dict(
        m1h=m1,
        hx2=y1,
        hx2_slits=None,
        m2h=m2,
        dg3=y2,
        dg3_slits=None,
        xrtm2=xrtm2,
        mfxdg1=mfxdg1,
        mfxdg1_slits=None,
    )
    return config


# System mapping of associated devices
def get_system(config, rotation):
    system = dict(
        m1h=dict(mirror=config['m1h'],
                 imager=config['hx2'],
                 slits=config['hx2_slits'],
                 rotation=rotation),
        m2h=dict(mirror=config['m2h'],
                 imager=config['dg3'],
                 slits=config['dg3_slits'],
                 rotation=rotation),
        mfx=dict(mirror=config['xrtm2'],
                 imager=config['mfxdg1'],
                 slits=config['mfxdg1_slits'],
                 rotation=rotation),
        )
    return system


class SkywalkerGui(Display):
    """
    Display class to define all the logic for the skywalker alignment gui.
    Refers to widgets in the .ui file.
    """
    # Alignment mapping of which sets to use for each alignment
    alignments = {'HOMS': [['m1h', 'm2h']],
                  'MFX': [['mfx']],
                  'HOMS + MFX': [['m1h', 'm2h'], ['mfx']]}

    def __init__(self, parent=None, args=None):
        super().__init__(parent=parent, args=args)
        ui = self.ui

        # Configure debug file after all the qt logs
        logging.basicConfig(level=logging.DEBUG,
                            format=('%(asctime)s '
                                    '%(name)-12s '
                                    '%(levelname)-8s '
                                    '%(message)s'),
                            datefmt='%m-%d %H:%M:%S',
                            filename='./skywalker_debug.log',
                            filemode='a')

        # Decide whether to be sim or real, based on if 'live' at command line
        if 'live' in args:
            self.sim = False
            self.system = get_system(homs_system(), 90)
        else:
            self.sim = True
            self.system = get_system(sim_system(), 0)

        # Enable scrolling on small windows
        scroll = QScrollArea()
        scroll.setWidget(ui.main_frame)
        scroll.setWidgetResizable(True)
        ui.main_layout.addWidget(scroll)

        # Load config into the combo box objects
        ui.image_title_combo.clear()
        ui.procedure_combo.clear()
        self.all_imager_names = [entry['imager'].name for
                                 entry in self.system.values()]
        for imager_name in self.all_imager_names:
            ui.image_title_combo.addItem(imager_name)
        for align in self.alignments.keys():
            ui.procedure_combo.addItem(align)

        # Pick out some initial parameters from system and alignment dicts
        first_alignment_name = list(self.alignments.keys())[0]
        first_system_key = list(self.alignments.values())[0][0][0]
        first_set = self.system[first_system_key]
        first_imager = first_set['imager']
        first_slit = first_set['slits']
        first_rotation = first_set.get('rotation', 0)

        # self.procedure and self.image_obj keep track of the gui state
        self.procedure = first_alignment_name
        self.image_obj = first_imager

        # Initialize slit readback
        self.slit_group = ObjWidgetGroup([ui.slit_x_width,
                                          ui.slit_y_width],
                                         ['xwidth.readback',
                                          'ywidth.readback'],
                                         first_slit,
                                         label=ui.readback_slits_title)

        # Initialize mirror control
        self.mirror_groups = []
        mirror_labels = self.get_widget_set('mirror_name')
        mirror_rbvs = self.get_widget_set('mirror_readback')
        mirror_vals = self.get_widget_set('mirror_setpos')
        mirror_circles = self.get_widget_set('mirror_circle')
        for label, rbv, val, circle, mirror in zip(mirror_labels,
                                                   mirror_rbvs,
                                                   mirror_vals,
                                                   mirror_circles,
                                                   self.mirrors_padded()):
            mirror_group = ObjWidgetGroup([rbv, val, circle],
                                          ['pitch.user_readback',
                                           'pitch.user_setpoint',
                                           'pitch.motor_done_move'],
                                          mirror, label=label)
            if mirror is None:
                mirror_group.hide()
            self.mirror_groups.append(mirror_group)

        # Initialize the goal entry fields
        self.goal_cache = {}
        self.goals_groups = []
        goal_labels = self.get_widget_set('goal_name')
        goal_edits = self.get_widget_set('goal_value')
        slit_checks = self.get_widget_set('slit_check')
        for label, edit, check, img, slit in zip(goal_labels, goal_edits,
                                                 slit_checks,
                                                 self.imagers_padded(),
                                                 self.slits_padded()):
            if img is None:
                name = None
            else:
                name = img.name
            validator = QDoubleValidator(0, 5000, 3)
            goal_group = ValueWidgetGroup(edit, label, checkbox=check,
                                          name=name, cache=self.goal_cache,
                                          validator=validator)
            if img is None:
                goal_group.hide()
            elif slit is None:
                goal_group.checkbox.setEnabled(False)
            self.goals_groups.append(goal_group)

        # Initialize image and centroids. Needs goals defined first.
        self.image_group = ImgObjWidget(ui.image, first_imager,
                                        ui.beam_x_value, ui.beam_y_value,
                                        ui.beam_x_delta, ui.beam_y_delta,
                                        ui.readback_imager_title,
                                        self, first_rotation)

        # Create the RunEngine that will be used in the alignments.
        # This gives us the ability to pause, etc.
        self.RE = lcls_RE()
        install_qt_kicker()

        # Make sure we don't get stopped by no real beam in sim mode
        if self.sim:
            self.RE.clear_suspenders()

        # Some hax to keep the state string updated
        # There is probably a better way to do this
        # This might break on some package update
        self.RE.state  # Yes this matters
        old_set = RunEngine.state._memory[self.RE].set_
        def new_set(state):  # NOQA
            old_set(state)
            txt = " Status: " + state.capitalize()
            self.ui.status_label.setText(txt)
        RunEngine.state._memory[self.RE].set_ = new_set

        # Connect relevant signals and slots
        procedure_changed = ui.procedure_combo.currentIndexChanged[str]
        procedure_changed.connect(self.on_procedure_combo_changed)

        imager_changed = ui.image_title_combo.currentIndexChanged[str]
        imager_changed.connect(self.on_image_combo_changed)

        for goal_value in self.get_widget_set('goal_value'):
            goal_changed = goal_value.editingFinished
            goal_changed.connect(self.on_goal_changed)

        start_pressed = ui.start_button.clicked
        start_pressed.connect(self.on_start_button)

        pause_pressed = ui.pause_button.clicked
        pause_pressed.connect(self.on_pause_button)

        abort_pressed = ui.abort_button.clicked
        abort_pressed.connect(self.on_abort_button)

        slits_pressed = ui.slit_run_button.clicked
        slits_pressed.connect(self.on_slits_button)

        # Set up automatic camera switching
        self.auto_switch_cam = False
        self.cam_lock = RLock()
        for comp_set in self.system.values():
            imager = comp_set['imager']
            imager.subscribe(self.pick_cam, run=False)

        # Setup the on-screen logger
        console = self.setup_gui_logger()

        # Stop the run if we get closed
        close_dict = dict(RE=self.RE, console=console)
        self.destroyed.connect(partial(SkywalkerGui.on_close, close_dict))

        # Put out the initialization message.
        init_base = 'Skywalker GUI initialized in '
        if self.sim:
            init_str = init_base + 'sim mode.'
        else:
            init_str = init_base + 'live mode.'
        logger.info(init_str)

    # Close handler needs to be a static class method because it is run after
    # the object instance is already completely gone
    @staticmethod
    def on_close(close_dict):
        RE = close_dict['RE']
        console = close_dict['console']
        console.close()
        if RE.state != 'idle':
            RE.abort()

    def setup_gui_logger(self):
        """
        Initializes the text stream at the bottom of the gui. This text stream
        is actually just the log messages from Python!
        """
        console = GuiHandler(self.ui.log_text)
        console.setLevel(logging.INFO)
        formatter = logging.Formatter(fmt='%(asctime)s %(message)s',
                                      datefmt='%m-%d %H:%M:%S')
        console.setFormatter(formatter)
        logging.getLogger('').addHandler(console)
        return console

    @pyqtSlot(str)
    def on_image_combo_changed(self, imager_name):
        """
        Slot for the combo box above the image feed. This swaps out the imager,
        centroid, and slit readbacks.

        Parameters
        ----------
        imager_name: str
            name of the imager to activate
        """
        logger.info('Selecting imager %s', imager_name)
        for k, v in self.system.items():
            if imager_name == v['imager'].name:
                image_obj = v['imager']
                slits_obj = v.get('slits')
                rotation = v.get('rotation', 0)
        self.image_obj = image_obj
        self.image_group.change_obj(image_obj, rotation=rotation)
        if slits_obj is not None:
            self.slit_group.change_obj(slits_obj)

    @pyqtSlot(str)
    def on_procedure_combo_changed(self, procedure_name):
        """
        Slot for the main procedure combo box. This swaps out the mirror and
        goals sections to match the chosen procedure, and determines what
        happens when we press go.

        Parameters
        ----------
        procedure_name: str
            name of the procedure to activate
        """
        logger.info('Selecting procedure %s', procedure_name)
        self.procedure = procedure_name
        for obj, widgets in zip(self.mirrors_padded(), self.mirror_groups):
            if obj is None:
                widgets.hide()
                widgets.change_obj(None)
            else:
                widgets.change_obj(obj)
                widgets.show()
        for obj, widgets in zip(self.imagers_padded(), self.goals_groups):
            widgets.save_value()
            widgets.clear()
        for obj, slit, widgets in zip(self.imagers_padded(),
                                      self.slits_padded(),
                                      self.goals_groups):
            if obj is None:
                widgets.hide()
            else:
                widgets.setup(name=obj.name)
                if slit is None:
                    widgets.checkbox.setEnabled(False)
                else:
                    widgets.checkbox.setEnabled(True)
                widgets.show()

    @pyqtSlot()
    def on_goal_changed(self):
        """
        Slot for when the user picks a new goal. Updates the goal delta so it
        reflects the new chosen value.
        """
        self.image_group.update_deltas()

    @pyqtSlot()
    def on_start_button(self):
        """
        Slot for the start button. This begins from an idle state or resumes
        from a paused state.
        """
        if self.RE.state == 'idle':
            # Check for valid goals
            active_size = len(self.active_system())
            raw_goals = []
            for i, goal in enumerate(self.goals()):
                if i >= active_size:
                    break
                elif goal is None:
                    msg = 'Please fill all goal fields before alignment.'
                    logger.info(msg)
                    return
                raw_goals.append(goal)

            logger.info("Starting %s procedure with goals %s",
                        self.procedure, raw_goals)
            self.auto_switch_cam = True
            try:
                alignment = self.alignments[self.procedure]
                for key_set in alignment:
                    yags = [self.system[key]['imager'] for key in key_set]
                    mots = [self.system[key]['mirror'] for key in key_set]
                    rots = [self.system[key].get('rotation')
                            for key in key_set]
                    mot_rbv = 'pitch'
                    # We need to select det_rbv and interpret goals based on
                    # the camera rotation, converting things to the unrotated
                    # coordinates.
                    det_rbv = []
                    goals = []
                    for rot, yag, goal in zip(rots, yags, raw_goals):
                        rot_info = ad_stats_x_axis_rot(yag, rot)
                        det_rbv.append(rot_info['key'])
                        modifier = rot_info['mod']
                        if modifier is not None:
                            goal = modifier - goal
                        goals.append(goal)
                    first_steps = 6
                    tolerances = 5
                    average = 100
                    timeout = 600
                    tol_scaling = 8
                    # Temporary fix: undo skywalker's goal mangling.
                    # TODO remove goal mangling from skywalker.
                    goals = [480 - g for g in goals]
                    plan = skywalker(yags, mots, det_rbv, mot_rbv, goals,
                                     first_steps=first_steps,
                                     tolerances=tolerances,
                                     averages=average, timeout=timeout,
                                     sim=self.sim, use_filters=not self.sim,
                                     tol_scaling=tol_scaling)
                    self.RE(plan)
            except:
                logger.exception("Error in procedure.")
        elif self.RE.state == 'paused':
            logger.info("Resuming procedure.")
            self.auto_switch_cam = True
            try:
                self.RE.resume()
            except:
                logger.exception("Error in procedure.")
        self.auto_switch_cam = False

    @pyqtSlot()
    def on_pause_button(self):
        """
        Slot for the pause button. This brings us from the running state to the
        paused state.
        """
        self.auto_switch_cam = False
        if self.RE.state == 'running':
            logger.info("Pausing procedure.")
            try:
                self.RE.request_pause()
            except:
                logger.exception("Error on pause.")

    @pyqtSlot()
    def on_abort_button(self):
        """
        Slot for the abort button. This brings us from any state to the idle
        state.
        """
        self.auto_switch_cam = False
        if self.RE.state != 'idle':
            logger.info("Aborting procedure.")
            try:
                self.RE.abort()
            except:
                logger.exception("Error on abort.")

    @pyqtSlot()
    def on_slits_button(self):
        """
        Slot for the slits procedure. This checks the slit fiducialization.
        """
        logger.info('Starting slit check process.')
        image_to_check = []
        slits_to_check = []

        # First, check the slit checkboxes.
        for img_obj, slit_obj, goal_group in zip(self.imagers_padded(),
                                                 self.slits_padded(),
                                                 self.goals_groups):
            if slit_obj is not None and goal_group.is_checked:
                image_to_check.append(img_obj)
                slits_to_check.append(slit_obj)
        if not slits_to_check:
            logger.info('No valid slits selected!')
            return
        logger.info('Checking the following slits: %s',
                    [slit.name for slit in slits_to_check])

        self.auto_switch_cam = True

        def plan(img, slit, rot, output_obj):
            rot_info = ad_stats_x_axis_rot(img, rot)
            det_rbv = rot_info['key']
            fidu = slit_scan_fiducialize(img, slit, centroid=det_rbv)
            output = yield from fidu
            modifier = rot_info['mod']
            if modifier is not None:
                output = modifier - output
            output_obj[img.name] = output

        results = {}
        for img, slit in zip(image_to_check, slits_to_check):
            self.RE(plan(img, slit, results))

        logger.info('Slit scan found the following goals: %s', results)
        if self.ui.slit_fill_check.isChecked():
            logger.info('Filling goal fields automatically.')
            for img, field in zip(self.imagers_padded(), self.goals_groups):
                if img is not None:
                    try:
                        field.value = results[img.name]
                    except KeyError:
                        pass

        self.auto_switch_cam = False

    def pick_cam(self, *args, **kwargs):
        """
        Callback to switch the active imager as the procedures progress.
        """
        if self.auto_switch_cam:
            with self.cam_lock:
                chosen_imager = None
                for img in self.imagers():
                    if img.position == "Unknown":
                        return
                    elif img.position == "IN":
                        chosen_imager = img
                        break
                combo = self.ui.image_title_combo
                if chosen_imager is not None:
                    name = chosen_imager.name
                    if name != combo.currentText():
                        # TODO why does this segfault
                        # logger.info('Automatically switching cam to %s',name)
                        index = self.all_imager_names.index(name)
                        combo.setCurrentIndex(index)

    def active_system(self):
        """
        List of system keys that are part of the active procedure.
        """
        active_system = []
        for part in self.alignments[self.procedure]:
            active_system.extend(part)
        return active_system

    def mirrors(self):
        """
        List of active mirror objects.
        """
        return [self.system[act]['mirror'] for act in self.active_system()]

    def imagers(self):
        """
        List of active imager objects.
        """
        return [self.system[act]['imager'] for act in self.active_system()]

    def slits(self):
        """
        List of active slits objects.
        """
        return [self.system[act].get('slits') for act in self.active_system()]

    def goals(self):
        """
        List of goals in the user entry boxes, or None for empty or invalid
        goals.
        """
        return [goal.value for goal in self.goals_groups]

    def goal(self):
        """
        The goal associated with the visible imager, or None if the visible
        imager is not part of the active procedure.
        """
        index = self.procedure_index()
        if index is None:
            return None
        else:
            return self.goals()[index]

    def procedure_index(self):
        """
        Goal index of the active imager, or None if the visible imager is not
        part of the active procedure.
        """
        try:
            return self.imagers_padded().index(self.image_obj)
        except ValueError:
            return None

    def none_pad(self, obj_list):
        """
        Helper function to extend a list with 'None' objects until it's the
        length of MAX_MIRRORS.
        """
        padded = []
        padded.extend(obj_list)
        while len(padded) < MAX_MIRRORS:
            padded.append(None)
        return padded

    def mirrors_padded(self):
        return self.none_pad(self.mirrors())

    def imagers_padded(self):
        return self.none_pad(self.imagers())

    def slits_padded(self):
        return self.none_pad(self.slits())

    def get_widget_set(self, name, num=MAX_MIRRORS):
        """
        Widgets that come in sets of count MAX_MIRRORS are named carefully so
        we can use this macro to grab related widgets.

        Parameters
        ----------
        name: str
            Base name of widget set e.g. 'name'

        num: int, optional
            Number of widgets to return

        Returns
        -------
        widget_set: list
            List of widgets e.g. 'name_1', 'name_2', 'name_3'...
        """
        widgets = []
        for n in range(1, num + 1):
            widget = getattr(self.ui, name + "_" + str(n))
            widgets.append(widget)
        return widgets

    def ui_filename(self):
        return 'skywalker_gui.ui'

    def ui_filepath(self):
        return path.join(path.dirname(path.realpath(__file__)),
                         self.ui_filename())

intelclass = SkywalkerGui # NOQA


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
                msg = self.format(record)
                cursor = self.text_widget.cursorForPosition(QPoint(0, 0))
                cursor.insertText(msg + self.terminator)
            except Exception:
                self.handleError(record)

    def close(self):
        self.text_widget = None


class BaseWidgetGroup:
    """
    A group of widgets that are part of a set with a single label.
    """
    def __init__(self, widgets, label=None, name=None, **kwargs):
        """
        Parameters
        ----------
        widgets: list
            list of widgets in the group

        label: QLabel, optional
            A special widget that acts as the label for the group

        name: str, optional
            The label text
        """
        self.widgets = widgets
        self.label = label
        self.setup(name=name, **kwargs)

    def setup(self, name=None, **kwargs):
        """
        Do basic widget setup. For Base, this is just changing the label text.
        """
        if None not in (self.label, name):
            self.label.setText(name)

    def hide(self):
        """
        Hide all widgets in group.
        """
        for widget in self.widgets:
            widget.hide()
        if self.label is not None:
            self.label.hide()

    def show(self):
        """
        Show all widgets in group.
        """
        for widget in self.widgets:
            widget.show()
        if self.label is not None:
            self.label.show()


class ValueWidgetGroup(BaseWidgetGroup):
    """
    A group of widgets that have a user-editable value field.
    """
    def __init__(self, line_edit, label, checkbox=None, name=None, cache=None,
                 validator=None):
        """
        Parameters
        ----------
        line_edit: QLineEdit
            The user-editable value field.

        checkbox: QCheckbox, optional
            Optional checkbox widget associated with the value.

        cache: dict, optional
            For widgets that need to save/share values

        validator: QDoubleValidator, optional
            Make sure the text is a double
        """
        widgets = [line_edit]
        if checkbox is not None:
            widgets.append(checkbox)
        self.line_edit = line_edit
        self.checkbox = checkbox
        if cache is None:
            self.cache = {}
        else:
            self.cache = cache
        if validator is None:
            self.force_type = None
        else:
            if isinstance(validator, QDoubleValidator):
                self.force_type = float
            else:
                raise NotImplementedError
            self.line_edit.setValidator(validator)
        super().__init__(widgets, label=label, name=name)

    def setup(self, name=None, **kwargs):
        """
        Put name in the checkbox too
        """
        super().setup(name=name, **kwargs)
        if None not in (self.checkbox, name):
            self.checkbox.setText(name)
        if self.checkbox is not None:
            self.checkbox.setChecked(False)
        self.load_value(name)

    def save_value(self):
        """
        Stash current value in self.cache
        """
        old_name = self.label.text()
        old_value = self.value
        if None not in (old_name, old_value):
            self.cache[old_name] = old_value

    def load_value(self, name):
        """
        Grab current value from self.cache
        """
        cache_value = self.cache.get(name)
        if cache_value is not None:
            self.value = cache_value

    def clear(self):
        """
        Reset the value
        """
        self.line_edit.clear()

    @property
    def value(self):
        raw = self.line_edit.text()
        if not raw:
            return None
        if self.force_type is None:
            return raw
        else:
            try:
                return self.force_type(raw)
            except:
                return None

    @value.setter
    def value(self, val):
        txt = str(val)
        self.line_edit.setText(txt)

    @property
    def is_checked(self):
        if self.checkbox is None:
            return False
        else:
            return self.checkbox.isChecked()


class PydmWidgetGroup(BaseWidgetGroup):
    """
    A group of pydm widgets under a single label that may be set up and reset
    as a group.
    """
    protocol = 'ca://'

    def __init__(self, widgets, pvnames, label=None, name=None, **kwargs):
        """
        Parameters
        ----------
        pvnames: list
            pvs to assign to the widgets
        """
        super().__init__(widgets, label=label, name=name,
                         pvnames=pvnames, **kwargs)

    def setup(self, *, pvnames, name=None, **kwargs):
        """
        In addition to base setup, assign pv names.
        """
        super().setup(name=name, **kwargs)
        if pvnames is None:
            pvnames = [None] * len(self.widgets)
        for widget, pvname in zip(self.widgets, pvnames):
            if pvname is None:
                chan = ''
            else:
                chan = self.protocol + pvname
            try:
                widget.setChannel(chan)
            except:
                widget.channel = chan

    def change_pvs(self, pvnames, name=None, **kwargs):
        """
        Swap active pv names and manage connections
        """
        self.clear_connections()
        self.setup(pvnames=pvnames, name=name, **kwargs)
        self.create_connections()

    def clear_connections(self):
        """
        Tell pydm to drop own pv connections.
        """
        QApp = QCoreApplication.instance()
        for widget in self.widgets:
            QApp.close_widget_connections(widget)
            widget._channels = None

    def create_connections(self):
        """
        Tell pydm to establish own pv connections.
        """
        QApp = QCoreApplication.instance()
        for widget in self.widgets:
            QApp.establish_widget_connections(widget)


class ObjWidgetGroup(PydmWidgetGroup):
    """
    A group of pydm widgets that get their channels from an object that can be
    stripped out and replaced to change context, provided the class is the
    same.
    """
    def __init__(self, widgets, attrs, obj, label=None, **kwargs):
        """
        Parameters
        ----------
        attrs: list
            list of attribute strings to pull from obj e.g. 'centroid.x'

        obj: object
            Any object that holds ophyd EpicsSignal objects that have pvname
            fields that we can use to send pvname info to pydm
        """
        self.attrs = attrs
        self.obj = obj
        if obj is None:
            name = None
        else:
            name = obj.name
        pvnames = self.get_pvnames(obj)
        super().__init__(widgets, pvnames, label=label, name=name,
                         **kwargs)

    def change_obj(self, obj, **kwargs):
        """
        Swap the active object and fix connections

        Parameters
        ----------
        obj: object
            The new object
        """
        self.obj = obj
        pvnames = self.get_pvnames(obj)
        if obj is None:
            name = None
        else:
            name = obj.name
        self.change_pvs(pvnames, name=name, **kwargs)

    def get_pvnames(self, obj):
        """
        Given an object, return the pvnames based on self.attrs
        """
        if obj is None:
            return None
        pvnames = []
        for attr in self.attrs:
            sig = self.nested_getattr(obj, attr)
            try:
                pvnames.append(sig.pvname)
            except AttributeError:
                pvnames.append(None)
        return pvnames

    def nested_getattr(self, obj, attr):
        """
        Do a getattr more than one level deep, splitting on '.'
        """
        steps = attr.split('.')
        for step in steps:
            obj = getattr(obj, step)
        return obj


class ImgObjWidget(ObjWidgetGroup):
    """
    Macros to set up the image widget channels from opyhd areadetector obj.
    This also includes all of the centroid stuff.
    """
    def __init__(self, img_widget, img_obj, cent_x_widget, cent_y_widget,
                 delta_x_widget, delta_y_widget, label, goals_source,
                 rotation=0):
        self.cent_x_widget = cent_x_widget
        self.cent_y_widget = cent_y_widget
        self.delta_x_widget = delta_x_widget
        self.delta_y_widget = delta_y_widget
        self.goals_source = goals_source
        attrs = ['detector.image2.width',
                 'detector.image2.array_data']
        super().__init__([img_widget], attrs, img_obj, label=label,
                         rotation=rotation)

    def setup(self, *, pvnames, name=None, rotation=0, **kwargs):
        BaseWidgetGroup.setup(self, name=name)
        self.rotation = rotation
        img_widget = self.widgets[0]
        width_pv = pvnames[0]
        image_pv = pvnames[1]
        image_item = img_widget.getImageItem()
        image_item.setTransformOriginPoint(self.raw_size_x//2,
                                           self.raw_size_y//2)
        image_item.setRotation(rotation)
        view = img_widget.getView()
        view.setRange(xRange=(0, self.raw_size_x),
                      yRange=(0, self.raw_size_y),
                      padding=0.0)
        view.setLimits(xMin=0, xMax=self.raw_size_x,
                       yMin=0, yMax=self.raw_size_y)
        img_widget.resetImageChannel()
        img_widget.resetWidthChannel()
        if width_pv is None:
            width_channel = ''
        else:
            width_channel = self.protocol + width_pv
        if image_pv is None:
            image_channel = ''
        else:
            image_channel = self.protocol + image_pv
        img_widget.setWidthChannel(width_channel)
        img_widget.setImageChannel(image_channel)
        centroid = self.obj.detector.stats2.centroid
        self.beam_x_stats = centroid.x
        self.beam_y_stats = centroid.y
        self.beam_x_stats.subscribe(self.update_centroid)
        self.update_centroid()

    def update_centroid(self, *args, **kwargs):
        centroid_x = self.beam_x_stats.value
        centroid_y = self.beam_y_stats.value
        rotation = -self.rotation
        xpos, ypos = self.rotate(centroid_x, centroid_y, rotation)
        if xpos < 0:
            xpos += self.size_x
        if ypos < 0:
            ypos += self.size_y
        self.xpos = xpos
        self.ypos = ypos
        self.cent_x_widget.setText(str(xpos))
        self.cent_y_widget.setText(str(ypos))
        self.update_deltas()

    def update_deltas(self):
        goal = self.goals_source.goal()
        if goal is None:
            self.delta_x_widget.clear()
        else:
            self.delta_x_widget.setText(str(self.xpos - goal))
        self.delta_y_widget.clear()

    @property
    def size(self):
        rot_x, rot_y = self.rotate(self.raw_size_x, self.raw_size_y,
                                   self.rotation)
        return (int(round(abs(rot_x))), int(round(abs(rot_y))))

    @property
    def size_x(self):
        return self.size[0]

    @property
    def size_y(self):
        return self.size[1]

    @property
    def raw_size_x(self):
        return self.obj.detector.cam.array_size.array_size_x.value

    @property
    def raw_size_y(self):
        return self.obj.detector.cam.array_size.array_size_y.value

    def to_rad(self, deg):
        return deg*pi/180

    def sind(self, deg):
        return sin(self.to_rad(deg))

    def cosd(self, deg):
        return cos(self.to_rad(deg))

    def rotate(self, x, y, deg):
        x2 = x * self.cosd(deg) - y * self.sind(deg)
        y2 = x * self.sind(deg) + y * self.cosd(deg)
        return (x2, y2)


def ad_stats_x_axis_rot(imager, rotation):
    """
    Helper function to pick the correct key and modify a value for a rotated
    areadetector camera with a stats plugin, where you care about the x axis of
    the centroid.

    Returns
    -------
    output: dict
        ['key']: 'detector_stats2_centroid_x' or 'detector_stats2_centroid_y'
        ['mod']: int or None. If int, you get a true value by doing int-value
    """
    det_key_base = 'detector_stats2_centroid_'
    sizes = imager.detector.cam.array_size
    rotation = rotation % 360
    if rotation % 180 == 0:
        det_key = det_key_base + 'x'
        axis_size = sizes.array_size_x.value
    else:
        det_key = det_key_base + 'y'
        axis_size = sizes.array_size_y.value
    if rotation in (90, 180):
        modifier = axis_size
    else:
        modifier = None
    return dict(key=det_key, mod=modifier)


def debug_log_pydm_connections():
    QApp = QCoreApplication.instance()
    plugins = QApp.plugins
    ca_plugin = plugins['ca']
    connections = ca_plugin.connections
    counts = {k: v.listener_count for k, v in connections.items()}
    logger.debug('Pydm connection counts: %s', counts)
