"""
Fixed-width text tables for the nightly report.

Column widths are taken from the widest header or cell in that column, so titles
stay lined up with the values underneath even when number lengths change.
"""

from __future__ import annotations


def format_table(
    headers: list[str],
    rows: list[list[str]],
    *,
    aligns: list[str] | None = None,
    indent: str = "  ",
) -> list[str]:
    """
    Format a text table.

    ``aligns`` is a list of ``"l"`` or ``"r"`` per column (default: right).
    Returns one string per line, including the header.
    """
    if not headers:
        return []
    n = len(headers)
    aligns = list(aligns) if aligns is not None else ["r"] * n
    if len(aligns) < n:
        aligns.extend(["r"] * (n - len(aligns)))

    widths = [len(h) for h in headers]
    for row in rows:
        for i in range(min(n, len(row))):
            widths[i] = max(widths[i], len(row[i]))

    def cell(i: int, text: str) -> str:
        return f"{text:<{widths[i]}}" if aligns[i] == "l" else f"{text:>{widths[i]}}"

    lines = [indent + "  ".join(cell(i, h) for i, h in enumerate(headers))]
    for row in rows:
        padded = [row[i] if i < len(row) else "" for i in range(n)]
        lines.append(indent + "  ".join(cell(i, padded[i]) for i in range(n)))
    return lines
