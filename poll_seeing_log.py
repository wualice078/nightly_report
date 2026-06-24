#!/usr/bin/env python3
"""Append one ESO DIMM sample to seeing.logs (cron: every 15 minutes)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PACKAGE = Path(__file__).resolve().parent
sys.path.insert(0, str(PACKAGE))

from practice_config import ESO_SEEING_URL, SEEING_LOG
from seeing_samples import append_seeing_sample


def main() -> int:
    p = argparse.ArgumentParser(description="Poll ESO seeing.last and append to seeing.logs")
    p.add_argument("--log", type=Path, default=SEEING_LOG, help="seeing log path")
    p.add_argument("--url", default=ESO_SEEING_URL, help="ESO seeing.last URL")
    args = p.parse_args()
    return 0 if append_seeing_sample(args.log, args.url) else 1


if __name__ == "__main__":
    raise SystemExit(main())
