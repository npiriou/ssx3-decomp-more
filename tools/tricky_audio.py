"""Append disc-authored Tricky sounds to native SSX 3 mountain banks.

Retail patches/samples stay available. Native object-sound builtin30 plays
the added indices below100. All courses share one fixed archive extent.
"""

from functools import lru_cache
import hashlib
from pathlib import Path
import struct

from ssx3_world_archive import pack_bigf
from ssx3_world_probe import bigf_members
from tricky_assets import FormatError, read_cofb_member, read_iso_file
from tricky_courses import COURSES

SOURCE_BANKS = {
    "GARI": "garibaldi1", "SNOW": "snowdream1", "ELYSIUM": "elysium1",
    "MESA": "mesabanca1", "MERQUER": "merqurycity1", "MEGAPLE": "megaplex1",
    "ALOHA": "iceberg", "ALASKA": "alaska1", "UNTRACK": "untracked1",
    "PIPE": "pipedream1", "TRICK": "tricktutorial",
}


def align(value, boundary=16):
    return (value + boundary - 1) & -boundary


class Bank:
    def __init__(self, data):
        if len(data) < 20 or data[:6] != b"BNKl\x05\0":
            raise FormatError("object audio requires a version5 little-endian BNK")
        self.data = data
        self.count = struct.unpack_from("<H", data, 6)[0]
        self.header, self.spu_size, iop_size = struct.unpack_from("<3I", data, 8)
        if (iop_size or 20 + self.count * 4 > self.header
                or self.header + self.spu_size != len(data)):
            raise FormatError("unsupported object bank memory regions")

    def patch(self, index):
        if not 0 <= index < self.count:
            raise FormatError("object sound index exceeds its source bank")
        entry = 20 + index * 4
        rel = struct.unpack_from("<I", self.data, entry)[0]
        if not rel:
            return None
        start = entry + rel
        if not 20 + self.count * 4 <= start < self.header - 4:
            raise FormatError("object patch overlaps its offset table")
        if self.data[start:start + 4] != b"PT\x05\0":
            raise FormatError("object patch is not a native PS2 patch")
        at, fields, segments, offsets = start + 4, {}, [], []
        while at < self.header:
            tag = self.data[at]
            at += 1
            if tag in (0xfe, 0xff):
                segments.append(fields)
                if tag == 0xff:
                    return {"start": start, "raw": self.data[start:at],
                            "segments": segments, "offsets": offsets}
                # Native SND_ParsePatch returns after FE, then its caller
                # parses the next variant with fresh defaults. FF ends the
                # whole entry. Preserve every variant and marker verbatim.
                fields = {}
                continue
            if tag in (0xfc, 0xfd):
                continue
            if at >= self.header:
                break
            size = self.data[at]
            at += 1
            if at + size > self.header or tag in fields:
                raise FormatError("invalid or repeated object patch field")
            value = int.from_bytes(self.data[at:at + size], "big")
            fields[tag] = (at - start, size, value)
            if tag in (0x88, 0x89):
                offsets.append((at - start, size, value))
            at += size
        raise FormatError("unterminated object patch")


@lru_cache(maxsize=4)
def audio_members(iso):
    return {name.replace("\\", "/").lower(): data for name, data in
            bigf_members(read_iso_file(Path(iso), "DATA/AUDIO/AUDIO.BIG")).items()}


def requested_sounds(ssf):
    from tricky_object_effects import read_logic
    _, chains, functions = read_logic(ssf)
    nodes = [node for chain in chains for node in chain]
    nodes += [node for function in functions for node in function["nodes"]]
    sounds = set()
    for node in nodes:
        if node["main"] == 8:
            if len(node["words"]) != 1:
                raise FormatError("invalid Tricky object sound command")
            sounds.add(node["words"][0])
    return tuple(sorted(sounds))


def relocate_samples(patch, destinations):
    raw = bytearray(patch["raw"])
    for at, size, value in destinations:
        if size != 4 or not 0 <= value <= 0xffffffff:
            raise FormatError("unsupported object sample offset encoding")
        raw[at:at + size] = value.to_bytes(size, "big")
    return raw


def append_sounds(retail, source, identifiers):
    native, original = Bank(retail), Bank(source)
    payload = bytearray(retail[native.header:])
    mapping, appended, samples_seen = {}, [], {}
    entries, records, seen = [], [], {}
    for index in range(native.count):
        patch = native.patch(index)
        if patch is None:
            entries.append(None)
            continue
        key = ("native", patch["start"])
        if key not in seen:
            offsets = [(at, size, value - native.header) for at, size, value in patch["offsets"]]
            if any(not 0 <= value < native.spu_size for _, _, value in offsets):
                raise FormatError("native object sample leaves its SPU region")
            seen[key] = len(records)
            records.append((patch, offsets))
        entries.append(seen[key])
    for sound in identifiers:
        patch = original.patch(sound)
        if patch is None:
            mapping[sound] = None
            continue
        offsets, parts = [], []
        for fields in patch["segments"]:
            if 0x88 not in fields:
                if 0x89 in fields:
                    raise FormatError("source sound has no first channel")
                continue
            channels = fields.get(0x82, (0, 0, 1))[2]
            codec = fields.get(0xa0, (0, 0, 5))[2]
            samples = fields.get(0x85, (0, 0, 0))[2]
            if (channels not in (1, 2) or codec != 5 or samples <= 0
                    or fields.get(0x8a, (0, 0, 0))[2] != 0):
                raise FormatError("unsupported source object sound sample layout")
            length, digests = (samples + 27) // 28 * 16, []
            for channel in range(channels):
                tag = 0x88 + channel
                if tag not in fields:
                    raise FormatError("missing source object sound channel")
                field, size, at = fields[tag]
                if not original.header <= at < at + length <= len(source):
                    raise FormatError("source object sound leaves its SPU region")
                key = at, length
                if key not in samples_seen:
                    payload.extend(b"\0" * (align(len(payload)) - len(payload)))
                    samples_seen[key] = len(payload)
                    payload.extend(source[at:at + length])
                offsets.append((field, size, samples_seen[key]))
                digests.append(hashlib.sha256(source[at:at + length]).hexdigest())
            parts.append({"channels": channels, "samples": samples,
                          "sample_bytes": length * channels, "sha256": digests})
        mapping[sound] = len(entries)
        entries.append(len(records))
        records.append((patch, offsets))
        appended.append({"source": sound, "native": mapping[sound],
                         "parts": parts, "segments": len(patch["segments"]),
                         "sample_bytes": sum(part["sample_bytes"] for part in parts)})
    if len(entries) > 100:
        raise FormatError("object sounds exceed native bank2 ID range")
    report = {"native_patch_count": native.count, "patch_count": len(entries),
        "source_bank": None, "sounds": appended,
        "empty_source_sounds": [i for i, alias in mapping.items() if alias is None],
        "added_spu_bytes": len(payload) - native.spu_size}
    if not appended:
        return retail, mapping, report
    out = bytearray(20 + len(entries) * 4)
    out[:20] = retail[:20]
    positions = []
    for patch, _ in records:
        out.extend(b"\0" * (align(len(out), 4) - len(out)))
        positions.append(len(out))
        out.extend(patch["raw"])
    out.extend(b"\0" * (align(len(out), 64) - len(out)))
    header = len(out)
    for (patch, offsets), at in zip(records, positions):
        raw = relocate_samples(patch, [(field, size, header + value) for field, size, value in offsets])
        out[at:at + len(raw)] = raw
    for index, record in enumerate(entries):
        entry = 20 + index * 4
        struct.pack_into("<I", out, entry, 0 if record is None else positions[record] - entry)
    struct.pack_into("<H3I", out, 6, len(entries), header, len(payload), 0)
    out.extend(payload)
    return bytes(out), mapping, report


@lru_cache(maxsize=16)
def course_bank(ssx3_iso, tricky_iso, code, identifiers):
    native = audio_members(ssx3_iso)["data/audio/mtn.bnk"]
    name = SOURCE_BANKS[code] + ".bnk"
    source = audio_members(tricky_iso)["data/audio/" + name]
    data, mapping, report = append_sounds(native, source, identifiers)
    report["source_bank"] = name
    return data, mapping, report


def object_sounds(ssx3_iso, tricky_iso, code, ssf):
    return course_bank(str(ssx3_iso), str(tricky_iso), code, requested_sounds(ssf))


def prepare(ssx3_iso, tricky_iso, overlay):
    banks, reports = {}, {}
    for course in COURSES:
        archive = read_iso_file(tricky_iso, course.archive)
        ssf = read_cofb_member(archive, f"data/models/{course.code.lower()}.ssf")
        data, _, report = object_sounds(ssx3_iso, tricky_iso, course.code, ssf)
        banks[course.code], reports[course.code] = data, report
    # A mounted native BIG directory survives event selection. Its Mtn member
    # needs a fixed extent; the host reader substitutes just that extent.
    members = bigf_members(read_iso_file(ssx3_iso, "DATA/AUDIO/AUDIO.BIG"))
    mountain = next(name for name in members if name.replace("\\", "/") == "data/audio/mtn.bnk")
    retail = members[mountain]
    capacity = align(max(len(retail), *(len(bank) for bank in banks.values())), 2048)
    members[mountain] = retail.ljust(capacity, b"\0")
    packed = pack_bigf(list(members.items()), header_limit=1024 * 1024)
    pos, extent = 16, None
    for _ in members:
        at, size = struct.unpack_from(">II", packed, pos)
        end = packed.index(0, pos + 8)
        if packed[pos + 8:end].replace(b"\\", b"/") == b"data/audio/mtn.bnk":
            extent = at, size
        pos = end + 1
    if extent is None:
        raise FormatError("prepared audio has no mountain member")
    root = Path(overlay) / "DATA/AUDIO/TRICKY"
    root.mkdir(parents=True, exist_ok=True)
    for code, bank in banks.items():
        (root / f"{code}.BNK").write_bytes(bank.ljust(capacity, b"\0"))
    (root.parent / "AUDIO.BIG").write_bytes(packed)
    (root / "MOUNTAIN.BIN").write_bytes(struct.pack("<4sIII", b"TAU1", 1, *extent))
    return reports
