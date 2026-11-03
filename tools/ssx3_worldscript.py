"""Build native world properties and Luno bindings for imported Tricky objects."""

from __future__ import annotations

import struct

from ssx3_surfaces import surface
from tricky_assets import FormatError


def pack_world_script(pbd: dict, models: list[dict], source: dict,
                       instances: list[int], section_id: int, version: bytes,
                       mesh_counts: dict[int, int], interactives=None) -> tuple[bytes, dict]:
    properties = bytearray()
    offsets = []
    instance_properties = []
    unique = {}
    physics_base = len(source["collisions"])
    for instance_id in instances:
        if interactives and instance_id in interactives.properties:
            native = interactives.properties[instance_id]
            key = ("native", native)
            if key not in unique:
                unique[key] = len(offsets)
                offsets.append(len(properties))
                properties.extend(native)
            instance_properties.append(unique[key])
            continue
        instance = pbd["instances"][instance_id]
        source_index = source["instance_properties"][instance_id]
        prop = source["properties"][source_index]
        mode = prop["collision_mode"]
        collider = 0xffffffff
        parts = max(1, len(models[instance["model_id"]]["objects"]))
        if mode == 1 and prop["collision_index"] >= 0:
            index = prop["collision_index"]
            collider = (index << 8) | section_id
            parts = max(parts, mesh_counts[index])
        elif mode == 3 and prop["physics_index"] >= 0:
            index = prop["physics_index"]
            collider = ((physics_base + index) << 8) | section_id
            parts = max(parts, len(source["physics"][index]["bodies"]))
        binding = (interactives.object_bindings.get(instance_id, 0xffffffff)
                   if interactives else 0xffffffff)
        contact_only = bool(interactives and instance_id in interactives.contact_only_instances)
        key = (source_index, parts, binding, contact_only)
        if key not in unique:
            unique[key] = len(offsets)
            offsets.append(len(properties))
            # Map the two established static-instance flags. Tricky UV/event
            # flags do not become unrelated SSX 3 instance flags.
            flags = prop["flags"] & 0x21
            if mode in (1, 3) and collider == 0xffffffff:
                flags &= ~0x20
            properties.extend(struct.pack("<4I", mode, flags << 16, binding, collider))
            # Native per-part data: mass, restitution, contact flags and
            # signed surface. Bit 0 bounces; bit 1 records wall contacts.
            contact_flags = 2 | (1 if prop["flags"] & 0x80 else 0)
            if contact_only:
                # Use the same contact contract as the working breakable
                # triggers: retain notifications, suppress the bounce bit.
                contact_flags = 2
            native_surface = surface(prop["surface"]).native_id
            part_data = struct.pack("<2fHh", prop["mass"], prop["bounce"], contact_flags, native_surface)
            properties.extend(part_data * parts)
        instance_properties.append(unique[key])
    if interactives:
        for _ in interactives.posts:
            key = ("native", interactives.post_properties)
            if key not in unique:
                unique[key] = len(offsets)
                offsets.append(len(properties))
                properties.extend(interactives.post_properties)
            instance_properties.append(unique[key])
        anchor_count = len(interactives.emitter_anchors) + len(interactives.collision_emitter_anchors)
        if anchor_count:
            # Invisible, collision-free native hosts keep detached pop
            # emitters alive after their animated source receives DeadNode.
            key = ("emitter-anchor",)
            unique[key] = len(offsets)
            offsets.append(len(properties))
            properties.extend(struct.pack("<4I2fHh", 0, 0, 0xffffffff, 0xffffffff, 0., 0., 0, -1))
            instance_properties.extend([unique[key]] * anchor_count)
    if len(offsets) > 65535:
        raise FormatError("custom world has too many native object properties")
    out = bytearray(92)
    struct.pack_into("<3I", out, 0, 0x1000, 0x3800, 0)
    out[12:16] = version
    # Source object effects are compiled to native Luno callbacks. Raw Tricky
    # scripts and unrelated native career/event missions are not copied.
    for count, pointer in ((0x10, 0x14), (0x18, 0x1c), (0x20, 0x24),
                            (0x28, 0x2c), (0x30, 0x34), (0x38, 0x3c)):
        struct.pack_into("<II", out, count, 0, 92)
    if interactives:
        interactives.pack_script_tables(out)
    struct.pack_into("<I", out, 0x40, len(out))
    out.extend(properties)
    struct.pack_into("<2I", out, 0x44, len(instance_properties), len(out))
    out.extend(struct.pack("<" + "H" * len(instance_properties), *instance_properties))
    out.extend(b"\0" * (-len(out) % 4))
    struct.pack_into("<2I", out, 0x4c, len(offsets), len(out))
    out.extend(struct.pack("<" + "I" * len(offsets), *offsets))
    splines = source["splines"]
    if len(splines) != len(pbd["splines"]):
        raise FormatError("Tricky SSF and PBD spline counts differ")
    struct.pack_into("<2I", out, 0x54, len(splines), len(out))
    for spline in splines:
        # Garibaldi's rails use Tricky metal style 13. Native SSX 3 retail
        # race rails use style 10 and active flags 3.
        style = -1 if spline["style"] == 0xffffffff else spline["style"]
        native_surface = surface(style).native_id
        flags = 3 if spline["rail_flags"] & 1 and native_surface >= 0 else 0
        if interactives and spline["index"] in interactives.rail_initial:
            flags = 3 if interactives.rail_initial[spline["index"]] else 0
        out.extend(struct.pack("<I", ((native_surface & 0xffff) << 16) | flags))
    return bytes(out), {"native_object_properties": len(offsets),
                        "native_instance_assignments": len(instance_properties),
                        "native_rail_assignments": len(splines)}
