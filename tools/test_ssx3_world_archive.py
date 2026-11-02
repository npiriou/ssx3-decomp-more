"""Append-only SDB/SSB and BIGF container checks."""

import struct
import unittest

from ssx3_world_archive import append_location, pack_bigf, shared_next_id
from ssx3_world_build import pack_resource
from ssx3_world_probe import bigf_members, decode_stream, read_sdb, resource_summary


class ArchiveTests(unittest.TestCase):
    def test_append_one_leaf_and_keep_original_member(self):
        sdb = bytearray(80)
        sdb[:4] = b"\x00\x38\x00\x01"
        patch = bytearray(432)
        struct.pack_into("<h", patch, 0x156, 0)
        leaf = pack_resource(9, 255, 0, b"texture")
        shared = pack_resource(1, 0, 0, patch)
        shared += pack_resource(14, 0, 0, b"aip")
        new_sdb, new_ssb = append_location(
            bytes(sdb), b"retail-streams", name="GARI",
            bounds_min=(-10.0, -20.0, -30.0),
            bounds_max=(10.0, 20.0, 30.0),
            leaf_resources=leaf, shared_resources=shared,
        )
        locations, chunks, streams = read_sdb(new_sdb)
        self.assertEqual(shared_next_id(new_sdb, 9), 1)
        self.assertEqual(locations[0]["name"], "GARI")
        self.assertEqual((chunks[0]["child1"], chunks[0]["streaming_chunk_id"]),
                         (0xffffffff, 0))
        self.assertEqual(resource_summary(decode_stream(new_ssb, streams[1]), 2)
                         ["resource_counts"], {1: 1, 14: 1})
        self.assertEqual(decode_stream(new_ssb, streams[0]), leaf)
        archive = pack_bigf([("data/worlds/bam.sdb", new_sdb),
                             ("data/worlds/bam.ssb", new_ssb),
                             ("data/worlds/serial.txt", b"original")])
        members = bigf_members(archive)
        self.assertEqual(members["data/worlds/serial.txt"], b"original")
        self.assertEqual(members["data/worlds/bam.sdb"], new_sdb)


if __name__ == "__main__":
    unittest.main()
