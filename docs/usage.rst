Usage
=====

Build one report
----------------

.. code-block:: bash

   python3 make_report.py --date YYYYMMDD
   python3 make_report.py --morning          # email configured recipient
   python3 make_report.py --practice-fallback

Diagnostics
-----------

.. code-block:: bash

   python3 tools/check_night.py YYYYMMDD

Batch build (Northwestern / testing)
------------------------------------

.. code-block:: bash

   python3 tools/build_all_reports.py
   python3 tools/build_all_reports.py --date 20260529 --date 20260530

Environment variables
---------------------

See ``README.md`` for the full list. Common overrides:

+----------------------+----------------------------------+
| Variable             | Purpose                          |
+======================+==================================+
| ``LS4_DATA_ROOT``    | Colon-separated night data roots |
| ``LS4_OBSPLAN_ROOT`` | Obsplan search paths             |
| ``LS4_PRACTICE_ROOT``| Archived nights for testing      |
| ``LS4_LIVE_ONLY``    | Skip practice fallback (mountain)|
| ``LS4_DIMM_LOG``     | Live DIMM sample file            |
+----------------------+----------------------------------+

Mountain paths (default)
------------------------

+------------------+------------------------------------------+
| Data             | ``~/data/YYYYMMDD/logs/log.obs``         |
| Obsplan          | ``~/obsplans/YYYYMMDD/YYYYMMDD.obsplan`` |
| Scheduler log    | ``~/data/YYYYMMDD/logs/YYYYMMDD.log``    |
| questctl         | ``~/logs/questctl.*.log``                |
| dome_daemon      | ``~/logs/dome_daemon.log``               |
| DIMM             | ``~/logs/dimm.logs``                     |
| Report output    | ``~/nightly_report/reports/``            |
+------------------+------------------------------------------+

Tests
-----

.. code-block:: bash

   python3 tests/test_practice_nights.py
   python3 tests/test_dome_daemon.py
   python3 tests/test_questctl_log.py
   python3 tests/test_seeing_samples.py
