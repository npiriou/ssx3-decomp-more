"""Add a Bonus row to SSX 3's Single Event peak list and locale.

The modified files are derived from the user's SSX 3 ISO and belong only in
the data overlay. No disc assets are stored in Git.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import struct

from ssx3_world_build import encode_refpack_literals
from tricky_assets import FormatError, decode_refpack, read_iso_file


PEAK1 = 0x0056B7E1
PEAK4 = 0x0056B7E4
MOUNTAIN = 0x06C5AD7E
PEAK_LIST = 0x0BD0F864
EVENT_SELECT_SCREEN = 0x5380


def str_hash(value: str) -> int:
    """SSX 3's signed-byte variant of the ELF string hash."""
    result = 0
    for byte in value.encode("ascii"):
        result = ((result << 4) + byte) & 0xffffffff
        top = result & 0xf0000000
        if top:
            result ^= (top >> 23) ^ top
    return result


BONUS_TEXT = str_hash("kT_BonusPeakName")
GARIBALDI_TEXT = str_hash("kT_CustomGaribaldiName")
BONUS_GOALS = str_hash("SPG_BonusGoals")
BONUS_RACE = str_hash("BonusRaceLocations")
BONUS_RACE_ITEM = str_hash("BonusRace")
GARIBALDI_ITEM = str_hash("BonusGaribaldi")


def _records(data: bytes, pos: int, count: int) -> tuple[list[bytearray], int]:
    rows = []
    for _ in range(count):
        if pos + 4 > len(data):
            raise FormatError("LUI row header is truncated")
        size = struct.unpack_from("<H", data, pos + 2)[0]
        if size < 8 or pos + size > len(data):
            raise FormatError("LUI row extends beyond the screen")
        rows.append(bytearray(data[pos:pos + size]))
        pos += size
    return rows, pos


def _row(rows: list[bytearray], name: int) -> bytearray:
    return next(row for row in rows if struct.unpack_from("<I", row, 4)[0] == name)


def add_peak_to_screen(screen: bytes) -> bytes:
    if len(screen) < 32 or struct.unpack_from("<I", screen)[0] != EVENT_SELECT_SCREEN:
        raise FormatError("FE.LUI does not contain the expected Event Select screen")
    second = struct.unpack_from("<I", screen, 8)[0]
    first_count = struct.unpack_from("<I", screen, 16)[0]
    first, end = _records(screen, 20, first_count)
    if end != second or first_count != 377:
        raise FormatError("Event Select widget table differs from the USA disc")
    first_peak = _row(first, PEAK1)
    bonus_widget = bytearray(first_peak)
    struct.pack_into("<I", bonus_widget, 4, PEAK4)
    struct.pack_into("<I", bonus_widget, 36, BONUS_TEXT)
    first.insert(first.index(first_peak) + 1, bonus_widget)

    peak_list = _row(first, PEAK_LIST)
    if (len(peak_list) != 52 or struct.unpack_from("<I", peak_list, 32)[0] != 4
            or struct.unpack_from("<I", peak_list, 48)[0] != MOUNTAIN):
        raise FormatError("Event Select peak list differs from the USA disc")
    struct.pack_into("<H", peak_list, 2, 56)
    struct.pack_into("<I", peak_list, 32, 5)
    # Menu children are prepended by the UI loader: serialize Bonus first
    # so the selectable order remains Peak1, Peak2, Peak3, Bonus.
    peak_list[36:36] = struct.pack("<I", PEAK4)

    second_header = bytearray(screen[second:second + 16])
    second_count = struct.unpack_from("<H", second_header, 14)[0]
    third_relative = struct.unpack_from("<I", second_header, 8)[0]
    properties, properties_end = _records(screen, second + 16, second_count)
    if second_count != first_count or properties_end != second + 4 + third_relative:
        raise FormatError("Event Select property table differs from its header")
    source = _row(properties, PEAK1)
    bonus_property = bytearray(source)
    if len(source) != 68 or struct.unpack_from("<H", source, 18)[0] != 50:
        raise FormatError("Peak1 layout differs from the USA disc")
    struct.pack_into("<I", bonus_property, 4, PEAK4)
    struct.pack_into("<h", bonus_property, 18, -25)
    properties.insert(properties.index(source) + 1, bonus_property)
    peak_list_property = _row(properties, PEAK_LIST)
    if struct.unpack_from("<H", peak_list_property, 38)[0] != 120:
        raise FormatError("Event Select peak-list height differs from the USA disc")
    struct.pack_into("<H", peak_list_property, 38, 145)

    # Separate native UIMenu objects keep the custom panels out of the
    # original three-peak event arrays. Each contains exactly one item.
    for old_root, new_root, new_child, text in (
            (str_hash("SPG_Peak1Goals"), BONUS_GOALS,
             BONUS_RACE_ITEM, None),
            (str_hash("Peak1RaceLocations"), BONUS_RACE,
             GARIBALDI_ITEM, GARIBALDI_TEXT)):
        root = _row(first, old_root)
        child_name = struct.unpack_from("<I", root, 36)[0]
        child = bytearray(_row(first, child_name))
        new_menu = bytearray(root[:36] + struct.pack("<I", new_child))
        struct.pack_into("<H", new_menu, 2, len(new_menu))
        struct.pack_into("<I", new_menu, 4, new_root)
        struct.pack_into("<I", new_menu, 32, 1)
        struct.pack_into("<I", child, 4, new_child)
        if text is not None:
            struct.pack_into("<I", child, 36, text)
        first.extend((child, new_menu))
        for old_name, new_name in ((child_name, new_child), (old_root, new_root)):
            layout = bytearray(_row(properties, old_name))
            struct.pack_into("<I", layout, 4, new_name)
            properties.append(layout)

    first_bytes = b"".join(first)
    properties_bytes = b"".join(properties)
    new_second = 20 + len(first_bytes)
    struct.pack_into("<H", second_header, 14, len(properties))
    struct.pack_into("<I", second_header, 8, 12 + len(properties_bytes))
    header = bytearray(screen[:20])
    struct.pack_into("<I", header, 8, new_second)
    struct.pack_into("<I", header, 16, len(first))
    return (bytes(header) + first_bytes + bytes(second_header) +
            properties_bytes + screen[properties_end:])


def add_bonus_locale(data: bytes) -> bytes:
    if data[:4] != b"LOCH" or data[20:24] != b"LOCT":
        raise FormatError("CMNAMER.LOC has an unsupported header")
    table_end = struct.unpack_from("<I", data, 16)[0]
    if data[table_end:table_end + 4] != b"LOCL":
        raise FormatError("CMNAMER.LOC has no LOCL string table")
    entries = [struct.unpack_from("<II", data, pos)
               for pos in range(28, table_end, 8)]
    additions = ((BONUS_TEXT, "Bonus"), (GARIBALDI_TEXT, "Garibaldi"))
    if len(entries) != 1387 or any(key in (BONUS_TEXT, GARIBALDI_TEXT) for key, _ in entries):
        raise FormatError("CMNAMER.LOC differs from the USA disc")
    chunk = bytearray(data[table_end:])
    count = struct.unpack_from("<I", chunk, 12)[0]
    if count != 1386 or len(chunk) != struct.unpack_from("<I", chunk, 4)[0]:
        raise FormatError("CMNAMER.LOC string count differs from the USA disc")
    entries.extend((key, count + index) for index, (key, _) in enumerate(additions))
    entries.sort()
    packed_entries = b"".join(struct.pack("<II", *row) for row in entries)
    old_offsets = struct.unpack_from("<" + "I" * count, chunk, 16)
    shift = 4 * len(additions)
    new_offsets = []
    string = bytearray()
    for _, value in additions:
        new_offsets.append(len(chunk) + shift + len(string))
        string.extend((value + "\0").encode("utf-16le"))
        string.extend(b"\0" * (-len(string) % 4))
    chunk = (chunk[:16] +
             struct.pack("<" + "I" * (count + len(additions)),
                         *(offset + shift for offset in old_offsets), *new_offsets) +
             chunk[16 + 4 * count:] + string)
    struct.pack_into("<I", chunk, 4, len(chunk))
    struct.pack_into("<I", chunk, 12, count + len(additions))
    header = bytearray(data[:28])
    struct.pack_into("<I", header, 16, table_end + 8 * len(additions))
    return bytes(header) + packed_entries + bytes(chunk)


def add_bonus_screen(data: bytes) -> bytes:
    if len(data) < 24 or data[:4] != b"IYF\0":
        raise FormatError("FE.LUI has an unsupported header")
    screen_table = struct.unpack_from("<I", data, 12)[0]
    object_table = struct.unpack_from("<I", data, 16)[0]
    font_table = struct.unpack_from("<I", data, 20)[0]
    count = struct.unpack_from("<I", data, screen_table)[0]
    entries = [struct.unpack_from("<II", data, screen_table + 4 + index * 8)
               for index in range(count)]
    index = next((i for i, (name, _) in enumerate(entries)
                  if name == EVENT_SELECT_SCREEN), None)
    if index is None or index + 1 >= count:
        raise FormatError("Event Select screen is absent from FE.LUI")
    begin = screen_table + entries[index][1]
    end = screen_table + entries[index + 1][1]
    original = decode_refpack(data[begin:end])
    replacement = encode_refpack_literals(add_peak_to_screen(original))
    delta = len(replacement) - (end - begin)
    output = bytearray(data[:begin] + replacement + data[end:])
    struct.pack_into("<I", output, 16, object_table + delta)
    struct.pack_into("<I", output, 20, font_table + delta)
    for later in range(index + 1, count):
        offset_at = screen_table + 4 + later * 8 + 4
        old = struct.unpack_from("<I", output, offset_at)[0]
        struct.pack_into("<I", output, offset_at, old + delta)
    return bytes(output)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--iso", type=Path, required=True)
    parser.add_argument("--overlay", type=Path, default=Path(".cache/overlay"))
    args = parser.parse_args()
    fe = add_bonus_screen(read_iso_file(args.iso, "DATA/UI/FE.LUI"))
    locale = add_bonus_locale(read_iso_file(args.iso, "DATA/LOCALE/CMNAMER.LOC"))
    for path, payload in (("DATA/UI/FE.LUI", fe),
                          ("DATA/LOCALE/CMNAMER.LOC", locale)):
        target = args.overlay / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(payload)
        print(f"{target}: {len(payload)} bytes")


if __name__ == "__main__":
    main()
