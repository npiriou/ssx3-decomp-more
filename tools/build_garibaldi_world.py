"""Build a Garibaldi world section in an SSX 3 BAM archive.

The derived data includes terrain, static models, textures, splines and
native race paths and native object/rail property tables. Surface conversion
and the surrounding event flow remain in development. The generated BAM
belongs in .cache/.
"""

from __future__ import annotations

import argparse
import json
import math
import os
from pathlib import Path
import struct

from ssx3_aip import convert_tricky_aip, inspect_world_aip
from ssx3_collision import pack_collision, pack_sphere_tree
from ssx3_interactives import NativeInteractives
from ssx3_models import pack_instance, pack_model
from ssx3_splines import convert_splines, spline_template
from ssx3_surfaces import patch_surface
from ssx3_world_archive import append_location, pack_bigf, shared_next_id
from ssx3_worldscript import pack_world_script
from ssx3_world_build import (conservative_patch_bounds, pack_patch_geometry,
                              pack_resource)
from ssx3_world_probe import (bigf_members, decode_stream, read_sdb,
                              resource_summary)
from tricky_assets import (FormatError, parse_ltg, parse_pbd, read_cofb_member,
                           read_iso_file)
from tricky_models import parse_prefabs
from tricky_collision import parse_ssf
from tricky_ssh import inspect_world_ssh, parse_shps, to_world_ssh


def _verify_disc(iso: Path, serial: bytes, label: str) -> None:
    if serial not in read_iso_file(iso, "SYSTEM.CNF"):
        raise FormatError(f"{iso}: expected {label} ({serial.decode('ascii')})")


def _material_payload(source: dict, texture_rid: int) -> bytes:
    # The Tricky 0x20000 and 0x40000 appearance bits correspond to alpha
    # test and alpha blend. SSX 3 WorldMaterial uses bits 2 and 4 in its
    # render flags. This visual mapping still needs an in-game comparison.
    flags = source["appearance_flags"]
    if flags & ~0x75108:
        raise FormatError(f"unknown Tricky material appearance flags {flags:#x}")
    render_flags = 1 | (2 if flags & 0x20000 else 0) | (4 if flags & 0x40000 else 0)
    return struct.pack("<10h", texture_rid, -1, -1, 0, 0, 0, 1,
                       render_flags, -1, -1)


def build(SSX3_iso: Path, tricky_iso: Path, output: Path) -> dict:
    _verify_disc(SSX3_iso, b"SLUS_207.72", "SSX 3 USA")
    _verify_disc(tricky_iso, b"SLUS_203.26", "SSX Tricky USA")
    retail_archive = read_iso_file(SSX3_iso, "DATA/WORLDS/BAM.BIG")
    members = bigf_members(retail_archive)
    sdb = members["data/worlds/bam.sdb"]
    ssb = members["data/worlds/bam.ssb"]
    locations, _, streams = read_sdb(sdb)
    template_location = next(location for location in locations
                             if location["name"] == "ARA1")
    template_stream = decode_stream(ssb, streams[template_location["last_stream"]])
    world_splines = spline_template(template_stream)
    section_id = len(locations)
    leaf_id = len(streams)
    texture_base = shared_next_id(sdb, 9)
    lightmap_base = shared_next_id(sdb, 10)
    if section_id > 255 or leaf_id > 32767:
        raise FormatError("SSX 3 world has no custom section ID capacity")
    tricky_archive = read_iso_file(tricky_iso, "DATA/MODELS/GARI.BIG")
    pbd_data = read_cofb_member(tricky_archive, "data/models/gari.pbd")
    pbd = parse_pbd(pbd_data, True)
    models = parse_prefabs(pbd_data, pbd["counts"], pbd["offsets"])
    collision_data = parse_ssf(read_cofb_member(tricky_archive, "data/models/gari.ssf"))
    spatial = parse_ltg(read_cofb_member(tricky_archive, "data/models/gari.ltg"),
                        pbd["counts"], True)
    race_instances = sorted({index for node in spatial["nodes"]
                             for index in node["race_instances"]})
    interactives = NativeInteractives(
        ssb, streams, template_location,
        read_cofb_member(tricky_archive, "data/models/gari.map"),
        pbd, models, race_instances)
    # Follow Race scenery dependencies before assigning native IDs. Compact
    # local tables avoid sparse slots that native resource loops can visit.
    source_models = {pbd["instances"][index]["model_id"] for index in race_instances
                     if index not in interactives.replacements}
    # Tricky terrain TextureAssignment indexes SSH images directly.
    # Only prefab meshes use the separate material table.
    source_materials = set()
    for index in source_models:
        for part in models[index]["objects"]:
            source_materials.update(mesh["material"] for mesh in part["meshes"])
    model_ids = {source: rid for rid, source in enumerate(sorted(source_models))}
    material_ids = {source: rid for rid, source in enumerate(sorted(source_materials))}
    materials = [material for material in pbd["materials"]
                 if material["index"] in source_materials]
    if len(materials) != len(material_ids):
        raise FormatError("Race geometry references a missing source material")
    source_to_instance = {source: rid for rid, source in enumerate(race_instances)}
    interactives.prepare(section_id, leaf_id, len(model_ids), len(material_ids),
                         source_to_instance)
    source_textures = {patch["texture_assignment"] for patch in pbd["patches"]}
    source_textures.update(material["texture_id"] for material in materials)
    source_lightmaps = {patch["lightmap_id"] for patch in pbd["patches"]}
    aip, starter_paths = convert_tricky_aip(
        read_cofb_member(tricky_archive, "data/models/gari.aip"),
        main_route=(0, 1, 2, 3, 4, 5))
    textures = [(rid, body) for rid, body in parse_shps(
        read_cofb_member(tricky_archive, "data/models/gari.ssh")) if rid in source_textures]
    lightmaps = [(rid, body) for rid, body in parse_shps(
        read_cofb_member(tricky_archive, "data/models/gari_l.ssh")) if rid in source_lightmaps]
    texture_ids = {rid for rid, _ in textures}
    lightmap_ids = {rid for rid, _ in lightmaps}
    lightmap_sizes = {rid: struct.unpack_from("<2H", body, 4) for rid, body in lightmaps}
    if max(texture_ids, default=-1) + texture_base > 32767:
        raise FormatError("Garibaldi texture IDs exceed the SSX 3 format")
    leaf = bytearray()
    for rid, source in textures:
        body = to_world_ssh(source, lightmap=False)
        inspect_world_ssh(body, lightmap=False)
        leaf.extend(pack_resource(9, 255, texture_base + rid, body))
    for rid, source in lightmaps:
        body = to_world_ssh(source, lightmap=True)
        inspect_world_ssh(body, lightmap=True)
        leaf.extend(pack_resource(10, 255, lightmap_base + rid, body))
    for rid, body in interactives.textures():
        leaf.extend(pack_resource(9, 255, rid, body))
    shared = bytearray()
    for material in materials:
        if material["texture_id"] not in texture_ids:
            raise FormatError("Garibaldi material references a missing SSH texture")
        shared.extend(pack_resource(
            0, section_id, material_ids[material["index"]],
            _material_payload(material, texture_base + material["texture_id"]),
        ))
    model_layouts = {}
    for model in models:
        if model["index"] not in model_ids:
            continue
        rid = model_ids[model["index"]]
        payload, layout = pack_model(model, section_id, resource_id=rid,
                                     material_rids=material_ids)
        shared.extend(pack_resource(2, section_id, rid, payload))
        model_layouts[model["index"]] = layout
    for kind, rid, payload in interactives.records():
        shared.extend(pack_resource(kind, section_id, rid, payload))
    mesh_counts = {}
    for collision in collision_data["collisions"]:
        payload = pack_collision(collision)
        mesh_counts[collision["index"]] = struct.unpack_from("<H", payload, 2)[0]
        shared.extend(pack_resource(12, section_id, collision["index"], payload))
    physics_base = len(collision_data["collisions"])
    for physics in collision_data["physics"]:
        shared.extend(pack_resource(12, section_id, physics_base + physics["index"],
                                    pack_sphere_tree(physics)))
    instance_bounds = []
    collision_bindings = []
    instance_flags = []
    for rid, index in enumerate(race_instances):
        instance = pbd["instances"][index]
        if index in interactives.instance_payloads:
            payload = interactives.instance_payloads[index]
        else:
            payload = pack_instance(instance, model_layouts[instance["model_id"]],
                                    section_id, leaf_id, resource_id=rid,
                                    model_resource_id=model_ids[instance["model_id"]])
        shared.extend(pack_resource(3, section_id, rid, payload))
        source_to_instance[index] = rid
        instance_bounds.append((instance["bounds_min"], instance["bounds_max"]))
        properties = collision_data["properties"][collision_data["instance_properties"][index]]
        instance_flags.append(properties["flags"])
        if properties["flags"] & 32:
            collision_bindings.append({"instance": rid, "source_instance": index,
                                       **properties})
    # Retail target patches have these two constant words and a constant
    # 12-byte tail. The remaining header flags are taken from Tricky where
    # meanings are known. The section byte at +0x155 must identify GARI,
    # independently of the logical section slot leased by the event loader.
    patch_tail = struct.pack("<6h", -1, -1, -1, -1, 0x483c, 17)
    world_min = [math.inf] * 3
    world_max = [-math.inf] * 3
    for patch in pbd["patches"]:
        if patch["texture_assignment"] not in texture_ids:
            raise FormatError("Garibaldi patch references a missing SSH image")
        if patch["lightmap_id"] not in lightmap_ids:
            raise FormatError("Garibaldi patch references a missing lightmap")
        bounds_min, bounds_max = conservative_patch_bounds(patch)
        for axis in range(3):
            world_min[axis] = min(world_min[axis], bounds_min[axis])
            world_max[axis] = max(world_max[axis], bounds_max[axis])
        # Tricky's tile has edge samples but no duplicated gutter. Address
        # the centers of its first/last texels, keeping the shared edge
        # lighting and excluding neighbouring atlas tiles from filtering.
        width, height = lightmap_sizes[patch["lightmap_id"]]
        u, v, du, dv = patch["lightmap_vector"]
        lightmap_uv = [u + 0.5 / width, v + 0.5 / height,
                       du - 1 / width, dv - 1 / height]
        if lightmap_uv[2] <= 0 or lightmap_uv[3] <= 0:
            raise FormatError("Tricky lightmap tile has no interior texels")
        geometry = {**patch, "bounds_min": bounds_min, "bounds_max": bounds_max,
                    "lightmap_vector": lightmap_uv}
        native_surface, terrain_flags = patch_surface(patch["surface_type"])
        prefix = struct.pack(
            "<2I4h", 0x4f7b36c0, 0x004045b7,
            native_surface, terrain_flags, patch["resource_kind_tags"],
            0 if patch["visibility"] else 128,
        )
        rid = patch["index"]
        payload = pack_patch_geometry(
            geometry, prefix=prefix,
            object_id=bytes([section_id]) + rid.to_bytes(3, "little"),
            u10=section_id << 8, chunk_id=leaf_id,
            texture_rid=texture_base + patch["texture_assignment"],
            lightmap_rid=lightmap_base + patch["lightmap_id"],
            tail=patch_tail,
        )
        shared.extend(pack_resource(1, section_id, rid, payload))
    for low, high in instance_bounds:
        for axis in range(3):
            world_min[axis] = min(world_min[axis], low[axis])
            world_max[axis] = max(world_max[axis], high[axis])
    splines = convert_splines(pbd, world_splines, section_id)
    for rid, payload in enumerate(splines):
        shared.extend(pack_resource(8, section_id, rid, payload))
    shared.extend(pack_resource(14, section_id, 0, aip))
    # Retail race/showoff AIP companion resources are zero-length. They are
    # kept so the resource count and RID layout match a normal race section.
    shared.extend(pack_resource(14, section_id, 1, b""))
    shared.extend(pack_resource(14, section_id, 2, b""))
    world_script, script_summary = pack_world_script(
        pbd, models, collision_data, race_instances, section_id, sdb[4:8], mesh_counts,
        interactives)
    shared.extend(pack_resource(16, section_id, 0, world_script))
    new_sdb, new_ssb = append_location(
        sdb, ssb, name="GARI", bounds_min=tuple(world_min),
        bounds_max=tuple(world_max), leaf_resources=bytes(leaf),
        shared_resources=bytes(shared),
    )
    new_locations, _, new_streams = read_sdb(new_sdb)
    if new_locations[:-1] != locations or new_streams[:-2] != streams:
        raise FormatError("the original SSX 3 world entries changed")
    if new_ssb[:len(ssb)] != ssb:
        raise FormatError("the original SSX 3 world stream bytes changed")
    if decode_stream(new_ssb, new_streams[-2]) != leaf:
        raise FormatError("Garibaldi texture stream failed a roundtrip")
    decoded_shared = decode_stream(new_ssb, new_streams[-1])
    if decoded_shared != shared:
        raise FormatError("Garibaldi geometry stream failed a roundtrip")
    summary = resource_summary(decoded_shared, new_streams[-1]["num_resources"])
    rebuilt_members = dict(members)
    rebuilt_members["data/worlds/bam.sdb"] = new_sdb
    rebuilt_members["data/worlds/bam.ssb"] = new_ssb
    archive = pack_bigf(list(rebuilt_members.items()))
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(archive)
    return {
        "output": str(output), "archive_bytes": len(archive),
        "location_index": section_id, "leaf_stream": leaf_id,
        "shared_stream": leaf_id + 1, "world_bounds_min": world_min,
        "world_bounds_max": world_max, "texture_count": len(textures),
        "lightmap_count": len(lightmaps),
        "world_texture_slots": shared_next_id(new_sdb, 9) + shared_next_id(new_sdb, 10),
        "spline_count": len(splines),
        "model_count": len(model_ids) + len(interactives.model_ids),
        "material_count": len(material_ids) + len(interactives.material_ids),
        "source_model_count": len(models),
        "instance_count": len(race_instances) + len(interactives.posts),
        **interactives.summary(),
        "collision_count": physics_base + len(collision_data["physics"]),
        "mesh_collision_count": physics_base,
        "sphere_collision_count": len(collision_data["physics"]),
        **script_summary,
        "collision_bindings": collision_bindings,
        "instance_flags": instance_flags,
        "source_to_instance": source_to_instance,
        "source_to_model": model_ids,
        "source_to_material": material_ids,
        "starter_ai_path_indices": starter_paths,
        "aip": inspect_world_aip(aip), **summary,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ssx3-iso", type=Path,
                        default=Path(os.environ.get("SSX3_ISO", "SSX 3 (USA).iso")))
    parser.add_argument("--tricky-iso", type=Path,
                        default=Path(os.environ.get("SSX_TRICKY_ISO", "SSX Tricky (USA).iso")))
    parser.add_argument("--output", type=Path,
                        default=Path(".cache/BAM-GARI.BIG"))
    args = parser.parse_args()
    try:
        result = build(args.ssx3_iso, args.tricky_iso, args.output)
    except (OSError, FormatError, ValueError, OverflowError, struct.error) as error:
        parser.exit(2, f"Garibaldi world builder: {error}\n")
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
