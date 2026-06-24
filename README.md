# LS4 nightly report

Python package that builds the Schmidt **LS4 nightly report** from obsplan,
`log.obs`, scheduler logs, dome daemon logs, and ESO DIMM seeing samples.

Production copy on the mountain: `observer@ls4-workstn:~/nightly_report`  
GitHub: https://github.com/wualice078/nightly_report

---

## Quick start

### Mountain (production)

```bash
cd ~/nightly_report
git pull

# Build report for the night that just ended (before 8 AM local → correct default date)
python3 send_report_email.py --build-only

# Or a specific UT night
python3 send_report_email.py --date YYYYMMDD --build-only

# Diagnostics
python3 check_night.py YYYYMMDD
```

Morning cron (observer account, **7 AM local**):

```
0 7 * * * /home/observer/nightly_report/send_morning_report.sh
```

Output: `~/nightly_report/reports/report_YYYYMMDD.txt` (and email if `mail` is available).

### Northwestern (practice / dev)

```bash
python3 send_report_email.py --date 20260530 --build-only --practice-fallback
python3 test_practice_nights.py
python3 test_seeing_samples.py
```

Optional dev poller (not used on mountain once `ntt_dome_status` DIMM hook is deployed):

```
*/15 * * * * /home/observer/nightly_report/poll_seeing_cron.sh
```

Use `poll_seeing_cron.sh` (not bare `python3 poll_seeing_log.py`) so cron gets Python 3.11+.

---

## Report sections

| Section | Source |
|---------|--------|
| Night summary | obsplan + log.obs + scheduler + dome_daemon |
| Fields | obsplan vs log.obs completion |
| Exposures | log.obs + scheduler weather + **DIMM** |
| Dome | scheduler `dome :` lines + dome_daemon fallback |
| Weather | scheduler log, 30-min UT grid |

Paths resolved by `night_paths.py` from `~/data/YYYYMMDD/`, `~/obsplans/`, and env overrides.

---

## DIMM / seeing

The exposure table **DIMM** column uses, in order:

1. `seeing` / `DIMM` in the scheduler log line (if present), else  
2. Nearest sample from **`dimm.logs`** (preferred on mountain) or `seeing.logs` (dev poller)

### Mountain (recommended — Kenneth)

Deploy scripts in [`mountain_deploy/`](mountain_deploy/README.md):

- `append_eso_dimm_log.csh` — `curl` ESO `dimm.last`, append to `$LS4_ROOT/logs/dimm.logs`
- `ntt_dome_status` — same as production script plus a hook that calls the helper (**stdout unchanged**)

Install as `ls4` on ls4-workstn:

```bash
cp ~/nightly_report/mountain_deploy/append_eso_dimm_log.csh $LS4_ROOT/bin/
cp ~/nightly_report/mountain_deploy/ntt_dome_status $LS4_ROOT/bin/
chmod +x $LS4_ROOT/bin/append_eso_dimm_log.csh
```

After the morning report, live `dimm.logs` is archived to `~/data/YYYYMMDD/logs/dimm.logs` and cleared.

**Note:** DIMM is logged when `ntt_dome_status` runs (weather server requests), not automatically per exposure. Per-exposure DIMM requires an additional scheduler hook — see `mountain_deploy/README.md`.

### Northwestern dev poller (optional)

`poll_seeing_log.py` / `poll_seeing_cron.sh` append to `~/logs/seeing.logs` every 15 minutes for pipeline testing. Not a substitute for mountain `dimm.logs`.

---

## Layout

```
nightly_report/
  README.md                 ← this file
  practice_config.py        paths, email, DIMM_LOG, data roots
  night_paths.py            resolve obsplan / logs for one UT night
  send_report_email.py      build (+ optional email)
  send_morning_report.sh    cron wrapper (7 AM)
  build_*.py                report sections
  seeing_samples.py         load dimm.logs / seeing.logs, join to exposures
  dome_daemon.py            parse dome_daemon.log
  check_night.py            one-night diagnostics
  mountain_deploy/          DIMM hooks for quest-src-lasilla (see README there)
  poll_seeing_*.py/sh       optional Northwestern ESO poller
  test_*.py                 unit / practice tests
  reports/                  generated report_YYYYMMDD.txt (gitignored)
```

---

## Environment variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `LS4_OBSERVER_ROOT` | `/home/observer` | Observer home |
| `LS4_DATA_ROOT` | `~/data`, … | Night data trees (`YYYYMMDD/logs/`) |
| `LS4_OBSPLAN_ROOT` | `~/obsplans` | Obsplan directories |
| `LS4_ROOT` | `~/quest-src-lasilla` | Quest tree; `logs/dimm.logs` |
| `LS4_DIMM_LOG` | `$LS4_ROOT/logs/dimm.logs` | ESO DIMM append log |
| `LS4_SEEING_LOG` | `~/logs/seeing.logs` | Dev poller log |
| `LS4_ESO_DIMM_URL` | ESO `dimm.last` HTTPS URL | |
| `LS4_DOME_DAEMON_LOG` | `~/logs/dome_daemon.log` | |
| `LS4_LIVE_ONLY` | `1` on mountain | Skip practice fallback |
| `LS4_PYTHON` | auto | Python for `poll_seeing_cron.sh` |

---

## Tests

```bash
python3 test_seeing_samples.py
python3 test_dome_daemon.py
python3 test_practice_nights.py
python3 test_practice_nights.py --date 20260530
```

---

## `get_ut_date` and cron timing

Morning cron at **7 AM local** uses `bin/get_ut_date`: before **8 AM local**, the night label is the **night that just ended**. After 8 AM local, the default date switches to the **next** night — use `--date YYYYMMDD` for manual runs of a finished night.
