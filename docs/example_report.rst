Example report
==============

Full output for UT night **20260419**, an archived practice night from
``~/all_logs`` (Hydra cluster fields), built with:

.. code-block:: bash

   python3 make_report.py --date 20260419 --practice-fallback

Input logs
----------

Each log the report reads, where it was found for this night, and where it
lives on the mountain.

.. list-table::
   :header-rows: 1
   :widths: 20 30 25 25

   * - Log
     - Path used for this example
     - Path on the mountain
     - Used for
   * - obsplan
     - ``~/all_logs/20260419/20260419.obsplan``
     - ``~/data/20260419/logs/20260419.obsplan``
     - Planned fields: summary counts and field inventory
   * - log.obs
     - ``~/all_logs/20260419/log.obs``
     - ``~/data/20260419/logs/log.obs``
     - One line per exposure: exposures table, field inventory
   * - Scheduler log
     - ``~/all_logs/20260419/20260419.log``
     - ``~/data/20260419/logs/20260419.log``
     - Dome open/closed and weather (Temp, RH, wind)
   * - dimm.logs
     - ``~/logs/dimm.logs`` (no samples for this night)
     - ``~/data/20260419/logs/dimm.logs`` (archived each morning from ``~/logs/dimm.logs``)
     - DIMM seeing column
   * - dome_daemon log
     - ``~/recent_logs/logfiles/dome_daemon.log`` (no entries for this night)
     - ``~/logs/dome_daemon.log``
     - Preferred dome close time
   * - questctl logs
     - ``~/recent_logs/logfiles/questctl.*.log`` (no entries for this night)
     - ``~/logs/questctl.*.log``
     - Dome close from shutter bits or CLOSE_CODE

obsplan
~~~~~~~

The whole file. The report reads RA (hours), Dec (degrees), shutter
(``Y``/``S`` = science, otherwise calibration), the 6th column (exposures
needed), and the tag after ``#``.

.. literalinclude:: examples/inputs_20260419/20260419.obsplan
   :language: text
   :caption: ~/all_logs/20260419/20260419.obsplan

log.obs
~~~~~~~

First 4 of 22 lines. The report reads RA, Dec, shutter, the FITS timestamp
(``20260419015150`` gives UT 01:51:50) and the tag after ``#``.

.. literalinclude:: examples/inputs_20260419/log.obs
   :language: text
   :caption: ~/all_logs/20260419/log.obs (lines 1–4)

Scheduler log
~~~~~~~~~~~~~

The file is about 10,800 lines of scheduler output. The report only reads
status lines that start with ``UT :``. These three are where the dome state
changes: closed at 3.001 h, open at 3.209 h (observing slot start) and closed
at 3.366 h (slot end). Each one also carries the weather used in the exposure
and weather tables.

.. literalinclude:: examples/inputs_20260419/20260419.log
   :language: text
   :caption: ~/all_logs/20260419/20260419.log (lines 297, 3001, 5679)

dimm.logs
~~~~~~~~~

There are no samples for this night, so the DIMM column shows ``n/a``. For
reference, lines look like this (UT time and seeing in arcsec, from a June
night):

.. literalinclude:: examples/inputs_20260419/dimm.logs
   :language: text
   :caption: ~/logs/dimm.logs (lines 1–3, June 24)

dome_daemon log
~~~~~~~~~~~~~~~

No entries for this night, so the close time came from the scheduler log. For
reference, this is a close the report would use (local time, from June 1):

.. literalinclude:: examples/inputs_20260419/dome_daemon.log
   :language: text
   :caption: ~/recent_logs/logfiles/dome_daemon.log (lines 2613, 2616)

questctl logs
~~~~~~~~~~~~~

No entries for this night. For reference, the report reads the shutter bit
after each status check (``0`` closed, ``1`` open, ``2`` moving; the number
after ``status`` is the Unix time) and ``CLOSE_CODE`` lines from a manual
``closedome`` (from June 1, not consecutive lines):

.. literalinclude:: examples/inputs_20260419/questctl.log
   :language: text
   :caption: ~/recent_logs/logfiles/questctl.20260601181324.log (excerpt)

Report
------

DIMM shows ``n/a`` because no ``dimm.logs`` samples exist for that night. The
first nine exposures have no weather because the scheduler log has no weather
lines before about 3.0 h UT.

.. literalinclude:: examples/report_20260419.txt
   :language: text
   :caption: reports/report_20260419.txt
