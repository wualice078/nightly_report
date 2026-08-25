LS4 Nightly Report
==================

Text nightly reports for Schmidt LS4, built from obsplan, ``log.obs``, scheduler
logs, questctl / dome_daemon logs, and ESO DIMM samples.

.. toctree::
   :maxdepth: 2
   :caption: Contents

   usage
   architecture
   api/index

Quick start
-----------

On the mountain (``observer@ls4-workstn``)::

   cd ~/nightly_report
   python3 make_report.py --date YYYYMMDD

Morning cron runs ``cron_morning.sh``, which invokes ``make_report.py --morning``.

Report sections
---------------

1. **Night summary** — field completion counts and dome times
2. **Field inventory** — obsplan vs ``log.obs`` (COMPLETE / PARTIAL / NOT OBSERVED)
3. **Exposures** — one row per exposure with weather and DIMM
4. **Dome** — open/close timeline and resolved close time
5. **Weather** — 30-minute UT grid from the scheduler log

Indices
-------

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
