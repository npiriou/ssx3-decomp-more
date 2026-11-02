"""Explicit Tricky-to-SSX 3 surface policy for the imported Race resources.

The numbers are different enums. All returned IDs select SSX 3's existing
SurfPropCache records; no source game's friction or physics is imported.
"""

from __future__ import annotations

from dataclasses import dataclass

from tricky_assets import FormatError


@dataclass(frozen=True)
class Surface:
    source_name: str
    native_id: int
    native_name: str
    collision: bool = True
    reset: bool = False


# Source names: SSX-Library TrickyEnums.TrickySurfaceType. Native snow IDs
# follow the board-trail depth switch; native 9/10 are the retail wood/metal
# rail surfaces. Reset is a terrain flag, rather than a new physics model.
SURFACES = {
    -1: Surface("None", -1, "obstacle"),
    0: Surface("Reset", 13, "impassable powder", reset=True),
    1: Surface("StandardSnow", 0, "packed snow"),
    2: Surface("StandardOffTrack", 2, "powder"),
    3: Surface("PowderedSnow", 2, "powder"),
    4: Surface("SlowPowderedSnow", 3, "deep powder"),
    5: Surface("Ice", 4, "ice"),
    6: Surface("BounceUnskiable", 8, "rock obstacle"),
    7: Surface("IceWaterNoTrail", 5, "water"),
    8: Surface("GlidySnow", 0, "packed snow"),
    9: Surface("Rock", 7, "rock"),
    10: Surface("Wall", 8, "rock obstacle"),
    11: Surface("IceCrunchNoTrail", 4, "ice"),
    12: Surface("Wood", 9, "wood"),
    13: Surface("OffTrackMetal", 10, "metal"),
    14: Surface("SpeedGrinding", 10, "metal"),
    15: Surface("StandardUnknown", 0, "packed snow"),
    16: Surface("Sand", 12, "sand"),
    17: Surface("NoCollision", 0, "packed snow", collision=False),
    18: Surface("ShowOffRampMetal", 10, "metal"),
    19: Surface("ShowOffRampMetal2", 10, "metal"),
}


def surface(source: int) -> Surface:
    try:
        return SURFACES[source]
    except KeyError as exc:
        raise FormatError(f"Tricky surface {source} has no native mapping") from exc


def patch_surface(source: int) -> tuple[int, int]:
    """Return native surface and terrain flags before section activation.

    Collision queries require flags & 0x41 == 0x41. Section activation adds
    0x40; bit 0 therefore controls physical contact independently of drawing.
    Ground motion consumes bit 1 as the native reset request. Retail terrain
    uses flags 8, 9 and 11 for these combinations.
    """
    rule = surface(source)
    flags = 8 | int(rule.collision) | (2 if rule.reset else 0)
    return rule.native_id, flags
