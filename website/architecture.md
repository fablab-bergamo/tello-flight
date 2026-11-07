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
app's full-resolution photo feature. Recording and automatic flight sequences are not implemented.

## Diagnostics and distribution

Rotating JSONL logs include session IDs, command timing, telemetry, transport events and tracebacks.
ZIP export adds a system/version manifest and current state. Data is never uploaded automatically.

GitHub Actions runs tests on Windows and Ubuntu 24.04, builds separate native bundles, and publishes
tagged archives with checksums to GitHub Releases. MkDocs renders `website/` to GitHub Pages.
Reference manuals remain in `docs/` and are not automatically republished.
