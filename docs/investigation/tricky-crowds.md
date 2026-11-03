# Tricky crowd boxes

CrowdBox17 was absent from the mechanic inventory and from the importer.
This is scenery animation, separate from the already accepted rider anger
icon. Source Movie23 is a second newly identified omission and remains open.

## Source contract

- Property switch36b7e0 selects constructor145b28 for Sub17, allocating104
  bytes. It retains descriptor rows/columns, calls145c00 and switches the
  instance to dynamic drawing. All reachable supplied descriptors are
  `[17,0,2,8]` or `[17,0,4,4]`.
- Setup1458e0 loads `DATA/TEXTURES/CROWD.SSH` independently of the course
  archive. Its16 directory images `cd00`..`cd15` are registered under runtime
  names `crowd00`..`crowd15`. It creates16 material records of48h bytes at
  31d4b8, flags20001, and replaces placeholder materials of model flag1.
  The importer previously used those placeholders' mountain texture0.
- Init145c00 gives each spectator a phase `random&15` and one of four
  animations `random&3`. BuildFrames145e08 chooses through four16-entry
  frame maps at31d378. A negative phase uses the animation's first image;
  otherwise it uses `(phase+spectatorIndex)&15`.
- Update145c88 runs every5 source ticks, hence12Hz at60Hz. Active crowds
  advance phases. At each16-phase boundary they choose another animation;
  reaction-dependent idle probabilities are `[256,0,50,100,200,100,50]`.
  A successful idle draw waits `random&63` updates. Crowd state0 freezes;
  state7 animates without the idle selection. A human within20000cm supplies
  `(CrowdAudio_GetInstanceReaction(riderIndex)+4)&7`.
- Source audio lookup2213f8 and native2a77c8 both read signed reaction18c
  from the rider's190-byte voice. Native2a77c8 uses count14/table18. Its
  exact inspected Rust translation remains uninstalled with empty overrides.
- Source Render145fc0 culls the original instance bounds, then sends its
  model, matrix and16 independent material pointers to the graphics manager.
  All supplied flag1 models have one untransformed part,16 meshes and16
  distinct materials. Their materials are not shared with ordinary models.
  The raw source mesh material-slot fields are0..15 in mesh order for all30
  models; mapping those slots to native sorted material IDs preserves order.

## Native implementation

`ssx3_tricky_crowds.py` imports all16 original images through native world
texture resources. It reserves their IDs before lazy particle assignment;
no existing retail texture or FX catalogue entry is overwritten. Crowd
materials use native textured/alpha-tested flags3 and frame0 as the static
fallback before focus. Geometry, vertex colours, instance lighting, matrices
and bounds remain the original converted resources.

Each selected source crowd instance reserves420 bytes after its existing
colour DMA chain, aligned to16 bytes. CRD1/version1, the texture base and the
source mesh-to-native-material ordering occupy32 bytes. The remaining388
bytes hold a native `{count16,pointers[16],records[16]}` material table. No
pointer is serialized: builtin134 initializes pointers after residency and
copies each resolved source20-byte material into its own record.

The original source property now creates an ordinary native Object and
registers RID/storage offset/rows/columns. Native Object owns focus entry,
exit, visibility, culling and rendering. The existing typed ModObj_Render
supplies the registered private table to its ordinary graphics draw call.
It never constructs the native TexFlipModifier, whose fixed private storage
holds only8 materials. No extra instance, renderer, geometry sampler, native
heap allocation or per-frame allocation per spectator is introduced.

The script manager updates registered live boxes at12Hz in configured game
time. Animation maps, delays, source carry-generator arithmetic and200m
proximity are retained. Cosmetic RNG state is private, seeded per owner;
source global RNG ordering is not bit-exact and does not alter SSX3's RNG.
Native Rider::AI_INDEX86c selects the corresponding audio voice. Native AI
preparation before state4 uses the unrestricted state7 animation; race and
countdown use native human positions/reactions. This is the native phase
adaptation, not a proven one-to-one source game-state enum mapping.

The adapter validates owner RID, instance/node backlinks, kind17, CRD1 and
version, sixteen source materials, mapping permutation, texture range and
storage addresses before use. Stale entries are pruned at the12Hz update;
the render path validates identity again. Restart/course changes clear the
host registry; streamed instance memory owns all private material storage.

## Scope and observations

This is source-derived implementation with native compilation and serialized
asset inspection, not gameplay acceptance. Current-version crowd appearance,
focus/re-entry, reaction correspondence and course switches remain unobserved.
No tests, replay, gate, game launch or window control are used. Movie23 is not
reported as covered merely because its screen geometry is present.

- Final native build: `.cache/build-tricky-crowds-v55-final.log`, successful
  in1m24s. The earlier v55 build predates the explicit AI_INDEX audio lookup
  and inactive-course render fast path.
- Final assets: `.cache/prepare-tricky-crowds-v55-all.log`, all19 variants,
  including the existing11 course audio banks. No later importer change.
- Read-only source layout inventory:
  `.cache/inspect-crowd-layouts-v55-final.log`, all30 crowd models in8 worlds,
  source slots0..15 and no material overlap with ordinary models.
- Actual BAM inventory: `.cache/tricky-crowds-v55-inspection.json`, no
  reported differences. It contains1260 source descriptors/private storage
  blocks/paired Object+134 calls across16 affected variants,352 distinct
  per-variant source material records and256 imported frame payloads. Every
  variant's serialized argument set matches source owner/rows/columns and
  its native storage offset. The maximum WSD is387248 bytes in Merqury
  Freestyle, using the existing oversized resource allocation path.
- Expanded audit: `.cache/audit-tricky-mechanics-v55.log`; the remaining
  declared missing consumers are the14 Movie owners (8 Garibaldi and1 each
  Snowdream/Elysium/Mesa/Merqury/Tokyo/Aloha). These are28 per-mode records.
  Zero crowd gaps means serialized consumers, not observed runtime execution.
