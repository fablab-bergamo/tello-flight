# Architecture

## Shared runtime

The Python package under `src/tello_flight` has no OS-specific flight implementations.
`FlightEngine` is independent of Qt. It owns transport polling, command scheduling, control timing,
state transitions and watchdogs in one worker. The desktop GUI and read-only CLI use the same API.

`UDPTransport` communicates directly with Tello. `SimulatorTransport` supplies synthetic responses
and telemetry through the same interface. The simulator is not a physics model.

## Command handling

Only one acknowledged command is outstanding. Normal flight control uses RC channels at up to 20 Hz.
Manual inputs expire after 350 ms. GUI heartbeats are monitored independently from drone telemetry.
Flight commands time out after 12 seconds; setup/query commands after 5 seconds.
Command cards use 15 seconds for takeoff, landing, speed and rotation, and 65 seconds for distance moves
so that a 500 cm movement at 10 cm/s can complete. Long waits are local timers with neutral RC keepalives.

Movement outcomes are never automatically retried. A timeout quarantines the session; late responses
are logged and ignored. Reconnect creates a new UDP command source port. Priority landing and motor
cut bypass the queue, invalidate response correlation, and require physical inspection before reconnect.
Landing acknowledgement plus subsequent low-height telemetry is treated as grounded; this is an
estimate, not a definitive motor-state measurement. A dead control thread cannot safely recover itself.

No background battery query is sent during flight; fresh state packets provide battery. This avoids
holding manual control behind a delayed query. The firmware's documented no-command auto-land is
an additional device behavior that must be verified on the actual unit.

## Video

An independent UDP worker parses the incoming H.264 byte stream using PyAV/FFmpeg. A single latest
RGB frame is shared with the GUI, avoiding an unbounded frame queue. Old frames are marked unavailable.
Video is enabled/disabled while grounded. Snapshot captures the decoded preview, not the official
app's full-resolution photo feature. Recording is not implemented.

## Sequential programs

`program.py` defines immutable, range-checked cards and a versioned JSON file format. Drafts can be saved
without valid flight order, but execution requires exactly one Take off at the start and Land at the end.
There are at most 100 cards. Imported files cannot contain arbitrary SDK text or executable code.

The control worker owns the runner; the GUI does not schedule flight commands. Each acknowledged card
finishes before the next dispatch. Wait cards use nonblocking timers. Landing completion also requires
fresh low-height telemetry. Manual RC input is suppressed during a run. Stop, Land and motor cut discard
remaining cards. A rejection, timeout, stale telemetry, operator loss or critically low battery aborts the
run. Flip cards require at least 50% battery at preflight and again when dispatched.

Program cards, parameters, active index and completion status are included in state snapshots and
diagnostic bundles. Start, card dispatch, completion and failures are logged with the session ID.

## Diagnostics and distribution

`i18n.py` contains the English/Italian presentation catalog. The UI translates labels, canonical status
messages and Qt dialog buttons without modifying engine state, SDK commands or the JSON program format.
Changing the language retranslates existing widgets and painter text in place. QSettings stores the user's
language choice; the command-line option can override startup language. Technical logs retain stable
English events and protocol identifiers for troubleshooting across languages.

Rotating JSONL logs include session IDs, command timing, telemetry, transport events and tracebacks.
ZIP export adds a system/version manifest and current state. Data is never uploaded automatically.

GitHub Actions runs tests on Windows and Ubuntu 24.04, builds separate native bundles, and publishes
tagged archives with checksums to GitHub Releases. MkDocs renders `website/` to GitHub Pages.
Reference manuals remain in `docs/` and are not automatically republished.
