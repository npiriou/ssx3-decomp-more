"""Extract authored Tricky boost volumes and lap passes for the native rider.

The payload stays beside the derived BAM, outside Git. World coordinates are
centimetres; authored boost speeds are metres/second. SSF MainType 0's boost
family is separate from the collectible speed/trick/score pickups.
"""

import math
import struct

from tricky_assets import FormatError, parse_aip


RECORD = struct.Struct("<4I32f")
BOOST_TYPES = (7, 15, 18, 24)


def pack_gameplay(ssf, pbd, collision, instances, aip, *, showoff_hundredths=0,
                  freestyle=False):
    source = parse_aip(aip, True)
    passes = {event["value"] for path in source["race_paths"]
              for event in path["events"] if event["type"] == 12}
    if len(passes) > 1 or any(value < 2 or value > 16 for value in passes):
        raise FormatError("inconsistent Tricky lap pass count")
    pass_count = next(iter(passes), 1)
    slot_count, slot_at = struct.unpack_from("<2I", ssf, 12)
    effect_count, effect_at = struct.unpack_from("<2I", ssf, 36)
    effect_base = effect_at + effect_count * 8
    records = []
    sources = set()
    for index in instances:
        prop = collision["properties"][collision["instance_properties"][index]]
        slot = prop["effect_slot"]
        if slot < 0:
            continue
        if slot >= slot_count:
            raise FormatError("Tricky effect slot is out of range")
        chain = struct.unpack_from("<i", ssf, slot_at + slot * 28 + 4)[0]
        if chain < 0:
            continue
        if chain >= effect_count:
            raise FormatError("Tricky collision effect chain is out of range")
        count, offset = struct.unpack_from("<2I", ssf, effect_at + chain * 8)
        pos = effect_base + offset
        for _ in range(count):
            main_type, size = struct.unpack_from("<2I", ssf, pos)
            if size < 8 or pos + size > len(ssf):
                raise FormatError("Tricky effect extends beyond SSF")
            subtype = struct.unpack_from("<I", ssf, pos + 8)[0] if size >= 12 else -1
            if main_type == 0 and subtype in BOOST_TYPES:
                mode = 1
                values = [0.] * 32
                payload = pos + 12
                if subtype in (7, 24):
                    mode, window = struct.unpack_from("<If", ssf, payload)
                    values[2] = window
                    payload += 8
                values[0], values[1] = struct.unpack_from("<2f", ssf, payload)
                values[4:7] = struct.unpack_from("<3f", ssf, payload + 8)
                instance = pbd["instances"][index]
                values[8:11] = instance["bounds_min"]
                values[12:15] = instance["bounds_max"]
                values[16:19] = instance["matrix"][0][:3]
                if subtype == 18:
                    values[19], values[3] = struct.unpack_from("<2f", ssf, payload + 20)
                elif subtype == 24:
                    for stage in range(3):
                        values[20 + stage * 4:23 + stage * 4] = struct.unpack_from(
                            "<3f", ssf, payload + 20 + stage * 12)
                        values[23 + stage * 4] = struct.unpack_from(
                            "<f", ssf, payload + 56 + stage * 4)[0]
                if not all(math.isfinite(value) for value in values):
                    raise FormatError("non-finite authored boost volume")
                records.append(RECORD.pack(index, subtype, mode, 0, *values))
                sources.add(index)
            pos += size
    return (struct.pack("<4s5I", b"TFX2", pass_count, len(records),
                        showoff_hundredths, int(freestyle), 0) + b"".join(records),
            {"lap_passes": pass_count, "native_boost_volumes": len(records),
             "showoff_hundredths": showoff_hundredths if freestyle else None,
             "source_boost_instances": sorted(sources)})
