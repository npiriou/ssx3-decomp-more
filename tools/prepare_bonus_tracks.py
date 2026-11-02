"""Build local Bonus menu and Garibaldi assets for normal game startup."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from build_garibaldi_world import build
from ssx3_bonus_menu import add_bonus_locale, add_bonus_screen
from tricky_assets import read_iso_file


def main() -> None:
    root = Path(__file__).resolve().parent.parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ssx3-iso", type=Path, default=root / "SSX 3 (USA).iso")
    parser.add_argument("--tricky-iso", type=Path,
                        default=root.parent / "SSX Tricky (USA).iso")
    parser.add_argument("--overlay", type=Path, default=root / ".cache/overlay")
    args = parser.parse_args()
    ready = args.overlay / "custom-tracks.ready"
    ready.unlink(missing_ok=True)
    world = build(args.ssx3_iso, args.tricky_iso,
                  args.overlay / "DATA/WORLDS/BAM.BIG")
    for path, convert in (("DATA/UI/FE.LUI", add_bonus_screen),
                          ("DATA/LOCALE/CMNAMER.LOC", add_bonus_locale)):
        target = args.overlay / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(convert(read_iso_file(args.ssx3_iso, path)))
    ready.write_text(json.dumps({"version": 1, "tracks": ["garibaldi"],
                                 "world": world}, indent=2), encoding="utf-8")
    print(f"Bonus assets: {args.overlay}")
    print(f"Garibaldi: {world['resource_counts']}")


if __name__ == "__main__":
    main()
