# Animation actors with static models

## Original behavior

Tokyo models7,8 and20 each have one part, no animation descriptor, no local
matrix and a zero header duration. Their42 placed owners nevertheless have
Main0/Sub256 focus commands. These include the BigFanAnim_C/D models and
Pinball_DoorMain. The commands request mode1, bounds-1/-1, rate30, variation0,
debounce1, random0 and direction3. A name containing `Anim` is not evidence of
missing curve data: other Tokyo models have correctly decoded tracks.

The USA Tricky dispatch table at36b7e0 sends Sub256 through13c804 to constructor
198810, allocating0x68 bytes. The constructor counts non-null animation pointers
at19899c..1989e4. Its zero-count branch198a8c sets the per-part animation-info
pointer to null but continues initialization and initial matrix publication.
It changes the visible instance's drawing/dynamic flags, attaches the actor and
initializes its playing state even when there are no animated parts.

Update199058 advances its clock. Loop mode1 wraps once by subtraction/addition;
it does not divide by the duration or repeatedly subtract a zero span. A zero
duration therefore does not prevent the original actor from existing. It does
not create an unrecorded fan rotation either.

## Import correction

The importer previously skipped256/257/258 commands whenever the model had no
curve channels. It now retains the command and translates its original
parameters through the existing native factories3/4/5. Negative source lower
bounds still become0; upper-1 still resolves to the native MDR duration.
The native actor, process registration and focus/contact ownership are retained.
No geometry, animation curves, clip duration or rotation is fabricated.

The inspected SSX3 code already supports this case:

- AnimObject_BaseCtor34d9b0 allocates matrices by model part count independently
  of the animation-info allocation. Null node-info is supported.
- AnimObject_BuildMatrices34dd18 uses each unanimated part's own matrix.
  The serializer's existing matrix-absent sentinel remainsFFFFFFFF.
- AnimObject_StepLoop341e48 uses the same single wrap arithmetic. It has no
  zero-span division or loop.

These functions already have handwritten translations; no new override is
installed. `source_static_animation_nodes` records exact source owner/node
pairs so the inventory distinguishes these actors from curve-driven players.

The change restores42 focus actors per Tokyo mode. Their actual runtime
appearance, focus re-entry and contact behavior remain unobserved; serialized
consumer coverage alone does not establish any of those outcomes.
