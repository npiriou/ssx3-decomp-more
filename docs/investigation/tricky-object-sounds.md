# Tricky object sound commands through native SSX3 audio

This implements source SSF Main8 commands, previously omitted by the object
script compiler. It does not replace the audio engine or establish whole-course
audio acceptance. Automated tests, replays and game/window operations remain
disabled by the user.

## Source and native contracts

Tricky's Main8 branch at `13c384` forwards the source instance and payload word
to `2165c8`. The ordinary object-voice path selects bank2 and retains the sound
index. The configuration loader at `21143c..211480` maps `BANK` to slot2, using
the per-course bank from `DATA/CONFIG/BANKS.INF`. It is **not** the global
`zbxsfx.bnk` bank. Looking up the same ID in that global bank gives the wrong
descriptor, and sometimes an empty slot.

The source banks are garibaldi1, snowdream1, elysium1, mesabanca1,
merqurycity1, megaplex1, iceberg, alaska1, untracked1, pipedream1 and
tricktutorial. Supplied graph commands use IDs43/64/65/82/83/122. Merqury43
and Mesa83 are authored empty slots in their respective banks; Tokyo65 and
Snow83 are populated. A numeric ID alone does not identify the sample.

SSX3's `WScriptFn_PlayObjectSound` (`2fff00`) is native builtin30, pointer
`441fb0` in the table at `441f38`. Its two inputs are an instance RID and a
sound ID, forwarding to `SSXAudioSystem_PlayObjectSound` (`2974a0`). IDs below
100 select bank2. Saved native Tokyo RAM confirms that slot2 is `Mtn.bnk`.
IDs100..149/150..199 instead address memory banks8/9; source122 cannot be
copied directly into that dispatch. The original Mtn bank has94 entries.

The importer appends populated source patches at IDs94/95 and emits native
builtin30 with the exact imported instance RID and that alias. The second
argument uses the native resource-ID literal (`27`), already supported by
the installed VM. Source delays, gates, scopes and contact ownership stay
in their existing graph positions. Sound-only waiting continuations are now
retained; authored empty sounds remain no-ops.

Native SSX3 still owns voice suppression/tracking, instance position, channel
gain, listener pan/range, allocation and mixing. This is native object-audio
integration with original source samples, not a claim of bit-exact Tricky
spatial tuning or every source audio-system special case. Source ADL ambience
and other non-Main8 audio consumers are outside this implementation.

## BNK preservation

`tricky_audio.py` reads version5 little-endian `BNKl` and PS2 `PT05` patch
records. `FE` ends one variant, not the entry: native `SND_ParsePatch` returns
with its cursor advanced, and the next parse initializes fresh defaults
(one channel,22050Hz, codec5). The importer preserves all variants through
`FF`, including the intermediate `FC`/`FD` markers and every sample offset.
Metadata size is at+8, SPU size at+c and IOP size at+10. The supplied
mountain/source banks have no IOP region. Relative entries at+14 address the
patches; an empty entry is retained as empty. Source mono/stereo PS-ADPCM
channels use their original encoded frames, with `ceil(samples/28)*16` bytes
per channel. No audio is synthesized or resampled.

The output keeps every original Mtn patch, alias, control field and sample.
Metadata is rebuilt with self-relative entries; sample-offset fields88/89
are rebased to the new SPU region. Each original sample keeps its position
within that region. Only requested source channels are added, with their
original patch controls, rate, loop fields and channel count. Unsupported
layouts stop conversion rather than guessing a codec or replacement sound.

Studied native `SND_BankAdd` (`3b6098`) walks that self-relative table and
passes each nonempty patch to the relocation parser. SPU data starts after
the metadata and IOP region, and its allocation is SPU-size+30(hex). The
relocation origin is shared across a pass; retaining native patch0's first
sample at the SPU region's beginning preserves that origin. This is not a
linear scan requiring unreferenced original metadata or its original padding.

Seven studied native functions are retained as uninstalled Rust files, with
empty `OVERRIDES`: the script/audio object-sound entries, SndBank_Load,
SND_BankAdd, SND_BankRelocatePatches, SND_RelocatePatchCallback and
SND_ParsePatch. They are
not registered modules and their equivalence has not been verified by
execution. Existing runtime sound functions remain installed as before.

## Mounted archive and course changes

The native audio BIG can be mounted before event selection. Its directory
must remain stable across courses. The prepared `DATA/AUDIO/AUDIO.BIG`
retains all140 original members and their names, adding zero padding after
the original Mtn member to reserve one397312-byte extent. Every other member
is byte-for-byte original. The default Mtn payload retains its original
bytes before the padding, including when no imported course is active.

`MOUNTAIN.BIN` is a16-byte `TAU1`, version1 sidecar containing that extent's
offset/size. Eleven equally padded course banks live beside it. The private
host-file adapter validates the extent against the actual BIG directory,
then substitutes only reads intersecting Mtn with the active course's bank.
Header/other-member bytes come from the ordinary archive. Handles are cached
per course. No bank filename, native load-request record, constant string,
native bank slot or game-state memory is rewritten. Both synchronous and
asynchronous loaders consume the same host-file bytes.

Missing optional course banks retain the original read; their extra sound
IDs then miss safely in the native patch range check. A read failure reports
failure instead of treating a partially replaced buffer as complete. Actual
loading, listening, restart and successive course-switch behavior remain
unobserved in this wave.

## Prepared-data evidence

The read-only final inventory is
`.cache/tricky-object-sounds-v53-inspection.json`. It parses real BNK/BIG/BAM
bytes without executing the VM or game. It records original archive-member
preservation, native patch controls and sample offsets, native SPU data,
source patch controls and encoded channels, fixed extents and all serialized
sound-call argument pairs. Counts include graph/deferred duplicates, not
observed playback events.

Native build: `.cache/build-tricky-object-sounds-v53.log`.
All19 final archives: `.cache/prepare-tricky-object-sounds-v53-complete-all.log`.
The declared mechanics inventory now includes Main8, including its authored
empty slots; zero missing declared consumers is not whole-course acceptance.
