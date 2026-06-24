# LS4 nightly report

Python package that builds the Schmidt **LS4 nightly report** from obsplan,
`log.obs`, scheduler logs, questctl / dome_daemon logs, and ESO DIMM seeing samples.

Production copy on the mountain: `observer@ls4-workstn:~/nightly_report`  
GitHub: https://github.com/wualice078/nightly_report

**Shell on the mountain is tcsh** — use `setenv` / `` set VAR = `cmd` `` (not bash `export` / `$()`).

---

## Quick start

### Mountain (production)

```tcsh
cd ~/nightly_report
git pull

# Night that just ended (before 8 AM local → get_ut_date is correct)
python3 send_report_email.py --build-only

# Specific UT night
python3 send_report_email.py --date YYYYMMDD --build-only

# Diagnostics for one night
set NIGHT = 20260624
python3 check_night.py $NIGHT
```

Morning cron (**observer** account, **7 AM local**):

```
0 7 * * * /home/observer/nightly_report/send_morning_report.sh
```

Output: `~/nightly_report/reports/report_YYYYMMDD.txt` (and email if `mail` is available).

### Northwestern (practice / dev)

```bash
python3 send_report_email.py --date 20260530 --build-only --practice-fallback
python3 test_practice_nights.py
python3 test_seeing_samples.py
python3 test_dome_daemon.py
python3 test_questctl_log.py
```

Optional dev poller (Northwestern only):

```
*/15 * * * * /home/observer/nightly_report/poll_seeing_cron.sh
```

---

## Mountain paths (`observer@ls4-workstn`)

| What | Path |
|------|------|
| Night data | `~/data/YYYYMMDD/logs/log.obs`, `…/YYYYMMDD.log` |
| Obsplans | `~/obsplans/YYYYMMDD/YYYYMMDD.obsplan` |
| **Dome close (primary)** | `~/logs/questctl.*.log` → `CLOSE_CODE` line |
| Dome close (weather/safety) | `~/logs/dome_daemon.log` |
| **DIMM (after deploy)** | `~/logs/dimm.logs` |
| Report package | `~/nightly_report` |

`LS4_ROOT` on the mountain is `/home/observer` (not the `quest-src-lasilla` subdirectory).
`start_questctl` runs from `cd $LS4_ROOT/logs`, so questctl and dome_daemon logs land in `~/logs/`.

---

## What populates the report (two separate deploys)

| Feature | Requires | When it works |
|---------|----------|----------------|
| **Dome close time** | `git pull` in `~/nightly_report` only | Next report for nights where observer ran `closedome` (questctl logs `CLOSE_CODE`) |
| **DIMM column** | Deploy [`mountain_deploy/ntt_dome_status`](mountain_deploy/ntt_dome_status) to `$LS4_ROOT/bin/` | After `ntt_dome_status` runs (~60 s cadence); until then column is `n/a` |

`git pull` on this repo does **not** install the DIMM hook — that is a manual copy into quest-src-lasilla.

---

## Report sections

| Section | Source |
|---------|--------|
| Night summary | obsplan + log.obs + dome close resolution |
| Fields | obsplan vs log.obs completion |
| Exposures | log.obs + scheduler weather + **DIMM** (nearest `dimm.logs` sample) |
| Dome | See [Dome close](#dome-close) below |
| Weather | scheduler log, 30-min UT grid |

Paths resolved by `night_paths.py` from `~/data/`, `~/obsplans/`, and env overrides.

---

## Dome close

### Priority (first match wins)

1. **questctl** — `signal code has been set to CLOSE_CODE <unix_epoch>` in `~/logs/questctl.*.log`  
   Normal end-of-night: observer runs **`closedome`** → signal to questctl → exact UTC timestamp.

2. **Scheduler** — `dome  : closed` on `print_telescope_status` lines in `~/data/YYYYMMDD/logs/YYYYMMDD.log`  
   Often **missing** (scheduler stops before the next TCS poll after close).

3. **dome_daemon** — `schmidt dome now closed` in `~/logs/dome_daemon.log`  
   Uncommon: weather/safety guard (La Silla domes closed, sun up). Report notes manual vs weather when possible.

### Verify on the mountain (tcsh)

```tcsh
set NIGHT = 20260624

grep -c 'dome  : closed' $HOME/data/$NIGHT/logs/$NIGHT.log
grep 'CLOSE_CODE' $LS4_ROOT/logs/questctl.*.log | tail -3
grep -i 'now closed' $LS4_ROOT/logs/dome_daemon.log | tail -3

cd ~/nightly_report
python3 check_night.py $NIGHT
```

### Why close was missing before

The old report only used scheduler `dome  : closed`, which usually never appears. Manual close is logged in **questctl**, which was not read until the questctl fallback was added.

---

## DIMM

The exposure **DIMM** column reads **only** `~/logs/dimm.logs` (live) or `~/data/YYYYMMDD/logs/dimm.logs` (archived after morning report).

- Each exposure time comes from the FITS timestamp in `log.obs`.
- The report picks the **nearest** `dimm.logs` sample within **10 minutes** UT.
- With ~60 s ingest cadence, offsets are typically under ~30 s.
- If `dimm.logs` is missing or empty, DIMM is **`n/a`** and the rest of the report still builds.

### Ingest (separate from this package)

Append samples inside `ntt_dome_status` when it runs — see [`mountain_deploy/`](mountain_deploy/).

```tcsh
diff -u $LS4_ROOT/bin/ntt_dome_status ~/nightly_report/mountain_deploy/ntt_dome_status
cp ~/nightly_report/mountain_deploy/ntt_dome_status $LS4_ROOT/bin/
chmod +x $LS4_ROOT/bin/ntt_dome_status
```

Requires write access to quest-src-lasilla (often as `ls4` after approval).

**Log format:** `2026-06-24T15:00:00Z 0.662`

After a successful morning report, live `dimm.logs` is copied to the night’s `logs/` directory and truncated.

### Northwestern dev poller (optional)

`poll_seeing_log.py` / `poll_seeing_cron.sh` append to `~/logs/seeing.logs` for pipeline testing. **Not** used on the mountain and **not** a substitute for `dimm.logs`.

---

## Layout

```
nightly_report/
  README.md
  practice_config.py        paths, email, env defaults
  night_paths.py            resolve obsplan / logs for one UT night
  send_report_email.py      build (+ optional email)
  send_morning_report.sh    cron wrapper (7 AM); sets mountain env vars
  build_*.py                report sections
  seeing_samples.py         load dimm.logs, nearest match per exposure
  questctl_log.py           parse questctl CLOSE_CODE close times
  dome_daemon.py            parse dome_daemon.log (weather/safety fallback)
  check_night.py            one-night diagnostics
  mountain_deploy/          staged ntt_dome_status DIMM hook
  poll_seeing_*.py/sh       optional Northwestern ESO poller
  test_*.py
  reports/                  generated report_YYYYMMDD.txt (gitignored)
```

---

## Environment variables

Set automatically by `send_morning_report.sh` on the mountain. Override only if your layout differs.

| Variable | Mountain default | Purpose |
|----------|------------------|---------|
| `LS4_OBSERVER_ROOT` | `/home/observer` | Observer home |
| `LS4_ROOT` | `/home/observer` | Quest runtime root; logs under `$LS4_ROOT/logs/` |
| `LS4_DATA_ROOT` | `/home/observer/data:/home/ls4/data` | Night data trees (`YYYYMMDD/logs/`) |
| `LS4_OBSPLAN_ROOT` | `/home/observer/obsplans:…` | Obsplan directories |
| `LS4_QUESTCTL_LOG_DIR` | `$LS4_ROOT/logs` | `questctl.*.log` (primary dome close) |
| `LS4_DOME_DAEMON_LOG` | `$LS4_ROOT/logs/dome_daemon.log` | Weather/safety dome close |
| `LS4_DIMM_LOG` | `$LS4_ROOT/logs/dimm.logs` | ESO DIMM append log |
| `LS4_ESO_DIMM_URL` | ESO `dimm.last` HTTPS URL | Used by `ntt_dome_status` hook |
| `LS4_SEEING_LOG` | `~/logs/seeing.logs` | Northwestern dev poller only |
| `LS4_LIVE_ONLY` | `1` | Skip practice fallback on mountain |
| `LS4_PYTHON` | auto | Python for cron scripts |

---

## Tests

```bash
python3 test_seeing_samples.py
python3 test_dome_daemon.py
python3 test_questctl_log.py
python3 test_practice_nights.py
python3 test_practice_nights.py --date 20260530
```

---

## `get_ut_date` and cron timing

Morning cron at **7 AM local** uses `bin/get_ut_date`:

- Before **8 AM local** → night label is the **night that just ended**.
- After **8 AM local** → default switches to the **next** night; use `--date YYYYMMDD` for a finished night.

---

## Troubleshooting

| Symptom | Check |
|---------|--------|
| No dome close | `grep CLOSE_CODE ~/logs/questctl.*.log` — need `closedome` with questctl running |
| DIMM all `n/a` | `ls ~/logs/dimm.logs` — deploy `mountain_deploy/ntt_dome_status` |
| Wrong night / missing data | `get_ut_date`; `ls ~/data/YYYYMMDD/logs/log.obs` |
| Permission errors | Run as **observer**, not `ls4` |
| tcsh errors | Use `setenv LS4_ROOT /home/observer`, not `export` |
