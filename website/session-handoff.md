# Session handoff — 7 November 2026

This records the completed development session and the starting point for the next one.

## Current delivery

| Item | Status |
| --- | --- |
| Repository | [fablab-bergamo/tello-flight](https://github.com/fablab-bergamo/tello-flight), default branch `main` |
| Current application release | [v0.1.0-beta.3](https://github.com/fablab-bergamo/tello-flight/releases/tag/v0.1.0-beta.3), marked prerelease |
| Application version | `0.1.0b3` |
| Released source commit | `beccb6f49d6dd3e47458a8ee7db7161997b2ba77` |
| Platforms | Windows x86-64 and Linux x86-64; initial Linux baseline: Ubuntu 24.04 |
| Languages | English and Italian, switchable from the top bar; preference remembered |
| Hardware validation | Pending: the user did not have access to the drone during this session |

Release assets are the Windows ZIP, Linux tar.gz and `SHA256SUMS.txt`. Extract the entire archive and
keep the executable with `_internal`. The default session is the simulator. No separate Python
installation is needed for the release packages.

The application runs locally. GitHub Pages hosts documentation and download links; GitHub Releases
hosts binaries. No cloud service is in the flight-control path. The organization’s canonical GitHub
name is **fablab-bergamo**.

## Decisions made

The original browser/mobile proposal was replaced by a shared Windows/Linux desktop runtime at the
user’s request. The selected stack is Python, PySide6/Qt Widgets, direct UDP communication, and
PyAV/FFmpeg for video decoding. PyInstaller builds a separate portable package on each operating system.
Development supports Python 3.10 or newer; CI uses Python 3.12.

The interface follows the official Tello app’s camera-centered layout, top status strip and Mode 2
joysticks. Programming uses Tello EDU-style command cards mapped to the basic single-drone SDK.
Original graphics and code are used; this is an independent project.

## Implemented

- Manual keyboard/joystick flight controls, takeoff, landing, hover and confirmed emergency motor cut.
- SDK handshake, telemetry parsing and freshness display, serialized acknowledged commands, input expiry,
  operator/telemetry watchdogs and session quarantine after uncertain outcomes.
- Independent H.264 video receiver, latest-frame preview and snapshot saving.
- Simulator with synthetic telemetry, generated camera scene, relative position/height/heading updates,
  flip counts and injectable signal loss.
- Card editor with drag-and-drop ordering, move/duplicate/remove, adjustable parameters, execution
  highlighting, progress, save/open JSON drafts and Stop & land.
- Takeoff/land, six movement directions, two turn directions, four flips, speed and wait/hover cards.
  Up/down parameters are relative height changes, not absolute altitude targets.
- English/Italian UI, including cards, parameters, statuses, settings and confirmations. Language changes
  preserve programs and run progress. Saved files and SDK identifiers are language-independent.
- Rotating structured logs, a visible flight log, support ZIP export and read-only CLI diagnostics.
- Documentation, an Italian guide, examples, Windows/Linux CI, Pages deployment and tagged prereleases.

## Verification at the released commit

**79 automated tests passed on both Windows and Linux.** They cover command validation/scheduling,
timeouts and late replies, watchdogs, loopback UDP, synthetic H.264 decoding, diagnostic export, CLI,
Qt controls, card editing/running/cancellation, localization and language switching during a run.

- [Release workflow](https://github.com/fablab-bergamo/tello-flight/actions/runs/42408201761): passed;
  tests, packaging, packaged read-only diagnostics and English/Italian editor rendering on both platforms.
- [Checks and portable builds](https://github.com/fablab-bergamo/tello-flight/actions/runs/42408201364): passed.
- [Documentation deployment](https://github.com/fablab-bergamo/tello-flight/actions/runs/42408201336): passed.

The English and Italian layouts were also inspected locally, including the minimum window size.
These results verify software and simulated/loopback behavior, not a physical aircraft.

## Debugging with the user

Use **Save diagnostics / Salva diagnostica** after reproducing a problem. The ZIP includes system and
dependency versions, session IDs, commands/timing, telemetry, program parameters/progress and exceptions.
It contains no camera frames or video. It can include connection IPs and local paths; review before sharing.
Technical log events retain canonical English text and SDK identifiers across UI languages.

Persistent log locations:

- Windows: `%LOCALAPPDATA%/TelloFlight/logs`
- Linux: `${XDG_STATE_HOME:-~/.local/state}/TelloFlight/logs`

Logs rotate at 5 MB with three backups per process; the ten newest process log sets are retained.
Use `--log-dir PATH` to override the location. No diagnostic data is uploaded automatically.

For a source-based simulator diagnostic:

```bash
python -m tello_flight --diagnose --seconds 3 --bundle simulator-debug.zip
```

For the first real-drone connection on Windows, from the extracted release folder:

```powershell
.\TelloFlight.exe --diagnose --live --seconds 10 --bundle tello-first-connection.zip
```

This diagnostic never takes off or moves the drone. Report expected/actual behavior, reproduction steps,
OS, application version, simulator/live mode and the approximate time, together with the reviewed bundle.

## Next session: hardware acceptance

No further feature work is required to close this session. The next priority, once the drone is available,
is hardware acceptance with the user in the loop:

1. Confirm the exact Tello model and firmware. The local reference material includes SDK 2.0, whose
   advanced EDU features must not be assumed for a standard Tello.
2. Connect the computer to the drone Wi-Fi, close other drone-control apps, run read-only diagnostics
   and retain the bundle. Check routing, adapter selection and firewall behavior.
3. Verify video while grounded; capture decoder errors and observe latency or frame loss.
4. Test a controlled takeoff/hover/land session, then the minimal card lesson: Take off → Wait → Land.
5. Validate distances, turns and disconnect/focus behavior before expanding the flight program.

The engine sends neutral/landing after operator or telemetry loss, but delivery cannot be guaranteed
over a broken link. Displayed landed state is an estimate from acknowledgements and height telemetry.
The simulator is not a physics or collision model. Windows packages are unsigned; other Linux
distributions have not been validated. Recording, EDU mission pads, swarms, loops, conditions and the
official app’s proprietary flight modes are outside the current implementation.

## Developer restart notes

Read this handoff, [architecture](architecture.md), [tests](testing.md) and
[programming guide](programming.md) before making changes.

| Area | Source |
| --- | --- |
| Flight state and scheduling | `src/tello_flight/engine.py`, `model.py` |
| UDP and simulator | `transport.py` |
| Desktop interface and video | `ui.py`, `video.py` |
| Command cards, persistence and editor | `program.py`, `program_ui.py` |
| English/Italian presentation | `i18n.py`; update translations/tests when changing user-facing messages |
| Diagnostics and CLI | `diagnostics.py`, `__main__.py` |
| Lessons | `examples/first-flight.tello.json`, `examples/square.tello.json` |
| Packaging and automation | `scripts/build.py`, `.github/workflows/` |

Install development dependencies in a virtual environment with `python -m pip install -e '.[dev]'`.
On Windows use `.venv/Scripts/python`; on Linux use `.venv/bin/python` after creating the environment.

```bash
python -m pytest -q
python -m ruff check src tests scripts
python -m mkdocs build --strict
python -m tello_flight --language it --program --screenshot artifacts/program-it.png
python scripts/build.py
```

Build on the target OS. For a future release, update `pyproject.toml` and `src/tello_flight/__init__.py`,
add `release-notes/<tag>.md`, then push an annotated version tag. Hyphenated version tags publish as
prereleases after the release workflow passes. Do not move an already published tag.

The local `.venv/`, `build/`, `dist/`, `artifacts/` and rendered `site/` are ignored and may contain
earlier builds. Use the tagged release or rebuild before assuming an executable is current. Original
SDK PDFs and saved vendor pages remain in the local ignored `docs/` directory; they were not republished.

## Session outcome

The requested desktop runtime, educational cards with parameters, diagnostic tooling, tests,
organization repository, beta distribution and Italian translation were delivered. The application
baseline is beta 3. This documentation-only handoff does not create a new application release.
