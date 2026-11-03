# Native fence response for Tricky

The supplied courses use Main0/Sub12 with mode0 and FlexAmount0.5. Its
source constructor143550 creates a Fence on the first physical contact.
Source143ff8 reads the previous/next instance links; source144428 handles
later contacts. Retained USA ELF disassembly is
`.cache/tricky-fence-source-v44.txt`.

## Native consumer and missing first-contact creation

Native builtin10/2fcc20 has the same `[RID,int,float]` defaults[-1,0,0.5],
but it never allocates a Fence. It calls AttachModifier2fae38(kind9) only
when the target already has a node. Creating an ordinary Object followed
by builtin10 would just discard the incompatible owner without constructing
the missing Fence. Builtin11/2fcdc8 is a FlexBridge, not a fence.

Native Fence_ctor34cab8 takes `(self,process_arg,Instance,descriptor)` and
an initial impulse in F12. It constructs WorldObj type9, copies a16-byte
descriptor and builds an8x2 dynamic mesh through34d1e8. Native neighbour
propagation34cc80 allocates0x10c bytes and calls this same constructor.
It applies a coefficient0.4 and threshold0.25; motion, damping, later
contacts, propagation delays, rendering, restorable kill and reset remain
native. The source mode0/coefficient0.5 feed that native descriptor directly.
This reuses SSX3's fence response, without claiming a bit-exact port of
Tricky's different normalized-mesh implementation.

Imported builtin128 supplies the missing initial allocation/constructor.
The initial source impulse is the VU-normalized authored local-X world axis
dotted with contact travel direction, multiplied by abs(speed)*0.001
(143614..1436a8). Later native Fence_v40/34d650 contacts use the contact
normal law, matching source144428. The adapter keeps a private caller frame
across a suspended allocation and returns through the existing VM boundary.
OnObjectTrigger's later notification uses Fence's inherited slot148,
WorldObj_v41/3609f8: a two-cycle empty return. It does not apply the
initial impulse again; its inspected port is retained uninstalled.

## Compatible source geometry

Native BuildMesh calls the already typed PS2GraphicsMan_v97/380380. It
extracts four model-local positions, UVs and colours from the first packed
quad. All supplied fence models meet that contract: one model part, one
mesh, one four-vertex strip. The source inventory contains359 Garibaldi,
577 Snowdream,680 Merqury and172 Tokyo owners before per-mode selection.
None has a part-local transform to omit. Compact source geometry evidence
is `.cache/tricky-fence-source-geometry-v44.json`.
Each serialized first quad uses the native position/UV offsets expected
by380380. Fence rendering supplies the original instance matrix.

Native UpdateVerts34cf98 displaces the top row along local X, using the
native200cm basis, authored coefficient, current sway and sine weights
`[0,.38267,.70710,.92387,.92387,.70710,.38267,0]`. Mode1 additionally moves
the bottom row; no source mode1 occurs in these courses. The imported
source model, texture, instance transform and static collider are retained.

## Authored adjacency and ownership

Native BuildMesh clears neighbour pointers104/108. The source PBD already
supplies semantic previous/next links; no proximity search is needed.
Focus builtin129 registers owner/next/previous native RIDs without creating
an actor or starting motion. For an active imported Fence, `custom_fences`
resolves next to104 and previous to108. The same preparation runs at native
Fence_Update entry, so a neighbour created by native propagation gets its
own authored links before its propagation counters run. End links and
targets absent from the selected mode remain null.

Only RIDs are retained. Native focus cleanup and world restart own meshes,
nodes and motion; static link definitions survive a same-course restart.
Changing course or event mode clears those definitions. Non-Fence actors
are not replaced by this adapter.

The already typed Fence_Update now resumes at its actual call-return PCs
ce78,ce9c,cef0 andcf84, rather than reopening its frame if a propagation
allocation or mesh update suspends. Its existing sway, damping, rate
conversion, branch arithmetic and cycle charges are retained.

Inspected native wrappers, constructor, propagation, mesh initialization
and vertex update remain separate uninstalled Rust translations, with empty
override lists. The live integration uses the native constructor/helpers
and the existing typed update. No automated tests or replay gates were
added or run. Serialized integration and compilation do not establish
physical or visual acceptance.
