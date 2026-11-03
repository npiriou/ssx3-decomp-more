# Mode-entry visibility and reusable fragments

## Source state

LTG's Race/Showoff instance lists do not completely define visibility. The
source mode functions also hide scenery through ordinary ActOn/function graphs.
The existing importer omitted unconditionally hidden scenery only when no other
graph referenced it. That retained both objects used by later effects and
objects which were merely hidden again.

The importer now finds the closed set of graphs containing only waits,
Dead(2/4), ActOn and calls into other graphs in that same set. A hide-only
reference does not require an already-hidden instance to remain imported.
Predicates, teleports, animations, particles, sounds and unknown actions remain
conservative dependencies. This is structural graph analysis, not execution.

Snowdream Freestyle LCD/scanner1639/1640 are hidden at mode entry and their later
BreakLogo3001 actions only hard-hide them. They can be omitted. Its fragment
instance1641 is also hidden initially, but BreakLogo3001 invokes MeshAnim through
chain42, so it must remain available. Elysium Freestyle has56 such reusable
fragment instances. Their source HideRace actions all use Main0/Sub5 `[5,2]`;
their later linked-glass chains reach real MeshAnim actions. They cannot be
discarded as a hide-only cascade.

Those56 Elysium MeshAnim consumers are compiled in Race, not Freestyle. Their
absence from Freestyle was already true before this change. Snowdream1641 has
no compiled activation in either mode; its named source BreakLogo function
still makes it a conservative dependency. Retaining a resource does not imply
that its animation must run in every mode.

## Native ownership

The57 retained instances have no source focus graph. Their native focus-entry
slot1 now calls builtin2 with native mode3, constructing **RestoreNode(kind19)**.
Ordinary permanent DeadNode(kind6) would block their later activation:
WorldObjFactory_AttachModifier2fae38 returns early for a kind6 owner.

The relevant native contracts were followed through existing handwritten code:

- Factory2/2fc2c0 mode3 constructs RestoreNode350f60, with vtable491680 and
  flags `(flags & ~0x62) | 4`. Its static saved flags and geometry remain intact.
- RestoreNode's vtable differs from DeadNode491b00 only in destruction,
  serialization and kill/event slots. Their drawing slots are identical.
- FocusEnter30a3a0 calls the serialized slot1 only when no node exists. An
  already activated MeshAnim therefore does not get hidden by focus re-entry.
- FocusLeave30a460 preserves a kind6 automatically, but other types can enter
  default cleanup. A populated, detached no-op slot3 prevents that cleanup
  from restoring the hidden instance's static flags while it is out of focus.
- TypedProcess_IsType3607a0 compares the stored kind with the requested kind.
  RestoreNode19 passes AttachModifier's9/6/22 early checks, so a subsequent
  MeshAnim request follows the native replacement path. That path retains
  the old owner's matrices for constructor351b40 and disposes of it after
  capture. No hidden/visible flag rewrite or custom fragment simulation is used.

This realizes the source initial state on the first native focus entry. It
leaves the original MeshAnim descriptor and native replacement/lifetime code
in control of activation. No extra end callback or physics change is added.
The existing source cleanup/end behavior remains a separate runtime observation.

RestoreNode_ctor350f60 is retained as an uninstalled handwritten translation,
with empty OVERRIDES. The runtime uses the existing native factory/constructor;
no native module is newly installed by this change.

`source_initial_restore_instances` inventories the exact source owners.
Final read-only BAM inventory `.cache/tricky-mode-state-v50-inspection.json`
finds57 exact mode3 focus calls and57 detached leave latches, complete coverage
of the retained mode-hidden actors, and dense instance tables in both affected
archives. All56 Race fragment descriptors still match the source parameters;
the activation scope of all57 actors is unchanged. The only removed source
instances are Snowdream Freestyle1639/1640. All19 manifests retain their prior
initial rail switches, timer seed and force-owner lists. The19 final archives
are prepared by `.cache/prepare-tricky-initial-restore-v50-all.log`.

Actual initial appearance, activation, expiry, focus travel and restart remain
unobserved. No automated test, replay, gate, browser build or game/window
operation was performed.
