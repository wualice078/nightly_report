#!/usr/bin/env python3
"""ESO DIMM samples from $LS4_ROOT/logs/dimm.logs (ntt_dome_status / append_eso_dimm_log.csh)."""

from __future__ import annotations

import re
import ssl
import subprocess
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from dome_daemon import belongs_to_ut_night, utc_to_ut_decimal
from practice_config import ESO_SEEING_URL, SEEING_LOG
from weather_samples import to_night_ut

SEEING_LOG_LINE = re.compile(
    r"^(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})Z\s+([\d.]+)\s*$"
)
# Cron polls every 15 min — match weather join window (10 min).
SEEING_JOIN_TOL = 10.0 / 60.0


@dataclass(frozen=True)
class SeeingSample:
    ut: float
    arcsec: str


def _fetch_seeing_text(url: str, timeout: float) -> str | None:
    req = urllib.request.Request(url, headers={"User-Agent": "ls4-nightly-report/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read().decode("utf-8", errors="replace").strip()
    except urllib.error.URLError as exc:
        if "CERTIFICATE" not in str(exc):
            return None
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        try:
            with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
                return resp.read().decode("utf-8", errors="replace").strip()
        except (OSError, urllib.error.URLError):
            pass
    except OSError:
        pass
    try:
        r = subprocess.run(
            ["curl", "-sk", "--max-time", str(int(timeout)), url],
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:
        return None
    if r.returncode != 0:
        return None
    return (r.stdout or "").strip() or None


def fetch_eso_seeing_arcsec(url: str = ESO_SEEING_URL, timeout: float = 15.0) -> float | None:
    """Read current DIMM seeing (arcsec) from ESO seeing.last."""
    text = _fetch_seeing_text(url, timeout)
    if not text:
        return None
    try:
        val = float(text.split()[0])
    except ValueError:
        return None
    if val <= 0.0 or val > 10.0:
        return None
    return val


def format_arcsec(val: float) -> str:
    return f"{val:.3f}"


def append_seeing_sample(log_path: Path = SEEING_LOG, url: str = ESO_SEEING_URL) -> bool:
    """Fetch ESO seeing and append one UTC-stamped line. Returns True on success."""
    val = fetch_eso_seeing_arcsec(url)
    if val is None:
        return False
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    line = f"{stamp} {format_arcsec(val)}\n"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as fh:
        fh.write(line)
    return True


def _parse_log_line(line: str) -> tuple[datetime, str] | None:
    m = SEEING_LOG_LINE.match(line.strip())
    if not m:
        return None
    try:
        utc_dt = datetime.strptime(m.group(1), "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc)
        arcsec = format_arcsec(float(m.group(2)))
    except ValueError:
        return None
    return utc_dt, arcsec


def load_seeing_samples(path: Path | None, night_date: str) -> list[SeeingSample]:
    if path is None or not path.is_file():
        return []
    out: list[SeeingSample] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        parsed = _parse_log_line(line)
        if not parsed:
            continue
        utc_dt, arcsec = parsed
        if not belongs_to_ut_night(utc_dt, night_date):
            continue
        out.append(SeeingSample(utc_to_ut_decimal(utc_dt), arcsec))
    out.sort(key=lambda s: s.ut)
    return out


def nearest_seeing_on_night(
    night_ut: float,
    samples: list[SeeingSample],
    anchor: float,
    max_delta: float = SEEING_JOIN_TOL,
) -> SeeingSample | None:
    """Nearest ESO seeing sample on the continuous night timeline."""
    best: SeeingSample | None = None
    best_d = max_delta + 1.0
    for s in samples:
        d = abs(to_night_ut(s.ut, anchor) - night_ut)
        if d <= max_delta and d < best_d:
            best, best_d = s, d
    return best


def dimm_for_exposure(
    night_ut: float,
    anchor: float,
    scheduler_seeing: str | None,
    eso_samples: list[SeeingSample],
) -> str:
    if scheduler_seeing:
        return scheduler_seeing
    hit = nearest_seeing_on_night(night_ut, eso_samples, anchor)
    return hit.arcsec if hit else "n/a"


def _lines_for_night(log_path: Path, night_date: str) -> list[str]:
    if not log_path.is_file():
        return []
    out: list[str] = []
    for line in log_path.read_text(encoding="utf-8", errors="replace").splitlines():
        parsed = _parse_log_line(line)
        if not parsed:
            continue
        utc_dt, _ = parsed
        if belongs_to_ut_night(utc_dt, night_date):
            out.append(line.strip())
    return out


def archive_and_clear_seeing_log(
    log_path: Path,
    night_date: str,
    archive_path: Path | None = None,
) -> int:
    """
    After a nightly report: copy this night's samples to the night log dir, then
    truncate the live polling file so it does not grow without bound.

    Returns number of lines archived.
    """
    lines = _lines_for_night(log_path, night_date)
    if archive_path is not None and lines:
        archive_path.parent.mkdir(parents=True, exist_ok=True)
        archive_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    if log_path.is_file():
        log_path.write_text("", encoding="utf-8")
    return len(lines)
