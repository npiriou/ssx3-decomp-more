"""Translate prefab animations and reset contacts to native SSX 3 scripts.

Curves live in the MDR. Luno's native focus-entry callback creates the process
when scenery enters the active area and recreates it after native focus cleanup.
"""

import math
import struct

from tricky_assets import FormatError
from ssx3_luno import calls_blob


def read_logic(data: bytes) -> tuple[list[tuple], list[list[dict]], list[dict]]:
    pairs = struct.unpack_from("<16I", data, 12)
    slot_count, slot_at = pairs[:2]
    effect_count, effect_at = pairs[6:8]
    function_count, function_at = pairs[8:10]
    base = effect_at + effect_count * 8

    def chain(count: int, offset: int) -> list[dict]:
        nodes = []
        pos = base + offset
        for _ in range(count):
            main, size = struct.unpack_from("<2I", data, pos)
            if size < 8 or size % 4 or pos + size > len(data):
                raise FormatError(f"invalid SSF effect at {pos:#x}")
            words = struct.unpack_from("<" + "I" * ((size - 8) // 4), data, pos + 8)
            nodes.append({"main": main, "sub": words[0] if main in (0, 2) else None,
                          "words": words, "offset": pos})
            pos += size
        return nodes

    slots = [struct.unpack_from("<7i", data, slot_at + i * 28) for i in range(slot_count)]
    effects = [chain(*struct.unpack_from("<2I", data, effect_at + i * 8))
               for i in range(effect_count)]
    functions = []
    for i in range(function_count):
        at = function_at + i * 24
        name = data[at + 8:at + 24].split(b"\0")[0].decode("ascii")
        functions.append({"name": name, "nodes": chain(*struct.unpack_from("<2I", data, at))})
    return slots, effects, functions


def pack_object_scripts(ssf, pbd, models, collision, instances, source_to_instance,
                           interactives, section):
    slots, chains, functions = read_logic(ssf)
    selected = set(instances)
    records = {}
    roots = {}
    animation_kinds = {}
    resets = set()
    fragments = set()
    hidden = set()
    teleports = {}
    scrolls = set()
    flips = set()
    receiver_kinds = {}

    def float_value(bits):
        return struct.unpack("<f", struct.pack("<I", bits))[0]

    def walk(nodes, owner, seen, commands):
        for node in nodes:
            main, words = node["main"], node["words"]
            # A later wave must translate their scheduling/predicates. Never
            # hoist later actions across a wait or conditional gate.
            if main in (4, 5):
                break
            if main == 7:
                target, chain = words[:2]
                key = ("chain", target, chain)
                if target in selected and key not in seen and chain < len(chains):
                    walk(chains[chain], target, seen | {key}, commands)
            elif main in (21, 26):
                index = words[0]
                key = ("function", owner, index)
                if key not in seen and index < len(functions):
                    walk(functions[index]["nodes"], owner, seen | {key}, commands)
            elif owner in interactives.replacements:
                continue
            elif main == 13:
                if words != (0,):
                    raise FormatError("unsupported Tricky reset-zone parameters")
                commands.append((111, []))
                resets.add(owner)
            elif main == 24:
                if len(words) != 1 or words[0] not in selected:
                    raise FormatError("Tricky teleport destination is not imported")
                destination = words[0]
                rid = (source_to_instance[destination] << 8) | section
                # Native matrix placement uses the authored exit frame/spread,
                # then primes its path without sweeping skipped checkpoints.
                commands.extend(((112, [(0, rid, 1)]), (113, []), (114, [])))
                teleports[owner] = destination
            elif main == 0 and words[0] == 5 and words[1] == 4:
                # Tricky's hard breakable kill is native DeadNode mode zero.
                # Its constructor clears drawing/collision and the native
                # reset lifecycle restores the source static property flags.
                rid = (source_to_instance[owner] << 8) | section
                commands.append((2, [(0, rid, 1), (1, 0, 1)]))
                hidden.add(owner)
            elif main == 0 and words[0] == 20:
                model = models[pbd["instances"][owner]["model_id"]]
                if len(words) != 11 or len(model["objects"]) > 24:
                    raise FormatError("Tricky fragments exceed native MeshAnim layout")
                if not all(math.isfinite(float_value(v)) for v in words[2:]):
                    raise FormatError("non-finite Tricky MeshAnim parameters")
                rid = (source_to_instance[owner] << 8) | section
                # The native constructor's frame step/lifetime, random launch
                # vector and contact-scaled centre velocity correspond to the
                # authored SSF fields. Remaining angular settings use SSX 3's
                # defaults. Keep every original part and its geometry.
                params = [rid, words[1], words[2], words[10], words[3],
                          *words[7:10], *words[4:7]]
                commands.append((13, [(i, value, 1 if i < 2 else 2)
                                      for i, value in enumerate(params)]))
                fragments.add(owner)
            elif main == 0 and words[0] == 2:
                if len(words) != 2 or not math.isfinite(float_value(words[1])):
                    raise FormatError("invalid Tricky debounce duration")
                rid = (source_to_instance[owner] << 8) | section
                commands.append((1, [(0, rid, 1), (1, words[1], 2)]))
            elif main == 0 and words[0] == 10:
                if len(words) != 7 or not all(math.isfinite(float_value(v)) for v in words[2:]):
                    raise FormatError("invalid Tricky UV scroll parameters")
                _, mode, du, dv, active, pause, lifetime = words
                if float_value(lifetime) != 0:
                    continue  # finite property teardown needs its continuation
                rid = (source_to_instance[owner] << 8) | section
                native_mode = {1: 6, 2: 2}.get(mode, 0)
                # Native Object promotes visible static instances itself.
                # Keep its force-dynamic default zero so an invisible source
                # receiver does not become a newly drawable object.
                commands.append((0, [(0, rid, 1)]))
                params = [rid, native_mode, 0, 0, du, dv, active, pause,
                          0, 0, 0, 0x3f800000]
                commands.append((21, [(i, v, 1 if i < 2 else 2)
                                      for i, v in enumerate(params)]))
                scrolls.add(owner)
                receiver_kinds[owner] = 10
            elif main == 0 and words[0] == 11:
                if len(words) != 6 or not all(math.isfinite(float_value(v)) for v in words[3:5]):
                    raise FormatError("invalid Tricky texture flip parameters")
                _, start, direction, speed, lifetime, dwell = words
                if float_value(lifetime) != 0:
                    continue  # preserve finite lifetime rather than loop forever
                model = models[pbd["instances"][owner]["model_id"]]
                materials = {mesh["material"] for part in model["objects"] for mesh in part["meshes"]}
                if not any(pbd["materials"][i]["texture_flipbook_id"] >= 0 for i in materials):
                    continue
                if len(materials) > 8:
                    raise FormatError("Tricky texture flip exceeds native eight-material capacity")
                if direction not in (0, 1) or dwell not in (0, 1):
                    raise FormatError("unsupported Tricky texture flip mode")
                rid = (source_to_instance[owner] << 8) | section
                commands.append((0, [(0, rid, 1)]))
                commands.append((22, [(0, rid, 1), (1, dwell, 1), (2, start, 1),
                                      (3, direction, 1), (4, speed, 2)]))
                flips.add(owner)
                receiver_kinds[owner] = 11
            elif main == 0 and words[0] in (256, 257, 258):
                model = models[pbd["instances"][owner]["model_id"]]
                if not any(part["animation"] and part["animation"]["channels"]
                           for part in model["objects"]):
                    continue
                kind = words[0]
                if len(words) != (13 if kind == 258 else 9):
                    raise FormatError("unexpected Tricky animation parameter count")
                _, loop, start, end, rate, variation, debounce, random, direction = words[:9]
                floats = [float_value(v) for v in (start, end, rate, variation, debounce)]
                if not all(math.isfinite(v) for v in floats) or loop > 2 or direction not in (3, 4):
                    raise FormatError("unsupported Tricky animation parameters")
                # Native -1 lower bound means current time; Tricky -1 starts
                # the complete clip at zero. End bounds remain frames30.
                if floats[0] < 0:
                    start = 0
                rid = (source_to_instance[owner] << 8) | section
                params = [rid, loop, int(direction == 4), start, end, rate,
                          variation, 0xbf800000, random, 0]
                if kind == 258:
                    combo_start, combo_end, combo_rate, combo_mode = words[9:]
                    if float_value(combo_start) < 0:
                        resolved_end = model["animation_time"] if floats[1] < 0 else floats[1]
                        combo_start = struct.unpack("<I", struct.pack("<f", resolved_end))[0]
                    params += [combo_start, combo_end, combo_rate, combo_mode, 0]
                else:
                    params += [0]
                arguments = [(i, value, 2 if 3 <= i <= 7 or (kind == 258 and 10 <= i <= 12) else 1)
                             for i, value in enumerate(params)]
                commands.append((kind - 253, arguments))  # native builtin IDs 3/4/5
                animation_kinds[owner] = kind
                records[owner, node["offset"]] = kind
            elif main in (3, 9):
                command, value = words
                kind = animation_kinds.get(owner)
                message = (0x8c if command == 2 and kind == 257 else
                           0x82 if command == 3 and kind == 258 else None)
                receiver = receiver_kinds.get(owner)
                if receiver == 10 and 1 <= command <= 6:
                    message = (201, 200, 202, 203, 204, 205)[command - 1]
                elif receiver == 11 and 1 <= command <= 3:
                    message = 299 + command
                    if command == 1:
                        # Native event 300 takes phase-per-60Hz-tick; the
                        # source receiver command is frames per second.
                        value = struct.unpack("<I", struct.pack("<f", float_value(value) / 60))[0]
                if message is not None:
                    rid = (source_to_instance[owner] << 8) | section
                    commands.append((28, [(0, rid, 1), (1, message, 1), (2, value, 2)]))

    # Establish native receiver types before translating contact commands that
    # address another instance (the Elysium kicker trigger uses three targets).
    for source_channel, native_slot in ((0, 1), (1, 2)):
        for owner in instances:
            if owner in interactives.replacements:
                continue
            prop = collision["properties"][collision["instance_properties"][owner]]
            slot = prop["effect_slot"]
            if slot < 0:
                continue
            chain = slots[slot][source_channel]
            if chain >= 0:
                commands = []
                walk(chains[chain], owner, {("chain", owner, chain)}, commands)
                if any(builtin in (2, 3, 4, 5, 13, 21, 22, 28, 111, 112) for builtin, _ in commands):
                    roots[owner, native_slot] = commands
    owners = sorted({owner for owner, _ in roots})
    for owner in owners:
        binding = [0xffffffff] * 6
        for native_slot in (1, 2):
            calls = roots.get((owner, native_slot))
            if calls:
                binding[native_slot] = interactives.add_function(calls_blob(calls))
        binding = tuple(binding)
        if binding not in interactives.bindings:
            interactives.bindings.append(binding)
        interactives.object_bindings[owner] = (interactives.bindings.index(binding) << 8) | section
    return {"native_object_animations": sum(kind == 256 for kind in records.values()),
            "native_delta_animations": sum(kind == 257 for kind in records.values()),
            "native_combo_animations": sum(kind == 258 for kind in records.values()),
            "native_scripted_resets": len(resets),
            "source_reset_instances": sorted(resets),
            "native_mesh_break_animations": len(fragments),
            "source_mesh_anim_instances": sorted(fragments),
            "native_breakable_kills": len(hidden),
            "source_hard_hide_instances": sorted(hidden),
            "native_teleports": [{"source_instance": owner, "destination": destination}
                                 for owner, destination in sorted(teleports.items())],
            "native_object_script_owners": owners,
            "source_uv_scroll_instances": sorted(scrolls),
            "source_texture_flip_instances": sorted(flips),
            "source_animated_instances": sorted({owner for owner, _ in records})}
