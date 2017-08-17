#!/usr/bin/env python
# -*- coding: utf-8 -*-
from os import path
from pydm import Display

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
        self.alignments

    def ui_filename(self):
        return 'skywalker_gui.ui'

    def ui_filepath(self):
        return path.join(path.dirname(path.realpath(__file__)),
                         self.ui_filename())

intelclass = SkywalkerGui
