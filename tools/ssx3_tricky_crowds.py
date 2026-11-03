"""Source crowd images and instance-owned native material tables.

Tricky1458e0 loads crowd.ssh independently of each mountain's textures and
replaces the placeholder materials on model flag1. Each box has16 separately
animated materials. Native TexFlip reserves only8; never feed it these models.
"""

from functools import lru_cache
from pathlib import Path
import struct

from tricky_assets import FormatError, read_iso_file
from tricky_ssh import to_world_ssh
from ssx3_models import pack_instance, pack_model

MAGIC = 0x31445243  # CRD1
TABLE_OFFSET = 32
STORAGE_BYTES = TABLE_OFFSET + 4 + 16 * 4 + 16 * 20


@lru_cache(maxsize=2)
def images(iso: Path):
    data = read_iso_file(iso, "DATA/TEXTURES/CROWD.SSH")
    if (len(data) < 144 or data[:4] != b"SHPS"
            or struct.unpack_from("<2I", data, 4) != (len(data), 16)):
        raise FormatError("unexpected Tricky crowd image directory")
    entries = [struct.unpack_from("<4sI", data, 16 + 8 * i) for i in range(16)]
    if [name for name, _ in entries] != [f"cd{i:02d}".encode() for i in range(16)]:
        raise FormatError("unexpected Tricky crowd frame order")
    result = []
    for i, (_, start) in enumerate(entries):
        end = entries[i + 1][1] if i < 15 else len(data)
        if not 144 <= start < end <= len(data):
            raise FormatError("invalid Tricky crowd image extent")
        result.append(to_world_ssh(data[start:end], lightmap=False))
    return tuple(result)


class CrowdSprites:
    def __init__(self, iso, first_id, pbd, models, selected, model_ids,
                 material_ids, source_to_instance, section, leaf):
        self.first_id = first_id
        self.instances = {}
        self.offsets = {}
        self.materials = set()
        self.layouts = {}
        self.nodes = set()
        self.frames = ()
        for model in models:
            if model["index"] not in model_ids or not model["flags"] & 1:
                continue
            parts = model["objects"]
            ordered = [mesh["material"] for part in parts for mesh in part["meshes"]]
            if (len(parts) != 1 or parts[0]["matrix"] is not None
                    or parts[0]["animation"] is not None or len(ordered) != 16
                    or len(set(ordered)) != 16):
                raise FormatError("unsupported Tricky crowd mesh/material layout")
            self.materials.update(ordered)
            slots = [ordered.index(material) for material in sorted(ordered)]
            _, groups = pack_model(model, section, resource_id=model_ids[model["index"]],
                                   material_rids=material_ids)
            self.layouts[model["index"]] = slots, groups
        if self.layouts:
            if first_id + 15 > 32767:
                raise FormatError("Tricky crowd frames exceed native signed texture IDs")
            self.frames = images(iso)
        for owner in selected:
            instance = pbd["instances"][owner]
            if instance["model_id"] not in self.layouts:
                continue
            slots, groups = self.layouts[instance["model_id"]]
            payload = bytearray(pack_instance(instance, groups, section, leaf,
                resource_id=source_to_instance[owner],
                model_resource_id=model_ids[instance["model_id"]]))
            payload.extend(b"\0" * (-len(payload) % 16))
            offset = len(payload)
            payload.extend(struct.pack("<4I16B", MAGIC, 1, first_id, 16, *slots))
            payload.extend(b"\0" * (STORAGE_BYTES - TABLE_OFFSET))
            self.instances[owner] = bytes(payload)
            self.offsets[owner] = offset

    def register(self, owner, offset, words, rid):
        if len(words) != 4 or words[:2] != (17, 0) or words[2] * words[3] != 16:
            raise FormatError("unsupported Tricky crowd box parameters")
        if owner not in self.offsets:
            raise FormatError("Tricky crowd property requires its source crowd model")
        self.nodes.add((owner, offset))
        return [(0, rid, 1), (1, self.offsets[owner], 1),
                (2, words[2], 1), (3, words[3], 1)]

    def records(self):
        return enumerate(self.frames, self.first_id)

    def material(self):
        # Source Init forces flags0x20001: textured, alpha-tested crowd image.
        # This shared frame0 is also valid before native focus creates a node.
        return struct.pack("<8hi", self.first_id, -1, -1, 0, 0, 0, 1, 3, -1)

    def summary(self):
        return {"source_crowd_nodes": sorted(self.nodes),
                "source_crowd_instances": sorted(self.instances),
                "native_crowd_textures": len(self.frames),
                "native_crowd_texture_base": self.first_id if self.frames else None,
                "source_crowd_materials": sorted(self.materials),
                "native_crowd_storage": [[owner, offset, STORAGE_BYTES]
                                         for owner, offset in sorted(self.offsets.items())]}
