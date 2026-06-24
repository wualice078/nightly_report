#!/usr/bin/env python3
"""Tests for ESO seeing log ingest and exposure DIMM join."""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

PACKAGE = Path(__file__).resolve().parent
sys.path.insert(0, str(PACKAGE))

from seeing_samples import (
    _parse_log_line,
    dimm_for_exposure,
    format_arcsec,
    load_seeing_samples,
    nearest_seeing_on_night,
)


def test_parse_log_line() -> None:
    row = _parse_log_line("2026-06-08T23:30:45Z 0.937")
    assert row is not None
    utc_dt, arcsec = row
    assert utc_dt == datetime(2026, 6, 8, 23, 30, 45, tzinfo=timezone.utc)
    assert arcsec == "0.937"


def test_load_seeing_samples_filters_night() -> None:
    log = PACKAGE / "reports" / "_test_seeing.logs"
    log.write_text(
        "2026-06-08T23:30:45Z 0.937\n"
        "2026-06-09T05:15:00Z 1.120\n"
        "2026-06-09T19:00:00Z 0.500\n"
    )
    try:
        samples = load_seeing_samples(log, "20260608")
        assert len(samples) == 2
        assert samples[0].arcsec == "1.120"
        assert samples[1].arcsec == "0.937"
    finally:
        log.unlink(missing_ok=True)


def test_nearest_seeing_on_night() -> None:
    from seeing_samples import SeeingSample

    samples = [
        SeeingSample(23.5, "0.90"),
        SeeingSample(1.25, "1.10"),  # 01:15 UT next calendar day
    ]
    anchor = 23.0
    hit = nearest_seeing_on_night(23.52, samples, anchor)
    assert hit is not None
    assert hit.arcsec == "0.90"


def test_dimm_for_exposure_prefers_scheduler() -> None:
    from seeing_samples import SeeingSample

    samples = [SeeingSample(23.5, "0.90")]
    assert dimm_for_exposure(23.52, 23.0, "0.55", samples) == "0.55"


def test_format_arcsec() -> None:
    assert format_arcsec(0.937) == "0.937"


def test_archive_and_clear_seeing_log() -> None:
    from seeing_samples import archive_and_clear_seeing_log

    log = PACKAGE / "reports" / "_test_seeing_archive.logs"
    archive = PACKAGE / "reports" / "_test_seeing_night.logs"
    log.write_text(
        "2026-06-08T23:30:45Z 0.937\n"
        "2026-06-09T05:15:00Z 1.120\n"
        "2026-06-09T19:00:00Z 0.500\n"
    )
    try:
        n = archive_and_clear_seeing_log(log, "20260608", archive)
        assert n == 2
        assert archive.read_text().count("\n") == 2
        assert log.read_text() == ""
    finally:
        log.unlink(missing_ok=True)
        archive.unlink(missing_ok=True)


def main() -> int:
    tests = [
        test_parse_log_line,
        test_load_seeing_samples_filters_night,
        test_nearest_seeing_on_night,
        test_dimm_for_exposure_prefers_scheduler,
        test_format_arcsec,
        test_archive_and_clear_seeing_log,
    ]
    for t in tests:
        t()
    print(f"ok ({len(tests)} tests)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
