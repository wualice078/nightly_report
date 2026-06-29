# LS4 nightly report

Builds a text **nightly report** for Schmidt LS4 from obsplan, `log.obs`, scheduler logs, questctl / dome_daemon logs, and ESO DIMM samples.

**Production:** `observer@ls4-workstn:~/nightly_report`  
**GitHub:** https://github.com/wualice078/nightly_report

The mountain shell is **tcsh** (`setenv`, `` set VAR = `cmd` ``).

---

## Report contents

Each `report_YYYYMMDD.txt` has five sections:

| Section | What it shows |
|---------|----------------|
| **Night summary** | Field completion counts (observing + calibration), exposure count, dome first open / last close / total open time |
| **Field inventory** | Every obsplan field vs `log.obs`: COMPLETE / PARTIAL / NOT OBSERVED |
| **Exposures** | One row per exposure: UT, field tag, RA/Dec, Temp/RH/wind from scheduler log, **DIMM** arcsec, FITS stem |
| **Dome** | Open/close events from scheduler log; resolved close time; open intervals and total open hours |
| **Weather** | 30-minute UT grid of Temp, RH%, wind speed, wind direction from scheduler log |

**DIMM column:** nearest sample from `~/logs/dimm.logs` within 10 minutes of each exposure UT. Shows `n/a` if the log is missing or empty.

**Dome close time** (first match wins):

1. `~/logs/questctl.*.log` → `CLOSE_CODE` (manual `closedome`, exact UTC)
2. Scheduler log → `dome  : closed`
3. `~/logs/dome_daemon.log` → `schmidt dome now closed` (weather/safety)

See [examples/report_example.txt](examples/report_example.txt) for layout (abbreviated).

---

## Deploy

On **observer@ls4-workstn**:

```tcsh
cd ~/nightly_report
git pull
```

Morning cron:

```
0 7 * * * /home/observer/nightly_report/send_morning_report.sh
```

### DIMM column (optional)

The report reads `~/logs/dimm.logs`. To fill it, add the DIMM block from [`mountain_deploy/ntt_dome_status`](mountain_deploy/ntt_dome_status) into `$LS4_ROOT/bin/ntt_dome_status` — after the date-tolerance check, before the final `echo … OPEN|CLOSED` line. Stdout to the weather server stays the same; the script appends lines like `2026-06-24T15:00:00Z 0.662` to `~/logs/dimm.logs` when it runs (~60 s). You do not need to create that file by hand.

---

## Mountain paths

| Data | Path |
|------|------|
| Night data | `~/data/YYYYMMDD/logs/log.obs`, `…/YYYYMMDD.log` |
| Obsplan | `~/obsplans/YYYYMMDD/YYYYMMDD.obsplan` |
| Dome close (primary) | `~/logs/questctl.*.log` |
| Dome close (fallback) | `~/logs/dome_daemon.log` |
| DIMM samples | `~/logs/dimm.logs` |
| Report output | `~/nightly_report/reports/report_YYYYMMDD.txt` |

`LS4_ROOT=/home/observer` on the mountain.

---

## Commands

All commands below assume `cd ~/nightly_report` (mountain) or the repo root (Northwestern).

### Build a report

```tcsh
# Default night (get_ut_date)
python3 send_report_email.py --build-only

# Specific UT night (use this after ~8 AM local if get_ut_date already flipped)
python3 send_report_email.py --date YYYYMMDD --build-only

# Build and email
python3 send_report_email.py --date YYYYMMDD --to you@example.edu

# Northwestern: use practice archive when live data missing
python3 send_report_email.py --date 20260530 --build-only --practice-fallback
```

### Morning cron (manual run)

```tcsh
~/nightly_report/send_morning_report.sh
```

Log: `~/nightly_report/reports/cron_morning.log`

### Diagnostics

```tcsh
set NIGHT = 20260624
python3 check_night.py $NIGHT
```

Shows which input files exist, scheduler `dome:closed` count, questctl `CLOSE_CODE` count, dome_daemon closes, and dimm.logs sample count.

### Batch build (Northwestern / testing)

```bash
python3 build_all_reports.py --practice-fallback
python3 build_all_reports.py --date 20260529 --date 20260530 --build-only
```

### Tests

```bash
python3 test_practice_nights.py
python3 test_practice_nights.py --date 20260530
python3 test_dome_daemon.py
python3 test_questctl_log.py
python3 test_seeing_samples.py
```

### Verify dome close on the mountain

```tcsh
grep 'CLOSE_CODE' $LS4_ROOT/logs/questctl.*.log | tail -3
grep -c 'dome  : closed' $HOME/data/YYYYMMDD/logs/YYYYMMDD.log
```

### Verify DIMM

```tcsh
tail -5 $LS4_ROOT/logs/dimm.logs
```

---

## How it works

```
obsplan + log.obs + scheduler log + questctl/dome_daemon/dimm logs
        │
        ▼
  night_paths.py          resolve paths for one UT night
        │
        ▼
  send_report_email.py    assemble sections → report_YYYYMMDD.txt
        │
        ├── build_summary.py       field counts + dome times
        ├── compare_obsplan_log.py field inventory
        ├── build_exposure_report.py  exposures + weather + DIMM join
        ├── build_dome_report.py   dome timeline + close resolution
        └── build_weather_report.py  30-min weather grid
```

After a successful **morning** live report, `dimm.logs` is archived to `~/data/YYYYMMDD/logs/dimm.logs` and the live file is truncated.

---

## Repository layout

| File | Role |
|------|------|
| `send_report_email.py` | Main entry: build report, optional email, optional dimm.logs cleanup |
| `send_morning_report.py` | Cron entry point |
| `send_morning_report.sh` | Cron wrapper; exports mountain env vars |
| `night_paths.py` | Find obsplan, log.obs, scheduler log, dimm.logs for one night |
| `practice_config.py` | Paths, email recipient, env defaults |
| `compare_obsplan_log.py` | Parse obsplan / log.obs; field completion |
| `build_summary.py` | Night summary section |
| `build_exposure_report.py` | Exposure table with weather + DIMM |
| `build_dome_report.py` | Dome section; questctl → scheduler → dome_daemon |
| `build_weather_report.py` | 30-min weather grid |
| `weather_samples.py` | Parse scheduler weather + dome status lines |
| `questctl_log.py` | Parse questctl `CLOSE_CODE` timestamps |
| `dome_daemon.py` | Parse dome_daemon.log closes |
| `seeing_samples.py` | Load dimm.logs; nearest match per exposure |
| `check_night.py` | One-night diagnostics |
| `build_all_reports.py` | Batch-build many nights |
| `mountain_deploy/ntt_dome_status` | Reference snippet to paste into `$LS4_ROOT/bin/ntt_dome_status` for DIMM |
| `examples/report_example.txt` | Sample report layout |
| `test_*.py` | Unit and practice-night tests |

---

## Environment variables

Set by `send_morning_report.sh` on the mountain unless overridden.

| Variable | Default (mountain) | Purpose |
|----------|-------------------|---------|
| `LS4_OBSERVER_ROOT` | `/home/observer` | Observer home |
| `LS4_ROOT` | `/home/observer` | Quest runtime; logs under `$LS4_ROOT/logs/` |
| `LS4_DATA_ROOT` | `/home/observer/data:…` | Night data directories |
| `LS4_OBSPLAN_ROOT` | `/home/observer/obsplans:…` | Obsplan directories |
| `LS4_QUESTCTL_LOG_DIR` | `$LS4_ROOT/logs` | questctl.*.log |
| `LS4_DOME_DAEMON_LOG` | `$LS4_ROOT/logs/dome_daemon.log` | dome_daemon fallback |
| `LS4_DIMM_LOG` | `$LS4_ROOT/logs/dimm.logs` | Live DIMM samples |
| `LS4_LIVE_ONLY` | `1` | Skip practice fallback |
| `LS4_PYTHON` | auto | Python for cron |

---

## Night date default

`send_report_email.py` with no `--date` calls `get_ut_date` (same as the rest of LS4). Morning cron at 7 AM runs before that label flips (~8 AM local). To rebuild a specific finished night anytime: `--date YYYYMMDD`.

---

## Troubleshooting

| Symptom | Check |
|---------|--------|
| No dome close | `grep CLOSE_CODE ~/logs/questctl.*.log` |
| DIMM all `n/a` | `tail ~/logs/dimm.logs` — add DIMM block to `ntt_dome_status` (see Deploy) |
| Missing night data | `ls ~/data/YYYYMMDD/logs/log.obs` |
| Wrong user | Run as **observer**, not `ls4` |
| tcsh syntax errors | Use `setenv` / `` set N = `get_ut_date` ``, not bash `export` |
