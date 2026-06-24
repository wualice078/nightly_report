# Mountain deploy: ESO DIMM in ntt_dome_status

Staging copies for **ls4-workstn** (`quest-src-lasilla` is owned by `ls4`; edit here, then `cp` into `$LS4_ROOT/bin/`).

Kenneth's pattern: fetch ESO [`dimm.last`](https://www.ls.eso.org/lasilla/dimm/dimm.last), append to `$LS4_ROOT/logs/dimm.logs`, **without changing** `ntt_dome_status` stdout (ASM FTP + OPEN/CLOSED unchanged).

See also the top-level [README](../README.md) for how `nightly_report` consumes `dimm.logs`.

**Per-exposure DIMM:** apply [scheduler_dimm.patch](scheduler_dimm.patch) and rebuild scheduler — see [SCHEDULER_DIMM.md](SCHEDULER_DIMM.md).

## Install on ls4-workstn (as `ls4` or with write access to quest-src-lasilla)

```bash
cp ~/nightly_report/mountain_deploy/append_eso_dimm_log.csh $LS4_ROOT/bin/
cp ~/nightly_report/mountain_deploy/ntt_dome_status $LS4_ROOT/bin/
chmod +x $LS4_ROOT/bin/append_eso_dimm_log.csh $LS4_ROOT/bin/ntt_dome_status
# also copy into weather_srv/ source tree if you use make install there
```

## Test append only

```tcsh
setenv LS4_ROOT ~/quest-src-lasilla   # or your LS4_ROOT
csh ~/nightly_report/mountain_deploy/append_eso_dimm_log.csh
tail -3 $LS4_ROOT/logs/dimm.logs
```

## Log format

```
2026-06-24T15:00:00Z 0.662
```

Parsed from ESO `dimm.last` lines like:
`2026-06-24T10:57:09: Current seeing=0.662`

## Collection frequency

This does **not** change when ASM `meteo.last` / `dome.last` are fetched, or when
scheduler TCS `weather` runs. DIMM is appended **only when `ntt_dome_status` runs**
(i.e. when `weather_srv.pl` gets a socket request).

For **per-exposure** DIMM, also call `append_eso_dimm_log.csh` from the scheduler
after each `log.obs` write — apply `mountain_deploy/scheduler_dimm.patch` and
`make install` in `ls4-scheduler` (see `mountain_deploy/SCHEDULER_DIMM.md`).
