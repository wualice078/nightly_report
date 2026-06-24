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

The exposure table **DIMM** column uses **only** `dimm.logs` (from `ntt_dome_status` on the mountain). Each exposure gets the **nearest** sample within **10 minutes** of its UT (FITS timestamp in `log.obs`). With ~60 s sampling, that is typically within ~30 s.

If `dimm.logs` is missing or empty, DIMM shows **n/a**; the rest of the report still generates.

### Mountain DIMM ingest (pending Kenneth — not in this repo)

The report reads `$LS4_ROOT/logs/dimm.logs`. That file is filled by a small addition to **`$LS4_ROOT/bin/ntt_dome_status`** in `quest-src-lasilla` (owned by `ls4`), not by anything in `nightly_report`.

**Stdout stays unchanged** (ASM FTP + OPEN/CLOSED). Insert **before** the final `if ( $ntt_status == "OPEN"` block:

```tcsh
# ESO DIMM seeing for nightly report — append to logs/dimm.logs (stdout unchanged).
set dimm_url = "https://www.ls.eso.org/lasilla/dimm/dimm.last"
if ($?LS4_ESO_DIMM_URL) set dimm_url = "$LS4_ESO_DIMM_URL"
set dimm_tmp = "/tmp/eso_dimm_${$}.tmp"
curl -sk --max-time 15 -o $dimm_tmp "$dimm_url" >& /dev/null
if ( $status == 0 && -s $dimm_tmp ) then
   set dimm_line = `cat $dimm_tmp`
   set dimm_arcsec = `echo "$dimm_line" | sed -n 's/.*[Ss]eeing=\([0-9.][0-9.]*\).*/\1/p'`
   if ( "$dimm_arcsec" == "" ) set dimm_arcsec = `echo "$dimm_line" | awk '{print $1}'`
   set dimm_ok = `echo "$dimm_arcsec" | awk '{ if ($1 > 0 && $1 < 10) print "ok" }'`
   if ( "$dimm_ok" == "ok" ) then
      set dimm_stamp = `date -u +"%Y-%m-%dT%H:%M:%SZ"`
      echo "$dimm_stamp $dimm_arcsec" >>! "$LS4_ROOT/logs/dimm.logs"
   endif
endif
rm -f $dimm_tmp
```

After Kenneth approves, apply in `quest-src-lasilla` / `$LS4_ROOT/bin/` as `ls4`. Samples arrive ~every 60 s while the weather path runs; the report joins the nearest sample to each exposure.

After the morning report, live `dimm.logs` is archived to `~/data/YYYYMMDD/logs/dimm.logs` and cleared.

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
