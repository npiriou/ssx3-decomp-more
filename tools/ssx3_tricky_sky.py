"""Convert a Tricky sky dome to the retail SSX 3 SkyBox instance contract."""

from __future__ import annotations

import math
import struct

from ssx3_interactives import prefab_bounds
from ssx3_models import pack_instance, pack_model
from ssx3_world_archive import _records, replace_single_stream_location, shared_next_id
from ssx3_world_build import pack_resource
from ssx3_world_probe import decode_stream, read_sdb
from tricky_assets import FormatError, parse_pbd, read_cofb_member
from tricky_models import parse_prefabs
from tricky_ssh import parse_shps, to_world_ssh


def close_upper_sky(model: dict) -> int:
    """Continue the authored top texture row across the open sky cylinder.

    Tricky's sky mesh has a horizon ring and a textured ground cap. Its upper
    rim is open; the SSX3 sky painter otherwise exposes the black clear buffer.
    Close that rim at its existing height using the same materials/UV edge.
    No sky image, horizon vertex, projection or geometry scale is replaced.
    """
    vertices = [v for part in model["objects"] for mesh in part["meshes"]
                for chunk in mesh["chunks"] for v in chunk["positions"]]
    if not vertices:
        return 0
    top = max(v[2] for v in vertices)
    epsilon = max(abs(model["scale"][2]) / 16384., 0.001)
    if any(abs(v[2] - top) <= epsilon and math.hypot(v[0], v[1]) <= epsilon
           for v in vertices):
        return 0  # the source already closes its upper rim
    added = 0
    for part in model["objects"]:
        if part["matrix"] is not None:
            raise FormatError("sky rim has an unsupported part transform")
        for mesh in part["meshes"]:
            edge = {}
            for chunk in mesh["chunks"]:
                for position, uv in zip(chunk["positions"], chunk["uv"]):
                    if abs(position[2] - top) <= epsilon:
                        edge[tuple(position)] = tuple(uv)
            if len(edge) < 2:
                continue
            middle = math.atan2(sum(v[1] for v in edge), sum(v[0] for v in edge))
            ring = sorted(edge, key=lambda v: (math.atan2(v[1], v[0]) - middle + math.pi) % (2 * math.pi))
            cap = {"positions": [], "normals": [], "uv": [], "strip_lengths": []}
            for a, b in zip(ring, ring[1:]):
                # Clockwise as seen from above: visible from inside the dome.
                center_uv = [(edge[a][i] + edge[b][i]) / 2 for i in range(2)]
                cap["positions"].extend(([0., 0., top], list(b), list(a)))
                cap["normals"].extend([[0., 0., -1.]] * 3)
                cap["uv"].extend((center_uv, list(edge[b]), list(edge[a])))
                cap["strip_lengths"].append(3)
                added += 1
            mesh["chunks"].append(cap)
        if part["bounds"] is not None:
            for axis in range(2):
                part["bounds"][axis] = min(part["bounds"][axis], 0.)
                part["bounds"][axis + 3] = max(part["bounds"][axis + 3], 0.)
    return added


def import_sky(archive: bytes, stem: str, sdb: bytes, ssb: bytes,
               material_payload) -> tuple[bytes, bytes, dict]:
    locations, _, streams = read_sdb(sdb)
    target = next(item for item in locations if item["name"] == "ASKY")
    section = target["index"]
    hull = target["first_stream"]
    retail = _records(decode_stream(ssb, streams[hull]))
    source = read_cofb_member(archive, f"data/models/{stem}_sky.pbd")
    pbd = parse_pbd(source, True)
    models = parse_prefabs(source, pbd["counts"], pbd["offsets"])
    if len(models) != 1:
        raise FormatError("Tricky sky must provide one camera-centered dome model")
    top_fill = close_upper_sky(models[0])
    textures = parse_shps(read_cofb_member(archive, f"data/models/{stem}_sky.ssh"))
    texture_base = shared_next_id(sdb, 9)
    texture_ids = {source: texture_base + i for i, (source, _) in enumerate(textures)}
    materials = {item["index"]: item["index"] for item in pbd["materials"]}
    raw = bytearray()
    for rid, body in textures:
        raw.extend(pack_resource(9, 255, texture_ids[rid], to_world_ssh(body, lightmap=False)))
    for item in pbd["materials"]:
        texture = item["texture_id"]
        raw.extend(pack_resource(0, section, item["index"], material_payload(
            item, -1 if texture < 0 else texture_ids[texture])))
    model, layout = pack_model(models[0], section, resource_id=0, material_rids=materials)
    raw.extend(pack_resource(2, section, 0, model))
    bounds = prefab_bounds(models[0])
    instance = {
        "index": 0, "model_id": 0,
        "matrix": [[1., 0., 0., 0.], [0., 1., 0., 0.],
                   [0., 0., 1., 0.], [0., 0., 0., 1.]],
        "bounds_min": bounds[:3], "bounds_max": bounds[3:],
        "light_matrix": [[0.] * 4 for _ in range(4)],
        "light_colours": [[0.] * 4 for _ in range(3)] + [[128.] * 4],
    }
    raw.extend(pack_resource(3, section, 0, pack_instance(instance, layout, section, hull)))
    # Retain native sky painter/binding records and the empty script header.
    # SkyBox_Render centers instance0 on the camera and draws at scale1.0;
    # the painted dome's angular shape therefore needs no invented rescale.
    for kind, track, rid, body in retail:
        if kind not in (0, 1, 2, 3, 9, 10):
            raw.extend(pack_resource(kind, track, rid, body))
    new_sdb, new_ssb = replace_single_stream_location(sdb, ssb, "ASKY", bytes(raw))
    return new_sdb, new_ssb, {
        "source_sky": f"data/models/{stem}_sky.pbd", "native_section": "ASKY",
        "texture_count": len(textures), "material_count": len(materials),
        "model_count": 1, "instance_count": 1, "unpacked_bytes": len(raw),
        "native_upper_fill_triangles": top_fill,
    }
