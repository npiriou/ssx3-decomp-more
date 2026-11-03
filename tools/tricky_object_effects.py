"""Translate prefab animations and reset contacts to native SSX 3 scripts.

Curves live in the MDR. Luno's native focus-entry callback creates the process
when scenery enters the active area and recreates it after native focus cleanup.
"""

import math
import struct

from tricky_assets import FormatError
from ssx3_luno import calls_blob, LABEL, GATE, JUMP


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


def source_pickups(ssf, collision, instances):
    """Recognize visible pickup actors by their authored contact effect.

    Aloha even spells two model names `TrickB00st`. Display/model names are
    not the gameplay contract: Main17/18 grant speed/trick, Main14 a multiplier.
    """
    slots, chains, _ = read_logic(ssf)
    pickups = {}
    for owner in instances:
        prop = collision["properties"][collision["instance_properties"][owner]]
        slot = prop["effect_slot"]
        if slot < 0 or not prop["flags"] & 1:
            continue
        chain = slots[slot][1]
        if chain < 0:
            continue
        kinds = set()
        for node in chains[chain]:
            if node["main"] == 17:
                kinds.add("speed")
            elif node["main"] == 18:
                kinds.add("trick")
            elif node["main"] == 14:
                multiplier = struct.unpack("<f", struct.pack("<I", node["words"][0]))[0]
                if multiplier in (2, 3, 5):
                    kinds.add(f"score{int(multiplier)}")
        if len(kinds) > 1:
            raise FormatError("Tricky pickup combines incompatible native rewards")
        if kinds:
            pickups[owner] = kinds.pop()
    return pickups


def pack_object_scripts(ssf, pbd, models, collision, instances, source_to_instance,
                           interactives, section, mode):
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
    material_lifetimes = set()
    counters = {}
    rollers = set()
    pop_bursts = set()
    initial_debounce = set()
    receiver_kinds = {}
    tasks = {}
    task_ids = {}
    waits = set()
    invisible_tombstones = set()
    tombstones = set()
    rail_switches = set()
    predicates = set()
    scope_counter = 0

    # Mode setup runs before play in Tricky. Bake its unconditional rail
    # assignments into native initial properties, so restarting also has the
    # correct baseline. Do not run the rest of these setup graphs as scenery
    # focus callbacks: a later focus entry must not undo a player's switch.
    initial_rails = {}

    def setup_rails(nodes, seen):
        for node in nodes:
            main, words = node["main"], node["words"]
            if main in (4, 5):
                return False  # not a constant baseline beyond this point
            if main == 25:
                rail, enabled = words
                if rail >= len(collision["splines"]) or enabled not in (0, 1):
                    raise FormatError("invalid Tricky initial rail assignment")
                initial_rails[rail] = enabled
            elif main in (21, 26):
                function = words[0]
                key = ("function", function)
                if function < len(functions) and key not in seen:
                    setup_rails(functions[function]["nodes"], seen | {key})
            elif main == 7:
                chain = words[1]
                key = ("chain", chain)
                if chain < len(chains) and key not in seen:
                    if not setup_rails(chains[chain], seen | {key}):
                        return False
        return True

    entry = "ShowoffMode" if mode == "freestyle" else "RaceMode"
    for function in functions:
        if function["name"] == entry:
            setup_rails(function["nodes"], set())
    interactives.rail_initial = initial_rails

    def instance_rid(owner):
        return (source_to_instance[owner] << 8) | section

    def float_value(bits):
        return struct.unpack("<f", struct.pack("<I", bits))[0]

    def expand(nodes, owner, seen):
        """ActOn runs a target graph in the current thread/continuation."""
        nonlocal scope_counter
        scope = scope_counter
        scope_counter += 1
        result = []
        for node in nodes:
            if node["main"] == 7:
                target, chain = node["words"][:2]
                key = (target, chain)
                if target in selected and key not in seen and chain < len(chains):
                    result.extend(expand(chains[chain], target, seen | {key}))
            else:
                result.append((owner, dict(node, scope=scope)))
        result.append((owner, {"main": -1, "words": (), "offset": -1, "scope": scope}))
        return result

    # Pop actors consume contact with detached bursts followed by a hard
    # hide. They are not rigid obstacles. Recognize their authored graph,
    # rather than animal/model names. Other emitter families remain separate.
    popping = set()
    for owner in sorted(selected - set(interactives.replacements)):
        prop = collision["properties"][collision["instance_properties"][owner]]
        if prop["effect_slot"] < 0:
            continue
        chain = slots[prop["effect_slot"]][1]
        if chain < 0:
            continue
        nodes = [node for target, node in expand(chains[chain], owner, {(owner, chain)})
                 if target == owner]
        bursts = [node for node in nodes if node["main"] == 2]
        hard_hide = any(node["main"] == 0 and node["words"] == (5, 4) for node in nodes)
        if hard_hide and bursts and all(
                len(node["words"]) == 52 and node["words"][0] == 0
                and node["words"][50] == 18 and float_value(node["words"][3]) >= 0
                for node in bursts):
            popping.add(owner)

    def compile_task(items, root, native_slot):
        # Scope serials are local compiler labels, not runtime identity. A
        # canonical topology key lets loops across waits reuse their function.
        scopes = {}
        key = (root, native_slot, tuple((owner, node["offset"],
               scopes.setdefault(node["scope"], len(scopes))) for owner, node in items))
        if key not in task_ids:
            rid = interactives.reserve_function()
            task_ids[key] = rid
            calls = []
            # A wait resumes after the immediate graph stack has unwound.
            # Reserving first also permits authored loops across a wait.
            walk(items, root, native_slot, set(), calls)
            tasks[rid] = calls
        return task_ids[key]

    def walk(items, root, native_slot, active_functions, commands):
        thread_end = items[-1][1]["scope"]
        for index, (owner, node) in enumerate(items):
            main, words = node["main"], node["words"]
            if main == -1:
                commands.append((LABEL, node["scope"]))
            elif main == 5:
                if len(words) != 3 or words[0] not in (0, 1, 2, 3):
                    raise FormatError("invalid Tricky predicate mode")
                kind, operation, value = words
                if kind in (0, 1):
                    number = float_value(value)
                    if not math.isfinite(number) or number < 0 or (kind == 1 and number > 1):
                        raise FormatError("invalid Tricky predicate threshold")
                if kind == 0 and operation not in (0, 1):
                    raise FormatError("invalid Tricky speed comparison")
                # Human/no-node modes do not consume the trailing serialized
                # words. Retail Merqury even contains an out-of-range word in
                # its train gate: it is not a target instance reference.
                args = [(0, kind, 1), (1, operation if kind == 0 else 0, 1),
                        (2, value if kind in (0, 1) else 0, 2),
                        (3, instance_rid(owner), 1)]
                commands.append((GATE, (args, node["scope"])))
                predicates.add((owner, node["offset"], kind))
            elif main == 4:
                if len(words) != 1 or not math.isfinite(float_value(words[0])) or float_value(words[0]) < 0:
                    raise FormatError("invalid Tricky wait duration")
                tail = compile_task(items[index + 1:], root, native_slot)
                commands.append((115, [(0, tail, 1), (1, instance_rid(owner), 1),
                                       (2, words[0], 2), (3, instance_rid(root), 1),
                                       (4, native_slot, 1)]))
                waits.add((owner, node["offset"]))
                # The passing path waits. A failed inner gate can still
                # return to its caller and reach this remainder immediately,
                # so retain it behind a branch to this thread's scope end.
                commands.append((JUMP, thread_end))
            elif main in (21, 26):
                function = words[0]
                key = (owner, function)
                if key not in active_functions and function < len(functions):
                    child = expand(functions[function]["nodes"], owner, set())
                    # The new thread's immediate prefix runs now; its waits
                    # schedule only that child tail, and the caller continues.
                    if main == 26:
                        commands.append((117, [(0, instance_rid(owner), 1)]))
                    walk(child, root, native_slot, active_functions | {key}, commands)
                    if main == 26:
                        commands.append((118, []))
            elif owner in interactives.replacements:
                continue
            elif main == 2 and words[0] == 0 and owner in popping:
                if len(words) != 52 or not all(math.isfinite(float_value(v)) for v in words[3:50]):
                    raise FormatError("invalid Tricky pop emitter parameters")
                if words[1] > 4096 or words[2] > 64 or words[51] > 4:
                    raise FormatError("Tricky pop emitter exceeds native limits")
                if owner not in interactives.emitter_anchors:
                    interactives.emitter_anchors[owner] = (
                        len(instances) + len(interactives.posts) + len(interactives.emitter_anchors))
                anchor = (interactives.emitter_anchors[owner] << 8) | section
                params = list(words[1:])
                # Shared particle sprite numbers differ between the games:
                # Tricky18 is a white streak; SSX3's18 is an impact image.
                # SSX3's neutral white 'part'20 preserves the source RGBA
                # curves. All source launch/lifetime/count fields stay raw.
                params[49] = 20
                commands.append((25, [(i, value, 1 if i in (0, 1, 49, 50) else 2)
                                      for i, value in enumerate(params)] + [(54, anchor, 1)]))
                pop_bursts.add((owner, node["offset"]))
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
            elif main == 25:
                if len(words) != 2 or words[0] >= len(collision["splines"]) or words[1] not in (0, 1):
                    raise FormatError("invalid Tricky rail switch parameters")
                rail, enabled = words
                commands.append((119, [(0, (rail << 8) | section, 1), (1, enabled, 1)]))
                rail_switches.add(rail)
            elif main == 0 and words[0] == 0:
                if len(words) != 7 or not all(math.isfinite(float_value(v)) for v in words[1:]):
                    raise FormatError("invalid Tricky Roller parameters")
                prop = collision["properties"][collision["instance_properties"][owner]]
                if prop["collision_mode"] != 3 or prop["physics_index"] < 0:
                    raise FormatError("Tricky Roller requires its authored native sphere body")
                # Runtime resolves the target's own body before creating its
                # native ModObj/roller. Raw launch XYZ are source velocities,
                # not a normalized direction with an invented launch speed.
                commands.append((122, [(0, instance_rid(owner), 1)]
                                 + [(i, value, 2) for i, value in enumerate(words[1:], 1)]))
                rollers.add(owner)
            elif main == 0 and words[0] == 6:
                if len(words) != 3 or not 0 <= words[1] <= 32767:
                    raise FormatError("invalid Tricky counter parameters")
                # Native Counter owns the count, numbered latches and end
                # dispatch. Source word two is opaque, not a lifetime. A
                # zero source count must not fire on its first native update.
                rid = instance_rid(owner)
                commands.append((9, [(0, rid, 1),
                                     (1, words[1] if words[1] else 0xffffffff, 1)]))
                counters[owner] = (words[1], words[2])
                receiver_kinds[owner] = 6
            elif main == 0 and words[0] == 5 and words[1] == 4:
                # Tricky's hard breakable kill is native DeadNode mode zero.
                # Its constructor clears drawing/collision and the native
                # reset lifecycle restores the source static property flags.
                rid = (source_to_instance[owner] << 8) | section
                commands.append((2, [(0, rid, 1), (1, 0, 1)]))
                hidden.add(owner)
            elif main == 0 and words[0] == 5 and words[1] == 2:
                prop = collision["properties"][collision["instance_properties"][owner]]
                # An ordinary source tombstone removes the host's drawing and
                # player contacts until restart. Native DeadNode owns this
                # lifecycle for visible panes as well as invisible triggers.
                # Detached spline-copy ownership is a separate source node;
                # it must not be attached to this host's native dead actor.
                commands.append((2, [(0, instance_rid(owner), 1), (1, 0, 1)]))
                tombstones.add(owner)
                if not prop["flags"] & 1:
                    invisible_tombstones.add(owner)
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
                if native_slot == 1:
                    # Loading/briefing must not consume the source start
                    # guard before the native three-second countdown.
                    commands.append((123, [(0, rid, 1)]))
                    initial_debounce.add(owner)
            elif main == 0 and words[0] == 10:
                if len(words) != 7 or not all(math.isfinite(float_value(v)) for v in words[2:]):
                    raise FormatError("invalid Tricky UV scroll parameters")
                _, mode, du, dv, active, pause, lifetime = words
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
                commands.append((121, [(0, rid, 1), (1, 10, 1), (2, lifetime, 2)]))
                if float_value(lifetime) > 0:
                    material_lifetimes.add((owner, 10, float_value(lifetime)))
                scrolls.add(owner)
                receiver_kinds[owner] = 10
            elif main == 0 and words[0] == 11:
                if len(words) != 6 or not all(math.isfinite(float_value(v)) for v in words[3:5]):
                    raise FormatError("invalid Tricky texture flip parameters")
                _, start, direction, speed, lifetime, dwell = words
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
                commands.append((121, [(0, rid, 1), (1, 11, 1), (2, lifetime, 2)]))
                if float_value(lifetime) > 0:
                    material_lifetimes.add((owner, 11, float_value(lifetime)))
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
                if receiver == 6 and 1 <= command <= 3:
                    message = 499 + command  # native mark / ordered mark / decrement
                elif receiver == 10 and 1 <= command <= 6:
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
    for source_channel, native_slot in ((0, 1), (1, 2), (3, 3), (4, 4)):
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
                walk(expand(chains[chain], owner, {(owner, chain)}), owner,
                     native_slot, set(), commands)
                roots[owner, native_slot] = commands
    # Do not schedule loops consisting only of unimplemented sounds/emitters.
    # Keep every continuation which reaches a supported action, including
    # through other continuations; remove only code with no native consumer.
    meaningful = {1, 2, 3, 4, 5, 9, 13, 21, 22, 25, 28, 111, 112, 119, 122, 123}

    def action(call):
        builtin, args = call
        # A random condition consumes the native game RNG even while its
        # particle consumer is pending. Retain its waiting continuations too.
        return builtin in meaningful or (builtin == GATE and args[0][0][1] == 1)

    live_tasks = set()
    while True:
        discovered = {rid for rid, calls in tasks.items() if any(
            action(call) or (call[0] == 115 and call[1][0][1] in live_tasks)
            for call in calls)}
        if discovered == live_tasks:
            break
        live_tasks = discovered

    def supported(calls):
        return [call for call in calls if call[0] != 115 or call[1][0][1] in live_tasks]

    for rid, calls in tasks.items():
        interactives.define_function(rid, calls_blob(supported(calls)))
    roots = {key: supported(calls) for key, calls in roots.items()}
    # A populated leave/end slot, even an empty source graph, suppresses
    # native default teardown. Preserve that latch independently of whether
    # all its visual consumers are available yet (e.g. Pipedream fireworks).
    roots = {key: calls for key, calls in roots.items()
             if key[1] in (3, 4) or any(action(call) or call[0] == 115 for call in calls)}
    for (owner, native_slot), calls in roots.items():
        if native_slot in (3, 4):
            # Node-owned lifecycle callbacks have no contacting rider. The
            # retail script manager otherwise retains its default rider0.
            # Keep the restore after every graph-end label, and the busy
            # guard outside this scope so its early return cannot leak it.
            calls.insert(0, (117, [(0, instance_rid(owner), 1)]))
            calls.append((118, []))
        if any(builtin == 115 for builtin, _ in calls):
            calls.insert(0, (116, [(0, instance_rid(owner), 1), (1, native_slot, 1)]))
    owners = sorted({owner for owner, _ in roots})
    for owner in owners:
        binding = [0xffffffff] * 6
        for native_slot in (1, 2, 3, 4):
            calls = roots.get((owner, native_slot))
            if calls is not None:
                binding[native_slot] = interactives.add_function(calls_blob(calls))
        binding = tuple(binding)
        if binding not in interactives.bindings:
            interactives.bindings.append(binding)
        interactives.object_bindings[owner] = (interactives.bindings.index(binding) << 8) | section
    interactives.contact_only_instances = popping
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
            "source_finite_material_properties": sorted(material_lifetimes),
            "source_counter_configs": [[owner, *config] for owner, config in sorted(counters.items())],
            "source_roller_instances": sorted(rollers),
            "source_initial_debounce_instances": sorted(initial_debounce),
            "source_pop_burst_nodes": sorted(pop_bursts),
            "source_contact_only_instances": sorted(popping),
            "native_emitter_anchors": [[owner, rid] for owner, rid in interactives.emitter_anchors.items()],
            "source_leave_latches": sorted(owner for owner, slot in roots if slot == 3),
            "source_end_latches": sorted(owner for owner, slot in roots if slot == 4),
            "native_deferred_functions": len(live_tasks),
            "source_wait_nodes": sorted(waits),
            "source_invisible_tombstones": sorted(invisible_tombstones),
            "source_tombstones": sorted(tombstones),
            "source_predicate_nodes": sorted(predicates),
            "source_initial_rail_states": initial_rails,
            "source_scripted_rail_switches": sorted(rail_switches),
            "source_animated_instances": sorted({owner for owner, _ in records})}
