# Staging: `ntt_dome_status` DIMM hook

Proposed change for `$LS4_ROOT/bin/ntt_dome_status` in `quest-src-lasilla`. **Not** part of the nightly report runtime and **not** applied by `git pull` on this repo.

## What it does

- Adds an inline `curl` of ESO [`dimm.last`](https://www.ls.eso.org/lasilla/dimm/dimm.last).
- Appends one line to `$LS4_ROOT/logs/dimm.logs` (~every 60 s when `ntt_dome_status` runs).
- **Stdout is unchanged** (ASM FTP weather + OPEN/CLOSED for `weather_srv`).

The nightly report reads `dimm.logs` only. Until this is deployed, the DIMM column shows **`n/a`** (the rest of the report still builds).

**Dome close does not depend on this script** — dome close comes from questctl logs after `git pull` on `nightly_report`.

## Install (requires write access to quest-src-lasilla)

```bash
diff -u $LS4_ROOT/bin/ntt_dome_status ~/nightly_report/mountain_deploy/ntt_dome_status
cp ~/nightly_report/mountain_deploy/ntt_dome_status $LS4_ROOT/bin/
chmod +x $LS4_ROOT/bin/ntt_dome_status
```

## Log format

```
2026-06-24T15:00:00Z 0.662
```

## Sampling

Whenever `ntt_dome_status` runs (typically ~every 60 s while `dome_daemon` is up), a sample is appended. The report matches the nearest sample to each exposure UT within 10 minutes.
