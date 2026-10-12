"""Validate Final Report CSV produced by roles/patch_report/tasks/final_write.yml."""
from __future__ import annotations

import csv
import io
import sys
from pathlib import Path
from typing import Optional

EXPECTED_HEADER = [
    "Hostname",
    "FQDN",
    "OS Release",
    "Post-Patch Kernel/Build",
    "Location",
    "Patched",
    "Exempt",
    "Result",
    "Reason",
    "Updates Installed",
    "Updates Remaining",
    "Change Ticket",
    "Patch Wave",
    "Reason Code",
    "Pending Reboot",
    "Manual Follow-up Required",
]

LITERAL_BACKSLASH_N = "\\" + "n"


def main(path: str, expected_row_count: Optional[int] = None) -> None:
    raw = Path(path).read_bytes()
    text = raw.decode("utf-8")
    without_newlines = text.replace("\r\n", "").replace("\n", "").replace("\r", "")
    if LITERAL_BACKSLASH_N in without_newlines:
        raise SystemExit("CSV contains literal backslash-n text instead of row separators")

    lines = [line for line in text.splitlines()]
    if any(line.strip() == "" for line in lines):
        raise SystemExit("CSV contains unintended blank rows")

    rows = list(csv.reader(io.StringIO(text)))
    if not rows:
        raise SystemExit("CSV has no header row")
    if rows[0] != EXPECTED_HEADER:
        raise SystemExit(f"Unexpected CSV header: {rows[0]!r}")
    if expected_row_count is not None and len(rows) != expected_row_count:
        raise SystemExit(f"Expected {expected_row_count} CSV rows including header, got {len(rows)}")
    for index, row in enumerate(rows):
        if len(row) != len(EXPECTED_HEADER):
            raise SystemExit(
                f"CSV row {index} has {len(row)} fields, expected {len(EXPECTED_HEADER)}: {row!r}"
            )
        for cell in row:
            if LITERAL_BACKSLASH_N in cell:
                raise SystemExit(f"CSV cell contains literal backslash-n: {cell!r}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit("usage: assert_generated_csv.py <csv-path> [expected-row-count]")
    expected = int(sys.argv[2]) if len(sys.argv) > 2 else None
    main(sys.argv[1], expected)
