# Animation contact delays

## Source behavior

Main0/Sub256/257/258 include an authored debounce value at word6. Every such
descriptor found in the supplied worlds uses1.0s. AnimNode198810 reads the value
at parameter+20, multiplies by60 and stores the integer at self+18.
Its contact handler198eb8 rejects a nonzero self+1c, then rearms that counter
from self+18 before starting the contact graph. Update199030 decrements a
positive counter. Animation clip position and playback rate are separate.

The source factory13c5d0 passes a context pointer only when the script has
contact context (`script+d0`); constructor198af0 uses that presence to start
the initial counter. A focus-created actor starts with counter0. The exact
source code excerpts are retained in ignored
`.cache/tricky-animation-debounce-v51.disasm.txt`.

## Native mismatch and correction

SSX3 ModObj_v40/355770 first gates contact dispatch on its native counter at
WorldObj+20. WScriptMan_OnObjectTrigger then calls virtual+148 with literal0.5s,
returning at30a240. For native AnimObject/Delta/Combo, all three vtables
490b10/48ea70/48ec28 point that slot, with zero adjustment, to ModObj_v41/355858.
That leaf multiplies seconds by the configured native tick frequency and
stores an integer counter. It previously replaced the source1s with0.5s.

The compiler now follows each imported animation factory3/4/5 with builtin133:
owner RID, exact source seconds and whether its graph inherits contact context.
The adapter registers only a live animation owner of native kind1/2/3, checking
the instance backlink. Contact-origin creation, including an ActOn/deferred
child with copied contacts, initializes the counter through the real native
355858 leaf. Focus graphs cannot initialize it from an unrelated transient
contact. Detached graph scopes clear contacts and therefore do not acquire an
initial guard.

The existing handwritten ModObj_v41 entry substitutes the registered seconds
only for the hard-coded0.5s call returning at30a240. Other callers and explicit
timer resets retain their supplied argument. The original FPU conversion,
native timer field and8-cycle body remain; F12 is restored before return.
There is no host wall clock, per-frame scan or custom decrement loop.

Records retain owner/instance/node identity, discard stale identities on use,
and replace the previous record on focus allocation. A direct node lookup is
bounded by source owners. Restart/course changes clear the records. An actor
which has not been registered keeps the retail behavior. Playback curves,
animation bounds/rate, rider motion, boosts and course timers are untouched.

Builtin133 is intercepted before the retail function-table call. It is outside
the defined retail builtin range, just like the existing imported adapters;
the raw adjacent word at that index is not a callable retail function. Late
imported callbacks with no active custom course are consumed by the adapter
range rather than dispatched into that data.

Native compilation and exported-script inventories establish integration.
`.cache/build-tricky-animation-debounce-v51-final.log` succeeds in1m30s;
`.cache/prepare-tricky-animation-debounce-v51-final-all.log` prepares all19
variants. Final BAM/source inventory
`.cache/tricky-animation-debounce-v51-inspection.json` finds697 exact source
owner/node/delay records across15 variants (373 owners per-variant combined),
all1.0s. Every imported factory call is immediately followed by the three-arg
registration:1497 serialized sites, comprising1457 AnimObject,30 Delta and10
Combo calls. Their graph-context flags are257 zero/1240 one. These include
duplicated graph/continuation sites and are not runtime contact counts.
The largest inspected WSD is379796 bytes (Merqury Freestyle), covered by the
existing oversized section allocation.

Repeated contacts, initial/deferred contact timing, focus travel and restart
still require ordinary gameplay observation. No automated tests, replay, gate,
browser build or game/window control is used for this work.
