############
# Standard #
############
import os.path

###############
# Third Party #
###############
import pytest


##########
# Module #
##########
from skywalker.config import ConfigReader, sim_config

def make_test_path(path):
    """
    Make a file in the test directory absolute
    """
    return os.path.join(os.path.dirname(__file__), path)

def test_system_loading():
    #Load configuration
    cfg = ConfigReader(make_test_path('happi.json'),
                       make_test_path('system.json'))
    #Check that all of the simulation systems are loaded
    assert all([system in cfg.cache for system in sim_config.keys()])
    #Load a subsystem
    system = cfg.get_subsystem('m1h')
    #Check we have all of our device types
    assert all([_type in system.keys() for _type in cfg.device_types])
    #Check that a second call only retrieves a cached system
    assert id(cfg.get_subsystem('m1h')) == id(system)
