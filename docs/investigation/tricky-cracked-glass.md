# Tricky cracked-glass source contract

Static investigation of the supplied USA `SLUS_203.26`, 2026-11-03. This handler is still pending; the Snowdream correction takes priority. No game run or automated test was used for this investigation.

The ELF load segment maps file offset0x1000 to VA0x100000. `cCrackedNode` has name0x36dd28, RTTI function0x149748 and vtable0x36cbd8. Original instructions, including decoded PS2 VU operations, are retained in the ignored `.cache/tricky-cracked.disasm.txt` and `.cache/tricky-cracked-material.disasm.txt`.

| Source function | Contract |
| --- | --- |
| Constructor0x145458 | Params+0xc is lifetime seconds, converted to frames60 at node+0x34. Params+0x10 is strength at node+0x3c. Set contact cooldown+0x38 to30, apply the initial contact through0x145808, initialize private material state at node+0x40. |
| Contact0x1457e8 | Apply another contact only when cooldown+0x38 equals0. |
| Damage0x145808 | If contact exists and strength is positive: subtract `abs(VU_dot(contact+0x10, contact+0x20) * float(contact+0x30)) * float(0x3d1374bd)` and set cooldown30. The multiplier is approximately0.036. The VU reduction includes all four lanes; ordinary velocity/normal vectors have w=0. No eight-metre-per-second threshold or fixed damage was found. |
| Update0x1455a0 | Decrement positive cooldown once per source tick. Decrement positive lifetime and invoke restorable kill when it reaches0. Otherwise, when strength<=0, resolve source end column4. A populated end graph becomes a separate script node with null contacts; without one, use ordinary node teardown. |
| Message0x1457a8 | Command1 replaces lifetime in frames60 from its float-seconds value. Command2 replaces strength. |
| Private materials0x142af0/0x142c78/0x142d40 | Copy per-instance material records for materials with a flip table; never mutate the shared material. Negative initial frame selects a cracked frame from1..count-1, with random selection only for count>=3. A two-frame table selects1 without consuming RNG. This is not progressive texture selection from remaining strength. |

Both Tokyo variants include20 such panes. Every pane uses source material43, flipbook1, frames `[50,69]`, lifetime-1 and strength5. That material is also used by other source instances, so modifying its shared frame/texture would affect intact scenery.

The first pane is source7 `Mdl_Glass_Pane_5000`. Contact graph587 constructs Cracked(-1,5); graph588 is an empty source column2 latch. End graph589 tombstones the pane, acts on support6 through graph590, then activates fragments8 through MeshAnim graph591. The source end column is already retained by the importer. Implement the actual health/contact gate and private cracked material, then dispatch that existing graph rather than duplicating the support/fragment behavior in a host table.
