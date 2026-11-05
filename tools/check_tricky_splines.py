"""Compare imported spline positions with the Tricky disc at sampled distances.

Run after prepare_tricky_tracks.py. This checks semantic distance units as well
as resource framing; structurally valid archives can still contain bad curves.
"""

from __future__ import annotations

import argparse
import math
import os
from pathlib import Path
import struct

from ssx3_world_probe import bigf_members, decode_stream, read_sdb
from tricky_assets import parse_pbd, read_cofb_member, read_iso_file
from tricky_courses import COURSES


def cubic(values, x):
    a, b, c, d = values
    return ((a * x + b) * x + c) * x + d


def check_archive(pbd, archive):
    members = bigf_members(archive.read_bytes())
    locations, _, streams = read_sdb(members["data/worlds/bam.sdb"])
    location = locations[-1]
    splines = {}
    for index in range(location["first_stream"], location["last_stream"] + 1):
        data = decode_stream(members["data/worlds/bam.ssb"], streams[index])
        pos = 0
        while pos < len(data):
            size = int.from_bytes(data[pos + 1:pos + 4], "little")
            end = pos + 8 + size
            assert end <= len(data), "truncated resource"
            if data[pos] == 8:
                rid = int.from_bytes(data[pos + 5:pos + 8], "little")
                assert rid not in splines, "duplicate spline"
                splines[rid] = data[pos + 8:end]
            pos = end
    assert len(splines) == len(pbd["splines"]), "missing spline resources"
    samples = 0
    max_error = 0.
    for spline in pbd["splines"]:
        body = splines[spline["index"]]
        count = spline["segment_count"]
        assert len(body) == 48 + 144 * count
        for local in range(count):
            source = pbd["spline_segments"][spline["first_segment"] + local]
            base = 48 + 144 * local
            points = struct.unpack_from("<16f", body, base + 0x10)
            assert points == tuple(v for point in source["control_points"] for v in point)
            length, = struct.unpack_from("<f", body, base + 0xc)
            start, = struct.unpack_from("<f", body, base + 0x84)
            assert (length, start) == (source["length"], source["previous_length"])
            coefficients = struct.unpack_from("<4f", body, base + 0x50)
            for fraction in (0., .01, .1, .25, .5, .75, .9, .99, 1.):
                distance = length * fraction
                expected_u = cubic(source["coefficients"], distance / 100.)
                actual_u = cubic(coefficients, distance)
                assert math.isclose(expected_u, actual_u, rel_tol=2e-5, abs_tol=2e-6), (
                    f"spline {spline['index']}, segment {local}: arc parameter "
                    f"{actual_u} != source {expected_u} at {distance} cm")
                for axis in range(3):
                    basis = points[axis::4]
                    expected = cubic(basis, expected_u)
                    actual = cubic(basis, actual_u)
                    error = abs(actual - expected)
                    max_error = max(max_error, error)
                    assert math.isfinite(actual) and math.isclose(
                        expected, actual, rel_tol=2e-5, abs_tol=.1), (
                            f"spline {spline['index']}, segment {local}: "
                            f"position error {error} cm")
                samples += 1
    return len(splines), samples, max_error


def main():
    root = Path(__file__).resolve().parent.parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tricky-iso", type=Path,
                        default=Path(os.environ.get("SSX_TRICKY_ISO", root / "SSX Tricky (USA).iso")))
    parser.add_argument("--overlay", type=Path, default=root / ".cache/overlay")
    args = parser.parse_args()
    for course in COURSES:
        source = read_iso_file(args.tricky_iso, course.archive)
        pbd = parse_pbd(read_cofb_member(source, f"data/models/{course.code.lower()}.pbd"), True)
        for mode in course.modes:
            archive = args.overlay / f"DATA/WORLDS/TRICKY/{course.code}-{mode}.BIG"
            count, samples, error = check_archive(pbd, archive)
            print(f"PASS: {course.code}/{mode}: {count} splines, {samples} positions, "
                  f"maximum error {error:.6f} cm", flush=True)


if __name__ == "__main__":
    main()
