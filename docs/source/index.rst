.. _index:

Welcome to Shape-Cellkit Documentation !
========================================

**ShapeIC CellKit** is an open-source Python library for generating
parameterized analog integrated circuit layouts.

It provides a collection of reusable analog primitives and macros,
with technology-specific implementations for different Process Design
Kits (PDKs).

CellKit can be used independently through Python scripts or integrated
into the `ShapeIC <https://github.com/ShapeIC/shapeic>`_ design
automation framework.

Key Features
------------

* **Parameterized Layout Generation:** Generate analog layouts
  programmatically using configurable device geometries.

* **Reusable Primitives and Macros:** Build complex analog circuits
  from reusable layout components.

* **Multi-Technology Support:** Access technology-specific layout
  implementations through a common interface.

* **Layout Verification:** Support for Design Rule Checking (DRC)
  and Layout Versus Schematic (LVS) verification.

* **Python Integration:** Generate, manipulate, and export layouts
  directly from Python.

Architecture Overview
---------------------

ShapeIC CellKit is organized around four main components:

* **Catalog:** Provides a unified interface for discovering and
  accessing available layout implementations.

* **Primitives:** Parameterized analog building blocks, such as
  differential pairs and current mirrors.

* **Macros:** Higher-level analog layouts constructed from multiple
  primitives.

* **Technologies:** Technology-specific PCells, design rules, and
  layout utilities associated with supported PDKs.

This organization separates the interface for generating layouts
from their technology-specific implementations.

Documentation
-------------

.. toctree::
   :maxdepth: 1
   :caption: Getting Started

   getting-started/index

.. toctree::
   :maxdepth: 2
   :caption: User Guide

   user-guide/index

.. toctree::
   :maxdepth: 2
   :caption: Developer Guide

   developer-guide/index

.. toctree::
   :maxdepth: 2
   :caption: API Reference

   api/index

Project Links
-------------

* `GitHub Repository <https://github.com/ShapeIC/shapeic-cellkit>`_
* `ShapeIC Project <https://github.com/ShapeIC/shapeic>`_
* `Issue Tracker <https://github.com/ShapeIC/shapeic-cellkit/issues>`_
