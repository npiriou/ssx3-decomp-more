# Native finish transition on imported courses

This investigation follows the reported Tokyo finish stall in Race and
Freestyle. It does not establish that the stall has been resolved. Automated
tests, replays and game/window operations remain disabled for this work.

## Native ordering

- `Rider_OnFinishRace` (`125108`) marks the rider finished at `+470`, then calls
  `GameModeMan_OnRiderFinished` (`238358`). The installed dispatch retains the
  native mode handler before submitting the result snapshot.
- The selected handler in saved Tokyo RAM is `GMHandler0_OnRiderFinished`
  (`239230`). Its completion gate is `AI_AllPlayersFinished` (`12a250`), which
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
