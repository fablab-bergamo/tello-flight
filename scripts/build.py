"""Build on the target OS: python scripts/build.py."""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
args = [
    sys.executable,
    "-m",
    "PyInstaller",
    "--noconfirm",
    "--clean",
    "--onedir",
    "--name",
    "TelloFlight",
    "--paths",
    str(ROOT / "src"),
    "--collect-all",
    "av",
    "--copy-metadata",
    "av",
    "--copy-metadata",
    "PySide6-Essentials",
    "--exclude-module",
    "PySide6.QtWebEngineCore",
    "--exclude-module",
    "PySide6.QtWebEngineWidgets",
    str(ROOT / "scripts/desktop_entry.py"),
]
# Keep a console for packaged diagnostics. Launch without it via pythonw in source mode if desired.
subprocess.run(args, cwd=ROOT, check=True)
