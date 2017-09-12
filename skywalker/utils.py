#!/usr/bin/env python
# -*- coding: utf-8 -*-
import logging
from pydm.PyQt.QtCore import QCoreApplication

logger = logging.getLogger(__name__)


def ad_stats_x_axis_rot(imager, rotation):
    """
    Helper function to pick the correct key and modify a value for a rotated
    areadetector camera with a stats plugin, where you care about the x axis of
    the centroid.

    Returns
    -------
    output: dict
        ['key']: 'detector_stats2_centroid_x' or 'detector_stats2_centroid_y'
        ['mod_x']: int or None. If int, you get a true value by doing int-value
        ['mod_y']: int or None. If int, you get a true value by doing int-value
        ['x_cent']: Signal associated with the x centroid
        ['y_cent']: Signal associated with the y centroid
        ['x_size']: Signal associated with the x size
        ['y_size']: Signal associated with the y size
    """
    det_key_base = 'detector_stats2_centroid_'
    sizes = imager.detector.cam.array_size
    centroid = imager.detector.stats2.centroid
    rotation = rotation % 360
    if rotation % 180 == 0:
        det_key = det_key_base + 'x'
        x_size = sizes.array_size_x
        y_size = sizes.array_size_y
        x_cent = centroid.x
        y_cent = centroid.y
    else:
        det_key = det_key_base + 'y'
        x_size = sizes.array_size_y
        y_size = sizes.array_size_x
        x_cent = centroid.y
        y_cent = centroid.x
    if rotation == 0:
        mod_x = None
        mod_y = None
    elif rotation == 90:
        mod_x = x_size.value
        mod_y = None
    elif rotation == 180:
        mod_x = x_size.value
        mod_y = y_size.value
    else:
        mod_x = None
        mod_y = y_size.value
    return dict(key=det_key, mod_x=mod_x, mod_y=mod_y, x_cent=x_cent,
                y_cent=y_cent, x_size=x_size, y_size=y_size)


def debug_log_pydm_connections():
    QApp = QCoreApplication.instance()
    plugins = QApp.plugins
    ca_plugin = plugins['ca']
    connections = ca_plugin.connections
    counts = {k: v.listener_count for k, v in connections.items()}
    logger.debug('Pydm connection counts: %s', counts)
