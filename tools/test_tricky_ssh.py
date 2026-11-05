"""Texture recontainerization preserves texels and palette colours."""

import struct
import unittest

from tricky_ssh import inspect_world_ssh, parse_shps, to_world_ssh


class SshTests(unittest.TestCase):
    def test_indexed_texels_and_swizzled_palette_are_unchanged(self):
        pixels = b"\x04\x03\x02\x01"
        colours = bytes(i % 256 for i in range(1024))
        entry = bytearray(16 + len(pixels) + 16 + len(colours))
        entry[0] = 2
        entry[1:4] = (16 + len(pixels)).to_bytes(3, "little")
        struct.pack_into("<2H", entry, 4, 2, 2)
        entry[16:20] = pixels
        entry[20] = 0x21
        struct.pack_into("<I", entry, 32, 0x2000)  # Already in PS2 CLUT order.
        entry[36:] = colours
        image = to_world_ssh(entry, lightmap=False)
        self.assertEqual(inspect_world_ssh(image, lightmap=False)["bytes"], len(image))
        self.assertEqual(image[128:132], pixels)
        self.assertEqual(image[-1024:], colours)
        container = (b"SHPS" + struct.pack("<2I", 24 + len(entry), 1) +
                     b"G278" + b"0000" + struct.pack("<I", 24) + entry)
        self.assertEqual(parse_shps(container), [(0, bytes(entry))])

    def test_linear_palette_preserves_each_indexed_colour(self):
        colours = b"".join(struct.pack("<I", index) for index in range(256))
        entry = bytearray(16 + 256 + 16 + len(colours))
        entry[0] = 2
        entry[1:4] = (16 + 256).to_bytes(3, "little")
        struct.pack_into("<2H", entry, 4, 16, 16)
        entry[16:272] = bytes(range(256))
        entry[272] = 0x21
        entry[288:] = colours
        image = to_world_ssh(entry, lightmap=False)
        self.assertEqual(image[128:384], bytes(range(256)))
        palette = struct.unpack("<256I", image[-1024:])
        # Decode four adjacent 8-colour banks in their PS2 hardware order.
        for block in range(0, 256, 32):
            self.assertEqual(palette[block:block + 32], tuple(
                list(range(block, block + 8)) + list(range(block + 16, block + 24)) +
                list(range(block + 8, block + 16)) + list(range(block + 24, block + 32))))

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
