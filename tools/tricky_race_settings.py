"""Read the USA executable's course catalogue, including Showoff clock seeds.

The level archives do not contain the initial duration. SLUS_203.26 stores
twelve 28-byte rows at file offset 0x233f28; the duration is in hundredths.
Names and stems are followed through ELF load segments rather than copied
from a host course-name table. No executable bytes are emitted into Git.
"""

import struct
from functools import lru_cache

from tricky_assets import FormatError, read_iso_file


@lru_cache(maxsize=4)
def showoff_catalog(iso):
    elf = read_iso_file(iso, "SLUS_203.26")
    if elf[:6] != b"\x7fELF\x01\x01":
        raise FormatError("Tricky USA clock catalogue requires a little-endian ELF32")
    ph_at = struct.unpack_from("<I", elf, 28)[0]
    ph_size, ph_count = struct.unpack_from("<2H", elf, 42)
    segments = [struct.unpack_from("<8I", elf, ph_at + i * ph_size)
                for i in range(ph_count)]

    def string(address):
        for kind, offset, virtual, _, size, _, _, _ in segments:
            if kind == 1 and virtual <= address < virtual + size:
                pos = offset + address - virtual
                end = elf.find(b"\0", pos, min(pos + 64, offset + size))
                if end >= 0:
                    return elf[pos:end].decode("ascii")
        raise FormatError("Tricky course catalogue string is outside an ELF load segment")

    result = {}
    for index in range(12):
        at = 0x233f28 + index * 28
        slot, name, _, hundredths, stem, _, _ = struct.unpack_from("<7I", elf, at)
        if slot != index or hundredths > 30000:
            raise FormatError("unexpected Tricky USA course catalogue layout")
        code = string(stem).upper()
        if code in result:
            raise FormatError("duplicate Tricky course catalogue stem")
        result[code] = {"name": string(name), "showoff_hundredths": hundredths,
                        "source_executable": "SLUS_203.26",
                        "source_duration_file_offset": at + 12}
    return result
