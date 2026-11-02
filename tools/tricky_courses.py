"""Disc-backed SSX Tricky course catalog shared by the asset preparation tools."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Course:
    id: str
    name: str
    code: str
    preview: str
    main_route: tuple[int, ...]
    modes: tuple[str, ...] = ("race", "freestyle")

    @property
    def archive(self) -> str:
        return f"DATA/MODELS/{self.code}.BIG"


# The main routes are the disc's first descending-distance path chain,
# ending at its finish event, before the alternate branches begin.
COURSES = (
    Course("garibaldi", "Garibaldi", "GARI", "gari", tuple(range(6))),
    Course("snowdream", "Snowdream", "SNOW", "snow", tuple(range(4))),
    Course("elysium-alps", "Elysium Alps", "ELYSIUM", "elys", tuple(range(8))),
    Course("mesablanca", "Mesablanca", "MESA", "mesa", tuple(range(5))),
    Course("merqury-city", "Merqury City Meltdown", "MERQUER", "merq", tuple(range(7))),
    Course("tokyo-megaplex", "Tokyo Megaplex", "MEGAPLE", "toky", (0, 1)),
    Course("aloha-ice-jam", "Aloha Ice Jam", "ALOHA", "aloh", tuple(range(4))),
    Course("alaska", "Alaska", "ALASKA", "alas", tuple(range(8))),
    Course("untracked", "Untracked", "UNTRACK", "untr", tuple(range(5)), ("race",)),
    Course("pipedream", "Pipedream", "PIPE", "pipe", (0, 1), ("freestyle",)),
    Course("trick-tutorial", "Trick Tutorial", "TRICK", "", (0,), ("freestyle",)),
)


def course(value: str) -> Course:
    return next(item for item in COURSES
                if value.lower() in (item.id, item.code.lower()))
