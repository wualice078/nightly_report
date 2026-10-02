Architecture
============

Data flow
---------

.. code-block:: text

   obsplan + log.obs + scheduler log + questctl/dome_daemon/dimm logs
           │
           ▼
     lib/night_paths.py       resolve paths for one UT night
           │
           ▼
     make_report.py           assemble sections → report_YYYYMMDD.txt
           │
           ├── build/build_summary.py          field counts + dome times
           ├── build/compare_obsplan_log.py    field inventory
           ├── build/build_exposure_report.py  exposures + weather + DIMM
           ├── build/build_dome_report.py      dome timeline + close resolution
           └── build/build_weather_report.py   30-min weather grid

Input logs
----------

All per-night files live in ``~/data/YYYYMMDD/logs/`` on the mountain.

.. list-table::
   :header-rows: 1
   :widths: 25 30 45

   * - File
     - Written by
     - If missing
   * - ``YYYYMMDD.log`` (scheduler log)
     - ``~/scheduler/bin/scheduler``, started by ``obs_control_script``
       with its output redirected to this file
     - No weather; dome times come from dome_daemon / questctl only
   * - ``log.obs``
     - scheduler
     - Exposures section is skipped; summary shows ``n/a``
   * - ``YYYYMMDD.obsplan``
     - copied in by ``obs_control_script``
     - Field inventory is skipped; summary shows ``n/a``
   * - ``dimm.logs``
     - ``ntt_dome_status`` (archived here by the morning run)
     - DIMM column shows ``n/a``
   * - ``dome_daemon.log``, ``questctl.*.log``
     - dome_daemon, questctl (in ``~/logs``)
     - Dome close falls back to the scheduler log

The report is built if **any** of the scheduler log, ``log.obs``, or obsplan
exists. Only when all three are missing does it write a short
``Status: DATA MISSING`` report.

The weather grid normally spans the observing window (first open / exposure to
last close / exposure). If there is no window, e.g. the dome stayed shut for
weather, it shows every weather sample in the scheduler log instead.

Dome close resolution
---------------------

When ``night_date`` is known, ``build_dome_report.dome_summary`` picks the
last close time in this order:

1. **dome_daemon** — ``schmidt dome now closed`` (confirmed close)
2. **questctl shutter bits** — TCS ``dome status bit`` ``1→2→0``
   (``2`` = opening/closing). Usual end-of-night close while questctl is
   still polling during ``stow_telescope``.
3. **questctl** — ``CLOSE_CODE`` after manual ``closedome`` (command time)
4. **scheduler** — ``dome : closed`` after the last exposure

Night timeline
--------------

UT times after local midnight are mapped to a continuous 24–48 h timeline
(``lib.weather_samples.to_night_ut``) so exposures, weather, and dome events
sort and join correctly across midnight.

DIMM cleanup
------------

After a successful **morning** live report (no explicit ``--date``),
``make_report.py`` archives ``dimm.logs`` to ``data/YYYYMMDD/logs/dimm.logs``
and truncates the live file.
