# Next Event: Pipe Dream Freestyle loading loop

2026-11-04, v67 investigation. User sequence: finish an event, choose Next
Event, Freestyle, Pipe Dream. Session started from v66/commit `ae86da5` in
`.cache/user-play-v66-20261104-161014.log`. It previously loaded Garibaldi,
then Mesa Blanca Freestyle. Pipe Dream becomes the selected course at log
lines1935..1937. At line1938, frame29520/~494.8s, loader thread5 is running
at `31e968`. It remains at that loop across several minutes of frame logs.
The process remains responsive; there is no new fatal-stop record.

## Captured state

The user's existing process312680 was inspected with read-only Windows
`OpenProcess(QUERY_INFORMATION | VM_READ)`, `VirtualQueryEx` and
`ReadProcessMemory`. No debugger attachment, suspension, memory writes,
input, game restart or window operation was used. The ignored helpers are
`.cache/capture_live_game_ram_v67.py` and
`.cache/capture_live_game_cpu_v67.py`.

Candidate private memory must match both the supplied native ELF's text
at100100 and the graphics vtable at493260 before the32MiB game RAM is saved.
Exactly one candidate matched. The live Cpu was then identified by ownership
of that validated RAM vector and its register layout, rather than guessing
a host address. The artifacts are:

- `.cache/next-event-pipedream-v67-live-ram-0.bin`
- `.cache/next-event-pipedream-v67-live.json`
- `.cache/next-event-pipedream-v67-live-cpu.json`
- `.cache/next-event-pipedream-v67-contexts.json`

These are ordinary-play observations, not a synthetic fixture or replay.
Capture does not suspend execution, so it is not an atomic machine snapshot;
the persistent loop and independently captured invalid victim corroborate
the structural problem.

`DLHeap_Malloc` (`31e818`) has `FP=004ff250`, heap state `S2=0053f940`,
unsorted-list sentinel `S5=0053f978`, normalized request `S3=000089a0`, and
victim `S1=0`. Native PC31e968 drains the unsorted list; it must terminate
at the sentinel and cannot legitimately process address zero as a chunk.
RAM confirms the sentinel's tail (`state+44`) is zero. Following the other
direction reaches valid arena chunks followed by `002ebd34`, outside the
heap and in the ELF code range, then another invalid link. The list is
already corrupted, not merely awaiting a file completion.

The allocator's frame is0xa0 with its caller RA atSP+0. The captured stack
contains the following native returns:

```
31f3ac  DLHeap_Memalign -> malloc
320068  MEM_HeapMemalign -> Memalign
319b0c  MEM_AllocInternal -> aligned heap allocation
317e00  EA_MemAllocNamed -> MEM_AllocInternal
317e40  operator_new_named -> EA_MemAllocNamed
2529f0  named allocation adapter
252fbc  MEM_AllocNamed128
3e1870  EAFile_LoadFileWorker -> allocation
3dde24  file-load adapter
3e18fc  EAFile_LoadFileEx
```

Older frames preserve original size `000088f8` (35064bytes), alignment128,
and filename `data/ui/gl.lui` at00618520. Memalign's normalized client
chunk8900 plus alignment slack produces malloc's89a0; this is an ordinary
interface-file allocation, not a request for an enormous Pipe Dream buffer.
Its caller inherits broken shared heap state. This capture alone does not
identify which earlier allocation, release or write first corrupted it.

Old world-manager fields still reference a zero-count pool's freed tiny
descriptor array. Those are stale fields in an already freed owner, not
proof of a double destruction. Neither a per-course bypass nor a speculative
change to that pool's ownership is installed. The preceding Snowdream
null-render-call crash may share a memory-lifetime cause, but its all-zero
RAM dump does not establish that connection.

## First-corruption observations

`custom_heap_diagnostics.rs` observes the already installed native
`MEM_AllocInternal` and `MEM_FreeInternal` bodies when
`SSX3_HEAP_TRACE=1` and converted assets are available. It preserves:

- 256 recent operation entries/returns, caller registers and bounded native
  return-address candidates from the caller stack;
- two rolling4MiB event files, written directly before/after operations, so
  a hang inside an allocator call still leaves its entry and preceding frees;
- at most8192 partial heap-owner records, including one preceding lifetime;
- the first invalid main-heap header, unsorted-list link/reciprocal link or
  out-of-arena heap free, its original RAM and recent/owner records under
  `.cache/diagnostics/heap-*`.

Pool classification remains the actual native result. Singly linked fast
bins may legitimately end in zero and are not subjected to the unsorted
sentinel check. Realloc and other entry points can bypass this ownership
journal, so owner history is explicitly labelled partial and is not itself
used to diagnose a double free. All allocator calls, guest state, register
effects, cycles and allocation/free decisions are unchanged. No list repair,
skipped free, timeout or forced loader completion is added.

The two newly studied generated functions are retained separately in
`custom_dlheap_malloc.rs` and `custom_dlheap_memalign.rs`, each with empty
OVERRIDES, unregistered and without automated tests. Their source contracts
support the capture interpretation; these retained ports are not installed
or presented as compiled/differentially verified replacements.

## Current readiness

After preserving the live state, only the captured process312680 was stopped.
The executable path and continuing31e968 loader loop were checked again
before termination. Native compilation follows in
`.cache/build-tricky-heap-observer-v67-final.log`, before another ordinary launch,
with one heavy process at a time. Enable `SSX3_HEAP_TRACE=1` alongside the
existing ISO/overlay/snapshot settings. Build and launch outcomes follow
below. The earlier successful v67 build predates the rolling file journal and
is superseded. No generated dispatch regeneration or asset conversion is needed.

The final native build succeeds in2m07s. No runtime source changed afterward.
The ordinary game is reopened as process355776, with
`SSX3_HEAP_TRACE=1` and stderr
`.cache/user-play-v67-20261104-170549.log`. The startup window responds, the
native renderer is installed, and the observer announces its directory
`.cache/diagnostics/heap-355776-1793786751278`. No input is driven and the
Next Event sequence is not automatically replayed. A new first-corruption
capture or successful course transition has not yet been observed.

No automated test, replay, gate, browser build or game input is used. The
loading failure has been diagnosed as heap-list corruption; its first writer
and a verified behavioral correction remain outstanding. The observer keeps
native behavior intact and is not presented as a fix for the loading loop.
