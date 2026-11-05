# Tricky course crashes: spline distance units

## Snowdream moving-object corruption

The Snowdream stall at about 20 seconds stopped game updates in
`Cell_GatherObjects` (`0x3309f8`). A moving chairlift instance had a spatial-list
link pointing to itself and a translation of approximately
`[4.5e12, -4.4e11, -6.57e12]` centimetres. The list failure followed the invalid
position; changing traversal or insertion would conceal the data error.

The source was spline 55, a 43-segment path used by a 15-instance
`MultiSplineModifier`. `SplineModifier_EvalSegment` (`0x345048`) reads the
inverse arc-distance polynomial at segment offsets `0x50..0x5c`:

```text
local_distance = distance - segment.start_distance
u = ((a * local_distance + b) * local_distance + c) * local_distance + d
position = basis * [u^3, u^2, u, 1]
```

Tricky stores its length, cumulative distance and geometry in centimetres,
but authors this polynomial for an input in metres. SSX 3 supplies centimetres
to the polynomial. The importer copied the coefficients without converting
their units. One captured clone sample produced `u = 1720.63`; the same
authored sample with the correct distance unit produces `u = 0.471529` and a
position inside the course.

`tools/ssx3_splines.py` now divides `[a, b, c, d]` by
`[1e6, 1e4, 1e2, 1]`. Lengths, start distances and geometry retain their
centimetre values. The runtime evaluator and spatial-list algorithms retain
their original behavior.

## Tokyo Megaplex circuit limit

Both Tokyo AIP and SOP contain a pass count of four: the initial tube ascent
and three full circuits. `custom_course_rules` previously discarded this
count in Freestyle, allowing unlimited ascents. Freestyle now consumes the
authored count too. SOP time awards remain separate from pass counting and
can be earned again after an ascent starts the next circuit.

The regression tests exercise the initial ascent and three laps through the
actual mouth/lift logic, repeated contact without an extra count, the final
disabled ascent, finish suppression and time awards on circuit/linear courses.

## Validation

- 11 Python importer tests pass, including distance conversion and texture
  palette preservation in both source palette layouts.
- All 19 derived archives were rebuilt. Original BAM member data is preserved;
  custom streams decompress and their resource/chunk/FX/movie layouts validate.
- `python tools/check_tricky_splines.py` compares 90,261 sampled positions in
  the 19 archives against the disc's curves. Maximum difference is below
  `0.0016 cm`. The check rejects the previous archives immediately.
- Eight targeted game tests pass, including strict argument/register/cycle/RAM
  comparisons for spline evaluation, placement, spatial insertion and list
  gathering. The placement audit covers 180 fixtures and remains uninstalled.
- Two GPU-loss tests pass. A device loss no longer poisons the renderer lock;
  unrelated rendering panics still propagate. Native window rendering can
  recreate its device and retain the CPU game/draw state after a driver reset.
- Native Snowdream completes 6,000 frames and 5,960 game updates, past the
  previous stall near update 1,110. Its final RAM contains no fatal halt.
- Tokyo Freestyle entered through the full menus, consumed its initial pass
  (three remain), and returned to the interactive title after confirming Quit.
  The 10,000-frame run completes 9,959 updates with no missing functions.
  Reproduce its input with `python tools/scenarios.py input tricky_tokyo_freestyle_quit`.
- A native-window Snowdream run with `SSX3_GPU_RESET_FRAME=900` recreates its
  renderer once and reaches 2,518 updates before its configured exit, without
  a fatal halt or poisoned renderer mutex.
- All 19 course/mode combinations complete a native 1,800-frame smoke run:
  34,200 frames and 33,440 updates in total, zero missing functions, panics or
  fatal halts. These are bounded startup/play checks, not full-course runs.

The browser smoke was not run: the installed Rust target is Windows only.

Fatal native halts now automatically save RAM and registers under
`.cache/diagnostics`; `SSX3_DEBUG_SNAPSHOT` can select a diagnostic directory.
These generated captures and imported disc assets remain outside Git.
