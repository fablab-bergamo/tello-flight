# Tests without a drone

The test suite uses generated data, local UDP sockets, and the built-in simulator. No test sends commands
to a physical drone. Live mode is never selected automatically.

```bash
python -m pip install -e '.[dev]'
python -m pytest -q
```

| Test module | Behavior verified |
| --- | --- |
| `test_engine.py` | Telemetry validation, input limits, takeoff checks, command serialization, timeout quarantine, late replies, expired controls, watchdog landing, emergency priority, landing state, simulator lifecycle |
| `test_udp.py` | Actual loopback UDP handshake, battery/telemetry reception, shutdown without movement |
| `test_video.py` | Generated H.264 encoded and sent over loopback UDP, decoded to an RGB frame |
| `test_diagnostics.py` | ZIP manifest, structured logs, session metadata, absence of camera images |
| `test_cli.py` | Headless diagnostic process, nested ZIP export, no flight commands |
| `test_ui.py` | Qt simulator takeoff/land, keyboard input, focus-loss reset, rendering |

CI is configured to run on Windows and Ubuntu 24.04 using Python 3.12. It also builds the docs,
renders a UI screenshot, packages the executable, and checks the packaged diagnostic command.

For a local preview:

```bash
python -m tello_flight --screenshot artifacts/console.png
python -m tello_flight --diagnose --seconds 3 --bundle artifacts/debug.zip
```

## Limits

Synthetic video verifies the decoder pipeline, not a real Tello's packet loss behavior or camera latency.
Loopback UDP verifies transport integration, not Wi-Fi or firewall configuration. The simulator does not
prove physical safety or positioning accuracy. Hardware acceptance remains pending until the drone is
available. Initial hardware checks should be read-only, followed by grounded video, then controlled flight.
