"""Convert Tricky AIP route records to an SSX 3 WorldAIP resource body.

Both games use the same 7-word AI and 4-word race-path headers, followed by
direction/distance points and events. Tricky wraps the two sections in an
offset table and stores starter path indices separately. SSX 3 uses one
contiguous resource with additional trailing tables. The caller retains the
starter indices as race metadata; no SSX 3 start table is guessed here.
"""

from __future__ import annotations

import argparse
import json
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


def convert_tricky_aip(data: bytes) -> tuple[bytes, list[int]]:
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
    for _ in range(ai_count):
        ai_end = _skip_path(data, ai_end, "ai")
    race_header = race_offset + 16
    if ai_end != race_header:
        raise FormatError("Tricky AIP AI records do not meet the race section")
    race_count = _u32(data, race_header + 8)
    if race_count > 100_000:
        raise FormatError("Tricky AIP race path count is unreasonable")
    race_begin = race_header + 16
    race_end = race_begin
    for _ in range(race_count):
        race_end = _skip_path(data, race_end, "race")
    if race_end != len(data):
        raise FormatError("Tricky AIP has unexpected trailing bytes")
    target = (b"iiii" + struct.pack("<I", ai_count) + data[ai_begin:ai_end] +
              struct.pack("<I", race_count) + data[race_begin:race_end] +
              struct.pack("<2I", 0, 0))
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
