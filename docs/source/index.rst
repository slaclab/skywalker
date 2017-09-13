.. Skywalker documentation master file, created by
   sphinx-quickstart on Tue Sep 12 15:24:13 2017.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

The PCDS Skywalker Project
==========================

The Skywalker software suite is a set of of Python tools designed to
automatically deliver the photon beam to a number of experimental hutches at
LCLS

Design Goals
============

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

Software Packages
=================

The following software packages work in concert to accomplish the goals listed
above:

* **happi:** A database protocol capable of storing arbitrary metadata about
  beamline devices.
* **lightpath:** Group devices into long paths allowing operators to quickly
  determine where the beam is currently being delivered  
* **pswalker:** Plans neccesary for the alignment of the LCLS beamlines.
* **psbeam:** Image processing tools used to analyze the output of photon
  diagnostics.

.. toctree::
   :hidden:
   :maxdepth: 2

   installation.rst

.. toctree::
   :hidden:
   :caption: Core Skywalker Packages

   happi/index.rst
   lightpath/index.rst
   pcds-devices/index.rst
   pswalker/index.rst
   psbeam/index.rst

.. toctree::
   :hidden:
   :caption: Related Software  
   
    bluesky <https://nsls-ii.github.io/bluesky>
    ophyd <https://nsls-ii.github.io/ophyd>

.. toctree::
   :hidden:
   :caption: GitHub Links

   SLAC Repositories <https://github.com/slaclab/>
   PCDS Repositories <https://github.com/lcls-pcds/>
   :maxdepth: 2
   :caption: Contents:

