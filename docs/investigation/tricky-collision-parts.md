# Split prefab collision meshes

## Native traversal and the lost faces

The retained `custom_collide_volume_object.rs` translation of native
`Collide_VolumeObject`334888 establishes the association:

- S5 iterates MDR parts, bounded by model+4; each part occupies16bytes.
- A null geometry pointer skips the part without consuming a collider.
- A non-null geometry pointer selects the next collision mesh through S6.
- The part's geometry bounds reject distant queries before its faces are read.
- Both an AABB miss and a completed mesh query increment S6 at334f4c.
- Per-part surface/contact data uses the MDR part index, not the collision count.

The SSF reader retains source32-bit triangle indices. Native type1 collision
meshes use byte indices, so `pack_collision` splits a source mesh when the
next triangle would exceed256 distinct vertices. Previously this increased
the collision resource count and the WorldScript property count, but not
the MDR part count. A one-part model therefore visited only its first chunk.
The remaining faces were serialized and resident but never queried.

Exact vertex-identity inventory ruled out lossless welding as a solution:
each affected source mesh really has more than256 distinct vertex positions.
No rounding, simplification, invented collision volume or index truncation is
used.

## Resource correction (v63)

All24 affected supplied prefabs have one static root, one drawable geometry
part and one source collision mesh. Every instance of each prefab uses the
same compatible collision layout. The native resource now appends one sibling
part with the same parent, local matrix and bounds as the source root. Its
geometry header is non-null, its draw-group count is zero, and it has no
animation. Native collision consumes the second mesh using the same original
transform; the existing native model renderer skips the draw-free part.
The source visible groups, materials, DMA chains and instance lighting are
retained. Existing WorldScript allocation already reserves both part records.

The importer derives this mapping from real collider/model bindings. It
rejects incompatible shared bindings and multi-part/animated split layouts
instead of silently assigning a chunk to the wrong transform. There are no
such unsupported layouts in the supplied course data. Source inventories also
find matching original geometry/body counts for every collision-enabled
mode1/mode3 instance across all11 worlds; the mismatch was introduced by the
byte-index splitting.

Actual prepared resource inventory:

| World | Affected models | Instances per mode | Previously unqueried faces per mode |
| --- | ---: | ---: | ---: |
| Garibaldi |5|13|1072|
| Snowdream |1|4|32|
| Elysium |4|10|972|
| Mesa |6|17|892|
| Merqury |2|3|400|
| Aloha |4|8|612|
| Alaska |1|1|76|
| Tutorial |1|4|40|

Tutorial has one prepared mode; the other affected worlds have two. Across
the19 prepared variants this restores native traversal of8152 face instances
on116 object instances. Tokyo, Untracked and Pipedream have no affected
prefabs. This correction therefore does not explain Tokyo's intermittent
glass/camera problems, and it is not evidence that the separately corrected
Elysium/Alaska grind attachment is accepted in play.

Evidence stays in ignored derived data:
`.cache/collision-vertex-identity-v63-inspection.json`,
`.cache/collision-model-bindings-v63-inspection.json`,
`.cache/collision-source-parts-v63-inspection.json` and
`.cache/collision-parts-v63-actual-resources.json`.
All19 archives were rebuilt successfully in
`.cache/prepare-tricky-collision-parts-v63-all.log`, retaining the existing
11 sound banks and7 movie files. No Rust runtime changed, so no native rebuild
is needed. No automated tests, replays or game/window operations were used.
Current gameplay acceptance remains unobserved.
