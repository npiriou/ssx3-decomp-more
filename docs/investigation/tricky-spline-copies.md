# Detached spline copies: chairlifts and subway

## Source contract

Tricky Main2/Sub1 is a spline-copy process, not a particle emitter. The factory
at `0x13d27c` allocates a separate process and calls `0x1fa108`. Its prototype
keeps its existing node, normally the Debounce created immediately before it.
The constructor hides the prototype's static/dynamic drawing bits at
`0x1fa440..0x1fa45c`; it does not replace that node with the spline process.

The supplied records all have EndMode1 (wrap) and Orientation1 (horizontal
heading without pitch). Snowdream has three prototypes,93/939/2008, with15
copies each on spline292/222/55. Each record uses speed10, yaw0, route-line
enabled and colour vector `[1,0.1,0.1,0.1]`. Merqury prototype344 has two entry
graphs with identical settings: spline38, one copy, speed35, yaw1.62 radians,
route line disabled and a zero colour vector. Both Race/Freestyle use these
settings. Several chairlift pylons can address the same prototype.

`0x1fa108` stores spacing as pathLength/count. It converts speed to a step with
`speed*100/60`: source speed is metres/second. Update `0x1fa6a0` advances and
wraps the distance. Orientation helper `0x1fa8d8` computes horizontal heading
`yaw + pi/2 - atan2(tangentY,tangentX)` for Orientation1, with zero pitch/roll.
Source EndMode2/3 and other orientation settings are not used by these worlds
and are not silently mapped to a loop.

All four prototypes have collision mode0/no collider. Snowdream939/2008 are
initially visible prototypes;93 and the subway prototype are initially hidden.
The spline process draws its copies independently of that initial visibility.

## Native mapping

Native factory20 `0x2fe0c0` requires a ModObj-compatible node. A Debounce does
not satisfy that contract. Each prototype therefore gets a separate initially
invisible/collision-free native host with the complete original MDR and instance
lighting. Adapter131 creates an owned native Object through factory0, enables
its drawing, then forwards the native MultiSpline descriptor to factory20.
The authored prototype's Debounce/no-node guard remains intact. A host already
owning a node cannot acquire a second set of copies from another pylon.

| Native parameter | Mapping |
| --- | --- |
| 0 | Dedicated host RID |
| 1 | Authored WorldSpline RID in the imported section |
| 2 | Mode2: horizontal heading only |
| 3 | Source speed multiplied by3.6 |
| 4 | `90 + degrees(sourceYaw)` |
| 5 | Initial distance0 |
| 6..9 | Four original route-colour values, unchanged |
| 10 | Original route-line flag |
| 11 | Original copy count15 or1 |

Native SetSpeed `0x35a550` multiplies km/h by27.77777862548828 to obtain cm/s.
This constant is present in the native ELF at `gp-0x2a28` (`0x4a06c8`) and in
the saved native RAM. Thus chairlift input is36km/h, subway input126km/h;
forwarding10/35 directly would slow them by3.6. Native constructor converts
the yaw parameter from degrees to radians. Its extra yaw matrix uses the Z
axis at `0x4ff160`, observed as `[0,0,1,0]` in saved Tokyo RAM.

Native MultiSpline owns path evaluation, equal spacing, looping, per-instance
transforms, culling, route-line drawing, instance allocation and cleanup. No
host-side path integrator or speed tuning is added. Each native update uses
elapsed seconds, while the source update uses one1/60 step.

Adapter-only parameter12 is the prototype RID. The adapter canonicalizes the
twelve factory fields in a private0x100-byte caller frame and never forwards
parameter12 into the factory's opaque tail. Both Object and MultiSpline native
calls retain this frame across suspension and return through the ordinary VM
continuation. Restart clears abandoned pending frames.

After construction the adapter verifies the installed transform at
`*(*(node+0x1c))` against MultiSpline's vtable `0x48f168`. Only then does it
clear drawing bits2/4 on the prototype, matching the source constructor. A
failed installation restores the hidden host's original flags. The native
setter's V0 is the updated instance flags, not the transform pointer.

Hosts share a dense RID allocator with both emitter-host families. Their
serialized properties start with visibility0, collision0, surface-1, no
contact flags or callback binding. Native Object owns runtime visibility;
the original source instance, collision properties and script bindings remain
separate. Focus, cleanup/re-entry, appearance and restart need ordinary play
observations; source-process/native-focus lifetime equivalence is not proven
by the serialized records.

## Retained ports and evidence

The exact native factory20, AddMultiSpline, two constructors (including the
stream constructor), CloneInstances, UpdateNodes and SetTransformModifier are
retained uninstalled in separate Rust files with empty override lists. They
were read statically; no tests were added or run. Clone0 preserves its allocated
RID while copying the complete template; other clones use CopyInstance and
the native flag masks. The count is validated before native construction,
whose first-clone path otherwise assumes count is positive.

Ignored source disassembly is in `.cache/tricky-spline-node-*.disasm.txt`.
Compilation/resource inventories are recorded in the implementation plan.
They establish available code/data, not observed motion or lifecycle behavior.
No automated test, replay, gate, browser build, game launch or window operation
was performed.
