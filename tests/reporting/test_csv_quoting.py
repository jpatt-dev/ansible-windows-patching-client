"""Lightweight RFC 4180 quoting checks for Final Report CSV fields.

Mirrors roles/patch_report/tasks/final_write.yml:
  quote every field; escape " as "".
"""
from __future__ import annotations

import csv
import io
import unittest


HEADER = [
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


def csvq(value) -> str:
    return '"' + str(value).replace('"', '""') + '"'


def render_row(fields) -> str:
    return ",".join(csvq(f) for f in fields)


def parse_row(line: str) -> list[str]:
    return next(csv.reader(io.StringIO(line)))


class CsvQuotingTests(unittest.TestCase):
    def test_normal_hostname_and_os_release(self) -> None:
        row = [
            "WINHOST01",
            "winhost01.example.com",
            "Microsoft Windows Server 2019 Datacenter",
            "17763.7553",
            "Lexington Datacenter",
            True,
            False,
            "success",
            "Updates installed successfully",
            2,
            0,
            "CHG001",
            "wave_1",
            "PATCH_SUCCEEDED",
            False,
            False,
        ]
        parsed = parse_row(render_row(row))
        self.assertEqual(parsed[0], "WINHOST01")
        self.assertEqual(parsed[2], "Microsoft Windows Server 2019 Datacenter")
        self.assertEqual(parsed[3], "17763.7553")
        self.assertEqual(parsed[13], "PATCH_SUCCEEDED")
        self.assertEqual(parsed[14], "False")
        self.assertEqual(parsed[15], "False")

    def test_comma_in_os_release_and_location(self) -> None:
        row = [""] * 16
        row[0] = "HOST,COMMA"
        row[2] = "Windows Server 2022, Datacenter"
        row[4] = "London, UK"
        parsed = parse_row(render_row(row))
        self.assertEqual(parsed[0], "HOST,COMMA")
        self.assertEqual(parsed[2], "Windows Server 2022, Datacenter")
        self.assertEqual(parsed[4], "London, UK")
        self.assertEqual(len(parsed), 16)

    def test_embedded_double_quotes(self) -> None:
        row = [""] * 16
        row[0] = 'HOST "QUOTED"'
        row[8] = 'Reason with "quotes"'
        rendered = render_row(row)
        self.assertIn('"HOST ""QUOTED"""', rendered)
        parsed = parse_row(rendered)
        self.assertEqual(parsed[0], 'HOST "QUOTED"')
        self.assertEqual(parsed[8], 'Reason with "quotes"')

    def test_empty_strings_are_quoted(self) -> None:
        row = [""] * 16
        row[0] = "EMPTY"
        rendered = render_row(row)
        parsed = parse_row(rendered)
        self.assertEqual(parsed[0], "EMPTY")
        self.assertEqual(parsed[1], "")
        self.assertEqual(parsed[2], "")
        self.assertTrue(rendered.startswith('"EMPTY",""'))
        self.assertEqual(parsed[-1], "")

    def test_header_column_count(self) -> None:
        self.assertEqual(len(HEADER), 16)
        self.assertEqual(len(parse_row(render_row(HEADER))), 16)
        self.assertEqual(HEADER[-3:], ["Reason Code", "Pending Reboot", "Manual Follow-up Required"])

    def test_unknown_reboot_state_is_not_false(self) -> None:
        row = [""] * 16
        row[0] = "MISSING"
        row[14] = "not_available"
        parsed = parse_row(render_row(row))
        self.assertEqual(parsed[14], "not_available")
        self.assertNotEqual(parsed[14], "False")


if __name__ == "__main__":
    unittest.main()
