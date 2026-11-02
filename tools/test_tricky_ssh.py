"""Texture recontainerization preserves swizzled texels and palette bytes."""

import struct
import unittest

from tricky_ssh import inspect_world_ssh, parse_shps, to_world_ssh


class SshTests(unittest.TestCase):
    def test_indexed_texels_and_palette_are_unchanged(self):
        pixels = b"\x04\x03\x02\x01"
        colours = bytes(i % 256 for i in range(1024))
        entry = bytearray(16 + len(pixels) + 16 + len(colours))
        entry[0] = 2
        entry[1:4] = (16 + len(pixels)).to_bytes(3, "little")
        struct.pack_into("<2H", entry, 4, 2, 2)
        entry[16:20] = pixels
        entry[20] = 0x21
        entry[36:] = colours
        image = to_world_ssh(entry, lightmap=False)
        self.assertEqual(inspect_world_ssh(image, lightmap=False)["bytes"], len(image))
        self.assertEqual(image[128:132], pixels)
        self.assertEqual(image[-1024:], colours)
        container = (b"SHPS" + struct.pack("<2I", 24 + len(entry), 1) +
                     b"G278" + b"0000" + struct.pack("<I", 24) + entry)
        self.assertEqual(parse_shps(container), [(0, bytes(entry))])

    def test_lightmap_rgba_is_unchanged(self):
        pixels = bytes(range(16))
        entry = bytearray(16 + len(pixels))
        entry[0] = 5
        entry[1:4] = len(entry).to_bytes(3, "little")
        struct.pack_into("<2H", entry, 4, 2, 2)
        entry[16:] = pixels
        image = to_world_ssh(entry, lightmap=True)
        self.assertEqual(inspect_world_ssh(image, lightmap=True)["bytes"], 144)
        self.assertEqual(image[128:], pixels)


if __name__ == "__main__":
    unittest.main()
