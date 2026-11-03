"""Inventory disc-authored Tricky mechanics against the prepared native import.

Read-only analysis: no game run, asset rebuild, test or replay. Derived instance
names, links and counts go to an ignored JSON report. MainType/SubType names
follow SSX-Library's TrickyEnums; source records remain the evidence.
"""

from __future__ import annotations

import argparse
from collections import Counter
import json
import os
from pathlib import Path
import struct

from ssx3_interactives import map_names
from tricky_assets import (FormatError, cofb_index, parse_aip, parse_ltg,
                           parse_pbd, read_cofb_member, read_iso_file)
from tricky_collision import parse_ssf
from tricky_courses import COURSES


PROPERTY_TYPES = {
    0: "roller_response", 7: "directional_push", 10: "uv_scroll",
    11: "texture_flip", 12: "fence_flex", 13: "flag_wind",
    14: "cracked_glass", 15: "lap_lift", 18: "vertical_lift",
    20: "mesh_break_animation", 24: "tube_exit",
    256: "object_animation", 257: "delta_animation", 258: "combo_animation",
}
PUSHES = {"directional_push", "lap_lift", "vertical_lift", "tube_exit"}
VISUAL = {"uv_scroll", "texture_flip", "fence_flex", "flag_wind", "particles"}


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


def mechanic(node: dict) -> str | None:
    main, sub, words = node["main"], node["sub"], node["words"]
    if main == 0:
        if sub == 5 and words[1] == 4:
            return "breakable_hide"
        return PROPERTY_TYPES.get(sub)
    if main == 2:
        return "spline_mover" if sub == 1 else "particles"
    return {13: "scripted_reset", 16: "time_pickup", 24: "teleport",
            25: "rail_switch"}.get(main)


def audit(course, iso: Path, overlay: Path) -> dict:
    archive = read_iso_file(iso, course.archive)
    stem = course.code.lower()
    get = lambda ext: read_cofb_member(archive, f"data/models/{stem}.{ext}")
    pbd = parse_pbd(get("pbd"), True)
    ssf = get("ssf")
    collision = parse_ssf(ssf)
    slots, chains, functions = read_logic(ssf)
    names = map_names(get("map"))
    spatial = parse_ltg(get("ltg"), pbd["counts"], True)
    mode_instances = {
        mode: {i for node in spatial["nodes"]
               for i in node["race_instances" if mode == "race" else "showoff_instances"]}
        for mode in course.modes
    }
    native = {}
    for mode in course.modes:
        path = overlay / f"DATA/WORLDS/TRICKY/{course.code}-{mode}.json"
        if path.exists():
            native[mode] = json.loads(path.read_text())["world"]
    replacement_ids = {mode: {item["source_instance"] for item in report["native_replacements"]}
                       for mode, report in native.items()}
    boost_ids = {mode: set(report["source_boost_instances"]) for mode, report in native.items()}

    # ActOnInstance names an effect header on another instance, not a slot.
    # Collision roots alone miss sewer gates, falling trees and wall fragments.
    def walk(nodes, target, seen):
        for node in nodes:
            yield target, node
            main, words = node["main"], node["words"]
            if main == 7:
                other, header = words[:2]
                key = ("header", other, header)
                if key not in seen and other < len(pbd["instances"]) and header < len(chains):
                    yield from walk(chains[header], other, seen | {key})
            elif main in (21, 26):
                index = words[0]
                key = ("function", target, index)
                if key not in seen and index < len(functions):
                    yield from walk(functions[index]["nodes"], target, seen | {key})

    entries = {}
    for owner in sorted(set().union(*mode_instances.values())):
        prop = collision["properties"][collision["instance_properties"][owner]]
        slot = prop["effect_slot"]
        if slot < 0:
            continue
        for channel, header in enumerate(slots[slot]):
            if header < 0:
                continue
            for target, node in walk(chains[header], owner, {("header", owner, header)}):
                kind = mechanic(node)
                if kind is None:
                    continue
                for mode, selected in mode_instances.items():
                    if owner not in selected:
                        continue
                    manifest = native.get(mode)
                    replacements = replacement_ids.get(mode, set())
                    if owner in replacements or target in replacements:
                        status = "native_replacement"
                    elif manifest and kind in PUSHES and target in boost_ids[mode]:
                        status = "native_volume"
                    elif manifest is None:
                        status = "unprepared"
                    elif kind == "roller_response":
                        status = "source_node_missing_native_contact_not_assessed"
                    elif kind in VISUAL:
                        status = "visual_effect_missing"
                    else:
                        status = "source_mechanic_missing"
                    key = mode, target, kind, node["offset"]
                    entry = entries.setdefault(key, {
                        "mode": mode, "instance": target, "name": names.get(target, ""),
                        "mechanic": kind, "status": status, "links": [],
                    })
                    link = {"owner": owner, "name": names.get(owner, ""),
                            "slot_channel": channel, "header": header}
                    if link not in entry["links"]:
                        entry["links"].append(link)
                    if kind == "teleport":
                        entry["destination"] = {"instance": node["words"][0],
                                                "name": names.get(node["words"][0], "")}
                    if kind == "rail_switch":
                        rail, command = node["words"][:2]
                        entry["rail_switch"] = {"rail": rail, "command": command,
                                                "source": collision["splines"][rail]}

    source_paths = parse_aip(get("aip"), True)
    sop_gates = []
    if f"data/models/{stem}.sop" in cofb_index(archive):
        sop = parse_aip(get("sop"), True)
        for path_id, path in enumerate(sop["race_paths"]):
            for event in path["events"]:
                if event["type"] == 11 and event["value"] > 0:
                    sop_gates.append({"path": path_id, "seconds": event["value"],
                                      "distance_to_finish": path["distance_to_finish"] - event["start"]})
    # Alternate paths can award different seconds at the same station.
    groups = []
    for gate in sorted(sop_gates, key=lambda g: g["distance_to_finish"]):
        if not groups or abs(gate["distance_to_finish"] - groups[-1][0]["distance_to_finish"]) > 200:
            groups.append([])
        groups[-1].append(gate)
    counts = Counter((entry["mode"], entry["mechanic"], entry["status"]) for entry in entries.values())
    return {"code": course.code, "name": course.name,
            "race_pass_events": [event for path in source_paths["race_paths"]
                                 for event in path["events"] if event["type"] == 12],
            "showoff_time_gate_groups": groups,
            "showoff_gate_import": "not implemented" if groups and "freestyle" in course.modes else "not applicable",
            "summary": [{"mode": mode, "mechanic": kind, "status": status, "nodes": count}
                        for (mode, kind, status), count in sorted(counts.items())],
            "instances": list(entries.values())}


def main() -> None:
    root = Path(__file__).resolve().parent.parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tricky-iso", type=Path, default=Path(os.environ.get(
        "SSX_TRICKY_ISO", root.parent / "SSX Tricky (USA).iso")))
    parser.add_argument("--overlay", type=Path, default=root / ".cache/overlay")
    parser.add_argument("--output", type=Path, default=root / ".cache/tricky-mechanics-audit.json")
    args = parser.parse_args()
    reports = []
    for course in COURSES:
        report = audit(course, args.tricky_iso, args.overlay)
        reports.append(report)
        missing = {(entry["instance"], entry["mechanic"]) for entry in report["instances"]
                   if entry["status"] == "source_mechanic_missing"}
        print(f"{course.name}: {len(missing)} object/mechanic pairs absent; "
              f"{len(report['showoff_time_gate_groups'])} Showoff gate stations", flush=True)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps({"method": "static source/import inspection, no play verification",
                                      "courses": reports}, indent=2), encoding="utf-8")
    print(args.output)


if __name__ == "__main__":
    main()
