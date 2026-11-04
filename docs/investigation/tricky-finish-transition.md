# Native finish transition on imported courses

This investigation follows the reported Tokyo finish stall in Race and
Freestyle. It does not establish that the stall has been resolved. Automated
tests, replays and game/window operations remain disabled for this work.

## Native ordering

- `Rider_OnFinishRace` (`125108`) marks the rider finished at `+470`, then calls
  `GameModeMan_OnRiderFinished` (`238358`). The installed dispatch retains the
  native mode handler before submitting the result snapshot.
- The selected handler in saved Tokyo Freestyle RAM is `GMHandler0_OnRiderFinished`
  (`239230`); saved Race RAM selects handler1 (`23a760`). Their completion gate
  is `AI_AllPlayersFinished` (`12a250`), which
  checks human players' riders at `+470`, rather than waiting for every AI
  competitor. Quick-event initialization selects heat 3. Heat 3 writes
  `GameModeMan+9c = 1`; intermediate heats intentionally do not.
- `GameStateFinish_Enter` (`233c50`) sets phase `+10 = 0` and arms delay `+14`
  for 180 ticks at 60 Hz. The constructor (`233c10`) puts the state vtable at
  **object+0c**, default next state 7 at `+0`, phase 2 and delay 0.
- `GameStateFinish_Update` (`233cd8`) advances phase 0 only after the native
  mode's result gate (`+98` / `+9c`) permits it. Imported courses already skip
  the rider speed wait, preserving the native S5/S1 setup. They also avoid
  the template career calls; these policies are unchanged here.
- Phase 1 waits for presentation list 0, tries to show `finishov`, and enters
  phase 2. The delay independently opens `GameUI_OpenFinishScreen` (`20cc60`)
  after three seconds, unless its module-state gate suppresses the request.
  The UI creates the dialog at that later point. An earlier dictionary miss
  for `finishov` is therefore normal, and must not be converted into an
  immediate results transition.
- The native finish UI action advances to `GameStateResults_Enter` (`236da0`),
  which opens results screen 7. Race normally selects finish screen `0c`;
  solo Freestyle selects `0d`.

The retained translation `custom_gm_handler0_finish.rs` covers the studied
native handler, including native call/event continuations. It has empty
`OVERRIDES`, is not registered as a module and does not replace the runtime
handler. Its equivalence has not been established by execution.

## Evidence limits

The saved Tokyo samples in `.cache/tokyo-laps-v4` and
`.cache/finite-materials-tokyo-v29/ram-1067.bin` all have the human rider's
finish timer at -1 and the result-ready flag at 0. They are running-course
samples, not captures of the reported failure. The allocated finish object
still has its constructor's phase 2 / delay 0, which does not establish that
the state is active. An earlier inspection used vtable offset +8; the corrected
read-only inventory uses +0c. The raw field used by the overlay gate is called
`module_gate_state`, without inferring a game-state enum from it.

No recent manual finish sample was available during this pass. No completion
flag is forced, no native delay is removed, and no missing-widget fallback
is installed on that evidence.

## Bounded observations during ordinary play

`custom_finish_trace` records native finish milestones to
`.cache/diagnostics/finish-<pid>-<timestamp>.log` when an imported course is
active. It records rider-finish dispatch, handler return, finish-state entry,
delay arming/expiry, mode/presentation waits, dialog lookup, finish-screen
request/return and results entry/request/return.

Each record includes the course/run, cycles, mode flags, raw module gate,
manager/handler/heat, `+98`/`+9c`, human rider completion/DNF flags and supplied
finish object's phase/next-state/delay. A lookup's detail value is the actual
dialog pointer, zero on a miss. No memory scan guesses the active finish
object. The positive delay value and advancing rider timers are excluded
from the change key. Identical stage/state observations are suppressed, with
a cap of 64 records per course/run; restart clears that budget. Records are
flushed so a stall/exit retains the last observation. File failures do not
change native progression.

The observer reads validated RAM addresses only. It writes no native RAM,
registers, cycles, physics, result flags or UI state. Hooks after native calls
can be absent if a call unwinds; absence alone does not prove that call hung.
The observer neither launches the game nor drives a route or replay.

## Preserving a gated menu request (v62)

The v61 rail-contact change is installed separately in c96f957. This pass
examines Race's handler1 as well as the earlier Freestyle handler0. Its two
12a250 gates also inspect human players, not all racers. On the final gated
human notification, it estimates unfinished racers' times through122d78,
sorts them and sets manager+9c at heat3. It does not directly read a Tricky
lap counter. Waiting for AI riders is not established as the cause of the
reported Tokyo stall. The exact handler1 translation is retained uninstalled
in `custom_gm_handler1_finish.rs`, without tests.

The UI has two distinct interfaces. `GameUI_OpenScreenForState`20a8f8 maps
game states2/7 to a screen and can reject a nonzero module state below10.
`GameUI_OpenFinishScreen`20cc60 correctly calls the direct
`GameUI_OpenScreen`20ab50 with finish-screen IDs0xc/0xd; Results_Enter
correctly calls20a8f8 with game state7. The retained uninstalled
`custom_game_ui_open_screen.rs` covers20a8f8; those interfaces must not be
substituted for one another.

An actual request-loss path exists in `custom_finish_update::overlay_timer`:
it decremented the delay to0 before checking the module-state gate. If that
gate was active on the expiry tick, no UI-open call occurred and subsequent
updates saw no pending timer. An imported course could therefore remain in
the finish state without ever retrying its sole menu request, even after
the module became eligible.

Imported events now retain1 pending tick only on that explicit pre-call
rejection. The normal gate is checked on the following update; when it
permits the request, the ordinary native screen-opening call runs once
and the delay stays0. There is no timeout, forced result-ready flag,
skipped delay, missing-widget fallback or repeated request after a screen
has actually been queued. Retail events retain their original policy.

This corrects the demonstrated lost-request path. It does not establish
that it was the exact stage of the user's Tokyo failure; the current
Race/Freestyle finish interaction still lacks a fresh gameplay observation.

The actual direct screen factory20ab50 is also retained uninstalled in
`custom_game_ui_open.rs`. IDs0xc/0xd construct their native0xa4-byte
`finishov` states and push them through39f320, with no course/career or
already-active-screen filter in those branches. Race uses vtable473e00
(Init1e7bb0, Update1e8098); Freestyle uses473d28 (Init1e8200,
Update1e87b8). Their Init paths are retained uninstalled in
`custom_race_finish_ui_init.rs` / `custom_freestyle_finish_ui_init.rs` and
explicitly clear timer+9c after base overlay
initialization. Required placement/score widgets are not null-guarded;
screen creation/loading remains a meaningful runtime boundary, but neither
an uninitialized completed-Init timer nor a direct course-index lookup is
supported as the cause.

A read-only source/current-bank inventory confirms that the entire
decompressed `finishov` definition in the prepared OV.LUI is byte-identical
to the original disc:8540bytes, SHA256
`2f7ae9db7767ade046c484e876dd364c798e7191057269183152f73696125cf8`.
Evidence: `.cache/finish-ui-bank-v62-inspection.json`. This establishes
resource preservation, not successful native loading/initialization.

The final native build succeeds in1m27s in
`.cache/build-tricky-finish-pending-v62.log`. The retained investigation
ports remain unregistered and were not compiled or executed by that build.
No importer/assets change, automated test, replay, gate, browser build or
game/window operation is performed.

## Preserving a gated results-screen request (v64)

The v62 correction covers the delayed `finishov` request. The later results
screen has an independent one-shot request: Results_Enter236da0 clears
`self+8` and calls OpenScreenForState20a8f8 with7. That function returns
before allocating or queuing any screen when the module gate is nonzero
and signed-less-than10. The existing typed Results_Update236e60 only waits
for `self+8 == 1`, which the missing UI would normally set. It never opens
the results screen again. A gate active at this second request can therefore
leave a results state waiting for a UI action that cannot occur.

For imported courses, the actual20a8f8 entry now records only that explicit
rejection when called from Results_Enter's236e40 return site. This wrapper
then runs the unchanged generated native body once. Checking at the real
callee entry covers calls reached through a generated Results_Enter
continuation after a previous call yielded; an Enter-only Rust hook would
not cover those continuations.

The pending record contains the course, module and Results state identities.
Results_Update waits for the same native gate to permit opening, consumes
the record before making its one retry, and calls the ordinary state7 screen
selector. Already-created screens are never registered as pending. A new
Results_Enter, restart, changed identity or an already-completed results
state clears the record. No completion/rank/score/input flag, game-state
number or loading-state value is forced, and no missing-widget/timeout
fallback is installed. Retail state flow retains its original behavior.

The additional call uses the native Update frame and real236e90 return
site. The supplied SSX3 ELF confirms that this continuation only restores
RA at stack+0 and returns with stack+0x10. A UI callee that yields can thus
resume through the existing generated epilogue without a synthetic PC or
an unregistered host continuation. Passive records distinguish the gated
request and its retry.

This fixes another demonstrated request-loss path; no current Tokyo
Race/Freestyle failure sample establishes it as the user's exact stall.
Gameplay completion remains unproven. Assets remain the19 v63 archives,
11 sound banks and7 TVM files. No automated tests, replays or game/window
operations accompany this correction.

Both generated dispatch forms include the20a8f8 wrapper slot. Native build
`.cache/build-tricky-results-pending-v64.log` succeeds in2m02s; no Rust
runtime change follows that build. The resulting executable is
`target/game/ssx3.exe`. No browser build was run.
