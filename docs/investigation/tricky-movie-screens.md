# Tricky Movie23 screens

Movie23 was newly exposed by the v55 inventory. This pass supplies its source
pictures, shared playback and native texture/material consumer. It does not
establish in-game appearance or completion of the full mechanics objective.

## Source

- Property constructor148a70 calls148b28, selects the course's
  `data/video/j*.sss` and requests width128/height64/loop1/rate15 from1fff30.
  The manager shares a player when filename, loop and rate match and maintains
  references at manager+1c. Releasing the last reference calls1ffa10 to stop.
  A subsequent1ff990 start resets counters and opens the stream at its start.
- Seven supplied worlds contain14 selected owners: Garibaldi8, plus1 each
  Snowdream/Elysium/Mesa/Merqury/Tokyo/Aloha. Both modes use them. Garibaldi's
  advertising screens and finish screen share the same sequence. Each model
  has one untransformed, unanimated part with one material. Merqury200 and
  Aloha156 are also used by ordinary scenery, so changing their shared records
  would replace unrelated textures.
- Source1ff6f0/1ff890 creates a black16-bit texture. Its material table has4
  pointers to one record, flags1. The imported models use one of these entries.
  Playback1ffa88 increments60Hz counters and consumes one picture every
  `60/15=4` ticks; end-of-stream restarts because loop1 was requested.
- SSS files contain consecutive SSSF chunks, each4152 bytes. At+8 is a shape
  header with packed value102060, width128, height64;512 colour blocks follow
  at+24. Shape padding/name records are not pixels. There is no audio payload.
- Callback1ff928 invokes shape decoder2c2318, then2c2bf8/2c27c8. The latter
  is materially different from a generic BC1 decoder: four colours require
  `endpoint0 > endpoint1`; interpolation uses5/8 and3/8 on masked565 channels.
  The other case uses a truncated average and zero fourth entry. Zero original
  endpoints become1 before conversion; computed zero entries remain zero.
  Nonzero565 values become PS2 RGB5551 by
  `((v&31)<<10)|((v>>1)&3e0)|(v>>11)|8000`. Preserve these details.
- Render148d28 gets the shared material table through2001c8 and draws the
  original model/instance/matrix. It also calls graphics virtual1e0 with3.
  Source constructor1ea0c0 installs vtable393610; that slot resolves to1e9418,
  which updates bytes15/17 of the current draw-state record at graphics+470.
  Those are the two alpha blend selectors: state emission1c5298/1c52fc passes
  them to GsPkt_AddAlpha1c03e8 with context1/2. Case3 at1c0438, selected by
  table390860, emits GS ALPHA44: `(Cs-Cd)*As+Cd`. Native preset5 emits the same
  value (ssx3-render/frame.rs::blend_preset). This correspondence is resolved
  in v57. It is unrelated to native SetTextureFilter's separate TEX1 fields.
- Source model material flags1 selects the ordinary zero/zero test branch
  at1e273c; it does not replace those blend selectors. Source translucent
  flags40000 follow a different branch. Therefore preserve ordinary native
  sorting/Z/test fields while supplying the recovered alpha equation; using
  a translucent native material would also change those unrelated fields.

## Native consumer

`ssx3_tricky_movies.py` prepares the source decoder's sixteen-bit pictures
offline into one TVM1 file per course. It retains dimensions/frame count/15Hz
and source ordering. Only one16KiB black native WorldSSH texture is loaded
into game RAM; the full sequence stays in host memory, cached once per active
course. A texture ID is reserved after crowd images and before particle IDs.
No retail FX slot, movie decoder or native global texture is replaced.

Each source screen reserves48 bytes after its existing colour DMA chain:
TVS1/version1/textureID/count1, then a native material table and20-byte record.
Object factory0 plus imported135 creates/registers its original instance.
The private material uses the source flags1 and the shared video texture;
source geometry, lighting, colliders, shared material records and matrices
are not rewritten. The existing native ModObj draw passes the private table.
Typed native ModObj_Update356198 permits an empty modifier block; it does
not impose a lifetime on these Objects. Focus cleanup stays native.

After ordinary native LoadTextureFromShape succeeds, the explicitly tagged
TVM1 shape publishes its texture. The adapter obtains TexMan through the same
vtable178 `this` adjustment used by that loader and verifies its slot, format2,
16384-byte size and pixel pointer. It does not guess an embedded manager offset.
The retained native SetTextureFilter37d090 port is uninstalled/empty OVERRIDES;
its inspected TEX1 contract is not installed as a replacement or mapped to
the source alpha selector.

The native script-manager epilogue copies at most one due picture into the
native texture buffer, then calls existing native TexMan_EvictTexture369098.
The next ordinary draw uploads it through the existing VRAM/GS path. No new
renderer, texture upload format, guest heap or per-frame picture allocation
is added. Playback starts after1/15s, uses configured game time, shares one
cursor across all live screens and loops at the source count. Low tick rates
can advance multiple source pictures to preserve playback duration.

Native Object/instance/RID/header identities reject stale screens. The last
screen leaving stops playback; the next starts at picture0. Same-course
restart clears screen registrations/cursor while retaining valid native
texture ownership and cached media. A course change clears them; a reloaded
tagged texture republishes its current native ownership. Missing/corrupt TVM
data leaves the initialized texture static and emits one load diagnostic.
`native_files` supplies the actual configured overlay root. The preparer also
requires the shared TVM file/extent before retaining a cached movie world.

## Evidence and remaining observations

### Native alpha correspondence (v57)

The existing native DrawModel normally replaces the opaque branch's blend
with preset1/context1 and preset3/context2. Setting the current state before
calling it would be overwritten; its predefined opaque bucket also carries
those modes. `custom_movies::is_screen` identifies only a live registered
instance with its exact private material table. The native model path now
uses preset5 in both fields for that movie's opaque branch and avoids the
predefined opaque bucket. Ordinary native sort, Z/test/AREF, geometry, texture
IDs, clipping, lighting and existing fade handling are retained.

The packet-capture fallback also routes registered movie tables through this
existing native model implementation. Other imported/retail models retain
their original path. No shared base-state record, shared material, global
texture, native preset table or GPU blend implementation is patched. Native
draw-state interning and bucket submission receive the source equation.

The prepared source16-bit pictures have binary alpha. The initial all-zero
texture and zero palette entries now preserve the destination under that
equation; nonzero opaque entries use alpha128. This follows from the source
pixels and blend operation, not a current-version visual observation.

Only Rust rendering code changes in v57. All19 final v56 archives/seven TVM
files remain current; they are not rebuilt for this change. Source inspection
is retained in `.cache/tricky-movie-{model,alpha,state}-v57.disasm.txt` and
`.cache/inspect-movie-blend-v57.log`. Native compilation is recorded in
`.cache/build-tricky-movie-blend-v57.log`. Current appearance and native
submission/upload execution remain unobserved. The v57 native build succeeds
in1m24s; it is the current binary for this rendering change.

- `.cache/build-tricky-movies-v56.log`: native build succeeds in1m24s.
  This is the initial v56 integration build, superseded by the v57 build
  above. The retained filter translation is not compiled or installed.
- `.cache/prepare-tricky-movies-v56-all.log`: all19 variants regenerated,
  including the existing11 object-sound banks and7 shared TVM files.
- `.cache/tricky-movies-v56-inspection.json`: read-only actual SSS/TVM/BAM
  inventory, no reported differences. Seven complete sequences contain1796
  source pictures: Gari264, Snow254, Elysium255, Mesa261, Merqury254, Tokyo255,
  Aloha253. Header/extent/order count and15Hz metadata are retained. The report
  does not execute either decoder or prove pixel equivalence by running them.
- The same inventory finds14 black PSMCT16 texture resources,28 private
  instance tails and28 paired Object+135 calls. Each affected variant's
  serialized argument set matches its source owners and storage offsets.
  The four Merqury/Aloha per-mode ordinary shared-material payload hashes
  remain unchanged. Maximum WSD is387344 bytes in Merqury Freestyle, using
  the existing oversized resource allocation path.
- `.cache/audit-tricky-mechanics-v56.log`: zero missing consumers within the
  inventory's declared families, now including CrowdBox17/Movie23. This does
  not mean all source rendering state, actual native publication/uploads,
  appearance, loop/focus/restart/course-switch behavior or full courses are
  accepted. Source virtual1e0/native correspondence is resolved in v57; the
  reported rails, Tokyo groundmark/camera/finish and other pending observations
  remain open.

No automated tests, replay, gate, browser build, game launch or window control
occurred. Existing user-accepted snow/boosts/anger icons/Roller physics remain
outside this change.
