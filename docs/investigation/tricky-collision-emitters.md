# Tricky collision particle emitters

Main2/Sub2 is distinct from an ordinary independent emitter. The supplied
Untracked Race course binds it to34 SnowGhost tree owners, all using the
same source chain10/node2156. Each descriptor requests50 particles, no
trails, a0.01s window, source sprite2 (`clod`) and source blend0.

## Recovered source contract

Source dispatch13d130 first calls148900 with the contacting rider. It
allows fewer than3 live collision emitters when rider+41c is1, otherwise
fewer than1. Constructor148560 creates a separate process type1004 and
increments the rider-indexed counter31d498; destructor148890 decrements
that counter. The emitter does not replace the contacted tree's WorldObj.

Constructor148560 copies the first contact vector into node+30. It takes
the VU XYZ length of the descriptor's velocity vector (source node words
at offsets54/58/5c), multiplies the contact normal at+20 by that length,
and stores the result in node+40. Setup148748 copies the51 descriptor
fields and replaces only origin offsets24/28/2c and velocity48/4c/50.
It supplies the identity matrix346440. That matrix is initially BSS in
the ELF; initialization251238..2512bc writes the four diagonal ones and
twelve zeros. Treating its raw zero file bytes as a zero matrix would be
incorrect. Retained disassembly: `.cache/tricky-collision-emitter-source-v43.txt`.

Update148948 advances the embedded emitter and deletes the process once
its life reaches zero or the source owner is no longer active. Its destructor
owns the source counter decrement. These limits concern simultaneous live
emitters, not total contacts or an arbitrary cooldown.

## Native implementation

The compiler retains all51 authored fields, original catalogue-selected
sprite/blend, static frame1/rate0 and a dedicated hidden host. Main2/Sub2
uses builtin127 at the existing Luno native-call boundary. The adapter
changes origin9..11 to contactB's point and velocity18..20 to
normal20*authored speed, issuing the source VU length/multiply operations.
It then calls native AddParticleData2fe840 with54 named arguments. Native
allocation, particle integration, lifetime, rendering and list removal remain
unchanged. The native main-tree property, collision and bounce are unchanged.

Collision hosts have identity matrices because the descriptor already holds
world coordinates. They retain the original tree's world bounds for native
focus cleanup. Ordinary independent emitters keep their separate authored-
matrix hosts; the two types may coexist without sharing a coordinate frame.

The adapter counts effects by contacting rider across all collision hosts,
with the source3/1 limit (native human flag874). A retained effect is live
only while its instance/node/modifier/description identities still match,
the modifier is actually in the native particle list, and its done field1e4
is clear. Native ModifierList_PushFront345700 and ParticleModifier_Update345b40
are already typed. Restart/course changes clear retained ownership. A pending
native allocation keeps its private stack until the normal VM return site,
including a suspended return; no VM opcode or host particle integrator is added.

Source metadata lists exact `(owner,node offset)` collision consumers separately
from Main2/Sub0. Prepared bytecode and a successful native build establish the
integration; visual appearance, physical contacts and cap retirement still
require ordinary manual observation. No automated tests, replays, gates,
browser builds or game/window control are part of this wave.
