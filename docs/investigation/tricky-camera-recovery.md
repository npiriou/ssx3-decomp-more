# Imported platform cameras and off-limit recovery

2026-11-04, v66. The user's ordinary play exposed camera-under-platform
behavior at Alaska's start and Elysium's wooden bridge, and repeated off-limit
recovery for humans and AI across courses. The earlier Tokyo glass-platform
camera report belongs to the same general visibility requirement. No course
coordinates, object names or per-map exceptions are used by these changes.

## Camera visibility

The installed typed `GameCamera_AvoidCollision` (`15ee00`) first sweeps a
vertical segment around the desired eye. Its lift response can accept free
space underneath a raised floor. The existing second query tests the segment
from `lookAt + 100cm up` to the desired eye, but retail only runs it while a
script camera is active in the chase controller.

For imported ordinary chase views, run that same native solid-world segment
query as well. The active controller at `camera+a0` must match its chase
controller at `camera+a8`, and the native script-camera predicate must be
false. Other controllers and active script cameras retain their normal path.
The segment's contact-reference fraction is zero, so the world selects the
first obstruction from the rider-side endpoint. Retract the eye along this
line to the rider's side of that obstruction, using the existing native
50cm avoidance margin. Save that position as the clear eye. This constrains
visibility through terrain and prefab collision, including thin or stacked
platforms; it does not assume that terrain below the camera is the ridden floor.

The following native functions were studied and retained as uninstalled Rust
reference modules, each with empty `OVERRIDES` and no automated test:

- `custom_nash_closest_contact.rs`, `336850`: collects at most64 contacts,
  chooses the fraction closest to the query's virtual reference, and copies
  the full128-byte contact. A miss returns-1. Stable tie-breaking prefers an
  instance and then its lower RID, or lower dynamic-object ordering word.
- `custom_nash_collide_volume.rs`, `335d78`: traverses all eight root cells,
  visiting static instances and dynamic objects as well as child subtrees.
  It forwards the native query and ignore list; this traversal itself does
  not exclude platforms or add a surface/kind filter.
- `custom_segment_reference.rs`, `340a10`: returns `segment+a0`, which the
  constructor stores from F12. This parameter is a preferred contact
  fraction, not a capsule radius; the existing constructor comments now
  reflect that contract.

The actual runtime continues to use those native collision implementations.
Script-camera handling and retail courses keep their existing policy.

## Recovery point selection

Original Tricky's ordinary reset controller (`106c7c`) calls `118c08` before
placement. That selector starts from the rider's current AI path and path
distance, with the controller's distance offset (the ordinary request at
`1191b0` writes zero). It samples that
route (or extrapolates its final segment), finds nearby respawnable paths
around the resulting point, and scores projections and an800cm look-ahead.
It excludes candidates within200cm of a path end for every rider. The falling
rider's world position is not the positional reference for this selection.

Native SSX3's `Rider_SnapToNearestAIPath` (`112d58`) instead searches and scores
around the current world position. The installed imported-course adaptation
of its previously retained typed body seeds all those operations from the
current native AI path at `rider+4c4`, retaining native cursor/boundary
resolution and final recovery outputs. The immutable query seed temporarily
uses the routine's own look-ahead output at `rider+4a0`, separate from its
projection output at `rider+490`. The final native look-ahead overwrites it.
The rider's actual pose is untouched during selection. Imported candidates
use Tricky's800cm look-ahead and unconditional200cm end exclusion. Retail
courses delegate to the unchanged generated body.

`custom_near_ai_wrapper.rs` retains the studied native wrapper `26af98`,
uninstalled with empty `OVERRIDES`: it already passes fifth argument T0=1 to
the nearby-path selector, requesting respawnable filtering. The fix therefore
does not invent a missing eligibility flag, rewrite serialized respawnable
values, or force all paths eligible. Existing marker-boundary handling stays
in control.

## Placement near the selected route

Tricky `119220` resolves the selected route point and calls `11cae8`. Its ground
probe at `11cc8c..11ccd4` runs from `pathZ - clearance - 200cm` to
`pathZ + 200cm`, with contact-reference fraction0. A contact supplies the
placement position and normal; a miss preserves the requested path point.
It then adds the caller's clearance (`11cddc..11cdfc`). Tricky does project to
nearby ground: suppressing every ground query would not reproduce this behavior.

Native `Rider_Place` (`11d660`, already retained in `custom_rider_place.rs`)
uses a segment starting7000cm below the requested point and ending200cm
above, with reference0.9791667. Imported reset placement now uses Tricky's
shorter probe and reference, preserving native clearance and the real world
query, contact normal, no-hit fallback and subsequent motion/camera setup.

The adjustment runs in the existing typed segment constructor (`32e100`)
only for return `11d814`, with the placement argument equal to the rider's
canonical recovery point and its motion owner in reset state3. This is the
common placement used by human and AI reset handling (`12f398`, placement
return `12f494`). Starts, teleport placements and other segment queries retain
their normal behavior. No separate human-only safety path, trigger cooldown,
coordinate blacklist or forced state transition is added.

Source disassembly derived from the supplied Tricky ELF stays ignored in
`.cache/tricky-*-v66.disasm.txt`; the key placement record is
`.cache/tricky-place-ground-v66.disasm.txt`. The retained reference ports are
not registered or presented as differentially verified modules.

## Build and evidence limit

Both generated dispatch forms are regenerated for the added `112d58` slot
in `.cache/regen-tricky-camera-recovery-v66-final.log`. This is code generation,
not a browser build. The final native executable is built with
`cargo build --profile game -p ssx3 --bin ssx3`, recorded in
`.cache/build-tricky-camera-recovery-v66-final.log`, successful in2m06s.
The final code also preserves the existing script-camera predicate before
enabling ordinary-chase retraction. The initial v66 build preceded the final
short-ground-probe correction and is superseded.

No importer or asset changes are required; all19 v63 archives remain current.
No automated tests, replays, gate, browser build or game/window operation is
performed for v66. These are general implementation corrections supported by
the source contracts. The user's next ordinary play must establish their
actual camera and reset behavior; neither this compilation nor the earlier
v64 manual session proves those outcomes.
