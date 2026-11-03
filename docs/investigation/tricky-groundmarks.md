# Tokyo persistent groundmark investigation

The user identifies the red/black effect as the mark left on the ground,
visible from the start. It is not the airborne snow spray. This issue is
still open; no current appearance is claimed fixed by this investigation.

## Existing saved observations

Read-only inspection of four previously saved RAM snapshots (Tokyo frames
1067/8303, Elysium frames1149/16030) selects native FX slot55, texture1715,
TexInfo589700, format0/PSMCT32,128x64. Its complete pixel SHA256 is
`bd27b7b3669eeadc074b98955005e620fbf3efaa259e8d7a195e6eef1139e901`
in all four. RGB ranges are178..255,179..255,180..255; alpha0..128.
All four retained layer3 records contain
`{c0,1400294,60,0,ffff06b3}`. The global selecting both faces is1.

The texture's TBP field is-1 in those snapshots: the packetless renderer
does not allocate its images to GS VRAM. This is not evidence that the
resource is missing or aliased. Native frame binding supplies an odd
synthetic TBP when needed, and maps the draw's actual TexMan ID into it.
Inspectors must exclude-1 when listing resident-address aliases.

Previous inspection found coherent neutral/light RGB values in Tokyo's six
54-vertex groundmark rings and inactive BoardWakeFX in both worlds. The
retained native RenderBatch2ea538 only forms up to16 ring descriptors; it
does not choose or replace the image.

The native shadow-volume renderer386e78 lives in the existing handwritten
`packetless/ribbon.rs`. Its first three face passes manipulate destination
alpha/depth, followed by five textured edge passes and an optional
destination-alpha-tested face pass. Alpha44 is the ordinary native
`(Cs-Cd)*As+Cd` equation. Therefore an ordinary texture/color substitution
cannot establish which stage produces the reported appearance.

Inspected packet writer387ec0 is retained in `custom_shadow_strips.rs`,
uninstalled with empty OVERRIDES and no tests. Its A/B copy order,36-pair
batch limit,54-vertex wrap, final two indices, common closing UNPACK and
one-pair overlap agree with the existing `capture::shadow_input` contract.
This source comparison does not execute either writer or prove GPU output.

Evidence remains local in `.cache/inspect_groundmark_binding_v58.py` and
`.cache/groundmark-binding-v58-inspection.json`. The script only reads the
four saved files; it does not launch or replay a game.

## Passive native observations

`ssx3-gfx::groundmark_trace` now records bounded inputs during ordinary
manual play of imported courses. It activates only after an actual
Mat3Strip/ALPHA44/main-target alpha-only face batch exists. Four frames
are sampled, at least0/60/300/900 rendered frames after the first such
batch. Course selection, departure and an ordinary restart update only
the host diagnostic context. The course/run label is host context; a
queued older frame may still complete across that transition.

The log records:

- The groundmark's expected TexMan ID from its published native draw
  state, plus actual resolved texture/target per GPU batch. It does not
  guess an ID from an uncaptured game-global page in the renderer snapshot.
- FRAME/ZBUF/TEST/FBA/ALPHA/TEX0/TEX1/CLAMP/TEXA and actual GPU draw ranges.
- The submitted calls' color extrema and three raw ST/RGBA/clip/flag samples,
  with their guard matrices, taken from the same CPU buffers uploaded to GPU.
- The final blend/depth/write plans, shader lighting flags, alpha-test side,
  texture-combine mode and alpha expansion uniforms.
- Source image key/dimensions/color ranges, configured replacement path and
  whether the actually cached GPU resource used a replacement. Source image
  ranges are explicitly distinct from a replacement's pixel contents.

Output is `.cache/diagnostics/groundmark-<pid>-<stamp>.log`, flushed once per
sample. Limits are24 batches,128 calls and96 plans per sampled frame.
There is no GPU readback, screenshot, extra rendered frame, game-memory
write, shader modification, texture replacement or input/window operation.
Outside those four samples only the small context/sampling checks remain.

No new runtime observation has been collected for this version. This adds
the missing evidence at the GPU input boundary; it is not a trail fix or
visual acceptance. Native compilation succeeds in1m32s in
`.cache/build-tricky-groundmark-observations-v58.log`; the retained
uninstalled packet writer is not compiled by that build. No automated test,
replay, gate or browser build is used.
