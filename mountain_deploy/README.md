# Mountain deploy: ESO DIMM in ntt_dome_status

Staging copy for **ls4-workstn** (`quest-src-lasilla` is owned by `ls4`; edit here, then `cp` into `$LS4_ROOT/bin/`).

[`ntt_dome_status`](ntt_dome_status) is production script plus an inline block that `curl`s ESO [`dimm.last`](https://www.ls.eso.org/lasilla/dimm/dimm.last) and appends to `$LS4_ROOT/logs/dimm.logs`. **Stdout is unchanged** (ASM FTP + OPEN/CLOSED for `weather_srv`).

See the top-level [README](../README.md) for how `nightly_report` consumes `dimm.logs`.

## Install on ls4-workstn (as `ls4`)

```bash
diff -u $LS4_ROOT/bin/ntt_dome_status ~/nightly_report/mountain_deploy/ntt_dome_status
cp ~/nightly_report/mountain_deploy/ntt_dome_status $LS4_ROOT/bin/
chmod +x $LS4_ROOT/bin/ntt_dome_status
# also copy into weather_srv/ source tree if you use make install there
```

## Test on mountain

```tcsh
setenv LS4_ROOT ~/quest-src-lasilla   # or your LS4_ROOT
$LS4_ROOT/bin/ntt_dome_status
tail -3 $LS4_ROOT/logs/dimm.logs
```

## Log format

```
2026-06-24T15:00:00Z 0.662
```

Parsed from ESO `dimm.last` lines like:
`2026-06-24T10:57:09: Current seeing=0.662`

## Collection frequency

DIMM is appended whenever `ntt_dome_status` runs — typically **~every 60 s** while `dome_daemon` is up at night (`weather` → `weather_srv` → `ntt_dome_status`). That is enough for the nightly report (nearest sample within 10 min per exposure).

No scheduler patch required.
