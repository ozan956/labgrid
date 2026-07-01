Use Cases
=========

labgrid can be used in different setups depending on where the boards are
connected, how many users need access, and where the target configuration is
maintained.

The common patterns below are:

* one developer with one board
* one tester with many boards
* multiple users sharing boards in one location
* multiple users sharing boards across locations

The same labgrid concepts are used in each pattern. Resources describe
interfaces such as serial consoles, power ports, USB devices, and network
services. Exporters publish resources from the hosts where the hardware is
connected. The coordinator keeps track of exported resources and places. Users
or automation acquire places and use them through :command:`labgrid-client`,
pytest, or the Python API.

One Developer with One Board
----------------------------

This is the simplest labgrid setup. One developer works with a board connected
directly to a workstation or laptop.

Typical characteristics are:

* the board is connected to the same host where labgrid commands are run
* serial ports, USB devices, power switches, images, and helper tools are local
* the environment file usually lives next to the project or test code
* the same person usually owns the board setup and uses it

In this setup, a local environment file can describe the target directly. It
can contain local paths, tool names, drivers, strategies, and resource
definitions used by the developer's project.

Typical usage includes:

* starting an interactive console
* power cycling or resetting the board
* bootstrapping the board over USB
* running project-specific pytest tests
* using labgrid from Python scripts

An example would be an embedded Linux developer with a laptop, a serial
adapter, a power switch, and a single board used for daily bring-up and
debugging.

One Tester with Many Boards
---------------------------

In this setup, one person or a small team operates several boards. The boards
may be connected to one or more lab hosts instead of directly to the user's
workstation.

Typical characteristics are:

* boards are exported from one or more remote hosts
* one person or a small team maintains the hardware setup
* places are commonly used to represent individual physical boards
* environment files are maintained by the team using the boards

The lab hosts run exporters. Each exporter publishes the resources connected to
that host, for example serial ports, power ports, USB devices, and network
interfaces. The coordinator stores the available resources and the places that
refer to them.

A common workflow is:

#. start exporters on the lab hosts
#. create places for the physical boards
#. add matches from each place to the exported resources
#. acquire a place before using the board
#. release the place after the interactive session or test run

Users can combine the remote resources with project-specific environment files.
Those environment files can define drivers, strategies, images, tool paths, and
other target configuration used by tests or scripts.

An example would be a tester with a rack of boards in a nearby lab, maintained
and used by the same person or team every day.

Multiple Users Sharing Boards in One Location
---------------------------------------------

In this setup, a board lab is shared by several users or teams in the same
organization and location. The boards are connected to lab hosts and published
through labgrid exporters.

Typical examples include internal hardware labs where development, validation,
bring-up, debugging, issue reproduction, and CI all use the same board
inventory. Users may include embedded Linux engineers, application developers,
electrical engineers, support engineers, validation teams, and automation
maintainers.

A simple board may export resources such as:

.. code-block:: text

   lab/board-01/NetworkSerialPort
   lab/board-01/NetworkUSBDebugger
   lab/board-01/NetworkPowerPort

These resources can be grouped through a place:

.. code-block:: shell

   labgrid-client -p board-01 add-match lab/board-01/*

Users can then acquire the place and run commands such as:

.. code-block:: shell

   labgrid-client -p board-01 acquire
   labgrid-client -p board-01 console
   labgrid-client -p board-01 power cycle
   labgrid-client -p board-01 release

Current labgrid functionality for this setup includes:

* resource publication from multiple exporters
* place creation and resource matching through the coordinator
* exclusive access to places through acquire and release operations
* interactive client commands for console, power, reset, SSH, and similar
  board operations
* use of place tags to describe board properties
* use of reservations to select places by tags
* project-specific environment files for drivers, strategies, tools, images,
  and test configuration
* pytest integration for automated tests using the same target descriptions

The coordinator stores shared information about resources, places, tags,
matches, reservations, and acquisitions. Project repositories can keep the
environment files and test code that describe how a specific project uses those
boards.

Host access, user accounts, SSH keys, permissions, exported tool paths, and
site-specific operating procedures are managed outside labgrid by the
organization operating the lab.

An example would be a central validation lab used by firmware, application, and
test teams in the same office.

Multiple Users Sharing Boards Across Locations
----------------------------------------------

This setup uses the same labgrid mechanisms as a shared lab in one location,
but the users, lab hosts, and boards may be in different offices, sites, or
time zones.

Typical characteristics are:

* exporters run on lab hosts in one or more locations
* users connect to the coordinator from their own workstations or CI systems
* places and tags identify the boards available to users
* environment files and test code can live in the users' project repositories
* access to lab hosts is handled through the organization's network and account
  management

The coordinator can track resources from exporters running on different hosts.
Users work with places in the same way as in a local shared lab: they list
available places, acquire a suitable place, run interactive commands or tests,
and release the place when finished.

The labgrid objects used in this setup are the same:

* exporters publish the hardware resources at each site
* the coordinator tracks resources, places, tags, matches, reservations, and
  acquisitions
* places provide stable names for boards or board setups
* reservations select suitable places by tag
* environment files describe the target used by project automation
* :command:`labgrid-client`, pytest, and the Python API provide user-facing
  access to the target

Site-specific information such as physical board location, local recovery
procedures, user account provisioning, SSH access, and lab ownership is kept in
the operational documentation of the organization using the lab.

An example would be a company with teams in different offices using boards
through a shared coordinator while a lab operations group maintains the
hardware at each site.
