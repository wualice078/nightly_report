# Staging: `ntt_dome_status` DIMM hook

Proposed change for `$LS4_ROOT/bin/ntt_dome_status` in `quest-src-lasilla` (not part of the nightly report runtime).

Adds an inline `curl` of ESO [`dimm.last`](https://www.ls.eso.org/lasilla/dimm/dimm.last) and appends one line to `$LS4_ROOT/logs/dimm.logs`. **Stdout is unchanged** (ASM FTP weather + OPEN/CLOSED for `weather_srv`).

The nightly report reads `dimm.logs` only; if the file is missing, the DIMM column is `n/a`.

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
