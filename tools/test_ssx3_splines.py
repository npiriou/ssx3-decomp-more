"""Spline import regressions: source metres and native centimetres agree."""

import struct
import unittest

from ssx3_splines import convert_splines


def polynomial(coefficients, distance):
    a, b, c, d = coefficients
    return ((a * distance + b) * distance + c) * distance + d


class SplineTests(unittest.TestCase):
    def test_arc_distance_conversion_preserves_positions_and_links(self):
        # Snowdream chairlift-like lengths: using these as metres instead of
        # centimetres previously sent clones trillions of centimetres away.
        coefficients = [5.88479e-5, .002777369, .06556125, .001403095]
        points = [[20., -30., 10., 0.], [-50., 60., -70., 0.],
                  [1000., 2000., -3000., 0.], [-5300., -28400., -10800., 1.]]
        segments = []
        for index, length in enumerate((1007.3986, 5863.0186)):
            segments.append({
                "parent": 0, "previous": 0xffffffff if index == 0 else 0,
                "next": 1 if index == 0 else 0xffffffff,
                "length": length, "previous_length": 0. if index == 0 else 1007.3986,
                "control_points": points,
                "coefficients": coefficients if index == 0 else [0., 0., 1 / (length / 100), 0.],
                "bounds_min": [-6000., -30000., -15000.],
                "bounds_max": [6000., -20000., 0.], "flags": 0,
            })
        pbd = {"splines": [{"index": 0, "segment_count": 2, "first_segment": 0,
                            "bounds_min": segments[0]["bounds_min"],
                            "bounds_max": segments[0]["bounds_max"]}],
               "spline_segments": segments}
        payload, = convert_splines(pbd, bytes(48 + 2 * 144), 49)
        self.assertEqual(struct.unpack_from("<I", payload)[0], 49)
        for index, source in enumerate(segments):
            base = 48 + index * 144
            native = struct.unpack_from("<4f", payload, base + 0x50)
            self.assertEqual(struct.unpack_from("<3I", payload, base + 0x60),
                             (source["previous"], source["next"], 0))
            self.assertAlmostEqual(struct.unpack_from("<f", payload, base + 0x84)[0],
                                   source["previous_length"], delta=.001)
            for fraction in (0., .01, .25, .5, .75, .99, 1.):
                distance = source["length"] * fraction
                expected_u = polynomial(source["coefficients"], distance / 100)
                actual_u = polynomial(native, distance)
                self.assertAlmostEqual(actual_u, expected_u, delta=2e-7)
                for axis in range(4):
                    curve = [point[axis] for point in points]
                    self.assertAlmostEqual(polynomial(curve, actual_u),
                                           polynomial(curve, expected_u), delta=.002)
        # The historical unconverted data fails this by five orders of magnitude.
        self.assertGreater(polynomial(coefficients, segments[0]["length"]), 60000.)


if __name__ == "__main__":
    unittest.main()
