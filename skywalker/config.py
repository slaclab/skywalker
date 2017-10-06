import logging

import happi
import simplejson
from happi.backends import JSONBackend

import pcdsdevices
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
              'sim_mfx' : {'mirror'   : xrtm2,
                           'imager'   : mfxdg1,
                           'rotation' : 0,
                           'slits'    : None}}

sim_alignments = {'HOMS': [['sim_m1h', 'sim_m2h']],
                  'MFX': [['sim_mfx']],
                  'HOMS + MFX': [['sim_m1h', 'sim_m2h'], ['sim_mfx']]}


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

    def get_subsystem(self, system, rotation=90, timeout=30, use_cache=True):
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

        use_cache : bool, optional
            Search the cache for previously loaded devices before instantiating
            new ones. True by default
        Returns
        -------
        subsystem : dict
            Dictionary containing keys for mirror, imager, slits and rotation
        """
        #Reload previously accessed systems
        if system in self.cache and use_cache:
            logger.debug("Using cached devices for %s", system)
            return self.cache[system]

        if system not in self.available_systems:
            logger.error("No system information found for %s", system)

        #Create new system
        logger.info("Loading necessary device information from database")
        system_objs  = dict.fromkeys(self.device_types)
        system_objs.update({'rotation' : rotation})
        #Get information from system names
        try:
            for dev_type in self.device_types:
                #Get device name
                name = self.live_systems[system][dev_type]
                dev  = self.load_device(name)
                #Report if we did not recieve a device
                if not dev:
                    raise ValueError
                #Store in system obj
                system_objs[dev_type] = dev

        #System JSON failure
        except KeyError:
            logger.error("System %s does not have a %s object registered",
                          system, dev_type)
        except ValueError:
            logger.error("Abandoning configuration load for %s",
                         system)
        #Cache system for quick recall
        else:
            self.cache[system] = system_objs

        return system_objs

    def load_device(self, name, timeout=1):
        """
        Load a device by name from happi

        The happi file is expected to be configured with a `device_class` that
        matches the necessary class from `pcdsdevices`, as well as information
        under `args` and `kwargs` that are used to instantiate the device.

        If the device fails to load for any reason, `None` is returned instead

        Parameters
        ----------
        name : str
            Name of the device

        timeout : float, optional
            Timeout for EPICS signal connections

        Returns
        -------
        `pcdsdevices.Device` or `None`

        """
        try:
            #Get device information
            logger.debug("Loading %s ...", name)
            happi_obj = self.client.load_device(name=name)
            #Grab proper device class
            device_cls = getattr(pcdsdevices,
                                 happi_obj.extraneous['device_class'])
            #Extra arguments and keywords
            (_args, _kwargs) = (happi_obj.extraneous.get(key)
                                for key in ('args', 'kwargs'))
            dev = construct_device(happi_obj,
                                   device_class=device_cls,
                                   **_kwargs)
            #Instantiate all our signals, even if lazy
            dev.wait_for_connection(all_signals=True,
                                    timeout=timeout)
        #Happi failure
        except happi.errors.SearchError:
            logger.error("Unable to find device %s in the database",
                         name)
        #No proper pcds-devices
        except AttributeError as exc:
            logger.exception("Unable to find proper object for %s",
                             exc)
        #Catch-all
        except Exception:
            logger.exception('Error loading device %s', name)
        #Return a device if no exceptions
        else:
            return dev
        #Do not return anything if we saw an exception
        return None

    def load_configuration(self, timeout=1):
        """
        Load the entire configuration

        In order to still represent devices in the lightpath that fail to load,
        if a device fails on intialization the happi container is returned
        instead.

        Parameters
        ----------
        timeout : float, optional
            Timeout for EPICS signal connections

        Returns
        -------
        pcdsdevices: list
            List of properly instantiated pcdsdevices

        containers : list
            List of happi containers that failed to load
        """
        #Load devices
        devices = list()
        containers = list()
        #Iterate through all the devices
        for container in self.client.all_devices:
            #Create a device
            dev = self.load_device(container.name,
                                   timeout=timeout)
            #Add to our list
            if dev is not None:
                devices.append(dev)
            else:
                containers.append(container)
        #Return a list of devices
        return devices, containers
