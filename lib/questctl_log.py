#!/usr/bin/env python3
"""
Parse dome open/close times from questctl logs.

Primary signal (TCS shutter field, echoed as ``dome status bit is N``):

    0 = closed
    1 = open
    2 = opening or closing (questctl labels this "unknown")

A real close is ``1 → (optional 2) → 0``. Isolated ``0 → 2 → 0`` blips while
already closed are ignored. Unix time comes from nearby
``checking telescope status <epoch>`` lines.

Fallback: ``CLOSE_CODE <epoch>`` after a manual ``closedome`` (signal 10).

Questctl log filenames reflect process **start** time; a single log may span
weeks. Always filter events by UTC timestamp, not filename. Large logs are
seeked to the night's epoch window so reports do not rescan months of history.
"""

from __future__ import annotations

import re
import subprocess
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from pathlib import Path

from lib.dome_daemon import belongs_to_ut_night, utc_to_ut_decimal
from lib.weather_samples import night_anchor_ut, to_night_ut

CLOSE_CODE = re.compile(r"signal code has been set to CLOSE_CODE\s+(\d+)")
BIT_LINE = re.compile(r"dome status bit is (\d+)")
STATUS_TS = re.compile(r"checking telescope status (\d{9,})")
STATUS_TS_BYTES = re.compile(br"checking telescope status (\d{9,})")
LOG_START = re.compile(r"^questctl\.(\d{8})\d+\.log$")
# Keep at most this many newest overlapping logs per directory.
_MAX_LOGS_PER_DIR = 3
# Files bigger than this are byte-seeked to the night window first.
_SEEK_MIN_BYTES = 1_000_000


def _night_epoch_bounds(night_date: str) -> tuple[int, int]:
    """
    Unix epoch ``[lo, hi]`` covering UT night ``night_date``.

    Starts at 12:00 UT on the **previous** calendar day so shutter state from
    the prior evening is available for ``1→0`` detection; event lists are still
    filtered with :func:`belongs_to_ut_night`. ``hi`` is 18:00 UT the day after
    ``night_date``.
    """
    d0 = datetime.strptime(night_date, "%Y%m%d").replace(tzinfo=timezone.utc)
    lo = int((d0 - timedelta(hours=12)).timestamp())  # previous day 12:00 UT
    hi = int((d0 + timedelta(days=1, hours=18)).timestamp())
    return lo, hi


def questctl_logs_for_night(log_dir: Path | None, night_date: str) -> list[Path]:
    """
    Return ``questctl.*.log`` files that could contain events for ``night_date``.

    Drops logs whose filename start date is after the UT night ends, and logs
    whose mtime is before the night starts (already finished earlier). Among
    the rest, keeps the newest few by start date — a long-running process log
    is included when its mtime reaches into the night.
    """
    if log_dir is None or not log_dir.is_dir():
        return []
    if not night_date:
        return sorted(log_dir.glob("questctl.*.log"))
    try:
        d0 = datetime.strptime(night_date, "%Y%m%d")
    except ValueError:
        return sorted(log_dir.glob("questctl.*.log"))
    night_end = d0 + timedelta(days=2)
    night_start_ts = (d0.replace(tzinfo=timezone.utc) + timedelta(hours=12)).timestamp()

    scored: list[tuple[datetime, Path]] = []
    for path in log_dir.glob("questctl.*.log"):
        m = LOG_START.match(path.name)
        if not m:
            continue
        try:
            started = datetime.strptime(m.group(1), "%Y%m%d")
        except ValueError:
            continue
        if started > night_end:
            continue
        try:
            mtime = path.stat().st_mtime
        except OSError:
            continue
        # Finished before this night began → cannot hold tonight's events.
        if mtime < night_start_ts - 3600:
            continue
        scored.append((started, path))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [p for _started, p in scored[:_MAX_LOGS_PER_DIR]]


def extra_questctl_log_dirs(primary: Path | None) -> list[Path]:
    """
    Directories to scan for shutter bits.

    Always includes ``primary``. Adds practice / sample-diagnostics archives
    only when ``primary`` is the practice questctl log dir (not the live
    mountain ``~/logs`` path), so mountain reports do not scan archives.
    """
    from lib.practice_config import OBSERVER_ROOT, PRACTICE_QUESTCTL_LOG_DIR

    archive = OBSERVER_ROOT / "2026_recent_logs" / "sample_diagnostics_logs"

    def _key(p: Path) -> str:
        try:
            return str(p.resolve()) if p.exists() else str(p)
        except OSError:
            return str(p)

    use_archives = primary is not None and _key(primary) == _key(PRACTICE_QUESTCTL_LOG_DIR)
    extras = [archive] if use_archives else []

    out: list[Path] = []
    seen: set[str] = set()
    for d in [primary, *extras]:
        if d is None:
            continue
        try:
            ok = d.is_dir()
        except OSError:
            ok = False
        if not ok:
            continue
        key = _key(d)
        if key in seen:
            continue
        seen.add(key)
        out.append(d)
    return out


def _grep_lines(path: Path, pattern: str) -> list[str]:
    """Return matching lines via grep, or stream the file if grep is unavailable."""
    try:
        r = subprocess.run(
            ["grep", "-E", pattern, str(path)],
            capture_output=True,
            text=True,
            errors="replace",
        )
        if r.stdout:
            return r.stdout.splitlines()
        return []
    except (OSError, FileNotFoundError):
        pass
    out: list[str] = []
    with path.open(encoding="utf-8", errors="replace") as fh:
        cre = re.compile(pattern)
        for line in fh:
            if cre.search(line):
                out.append(line.rstrip("\n"))
    return out


def _close_code_lines(path: Path):
    """Yield lines containing ``CLOSE_CODE`` without loading the whole log."""
    yield from _grep_lines(path, "CLOSE_CODE")


def _seek_near_epoch(path: Path, epoch_lo: int) -> int:
    """
    Byte offset near the first ``checking telescope status`` at/after ``epoch_lo``.

    Binary-searches a large chronological log so night rebuilds do not reread
    months of earlier polls. Returns 0 when seeking is unnecessary or fails.
    """
    try:
        size = path.stat().st_size
    except OSError:
        return 0
    if size < _SEEK_MIN_BYTES:
        return 0

    lo_off, hi_off = 0, size
    best = 0
    try:
        with path.open("rb") as fh:
            for _ in range(48):
                if hi_off - lo_off < 8192:
                    break
                mid = (lo_off + hi_off) // 2
                fh.seek(mid)
                fh.readline()  # align to next full line
                aligned = fh.tell()
                epoch: int | None = None
                for _ in range(400):
                    line = fh.readline()
                    if not line:
                        break
                    m = STATUS_TS_BYTES.search(line)
                    if m:
                        epoch = int(m.group(1))
                        break
                if epoch is None:
                    # No status in this slice — move earlier.
                    hi_off = mid
                    continue
                if epoch < epoch_lo:
                    lo_off = fh.tell()
                    best = lo_off
                else:
                    hi_off = aligned
                    best = aligned
    except OSError:
        return 0
    return best


def _bit_changes_from_file(
    path: Path,
    *,
    epoch_lo: int | None = None,
    epoch_hi: int | None = None,
) -> list[tuple[datetime, int]]:
    """
    Collapse ``dome status bit`` lines into timestamped state changes.

    Each bit sample uses the most recent ``checking telescope status`` epoch;
    bits before the first epoch wait for the next one. When ``epoch_lo`` /
    ``epoch_hi`` are set, seeks near ``epoch_lo`` on large files and stops
    once timestamps pass ``epoch_hi``.
    """
    start_off = _seek_near_epoch(path, epoch_lo) if epoch_lo is not None else 0
    last_ts: int | None = None
    pending_before_ts: list[int] = []
    events: list[tuple[datetime, int]] = []
    prev: int | None = None

    def _emit(ts: int, bit: int) -> None:
        nonlocal prev
        if bit == prev:
            return
        if epoch_lo is not None and ts < epoch_lo:
            prev = bit
            return
        if epoch_hi is not None and ts > epoch_hi:
            return
        events.append((datetime.fromtimestamp(ts, tz=timezone.utc), bit))
        prev = bit

    try:
        with path.open(encoding="utf-8", errors="replace") as fh:
            if start_off:
                fh.seek(start_off)
                fh.readline()  # drop possible partial line after seek
            for line in fh:
                if "checking telescope status" in line:
                    m = STATUS_TS.search(line)
                    if not m:
                        continue
                    last_ts = int(m.group(1))
                    if epoch_hi is not None and last_ts > epoch_hi:
                        break
                    for bit in pending_before_ts:
                        _emit(last_ts, bit)
                    pending_before_ts.clear()
                    continue
                if "dome status bit is" not in line:
                    continue
                m = BIT_LINE.search(line)
                if not m:
                    continue
                bit = int(m.group(1))
                if last_ts is None:
                    pending_before_ts.append(bit)
                else:
                    _emit(last_ts, bit)
    except OSError:
        return []

    return events


def _questctl_bit_log_paths(
    log_dir: Path | None,
    *,
    extra: bool = True,
    night_date: str | None = None,
) -> list[Path]:
    """Return unique questctl log paths to scan for shutter bits."""
    dirs = extra_questctl_log_dirs(log_dir) if extra else (
        [log_dir] if log_dir is not None else []
    )
    out: list[Path] = []
    seen: set[str] = set()
    for d in dirs:
        if d is None or not d.is_dir():
            continue
        paths = (
            questctl_logs_for_night(d, night_date)
            if night_date
            else sorted(d.glob("questctl.*.log"))
        )
        for path in paths:
            try:
                key = str(path.resolve()) if path.exists() else str(path)
            except OSError:
                key = str(path)
            if key in seen:
                continue
            seen.add(key)
            out.append(path)
    return out


@lru_cache(maxsize=64)
def _bit_changes_cached(
    path_str: str,
    mtime_ns: int,
    size: int,
    epoch_lo: int | None,
    epoch_hi: int | None,
) -> tuple[tuple[datetime, int], ...]:
    """Cached shutter-bit changes for one questctl log file (optional night window)."""
    return tuple(
        _bit_changes_from_file(
            Path(path_str),
            epoch_lo=epoch_lo,
            epoch_hi=epoch_hi,
        )
    )


def load_dome_bit_changes_for_file(
    path: Path,
    *,
    night_date: str | None = None,
) -> list[tuple[datetime, int]]:
    """Collapsed shutter-bit changes from a single questctl log."""
    try:
        st = path.stat()
    except OSError:
        return []
    epoch_lo = epoch_hi = None
    if night_date:
        epoch_lo, epoch_hi = _night_epoch_bounds(night_date)
    return list(
        _bit_changes_cached(
            str(path),
            st.st_mtime_ns,
            st.st_size,
            epoch_lo,
            epoch_hi,
        )
    )


def load_dome_bit_changes(
    log_dir: Path | None,
    *,
    extra: bool = True,
    night_date: str | None = None,
) -> list[tuple[datetime, int]]:
    """
    Load shutter-bit changes from each questctl log **separately**, then concat.

    Files are not interleaved: two concurrent questctl logs (practice vs
    diagnostics) must not be merged into one 0/1/2 stream.
    """
    events: list[tuple[datetime, int]] = []
    for path in _questctl_bit_log_paths(log_dir, extra=extra, night_date=night_date):
        events.extend(load_dome_bit_changes_for_file(path, night_date=night_date))
    return events


def shutter_opens_and_closes(
    changes: list[tuple[datetime, int]],
) -> tuple[list[datetime], list[datetime]]:
    """
    Turn bit changes into open and close confirmation times.

    Close: previous stable state was open (1), then 0 (with optional 2 in between).
    Open: previous stable state was closed (0), then 1 (with optional 2 in between).
    ``0 → 2 → 0`` does not count as a close.
    """
    opens: list[datetime] = []
    closes: list[datetime] = []
    last_stable: int | None = None
    motion_from: int | None = None
    for dt, bit in changes:
        if bit == 2:
            if last_stable in (0, 1) and motion_from is None:
                motion_from = last_stable
            continue
        if bit not in (0, 1):
            continue
        came_from_open = last_stable == 1 or motion_from == 1
        came_from_closed = last_stable == 0 or motion_from == 0
        if bit == 0 and came_from_open:
            closes.append(dt)
        elif bit == 1 and came_from_closed:
            opens.append(dt)
        last_stable = bit
        motion_from = None
    return opens, closes


def _shutter_events_on_night(
    log_dir: Path | None, night_date: str
) -> tuple[list[datetime], list[datetime]]:
    """
    Open and close confirmations on ``night_date``, unioned across log files.

    Each file is interpreted on its own so overlapping logs cannot create
    fake ``1→0`` transitions.
    """
    opens: list[datetime] = []
    closes: list[datetime] = []
    for path in _questctl_bit_log_paths(log_dir, night_date=night_date):
        file_opens, file_closes = shutter_opens_and_closes(
            load_dome_bit_changes_for_file(path, night_date=night_date)
        )
        opens.extend(dt for dt in file_opens if belongs_to_ut_night(dt, night_date))
        closes.extend(dt for dt in file_closes if belongs_to_ut_night(dt, night_date))
    return sorted(set(opens)), sorted(set(closes))


def load_dome_bit_events_on_night(
    log_dir: Path | None, night_date: str
) -> list[tuple[datetime, int]]:
    """
    Collapsed shutter-bit changes (0/1/2) on UT night ``night_date``.

    One row per state change, per log file. Files are not interleaved.
    """
    out: list[tuple[datetime, int]] = []
    for path in _questctl_bit_log_paths(log_dir, night_date=night_date):
        prev: int | None = None
        for dt, bit in load_dome_bit_changes_for_file(path, night_date=night_date):
            if not belongs_to_ut_night(dt, night_date):
                continue
            if bit == prev:
                continue
            out.append((dt, bit))
            prev = bit
    out.sort(key=lambda x: x[0])
    return out


def load_questctl_shutter_closes(log_dir: Path | None, night_date: str) -> list[datetime]:
    """Return shutter-closed confirmations (``1→0``) on UT night ``night_date``."""
    _opens, closes = _shutter_events_on_night(log_dir, night_date)
    return closes


def load_questctl_shutter_opens(log_dir: Path | None, night_date: str) -> list[datetime]:
    """Return shutter-open confirmations (``0→1``) on UT night ``night_date``."""
    opens, _closes = _shutter_events_on_night(log_dir, night_date)
    return opens


def count_questctl_bit_closes_on_night(log_dir: Path | None, night_date: str) -> int:
    """Count ``1→0`` shutter closes on UT night ``night_date``."""
    return len(load_questctl_shutter_closes(log_dir, night_date))


def recent_questctl_closes(log_dir: Path | None, *, limit: int = 5) -> list[tuple[datetime, Path]]:
    """
    Return the most recent ``CLOSE_CODE`` events across all questctl logs.

    Useful for diagnostics when a night has no matching close (see
    :mod:`tools.check_night`).
    """
    found: list[tuple[datetime, Path]] = []
    # Newest filename first among everything still on disk.
    paths = sorted(log_dir.glob("questctl.*.log"), reverse=True) if log_dir and log_dir.is_dir() else []
    for path in paths:
        for line in _close_code_lines(path):
            m = CLOSE_CODE.search(line)
            if not m:
                continue
            found.append(
                (datetime.fromtimestamp(int(m.group(1)), tz=timezone.utc), path)
            )
        if len(found) >= limit:
            break
    return sorted(found, key=lambda x: x[0])[-limit:]


def load_questctl_closes(log_dir: Path | None, night_date: str) -> list[datetime]:
    """
    Return UTC datetimes from ``CLOSE_CODE`` lines belonging to UT night ``night_date``.
    """
    out: list[datetime] = []
    for path in questctl_logs_for_night(log_dir, night_date):
        for line in _close_code_lines(path):
            m = CLOSE_CODE.search(line)
            if not m:
                continue
            utc_dt = datetime.fromtimestamp(int(m.group(1)), tz=timezone.utc)
            if belongs_to_ut_night(utc_dt, night_date):
                out.append(utc_dt)
    return out


def count_questctl_closes_on_night(log_dir: Path | None, night_date: str) -> int:
    """Count ``CLOSE_CODE`` events on UT night ``night_date``."""
    return len(load_questctl_closes(log_dir, night_date))


def _pick_close_after_open(
    closes: list[datetime],
    first_open: float | None,
    exposure_ut: list[float],
    scheduler_events: list[tuple[float, str]],
) -> tuple[float, datetime] | None:
    """Pick the latest close after dome open and (when possible) last exposure."""
    if not closes:
        return None
    anchor = night_anchor_ut(scheduler_events, exposure_ut)
    if first_open is not None:
        open_night = to_night_ut(first_open, anchor)
    elif exposure_ut:
        open_night = min(to_night_ut(u, anchor) for u in exposure_ut)
    else:
        open_night = to_night_ut(12.0, anchor)
    last_exp_night = max(to_night_ut(u, anchor) for u in exposure_ut) if exposure_ut else None

    candidates: list[tuple[float, float, datetime]] = []
    for utc_dt in closes:
        ut = utc_to_ut_decimal(utc_dt)
        night_ut = to_night_ut(ut, anchor)
        if night_ut + 1e-6 < open_night:
            continue
        candidates.append((night_ut, ut, utc_dt))

    if not candidates:
        return None

    if last_exp_night is not None:
        after_exp = [c for c in candidates if c[0] >= last_exp_night - 0.25]
        if after_exp:
            best = max(after_exp, key=lambda x: x[0])
            return best[1], best[2]

    best = max(candidates, key=lambda x: x[0])
    return best[1], best[2]


def find_night_close_from_dome_bits(
    log_dir: Path | None,
    night_date: str,
    first_open: float | None,
    exposure_ut: list[float],
    scheduler_events: list[tuple[float, str]],
) -> tuple[float, datetime] | None:
    """
    Pick the best shutter-bit close (``1→2→0`` or ``1→0``) for the night.

    Used after dome_daemon: questctl is still polling during a normal
    ``stow_telescope``, so the bit stream records the shutter actually closing.
    """
    return _pick_close_after_open(
        load_questctl_shutter_closes(log_dir, night_date),
        first_open,
        exposure_ut,
        scheduler_events,
    )


def find_night_open_from_dome_bits(
    log_dir: Path | None,
    night_date: str,
) -> tuple[float, datetime] | None:
    """Return the first shutter-open (``0→1``) on ``night_date``, if any."""
    opens = load_questctl_shutter_opens(log_dir, night_date)
    if not opens:
        return None
    dt = min(opens)
    return utc_to_ut_decimal(dt), dt


def find_night_close_from_questctl(
    log_dir: Path | None,
    night_date: str,
    first_open: float | None,
    exposure_ut: list[float],
    scheduler_events: list[tuple[float, str]],
) -> tuple[float, datetime] | None:
    """
    Pick the best questctl ``CLOSE_CODE`` for end-of-night reporting.

    Used when the shutter bit stream did not record a ``1→0`` transition.
    """
    return _pick_close_after_open(
        load_questctl_closes(log_dir, night_date),
        first_open,
        exposure_ut,
        scheduler_events,
    )
