# Tello Flight

A local Windows/Linux flight console for the Ryze Tello. One Python codebase, direct UDP,
an official-app-inspired camera view, Mode 2 joysticks, keyboard controls, and persistent diagnostics.

[Documentation](https://fablab-bergamo.github.io/tello-flight/) ·
[Releases](https://github.com/fablab-bergamo/tello-flight/releases) ·
[CI builds](https://github.com/fablab-bergamo/tello-flight/actions/workflows/checks.yml)

**Status: initial implementation. Simulator and local transport tests are available; no physical drone
has been used to validate this build.** Do not treat simulator results as flight certification.

## Run from source

Requires Python 3.10 or newer. Python 3.12 is the CI baseline.

```powershell
# Windows PowerShell
python -m venv .venv
.venv/Scripts/python -m pip install -e ".[dev]"
.venv/Scripts/python -m tello_flight
```

```bash
# Linux
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[dev]'
.venv/bin/python -m tello_flight
```

Starts in simulator mode. Choose **Session settings → Live Tello** only after joining the drone Wi-Fi.
The camera scene in simulator mode is generated, not a drone feed.

## Controls

| Input | Action |
| --- | --- |
| W / S | Ascend / descend |
| A / D | Turn left / right |
| Up / Down | Forward / backward |
| Left / Right | Strafe left / right |
| Space | Neutral input / hover |
| Mouse | Hold and drag either Mode 2 joystick; release to center |

Takeoff and land are explicit buttons. Motor cut has a separate confirmation because it stops motors
immediately. Initial controls are limited to 30% RC input. A lost operator heartbeat or stale telemetry
requests landing once; delivery is never guaranteed after loss of Wi-Fi.

## Debugging together

Open **Flight log** for current session events. Use **Save diagnostics** to export a ZIP containing
rotating JSONL logs, system/dependency versions, connection settings, and the current state. No images
or video are included. Logs include connection IPs and exception paths; review before sharing.

```bash
python -m tello_flight --diagnose --seconds 3 --bundle simulator-debug.zip
python -m tello_flight --diagnose --live --seconds 10 --bundle tello-debug.zip
```

The diagnostic command never sends takeoff, movement, or camera commands. See
[the debugging guide](website/debugging.md) for log locations and what to report.

## Verify and package

```bash
python -m pytest
python -m ruff check src tests scripts
python -m tello_flight --screenshot artifacts/console.png
python -m mkdocs build --strict
python scripts/build.py
```

Build separately on Windows and Linux. Portable output is in `dist/TelloFlight/`. Linux support initially
targets Ubuntu 24.04 x86-64; additional distributions require validation. GitHub Actions builds packages,
and version tags publish archives and SHA-256 checksums to GitHub Releases. GitHub Pages hosts docs
and links to downloads; application execution is entirely local.

## Reference material

Original SDK and user manuals are in `docs/`. The supplied SDK 2.0 manual contains EDU-only features;
this build implements basic single-drone commands, not mission pads or swarms. This is an independent
project, not an official Ryze or DJI application. The interface uses original code and generated graphics.
