"""Build native SSX 3 MDR model data from decoded Tricky prefab meshes."""

from __future__ import annotations

import math
import struct

from tricky_assets import FormatError


def _pad(data: bytearray, alignment: int = 16) -> None:
    data.extend(b"\0" * (-len(data) % alignment))


def _q16(value: float, factor: float) -> int:
    quantized = round(value * factor)
    if not -32768 <= quantized <= 32767:
        raise FormatError("model value exceeds signed 16-bit quantization")
    return quantized


def _batches(mesh: dict, maximum: int = 48) -> list[dict]:
    batches = []
    current = {"positions": [], "normals": [], "uv": [], "strip_lengths": []}

    def flush() -> None:
        nonlocal current
        if current["positions"]:
            batches.append(current)
            current = {"positions": [], "normals": [], "uv": [], "strip_lengths": []}

    for chunk in mesh["chunks"]:
        base = 0
        for length in chunk["strip_lengths"]:
            offset = 0
            while offset < length:
                count = min(maximum, length - offset)
                if len(current["positions"]) + count > maximum:
                    flush()
                for name in ("positions", "normals", "uv"):
                    current[name].extend(chunk[name][base + offset:base + offset + count])
                current["strip_lengths"].append(count)
                if offset + count == length:
                    break
                # Retain the last two vertices of a long strip. An even
                # batch capacity keeps the original winding after the split.
                flush()
                offset += count - 2
            base += length
    flush()
    return batches


def _model_segment(batch: dict, scale: tuple, first: bool) -> bytes:
    count = len(batch["positions"])
    strips = batch["strip_lengths"]
    base = 0x1b if first else 0
    strip_address = base + 2
    position_address = strip_address + len(strips)
    uv_address = position_address + count
    out = bytearray(struct.pack(
        "<12I", 0x01000101, 0x05000000, 0, 0x30000000,
        *([0x3f800000] * 4), 0, 0x04000000, 0,
        0x6c020000 | 0x8000 | base))
    gif_tag = count | (1 << 15) | (1 << 46) | (0x5c << 47) | (3 << 60)
    out.extend(struct.pack("<QQ4I", gif_tag, 0x412, len(strips), 0, count, 0))
    out.extend(struct.pack("<4I", 0, 0, 0,
                           0x66000000 | (len(strips) << 16) | 0x8000 | strip_address))
    for length in strips:
        out.extend(struct.pack("<BB", length, 0))
    _pad(out)
    out.extend(struct.pack("<4I", 0x20000000, 0x50505050, 0,
                           0x75000000 | (count << 16) | 0x8000 | uv_address))
    for uv in batch["uv"]:
        out.extend(struct.pack("<2h", *(_q16(value, 4096) for value in uv)))
    _pad(out)
    out.extend(struct.pack("<4I", 0x20000000, 0x40404040, 0,
                           0x79000000 | (count << 16) | 0x8000 | position_address))
    for position in batch["positions"]:
        out.extend(struct.pack("<3h", *(_q16(position[axis], 32768 / scale[axis])
                                        for axis in range(3))))
    _pad(out)
    return bytes(out)


def _normal_segment(batch: dict, first: bool) -> bytes:
    count = len(batch["positions"])
    address = (0x1b if first else 0) + 2 + len(batch["strip_lengths"]) + 2 * count
    out = bytearray(struct.pack("<4I", 0x20000000, 0x40404040, 0,
                                0x79000000 | (count << 16) | 0x8000 | address))
    for normal in batch["normals"]:
        out.extend(struct.pack("<3h", *(_q16(value, 32768) for value in normal)))
    _pad(out)
    # The model resolver replaces the retail DEADBEEF microprogram marker.
    out.extend(struct.pack("<4I", 0x20000000, 0, 0xdeadbeef, 0x04000001))
    return bytes(out)


def _dma_reference(data: bytearray, at: int, offset: int, payload: bytes) -> None:
    if len(payload) % 16 or offset > 0xffffff:
        raise FormatError("MDR DMA reference is outside its format")
    struct.pack_into("<4I", data, at, 0x30000000 | (len(payload) // 16), offset, 0, 0)


def _pack_animation(out: bytearray, animation: dict) -> int:
    # cPS2ChunkResolve_v06 relocates the part's third word, then v11 fixes
    # descriptor+0x20 and each channel pointer against the MDR model base.
    # Its channel callback v12 likewise fixes the segment pointer at +4.
    _pad(out)
    start = len(out)
    channels = animation["channels"]
    table = start + 36
    out.extend(struct.pack("<6f3I", *animation["base_position"],
                           *animation["base_rotation"], animation["mask"],
                           len(channels), table))
    out.extend(b"\0" * (4 * len(channels)))
    for index, curves in enumerate(channels):
        _pad(out)
        channel = len(out)
        struct.pack_into("<I", out, table + index * 4, channel)
        out.extend(struct.pack("<2I", len(curves), channel + 8))
        for curve in curves:
            out.extend(struct.pack("<6f", *curve))
    return start


def pack_model(model: dict, section_id: int, *, resource_id: int | None = None,
               material_rids: dict[int, int] | None = None) -> tuple[bytes, list[dict]]:
    """Return a type-2 payload and its group/batch layout for instances."""
    objects = model["objects"]
    materials = sorted({mesh["material"] for part in objects for mesh in part["meshes"]})
    material_indices = {material: index for index, material in enumerate(materials)}
    object_table = 44 + len(materials) * 4
    out = bytearray(object_table + len(objects) * 16)
    for index, material in enumerate(materials):
        rid = material if material_rids is None else material_rids[material]
        struct.pack_into("<I", out, 44 + index * 4, (rid << 8) | section_id)
    groups = []
    for index, part in enumerate(objects):
        geometry = 0
        if part["meshes"]:
            geometry = len(out)
            count = len(part["meshes"])
            pointer_table = geometry + 36
            out.extend(struct.pack("<6f3I", *part["bounds"], 1, count, pointer_table))
            out.extend(b"\0" * (count * 4))
            for mesh_index, mesh in enumerate(part["meshes"]):
                header = len(out)
                struct.pack_into("<I", out, pointer_table + mesh_index * 4, header)
                out.extend(struct.pack("<hHI", material_indices[mesh["material"]], 1, 0))
                groups.append({"header": header, "part": index,
                               "material": mesh["material"], "batches": _batches(mesh)})
        animation = (_pack_animation(out, part["animation"])
                     if part.get("animation") is not None else 0)
        matrix = 0xffffffff
        if part["matrix"] is not None:
            _pad(out)
            matrix = len(out)
            out.extend(struct.pack("<16f", *part["matrix"]))
        struct.pack_into("<4I", out, object_table + index * 16,
                         part["parent"], geometry, animation, matrix)
    _pad(out)
    model_data = len(out)
    chain_size = sum((2 * len(group["batches"]) + 1) * 16 for group in groups)
    dma = bytearray(chain_size)
    chain = 0
    for group in groups:
        group["chain_offset"] = chain
        struct.pack_into("<I", out, group["header"] + 4, chain)
        for batch_index, batch in enumerate(group["batches"]):
            vertices = _model_segment(batch, model["scale"], batch_index == 0)
            normals = _normal_segment(batch, batch_index == 0)
            offset = len(dma)
            _dma_reference(dma, chain, offset, vertices)
            dma.extend(vertices)
            batch["geometry_offset"] = offset
            batch["geometry_qwords"] = len(vertices) // 16
            offset = len(dma)
            _dma_reference(dma, chain + 16, offset, normals)
            dma.extend(normals)
            chain += 32
        struct.pack_into("<4I", dma, chain, 0x60000000, 0, 0, 0)
        chain += 16
    out.extend(dma)
    rid = model["index"] if resource_id is None else resource_id
    struct.pack_into("<5If3f2I", out, 0, (rid << 8) | section_id,
                     # Tricky's duration is frames30; both games' cubic key
                     # times are seconds, and native MDR duration is seconds.
                     len(objects), object_table, 40, 0, model.get("animation_time", 0.0) / 30.0,
                     *model["scale"], model_data, len(materials))
    return bytes(out), groups


def _vertex_colour(normal: list[float], instance: dict) -> int:
    directions = instance["light_matrix"]
    colours = instance["light_colours"]
    weights = [max(0.0, sum(normal[axis] * directions[axis][light]
                            for axis in range(3))) for light in range(3)]
    rgb = [min(31, max(0, round((colours[3][channel] +
                                sum(weights[light] * colours[light][channel]
                                    for light in range(3))) / 8)))
           for channel in range(3)]
    return rgb[0] | (rgb[1] << 5) | (rgb[2] << 10) | 0x8000


def _colour_segment(batch: dict, instance: dict, first: bool) -> bytes:
    count = len(batch["positions"])
    address = (0x1b if first else 0) + 2 + len(batch["strip_lengths"]) + 2 * count
    out = bytearray(struct.pack("<4I", 0, 0x01000101, 0,
                                0x6f000000 | (count << 16) | 0x8000 | address))
    for normal in batch["normals"]:
        out.extend(struct.pack("<H", _vertex_colour(normal, instance)))
    _pad(out)
    out.extend(struct.pack("<4I", 0x20000000, 0, 0xdeadbeef, 0x04000001))
    return bytes(out)


def pack_instance(instance: dict, groups: list[dict], section_id: int,
                  leaf_id: int, *, resource_id: int | None = None,
                  model_resource_id: int | None = None) -> bytes:
    """Build a type-3 instance with native per-vertex lighting chains."""
    low = instance["bounds_min"]
    high = instance["bounds_max"]
    center = [(low[axis] + high[axis]) / 2 for axis in range(3)]
    radius = math.sqrt(sum(((high[axis] - low[axis]) / 2) ** 2 for axis in range(3)))
    out = bytearray(160)
    rid = instance["index"] if resource_id is None else resource_id
    model_rid = instance["model_id"] if model_resource_id is None else model_resource_id
    matrix = [value for row in instance["matrix"] for value in row]
    struct.pack_into("<16f4f6f", out, 16, *matrix, *center, radius, *low, *high)
    struct.pack_into("<I2BhIf2I2h3I", out, 120,
                     (rid << 8) | section_id, 0, section_id, leaf_id,
                     (model_rid << 8) | section_id, 1.0, 0, 0,
                     -1, 0, 0, 160, 0)
    chain_size = sum((2 * len(group["batches"]) + 1) * 16 for group in groups)
    dma = bytearray(chain_size)
    chain = 0
    for group in groups:
        for batch_index, batch in enumerate(group["batches"]):
            struct.pack_into("<4I", dma, chain,
                             0x30000000 | batch["geometry_qwords"],
                             batch["geometry_offset"], 0, 0)
            colours = _colour_segment(batch, instance, batch_index == 0)
            offset = len(dma)
            _dma_reference(dma, chain + 16, offset, colours)
            dma.extend(colours)
            chain += 32
        struct.pack_into("<4I", dma, chain, 0x60000000, 0, 0, 0)
        chain += 16
    out.extend(dma)
    return bytes(out)
