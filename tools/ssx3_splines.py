"""Translate Tricky PBD splines into SSX 3 WorldSpline resources."""

from __future__ import annotations

import struct

from tricky_assets import FormatError


def spline_template(shared_stream: bytes) -> bytes:
    """Take the target-only fields from a regular retail spline.

    ARA1's first spline has an unusual first-segment prefix. Its second
    spline carries the normal first/middle segment fields used throughout
    that course. These fields have no counterpart in Tricky's PBD.
    """
    pos = 0
    while pos + 8 <= len(shared_stream):
        kind = shared_stream[pos]
        size = int.from_bytes(shared_stream[pos + 1:pos + 4], "little")
        rid = int.from_bytes(shared_stream[pos + 5:pos + 8], "little")
        end = pos + 8 + size
        if end > len(shared_stream):
            raise FormatError("retail SSB resource is truncated")
        if kind == 8 and rid == 1:
            payload = shared_stream[pos + 8:end]
            if len(payload) < 48 + 2 * 144:
                raise FormatError("retail WorldSpline template has too few segments")
            return payload
        pos = end
    raise FormatError("retail WorldSpline template was not found")


def convert_splines(pbd: dict, template: bytes, section_id: int) -> list[bytes]:
    """Build one SSX 3 type-8 payload for every Tricky spline."""
    if len(template) < 48 + 2 * 144:
        raise ValueError("WorldSpline template is too short")
    if not 0 <= section_id <= 255:
        raise ValueError("WorldSpline section ID is outside its format")
    target_scale = template[36:40]
    first_prefix = template[48:60]
    middle_prefix = template[48 + 144:60 + 144]
    target_tail = template[48 + 140:48 + 144]
    splines = pbd["splines"]
    segments = pbd["spline_segments"]
    output = []
    for spline in splines:
        index = spline["index"]
        count = spline["segment_count"]
        first = spline["first_segment"]
        if index > 0xffffff or count < 1:
            raise FormatError("Tricky spline cannot be represented in SSX 3")
        body = bytearray()
        body.extend(struct.pack("<I6fII", (index << 8) | section_id,
                                *spline["bounds_min"], *spline["bounds_max"],
                                0, count))
        body.extend(target_scale)
        body.extend(struct.pack("<II", 0xffffffff, 0))
        for local_index in range(count):
            source = segments[first + local_index]
            if source["parent"] != index:
                raise FormatError("Tricky spline segment has the wrong parent")
            previous = 0xffffffff if local_index == 0 else first + local_index - 1
            following = 0xffffffff if local_index == count - 1 else first + local_index + 1
            if (source["previous"] != (0xffffffff if local_index == 0 else first + local_index - 1)
                    or source["next"] != (0xffffffff if local_index == count - 1 else first + local_index + 1)):
                raise FormatError("Tricky spline segment is not a linear chain")
            body.extend(first_prefix if local_index == 0 else middle_prefix)
            body.extend(struct.pack("<f", source["length"]))
            for point in source["control_points"]:
                body.extend(struct.pack("<4f", *point))
            body.extend(struct.pack("<4f", *source["coefficients"]))
            body.extend(struct.pack("<3I", source["previous"],
                                    source["next"], index))
            body.extend(struct.pack("<6f", *source["bounds_min"],
                                    *source["bounds_max"]))
            body.extend(struct.pack("<f", source["previous_length"]))
            body.extend(struct.pack("<I", source["flags"]))
            body.extend(target_tail)
        if len(body) != 48 + 144 * count:
            raise AssertionError("WorldSpline payload length is wrong")
        output.append(bytes(body))
    return output
