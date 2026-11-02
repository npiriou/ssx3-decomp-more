"""SSB envelope roundtrips, including RefPack's literal command boundaries."""

import struct
import unittest

from ssx3_world_build import (encode_refpack_literals, encode_stream,
                              pack_patch_geometry, pack_resource)
from ssx3_world_probe import decode_stream
from tricky_assets import decode_refpack


class WorldStreamBuildTests(unittest.TestCase):
    def test_literal_refpack_boundaries(self):
        for length in (0, 1, 2, 3, 4, 7, 111, 112, 113, 115, 116, 224, 65537):
            with self.subTest(length=length):
                original = bytes((i * 97 + 13) % 256 for i in range(length))
                self.assertEqual(decode_refpack(encode_refpack_literals(original)), original)

    def test_ssb_blocks(self):
        original = bytes((i * 71 + 5) % 256 for i in range(130_003))
        packed = encode_stream(original, block_bytes=65536)
        self.assertEqual(decode_stream(packed, {"file_offset": 0}), original)
        self.assertEqual(packed.count(b"CEND"), 1)

    def test_patch_layout_and_resource_framing(self):
        source = {
            "lightmap_vector": [0.0, 0.0, 1.0, 1.0],
            "uv_vectors": [[0.0, 0.0], [1.0, 0.0],
                           [0.0, 1.0], [1.0, 1.0]],
            "coefficients": [[0.0, 0.0, 0.0, 1.0] for _ in range(16)],
            "bounds_min": [1.0, 2.0, 3.0],
            "bounds_max": [5.0, 6.0, 7.0],
            "corner_points": [[1.0, 2.0, 3.0, 1.0]] * 4,
        }
        patch = pack_patch_geometry(
            source, prefix=bytes(range(16)), object_id=b"\x08\x01\x00\x00",
            u10=0, chunk_id=25, texture_rid=12, lightmap_rid=-1,
            tail=b"\x77" * 12,
        )
        self.assertEqual(len(patch), 432)
        self.assertEqual(struct.unpack_from("<3f", patch, 0x158), (1.0, 2.0, 3.0))
        self.assertEqual(struct.unpack_from("<3f", patch, 0x170), (1.0, 2.0, 3.0))
        self.assertEqual(struct.unpack_from("<2h", patch, 0x1a0), (12, -1))
        framed = pack_resource(1, 8, 123, patch)
        self.assertEqual(framed[:8], b"\x01\xb0\x01\x00\x08\x7b\x00\x00")
        self.assertEqual(framed[8:], patch)


if __name__ == "__main__":
    unittest.main()
