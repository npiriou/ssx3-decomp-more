"""Tricky to SSX 3 route resource framing checks."""

import struct
import unittest

from ssx3_aip import convert_tricky_aip, inspect_world_aip
from tricky_assets import FormatError


def sample_tricky_aip() -> bytes:
    point = struct.pack("<4f", 1.0, 0.0, 0.0, 1.0)
    ai = struct.pack("<9I9f", *([0] * 7), 1, 0, *([0.0] * 9)) + point
    race = struct.pack("<4I2I9f", 1, 0, 0, 0, 1, 0, *([0.0] * 9)) + point
    ai_section = struct.pack("<2I", 1, 1) + struct.pack("<I", 0) + ai
    race_header = struct.pack("<4I", 1, len(race), 1, 0)
    race_offset = 16 + len(ai_section) - 16
    wrapper = b"\x0a" * 4 + struct.pack("<3I", 2, 0, race_offset)
    return wrapper + ai_section + race_header + race


class AipTests(unittest.TestCase):
    def test_converted_routes_parse_as_ssx3(self):
        output, starts = convert_tricky_aip(sample_tricky_aip())
        self.assertEqual(starts, [0])
        self.assertEqual(inspect_world_aip(output), {
            "ai_paths": 1, "race_paths": 1,
            "trailing_u0_records": 0, "trailing_u1_records": 0,
            "bytes": len(output),
        })

    def test_invalid_starter_is_rejected(self):
        source = bytearray(sample_tricky_aip())
        struct.pack_into("<I", source, 24, 1)
        with self.assertRaises(FormatError):
            convert_tricky_aip(source)


if __name__ == "__main__":
    unittest.main()
