# Imported rails: source data, spatial membership and contact evidence

The user's Elysium rail report and Alaska ice-ledge/pipe report remain open.
The observations below distinguish missing/corrupt data from an actual
native attachment attempt. They do not establish a gameplay fix.

## Current prepared archives (v59)

A read-only inventory reads the supplied Tricky ISO and all19 current v56
BAM archives directly. Across those variants it finds2886 spline resources
and10029 segments. Every serialized spline ID/bounds/count and segment's
length, cubic coefficients, links, parent, bounds, previous length and
source trailing word agree byte-for-byte with the source data.

The actual WorldScript rail words also agree with the importer policy:
source SSF flags/style and the manifest's recorded mode-entry overrides.
This comparison establishes the serialized policy, not execution of the
source mode-entry graphs. Counts include the same source rails in both
modes, where those modes exist.

| Variant | Spline resources | Active in serialized initial policy | Inactive |
| --- | ---: | ---: | ---: |
| Elysium Race |296|227|69|
| Elysium Freestyle |296|289|7|
| Alaska Race |84|43|41|
| Alaska Freestyle |84|84|0|

Alaska's six source ice rails41..46 retain source style5 -> native surface4.
All six have native WorldScript word40003 in both modes: surface4 and
eligibility3. None is disabled by the recorded initial-mode policy. This
does not prove their state at a later physical contact.

Evidence: `.cache/inspect_rail_archives_v59.py`,
`.cache/rail-archives-v59-inspection.json`,
`.cache/inspect-rail-archives-v59.log`. No game, VM or native rail query is
executed by this inventory. It does not rebuild or modify those archives.

## Existing RAM and analytic bounds

Four older saved snapshots contain all native segments in the Nash tree:
Alaska frames574/13455 contain213 primitive entries for84 rails; Elysium
frames1149/16030 contain442 for296 rails. Traversing each tree's eight
children and primitive lists finds every segment exactly once, with no
invalid pointer or duplicate membership. The snapshots contain1726 Alaska
cells and2837/2833 Elysium cells. Each listed segment's owner is its rail.

Those old Alaska samples predate the current mode-entry policy, and their
all-active84-rail state is not substituted for current Race's43 active
serialized assignments. None is a capture of the user's failed contact.

An analytic cubic-extrema inventory of all213 Alaska and442 Elysium source
segments finds only float-rounding-sized bounds excesses: at most
0.0126953125cm and0.01123046875cm respectively, for segment/parent bounds.
This does not support widening a rail's bounds, moving its curve or changing
the native snap/probe tolerance.

Native relocation3aa960 ignores non-sentinel serialized link indices and
reconstructs adjacent local segment pointers. Original global link indices
therefore do not become pointers into a different imported spline. Existing
typed/retained FindRail, ProbeRail and nearest-point functions remain
unchanged. The nearest-point refinement is a bounded interval search, not
a fixed sparse point cloud that would justify subdividing long source rails.

Evidence: `.cache/rail-spatial-v59-inspection.json` and
`.cache/rail-bounds-v59-inspection.json`, from their same-named inspectors.
These inspect saved data; neither executes a game or collision function.

## Passive contact observations (v59)

The earlier observer deduplicated by5m cell before checking candidate
membership. A distant sample could hide a later close approach in the same
cell; a later rail-policy change or entry into the real overlap list could
also remain hidden. Restarting the same course did not clear its budget.

The observer now distinguishes diagnostic distance bands(<25/50/100/300cm
and the remainder up to10m), current flags and actual overlap-list membership
within each existing5m cell. Restart clears the counters, region keys and
last-near records, and labels a new run. These bands change observation
deduplication only; no native acceptance threshold is modified. The existing
32-step sampled distance is approximate and is never an attachment result.

A read-only wrapper of native TryStartRailslide106848 calls its unchanged
generated body. On an ordinary return with restored SP it records the actual
return value and resulting motion state, without repeating FindRail or
installing the retained typed attach/probe implementations. The original
native0x140-byte frame's RailHit at its base is read only after success;
failure does not interpret uninitialized contact scratch. Native contact
point/kind/surface/descriptor and its raw first word are separate from the
last sampled rail. The latter includes its observation age and is accepted
only up to6 VSync ticks old; failure records require its sampled distance
below100cm. An unwound call can have no return record; absence is not a
hang/failure verdict.

The existing human-only observer remains capped at1024 distinct approaches
per course/run, sampled every6 updates. Native attempt observations have
their own512-key budget. Files remain
`.cache/diagnostics/rails-<pid>-<stamp>.log`; no special launcher, replay,
extra query, altered registers/cycles, game-memory write or window operation
is introduced. No current manual contact has yet been observed with this
version. Native compilation succeeds in1m24s in
`.cache/build-tricky-rail-approach-v59-final.log`. The earlier v59 build
predates the final observation wrapper and is not the current binary.
No automated tests, replay gates or browser build are run.

## Source board-contact volume (v61)

The previous inventory established that resources existed, not that their
contact volume matched Tricky. A further read-only traversal of all four
saved spatial trees now checks each segment's bounds against every ancestor
cell, using the actual native0.2-cell margins and X/Y/Z octant ordering.
All213 Alaska and442 Elysium segments fit their complete ancestry in both
snapshots. Evidence: `.cache/rail-cells-v61-inspection.json`. This supplies
no justification for moving curves or expanding their spatial bounds.

The source rider's rail-entry routine is125cb8..126250. It queries the
rail using the board matrix at rider+4a60, then tests the closest point
in that matrix's oriented box. At125dd0..125e28 it computes
`delta = hit - board_origin - 30 * board_Y`. Thus the box center is
`board_origin + 30 * board_Y`, not minus30. Its final contracted half-extents
at125ef0..125fcc are:

- forward: `0.9 * (150 * blend + 80 * (1-blend))`cm;
- board normal: `0.9 * 50`cm;
- across the board: `0.9 * (50 * blend + 30 * (1-blend))`cm.

Native SSX3 ProbeRail1086b8 instead uses an unshifted forward capsule with
radius30..50cm and its native axial interval. The volumes are different;
at blend1, Tricky's normal interval is[-15,+75]cm relative to the board,
whereas the native capsule reaches50cm in that direction. Retaining only
the native capsule discards source-supported entry positions. The source
routine, its selected axes, dimensions, shift sign and transition to its
railslide state are retained in `.cache/tricky-rail-attach-v61.disasm.txt`.

`custom_tricky_rail_probe` wraps the unchanged native ProbeRail. After a
native miss at FindRail's attach call108c10, it accepts an already-selected
plain-spline contact inside that source box. It requires an active imported
section, matching spline RID, active rail flags and valid board pose. No
additional search, relocated curve, changed broad-phase radius, altered
retail contact or forced motion state is added. The native state/task/input
guards, candidate, tangent, stance, speed and actual Railslide entry remain
in control. The source-box adapter is a compatibility policy for native
contacts; it is not a bit-exact replacement of Tricky's whole rail query.

The inspected Cruise131620 and NaturalAir12f730 callers are retained as
uninstalled Rust translations with empty override lists. Neither has an
imported-course/ice-surface gate around attachment. Cruise prioritizes
finish/reset/airborne transitions and the handplant input branch;
NaturalAir prioritizes reset, active-tweak transitions and successful
handplants. Installing those callers would not address the volume mismatch.

Both generated dispatch forms include the new1086b8 slot. The final native
build succeeds in1m33s in `.cache/build-tricky-rail-contact-v61-final.log`;
the first build failed on Rust mutability signatures and is superseded.
No assets/importer changed: the19 v56 archives remain current. This is an
installed contact correction, not manual confirmation of Elysium/Alaska's
reported rails. No automated test, replay, gate, browser build or game/window
operation is performed.
