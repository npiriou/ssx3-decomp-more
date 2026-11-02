"""Backward-compatible Garibaldi entry point for the shared Tricky importer."""

from build_tricky_world import build, main


if __name__ == "__main__":
    raise SystemExit(main())
