# Tricky wind flags and the native Flag consumer

## Source contract

Tricky USA Main0/Sub13 constructs a type13 Flag at144778 and initializes it
at144938. The serialized fields after subtype are variant, rate, amplitude
and lifetime. The supplied worlds use variant0/1, rate1.5, amplitude25/40 and
zero lifetime (indefinite): Snowdream47, Elysium22, Mesa38 and Tokyo12 owners.
All119 owners bind the effect to focus channel0. Their models are distinct,
single-part, single-mesh four-vertex strips with no part-local matrix.

Init stores rate/60 as phase increment, lifetime*60 as an integer counter,
and seeds one random phase in[0,1). It normalizes the model's X coordinates
and amplitude for its scaled dynamic mesh; the amplitude is divided by
`max(modelScaleX,1)*250`. This division does not belong in a native SSX3
descriptor: native GetQuad380380 already returns model-local centimetres.

Update144e48 advances/wraps the phase and calls UpdateVerts144ec8. The source
interpolates its two rest rows at column/7, but computes its wave at k/8:
`dx = amplitude * (k/8) * sin(-2*pi*phase + 2*pi*k/8)`, k1..7, with one
pinned endpoint. Variant0 pins the first column; variant1 reverses offsets
and pins the last. Both rows receive the same local-X displacement.

## Native implementation

Builtin12/2fc9c8 owns Flag construction34add8, ReadParams34ac88 and manager
registration34c548. The manager builds and animates an8x2 mesh for the
supplied one-wave descriptor. Native focus/reset owns its teardown and
restoration. Its group model key includes the MDR resource identity and
the complete0x58-byte converted descriptor.

The importer supplies seven explicit named parameters through adapter130:
owner0; pinned-first1; pinned-last2; rate4; amplitude5; spatial frequency6;
constant blend22. Source variant maps to complementary pinned-edge bits.
Rate is1.5. Amplitude and spatial frequency are multiplied by7/8 because
native ComputeVerts uses column/7. Thus source amplitude40 becomes35,
and25 becomes21.875; spatial frequency is0.875. Blend1 preserves the source
constant rate/amplitude instead of scaling them with native wind strength.
The other three native waves, row pin, bend vectors and UV scroll retain
their inactive defaults.

This deliberately uses the **native SSX3 flag response**. With a single
pinned edge, ComputeVerts34bca0 also accumulates a Y curvature from cosine
samples. Tricky's wave is X-only. Native sine quantization and four random
initial phases also differ. The mapping preserves the source X wave's
spatial profile, rate and fixed side, not bit-exact Tricky vertices/RNG.

Native capacity is15 groups,60 instances per matching group. These source
models each require a distinct group. Retail construction hides the static
quad before searching for an empty group and reports no registration
failure. Adapter130 therefore checks capacity before construction and
keeps the original static quad if all groups are occupied. A later focus
entry can try again after native cleanup. No capacity expansion, animation
retry loop, alternate physics or custom flag integrator was introduced.
The maximum active focus set has not been observed in a new game session.

## Retained translations and evidence

The exact native GroupAdd34b038, GroupRemove34b168, BuildMesh34b228 and
ComputeVerts34bca0 translations are retained separately in
`custom_flag_group_add.rs`, `custom_flag_group_remove.rs`,
`custom_flag_build_mesh.rs` and `custom_flag_compute.rs`. Their override
lists are empty; they are not installed or compiled. Factory12 was already
retained in `custom_flag_factory.rs`. These names reflect their actual
addresses;34b168 is removal, and34b228 is mesh construction.

Ignored source evidence: `.cache/tricky-flag-init.disasm.txt`,
`.cache/tricky-flag-update.disasm.txt`, `.cache/tricky-flags-source-v45.json`.
No automated test, replay, gate, browser build, game launch or window
operation is authorized for this work. Native compilation and resource
conversion do not establish an observed gameplay result.
