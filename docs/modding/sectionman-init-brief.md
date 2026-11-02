# SectionMan_Init port brief

Port `SectionMan_Init` (`0x0022cd40`) from
`generated/ee/s05/src/lib.rs` into the existing hand-written
`crates/ssx3-game/src/game/main/game.rs` unit, with one differential test.
The C++ reference clone is unavailable; the generated EE body is authoritative.
Follow `docs/investigation/phase2-worker-guide.md` and the one-function writer
rules in `AGENTS.md`. The module already contains other `SectionMan` ports and
tests; edit only this module file. Do not register the override yet, and do not
run Cargo. Report unresolved fixture or semantic details. The purpose is to
understand the logical section mapping needed for a custom Garibaldi course;
do not add custom-track behavior to the port itself.
