"""Inspect SSX Tricky PS2 level assets directly from a local retail ISO.

The ISO9660 reader and C0FB archive reader below are deliberately small and
read-only. Layout details were checked against SSX-Library's COFB and BDHandler
readers; see docs/modding/custom-tracks.md for source attribution.
"""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import math
import os
from pathlib import Path
import re
import struct

SECTOR = 2048
PBD_MAGIC = b"\x00\x15\x1b\x01"
PATCH_SIZE = 0x1C0
COUNTS = (
    "player_starts", "patches", "instances", "particle_instances",
    "materials", "material_blocks", "lights", "splines",
    "spline_segments", "texture_flipbooks", "models", "particle_models",
    "textures", "cameras", "lightmap_size",
)
OFFSETS = (
    "player_starts", "patches", "instances", "particle_instances",
    "materials", "material_blocks", "lights", "splines",
    "spline_segments", "texture_flipbooks", "model_pointers", "models",
    "particle_model_pointers", "particle_models", "camera_pointers",
    "cameras", "hash", "mesh_data",
)


class FormatError(ValueError):
    """The image or embedded level asset is unsupported or malformed."""


def _iso_directory(image, sector: int, size: int):
    image.seek(sector * SECTOR)
    directory = image.read(size)
    if len(directory) != size:
        raise FormatError("ISO directory extends beyond the image")
    pos = 0
    while pos < len(directory):
        length = directory[pos]
        if not length:
            pos = (pos // SECTOR + 1) * SECTOR
            continue
        record = directory[pos:pos + length]
        if length < 34 or len(record) != length or 33 + record[32] > length:
            raise FormatError("invalid ISO9660 directory record")
        name = record[33:33 + record[32]].decode("ascii", "replace")
        if name not in ("\x00", "\x01"):
            yield (
                name.split(";", 1)[0].upper(),
                struct.unpack_from("<I", record, 2)[0],
                struct.unpack_from("<I", record, 10)[0],
                bool(record[25] & 2),
            )
        pos += length


def read_iso_file(iso: Path, path: str) -> bytes:
    with iso.open("rb") as image:
        image.seek(16 * SECTOR)
        pvd = image.read(SECTOR)
        if len(pvd) != SECTOR or pvd[0] != 1 or pvd[1:6] != b"CD001":
            raise FormatError(f"{iso}: no ISO9660 primary volume descriptor")
        root = pvd[156:190]
        sector = struct.unpack_from("<I", root, 2)[0]
        size = struct.unpack_from("<I", root, 10)[0]
        parts = path.replace("\\", "/").upper().strip("/").split("/")
        for index, part in enumerate(parts):
            match = next(
                (entry for entry in _iso_directory(image, sector, size)
                 if entry[0] == part),
                None,
            )
            if match is None:
                raise FormatError(f"{iso}: missing {path} ({part})")
            _, sector, size, is_dir = match
            if is_dir != (index < len(parts) - 1):
                raise FormatError(f"{iso}: wrong ISO entry type for {part}")
        if size > 256 * 1024 * 1024:
            raise FormatError(f"{path}: unexpectedly large asset ({size} bytes)")
        image.seek(sector * SECTOR)
        result = image.read(size)
        if len(result) != size:
            raise FormatError(f"{path}: truncated ISO file")
        return result


def cofb_index(archive: bytes) -> dict[str, tuple[int, int]]:
    if archive[:2] != b"\xc0\xfb" or len(archive) < 6:
        raise FormatError("GARI.BIG is not a Tricky C0FB archive")
    header_size, count = struct.unpack_from(">HH", archive, 2)
    if not 6 <= header_size <= len(archive) or count > 4096:
        raise FormatError("invalid C0FB archive header")
    # Retail GARI.BIG reports 309 bytes, although the last filename ends
    # at 313. The first data offset is the reliable table boundary.
    data_begin = int.from_bytes(archive[6:9], "big") if count else header_size
    if not header_size <= data_begin <= len(archive):
        raise FormatError("invalid C0FB first member offset")
    pos = 6
    members = {}
    for _ in range(count):
        if pos + 6 > data_begin:
            raise FormatError("truncated C0FB member table")
        offset = int.from_bytes(archive[pos:pos + 3], "big")
        size = int.from_bytes(archive[pos + 3:pos + 6], "big")
        end = archive.find(b"\x00", pos + 6, data_begin)
        if end < 0:
            raise FormatError("unterminated C0FB member name")
        name = archive[pos + 6:end].decode("ascii", "replace")
        pos = end + 1
        if offset < header_size or offset + size > len(archive):
            raise FormatError(f"{name}: member extends beyond GARI.BIG")
        members[name.replace("\\", "/").casefold()] = (offset, size)
    return members


def read_cofb_member(archive: bytes, wanted: str) -> bytes:
    entry = cofb_index(archive).get(wanted.casefold())
    if entry is None:
        raise FormatError(f"GARI.BIG does not contain {wanted}")
    offset, size = entry
    member = archive[offset:offset + size]
    if len(member) >= 2 and member[1] == 0xFB:
        member = decode_refpack(member)
    return member


def decode_refpack(data: bytes) -> bytes:
    """Decode the EA RefPack command stream with strict output bounds."""
    if len(data) < 5 or data[1] != 0xFB:
        raise FormatError("invalid RefPack header")
    long_size = bool(data[0] & 0x80)
    size_bytes = 4 if long_size else 3
    pos = 2
    if pos + size_bytes > len(data):
        raise FormatError("truncated RefPack size")
    expected = int.from_bytes(data[pos:pos + size_bytes], "big")
    pos += size_bytes
    if data[0] & 1:
        pos += size_bytes  # Optional compressed size.
    if pos > len(data) or expected > 128 * 1024 * 1024:
        raise FormatError("invalid RefPack output size")
    output = bytearray()

    def take(count: int) -> bytes:
        nonlocal pos
        if pos + count > len(data):
            raise FormatError("truncated RefPack command")
        chunk = data[pos:pos + count]
        pos += count
        return chunk

    while len(output) < expected:
        control = take(1)[0]
        distance = 0
        match_len = 0
        if control < 0x80:
            second = take(1)[0]
            literal_len = control & 3
            distance = (((control >> 5) & 3) << 8) + second + 1
            match_len = ((control >> 2) & 7) + 3
        elif control < 0xC0:
            second, third = take(2)
            literal_len = second >> 6
            distance = ((second & 0x3F) << 8) + third + 1
            match_len = (control & 0x3F) + 4
        elif control < 0xE0:
            second, third, fourth = take(3)
            literal_len = control & 3
            distance = ((control & 0x10) << 12) + (second << 8) + third + 1
            match_len = ((control & 0x0C) << 6) + fourth + 5
        elif control < 0xFC:
            literal_len = ((control & 0x1F) + 1) * 4
        else:
            literal_len = control & 3
        if len(output) + literal_len + match_len > expected:
            raise FormatError("RefPack command exceeds output size")
        output.extend(take(literal_len))
        if match_len:
            if distance > len(output):
                raise FormatError("RefPack backward reference is out of range")
            for _ in range(match_len):
                output.append(output[-distance])
        if control >= 0xFC:
            break
    if len(output) != expected:
        raise FormatError("RefPack stream ended before expected output size")
    return bytes(output)


def parse_pbd(data: bytes, include_patches: bool) -> dict:
    if data[:4] != PBD_MAGIC or len(data) < 4 + 4 * (len(COUNTS) + len(OFFSETS)):
        raise FormatError("gari.pbd: unsupported PS2 PBD header")
    count_values = struct.unpack_from("<" + "I" * len(COUNTS), data, 4)
    offset_values = struct.unpack_from("<" + "I" * len(OFFSETS), data, 4 + 4 * len(COUNTS))
    counts = dict(zip(COUNTS, count_values))
    offsets = dict(zip(OFFSETS, offset_values))
    start = offsets["patches"]
    count = counts["patches"]
    if count > 100_000 or (count and start < 4 + 4 * (len(COUNTS) + len(OFFSETS))):
        raise FormatError("gari.pbd: invalid patch table")
    if start + count * PATCH_SIZE > len(data):
        raise FormatError("gari.pbd: truncated patch table")
    result = {
        "format": "ssx-tricky-ps2-pbd-v1",
        "source_sha256": hashlib.sha256(data).hexdigest(),
        "counts": counts,
        "offsets": offsets,
        "patch_record_bytes": PATCH_SIZE,
    }
    instance_ids = set()
    instances = []
    instance_start = offsets["instances"]
    instance_count = counts["instances"]
    instance_size = 0x100
    if instance_start + instance_count * instance_size > len(data):
        raise FormatError("Tricky PBD instance table is truncated")
    for index in range(instance_count):
        off = instance_start + index * instance_size
        model_id, previous, following = struct.unpack_from("<3I", data, off + 0xC0)
        instance_ids.add(model_id)
        if include_patches:
            matrix = struct.unpack_from("<16f", data, off)
            light_matrix = struct.unpack_from("<16f", data, off + 0x40)
            light_colours = struct.unpack_from("<16f", data, off + 0x80)
            bounds = struct.unpack_from("<6f", data, off + 0xCC)
            if not all(math.isfinite(v) for v in (*matrix, *light_matrix, *light_colours, *bounds)):
                raise FormatError(f"Tricky PBD instance {index} has a non-finite value")
            instances.append({
                "index": index,
                "model_id": model_id,
                "previous": previous,
                "next": following,
                "matrix": [list(matrix[i:i + 4]) for i in range(0, 16, 4)],
                "light_matrix": [list(light_matrix[i:i + 4]) for i in range(0, 16, 4)],
                "light_colours": [list(light_colours[i:i + 4]) for i in range(0, 16, 4)],
                "bounds_min": list(bounds[:3]),
                "bounds_max": list(bounds[3:]),
                "other_fields": list(struct.unpack_from("<7I", data, off + 0xE4)),
            })
    result["instance_summary"] = {
        "record_bytes": instance_size,
        "unique_model_ids": len(instance_ids),
        "largest_model_id": max(instance_ids, default=0),
    }
    if include_patches:
        result["instances"] = instances

    material_start = offsets["materials"]
    material_count = counts["materials"]
    material_size = 0x48
    if material_start + material_count * material_size > len(data):
        raise FormatError("Tricky PBD material table is truncated")
    if include_patches:
        result["materials"] = [
            {
                "index": index,
                "texture_id": struct.unpack_from("<h", data, material_start + index * material_size)[0],
                "appearance_flags": struct.unpack_from("<I", data, material_start + index * material_size + 0x40)[0],
                "texture_flipbook_id": struct.unpack_from("<h", data, material_start + index * material_size + 0x44)[0],
                "raw_hex": data[material_start + index * material_size:
                                material_start + (index + 1) * material_size].hex(),
            }
            for index in range(material_count)
        ]
    spline_start = offsets["splines"]
    segment_start = offsets["spline_segments"]
    spline_count = counts["splines"]
    segment_count = counts["spline_segments"]
    if (spline_start + spline_count * 40 > len(data) or
            segment_start + segment_count * 128 > len(data)):
        raise FormatError("Tricky PBD spline table is truncated")
    splines = []
    spline_ranges = []
    for index in range(spline_count):
        off = spline_start + index * 40
        bounds = struct.unpack_from("<6f", data, off)
        flags, count_segments, first_segment, next_spline = struct.unpack_from(
            "<4I", data, off + 24)
        if (not all(math.isfinite(v) for v in bounds) or
                any(bounds[axis] > bounds[axis + 3] for axis in range(3)) or
                first_segment + count_segments > segment_count):
            raise FormatError(f"Tricky PBD spline {index} has invalid bounds or segment range")
        spline_ranges.append((first_segment, count_segments))
        if include_patches:
            splines.append({
                "index": index, "bounds_min": list(bounds[:3]),
                "bounds_max": list(bounds[3:]), "flags": flags,
                "first_segment": first_segment, "segment_count": count_segments,
                "next_spline": next_spline,
            })
    segments = []
    segment_links = []
    for index in range(segment_count):
        off = segment_start + index * 128
        geometry = struct.unpack_from("<20f", data, off)
        previous, following, parent = struct.unpack_from("<3I", data, off + 80)
        bounds = struct.unpack_from("<6f", data, off + 92)
        length, previous_length = struct.unpack_from("<2f", data, off + 116)
        flags = struct.unpack_from("<I", data, off + 124)[0]
        if (not all(math.isfinite(v) for v in (*geometry, *bounds, length,
                                              previous_length)) or
                any(bounds[axis] > bounds[axis + 3] for axis in range(3)) or
                parent >= spline_count or
                previous != 0xffffffff and previous >= segment_count or
                following != 0xffffffff and following >= segment_count):
            raise FormatError(f"Tricky PBD spline segment {index} is invalid")
        segment_links.append((previous, following, parent))
        if include_patches:
            segments.append({
                "index": index,
                "coefficients": list(geometry[16:]),
                "control_points": [list(geometry[4 * i:4 * i + 4])
                                   for i in range(4)],
                "previous": previous, "next": following, "parent": parent,
                "bounds_min": list(bounds[:3]),
                "bounds_max": list(bounds[3:]),
                "length": length, "previous_length": previous_length,
                "flags": flags,
            })
    assigned = bytearray(segment_count)
    for spline, (first, count_segments) in enumerate(spline_ranges):
        for index in range(first, first + count_segments):
            if assigned[index] or segment_links[index][2] != spline:
                raise FormatError("Tricky PBD spline ranges overlap or disagree with segment parents")
            assigned[index] = 1
    if any(not value for value in assigned):
        raise FormatError("Tricky PBD contains an unassigned spline segment")
    for index, (previous, following, parent) in enumerate(segment_links):
        if (previous != 0xffffffff and
                (segment_links[previous][1] != index or
                 segment_links[previous][2] != parent)):
            raise FormatError(f"Tricky spline segment {index} has a broken previous link")
        if (following != 0xffffffff and
                (segment_links[following][0] != index or
                 segment_links[following][2] != parent)):
            raise FormatError(f"Tricky spline segment {index} has a broken next link")
    if include_patches:
        result["splines"] = splines
        result["spline_segments"] = segments
    if include_patches:
        patches = []
        surface_counts: Counter[int] = Counter()
        corner_max_error = 0.0
        for index in range(count):
            off = start + index * PATCH_SIZE
            # Tricky stores lightmap (16), four UV vectors (64), then
            # 16 power-basis coefficient vectors. Preserve the source order.
            coefficients = struct.unpack_from("<64f", data, off + 0x50)
            bounds = struct.unpack_from("<6f", data, off + 0x150)
            if not all(math.isfinite(v) for v in (*coefficients, *bounds)):
                raise FormatError(f"gari.pbd: non-finite patch {index}")
            vectors = [coefficients[i:i + 4] for i in range(0, 64, 4)]
            corners = [
                struct.unpack_from("<4f", data, off + 0x168 + 16 * corner)
                for corner in range(4)
            ]
            # Both games use the same descending power-basis layout. Check
            # all four endpoint combinations against Tricky's corner cache.
            for corner, terms in enumerate(((15,), (3, 7, 11, 15),
                                            (12, 13, 14, 15), tuple(range(16)))):
                for axis in range(3):
                    error = abs(sum(vectors[i][axis] for i in terms) - corners[corner][axis])
                    corner_max_error = max(corner_max_error, error)
                    if error > 0.25:
                        raise FormatError(f"gari.pbd: patch {index} coefficient/corner mismatch")
            surface = struct.unpack_from("<I", data, off + 0x1A8)[0]
            surface_counts[surface] += 1
            patches.append({
                "index": index,
                "lightmap_vector": list(struct.unpack_from("<4f", data, off)),
                "uv_vectors": [
                    list(struct.unpack_from("<4f", data, off + 0x10 + 16 * uv))
                    for uv in range(4)
                ],
                "coefficients": [list(vector) for vector in vectors],
                "bounds_min": list(bounds[:3]),
                "bounds_max": list(bounds[3:]),
                "corner_points": [list(corner) for corner in corners],
                "surface_type": surface,
                "resource_kind_tags": struct.unpack_from("<h", data, off + 0x1AC)[0],
                "visibility": struct.unpack_from("<h", data, off + 0x1AE)[0],
                "texture_assignment": struct.unpack_from("<h", data, off + 0x1B0)[0],
                "lightmap_id": struct.unpack_from("<h", data, off + 0x1B2)[0],
            })
        result["patches"] = patches
        result["surface_counts"] = dict(sorted(surface_counts.items()))
        result["corner_max_abs_error"] = corner_max_error
    return result


def _ltg_indices(data: bytes, base: int, offset: int, count: int, limit: int,
                 label: str) -> list[int]:
    if count < 0 or count > 65_535:
        raise FormatError("LTG node has an invalid resource count")
    if count == 0:
        return []
    start = base + offset
    if offset == 0 or start < 0 or start + count * 4 > len(data):
        raise FormatError("LTG resource list extends beyond the file")
    values = list(struct.unpack_from("<" + "I" * count, data, start))
    if any(value >= limit for value in values):
        raise FormatError(
            f"LTG {label} list at {start:#x} contains index {max(values)} "
            f"(source count {limit})"
        )
    return values


def parse_ltg(data: bytes, counts: dict, include_nodes: bool) -> dict:
    """Read Tricky's spatial grid and preserve its node-to-resource mapping."""
    if len(data) < 84 or data[:4] != b"\x00\x15\x1b\x00":
        raise FormatError("unsupported Tricky PS2 LTG header")
    bounds = [list(struct.unpack_from("<3f", data, 4 + i * 12)) for i in range(3)]
    box_size, width, height, total, occupied, empty = struct.unpack_from("<f5I", data, 40)
    node_size, sub_width, sub_count, pointer_offset, box_offset = struct.unpack_from("<f4I", data, 64)
    if (width * height != total or occupied + empty != total or
            not 0 < width <= 1024 or not 0 < height <= 1024 or
            not 0 < sub_width <= 16 or sub_width * sub_width != sub_count or
            pointer_offset + total * 4 > len(data) or box_offset >= len(data)):
        raise FormatError("invalid LTG grid dimensions or offsets")
    pointers = struct.unpack_from("<" + "I" * total, data, pointer_offset)
    if sum(pointer != 0 for pointer in pointers) != occupied:
        raise FormatError("LTG occupied cell count differs from its pointer grid")
    nodes = []
    seen_patches = set()
    seen_instances = set()
    seen_segments = set()
    patch_refs = 0
    instance_refs = 0
    segment_refs = 0
    for cell_index, base in enumerate(pointers):
        if base == 0:
            continue
        if base < box_offset or base + 84 + sub_count * 76 > len(data):
            raise FormatError("LTG main box extends beyond the file")
        for node_index in range(sub_count):
            node_base = base + 84 + node_index * 76
            node_counts = struct.unpack_from("<8h", data, node_base + 36)
            patch_count, instance_count, gem_split, spline_count = node_counts[:4]
            light_count, crossing_count, particle_count = node_counts[4:7]
            if any(value < 0 for value in node_counts[:7]):
                raise FormatError("LTG node has a negative resource count")
            offsets = struct.unpack_from("<6I", data, node_base + 52)
            patches = _ltg_indices(data, base, offsets[0], patch_count, counts["patches"], "patch")
            instances = _ltg_indices(data, base, offsets[1],
                                     max(instance_count, gem_split), counts["instances"], "instance")
            segments = _ltg_indices(data, base, offsets[2], spline_count,
                                    counts["spline_segments"], "spline segment")
            lights = _ltg_indices(data, base, offsets[3], light_count, counts["lights"], "light")
            crossing_lights = _ltg_indices(data, base, offsets[4], crossing_count, counts["lights"], "crossing light")
            particles = _ltg_indices(data, base, offsets[5], particle_count,
                                     counts["particle_instances"], "particle")
            if not any((patches, instances, segments, lights, crossing_lights, particles)):
                continue
            seen_patches.update(patches)
            seen_instances.update(instances)
            seen_segments.update(segments)
            patch_refs += len(patches)
            instance_refs += len(instances)
            segment_refs += len(segments)
            if include_nodes:
                nodes.append({
                    "grid": [cell_index % width, cell_index // width],
                    "subgrid": [node_index % sub_width, node_index // sub_width],
                    "bounds_min": list(struct.unpack_from("<3f", data, node_base)),
                    "bounds_max": list(struct.unpack_from("<3f", data, node_base + 12)),
                    "patches": patches,
                    "instances": instances,
                    "gem_split": gem_split,
                    "race_instances": instances[:instance_count],
                    "showoff_instances": instances[:gem_split],
                    "spline_segments": segments,
                    "lights": lights,
                    "crossing_lights": crossing_lights,
                    "particles": particles,
                })
    result = {
        "format": "ssx-tricky-ps2-ltg-v1",
        "source_sha256": hashlib.sha256(data).hexdigest(),
        "world_bounds": bounds,
        "grid": [width, height],
        "box_size": box_size,
        "subgrid": [sub_width, sub_width],
        "subbox_size": node_size,
        "occupied_cells": occupied,
        "patch_references": patch_refs,
        "unique_patches": len(seen_patches),
        "unreferenced_patches": sorted(set(range(counts["patches"])) - seen_patches),
        "instance_references": instance_refs,
        "unique_instances": len(seen_instances),
        "unreferenced_instances": sorted(set(range(counts["instances"])) - seen_instances),
        "spline_segment_references": segment_refs,
        "unique_spline_segments": len(seen_segments),
    }
    if include_nodes:
        result["nodes"] = nodes
    return result


def _unpack(data: bytes, offset: int, layout: str):
    size = struct.calcsize(layout)
    if offset < 0 or offset + size > len(data):
        raise FormatError("Tricky path record extends beyond AIP file")
    return struct.unpack_from(layout, data, offset), offset + size


def _parse_path(data: bytes, pos: int, kind: str, include_points: bool):
    if kind == "ai":
        fields, pos = _unpack(data, pos, "<7I")
        record = dict(zip(("type", "u1", "u2", "rating", "u4", "u5",
                           "respawnable"), fields))
    else:
        fields, pos = _unpack(data, pos, "<3If")
        record = dict(zip(("type", "u0", "u1", "distance_to_finish"), fields))
    (point_count, event_count), pos = _unpack(data, pos, "<2I")
    if point_count > 100_000 or event_count > 100_000:
        raise FormatError("Tricky AIP path has unreasonable point/event counts")
    origin, pos = _unpack(data, pos, "<3f")
    minimum, pos = _unpack(data, pos, "<3f")
    maximum, pos = _unpack(data, pos, "<3f")
    cursor = list(origin)
    measured_min = list(origin)
    measured_max = list(origin)
    points = []
    for _ in range(point_count):
        vector, pos = _unpack(data, pos, "<4f")
        if not all(math.isfinite(value) for value in vector):
            raise FormatError("Tricky AIP path has a non-finite vector")
        cursor = [cursor[i] + vector[i] * vector[3] for i in range(3)]
        measured_min = [min(measured_min[i], cursor[i]) for i in range(3)]
        measured_max = [max(measured_max[i], cursor[i]) for i in range(3)]
        if include_points:
            points.append(list(cursor))
    events = []
    for _ in range(event_count):
        event, pos = _unpack(data, pos, "<2I2f")
        if include_points:
            events.append({
                "type": event[0], "value": event[1],
                "start": event[2], "end": event[3],
            })
    bbox_error = max(
        *(abs(measured_min[i] - minimum[i]) for i in range(3)),
        *(abs(measured_max[i] - maximum[i]) for i in range(3)),
    )
    record.update({
        "origin": list(origin),
        "bounds_min": list(minimum),
        "bounds_max": list(maximum),
        "point_count": point_count,
        "event_count": event_count,
    })
    if include_points:
        record["points"] = points
        record["events"] = events
    return record, pos, bbox_error


def parse_aip(data: bytes, include_paths: bool) -> dict:
    """Read Tricky's AI graph and race line without importing its AI code."""
    if len(data) < 24 or data[:4] != b"\x0a" * 4:
        raise FormatError("unsupported Tricky AIP header")
    path_types, ai_offset, race_offset = struct.unpack_from("<3I", data, 4)
    if path_types != 2 or ai_offset + 24 > len(data) or race_offset + 32 > len(data):
        raise FormatError("invalid Tricky AIP path offsets")
    pos = ai_offset + 16
    (ai_count, start_count), pos = _unpack(data, pos, "<2I")
    if ai_count > 10_000 or start_count > 10_000:
        raise FormatError("invalid Tricky AIP AI path count")
    start_positions, pos = _unpack(data, pos, "<" + "I" * start_count)
    ai_paths = []
    bbox_error = 0.0
    ai_points = 0
    for _ in range(ai_count):
        path, pos, error = _parse_path(data, pos, "ai", include_paths)
        ai_paths.append(path)
        ai_points += path["point_count"]
        bbox_error = max(bbox_error, error)
    pos = race_offset + 16
    (unknown, byte_size, race_count, race_unknown), pos = _unpack(data, pos, "<4I")
    if race_count > 10_000:
        raise FormatError("invalid Tricky AIP race line count")
    race_paths = []
    race_points = 0
    for _ in range(race_count):
        path, pos, error = _parse_path(data, pos, "race", include_paths)
        race_paths.append(path)
        race_points += path["point_count"]
        bbox_error = max(bbox_error, error)
    result = {
        "format": "ssx-tricky-ps2-aip-v1",
        "source_sha256": hashlib.sha256(data).hexdigest(),
        "start_positions": list(start_positions),
        "ai_path_count": ai_count,
        "ai_point_count": ai_points,
        "race_path_count": race_count,
        "race_point_count": race_points,
        "path_bounds_max_abs_error": bbox_error,
        "race_header": [unknown, byte_size, race_unknown],
    }
    if include_paths:
        result["ai_paths"] = ai_paths
        result["race_paths"] = race_paths
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--iso", type=Path, default=Path(os.environ.get("SSX_TRICKY_ISO", "SSX Tricky (USA).iso")))
    parser.add_argument("--track", default="GARI", help="Tricky model archive stem (default: GARI)")
    parser.add_argument("--list-members", action="store_true", help="list files inside the track's C0FB archive")
    parser.add_argument("--output", type=Path, help="write inspectable JSON with every source patch")
    args = parser.parse_args()
    track = args.track.upper()
    if not re.fullmatch(r"[A-Z0-9]{1,8}", track):
        parser.error("--track must be a 1-8 character archive stem")
    try:
        system = read_iso_file(args.iso, "SYSTEM.CNF")
        if b"SLUS_203.26" not in system:
            raise FormatError(f"{args.iso}: expected SSX Tricky USA (SLUS_203.26)")
        archive = read_iso_file(args.iso, f"DATA/MODELS/{track}.BIG")
        if args.list_members:
            for name, (_, size) in cofb_index(archive).items():
                print(f"{size:>9}  {name}")
            return 0
        pbd = read_cofb_member(archive, f"data/models/{track.lower()}.pbd")
        result = parse_pbd(pbd, args.output is not None)
        ltg = read_cofb_member(archive, f"data/models/{track.lower()}.ltg")
        result["spatial"] = parse_ltg(ltg, result["counts"], args.output is not None)
        aip = read_cofb_member(archive, f"data/models/{track.lower()}.aip")
        result["paths"] = parse_aip(aip, args.output is not None)
        result["track"] = track
    except (OSError, FormatError) as error:
        parser.exit(2, f"tricky assets: {error}\n")
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        print(f"wrote {args.output} ({len(result['patches'])} patches)")
    else:
        print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
