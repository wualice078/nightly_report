#!/usr/bin/env python3
"""Compare nightly obsplan to log.obs (tag + RA/Dec match)."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path

RADEC_TOL = 0.002


@dataclass
class PlannedField:
    ra: float
    dec: float
    shutter: str
    n_required: int
    tag: str


def parse_obsplan(path: Path) -> list[PlannedField]:
    fields = []
    for i, raw in enumerate(path.read_text().splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if "#" in line:
            body, comment = line.split("#", 1)
            tag = comment.strip()
        else:
            body, tag = line, f"line_{i}"
        parts = body.split()
        if len(parts) < 7:
            continue
        fields.append(
            PlannedField(
                float(parts[0]),
                float(parts[1]),
                parts[2],
                int(parts[5]),
                tag,
            )
        )
    return fields


def parse_log_obs(path: Path) -> list[str]:
    return [ln.strip() for ln in path.read_text().splitlines() if ln.strip()]


def is_observing_field(field: PlannedField) -> bool:
    return field.shutter.upper() == "Y"


def matches(field: PlannedField, line: str) -> bool:
    parts = line.split()
    if len(parts) < 2:
        return False
    try:
        ra, dec = float(parts[0]), float(parts[1])
    except ValueError:
        return False
    if abs(ra - field.ra) > RADEC_TOL or abs(dec - field.dec) > RADEC_TOL:
        return False
    if field.tag and not field.tag.startswith("line_"):
        return field.tag in line
    return True


def count_field(field: PlannedField, log_lines: list[str]) -> int:
    return sum(1 for ln in log_lines if matches(field, ln))


def _bucket(fields: list[PlannedField], log_lines: list[str]):
    complete, partial, none = [], [], []
    for f in fields:
        n = count_field(f, log_lines)
        if n >= f.n_required:
            complete.append((f, n))
        elif n > 0:
            partial.append((f, n))
        else:
            none.append(f)
    return complete, partial, none


def _field_table(complete, partial, none) -> list[str]:
    header = f"  {'tag':<20}  {'RA':>8}  {'Dec':>9}  got/need"
    lines = [header]

    def add_group(label: str, items):
        if not items:
            return
        if len(lines) > 1:
            lines.append("")
        lines.append(f"  {label}")
        for f, n in items:
            lines.append(
                f"  {f.tag:<20}  {f.ra:8.4f}  {f.dec:9.4f}  {n}/{f.n_required}"
            )

    add_group(f"COMPLETE ({len(complete)})", complete)
    add_group(f"PARTIAL ({len(partial)})", partial)
    if none:
        if len(lines) > 1:
            lines.append("")
        lines.append(f"  NOT OBSERVED ({len(none)})")
        for f in none:
            lines.append(
                f"  {f.tag:<20}  {f.ra:8.4f}  {f.dec:9.4f}  0/{f.n_required}"
            )
    return lines


def _fields_block(title: str, fields: list[PlannedField], log_lines: list[str]) -> list[str]:
    if not fields:
        return [f"  {title} (0 planned)"]
    c, p, n = _bucket(fields, log_lines)
    return [f"  {title} ({len(fields)} planned)"] + _field_table(c, p, n)


def build_fields_section(obsplan: Path, log_obs: Path) -> str:
    planned = parse_obsplan(obsplan)
    log_lines = parse_log_obs(log_obs)
    obs_fields = [f for f in planned if is_observing_field(f)]
    cal_fields = [f for f in planned if not is_observing_field(f)]

    lines = [
        "=== Field inventory (obsplan vs log.obs) ===",
        f"  obsplan: {obsplan}",
        f"  log.obs: {log_obs}",
        f"  planned: {len(planned)}  exposures in log: {len(log_lines)}",
        "  RA in hours, Dec in degrees",
        "",
    ]
    lines += _fields_block("Observing fields", obs_fields, log_lines)
    lines.append("")
    lines += _fields_block("Calibration fields", cal_fields, log_lines)
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("obsplan", type=Path)
    p.add_argument("log_obs", type=Path)
    p.add_argument("-o", "--output", type=Path)
    args = p.parse_args()
    text = build_fields_section(args.obsplan, args.log_obs)
    if args.output:
        args.output.write_text(text)
    else:
        print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
