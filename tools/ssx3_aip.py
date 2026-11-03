"""Convert Tricky AIP route records to an SSX 3 WorldAIP resource body.

Both games use the same 7-word AI and 4-word race-path headers, followed by
direction/distance points and events. Tricky wraps the two sections in an
offset table and stores starter path indices separately. SSX 3 uses one
contiguous resource with additional trailing tables. A declared main route
also supplies native start and recovery markers from the source paths.
"""

from __future__ import annotations

import argparse
import json
import math
import os
from pathlib import Path
import re
import struct

from tricky_assets import FormatError, read_cofb_member, read_iso_file


def _u32(data: bytes, pos: int) -> int:
    if pos < 0 or pos + 4 > len(data):
        raise FormatError("AIP word extends beyond the resource")
    return struct.unpack_from("<I", data, pos)[0]


def _skip_path(data: bytes, pos: int, kind: str) -> int:
    fixed = 7 * 4 if kind == "ai" else 4 * 4
    if pos < 0 or pos + fixed + 8 + 36 > len(data):
        raise FormatError(f"AIP {kind} path header is truncated")
    points, events = struct.unpack_from("<2I", data, pos + fixed)
    if points > 100_000 or events > 100_000:
        raise FormatError(f"AIP {kind} path count is unreasonable")
    end = pos + fixed + 8 + 36 + 16 * (points + events)
    if end > len(data):
        raise FormatError(f"AIP {kind} path body is truncated")
    return end


def inspect_world_aip(data: bytes) -> dict:
    """Validate and summarize one SSX 3 type-14 WorldAIP payload."""
    if len(data) < 20 or data[:4] != b"iiii":
        raise FormatError("unsupported SSX 3 WorldAIP header")
    pos = 4
    ai_count = _u32(data, pos)
    pos += 4
    if ai_count > 100_000:
        raise FormatError("SSX 3 WorldAIP AI path count is unreasonable")
    for _ in range(ai_count):
        pos = _skip_path(data, pos, "ai")
    race_count = _u32(data, pos)
    pos += 4
    if race_count > 100_000:
        raise FormatError("SSX 3 WorldAIP race path count is unreasonable")
    for _ in range(race_count):
        pos = _skip_path(data, pos, "race")
    u0_count = _u32(data, pos)
    pos += 4
    if u0_count > 100_000 or pos + u0_count * 8 > len(data):
        raise FormatError("SSX 3 WorldAIP first trailing table is truncated")
    pos += u0_count * 8
    u1_count = _u32(data, pos)
    pos += 4
    if u1_count > 100_000 or pos + u1_count * 40 != len(data):
        raise FormatError("SSX 3 WorldAIP second trailing table has wrong size")
    return {
        "ai_paths": ai_count,
        "race_paths": race_count,
        "trailing_u0_records": u0_count,
        "trailing_u1_records": u1_count,
        "bytes": len(data),
    }


def _path_geometry(data: bytes, pos: int, kind: str) -> dict:
    fixed = 28 if kind == "ai" else 16
    count = _u32(data, pos + fixed)
    origin = struct.unpack_from("<3f", data, pos + fixed + 8)
    vectors = [struct.unpack_from("<4f", data, pos + fixed + 44 + index * 16)
               for index in range(count)]
    points = [origin]
    for vector in vectors:
        points.append(tuple(points[-1][axis] + vector[axis] * vector[3]
                            for axis in range(3)))
    return {"origin": origin, "vectors": vectors, "points": points,
            "remaining": struct.unpack_from("<f", data, pos + 12)[0]
            if kind == "race" else None}


def _sample_path(path: dict, distance: float) -> tuple[tuple, tuple]:
    position = path["origin"]
    for vector in path["vectors"]:
        step = min(max(distance, 0), vector[3])
        position = tuple(position[axis] + vector[axis] * step for axis in range(3))
        distance -= step
        if distance <= 0:
            return position, vector
    return position, path["vectors"][-1]


def _events(record: bytes, kind: str) -> list[tuple]:
    fixed = 28 if kind == "ai" else 16
    points, events = struct.unpack_from("<2I", record, fixed)
    start = fixed + 44 + 16 * points
    return [struct.unpack_from("<IIff", record, start + index * 16)
            for index in range(events)]


def _native_path_records(ai: list[bytes], race: list[bytes],
                         main_route: tuple[int, ...], freestyle: bool = False) -> tuple[bytes, bytes]:
    # SSX 3 maps stored event keys through Path_ReadEvent's native table.
    # In particular key 0 finishes a race and key 18 marks a checkpoint.
    # Tricky key 9 is its finish, and key 11 awards time at its gates.
    checkpoints = []
    for index in main_route:
        remaining = struct.unpack_from("<f", race[index], 12)[0]
        checkpoints.extend(remaining - start for key, _, start, _ in
                           _events(race[index], "race") if key == 11)

    def rebuild(record: bytes, kind: str, index: int) -> bytes:
        fixed = 28 if kind == "ai" else 16
        points = _u32(record, fixed)
        body = bytearray(record[:fixed + 44 + 16 * points])
        source = _events(record, kind)
        if kind == "ai":
            # These keys exist in SSX 3's native AI event table. Unsupported
            # Tricky commands (notably 105) are omitted, not reinterpreted.
            native = [event for event in source
                      if event[0] in (100, 101, 102, 103, 110, 111, 112, 113, 300)]
        else:
            native = []
            remaining = struct.unpack_from("<f", record, 12)[0]
            for key, value, start, end in source:
                if key == 11 and checkpoints:
                    checkpoint = min(range(len(checkpoints)),
                                     key=lambda item: abs(checkpoints[item] - (remaining - start)))
                    if freestyle:
                        # Stored 12 is inert in SSX 3 (runtime event 5). The
                        # custom rider consumes the encoded SOP group/seconds;
                        # these are not indices into Snow Jam's camera table.
                        if value > 600:
                            raise FormatError("SOP checkpoint award exceeds 600 seconds")
                        native.append((12, (value << 16) | checkpoint, start, end))
                    else:
                        native.append((18, checkpoint, start, end))
                elif key == 12 and not freestyle:
                    # The native rider adapter consumes the original pass
                    # countdown; key 12 is otherwise inert in SSX 3.
                    native.append((12, value, start, end))
            if index == main_route[-1]:
                finishes = [start for key, _, start, _ in source if key == 9]
                if not finishes:
                    raise FormatError("the final Tricky route has no finish event")
                finish = min(finishes)
                native.append((0, 0, finish, finish))
        struct.pack_into("<I", body, fixed + 4, len(native))
        body.extend(b"".join(struct.pack("<IIff", *event) for event in native))
        return bytes(body)

    return (b"".join(rebuild(record, "ai", index) for index, record in enumerate(ai)),
            b"".join(rebuild(record, "race", index) for index, record in enumerate(race)))


def _direction(vector: tuple[float, ...]) -> tuple[float, ...]:
    norm = math.sqrt(sum(value * value for value in vector[:3]))
    if not math.isfinite(norm) or norm == 0:
        raise FormatError("AIP marker has no source direction")
    return tuple(value / norm for value in vector[:3])


def _native_markers(ai: list[dict], race: list[dict], starts: list[int],
                    main_route: tuple[int, ...]) -> bytes:
    if not main_route or any(index >= len(race) or index < 0 for index in main_route):
        raise FormatError("AIP main route contains a missing race path")
    markers = []
    def route_distance(index: int, position: tuple[float, ...]) -> float:
        # A lap course can start near the end of its circuit. Link the actual
        # source segment rather than forcing every start onto the first path.
        points = race[index]["points"]
        best = math.inf
        for a, b in zip(points, points[1:]):
            delta = tuple(b[i] - a[i] for i in range(3))
            length2 = sum(value * value for value in delta)
            t = (sum((position[i] - a[i]) * delta[i] for i in range(3)) / length2
                 if length2 else 0.)
            t = min(max(t, 0.), 1.)
            best = min(best, sum((position[i] - a[i] - t * delta[i]) ** 2
                                 for i in range(3)))
        return best

    for lane, path_index in enumerate(starts):
        path = ai[path_index]
        route = min(main_route, key=lambda index: route_distance(index, path["origin"]))
        markers.append((lane, 0, *path["origin"],
                        *_direction(path["vectors"][0]), path_index, route))

    def nearest_ai(position: tuple[float, ...]) -> int:
        return min(range(len(ai)), key=lambda index: min(
            sum((point[axis] - position[axis]) ** 2 for axis in range(3))
            for point in ai[index]["points"]))

    # Type 1 markers are recovery anchors. Their final two words link the
    # native AIPath and TrackPath arrays; they are not world section IDs.
    # Keep the source route's junctions rather than inventing checkpoint
    # positions at arbitrary distances along the course.
    for marker_id, path_index in enumerate(main_route, 1):
        path = race[path_index]
        position = path["origin"]
        markers.append((marker_id, 1, *position,
                        *_direction(path["vectors"][0]),
                        nearest_ai(position), path_index))
    final_index = main_route[-1]
    final = race[final_index]
    position, direction = _sample_path(final, final["remaining"])
    markers.append((0, 1, *position, *_direction(direction),
                    nearest_ai(position), final_index))
    return (struct.pack("<I", len(starts)) + b"\0" * (8 * len(starts)) +
            struct.pack("<I", len(markers)) +
            b"".join(struct.pack("<II6fII", *marker) for marker in markers))


def convert_tricky_aip(data: bytes, *,
                       main_route: tuple[int, ...] | None = None,
                       freestyle: bool = False) -> tuple[bytes, list[int]]:
    """Preserve Tricky's routes and return its separate starter path indices."""
    if len(data) < 48 or data[:4] != b"\x0a" * 4:
        raise FormatError("unsupported Tricky AIP header")
    section_count, ai_offset, race_offset = struct.unpack_from("<3I", data, 4)
    if section_count != 2 or ai_offset + 24 > len(data) or race_offset + 32 > len(data):
        raise FormatError("invalid Tricky AIP section offsets")
    ai_count, start_count = struct.unpack_from("<2I", data, ai_offset + 16)
    if ai_count > 100_000 or start_count > 100_000:
        raise FormatError("Tricky AIP path/start count is unreasonable")
    start_pos = ai_offset + 24
    ai_begin = start_pos + 4 * start_count
    if ai_begin > len(data):
        raise FormatError("Tricky AIP starter table is truncated")
    starts = list(struct.unpack_from("<" + "I" * start_count, data, start_pos))
    if any(start >= ai_count for start in starts):
        raise FormatError("Tricky AIP starter path index is out of range")
    ai_end = ai_begin
    ai_geometry = []
    ai_records = []
    for _ in range(ai_count):
        end = _skip_path(data, ai_end, "ai")
        if main_route is not None:
            ai_geometry.append(_path_geometry(data, ai_end, "ai"))
            ai_records.append(data[ai_end:end])
        ai_end = end
    race_header = race_offset + 16
    if ai_end != race_header:
        raise FormatError("Tricky AIP AI records do not meet the race section")
    race_count = _u32(data, race_header + 8)
    if race_count > 100_000:
        raise FormatError("Tricky AIP race path count is unreasonable")
    race_begin = race_header + 16
    race_end = race_begin
    race_geometry = []
    race_records = []
    for _ in range(race_count):
        end = _skip_path(data, race_end, "race")
        if main_route is not None:
            race_geometry.append(_path_geometry(data, race_end, "race"))
            race_records.append(data[race_end:end])
        race_end = end
    if race_end != len(data):
        raise FormatError("Tricky AIP has unexpected trailing bytes")
    markers = (struct.pack("<2I", 0, 0) if main_route is None else
               _native_markers(ai_geometry, race_geometry, starts, main_route))
    ai_body, race_body = ((data[ai_begin:ai_end], data[race_begin:race_end])
                          if main_route is None else
                          _native_path_records(ai_records, race_records, main_route, freestyle))
    target = (b"iiii" + struct.pack("<I", ai_count) + ai_body +
              struct.pack("<I", race_count) + race_body +
              markers)
    inspect_world_aip(target)
    return target, starts


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--iso", type=Path,
                        default=Path(os.environ.get("SSX_TRICKY_ISO", "SSX Tricky (USA).iso")))
    parser.add_argument("--track", default="GARI", help="Tricky archive stem (default: GARI)")
    parser.add_argument("--output", type=Path, required=True,
                        help="write the converted WorldAIP body outside Git, e.g. .cache/gari.aip14")
    args = parser.parse_args()
    track = args.track.upper()
    if not re.fullmatch(r"[A-Z0-9]{1,8}", track):
        parser.error("--track must be a 1-8 character archive stem")
    try:
        system = read_iso_file(args.iso, "SYSTEM.CNF")
        if b"SLUS_203.26" not in system:
            raise FormatError(f"{args.iso}: expected SSX Tricky USA (SLUS_203.26)")
        archive = read_iso_file(args.iso, f"DATA/MODELS/{track}.BIG")
        source = read_cofb_member(archive, f"data/models/{track.lower()}.aip")
        converted, starts = convert_tricky_aip(source)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_bytes(converted)
    except (OSError, FormatError) as error:
        parser.exit(2, f"SSX 3 AIP converter: {error}\n")
    print(json.dumps({"track": track, "output": str(args.output),
                      "starter_ai_path_indices": starts,
                      **inspect_world_aip(converted)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
