# Scripted reactivation of a resting Roller

This corrects a source property retrigger, not the accepted impact/inertia law.
The Mesa cart's travel and prop-to-prop wall dispatch remain separate open
issues. No game/window operation or automated test/replay accompanies this pass.

## Source state transition

Tricky's Roller ctor13d6c0 installs vtable36d790. Relevant virtuals are:

| Slot | Entry | Effect |
| --- | --- | --- |
|60|149e28|Read paused flag at self+140|
|68|149e18|Set self+140 to1|
|70|149e10|Clear self+140|
|b0|13e860|Run the end callback when applicable, otherwise invoke slot68|

Property dispatch13c634..13c658 checks an existing paused node's kind against
the requested property kind. For the same kind it calls slot70 and returns.
An already active same-kind node is left alone. A retrigger therefore does
not reconstruct the Roller, reread its initial shape, reset its mass/tensor,
or reapply the authored launch vector.

Source update13e8a8 checks the paused flag before simulation. Its stop path
resets elapsed time at+e4 (13ea00), zeros the moving state and passes through
13e860. Where no end graph applies, this pauses the body at its current pose.
Clearing the pause resumes it with that reset elapsed time and its retained
state, rather than launching a new copy.

Mesa gives a concrete scripted target: trigger770/contact chain176 installs
Debounce10s and, after its independent3s wait, invokes Roller chain178 on907.
907 has no effect slot/end binding. Its initial parameters remain mass40,
0.002/1.5 and velocity[3500,-260,200]cm/s. A later trigger can request the same
retained body without a direct collision against907. Read-only source inventory:
`.cache/tricky-roller-retrigger-v54-inspection.json`.

## Native contact and imported property paths

Native `ModObj_v40`355770 forwards physical contact to the primary modifier's
slot50 before checking the world-script cooldown. Roller vtable48f080 resolves
that slot to `RollerModifier_v10`361cd8. It clears the native timer at+20, then
calls InitBody35dde8. Direct collisions already have a wake path.

The imported property adapter had returned immediately for every registered
live body. That skips native v10 for a script targeting a different object,
leaving a resting body at the native pause sentinel11. The imported update
guard intentionally retains that pose instead of allowing the retail
boulder's later16s disposal, so the stale timer prevented reactivation.

For the same registered owner/instance/node/primary Roller, builtin122 now
clears timer+20 only when it is at least11. It keeps the existing rigid body,
pose, momentum, activity, tensor and source parameters. It does not invoke
InitBody or explicit_launch again. Active bodies and direct native contacts
retain their prior path. This maps the source's cleared pause and already
reset elapsed time onto the native modifier's combined timer/state field.

The live-body lookup now validates the native Roller vtable and RAM
range, as well as ModObj kind/backlink and registered owner identity. A
reused modifier slot must not expose another modifier's+20 as a Roller timer.
New construction still uses the existing native factory and source tensor
setup. Only new construction resolves the original sphere resource; an
existing native body retains its copied sphere tree.

`custom_roller_v10.rs` retains the studied native leaf as uninstalled Rust
with empty OVERRIDES. It preserves the8-cycle body, frame and native return
continuation. It is not a registered module and its equivalence has not been
verified by execution.

Native build: `.cache/build-tricky-roller-retrigger-v54-final.log`.
No importer/assets changed: the19 complete v53 course archives and11 audio
banks remain current. Actual reactivation, repeated contacts, streaming and
Mesa's wall interactions remain unobserved in this wave; this is not a
whole-course completion claim.
