# Additional Single Event tracks

This checkout implements a fourth native **Bonus** menu category and a
Garibaldi Race importer. A manually played race has reached the native
results with six classified riders (Zoe: 3:45). Automated tests and replay
gates are stopped at the user's request; visual development uses the game.

## Prepare and start

The importer requires the USA PS2 images: SSX 3 `SLUS_207.72` and SSX Tricky
`SLUS_203.26`. No emulator installation is needed. On this machine:

```powershell
cd X:\dev\ssx3-decomp-more
$env:SSX3_ISO = 'X:\dev\ssx3\SSX 3 (USA).iso'
$env:SSX_TRICKY_ISO = 'X:\dev\SSX Tricky (USA).iso'
python tools/prepare_bonus_tracks.py
cargo run --profile game -p ssx3
```

Select a character, then **Single Event -> Bonus -> Race -> Garibaldi**.
The event uses the existing rules/confirmation and race loading flow.
No special event command is required for the menu path.

`prepare_bonus_tracks.py` accepts `--ssx3-iso`, `--tricky-iso` and `--overlay`.
Environment variables override its local ISO defaults. Missing files and
incompatible disc serials stop conversion with an explicit error. It writes
`DATA/WORLDS/BAM.BIG`, `DATA/UI/FE.LUI`, `DATA/LOCALE/CMNAMER.LOC` and a ready
marker under `.cache/overlay`. The game discovers that folder automatically.
`SSX3_DATA_OVERLAY_DIR` can select another prepared folder. Files absent from
the overlay continue to come from the SSX 3 ISO. Without prepared assets, the
game retains its original menu and events.

For direct development startup only:

```powershell
$env:SSX3_EVENT = 'GARI'
cargo run --profile game -p ssx3
Remove-Item Env:SSX3_EVENT
```

All derived resources stay ignored under `.cache/`. Neither ISO nor extracted
EA assets belong in Git. The project-root SSX 3 image in this checkout is a
hard link to the image under `X:\dev\ssx3`.

## Runtime architecture

`crates/ssx3-game/src/custom_tracks.rs` owns stable peak/course string IDs,
source metadata and the active custom event. Custom IDs never index the
original 17-entry TrackInfo or career tables. A separate 100-byte TrackInfo
copy supplies the Garibaldi display name while retaining bounded native race
setup fields. SSX 3 remains responsible for riders, physics, tricks, controls,
HUD, camera, countdown, progression, respawn and results.

The native UI additions live in the derived FE.LUI and locale file:

- A Bonus widget extends the existing peak list without changing the original
  three peak indices or their native default selection.
- Separate one-item native lists contain Race and Garibaldi. Their callbacks,
  focus, text and visibility use the existing UI methods. They belong to the
  native `SelectPeakGoal` and `SelectEvent` containers, and their text is
  refreshed after the native panel pass. One accept press advances one menu
  step, even when the new list occurs later in the same input traversal.
- Custom selection bypasses career locks. Native peak indices stay within
  their original bounds. The category is available in Single Event front-end
  flows, outside Conquer the Mountain progression.

`bonus_menu_mode.rs`, `custom_peak_widgets.rs`, `custom_ui_objects.rs` and
`custom_ui_screen.rs` implement the corresponding native UI functions;
`game/fe/uitemplatemap.rs` connects selection to the standard race flow.
The edited RefPack block retains its original alignment modulo 16 so the
following texture and font banks remain valid for native aligned loads.
The world stream also uses fixed 32 KiB CBXS/CEND envelopes, including end
padding. Literal RefPack data is split to fit that compressed read size, and
each appended stream begins at a 32 KiB boundary. Larger compressed blocks
overrun the native reader and corrupt models during loading.

The derived BAM appends a world location named `GARI` and preserves the
original locations and stream bytes. Its world index is 49. SectionMan has
50 logical slots and uses logical slot 49 as a queue sentinel, so the custom
course leases the template event's existing logical slot instead of extending
that table. `SectionMan_Init` resolves GARI from the loaded database and
updates that temporary mapping. The template residency row temporarily holds
only GARI plus the native sky and shared transport assets; Snow Jam's terrain
connectors and scripts are excluded. Selecting an original peak restores the
original mapping and residency row. Course terrain handles, section bytes
and hull references identify the appended world, not the template section.

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
| Materials | 117 | Type 0 WorldMaterial |
| Textures / lightmaps | 53 / 16 | Shared type 9 / 10 resources |
| Models | 627, with 699 hierarchical parts | Type 2 MDR meshes |
| Race instances | 3,236 of 3,393 source instances | Type 3 instances |
| Mesh collision resources | 412 | Type 12 triangle meshes |
| Sphere-tree collision resources | 56 | Type 12 native sphere bodies |
| Rails | 169 splines, 542 segments | Type 8 WorldSpline |
| AI routes / race routes | 90 / 14 | Type 14 WorldAIP |
| Instance and rail properties | 528 property records | Type 16 native world data |

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
texture references before packaging. It imports 627 of the 648 source
models, 117 of 125 materials and 53 of 121 textures. Local model/material IDs
are compacted together; the generated manifest preserves source-to-native
ID maps. Shared texture IDs retain their source offsets in the appended
global range. No model or material reference points into a removed slot.
Terrain stores the global texture ID directly; its source material is
dereferenced during conversion. MDR meshes retain their local material
indices and resolve them through the native model material table.

Tricky's linear 8-bit texels use native TexMan format 9; source entries
already marked as pre-swizzled retain their bytes and use format 10.
Linear palettes are converted to native CLUT index order. All 128-byte
image/palette headers explicitly store their relative data offset at +0x10;
the 0x1000 flag requires that offset rather than an implicit header size.
Lightmaps remain linear 32-bit images with the same offset convention.

The resulting texture leaf is 1,833,768 unpacked bytes and the shared world
stream is 5,361,088 bytes. Native shared textures use the separate
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
per-part contact properties, collider handles and rail flags. Its executable
script/global/process tables are empty: no Tricky gameplay scripts run.

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
isolation are implemented. Normal menu selection has loaded the course, and
a manual descent has reached Garibaldi's native results with all six riders
classified. The subsequent texture conversion changes still need visual
review. Restart, return, rails, respawn and original-course compatibility
remain to be observed in play. No automated tests or replay gates are run.

Source prefab animations are currently static. Source gameplay processes,
lights, particles and ambient audio are not executed/imported as Tricky
systems. Instance lighting is baked; terrain uses source lightmaps. The
native template sky and ambiance remain in use. Some target-only spline,
patch and material fields use retail defaults and still need refinement.

To add another course, register a stable catalog ID, append a separate BAM
location, generate its native routes/properties and add its own UI/locale
rows. Extend the explicit surface table when a new source type appears. Do
not enlarge or use out-of-range indices in official peak, course, career or
logical section tables. The current FE generator and metadata copy still
contain Garibaldi-specific labels/template choices and must be extended
alongside a new catalog entry.

## References

[SSX-Library](https://github.com/GlitcherOG/SSX-Library) is the external format
reference (GPL-3.0), particularly its Tricky BD/LTG/SSF readers and PS2 world
resource readers. Its checkout is ignored under `.refs/`; no library source
is copied into the runtime. The [DevvyDont C++ reference](https://github.com/DevvyDont/ssx3)
is available under `.refs/devvydont-ssx3` for readable comparisons. Generated
EE remains the authority for the hand-written Rust ports. No EA resource or
original binary is committed.
