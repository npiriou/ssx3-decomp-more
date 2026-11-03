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
