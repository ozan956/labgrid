Design Decisions
================

This document outlines the design decisions influencing the development of
labgrid.

Out of Scope
------------

Out of scope for labgrid are:

Integrated Build System
~~~~~~~~~~~~~~~~~~~~~~~

In contrast to some other tools, labgrid explicitly has no support for building
target binaries or images.

Our reasons for this are:

- Several full-featured build systems already exist and work well.
- We want to test unmodified images produced by any build system (OE/Yocto,
  PTXdist, Buildroot, Debian, …).

Test Infrastructure
~~~~~~~~~~~~~~~~~~~

labgrid does not include a test framework.

The main reason is that with `pytest <https://docs.pytest.org/>`_ we already
have a test framework which:

- makes it easy to write tests
- reduces boilerplate code with flexible fixtures
- is easy to extend and has many available plugins
- allows using any Python library for creating inputs or processing outputs
- supports test report generation

Furthermore, the hardware control functionality needed for testing is also very
useful during development, provisioning and other areas, so we don't want to
hide that behind another test framework.

In Scope
--------

- usable as a library for hardware provisioning
- device control via:

  - serial console
  - SSH
  - file management
  - power and reset

- emulation of external services:

  - USB stick emulation
  - external update services (Hawkbit)

- bootstrap services:

  - fastboot
  - imxusbloader

Shared Board Labs
-----------------

Large shared labs put different pressure on labgrid than project-owned or
single-user setups. The current model remains useful because it is flexible,
but large, mostly static board farms often need operational simplicity first.
The following notes collect design considerations which have come up in such
deployments.

Observed Friction In Practice
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The following situations tend to come up repeatedly in large shared labs:

Board identity is split across concepts
  The physical board is already obvious to the operator and to the exporter
  layout, but users still have to reason about resources, exporter groups,
  places, and separate client-side target descriptions. For a mostly static
  1:1 board setup, this can feel like modeling the same thing multiple times.

Interactive usage and full usage diverge
  Console access or power control may work directly through the place, but more
  realistic tasks often need OpenOCD configuration, image paths, strategies,
  helper scripts, or custom drivers. The result is that the simple workflow
  only covers the shallow end, while normal engineering work falls back to
  extra local setup.

Shared knowledge is distributed as per-user configuration
  If many users need the same board-specific OpenOCD setup, the same flash
  layout, or the same boot strategy, that knowledge is no longer really
  personal configuration. Treating it as such makes updates and consistency
  harder than they need to be.

Infrastructure changes propagate poorly
  When tool paths, images, server names, or debug settings change, the change
  is not absorbed once at the infrastructure boundary. Instead, it tends to
  trigger a documentation, support, and synchronization exercise across users,
  repositories, or wrapper scripts.

Access management becomes part of the user workflow
  Shared Unix users reduce friction but weaken isolation and traceability.
  Per-user Unix accounts improve traceability but increase provisioning,
  revocation, SSH key management, and host-side permissions work. Neither
  choice is attractive when the goal is simply safe, shared board access.

SSH access becomes a scaling problem of its own
  When labs span multiple hosts or locations, SSH setup and lifecycle
  management can become a visible part of daily operations. Teams may benefit
  from stronger centralized approaches for authentication and short-lived
  access. One option worth evaluating is `OpenPubkey SSH (opkssh)
  <https://github.com/openpubkey/opkssh>`_.

CI and human users compete through the same abstractions
  The same board inventory must serve automation and interactive work, but the
  current model often leaves teams building local conventions on top of places,
  locks, scripts, and documentation to make that coexistence understandable.

Why The Current Model Can Feel Mismatched
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The core issue is not that the present model is wrong. It is that it is
optimized for flexibility and configurability first, while large shared board
farms usually need operational simplicity first.

For dynamic setups, custom test suites, and project-owned environments, the
separation between resources, places, and client-side target descriptions makes
sense.

For large shared labs, however, this same separation can have unfortunate side
effects:

* the board looks simple at the hardware level, but complicated at the user
  interface level
* the infrastructure already knows most of the board description, but the user
  must still assemble the rest
* routine lab maintenance turns into user-facing migration work
* support effort grows faster than the apparent complexity of the board itself

In other words, the model remains powerful, but the user experience can become
heavier than the actual task being performed.

Possible Improvements
~~~~~~~~~~~~~~~~~~~~~

Large shared labs may benefit from an additional workflow which keeps the
current flexible model intact, but offers a more infrastructure-provided path
for common static deployments.

Possible improvements include:

* allow a board-oriented definition to be served centrally, so users can
  consume a ready-to-use target instead of rebuilding it locally
* make 1:1 exporter-group-to-board mappings first-class, so the common static
  case needs less manual place modeling
* allow exporters or the coordinator to provide environment fragments or merged
  target descriptions for interactive users
* reduce the amount of board-specific knowledge that must be duplicated across
  user repositories and local wrapper scripts
* provide a cleaner access model where users interact with shared boards without
  needing direct exposure to host-level account management details
* define a clearer workflow for mixed CI and interactive usage in the same
  shared board inventory

Further Goals
-------------

- tests should be equivalent for workstations and servers
- discoverability of available boards
- distributed board access
