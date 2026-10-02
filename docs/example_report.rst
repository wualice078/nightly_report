Example report
==============

Full output for UT night **20260419**, an archived practice night from
``~/all_logs`` (Hydra cluster fields), built with:

.. code-block:: bash

   python3 make_report.py --date 20260419 --practice-fallback

DIMM shows ``n/a`` because no ``dimm.logs`` samples exist for that night. The
first nine exposures have no weather because the scheduler log has no weather
lines before about 3.0 h UT.

.. literalinclude:: examples/report_20260419.txt
   :language: text
