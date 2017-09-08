import logging

import happi
import simplejson
from happi.backends import JSONBackend

from pcdsdevices import sim, OffsetMirror
from pcdsdevices.happireader import construct_device
from pswalker.examples import patch_pims

logger = logging.getLogger(__name__)

#####################
# Simulated Devices #
#####################
#Source
s   = sim.source.Undulator('test_undulator')

#Mirrors
m1  = sim.mirror.OffsetMirror('test_m1h', 'test_m1h_xy',
                              z=90.510, alpha=0.0014)
m2  = sim.mirror.OffsetMirror('test_m2h', 'test_m2h_xy',
                              x=0.0317324, z=101.843, alpha=0.0014)
xrtm2 = sim.mirror.OffsetMirror('test_xrtm2', 'test_xrtm2_xy',
                                x=0.0317324, z=200, alpha=0.0014)
#Imagers
y1     = sim.pim.PIM('test_p3h', x=0.0317324, z=103.660,
                     zero_outside_yag=True)
y2     = sim.pim.PIM('test_dg3', x=0.0317324, z=375.000,
                     zero_outside_yag=True)
mecy1  = sim.pim.PIM('test_mecy1', x=0.0317324, z=350,
                     zero_outside_yag=True)
mfxdg1 = mecy1

#Create simulation with proper distances
patch_pims([y1, y2], mirrors=[m1, m2], source=s)
patch_pims([mecy1], mirrors=[xrtm2], source=s)

#Pseudo-config
sim_config = {'sim_m1h' : {'mirror'   : m1,
                           'imager'   : y1,
                           'rotation' : 0,
                           'slits'    : None},
              'sim_m2h' : {'mirror'   : m2,
                           'imager'   : y2,
                           'rotation' : 0,
                           'slits'    : None},
              'sim_m2h' : {'mirror'   : m2,
                           'imager'   : y2,
                           'rotation' : 0,
                           'slits'    : None},
              'sim_mfx' : {'mirror'   : xrtm2,
                           'imager'   : mfxdg1,
                           'rotation' : 0,
                           'slits'    : None}}

class ConfigReader:
    """
    Device to store and load devices neccesary for alignment

    The configuration is dependent on two seperate JSON files. The first of
    which is the standard configuration file created by the `JSONBackend` for
    happi. This contains all the necessary devices for alignment. The second of
    which is a JSON file that contains all the device names grouped into single
    subsystems consisting of a slit, a mirror, an imager, and a rotation for
    the YAG.

    At initialization the system names and mapping are loaded into the
    ConfigReader, then a user can request that a subsystem be loaded by using
    :meth:`.get_subystem`. This looks in the system description for each child
    devices name, requests the child device's information in happi and
    instantiates the correct pcdsdevice. Once this has been done in happi,
    subsequent requests will simply returned cached value as to avoid
    unnecessary device creation.

    Parameters
    ----------
    happi_json : str
        Path to JSON file that contains happi information

    system_json : str
        Path to JSON file that holds device names to load from happi
    """
    device_types = ['mirror', 'imager', 'slits']
    info_swap    = {'mirror' : {'states' : 'prefix_xy'},
                    'imager' : {'data'   : 'prefix_det'}}
    def __init__(self, happi_json, system_json):
        #Load happi client
        self.client  = happi.Client(database=JSONBackend(happi_json))
        #Load system information
        self.live_systems = simplejson.load(open(system_json, 'r'))
        #Create cache of previously loaded devices
        self.cache = sim_config

    @property
    def available_systems(self):
        """
        All systems the ConfigReader has available mappings
        """
        return list(self.live_systems.keys())+list(sim_config.keys())

    def get_subsystem(self, system, rotation=90, timeout=30):
        """
        Load the pcdsdevices corresponding to a system name

        Parameters
        ----------
        system : str
            Name of subsystem to load

        rotation : float, optional
            Rotation to add to subsystem

        timeout : float, optional
            Timeout for devices

        Returns
        -------
        subsystem : dict
            Dictionary containing keys for mirror, imager, slits and rotation
        """
        #Reload previously accessed systems
        if system in self.cache:
            logger.debug("Using cached devices for %s", system)
            return self.cache[system]

        if system not in self.available_systems:
            logger.error("No system information found for %s", system)

        #Create new system
        logger.info("Loading necessary device information from database")
        system_objs  = dict.fromkeys(self.device_types)
        system_objs.update({'rotation' : rotation})
        for dev_type in self.device_types:
            #Get information from system names
            try:
                #Get device name
                name = self.live_systems[system][dev_type]
                #Get device information
                info = self.client.load_device(name=name)
                #Load device and store
                system_objs[dev_type]= construct_device(
                                        info,
                                        timeout=timeout,
                                        info_map=self.info_swap.get(dev_type,
                                                                    {}))
            #System JSON failure
            except KeyError:
                logger.error("System %s does not have a %s object registered",
                              system, dev_type)
            #Happi failure
            except happi.errors.SearchError:
                logger.error("Unable to find device %s in the database",
                             device_name)
            #Catch-all
            except Exception:
                logger.exception('Error loading device %s for %s',
                                 system, dev_type)
            #Cache system for quick recall
            else:
                self.cache[system] = system_objs

        return system_objs

