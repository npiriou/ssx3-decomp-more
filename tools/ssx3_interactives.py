"""Place complete native SSX 3 pickups and breakable shortcut signs in Tricky worlds.

The donor IDs below are the USA BAM.PHM/BAM.PSM named instances. Keep their
MDR/DMA data, object properties and Luno functions together: drawing a model
alone does not create a collectible or a breakable object.
"""

from __future__ import annotations

import itertools
import math
import re
import struct

from ssx3_world_archive import _records
from ssx3_world_probe import decode_stream
from tricky_assets import FormatError


def u32(data, offset):
    return struct.unpack_from("<I", data, offset)[0]


def map_names(data: bytes) -> dict[int, str]:
    """Read internal instance UIDs, rather than matching prefab hash values."""
    section = ""
    result = {}
    for line in data.decode("ascii").splitlines():
        if line.startswith("### ") and ("BEGIN" in line or "END" in line):
            section = line
        match = re.match(r"(\S+)\s+(\d+)\s+\d+\s+[a-fA-F0-9]+", line)
        if section == "### INTERNAL INSTANCES BEGIN" and match:
            result[int(match[2])] = match[1]
    return result


def transform(matrix, point):
    return [matrix[3][i] + sum(point[j] * matrix[j][i] for j in range(3))
            for i in range(3)]


def donor_matrix(payload):
    values = struct.unpack_from("<16f", payload, 16)
    return [list(values[i:i + 4]) for i in range(0, 16, 4)]


def local_point(matrix, point):
    # Retail donor placements are orthonormal (small exporter roundoff).
    delta = [point[i] - matrix[3][i] for i in range(3)]
    return [sum(delta[i] * matrix[j][i] for i in range(3)) /
            sum(matrix[j][i] ** 2 for i in range(3)) for j in range(3)]


def model_bounds(payload):
    node = u32(payload, 8)
    geometry = u32(payload, node + 4)
    return struct.unpack_from("<6f", payload, geometry)


def prefab_bounds(model):
    points = []
    for part in model["objects"]:
        if part["bounds"] is None:
            continue
        bounds = part["bounds"]
        for point in itertools.product(*[(bounds[i], bounds[i + 3]) for i in range(3)]):
            node = part
            while True:
                if node["matrix"] is not None:
                    values = node["matrix"]
                    point = transform([values[i:i + 4] for i in range(0, 16, 4)], point)
                if node["parent"] == 0xffffffff:
                    break
                node = model["objects"][node["parent"]]
            points.append(point)
    return [min(p[i] for p in points) for i in range(3)] + [
        max(p[i] for p in points) for i in range(3)]


class NativeInteractives:
    # Keep each RID with its source bank: ARA1 and ASS1 reuse local IDs.
    # ASS1 multia/b/c touch scripts award the native x2/x3/x5 multipliers.
    DONORS = {"speed": ("ARA1", 1383), "trick": ("ARA1", 847),
              "glass": ("ARA1", 900), "shards": ("ARA1", 242),
              "post": ("ARA1", 1415), "score2": ("ASS1", 2023),
              "score3": ("ASS1", 976), "score5": ("ASS1", 2249)}

    def __init__(self, ssb, streams, locations, source_map, pbd, models, instances):
        self.resources = {}
        for bank in sorted({bank for bank, _ in self.DONORS.values()}):
            location = next(item for item in locations if item["name"] == bank)
            for index in range(location["first_stream"], location["last_stream"] + 1):
                for kind, section, rid, payload in _records(decode_stream(ssb, streams[index])):
                    self.resources[bank, kind, rid] = payload
        self.names = map_names(source_map)
        self.replacements = {}
        self.posts = []
        self.bindings = []
        self.functions = []
        self.function_ids = {}
        self.properties = {}
        self.instance_payloads = {}
        self.model_ids = {}
        self.material_ids = {}
        source_ids = set(instances)
        for index in instances:
            name = self.names.get(index, "")
            if name.startswith("Mdl_SpeedBoost_"):
                self.replacements[index] = "speed"
            elif name.startswith("Mdl_TrickBoost_"):
                self.replacements[index] = "trick"
            elif match := re.fullmatch(r"Gem_TrickMultiplier_(?:YellowX(2)|OrangeX(3)|RedX(5))_.*", name):
                self.replacements[index] = "score" + next(value for value in match.groups() if value)
            elif re.match(r"Mdl_Lcd_ScreenLogo(?:Red)?_", name):
                self.replacements[index] = "glass"
        for index, kind in list(self.replacements.items()):
            if kind != "glass":
                continue
            name = self.names[index]
            broken = name.replace("ScreenLogoRed_", "ScreenLogoBrokenRed_").replace(
                "ScreenLogo_", "ScreenLogoBroken_")
            matches = [i for i, n in self.names.items() if n == broken and i in source_ids]
            if len(matches) != 1:
                raise FormatError(f"shortcut sign {name} has no unique Race fragments")
            self.replacements[matches[0]] = "shards"
            self.posts.append((index, matches[0]))
        self.source = pbd
        self.source_models = models

    def prepare(self, section, leaf, model_start, material_start, source_to_instance):
        self.section = section
        self.leaf = leaf
        kinds = set(self.replacements.values())
        if self.posts:
            kinds.add("post")
        model_sources = sorted({(bank, u32(self.resources[bank, 3, donor], 0x80) >> 8)
                                for bank, donor in (self.DONORS[kind] for kind in kinds)})
        self.model_ids = {source: model_start + i for i, source in enumerate(model_sources)}
        material_sources = set()
        for bank, rid in model_sources:
            model = self.resources[bank, 2, rid]
            material_sources.update((bank, u32(model, 44 + i * 4) >> 8)
                                    for i in range(u32(model, 40)))
        self.material_ids = {source: material_start + i
                             for i, source in enumerate(sorted(material_sources))}
        self.post_ids = {source: len(source_to_instance) + i
                         for i, (source, _) in enumerate(self.posts)}
        self.placement = {}
        for source, kind in self.replacements.items():
            if kind == "shards":
                continue
            self.placement[source] = self._placement(source, kind)
        for source, broken in self.posts:
            self.placement[broken] = self.placement[source]
        for source, kind in self.replacements.items():
            donor = self.DONORS[kind]
            remap = {}
            if kind == "glass":
                broken = next(b for a, b in self.posts if a == source)
                remap[(242 << 8) | 8] = (source_to_instance[broken] << 8) | section
            self.properties[source] = self._property(donor, remap)
            self.instance_payloads[source] = self._instance(
                donor, source_to_instance[source], self.placement[source])
        self.post_properties = self._property(self.DONORS["post"], {}) if self.posts else None

    def _placement(self, source, kind):
        instance = self.source["instances"][source]
        center = [(a + b) / 2 for a, b in zip(instance["bounds_min"], instance["bounds_max"])]
        bank, donor_id = self.DONORS[kind]
        donor = self.resources[bank, 3, donor_id]
        original = donor_matrix(donor)
        native_center = local_point(original, struct.unpack_from("<3f", donor, 80))
        if kind == "glass":
            source_model = self.source_models[instance["model_id"]]
            bounds = prefab_bounds(source_model)
            native_bounds = model_bounds(self.resources[bank, 2, u32(donor, 128) >> 8])
            width = (bounds[3] - bounds[0]) / (native_bounds[4] - native_bounds[1])
            height = (bounds[5] - bounds[2]) / (native_bounds[5] - native_bounds[2])
            source_matrix = instance["matrix"]
            # Tricky sign width is local X; the retail SSX 3 sign uses Y.
            axes = [[-v for v in source_matrix[1][:3]],
                    [v * width for v in source_matrix[0][:3]],
                    [v * height for v in source_matrix[2][:3]]]
        else:
            # Native pickups stand upright and animate themselves. Preserve
            # the source trigger's center, not the small Tricky icon's tilt.
            axes = [[1., 0., 0.], [0., 1., 0.], [0., 0., 1.]]
        translation = [center[i] - sum(native_center[j] * axes[j][i] for j in range(3))
                       for i in range(3)]
        return [a + [0.] for a in axes] + [translation + [1.]]

    def _instance(self, donor_ref, rid, matrix):
        bank, donor_id = donor_ref
        donor = self.resources[bank, 3, donor_id]
        out = bytearray(donor)
        bounds_bank, bounds_id = self.DONORS["glass"] if donor_ref == self.DONORS["shards"] else donor_ref
        model_id = u32(self.resources[bounds_bank, 3, bounds_id], 128) >> 8
        bounds = model_bounds(self.resources[bounds_bank, 2, model_id])
        corners = [transform(matrix, point)
                   for point in itertools.product(*[(bounds[i], bounds[i + 3]) for i in range(3)])]
        low = [min(p[i] for p in corners) for i in range(3)]
        high = [max(p[i] for p in corners) for i in range(3)]
        center = [(a + b) / 2 for a, b in zip(low, high)]
        radius = struct.unpack_from("<f", donor, 92)[0] * max(
            math.sqrt(sum(v * v for v in row[:3])) for row in matrix[:3])
        struct.pack_into("<16f4f6f", out, 16, *(v for row in matrix for v in row),
                         *center, radius, *low, *high)
        struct.pack_into("<I", out, 120, (rid << 8) | self.section)
        struct.pack_into("<BhI", out, 125, self.section, self.leaf,
                         (self.model_ids[bank, u32(donor, 128) >> 8] << 8) | self.section)
        # These are runtime pointers, resolved from the copied MDR/script.
        struct.pack_into("<2I", out, 136, 0, 0)
        return bytes(out)

    def _function(self, bank, handle, remap):
        if handle == 0xffffffff:
            return handle
        key = (bank, handle, tuple(sorted(remap.items())))
        if key not in self.function_ids:
            index = handle >> 8
            script = self.resources[bank, 16, 0]
            pointers = u32(script, 0x3c)
            start = u32(script, pointers + index * 4)
            end = u32(script, pointers + (index + 1) * 4)
            code = script[start:end]
            if code[:4] != b"LUN\0":
                raise FormatError("retail interactive function is not Luno bytecode")
            for old, new in remap.items():
                # Luno opcode 0x27 is a typed resource-handle literal.
                needle = b"\x27\0\0\0" + struct.pack("<I", old)
                if code.count(needle) != 1:
                    raise FormatError("retail shortcut function lost its fragment handle")
                code = code.replace(needle, b"\x27\0\0\0" + struct.pack("<I", new))
            self.function_ids[key] = len(self.functions)
            self.functions.append(code)
        return (self.function_ids[key] << 8) | self.section

    def _property(self, donor_ref, remap):
        bank, donor_id = donor_ref
        script = self.resources[bank, 16, 0]
        index = struct.unpack_from("<H", script, u32(script, 0x48) + donor_id * 2)[0]
        table = u32(script, 0x50)
        start = u32(script, 0x40) + u32(script, table + index * 4)
        end = u32(script, 0x40) + u32(script, table + (index + 1) * 4)
        out = bytearray(script[start:end])
        binding = u32(out, 8)
        if binding != 0xffffffff:
            original = struct.unpack_from("<6I", script, u32(script, 0x1c) + (binding >> 8) * 24)
            mapped = tuple(self._function(bank, h, remap if h != 0xffffffff else {}) for h in original)
            if mapped not in self.bindings:
                self.bindings.append(mapped)
            struct.pack_into("<I", out, 8, (self.bindings.index(mapped) << 8) | self.section)
        return bytes(out)

    def records(self):
        """Native model/material payloads; texture IDs remain global retail IDs."""
        for (bank, source), rid in self.material_ids.items():
            yield 0, rid, self.resources[bank, 0, source]
        for (bank, source), rid in self.model_ids.items():
            out = bytearray(self.resources[bank, 2, source])
            struct.pack_into("<I", out, 0, (rid << 8) | self.section)
            for i in range(u32(out, 40)):
                material = u32(out, 44 + i * 4) >> 8
                struct.pack_into("<I", out, 44 + i * 4,
                                 (self.material_ids[bank, material] << 8) | self.section)
            yield 2, rid, bytes(out)
        for source, _ in self.posts:
            rid = self.post_ids[source]
            yield 3, rid, self._instance(self.DONORS["post"], rid, self.placement[source])

    def textures(self):
        images = {}
        for bank, source in self.material_ids:
            for rid in struct.unpack_from("<3h", self.resources[bank, 0, source]):
                if rid < 0:
                    continue
                body = self.resources.get((bank, 9, rid))
                if body is None:
                    raise FormatError(f"native pickup texture {rid} missing from {bank}")
                if rid in images and images[rid] != body:
                    raise FormatError(f"conflicting native shared texture {rid}")
                images[rid] = body
        yield from sorted(images.items())

    def pack_script_tables(self, out):
        # Header+0x10 contains section-wide callback handles, not scalar
        # globals. ARA1's callbacks set up its scenery, emitters and collect
        # sets; none belongs to Garibaldi. Only copy per-object scripts.
        struct.pack_into("<2I", out, 0x18, len(self.bindings), len(out))
        for binding in self.bindings:
            out.extend(struct.pack("<6I", *binding))
        struct.pack_into("<2I", out, 0x38, len(self.functions), len(out))
        pointers = len(out)
        out.extend(b"\0" * (len(self.functions) * 4))
        for i, code in enumerate(self.functions):
            struct.pack_into("<I", out, pointers + i * 4, len(out))
            out.extend(code)

    def summary(self):
        return {"native_speed_pickups": sum(k == "speed" for k in self.replacements.values()),
                "native_trick_pickups": sum(k == "trick" for k in self.replacements.values()),
                "native_score_pickups": sum(k.startswith("score") for k in self.replacements.values()),
                "native_breakable_shortcuts": len(self.posts),
                "native_interactive_functions": len(self.functions),
                "native_replacements": [
                    {"source_instance": source, "source_name": self.names[source],
                     "kind": kind, "native_donor_location": self.DONORS[kind][0],
                     "native_donor_instance": self.DONORS[kind][1]}
                    for source, kind in sorted(self.replacements.items())]}
