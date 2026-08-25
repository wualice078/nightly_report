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

Dome close resolution
---------------------

When ``night_date`` is known, ``build_dome_report.dome_summary`` picks the
last close time in this order:

1. **questctl** — ``CLOSE_CODE`` after manual ``closedome`` (exact UTC)
2. **scheduler** — ``dome : closed`` after the last exposure
3. **dome_daemon** — ``schmidt dome now closed`` (weather/safety)

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
