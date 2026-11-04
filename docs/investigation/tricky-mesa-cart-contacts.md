# Mesa cart transition and object contacts

## Authored transition

Source contact trigger770 uses chain176. It first installs Debounce10s, starts
chain177 on771, waits3s, then starts chain178 on907. Chain177 starts the
unlooped30fps animation and independently waits3s before tombstoning771.
Chain178 constructs a Roller with mass40, source fields0.002/1.5 and authored
velocity `[3500,-260,200]` cm/s. These are two different source instances:

| Source | Role | Collision |
| --- | --- | --- |
|771|Animated cart, model173|Mode0, intentionally no collider|
|907|Launched cart, model171|Mode3, authored sphere body|

The earlier ActOn thread correction is essential here: a child's Wait must not
delay its caller. Both3s waits run from the original trigger, rather than
launching907 after6s. The current Race/Freestyle BAMs each contain two3s deferred
jobs, one removing771 and one launching907 with the exact source parameters.
Read-only inventory: `.cache/tricky-cart-v49-inspection.json`. Script calls
behind scope-ending branches are also present in the serialized functions;
they are not evidence of additional same-frame execution.

No new cart speed, lifetime or collider is introduced by this investigation.

## Collision paths

Native SSX3 `RollerModifier_CollideWorld35edc8` constructs a temporary sphere
query from `self+e0`, calls `Nash_FindClosestContact336850` with cache`self+2c0`,
and subtracts the query radius from the reported depth. A positive penetration
moves the body by `(depth+2)*normal`; incoming contact velocity proceeds through
native ResolveContact35d4a0. This function consumes contact position/normal and
does not itself call a target instance's contact virtual or a world script.
That does not establish the behavior of every callee or other collision path.

The inspected native function is retained as
`custom_roller_collide_world.rs`, with explicit native continuations and empty
OVERRIDES. It is not installed and does not change the current binary/physics.
The handwritten translation was reviewed against generated EE; no compilation
or automated execution was performed for this uninstalled module.

Tricky Update13e8a8 calls its terrain response13eda8. A separate original
helper13f330 constructs the Roller's collision volume, intersects another
WorldObj through13aad0, checks its virtual+60 and conditionally calls its
virtual+98 with contact data before resolving the Roller's response. The
helper's presence alone does not establish its runtime scheduling: this pass
found neither a direct JAL/J reference to13f330 nor its absolute address in the
supplied ELF. The follow-up search also found no LUI+ADDIU/DADDIU/ORI sequence
forming that callback address in the next64 instructions. Do not install a
guessed per-frame overlap scan on that basis.
The source call path, target callback meaning and correspondence to each wooden
barrier still need to be established before importing prop-to-prop dispatch.

This is source/integration evidence, not a claim that Mesa's wall contacts,
cart travel, intermittent glass, or the reported rider bounce are resolved.
No game/window operation, automated test, replay, gate or browser build occurred.

## Follow-up source/current-resource inspection (v60)

The source Roller vtable36d790 selects13e8a8 at+10 and13f9f8 at+18.
The latter is a drawing path: it checks the instance's visible bit, queries
graphics visibility, builds matrices, then calls graphics1ce140/1ce310 and
200680. It does not establish a missing physics post-update loop. Source
helpers13e140/13e6a0 contain state/vector/quaternion arithmetic, rather than
the previously hypothesized primitive-candidate traversal. Source Update
still reaches13eda8 at13ed00. A fresh direct-call inventory again finds no
J/JAL caller of13f330 or13f5c8. That is not a universal proof of dead code,
but it supplies no scheduling contract for a new prop-overlap scan.

Source model173 has an animated part2 under parent1, mask63, with authored
channels spanning0..3s. Its raw local translation changes from approximately
[-1.20,-0.05,-1.46]cm at0 to[7046.78,591.22,-3100.30]cm at3s.
These are source part translations; the inventory does not execute the native
animation or claim a complete hierarchical world pose. They support retaining
the authored3s animation/physical-cart handoff rather than inventing a longer
wait or faster cart. The source physical cart907 remains at its distinct
authored instance position[72505.80,15840.83,-49889.23]cm.

All14 source `Mdl_HoleCoverWood` owners are present in both current prepared
Mesa BAMs. Their actual per-part contact flags are2: notifications retained,
bounce bit0 cleared. They belong to the39 previously identified unconditional
Mesa break-through owners. Their contact graphs are retained in the inventory.
This confirms that the user's earlier wooden-cover bounce report is already
addressed by the exported policy; it does not prove that a current physical
contact selects that property, breaks the cover or avoids every possible
obstacle response. No additional collision/physics change is justified by
these serialized observations alone.

Evidence: `.cache/cart-assets-v60-inspection.json`,
`.cache/inspect-cart-assets-v60.log`, `.cache/inspect-cart-dispatch-v60.log`
and `.cache/tricky-cart-*-v60.disasm.txt`. The source decoder labels EE
LQ/SQ/LQC2/SQC2 explicitly and leaves VU/MMI words raw, avoiding Capstone's
unrelated MIPS64 branch interpretations. No source/native body is executed.
No runtime code or asset changes are made in this pass; the v59 native build
and v56 prepared assets remain current. The actual handoff, wall passage and
source prop-dispatch correspondence still lack a current gameplay observation.
