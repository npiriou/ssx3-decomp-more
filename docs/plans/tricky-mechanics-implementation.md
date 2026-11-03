# Tricky mechanics implementation

Full scope requested 2026-11-03; baseline audit: `7e01931`.
Automated tests and replay gates remain disabled by the user. Use native windowed play and source inspection.

| Requirement | Current status | Completion evidence required |
| --- | --- | --- |
| Freestyle solo, native slopestyle scoring | Implemented, Garibaldi manual run to results | RAM: one rider/one human, zero AI/extra in working/live settings. HUD uses medal targets, no opponent |
| Tricky initial timers | Implemented, source data extracted | USA ELF catalogue read by stem. Native Garibaldi 7200 ticks, Alaska 8100, tutorial budget 0/expiry disabled; normal slots 9000 hundredths in source |
| SOP checkpoint time awards | Implemented; remaining route/lap observations pending | All 22 stations exported in SOP routes. Garibaldi manual +75/+75/+45 once each (budget 18900 ticks), Alaska first +150 observed. Tokyo rearm and other routes still require manual observation |
| Pipedream eight breakable walls | Pending | Wall collider removed, source fragments activated, all eight links |
| Merqury teleport | Pending | Entry to source destination with native rider/camera/physics synchronized |
| Animated colliders | Pending | Elysium kickers/door; Merqury sewer gates; Aloha barriers/kicker; Mesa trees/bridge |
| Mesa rail transitions | Pending | NonGrind kept distinct, rails 87/88 activate with tree sequence |
| Tokyo cracked glass and pinball obstacles | Pending | Twenty distinct glass panes, flippers/doors animate and collide correctly |
| Other destructible props | Pending | Snowdream fences/lanterns, Alaska icicles, Untracked branches and source hide/fragments links |
| Scripted resets | Pending | 985 source hosts; volume versus actual geometry contact; preserve tunnels and native terrain reset |
| Roller response | Pending | Native equivalent or source law, including launched prop parts; preserve existing bounce |
| Decorative movement and effects | Pending | Train mover, helicopters/fans, fireworks/particles, UV/texture/flag/fence effects |
| All 19 variants prepared | Rebuilt for solo/TFX2/SOP; rebuild again after object mechanics | Current manifests use SOP in Freestyle. Manual Garibaldi, Alaska and Tutorial open in new build |

Do not mark the overall goal complete until every row has authoritative implementation and appropriate manual evidence.

## First implementation evidence

- Native build log: `.cache/build-showoff-solo-v2.log` (successful). No tests or replay gates.
- Garibaldi: `.cache/visual-showoff-solo-gari-v2.log` and RAM snapshots in `.cache/showoff-solo-gari-v2`.
  The source checkpoint awards appear at log lines 217, 390, 539. At frame 16096 the sole rider's native event budget was 18900 ticks and elapsed clock 15738. The run then reached native Slopestyle results with a recorded score of 2750.
- Solo is enforced in `BENewRaceInt_Commit`, after all setters. An earlier attempt to set zero AI only in `SetEventType` did not survive later native setup. The committed working/live structures now have total=1, humans=1, extra=0, AI=0.
- Alaska: `.cache/visual-showoff-alaska-v2.log`: source seed 13500 hundredths -> 8100 ticks and first SOP +150 s.
- Tutorial: `.cache/visual-showoff-untimed-v2.log`, `.cache/showoff-untimed-v2`: one rider, event budget 0 and timer-enabled flag 0, count-up HUD instead of immediate expiry.
- Initial times are read from the provided `SLUS_203.26` ELF, twelve 28-byte records at file offset `0x233f28`, field +12 in hundredths. Names/stems are resolved through ELF load segments. This is data extraction, not execution or an emulator.
- `TFX2` replaces the old 16-byte TFX1 header with 24 bytes, adding the source clock seed and mode. TFX1 remains readable. Freestyle uses its source SOP path table (Elysium's main chain ends at index 6 rather than Race's index 7).
- SOP events use stored key 12 (runtime 5), value `(seconds<<16)|logicalGroup`. Native camera checkpoint dispatch is bypassed for these custom time awards. Only humans are awarded, once per logical station; the Tokyo altitude return clears the set for another circuit. Raw elapsed time is unchanged.

## Native object integration findings for the next work

These are implementation leads, not completed object mechanics.

- `custom_resolve_resource.rs` retains the inspected 0x3a8cd0 port uninstalled. That entry inserts a resource; do not call it for lookup. Resident type-3 lookup: app=`*(0x4a28a8)`, module=`*(app+84)`, world=`*(module+10)`, cache=`*world`, banks=`*(cache+8)`, bank=`banks[section]`, refs=`*(bank+1c)`, count=`*(bank+20)`, word=`refs[index]`, pointer=`(word>>8)<<2`. Require a live low-byte reference count and reject the empty sentinel gp+16e0. A miss waits for residence.
- `custom_anim_object_factory.rs` retains the exact native AnimObject factory 0x2fbcb8. It takes sret Vec3 A0, count A1, 16-byte named args A2. Param 0 is an instance RID or -1 for the script's current instance. It attaches modifier type 1 to an existing node, otherwise allocates 0x6c and invokes `AnimObject_ctor(new,1,1,Instance*,params)`. Eleven parameters: types `[int,int,int,float,float,float,float,float,int,int,int]`. The constructor still needs study before mapping source modes to it.
- The actual native MDR relocation callback is 0x3abe40 (already typed in `game/world/worldview.rs`). Its following virtual slot +0x30/+0x34 relocates nested model data; inspect that existing typed pipeline before copying curve payloads. The live resolver vtable observed was 0x495090. Tricky part animation data is currently discarded: native MDR part-table word +8 is written as zero by `ssx3_models.py`.
- Source PBD curve header is BasePosition vec3, BaseRotation vec3, action/channel mask, channel count, offsets-start, then per-channel pointers. Each channel has count/offset followed by cubic coefficient quartets and start/end time. SSX3's WorldMDR reader exposes the analogous third-pointer block but does not fully interpret it; do not assume relocation conventions are identical.
- `WorldObj_BuildMatrices` already has a typed body in `game/object/instancenode.rs` but is not in that unit's override list. `WorldObj_ctor` is 0x34fb00; instance+0xc links its dynamic node. Native animations/modifiers should update both rendering and collision through this structure.
- Do not trust the old structs document's description of instance flag bit 1 as simply dead: `cPS2ChunkResolve_v13` initializes instance flags with `|2`. Study real hide/dead-node operations before mutating flags.
- A typed, uninstalled contact dispatcher is in `custom_object_trigger.rs`: rider interface is based at Rider+6c0, contact-A+50 holds Instance*, instance+78 is its compact RID. Existing typed `rider_states::rider_update_progress` is another possible contact-hook point; preserve native pickup/sign dispatch.
- `custom_race_time_limit.rs` and `custom_draw_race_time.rs` retain inspected ports uninstalled. Neither owns the Slopestyle time budget; it is app->eventEntity (+c0), deadline +78 and enable +88. AI+0c is elapsed race ticks. These fields were confirmed by the existing typed `Rider_CheckRaceFinish` and native snapshots.
