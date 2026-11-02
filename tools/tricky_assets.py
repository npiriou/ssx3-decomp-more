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


def read_cofb_member(archive: bytes, wanted: str) -> bytes:
    if archive[:2] != b"\xc0\xfb" or len(archive) < 6:
        raise FormatError("GARI.BIG is not a Tricky C0FB archive")
    header_size, count = struct.unpack_from(">HH", archive, 2)
    if not 6 <= header_size <= len(archive) or count > 4096:
        raise FormatError("invalid C0FB archive header")
    pos = 6
    for _ in range(count):
        if pos + 6 > header_size:
            raise FormatError("truncated C0FB member table")
        offset = int.from_bytes(archive[pos:pos + 3], "big")
        size = int.from_bytes(archive[pos + 3:pos + 6], "big")
        end = archive.find(b"\x00", pos + 6, header_size)
        if end < 0:
            raise FormatError("unterminated C0FB member name")
        name = archive[pos + 6:end].decode("ascii", "replace")
        pos = end + 1
        if name.replace("\\", "/").casefold() != wanted.casefold():
            continue
        if offset < header_size or offset + size > len(archive):
            raise FormatError(f"{name}: member extends beyond GARI.BIG")
        member = archive[offset:offset + size]
        if len(member) >= 2 and member[1] == 0xFB:
            member = decode_refpack(member)
        return member
    raise FormatError(f"GARI.BIG does not contain {wanted}")


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
    if count > 100_000 or start < 4 + 4 * (len(COUNTS) + len(OFFSETS)):
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


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--iso", type=Path, default=Path(os.environ.get("SSX_TRICKY_ISO", "SSX Tricky (USA).iso")))
    parser.add_argument("--track", default="GARI", help="Tricky model archive stem (default: GARI)")
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
        pbd = read_cofb_member(archive, f"data/models/{track.lower()}.pbd")
        result = parse_pbd(pbd, args.output is not None)
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
