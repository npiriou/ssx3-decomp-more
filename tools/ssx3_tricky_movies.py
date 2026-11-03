"""Tricky Movie23 screens: source SSSF pictures in native PSMCT16.

Source1ff928 ->2c2318 ->2c2bf8 ->2c27c8, not a general BC1 decoder:
four-colour interpolation uses5/8 and3/8, zero endpoints become1, then RGB565
is converted to PS2 RGB5551. Frames are prepared once; one native texture is
updated during play. Course movies are shared by every live screen.
"""

from functools import lru_cache
from pathlib import Path
import struct

from tricky_assets import FormatError, read_iso_file
from tricky_object_effects import read_logic
from ssx3_models import pack_instance, pack_model

SCREEN_MAGIC = 0x31535654  # TVS1
MOVIE_MAGIC = 0x314d5654  # TVM1
STORAGE_BYTES = 48
SOURCE_NAMES = {"GARI": "jgari", "SNOW": "jsnow", "ELYSIUM": "jelysium",
                "MESA": "jmesa", "MERQUER": "jmerquer", "MEGAPLE": "jmegaple",
                "ALOHA": "jaloha", "ALASKA": "jalaska", "PIPE": "jpipe"}


def decode_picture(blocks, width, height):
    if width % 4 or height % 4 or len(blocks) != width * height // 2:
        raise FormatError("invalid Tricky SSSF colour blocks")
    pixels = bytearray(width * height * 2)
    at = 0
    for y in range(0, height, 4):
        for x in range(0, width, 4):
            first, second, indices = struct.unpack_from("<HHI", blocks, at)
            at += 8
            palette = [first, second]
            if first > second:
                for a, b in ((5, 3), (3, 5)):
                    palette.append(sum(((a * (first & mask) + b * (second & mask)) >> 3) & mask
                                       for mask in (0xf800, 0x7e0, 0x1f)))
            else:
                palette += [sum((((first & mask) + (second & mask)) >> 1) & mask
                                for mask in (0xf800, 0x7e0, 0x1f)), 0]
            palette[:2] = [value or 1 for value in palette[:2]]
            palette = [(((value & 31) << 10) | ((value >> 1) & 0x3e0)
                        | (value >> 11) | 0x8000) if value else 0 for value in palette]
            for dy in range(4):
                for dx in range(4):
                    struct.pack_into("<H", pixels, ((y + dy) * width + x + dx) * 2,
                                     palette[indices & 3])
                    indices >>= 2
    return bytes(pixels)


@lru_cache(maxsize=9)
def movie(iso: Path, code: str):
    name = SOURCE_NAMES.get(code)
    if name is None:
        raise FormatError("no recovered Tricky movie name for this course")
    source = read_iso_file(iso, f"DATA/VIDEO/{name.upper()}.SSS")
    at = 0
    frames = []
    while at < len(source):
        if at + 24 > len(source) or source[at:at + 4] != b"SSSF":
            raise FormatError("invalid Tricky SSSF frame header")
        size, packed, width, height = struct.unpack_from("<IIHH", source, at + 4)
        shape_size = packed >> 8
        pixels = width * height // 2
        if (packed & 255 != 0x60 or (width, height) != (128, 64)
                or size < 24 + pixels or at + size > len(source)
                or not 16 + pixels <= shape_size <= size - 8):
            raise FormatError("unsupported Tricky SSSF image layout")
        frames.append(decode_picture(source[at + 24:at + 24 + pixels], width, height))
        at += size
    if not frames or len(frames) > 3600:
        raise FormatError("invalid Tricky movie frame count")
    # Native source requests loop1/rate15. Store only native pixels, without
    # SSSF padding/name records. None of this derived media enters Git.
    return struct.pack("<8I", MOVIE_MAGIC, 1, 128, 64, len(frames), 15, 16384, 0) + b"".join(frames)


def source_screens(ssf, collision, selected):
    slots, chains, functions = read_logic(ssf)
    found = set()

    def walk(nodes, owner, seen):
        for node in nodes:
            main, words = node["main"], node["words"]
            if main == 0 and words[0] == 23:
                if words != (23,):
                    raise FormatError("unsupported Tricky Movie23 parameters")
                found.add(owner)
            elif main == 7:
                target, header = words[:2]
                key = ("chain", target, header)
                if target in selected and key not in seen and header < len(chains):
                    walk(chains[header], target, seen | {key})
            elif main in (21, 26):
                index = words[0]
                key = ("function", owner, index)
                if index < len(functions) and key not in seen:
                    walk(functions[index]["nodes"], owner, seen | {key})

    selected = set(selected)
    for owner in selected:
        prop = collision["properties"][collision["instance_properties"][owner]]
        if prop["effect_slot"] < 0:
            continue
        for channel in (0, 1, 3, 4):
            header = slots[prop["effect_slot"]][channel]
            if header >= 0:
                walk(chains[header], owner, {("chain", owner, header)})
    return found


class MovieScreens:
    def __init__(self, iso, code, first_id, ssf, pbd, models, collision, selected,
                 model_ids, material_ids, source_to_instance, section, leaf, output):
        self.texture_id = first_id
        self.instances = {}
        self.offsets = {}
        self.nodes = set()
        self.data = b""
        owners = source_screens(ssf, collision, selected)
        if not owners:
            return
        if first_id > 32767:
            raise FormatError("Tricky movie texture exceeds native signed IDs")
        self.data = movie(iso, code)
        target = output.with_name(f"{code}.TVM")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(self.data)
        for owner in sorted(owners):
            instance = pbd["instances"][owner]
            model = models[instance["model_id"]]
            parts = model["objects"]
            if (len(parts) != 1 or parts[0]["matrix"] is not None
                    or parts[0]["animation"] is not None or len(parts[0]["meshes"]) != 1):
                raise FormatError("unsupported Tricky movie screen geometry")
            _, groups = pack_model(model, section, resource_id=model_ids[model["index"]],
                                   material_rids=material_ids)
            payload = bytearray(pack_instance(instance, groups, section, leaf,
                resource_id=source_to_instance[owner],
                model_resource_id=model_ids[instance["model_id"]]))
            payload.extend(b"\0" * (-len(payload) % 16))
            self.offsets[owner] = len(payload)
            payload.extend(struct.pack("<4I", SCREEN_MAGIC, 1, first_id, 1))
            payload.extend(b"\0" * (STORAGE_BYTES - 16))
            self.instances[owner] = bytes(payload)

    def register(self, owner, offset, rid):
        if owner not in self.offsets:
            raise FormatError("Tricky movie owner has no reserved private material")
        self.nodes.add((owner, offset))
        return [(0, rid, 1), (1, self.offsets[owner], 1)]

    def records(self):
        if not self.data:
            return
        # Source1ff890 creates a black128x64 native sixteen-bit texture.
        # The first decoded picture appears after the first four60Hz ticks.
        header = bytearray(128)
        header[0] = 3
        header[1:4] = (128 + 16384).to_bytes(3, "little")
        struct.pack_into("<2H", header, 4, 128, 64)
        struct.pack_into("<I", header, 12, 0x1000)
        struct.pack_into("<I", header, 16, 128)
        struct.pack_into("<4I", header, 32, MOVIE_MAGIC, 1, self.texture_id,
                         struct.unpack_from("<I", self.data, 16)[0])
        yield self.texture_id, bytes(header) + bytes(16384)

    def summary(self):
        return {"source_movie_nodes": sorted(self.nodes),
                "source_movie_instances": sorted(self.instances),
                "native_movie_texture": self.texture_id if self.data else None,
                "native_movie_frames": struct.unpack_from("<I", self.data, 16)[0] if self.data else 0,
                "native_movie_storage": [[owner, offset, STORAGE_BYTES]
                                         for owner, offset in sorted(self.offsets.items())]}
