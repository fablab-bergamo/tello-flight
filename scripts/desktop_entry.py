"""PyInstaller entry point (absolute imports work outside package execution)."""

from tello_flight.__main__ import main

if __name__ == "__main__":
    raise SystemExit(main())
