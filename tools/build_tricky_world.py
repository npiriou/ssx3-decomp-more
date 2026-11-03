"""Build one Tricky course/mode in its own native SSX 3 BAM archive.

The derived data includes terrain, animated prefabs, textures, splines and
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
from tricky_courses import Course, course
from ssx3_tricky_sky import import_sky
from ssx3_particle_sprites import ParticleSprites
from tricky_gameplay import pack_gameplay
from tricky_object_effects import (pack_object_scripts, source_pickups,
                                  mode_hidden_instances, read_logic)
from tricky_race_settings import showoff_catalog
from tricky_audio import object_sounds
from ssx3_tricky_crowds import CrowdSprites
from ssx3_tricky_movies import MovieScreens


def _verify_disc(iso: Path, serial: bytes, label: str) -> None:
    if serial not in read_iso_file(iso, "SYSTEM.CNF"):
        raise FormatError(f"{iso}: expected {label} ({serial.decode('ascii')})")


def _material_payload(source: dict, texture_rid: int, frames=()) -> bytes:
    # The Tricky 0x20000 and 0x40000 appearance bits correspond to alpha
    # test and alpha blend. SSX 3 WorldMaterial uses bits 2 and 4 in its
    # render flags. This visual mapping still needs an in-game comparison.
    flags = source["appearance_flags"]
    if flags & ~0x75108:
        raise FormatError(f"unknown Tricky material appearance flags {flags:#x}")
    render_flags = 1 | (2 if flags & 0x20000 else 0) | (4 if flags & 0x40000 else 0)
    # Native material+0x10 is -1 for no flipbook, otherwise the resolver
    # points it at the inline {count, {u16 texture,u16 opaque} frames[]}.
    # Native TexFlipModifier makes its own per-instance material records.
    out = struct.pack("<8hi", frames[0] if frames else texture_rid,
                      -1, -1, 0, 0, 0, 1, render_flags, 0 if frames else -1)
    if frames:
        out += struct.pack("<I", len(frames))
        out += b"".join(struct.pack("<HH", texture, 0) for texture in frames)
    return out


def build(SSX3_iso: Path, tricky_iso: Path, output: Path, *,
          selected: Course | None = None, mode: str = "race") -> dict:
    selected = selected or course("garibaldi")
    if mode not in selected.modes:
        raise FormatError(f"{selected.name} has no {mode} event")
    stem = selected.code.lower()
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
    tricky_archive = read_iso_file(tricky_iso, selected.archive)
    pbd_data = read_cofb_member(tricky_archive, f"data/models/{stem}.pbd")
    pbd = parse_pbd(pbd_data, True)
    models = parse_prefabs(pbd_data, pbd["counts"], pbd["offsets"])
    ssf_data = read_cofb_member(tricky_archive, f"data/models/{stem}.ssf")
    _, sound_ids, sound_summary = object_sounds(SSX3_iso, tricky_iso, selected.code, ssf_data)
    collision_data = parse_ssf(ssf_data)
    spatial = parse_ltg(read_cofb_member(tricky_archive, f"data/models/{stem}.ltg"),
                        pbd["counts"], True)
    instance_list = "race_instances" if mode == "race" else "showoff_instances"
    race_instances = sorted({index for node in spatial["nodes"]
                             for index in node[instance_list]})
    mode_hidden, mode_dynamic_hidden = mode_hidden_instances(ssf_data, mode)
    race_instances = [index for index in race_instances if index not in mode_hidden]
    aip_source = read_cofb_member(tricky_archive, f"data/models/{stem}.aip")
    timing = showoff_catalog(tricky_iso)[selected.code]
    gameplay, gameplay_summary = pack_gameplay(
        ssf_data, pbd, collision_data, race_instances, aip_source,
        showoff_hundredths=timing["showoff_hundredths"], freestyle=mode == "freestyle")
    path_source = aip_source
    main_route = selected.main_route
    if mode == "freestyle":
        path_source = read_cofb_member(tricky_archive, f"data/models/{stem}.sop")
        from tricky_assets import parse_aip
        source_paths = parse_aip(path_source, True)["race_paths"]
        finishes = [i for i, path in enumerate(source_paths)
                    if any(event["type"] == 9 for event in path["events"])]
        if len(finishes) != 1:
            raise FormatError("SOP requires a unique main-route finish")
        main_route = tuple(range(finishes[0] + 1))
    # Some invisible force volumes also own focus effects (Tokyo air shafts).
    # Keep those owners; pack_world_script retains their cleared visible bit.
    # Forces remain in TFX2. A mode1/zero-duration force with further contact
    # actions also needs its source shared ownership until every rider leaves.
    slots, effect_chains, _ = read_logic(ssf_data)
    boost_instances = set(gameplay_summary["source_boost_instances"])
    focus_volumes = set()
    contact_volumes = set()
    for index in boost_instances:
        prop = collision_data["properties"][collision_data["instance_properties"][index]]
        if prop["effect_slot"] >= 0 and slots[prop["effect_slot"]][0] >= 0:
            focus_volumes.add(index)
        if prop["effect_slot"] >= 0:
            chain = slots[prop["effect_slot"]][1]
            nodes = effect_chains[chain] if chain >= 0 else []
            if nodes:
                first = nodes[0]
                words = first["words"]
                if (first["main"] == 0 and len(words) == 8 and words[:3] == (7, 1, 0)
                        and len(nodes) > 1 and prop["collision_mode"] == 2
                        and prop["surface"] == -1
                        and len(models[pbd["instances"][index]["model_id"]]["objects"]) == 1):
                    contact_volumes.add(index)
    race_instances = [index for index in race_instances if index not in boost_instances
                      or index in focus_volumes
                      or index in contact_volumes
                      or collision_data["properties"][collision_data["instance_properties"][index]]["flags"] & 1]
    interactives = NativeInteractives(
        ssb, streams, locations,
        read_cofb_member(tricky_archive, f"data/models/{stem}.map"),
        pbd, models, race_instances,
        source_pickups(ssf_data, collision_data, race_instances))
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
    source_textures.update(material["texture_id"] for material in materials
                           if material["texture_id"] >= 0)
    for material in materials:
        flip = material["texture_flipbook_id"]
        if flip >= 0:
            source_textures.update(pbd["texture_flipbooks"][flip])
    source_lightmaps = {patch["lightmap_id"] for patch in pbd["patches"]}
    aip, starter_paths = convert_tricky_aip(path_source, main_route=main_route,
                                           freestyle=mode == "freestyle")
    textures = [(rid, body) for rid, body in parse_shps(
        read_cofb_member(tricky_archive, f"data/models/{stem}.ssh")) if rid in source_textures]
    lightmaps = [(rid, body) for rid, body in parse_shps(
        read_cofb_member(tricky_archive, f"data/models/{stem[:6]}_l.ssh")) if rid in source_lightmaps]
    texture_ids = {rid for rid, _ in textures}
    lightmap_ids = {rid for rid, _ in lightmaps}
    lightmap_sizes = {rid: struct.unpack_from("<2H", body, 4) for rid, body in lightmaps}
    particle_sprites = ParticleSprites(tricky_iso, texture_base + max(texture_ids, default=-1) + 1)
    # Reserve crowd frames before the lazily assigned particle images. Both
    # use native world slots and must never alias the mountain texture0.
    crowds = CrowdSprites(tricky_iso, particle_sprites.first_id, pbd, models,
        race_instances, model_ids, material_ids, source_to_instance, section_id, leaf_id)
    particle_sprites.first_id += len(crowds.frames)
    movies = MovieScreens(tricky_iso, selected.code, particle_sprites.first_id,
        ssf_data, pbd, models, collision_data, race_instances, model_ids, material_ids,
        source_to_instance, section_id, leaf_id, output)
    particle_sprites.first_id += bool(movies.data)
    object_summary = pack_object_scripts(
        ssf_data, pbd, models, collision_data, race_instances, source_to_instance,
        interactives, section_id, mode, particle_sprites=particle_sprites,
        force_leases=contact_volumes, initial_hidden=mode_dynamic_hidden,
        sound_ids=sound_ids, crowds=crowds, movies=movies)
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
    for rid, body in particle_sprites.records():
        inspect_world_ssh(body, lightmap=False)
        leaf.extend(pack_resource(9, 255, rid, body))
    for rid, body in crowds.records():
        inspect_world_ssh(body, lightmap=False)
        leaf.extend(pack_resource(9, 255, rid, body))
    for rid, body in movies.records():
        inspect_world_ssh(body, lightmap=False)
        leaf.extend(pack_resource(9, 255, rid, body))
    shared = bytearray()
    for material in materials:
        if material["texture_id"] >= 0 and material["texture_id"] not in texture_ids:
            raise FormatError("Garibaldi material references a missing SSH texture")
        shared.extend(pack_resource(
            0, section_id, material_ids[material["index"]],
            crowds.material() if material["index"] in crowds.materials else
            _material_payload(material, -1 if material["texture_id"] < 0 else
                              texture_base + material["texture_id"],
                              [texture_base + texture for texture in
                               pbd["texture_flipbooks"][material["texture_flipbook_id"]]]
                              if material["texture_flipbook_id"] >= 0 else ()),
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
        if index in movies.instances:
            payload = movies.instances[index]
        elif index in crowds.instances:
            payload = crowds.instances[index]
        elif index in interactives.instance_payloads:
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
    emitter_hosts = [(owner, rid, False) for owner, rid in interactives.emitter_anchors.items()]
    emitter_hosts += [(owner, rid, True) for owner, rid in interactives.collision_emitter_anchors.items()]
    emitter_hosts += [(owner, rid, False) for owner, rid in interactives.spline_anchors.items()]
    for owner, rid, world_space in sorted(emitter_hosts, key=lambda host: host[1]):
        instance = pbd["instances"][owner]
        if world_space:
            # Collision bursts already contain a world-space contact point
            # and velocity. Keep the owner's bounds for native focus cleanup,
            # with identity basis so the emitter does not transform them twice.
            instance = dict(instance, matrix=[[float(row == col) for col in range(4)]
                                              for row in range(4)])
        payload = pack_instance(instance, model_layouts[instance["model_id"]],
                                section_id, leaf_id, resource_id=rid,
                                model_resource_id=model_ids[instance["model_id"]])
        shared.extend(pack_resource(3, section_id, rid, payload))
        instance_bounds.append((instance["bounds_min"], instance["bounds_max"]))
        instance_flags.append(0)
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
        sdb, ssb, name=selected.code, bounds_min=tuple(world_min),
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
    new_sdb, new_ssb, sky_summary = import_sky(
        tricky_archive, stem, new_sdb, new_ssb, _material_payload)
    rebuilt_members = dict(members)
    rebuilt_members["data/worlds/bam.sdb"] = new_sdb
    rebuilt_members["data/worlds/bam.ssb"] = new_ssb
    archive = pack_bigf(list(rebuilt_members.items()))
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(archive)
    output.with_suffix(".FX").write_bytes(gameplay)
    return {
        "course_id": selected.id, "course_name": selected.name,
        "mode": mode, "source_archive": selected.archive,
        **gameplay_summary,
        **object_summary,
        "source_object_sound_bank": sound_summary,
        **particle_sprites.summary(),
        **crowds.summary(),
        **movies.summary(),
        "source_paths": "SOP" if mode == "freestyle" else "AIP",
        "source_timing": timing,
        "sky": sky_summary,
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
        "native_animation_base_pose_ranges": sum(
            bool(channel and channel[0][4] > 0)
            for model in models if model["index"] in model_ids
            for part in model["objects"] if part.get("animation") is not None
            for channel in part["animation"]["channels"]),
        "source_mode_hidden_instances": sorted(mode_hidden),
        "source_mode_hidden_dynamic_targets": sorted(mode_dynamic_hidden),
        "source_force_focus_instances": sorted(focus_volumes),
        "source_force_contact_instances": sorted(contact_volumes),
        "instance_count": len(race_instances) + len(interactives.posts) + len(emitter_hosts),
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
    parser.add_argument("--course", default="garibaldi")
    parser.add_argument("--mode", choices=("race", "freestyle"), default="race")
    parser.add_argument("--ssx3-iso", type=Path,
                        default=Path(os.environ.get("SSX3_ISO", "SSX 3 (USA).iso")))
    parser.add_argument("--tricky-iso", type=Path,
                        default=Path(os.environ.get("SSX_TRICKY_ISO", "SSX Tricky (USA).iso")))
    parser.add_argument("--output", type=Path,
                        default=Path(".cache/BAM-GARI.BIG"))
    args = parser.parse_args()
    try:
        result = build(args.ssx3_iso, args.tricky_iso, args.output,
                       selected=course(args.course), mode=args.mode)
    except (OSError, FormatError, ValueError, OverflowError, struct.error) as error:
        parser.exit(2, f"Garibaldi world builder: {error}\n")
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
