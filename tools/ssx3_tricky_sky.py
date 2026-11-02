"""Convert a Tricky sky dome to the retail SSX 3 SkyBox instance contract."""

from __future__ import annotations

import struct

from ssx3_interactives import prefab_bounds
from ssx3_models import pack_instance, pack_model
from ssx3_world_archive import _records, replace_single_stream_location, shared_next_id
from ssx3_world_build import pack_resource
from ssx3_world_probe import decode_stream, read_sdb
from tricky_assets import FormatError, parse_pbd, read_cofb_member
from tricky_models import parse_prefabs
from tricky_ssh import parse_shps, to_world_ssh


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
    }
