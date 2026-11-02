# Additional tracks: Garibaldi investigation

This repository copy is the work area for a fourth Single Event peak, **Bonus**, with
Garibaldi from SSX Tricky PS2. The race and menu integration are **not yet
implemented**. The current tool inspects source terrain without altering any
SSX 3 course or saving converted game data to Git.

## Local images and first import

Use SSX 3 USA (`SLUS_207.72`) and SSX Tricky USA (`SLUS_203.26`). On this
machine the image paths are:

```powershell
$env:SSX3_ISO = 'X:\dev\ssx3\SSX 3 (USA).iso'
$env:SSX_TRICKY_ISO = 'X:\dev\SSX Tricky (USA).iso'
cd X:\dev\ssx3-decomp-more
py tools/tricky_assets.py --output .cache\garibaldi-world.json
```

The converter verifies Tricky's disc serial, reads `DATA/MODELS/GARI.BIG`
through ISO9660, and expands its RefPack members. The inspectable JSON
preserves the PBD terrain patches, instance transforms and materials; the LTG
spatial grid with patch, instance and spline segment IDs; and the AIP AI paths
and race line. It retains each patch's 16 power-basis coefficient vectors, UV
vectors, lightmap vector, corners, bounds, texture assignment and surface
type. The output goes in `.cache/`, which is ignored by Git because it derives
from EA's disc.

For a source summary without output files:

```powershell
py tools/tricky_assets.py
py tools/tricky_assets.py --track SNOW
py tools/tricky_assets.py --list-members
```

The original SSX 3 events can be launched with the existing game command,
for example:

```powershell
$env:SSX3_ISO = 'X:\dev\ssx3\SSX 3 (USA).iso'
cargo run --profile game -p ssx3
```

There is **no Garibaldi launch command yet**. `SSX_TRICKY_ISO` is read by the
import tool only. The game does not register a custom track or display Bonus.

## Findings from the two images

Garibaldi's PBD contains 3,885 terrain patches, 3,393 instances, 169 splines,
542 spline segments, 125 materials, 121 textures and 942 lights. Snowdream
contains 1,653 patches and 3,230 instances, but 293 splines, 1,088 spline
segments and 1,466 models compared with Garibaldi's 648. It is not clearly a
simpler complete conversion, so Garibaldi remains the first target.

Each Tricky PS2 patch is 0x1c0 bytes. The 16 coefficient vectors begin at
offset 0x50. SSX 3's loaded patches contain 16 coefficient vectors at offset
0x40 in the same descending power basis. The polynomials reconstructed from
all 3,885 Garibaldi patches agree with their four stored corners to at most
0.0234375 world units. This verifies source order and basis; it does **not**
yet verify matching coordinate scale, UV conventions, collision behaviour or
the fields needed in an SSX 3 world section.

The LTG grid has 23 × 31 main cells, 243 occupied, each subdivided 4 × 4.
Every one of the 3,885 patches, 3,393 instances and 542 spline segments
appears exactly once in its resource lists. The AIP contains 90 AI paths with
2,105 points and 14 race-line paths with 756 points. Reconstructing each path
from its origin and `(direction × distance)` vectors agrees with the stored
path bounds to at most 0.001574 world units. These paths are source geometry
for adaptation to SSX 3; the Tricky AI is not executed.

SSX 3's `DATA/WORLDS/BAM.BIG` is a different BIGF archive. Its `bam.sdb`
describes 49 named locations, 183 spatial chunks and 159 streaming chunks;
`bam.ssb` holds compressed resource streams. The source LTG cells cannot be
substituted for those SDB/SSB structures. A standalone Garibaldi world needs
its own section graph and the resources the game expects in each section.

The read-only target probe can inspect a retail SSX 3 stream directly from
the SSX 3 ISO:

```powershell
py tools/ssx3_world_probe.py --iso $env:SSX3_ISO --location ARA1 --stream -1
```

ARA1's final stream contains 6,875 resources, including 1,913 terrain patches
of 432 bytes and 3,052 instances. Its SDB entry reports 4,734,956 unpacked
bytes, although its compressed blocks actually expand to 5,155,109 bytes;
resource framing verifies the latter. SSX 3 patch coefficients begin at
offset `0x40`. Six `vec3` fields at `0x158` are a bounding minimum and maximum
followed by four corner positions. The decoded coefficients match all four
corners to within 0.000641 world units over those 1,913 patches. This corrects
the corner interpretation in the external reference reader and confirms the
polynomial basis on real target data. It does not establish that a converted
Tricky patch is accepted by the game loader.

## Integration boundaries

- `crates/ssx3-game/src/event_boot.rs` scans three peaks from the original
  event tables. This is a debug boot path, not the menu architecture.
- `crates/ssx3-game/src/game/fe/uitemplatemap.rs` handles three original peak
  rows, fixed row flags, tabs and event records. Its peak acceptance rejects
  rows greater than two. The source UI templates also need inspection before
  exposing a fourth row.
- `crates/ssx3-game/src/state.rs` reads the original 17-entry track-info
  table. An extra index must never run through that allocation.
- `crates/ssx3-game/src/native_files.rs` already supports the SSX 3 ISO or a
  replacement data directory. A custom world needs its own file resolution
  and cache; replacing an original world file would break existing courses.
- `crates/ssx3-render/src/world_casters.rs` reads loaded terrain patches from
  the Nash world tree. Rendering alone will not provide gameplay collision.

The planned host catalog will keep custom peak and track IDs separate from
the 17 original records. The event UI will query that catalog for Bonus,
then the game world loader will select custom data from the Tricky image.
World sections must carry patches, instances, material mappings, collisions,
rails and race metadata. The standard SSX 3 race setup, AI, HUD and result
states should consume the resulting world. Save data for the three original
peaks must keep its current layout.

## Work still required for a playable race

1. Resolve Tricky surface/material IDs to SSX 3 surface properties and texture
   assets, then prove terrain orientation, scale and collision on a small
   section before converting the whole course.
2. Convert instances, splines and spatial grouping into SSX 3-compatible
   sections. Add start, checkpoints, finish, respawn and AI routes.
3. Add a separate host catalog and world loading path for custom tracks.
4. Extend Single Event's native UI with Bonus → Race → Garibaldi, including
   controller and keyboard navigation, confirmation, restart and return.
5. Verify Garibaldi end-to-end and replay the original three-peak menu and
   races. Keep the browser smoke test last.

## External format references

The binary layouts were checked against
[SSX-Library](https://github.com/GlitcherOG/SSX-Library), notably its Tricky
`BDHandler`, `LTGHandler` and `COFB` readers and its SSX 3 `WorldPatch`
reader. SSX-Library is GPL-3.0; it is a reference checkout under ignored
`.refs/`, and no library source or game assets are included in this repo.
The SSX 3 and Tricky game images remain local user files.
