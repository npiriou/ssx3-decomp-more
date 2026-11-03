# Invisible force owners and their scripts

The world builder formerly discarded every invisible instance listed in
`source_boost_instances`. TFX2 retains its force descriptor, but removing the
instance also removes its focus script and prevents ActOn from resolving it.
An invisible source property already has its visible flag cleared; retaining
the instance does not require displaying its model.

## Tokyo focus effects

Source owners1013 (`Mdl_twinAirShaft_BOOST_5`) and1212
(`Mdl_twinAirShaft_BOOST_0`) each have two independent bindings:

| Owner | Focus channel0 | Contact channel1 |
| --- | --- | --- |
| 1013 | chain376, Main2/Sub0 at43944 | chain377, Main0/Sub18 |
| 1212 | chain374, Main2/Sub0 at43688 | chain375, Main0/Sub18 |

The importer now retains force owners with an authored focus binding.
Ordinary native focus callbacks create the already implemented independent
emitter. Native property serialization retains visibility0, contact flags2
and surface-1. The lift descriptor remains in TFX2; Main0/Sub18 still does
not create another force in the Luno compiler.

## Alaska shared contact ownership

Owner794 (`Mdl_ForceWind_5000`) has no focus binding. Its contact chain102
creates Main0/Sub7, mode1, duration0, before launching emitter children on
owners798/983/797. Restoring that contact graph alone is insufficient.

Original Tricky dispatch13c99c constructs the force receiver140498 with
type7 and attaches it to instance+e4 through WorldObj13a840. Constructor
140498 stores the mode at+60 and duration in source60Hz ticks at+58/+5c.
Update140688 queries the receiver's spatial overlap list; mode1 remains
alive while a rider overlaps, then dispatches its restorable kill when no
overlapping rider keeps it alive. Its inherited contact slot+80 is the
no-op13b7b0. Thus an existing receiver consumes later contacts without
recreating the graph. The source ELF has no direct call from this force
receiver to WorldObj's contact-script method13aaf8.

The TFX2 adapter applies the force without constructing that receiver. The
importer now retains the contact owner and represents its shared lifetime
through the existing deferred graph/busy scope. The first contact schedules
one monitor and launches the three authored emitter children; further
contacts are rejected by the ordinary scope guard. The monitor uses native
rider collision hulls and the transformed mode2 box. It rearms the contact
only after no active rider has positive penetration. No arbitrary cooldown,
repeated-effect timer or force tuning was introduced. The detailed contract
and remaining runtime evidence are in `tricky-force-ownership.md`.

## Existing native ModObj contacts

Native ModObj_v40/355770 already waits half a second between eligible
script contacts, then calls ModObj_RunScriptEvent19b8/34fe00. The latter
ignores self and forwards triggerB/triggerA/rider to2d19b8, which supplies
the script manager and calls OnObjectTrigger30a060 (kind2). This is already
the contact path used by the imported cracked panes; an additional callback
would duplicate it. The inspected wrapper is retained uninstalled in
`custom_live_object_trigger.rs`, with empty overrides and no tests.

Resource inventories establish serialized bindings, not observed gameplay.
No game launch, automated test, replay, gate or browser build is part of
this investigation.
