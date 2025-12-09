================
 Ultralight Make Sheets
================

A super lightweight tool to create minimal character sheets for Dungeons and
Dragons 5th edition 2024 (D&D 5e) based on dungeonsheets_ and using `minimal latex docker images`_.

.. _dungeonsheets: https://github.com/canismarko/dungeon-sheets
.. _minimal latex docker images: https://github.com/kjarosh/latex-docker

Docker
======
This repository is designed to be ran directly from a container.

Run the following in the root of the repository. Substituting ``$(pwd)`` for a path 
containing valid character files:

.. code:: bash

    $ docker build -t ultralight-make_sheets:latest .
    $ docker run $(pwd):/build ultralight-make_sheets:latest


Installation
============

.. code:: bash

    $ pip install .


Optional External dependencies
==============================

* You will need **pdflatex**, and a few latex packages, installed to
  generate the PDF spell pages (optional).

In order to properly format descriptions for spells/features/etc.,
some additional latex packages are needed. On Ubuntu these can be
installed with:

.. code:: bash

    $ sudo apt-get -y install texlive-latex-base texlive-latex-extra texlive-fonts-recommended

Usage
=====

Each character or set of GM notes is described by a python (or a VTTES
JSON) file, which gives many attributes associated with the
character. See examples_ for more information about the character
descriptions.

.. _examples: https://github.com/seankcn/ultralight-make_sheets/tree/master/examples

The PDF's can then be generated using the ``makesheets`` command. If
no filename is given, the current directory will be parsed and any
valid files found will be processed.

.. code:: bash

    $ cd examples
    $ makesheets

dungeon-sheets contains definitions for standard weapons and spells,
so attack bonuses and damage can be calculated automatically.

By default, your character's spells are ordered alphabetically. If you
would like your spellbook to be ordered by level, you can use the ``-S``
option to do so.


Content Descriptions
====================

The descriptions of content elements (e.g. classes, spells, etc.) are
included in docstrings. The descriptions should ideally conform to
reStructured text. This allows certain formatting elements to be
properly parsed and rendered into LaTeX::

  class Scrying(Spell):
    """You can see and hear a particular creature you choose that is on
    the same plane of existence as you. The target must make a W isdom
    saving throw, which is modified by how well you know the target
    and the sort of physical connection you have to it. If a target
    knows you're casting this spell, it can fail the saving throw
    voluntarily if it wants to be observed.

    Knowledge - Save Modifier
    -------------------------
    - Secondhand (you have heard of the target) - +5
    - Firsthand (you have met the target) - +0
    - Familiar (you know the target well) - -5

    Connection - Save Modifier
    --------------------------
    - Likeness or picture - -2
    - Possession or garment - -4
    - Body part, lock of hair, bit of nail, or the like - -10

    """
    name = "Scrying"
    level = 5
    ...

For content that is not part of the SRD, consider using other
sources. As an example, parse5e_ can be used to retrieve spells.


.. _parse5e: https://github.com/user18130814200115-2/parse5e
