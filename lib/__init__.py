"""
Shared libraries for LS4 nightly reports.

Modules:

    practice_config   Environment defaults and mountain paths
    night_paths       Resolve obsplan / log.obs / scheduler log for one UT night
    weather_samples   Scheduler weather and dome event parsing
    questctl_log      Dome close from questctl shutter bits (1→2→0) and CLOSE_CODE
    dome_daemon       Preferred dome close from dome_daemon.log
    seeing_samples    ESO DIMM samples from dimm.logs
"""
