Example report
==============

Full output for UT night **20260419**, an archived practice night from
``~/all_logs`` (Hydra cluster fields), built with:

.. code-block:: bash

   python3 make_report.py --date 20260419 --practice-fallback

Input logs
----------

On the mountain these live in ``~/data/20260419/logs/``. For this practice
night they come from ``~/all_logs/20260419/``.

.. list-table::
   :header-rows: 1
   :widths: 22 22 56

   * - File
     - Written by
     - Used for
   * - ``20260419.obsplan``
     - survey team; ``grab_obsplan.csh`` fetches it, ``obs_control_script`` copies it in
     - Planned fields: summary counts and field inventory
   * - ``log.obs``
     - scheduler
     - One line per exposure: exposures table, field inventory
   * - ``20260419.log`` (scheduler log)
     - scheduler (``~/scheduler/bin/scheduler``)
     - Dome open/closed and weather (Temp, RH, wind)
   * - ``dimm.logs``
     - ``ntt_dome_status``
     - DIMM seeing column (no samples for this night)
   * - ``dome_daemon.log``
     - ``dome_daemon``
     - Preferred dome close time (no entries for this night)
   * - ``questctl.*.log``
     - ``questctl``
     - Dome close from shutter bits / CLOSE_CODE (no entries for this night)

obsplan
~~~~~~~

The whole file. The report reads RA (hours), Dec (degrees), shutter
(``Y``/``S`` = science, otherwise calibration), the 6th column (exposures
needed), and the tag after ``#``.

.. literalinclude:: examples/inputs_20260419/20260419.obsplan
   :language: text

log.obs
~~~~~~~

First 4 of 22 lines. The report reads RA, Dec, shutter, the FITS timestamp
(``20260419015150`` gives UT 01:51:50) and the tag after ``#``.

.. literalinclude:: examples/inputs_20260419/log.obs
   :language: text

Scheduler log
~~~~~~~~~~~~~

The file is about 10,800 lines of scheduler output. The report only reads
status lines that start with ``UT :``. These three are where the dome state
changes: closed at 3.001 h, open at 3.209 h (observing slot start) and closed
at 3.366 h (slot end). Each one also carries the weather used in the exposure
and weather tables.

.. literalinclude:: examples/inputs_20260419/20260419.log
   :language: text

dimm.logs
~~~~~~~~~

There are no samples for this night, so the DIMM column shows ``n/a``. For
reference, lines look like this (UT time and seeing in arcsec, from a June
night):

.. literalinclude:: examples/inputs_20260419/dimm.logs
   :language: text

Report
------

DIMM shows ``n/a`` because no ``dimm.logs`` samples exist for that night. The
first nine exposures have no weather because the scheduler log has no weather
lines before about 3.0 h UT.

.. literalinclude:: examples/report_20260419.txt
   :language: text
