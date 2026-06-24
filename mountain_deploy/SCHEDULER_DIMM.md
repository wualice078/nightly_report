# Scheduler hook: per-exposure ESO DIMM

## Architecture

All ESO fetch/parse logic lives in **`append_eso_dimm_log.csh`** only.

| Caller | When | Changes other weather? |
|--------|------|------------------------|
| **`scheduler`** (this patch) | After each `log.obs` line | **No** |
| **`ntt_dome_status`** | When `weather_srv.pl` runs | **No** — ASM `meteo.last` / `dome.last` unchanged; stdout unchanged |

Scheduler **TCS `weather`** (Temp/Humid/Wind in `YYYYMMDD.log`) is a separate path and is **not** modified.

## Apply on ls4-workstn

```bash
cd /home/ls4/code/ls4-scheduler
patch -p1 < ~/nightly_report/mountain_deploy/scheduler_dimm.patch
cd src && make install
# restarts scheduler / questctl as usual for your night setup
```

Requires `append_eso_dimm_log.csh` already in `$LS4_ROOT/bin/` (see [README.md](README.md)).

## What it does

After each exposure written to `log.obs`, the scheduler runs:

```csh
csh "$LS4_ROOT/bin/append_eso_dimm_log.csh" "<fits_filename>"
```

Appends to `$LS4_ROOT/logs/dimm.logs`, e.g.:

```
2026-06-24T05:39:50Z 0.662 20260530053950s
```

## Revert

```bash
cd /home/ls4/code/ls4-scheduler
patch -R -p1 < ~/nightly_report/mountain_deploy/scheduler_dimm.patch
cd src && make install
```
