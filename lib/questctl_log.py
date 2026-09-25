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
weeks. Always filter events by UTC timestamp, not filename.
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
LOG_START = re.compile(r"^questctl\.(\d{8})\d+\.log$")
GREP_BITS = r"checking telescope status [0-9]{9,}|dome status bit is [0-9]"


def questctl_logs_for_night(log_dir: Path | None, night_date: str) -> list[Path]:
    """
    Return ``questctl.*.log`` files that could contain events for ``night_date``.

    Drops logs whose filename start date is after the UT night ends. Older
    start dates are kept (a long-running process can cover later nights).
    """
    if log_dir is None or not log_dir.is_dir():
        return []
    try:
        night_end = datetime.strptime(night_date, "%Y%m%d") + timedelta(days=2)
    except ValueError:
        night_end = None
    out: list[Path] = []
    for path in sorted(log_dir.glob("questctl.*.log")):
        m = LOG_START.match(path.name)
        if m and night_end is not None:
            try:
                started = datetime.strptime(m.group(1), "%Y%m%d")
            except ValueError:
                started = None
            if started is not None and started > night_end:
                continue
        out.append(path)
    return out


def extra_questctl_log_dirs(primary: Path | None) -> list[Path]:
    """
    Directories to scan for shutter bits.

    Always includes ``primary``. Adds practice / sample-diagnostics archives
    only when ``primary`` is the usual mountain or practice questctl log dir,
    so unit tests with a temp directory stay isolated.
    """
    from lib.practice_config import OBSERVER_ROOT, PRACTICE_QUESTCTL_LOG_DIR, QUESTCTL_LOG_DIR

    archive = OBSERVER_ROOT / "2026_recent_logs" / "sample_diagnostics_logs"

    def _key(p: Path) -> str:
        try:
            return str(p.resolve()) if p.exists() else str(p)
        except OSError:
            return str(p)

    known = {_key(PRACTICE_QUESTCTL_LOG_DIR), _key(QUESTCTL_LOG_DIR)}
    use_archives = primary is None or _key(primary) in known
    extras = [PRACTICE_QUESTCTL_LOG_DIR, archive] if use_archives else []

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


def _file_has_dome_bits(path: Path) -> bool:
    """Return True if the log contains any ``dome status bit is`` line."""
    try:
        r = subprocess.run(
            ["grep", "-q", "dome status bit is", str(path)],
            capture_output=True,
        )
        return r.returncode == 0
    except (OSError, FileNotFoundError):
        with path.open(encoding="utf-8", errors="replace") as fh:
            for line in fh:
                if "dome status bit is" in line:
                    return True
        return False


def _bit_changes_from_lines(lines: list[str]) -> list[tuple[datetime, int]]:
    """
    Collapse ``dome status bit`` lines into timestamped state changes.

    Each bit sample is stamped with the most recent ``checking telescope status``
    epoch before it, or the next one after it if none came first.
    """
    records: list[tuple[str, int]] = []
    for line in lines:
        m = STATUS_TS.search(line)
        if m:
            records.append(("ts", int(m.group(1))))
            continue
        m = BIT_LINE.search(line)
        if m:
            records.append(("bit", int(m.group(1))))

    last_ts: int | None = None
    pending: list[tuple[int | None, int]] = []
    for kind, val in records:
        if kind == "ts":
            last_ts = val
            for i, (ts, bit) in enumerate(pending):
                if ts is None:
                    pending[i] = (val, bit)
        else:
            pending.append((last_ts, val))

    events: list[tuple[datetime, int]] = []
    prev: int | None = None
    for ts, bit in pending:
        if ts is None:
            continue
        if bit == prev:
            continue
        events.append((datetime.fromtimestamp(ts, tz=timezone.utc), bit))
        prev = bit
    return events


def _questctl_bit_log_paths(log_dir: Path | None, *, extra: bool = True) -> list[Path]:
    """Return unique questctl log paths to scan for shutter bits."""
    dirs = extra_questctl_log_dirs(log_dir) if extra else (
        [log_dir] if log_dir is not None else []
    )
    out: list[Path] = []
    seen: set[str] = set()
    for d in dirs:
        if d is None or not d.is_dir():
            continue
        for path in sorted(d.glob("questctl.*.log")):
            key = str(path.resolve()) if path.exists() else str(path)
            if key in seen:
                continue
            seen.add(key)
            out.append(path)
    return out


@lru_cache(maxsize=32)
def _bit_changes_cached(path_str: str, mtime_ns: int, size: int) -> tuple[tuple[datetime, int], ...]:
    """Cached shutter-bit changes for one questctl log file."""
    path = Path(path_str)
    if not _file_has_dome_bits(path):
        return ()
    return tuple(_bit_changes_from_lines(_grep_lines(path, GREP_BITS)))


def load_dome_bit_changes_for_file(path: Path) -> list[tuple[datetime, int]]:
    """Collapsed shutter-bit changes from a single questctl log."""
    try:
        st = path.stat()
    except OSError:
        return []
    return list(_bit_changes_cached(str(path), st.st_mtime_ns, st.st_size))


def load_dome_bit_changes(log_dir: Path | None, *, extra: bool = True) -> list[tuple[datetime, int]]:
    """
    Load shutter-bit changes from each questctl log **separately**, then concat.

    Files are not interleaved: two concurrent questctl logs (practice vs
    diagnostics) must not be merged into one 0/1/2 stream.
    """
    events: list[tuple[datetime, int]] = []
    for path in _questctl_bit_log_paths(log_dir, extra=extra):
        events.extend(load_dome_bit_changes_for_file(path))
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
    for path in _questctl_bit_log_paths(log_dir):
        file_opens, file_closes = shutter_opens_and_closes(load_dome_bit_changes_for_file(path))
        opens.extend(dt for dt in file_opens if belongs_to_ut_night(dt, night_date))
        closes.extend(dt for dt in file_closes if belongs_to_ut_night(dt, night_date))
    return sorted(set(opens)), sorted(set(closes))


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
    for path in reversed(questctl_logs_for_night(log_dir, "")):
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
