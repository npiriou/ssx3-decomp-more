# Tricky independent particle emitters

Static source investigation of the supplied USA discs,2026-11-04. No game run,
automated test, replay or gate is part of this work.

## Source indices are not SSH directory indices

The Tricky FX catalogue starts at ELF VA33edf0,38 records of12 bytes:
`{name[8],mip}`. The first five effects are `part,snfl,clod,spry,halo`.
The particle SSH directory instead begins `brk1,brk2,brk3,ndl1,ndl2`.
Source effect18 is `str1`,19 is `str2`,22 is `strk`; directory entry18 is
`strk`, which caused the earlier incorrect pop-effect description.

SSX3's independent catalogue at4891b0 starts `part,ftr0,ftr1,ftr2,fog0`.
Its effect20 is `tmb7`, although **SSH directory** entry20 is `part`.
The v33 pop adapter's hard-coded20 therefore selected a tombstone image,
not a neutral white particle. The v41 conversion supersedes that mapping.

`ssx3_particle_sprites` reads Tricky's catalogue and named SSH directory from
the disc, then imports the requested images as ordinary native kind9 world
resources. The existing indexed SSH conversion retains source texels/palette
and PS2 layout declarations. Images are interned by name per course variant;
sky import starts after the new resource IDs through the normal SDB counts.
No native rider FX slot or shared texture is replaced.

## Recovered blend arithmetic

Original Emitter_Render1d8bc8 selects a graphics style through table392cf8.
Graphics virtual slot1e0/1e9418 writes that style to state bytes15/17.
GsPkt_AddAlpha1c03e8 uses jump table390860 to emit these GS ALPHA values:

| Source emitter blend | Source style | GS ALPHA | Native preset |
| --- | --- | --- | --- |
| 0 |5|48|7|
| 1 |3|44|5|
| 2 |2|89|4|
| 3 |1|6a|3|
| 4 |4|46|6|
| 5 |0|2a|1|
| 6 |6|81|8|
| 7 |7|42|9|

The provided course effects use0,1,4. Native Emitter_Render's shortcut table
only provides presets7,5,9, so copying source blend4 did not select its
original0x46 arithmetic. The converter resolves source style/jump tables
from the ELF and maps the emitted ALPHA value to the existing native preset.
Retained source disassembly: `.cache/tricky-emitter-render.disasm.txt`.

## Ownership and native rendering

Main2/Sub0 dispatch13d130 ->147cf8 creates a separate cEmitterNode (type1003,
process argument4), rather than replacing the source object's WorldObj.
It keeps the source matrix pointer at node+18 and description at+1c;
Emitter_Setup1d8490 transforms its emission basis using that authored matrix
directly. This constructor neither calls the current object's dynamic matrix
getter nor binds the emitter to its destruction. Source evidence is retained
in `.cache/tricky-emitter-node-ctor.disasm.txt`.

Each imported owner has an invisible, collision-free native host. AddParticleData25
creates/reuses its native Particle actor and modifier list. The complete51
source fields retain count, trails, time window, time scale, size/life ranges,
spawn/velocity axes, gravity and four RGBA stops. Extra native frame count1
and frame speed0 explicitly keep the source's static sprite. Native emission,
integration, retirement, billboard generation, sorting and texture upload remain
unchanged.

Descriptor sprite49 uses a TX tag (54580000 plus the low16-bit texture handle);
blend50 uses a BP tag (42500000 plus the native preset). Already typed native
Emitter_Render3708c0 recognizes only these tagged values at its existing texture
and blend selection sites. Untagged emitters retain their original table lookups,
register writes and cycle charges. Retiring imported actors can still resolve
their marked values after a course stops being active; they never index outside
the native FX table. No new renderer, VM opcode, host particle integrator or
global FX-table rewrite is used.

Native Emitter_ctor370018 initializes its sprite phase184 to0 after calling
BoardSparkEmitter_ctor2f7a68(self+10). Its inspected Rust translation is retained
uninstalled in `custom_emitter_base_ctor.rs`, with no override entries or tests.
Thus the explicit zero animation speed does not leave an uninitialised frame.

Only exact exported `(owner,node offset)` Main2/Sub0 consumers are inventoried.
Collision emitters (Sub2), spline movers (Sub1), source sound mappings and the
remaining source mechanics are separate pending work. Compilation/resource
inventory does not establish in-game appearance or whole-course acceptance.
