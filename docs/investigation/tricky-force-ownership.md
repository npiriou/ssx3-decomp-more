# Shared force ownership and Alaska fireworks

## Original behavior

Alaska794 is an invisible mode2 trigger, surface-1, with contact chain102.
Its first node is Main0/Sub7, mode1, duration0, rate4, target45m/s and direction
`[0.6,0,0.8]`. Three ActOn children then start independent emitters on
798/983/797. Each child contains one Main2/Sub0 descriptor followed by sound82;
none has a Wait or recursive continuation.

Original dispatch13c99c constructs receiver140498, attaches it to the instance
and leaves its contact slot as the inherited no-op13b7b0. Further contacts
therefore do not recreate the children. Update140688 gathers nearby riders,
constructs a temporary rider collision volume through257810, then calls
WorldObj_Intersect13aad0/25bf48. Mode1/duration0 remains alive if **any rider**
produces positive penetration, and kills/restores when none does. Ownership
is shared by the volume, rather than a separate cooldown for each rider.

The model199 trigger is a single untransformed part with a model-local box.
Its instance basis rotates that box, including a30-degree tilt. A point-in-
world-AABB check is not equivalent to its collision hull intersection.

## Imported lifetime

The force remains applied by the existing TFX2 adapter. This change restores
the invisible native instance and its contact graph; it adds no second force
calculation or velocity write. It supports the supplied direct contact graph
whose first node is a mode1/zero-duration force, followed by other actions,
with one mode2 model part and signed surface-1. Other force modes are not
silently treated as this lifetime.

The existing `(root RID, callback slot)` deferred/busy scope represents the
receiver's ownership. Before the three emitter children, the first contact
schedules a detached monitor for the following script update. The compiler
adds its usual builtin116 guard to the contact root. While the monitor is
owned, subsequent contacts return without repeating the children.

The monitor calls builtin132 with the native volume RID. If any active rider
still penetrates it, builtin115 schedules the same monitor for the next update
with delay0. Its new busy reference is added before the current reference is
released. If no rider intersects, it schedules nothing and normal queue finish
releases the last reference. Delay0 is the queue's next-update epoch rule,
not a wall-clock cooldown or a guessed grace period. The existing scheduler
executes one native collision query per owned script update.

All three imported child emitters remain independent native particles, using
their authored descriptors/images and matrices. Sound82 remains part of the
separate pending audio mapping; importing its particles does not prove that
the original fireworks sound plays.

## Native collision query

Builtin132 enumerates the six native AI rider slots at World+84 ->AI+c ->28,
excluding null/out riders by the same878 field used in Rider_CheckRiderCollisions.
For each rider it borrows the current sphere tree at rider+aa0 and follows the
native Rider_HandleWallCollision105398 pattern:

1. CollHull_ctor32f650(hull, riderSphereTree,1).
2. Collide_VolumeObject334888(hull, instance, contacts,64,1).
3. Accept positive native contact depth at record+40.
4. CollHull_dtor32f708(hull,2), including after a positive result.

Query mode1 includes signed surface-1. Native collision code owns model/part
transforms, box clipping and rider geometry; no rider radius or position
approximation is substituted. The first positive rider ends the scan, while
the final exit can require scanning all active riders. Queries do not dispatch
the trigger's contact script or apply a collision response.

A private0x2400-byte caller frame reserves0x400 bytes for the Hull and all64
native0x80-byte contacts. The ordinary native wall caller reserves at least
0x370 for its Hull; a small0x80/0x100 temporary is insufficient for the embedded
sphere tree used during transformed queries. All three guest-call phases
survive suspension and retain that frame until the ordinary VM return.
Restart clears abandoned pending frames and the existing deferred/busy queue.

Both Hull constructor/destructor were already hand-written and installed in
game/intersect/riderspheretree.rs. Their contracts were read without adding
duplicate ports or tests. Collide_VolumeObject's earlier exact retained Rust
translation remains uninstalled; the adapter calls the existing native entry.

## Evidence limits

Ignored original ELF evidence is `.cache/tricky-force-owner.disasm.txt`.
The final build/archive inventories are recorded in the implementation plan.
Compilation and serialized monitor graphs do not establish observed bursts,
re-entry, overlapping AI riders or restart. TFX2's force integration itself
is unchanged. Alaska's reported ice rails are still a separate unresolved
issue. No automated test, replay, gate, browser build, game launch or window
operation was performed.
