#!/usr/bin/env python3
"""One-command night diagnostics (works in tcsh: python3 ~/nightly_report/check_night.py DATE)."""

from __future__ import annotations

import sys
from pathlib import Path

PACKAGE = Path(__file__).resolve().parent
sys.path.insert(0, str(PACKAGE))

from dome_daemon import count_daemon_closes_on_night, load_dome_daemon_closes
from night_paths import diagnose_live_night, discover_live_nights, resolve_night_paths
from practice_config import DIMM_LOG, DOME_DAEMON_LOG, QUESTCTL_LOG_DIR
from questctl_log import count_questctl_closes_on_night, load_questctl_closes, questctl_logs_for_night
from seeing_samples import load_dimm_samples


def main() -> int:
    date = sys.argv[1] if len(sys.argv) > 1 else None
    if not date:
        print("usage: python3 check_night.py YYYYMMDD")
        return 1

    print(f"=== night {date} ===\n")
    try:
        paths = resolve_night_paths(date, allow_practice_fallback=True)
        print(f"OK  source={paths.source}")
        print(f"    obsplan: {paths.obsplan}")
        print(f"    log.obs: {paths.log_obs}")
        print(f"    scheduler: {paths.scheduler_log}")
        print(f"    dimm.logs: {paths.dimm_log}")
        print(f"    questctl logs: {paths.questctl_log_dir}")
    except FileNotFoundError:
        print("MISSING live/practice inputs:")
        print(diagnose_live_night(date))
        return 1

    daemon = paths.dome_daemon_log or DOME_DAEMON_LOG
    print(f"\ndome_daemon: {daemon}")
    if daemon.is_file():
        closes = load_dome_daemon_closes(daemon)
        n = count_daemon_closes_on_night(daemon, date)
        print(f"  total closes in file: {len(closes)}")
        print(f"  closes for UT night {date}: {n}")
        if closes:
            print(f"  last close in file: {closes[-1].isoformat()}")
    else:
        print("  file not found")

    qdir = paths.questctl_log_dir or QUESTCTL_LOG_DIR
    print(f"\nquestctl: {qdir}")
    if qdir.is_dir():
        logs = questctl_logs_for_night(qdir, date)
        print(f"  questctl.*.log in dir: {len(logs)}", flush=True)
        for p in logs:
            try:
                mb = p.stat().st_size / (1024 * 1024)
                if mb >= 1:
                    print(f"  scanning {p.name} ({mb:.0f} MB) ...", flush=True)
            except OSError:
                pass
        closes = load_questctl_closes(qdir, date)
        print(f"  CLOSE_CODE signals for UT night {date}: {len(closes)}")
        if closes:
            print(f"  last CLOSE_CODE UTC: {closes[-1].isoformat()}")
    else:
        print("  directory not found")

    sched = paths.scheduler_log
    if sched and sched.is_file():
        import re

        pat = re.compile(r"dome\s*:\s*closed", re.I)
        hits = [ln for ln in sched.read_text(errors="replace").splitlines() if pat.search(ln)]
        print(f"\nscheduler dome:closed lines: {len(hits)}")
        if hits:
            print(f"  last: {hits[-1][:120]}")

    dimm_path = paths.dimm_log or DIMM_LOG
    print(f"\ndimm.logs: {dimm_path}")
    if dimm_path.is_file():
        samples = load_dimm_samples(dimm_path, date)
        print(f"  samples for UT night {date}: {len(samples)}")
        if samples:
            print(f"  first: UT {samples[0].ut:.3f} arcsec {samples[0].arcsec}")
            print(f"  last:  UT {samples[-1].ut:.3f} arcsec {samples[-1].arcsec}")
        elif dimm_path == DIMM_LOG:
            print("  (empty — cleared after morning report; check data/.../logs/dimm.logs)")
    else:
        print("  file not found (deploy ntt_dome_status DIMM hook on mountain)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
