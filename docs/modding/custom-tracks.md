# Additional tracks: Garibaldi investigation

This repository copy is the work area for a fourth Single Event peak, **Bonus**, with
Garibaldi from SSX Tricky PS2. The race and menu integration are **not yet
implemented**. The current importer builds a separate Garibaldi world location
inside a derived BAM archive. The three original peaks and their world streams
stay in place. Derived game data stays outside Git under `.cache/`.

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
import tools only. The game does not register a custom track or display Bonus.

## Build and inspect the derived world archive

The current builder converts Garibaldi's 3,885 terrain patches, 125 materials,
121 indexed textures, 16 lightmaps and 90 AI paths/14 race paths. It appends
one `GARI` location with a texture leaf and a shared resource stream to a copy
of SSX 3's `BAM.BIG`. It does not yet convert Tricky's models, instances,
collisions, splines or race markers. Consequently this archive is a resource
integration fixture, **not a playable course**.

```powershell
$env:SSX3_ISO = 'X:\dev\ssx3\SSX 3 (USA).iso'
$env:SSX_TRICKY_ISO = 'X:\dev\SSX Tricky (USA).iso'
py tools/build_garibaldi_world.py --output .cache\overlay\DATA\WORLDS\BAM.BIG
py tools/ssx3_world_probe.py --big .cache\overlay\DATA\WORLDS\BAM.BIG --location GARI
```

The builder checks both disc serials and fails with an explicit error if
either image is absent or incompatible. It verifies the decompressed new
streams and confirms the original locations and stream bytes are unchanged.
The new BAM can be supplied to the native file layer while all other files
still come from the SSX 3 ISO:

```powershell
$env:SSX3_DATA_OVERLAY_DIR = '.cache\overlay'
cargo run --profile game -p ssx3
```

With no overlay variable, the game reads the unmodified SSX 3 ISO. A headless
600-frame Snow Jam (`SSX3_EVENT=ARA1`) smoke run with the overlay reached
frame 600, reported no missing functions, and read the derived BAM header and
SDB. A matching retail run made the same 610 file reads; only the BAM header
and SDB contents differed among common read keys. Music selection also
varied between runs. This verifies existing course access with the appended
archive; it **does not** exercise loading `GARI` or prove gameplay compatibility.

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

The PBD reader now also preserves the 169 spline headers and all 542 segment
records: four control vectors, four curve coefficients, bounds, lengths,
parent and neighbour links. On the real Garibaldi image every segment belongs
to exactly one spline, and all previous/next links agree in both directions.
SSX 3 type-8 spline resources have a 48-byte header and 144-byte segments,
whereas Tricky has 40-byte headers and 128-byte segments. Their extra fields
still need semantic mapping before the splines can be packaged as rails.

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

ARA1 has a 15-node binary spatial tree: seven internal nodes and eight leaves.
The leaves point to streams 25–32, containing only resource kinds 9 and 10
(shapes and shape lightmaps). Stream 33 holds the location's terrain, models,
instances, collisions and race metadata; its patches refer back to those
eight leaf stream IDs. Thus the importer must preserve both the shared
resource stream and the leaf resource mapping. The probe validates each
stream's SDB counts against the SSB records and checks child indices within
the selected location's tree.

`tools/ssx3_world_build.py` writes SSB resource headers, uncompressed
RefPack literal blocks and the known 432-byte patch geometry layout. Its
encoder was verified by decoding a rebuilt 5,155,109-byte ARA1 resource
stream to the same SHA-256 as the original. Repacking each of ARA1's 1,913
terrain patch payloads with the original metadata reproduced every payload
byte for byte. All 3,885 Garibaldi patches also fit the target geometry layout
without changing a coefficient value. The writer requires explicit patch
metadata for material IDs, section IDs and unknown header/tail fields; it
does not fabricate them or claim that these geometry payloads form a loadable
world. Tricky's saved bounds omit a little surface curvature on some patches.
The writer can transform the power-basis coefficients to a Bernstein control
hull and expand the bounds, with a small rounding margin, before deriving a
bounding sphere. No sampled point among the 3,885 Garibaldi patches fell
outside those expanded bounds. The runtime mapping still needs validation.

The route converter produces an SSX 3 type-14 `WorldAIP` body from Tricky's
path records:

```powershell
py tools/ssx3_aip.py --iso $env:SSX_TRICKY_ISO --output .cache\gari.aip14
```

Its structural parser accepts both retail SSX 3 ARA1 AIP (129 AI paths,
eight race paths, six and 14 trailing records) and the converted Garibaldi
AIP (90 AI paths, 14 race paths). The generic CLI preserves the six Tricky
starter indices separately and leaves the trailing tables empty. The Garibaldi
world builder declares the main route as paths 0–5 and additionally creates
six native start markers from the six starter AI paths, plus recovery anchors
at the main route junctions and finish. Their final words link AIPath and
TrackPath indices, rather than world sections.
Garibaldi's 14 race paths include six sequential main-course paths: their
remaining-distance fields decrease from about 460,747 to 53,700 world units,
and each path's point distances nearly meet the next path's remaining-distance
value. Paths 6–13 are alternate branches. The native `Path_ReadEvent` maps
stored key 0 to runtime event 1 (finish) and stored key 18 to runtime event 11
(checkpoint). Tricky's finish key 9 is unsupported by that table. The custom
builder translates its first final-route finish event to key 0, and converts
its key-11 time gates into native key-18 checkpoints with matching IDs across
alternate routes. Other Tricky race commands are dropped. AI event keys are
restricted to the keys supported by SSX 3's native table.

## Prepare the local development assets

```powershell
python tools/prepare_bonus_tracks.py
```

Defaults use the SSX 3 ISO at the project root and the Tricky ISO one directory
above it. `--ssx3-iso`, `--tricky-iso` and `--overlay` override these paths.
The builder writes BAM.BIG, FE.LUI, CMNAMER.LOC and `custom-tracks.ready` under
`.cache/overlay`. The native file layer discovers that folder automatically,
so normal game startup needs no custom event command. The local SSX 3 ISO is
a hard link to `X:\dev\ssx3\SSX 3 (USA).iso` in this development checkout.
Generated disc assets remain ignored by Git.

## Integration boundaries

- `crates/ssx3-game/src/custom_tracks.rs` is now a host-owned catalog with a
  `Bonus` peak and a `Garibaldi` race entry, using stable string IDs and a
  Tricky archive source. Menu selection is a host flag while the native peak
  index stays zero. Starting Garibaldi activates its catalog entry and uses
  the normal ARA1 event/rules flow. Its IDs cannot index the original
  17-entry course table.
- `crates/ssx3-game/src/event_boot.rs` scans three peaks from the original
  event tables. This is a debug boot path, not the menu architecture.
- `tools/ssx3_bonus_menu.py` adds the Bonus text widget to `SP_PeakList` and
  creates separate one-item native menus `SPG_BonusGoals` (Race) and
  `BonusRaceLocations` (Garibaldi). Locale additions have new hashes and
  string indices; original locale entries are retained. The runtime accepts
  the Bonus widget by its name hash, bypasses career locks for custom rows,
  and switches these panels through the original UI object methods.
- `crates/ssx3-game/src/bonus_menu_mode.rs` ports EventSelect_SetMode and adds
  the custom-panel visibility pass. Original panel choices remain bounded to
  the original three peaks. New menu ordering, animation and navigation have
  not yet been observed in the running game.
- `state.rs` and `beintnewrace.rs` can return a separate, heap-allocated
  100-byte custom TrackInfo record. It supplies Garibaldi's locale name while
  retaining the native template's resource code and bounded peak metadata.
- `SectionMan_GetEventWorldSection` resolves an event through fixed guest
  event and section tables. A diagnostic override of its ARA1 result (8) to
  the appended world index (49) reached frame 300 but never read either new
  SSB stream. The section manager's logical mapping and load requests also
  need extension; changing this one return value is insufficient. The
  diagnostic code was removed after the run. The current SectionMan_Init
  port leases the template's existing logical map slot to GARI after the
  retail name mapping, and original peak selection restores the leased slot.
- The retail BAM has 49 world locations (indices 0–48). `SectionMan` has a
  fixed 50-node pool whose last node (logical ID 49) is its queue sentinel.
  The appended `GARI` world index 49 is valid in BAM, but assigning it as a
  new logical section ID would collide with that sentinel. Custom course
  selection therefore uses the separate mapping described above.
- `crates/ssx3-game/src/native_files.rs` supports the SSX 3 ISO, a replacement
  data directory, automatic local overlay, and `SSX3_DATA_OVERLAY_DIR`. The overlay BAM
  retains the original locations and adds `GARI` without replacing a course.
- `crates/ssx3-render/src/world_casters.rs` reads loaded terrain patches from
  the Nash world tree. Rendering alone will not provide gameplay collision.

The custom stream now contains 169 WorldSpline resources (542 segments),
in addition to patches, materials, textures and AIP. Geometry, global segment
links, lengths and the source's trailing flags are retained; the target-only
prefix and tail fields come from a retail spline template. Those extra fields
still need gameplay interpretation. No Tricky physics or gameplay scripts
are executed.

## Work still required for a playable race

1. Verify the provisional Tricky material/surface mapping, texture rendering,
   terrain orientation, scale and collision in a loaded `GARI` section.
2. Convert necessary models, instances, object collisions and spatial grouping.
   Confirm the spline fields actually produce working native rails.
3. Complete the surface mapping, ambiance/sky and course bounds.
4. Finish the native menu integration, confirmation, restart, return and
   custom result handling. The current added panels and world remapping are
   implementation work, not evidence of a playable end-to-end race.
5. Tests and replay gates are stopped at the user's explicit request. Do not
   infer runtime correctness from successful asset construction or compilation.

## External format references

The binary layouts were checked against
[SSX-Library](https://github.com/GlitcherOG/SSX-Library), notably its Tricky
`BDHandler`, `LTGHandler` and `COFB` readers and its SSX 3 `WorldPatch`
reader. SSX-Library is GPL-3.0; it is a reference checkout under ignored
`.refs/`, and no library source or game assets are included in this repo.
The SSX 3 and Tricky game images remain local user files.
