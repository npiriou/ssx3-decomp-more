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
from tricky_object_effects import read_logic
from tricky_courses import COURSES


PROPERTY_TYPES = {
    0: "roller_response", 6: "counter", 7: "directional_push", 10: "uv_scroll",
    11: "texture_flip", 12: "fence_flex", 13: "flag_wind",
    14: "cracked_glass", 15: "lap_lift", 18: "vertical_lift",
    20: "mesh_break_animation", 24: "tube_exit",
    256: "object_animation", 257: "delta_animation", 258: "combo_animation",
}
PUSHES = {"directional_push", "lap_lift", "vertical_lift", "tube_exit"}
VISUAL = {"uv_scroll", "texture_flip", "fence_flex", "flag_wind", "particles"}


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
            # The authored mode-entry tombstones further restrict LTG's
            # scenery list. Their removed contact/focus roots cannot run.
            mode_instances[mode] -= set(native[mode].get("source_mode_hidden_instances", []))
    replacement_ids = {mode: {item["source_instance"] for item in report["native_replacements"]}
                       for mode, report in native.items()}
    boost_ids = {mode: set(report["source_boost_instances"]) for mode, report in native.items()}
    animated_ids = {mode: set(report.get("source_animated_instances", [])) for mode, report in native.items()}
    reset_ids = {mode: set(report.get("source_reset_instances", [])) for mode, report in native.items()}
    fragment_ids = {mode: set(report.get("source_mesh_anim_instances", [])) for mode, report in native.items()}
    hidden_ids = {mode: set(report.get("source_hard_hide_instances", [])) for mode, report in native.items()}
    teleport_ids = {mode: {item["source_instance"] for item in report.get("native_teleports", [])}
                    for mode, report in native.items()}
    scroll_ids = {mode: set(report.get("source_uv_scroll_instances", [])) for mode, report in native.items()}
    flip_ids = {mode: set(report.get("source_texture_flip_instances", [])) for mode, report in native.items()}
    rail_ids = {mode: set(report.get("source_scripted_rail_switches", []))
                | {int(rail) for rail in report.get("source_initial_rail_states", {})}
                for mode, report in native.items()}
    counter_ids = {mode: {row[0] for row in report.get("source_counter_configs", [])}
                   for mode, report in native.items()}
    roller_ids = {mode: set(report.get("source_roller_instances", [])) for mode, report in native.items()}
    pop_nodes = {mode: {tuple(row) for row in report.get("source_pop_burst_nodes", [])}
                 for mode, report in native.items()}

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
                    elif kind == "scripted_reset" and target in reset_ids.get(mode, set()):
                        status = "native_contact_script"
                    elif kind in ("object_animation", "delta_animation", "combo_animation") and target in animated_ids.get(mode, set()):
                        status = "native_curve_script"
                    elif kind == "mesh_break_animation" and target in fragment_ids.get(mode, set()):
                        status = "native_fragment_script"
                    elif kind == "breakable_hide" and target in hidden_ids.get(mode, set()):
                        status = "native_dead_node_script"
                    elif kind == "teleport" and target in teleport_ids.get(mode, set()):
                        status = "native_placement_script"
                    elif kind == "uv_scroll" and target in scroll_ids.get(mode, set()):
                        status = "native_material_script"
                    elif kind == "texture_flip" and target in flip_ids.get(mode, set()):
                        status = "native_material_script"
                    elif kind == "rail_switch" and node["words"][0] in rail_ids.get(mode, set()):
                        status = "native_rail_state_script"
                    elif kind == "counter" and target in counter_ids.get(mode, set()):
                        status = "native_counter_script"
                    elif kind == "roller_response" and target in roller_ids.get(mode, set()):
                        status = "native_rigid_body_script"
                    elif kind == "particles" and (target, node["offset"]) in pop_nodes.get(mode, set()):
                        status = "native_particle_script"
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
    prepared_showoff = native.get("freestyle", {})
    gate_import = ("native_SOP_events" if prepared_showoff.get("source_paths") == "SOP"
                   and prepared_showoff.get("showoff_hundredths") is not None else "not implemented")
    return {"code": course.code, "name": course.name,
            "race_pass_events": [event for path in source_paths["race_paths"]
                                 for event in path["events"] if event["type"] == 12],
            "showoff_time_gate_groups": groups,
            "showoff_gate_import": gate_import if groups and "freestyle" in course.modes else "not applicable",
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
                   if entry["status"] in ("source_mechanic_missing", "visual_effect_missing",
                       "source_node_missing_native_contact_not_assessed")}
        print(f"{course.name}: {len(missing)} object/mechanic pairs without an imported consumer; "
              f"{len(report['showoff_time_gate_groups'])} Showoff gate stations", flush=True)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps({"method": "static source/import inspection, no play verification",
                                      "courses": reports}, indent=2), encoding="utf-8")
    print(args.output)


if __name__ == "__main__":
    main()
