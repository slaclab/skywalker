The PCDS Skywalker Project
==========================
.. image:: https://travis-ci.org/slaclab/skywalker.svg?branch=master
  :target: https://travis-ci.org/slaclab/skywalker

The Skywalker software suite is a set of of Python tools designed to
automatically deliver the photon beam to a number of experimental hutches at
LCLS

Design Goals
++++++++++++

* Create an organized database of photon instruments and their associated
  metadata. This allows high-level applications a clean and consistent API to
  both store the information necessary to perform their intended task with
  minimal repeated code written to instantiate and save device configurations

* Provide the device abstractions necessary to manipulate any instrument
  involved in the alignment of an LCLS beamline.

* Automatically detect devices that need to be removed or inserted during the
  alignment process. Provide a Python API for operators to control large
  swathes of the beamline as a single object.

* Create a Python ecosystem that is extensible to any automation project at
  SLAC by creating generalized scripts to perform common tasks. This includes
  providing the framework to use predictive control on any system that can be
  modeled with a simple analytical function
  
* Using existing Photon diagnostics, steer the beam through an abitrary number
  of mirrors to deliver the beam quickly aand accurately for the LCLS
  experimental program

Accessing Applications
++++++++++++++++++++++
The top level ``skywalker`` repository will install two executables ``skywalker``
and ``lightpath`` in your ``/usr/bin`` directory. One can manually use the
:class:`lightpath.ui.LightApp` widget, but this script will handle loading the
configuration stored with `skywalker/config/metadata.json` into the lightpath
itself.

.. code::

    lightpath --hutch MFX

The ``skywalker`` executable is installed as well. By default, this is launched
in a simulation mode, but by using ``--live`` option, the application is
instantiated ready for automated alignment

.. code::

    skywalker --live

    configuration stored with ``skywalker/config`` as their source.


Software Packages
+++++++++++++++++

The following software packages work in concert to accomplish the goals listed
above:

* **happi:** A database protocol capable of storing arbitrary metadata about
  beamline devices.
* **lightpath:** Group devices into long paths allowing operators to quickly
  determine where the beam is currently being delivered  
* **pswalker:** Plans neccesary for the alignment of the LCLS beamlines.
* **psbeam:** Image processing tools used to analyze the output of photon
  diagnostics.


Conda
++++++
Install the most recent tagged build:

.. code::
  
  conda install skywalker -c skywalker-tag -c lightsource2-tag -c conda-forge

Install the most recent development build: 

.. code::

  conda install skywalker -c skywalker-dev -c lightsource2-tag -c conda-forge

