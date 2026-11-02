"""Read Tricky SSF collision geometry and instance property assignments."""

from __future__ import annotations

import math
import struct

from tricky_assets import FormatError


def _extent(data: bytes, start: int, size: int, end: int | None = None) -> None:
    if start < 0 or size < 0 or start + size > (len(data) if end is None else end):
        raise FormatError("Tricky SSF data extends beyond its declared extent")


def parse_ssf(data: bytes) -> dict:
    _extent(data, 0, 76)
    pairs = struct.unpack_from("<16I", data, 12)
    names = ("effect_slots", "physics", "collisions", "effects", "functions",
             "properties", "instances", "splines")
    sections = {name: {"count": pairs[index * 2], "offset": pairs[index * 2 + 1]}
                for index, name in enumerate(names)}
    section = sections["collisions"]
    _extent(data, section["offset"], section["count"] * 12)
    collisions = []
    for index in range(section["count"]):
        start, size, count = struct.unpack_from("<3I", data, section["offset"] + index * 12)
        _extent(data, start, size)
        end = start + size
        pos = start
        meshes = []
        for _ in range(count):
            _extent(data, pos, 12, end)
            face_count, vertex_count, alignment = struct.unpack_from("<3I", data, pos)
            pos += 12
            _extent(data, pos, 12 * face_count + alignment + 16 * (vertex_count + face_count), end)
            indices = struct.unpack_from("<" + "I" * (3 * face_count), data, pos)
            if any(vertex >= vertex_count for vertex in indices):
                raise FormatError("Tricky SSF collision triangle has an invalid vertex")
            pos += 12 * face_count + alignment
            vertices = [list(struct.unpack_from("<4f", data, pos + vertex * 16))
                        for vertex in range(vertex_count)]
            pos += vertex_count * 16
            normals = [list(struct.unpack_from("<4f", data, pos + face * 16))
                       for face in range(face_count)]
            pos += face_count * 16
            if not all(math.isfinite(value) for vector in (*vertices, *normals) for value in vector):
                raise FormatError("Tricky SSF collision geometry is not finite")
            meshes.append({"vertices": vertices, "normals": normals,
                           "triangles": [list(indices[face * 3:face * 3 + 3])
                                         for face in range(face_count)]})
        collisions.append({"index": index, "meshes": meshes})

    section = sections["physics"]
    _extent(data, section["offset"], section["count"] * 12)
    physics = []
    for index in range(section["count"]):
        start, size, count = struct.unpack_from("<3I", data, section["offset"] + index * 12)
        _extent(data, start, size)
        end = start + size
        pos = start
        bodies = []
        for _ in range(count):
            body_start = pos
            _extent(data, pos, 112, end)
            alignment, mask_size, encoding, depth = struct.unpack_from("<4I", data, pos)
            center = list(struct.unpack_from("<3f", data, pos + 16))
            fields = list(struct.unpack_from("<3f", data, pos + 28))
            inertia = list(struct.unpack_from("<9f", data, pos + 40))
            inverse = list(struct.unpack_from("<9f", data, pos + 76))
            pos += 112
            _extent(data, pos, 12 * (depth + 1) + mask_size + alignment, end)
            levels = [struct.unpack_from("<2fI", data, pos + level * 12)
                      for level in range(depth + 1)]
            pos += 12 * (depth + 1)
            mask = data[pos:pos + mask_size]
            pos += mask_size + alignment
            bodies.append({"center": center, "source_fields": fields,
                           "inertia": inertia, "inverse_inertia": inverse,
                           "levels": levels, "encoding": encoding,
                           "mask_hex": mask.hex(), "raw_hex": data[body_start:pos].hex()})
        physics.append({"index": index, "bodies": bodies})

    section = sections["properties"]
    _extent(data, section["offset"], section["count"] * 24)
    properties = []
    for index in range(section["count"]):
        values = struct.unpack_from("<2f2Hi4h", data, section["offset"] + index * 24)
        mass, bounce, unknown, flags, surface, mode, collider, effect, u8 = values
        properties.append({"index": index, "mass": mass, "bounce": bounce,
                           "source_u2": unknown, "flags": flags, "surface": surface,
                           "collision_mode": mode, "collision_index": collider if mode != 3 else -1,
                           "physics_index": collider if mode == 3 else -1,
                           "effect_slot": effect, "source_u8": u8})
    section = sections["instances"]
    _extent(data, section["offset"], section["count"] * 4)
    instances = list(struct.unpack_from("<" + "I" * section["count"], data, section["offset"]))
    if any(index >= len(properties) for index in instances):
        raise FormatError("Tricky SSF instance references a missing property record")
    section = sections["splines"]
    _extent(data, section["offset"], section["count"] * 8)
    splines = []
    for index in range(section["count"]):
        unknown, flags, style = struct.unpack_from("<2hI", data, section["offset"] + index * 8)
        splines.append({"index": index, "source_u1": unknown,
                        "rail_flags": flags, "style": style})
    return {"collisions": collisions, "physics": physics, "properties": properties,
            "instance_properties": instances, "splines": splines}
