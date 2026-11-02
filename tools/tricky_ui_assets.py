"""Extract original Tricky presentation cards and logo into native SSH files."""

from __future__ import annotations

from pathlib import Path
import struct

from ssx3_world_archive import pack_bigf
from ssx3_world_probe import bigf_members
from tricky_assets import read_cofb_member, read_iso_file
from tricky_courses import COURSES
from tricky_ssh import _psmt8_palette


def image_entry(shps: bytes, name: bytes | None = None) -> bytes:
    count = struct.unpack_from("<I", shps, 8)[0]
    for i in range(count):
        key, offset = struct.unpack_from("<4sI", shps, 16 + i * 8)
        if name is None or key == name:
            end = struct.unpack_from("<I", shps, 28 + i * 8)[0] if i + 1 < count else len(shps)
            return shps[offset:end]
    raise ValueError(f"SSH image {name!r} is absent")


def native_shps(entry: bytes, template: bytes) -> bytes:
    """Use the frontend's 16-byte shape envelope, not WorldSSH's 128 bytes.

    Native UI palettes encode 256 colors as 255 and carry a block length.
    Retain that exact envelope and replace only the original indexed texels
    and CLUT. WorldSSH entries have a different resource-loading contract.
    """
    if entry[0] != 2 or struct.unpack_from("<2H", entry, 4) != (256, 256):
        raise ValueError("course presentation card must be indexed 256x256")
    if struct.unpack_from("<I", entry, 12)[0] & 0x2000:
        raise ValueError("course presentation texels must be linear")
    size = int.from_bytes(entry[1:4], "little")
    colors = entry[size + 16:size + 16 + 1024]
    if not struct.unpack_from("<I", entry, size + 12)[0] & 0x2000:
        colors = _psmt8_palette(colors)
    result = bytearray(template)
    offset = struct.unpack_from("<I", result, 20)[0]
    result[offset + 16:offset + 16 + 65536] = entry[16:16 + 65536]
    palette = offset + int.from_bytes(result[offset + 1:offset + 4], "little")
    result[palette + 16:palette + 16 + 1024] = colors
    return bytes(result)


def prepare(tricky_iso: Path, overlay: Path, ssx3_iso: Path = Path("SSX 3 (USA).iso")) -> None:
    loading = read_iso_file(tricky_iso, "DATA/TEXTURES/PS2LOAD.BIG")
    logo_container = read_iso_file(tricky_iso, "DATA/TEXTURES/LOADING.SSH")
    logo = bytearray(image_entry(logo_container, b"loa2"))
    width, height = struct.unpack_from("<2H", logo, 4)
    image_end = int.from_bytes(logo[1:4], "little")
    if (width, height) != (256, 256) or struct.unpack_from("<I", logo, 12)[0] & 0x2000:
        raise ValueError("unexpected Tricky loading logo layout")
    # The original logo occupies the top 148 rows of this UI atlas. Keep
    # those exact indexed texels, centered on a transparent 256-square card;
    # discard only the unrelated progress widgets below the logo.
    palette = logo[image_end + 16:image_end + 16 + 1024]
    transparent = next(i for i in range(256) if palette[i * 4 + 3] == 0)
    pixels = bytes(logo[16:16 + 256 * 148])
    logo[16:image_end] = bytes([transparent]) * (256 * 256)
    logo[16 + 54 * 256:16 + 202 * 256] = pixels
    ui = overlay / "DATA/UI/TRICKY"
    ui.mkdir(parents=True, exist_ok=True)
    maps = bigf_members(read_iso_file(ssx3_iso, "DATA/UI/MAPGFX.BIG"))
    template = maps["map_mtn.ssh"]
    logo_ssh = native_shps(bytes(logo), template)
    (ui / "logo.ssh").write_bytes(logo_ssh)
    maps["tricky_logo.ssh"] = logo_ssh
    for course in COURSES:
        if course.preview:
            source = read_cofb_member(loading, f"ldtrack{course.preview}.ssh")
            ssh = native_shps(image_entry(source), template)
        else:
            ssh = logo_ssh
        (ui / f"{course.code}.ssh").write_bytes(ssh)
        maps[f"tricky_{course.code.lower()}.ssh"] = ssh
        # The game requests a native template's name inside courspic.big.
        # Keep both names, so Race and Freestyle share the source card.
        (ui / f"{course.code}.BIG").write_bytes(pack_bigf([
            ("ara1.ssh", ssh), ("ass1.ssh", ssh)]))
    (overlay / "DATA/UI/MAPGFX.BIG").write_bytes(pack_bigf(list(maps.items())))


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tricky-iso", required=True, type=Path)
    parser.add_argument("--overlay", default=Path(".cache/overlay"), type=Path)
    args = parser.parse_args()
    prepare(args.tricky_iso, args.overlay)
