# Additional Single Event tracks

The native **Peak Tricky** catalog imports all eleven playable Tricky worlds.
The eight main courses have Race and Freestyle scenery variants; Untracked
uses Race, and Pipedream and the Trick Tutorial use Freestyle (19 entries).
Automated tests and replay gates remain stopped at the user's request.
Visual development uses the windowed native game.

## Prepare and start

The importer requires the USA PS2 images: SSX 3 `SLUS_207.72` and SSX Tricky
`SLUS_203.26`. On this machine:

```powershell
cd X:\dev\ssx3-decomp-more
$env:SSX3_ISO = 'X:\dev\ssx3\SSX 3 (USA).iso'
$env:SSX_TRICKY_ISO = 'X:\dev\SSX Tricky (USA).iso'
python tools/prepare_tricky_tracks.py
cargo run --profile game -p ssx3
```

Select a character, then **Single Event -> Peak Tricky -> Race or Freestyle**.
The course list uses the original Tricky names. `prepare_bonus_tracks.py`
remains a compatibility entry point for the same preparer.

The preparer accepts `--ssx3-iso`, `--tricky-iso`, `--overlay`, `--course`
(repeatable), `--force`, `--worlds-only` and `--ui-only`. It derives one native
BAM per course/mode in `DATA/WORLDS/TRICKY`, frontend lists/locales, the original
Tricky course cards and logo, and an extended native MAPGFX archive. Per-world
JSON files record the import inputs and resulting resources. Unchanged
archives are retained. Missing or incompatible discs stop conversion.

The game discovers `.cache/overlay/custom-tracks.ready` automatically.
`SSX3_DATA_OVERLAY_DIR` selects another prepared folder; absent replacement
files continue to come from the SSX 3 ISO. Without prepared assets, the game
retains its original menu and events.

For direct visual development, `SSX3_EVENT` accepts these source codes:
`GARI`, `SNOW`, `ELYSIUM`, `MESA`, `MERQUER`, `MEGAPLE`, `ALOHA`, `ALASKA`,
`UNTRACK`, `PIPE`, `TRICK`. Add `:freestyle` or `:race` to select a mode;
the first catalog mode is the default. Example:

```powershell
$env:SSX3_EVENT = 'ELYSIUM:freestyle'
cargo run --profile game -p ssx3
Remove-Item Env:SSX3_EVENT
```

All derived resources stay ignored under `.cache/`. Neither ISO nor extracted
EA assets belong in Git. The project-root SSX 3 image is a hard link to the
image under `X:\dev\ssx3`.

## Runtime architecture

`crates/ssx3-game/src/custom_tracks.rs` owns stable peak/course string IDs,
source metadata and the active custom event. Custom IDs never index the
original 17-entry TrackInfo or career tables. A separate 100-byte TrackInfo
copy supplies the selected course display name while retaining bounded native race
setup fields. SSX 3 remains responsible for riders, physics, tricks, controls,
HUD, camera, countdown, progression, respawn and results.

With the prepared overlay, the native geometry pool retains its 53 block
descriptors and 128 KiB block size but allocates each payload on first use.
Releasing a section returns its payloads to the named heap. This prevents
unused geometry reservations from exhausting shared-texture memory: Alaska
uses 27 blocks while its full-resolution leaf textures need about 4 MiB.
The retail allocator's packing, resource sizes and texture pixels are unchanged.

The native UI additions live in the derived FE.LUI and locale file:

- Peak Tricky appears below Peak 1 with the native row spacing and text size.
  Host course IDs and retail UIObject IDs
  remain separate from UIMenu child selection indices.
- Separate native menus contain Race/Freestyle and their course lists. Custom
  rows do not index the fixed native three-peak event arrays. Each selection
  resolves a valid native template event (ARA1 or ASS1) for rules and scoring.
- Custom selection bypasses career locks and remains outside career progress.
- Original Tricky course cards come from `PS2LOAD.BIG`. The Peak Tricky logo
  is extracted from the `loa2` loading atlas. The native MAPGFX archive keeps
  its retail entries and adds the custom cards. Loading screens receive the
  selected original course card under the native template's SSH filename.

`bonus_menu_mode.rs`, `custom_peak_widgets.rs`, `custom_ui_objects.rs` and
`custom_ui_screen.rs` implement the corresponding native UI functions;
`game/fe/uitemplatemap.rs` connects selection to the standard race flow.
The edited RefPack block retains its original alignment modulo 16 so the
following texture and font banks remain valid for native aligned loads.
The world stream also uses fixed 32 KiB CBXS/CEND envelopes, including end
padding. Literal RefPack data is split to fit that compressed read size, and
each appended stream begins at a 32 KiB boundary. Larger compressed blocks
overrun the native reader and corrupt models during loading.

Each derived BAM appends one world location at physical section 49. Keeping
one archive per course/mode avoids growing the fixed SectionMan arrays or
accumulating every course's textures. SectionMan has 50 logical slots and
uses logical slot 49 as a queue sentinel; the selected course leases the
existing template event's logical slot. The native file layer selects the
course archive whenever the game opens its normal BAM path. It reserves the
maximum shared texture range across prepared archives before FX initialize.

Each archive also replaces ASKY's model, instance, materials and textures with
that course's original Tricky sky dome, centered through the native SkyBox
path. Original course lightmaps and instance lighting retain their source
colors. Original non-sky section bytes and IDs are preserved. The template's
terrain connectors are excluded from custom residency; returning to a retail
peak restores the leased map slot and residency row.

The original event supplies a bounded race setup, not an official record ID
for custom results. `custom_results.rs` retains the native result snapshot
but skips high-score, record and character-profile writes for custom tracks.
`custom_placement.rs` retains placement and skips career points/medals.
`custom_finish_dispatch.rs` keeps the native finish handler and suppresses
peak rewards for custom events. Run times and placements live in the native
per-session results. The template's official leaderboard is not returned for
the active custom course; there is no Garibaldi leaderboard or custom
save-file format yet.

The finish overlay remains native. Custom worlds leave both finish
presentation queues empty, so the finish sequencer chooses Results rather
than a cinematic authored for Snow Jam. The associated first-time-profile
and race-end profile updates are excluded for custom events as well.

Restart retains the active custom world and uses the native computer-rider
rebuild, start-marker placement and countdown. Continuing out of Results
uses the native front-end loading screen instead of the career transport
state. The custom context remains active during world shutdown, then the
front-end load path restores the leased section mapping and residency row.
The ordinary pause-menu Quit path reaches the same cleanup point.

## Converted Garibaldi resources

| Resource | Imported amount | Native representation |
| --- | ---: | --- |
| Terrain | 3,885 patches | Type 1 bicubic Bezier patches |
| Materials | 114, including retail interactive props | Type 0 WorldMaterial |
| Textures / lightmaps | 104 / 16 | Shared type 9 / 10 resources |
| Models | 622, including retail interactive props | Type 2 MDR meshes |
| Race instances | 3,246, including 10 native sign posts | Type 3 instances |
| Mesh collision resources | 412 | Type 12 triangle meshes |
| Sphere-tree collision resources | 56 | Type 12 native sphere bodies |
| Rails | 169 splines, 542 segments | Type 8 WorldSpline |
| AI routes / race routes | 90 / 14 | Type 14 WorldAIP |
| Instance and rail properties | 529 property records | Type 16 native world data |

`tools/tricky_assets.py` reads ISO9660/COFB/RefPack, PBD geometry and LTG spatial
lists. `tools/tricky_models.py` decodes prefab hierarchy, quantized vertices,
normals, UVs, strips and material assignments. `tools/tricky_collision.py`
reads SSF collision meshes, sphere bodies and property bindings.

The source and target terrain use the same descending power basis. The
converter preserves all 16 coefficient vectors and expands bounds using a
Bernstein control hull. It does not triangulate the terrain. Instance bounds
also contribute to the world bounds. Race/common LTG lists select scenery;
Showoff-only instances are excluded.

The builder follows Race instances to their models, material assignments and
texture references before packaging. It imports 104 of 121 source textures;
the native replacements below supply their own models/materials. Local model/material IDs
are compacted together; the generated manifest preserves source-to-native
ID maps. Shared texture IDs retain their source offsets in the appended
global range. No model or material reference points into a removed slot.
Tricky terrain `TextureAssignment` already indexes the SSH image table.
Terrain stores that image ID plus the appended global texture base; it must
not pass through the prefab material table. MDR meshes retain their local
material indices and resolve them through the native model material table.

Tricky's linear 8-bit texels use native TexMan format 9; source entries
already marked as pre-swizzled retain their bytes and use format 10.
Linear palettes are converted to native CLUT index order. All 128-byte
image/palette headers explicitly store their relative data offset at +0x10;
the 0x1000 flag requires that offset rather than an implicit header size.
Lightmaps remain linear 32-bit images with the same offset convention.
Tricky's 8x8 lightmap tiles use local (v,u) axes. Native `TessUV2` already
matches this: U advances along grid rows and V along grid columns, while
the geometric u parameter advances along columns. Keep the atlas pixels
unchanged. The converter maps patch UV2 endpoints to the first/last texel
centers, retaining shared edge samples and excluding neighbouring tiles
from bilinear filtering. Across 944 shared snow edges, this native axis
mapping gives a mean source border difference of 0.64 levels in RGBA8;
an extra transpose gives 12.49. The corresponding Rust UV2 port is retained
uninstalled in `custom_patch_uv2.rs`.

The generated ready marker records current stream sizes. Native shared textures use the separate
`BxStream SHAREDMEM` allocator. Terrain, models, instances and collision data
use the section allocator; textures do not consume its fixed 128 KiB blocks.
The single texture leaf is retained for this first course. Spatial subdivision
can be added later using the native shared-resource reference counts.

`tools/ssx3_models.py` constructs native MDR part tables and DMA/VIF mesh
chains, retaining source hierarchy and scale. It builds per-instance lighting
colours from source light matrices and light colours. Native collision meshes
use byte indices, splitting source meshes when necessary. Bounds cover each
group of ten faces. Serialized sphere trees use the layout consumed by the
native SSX 3 reader. `tools/ssx3_worldscript.py` supplies native instance flags,
per-part contact properties, collider handles and rail flags. No Tricky
gameplay scripts run.

`tools/ssx3_interactives.py` identifies the source placements by their MAP
internal instance names. It replaces the two speed pickups, three trick
pickups and ten intact/broken shortcut-panel pairs with retail ARA1 resources.
Models retain their retail DMA chains and materials; native Luno scripts
retain their internal offsets and remap only the panel's fragment handle.
Section-wide Snow Jam processes and setup functions are excluded. The native
focus/contact paths run the pickup setup and hit scripts. Pickup collection,
panel breaking and the repaired anger exclamation have been confirmed in play
by the user. A hand-written contact dispatcher is retained as an uninstalled
port in `custom_object_trigger.rs`; the confirmed retail dispatch stays active.

World shapes and lightmaps occupy 1,546 global texture IDs. TexMan's retail
non-bound free list begins at 1,500, which allowed the appended lightmaps to
overwrite global FX such as `exlm` (the angry rider's exclamation). Native
file setup now reads the shared counts from the actual BAM.SDB before TexMan
initialization and moves the free-list start past that range. Retail archives
retain the 1,500-slot boundary and the total table remains 2,000 entries.

The rail geometry preserves spline coefficients, lengths, bounds and global
segment links. Source metal style 13 maps to native metal surface 10. Native
rail active flags and instance collision bindings are applied by the original
world-data relocation path.

The AIP converter declares main race paths 0-5 and retains paths 6-13 as
alternates. It creates six starting lanes from the source starter AI paths,
recovery anchors at the main route junctions and a finish anchor. Source
finish key 9 becomes native stored key 0; source checkpoint key 11 becomes
native stored key 18, with matching checkpoint IDs across alternate paths.
Garibaldi's three main-course gates become checkpoint indices 0, 1 and 2.
Only supported SSX 3 AI event keys are retained. SSX 3's AI code consumes the
converted routes; the Tricky AI is not imported.

The native marker reader translates serialized types 0/1 into runtime
start/recovery types 1/2, and resolves each marker's AIPath and TrackPath
indices. Markers remain in their resident world-resource buffer. The native
pre-race loader creates and loads the SSX 3 competitors, calls AI_Restart to
place them on this grid, then advances to the round card and countdown.

Custom courses suppress the template's queued presentation choices (fly-over,
approach, gate idle and podium). Their camera paths belong to Snow Jam. Empty
presentation lists retain native state 0, so the pre-race synchronization
continues through normal rider loading instead of waiting for a template
cinematic. Original tracks retain their presentation choices.

## Surface policy

`tools/ssx3_surfaces.py` is the explicit mapping. It selects native SSX 3
surface records rather than carrying over Tricky friction or speed values.
Garibaldi's terrain uses the following entries:

| Tricky surface | SSX 3 surface | Extra native policy |
| --- | --- | --- |
| 0 Reset | 13 impassable powder | Ground-reset flag 0x2 |
| 1 StandardSnow | 0 packed snow | Standard contact |
| 3 PowderedSnow | 2 powder | Standard contact |
| 4 SlowPowderedSnow | 3 deep powder | Standard contact |
| 5 Ice | 4 ice | Standard contact |
| 9 Rock | 7 rock | Standard contact |
| 10 Wall | 8 rock obstacle | Standard contact |
| 17 NoCollision | 0 packed snow | Clear contact flag 0x1 |
| 18 ShowOffRampMetal | 10 metal | Standard contact |

Native section activation adds terrain flag 0x40; collision requires 0x41.
The no-collision patches remain renderable. Source object surface -1 remains
an obstacle with native wall-contact handling. Wood and metal rail mappings
are also declared; unsupported source surface IDs fail conversion instead of
silently inheriting the wrong enum. Appearance flags and contact feel still
need visual/manual assessment during development.

## Current limits and remaining development

The menu path, world remapping, native collision bindings and result
isolation are implemented. A manual Garibaldi descent reached native results
with all six riders classified and uniform snow. All 19 catalog variants
have opened in the windowed game. The Peak Tricky menu, original loading
cards, a same-session Garibaldi-to-Mesablanca switch and Alaska Race to
Freestyle switch have also been observed. These openings establish loading
and initial rendering, rather than a full descent of every course.
No automated tests or replay gates are run.

Source prefab animations are currently static. Source gameplay processes,
lights, particles and ambient audio are not executed/imported as Tricky
systems. Instance lighting is baked; terrain uses source lightmaps. The
original Tricky sky geometry/materials/textures replace the template sky;
native template ambiance remains in use. Some target-only spline,
patch and material fields use retail defaults and still need refinement.

To add another course, register it in `tools/tricky_courses.py`, regenerate
the Rust catalog and prepare its separate course/mode archives and UI rows.
Extend the explicit surface table when a new source type appears. Do not
enlarge or use out-of-range indices in official peak, course, career or
logical section tables.

## References

[SSX-Library](https://github.com/GlitcherOG/SSX-Library) is the external format
reference (GPL-3.0), particularly its Tricky BD/LTG/SSF readers and PS2 world
resource readers. Its checkout is ignored under `.refs/`; no library source
is copied into the runtime. The [DevvyDont C++ reference](https://github.com/DevvyDont/ssx3)
is available under `.refs/devvydont-ssx3` for readable comparisons. Generated
EE remains the authority for the hand-written Rust ports. No EA resource or
original binary is committed.
