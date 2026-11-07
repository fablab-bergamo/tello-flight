# Debugging together

You can prepare useful diagnostics without a drone. All runs have a session ID shown in the footer.
Logging starts before the UI, so startup and worker failures are recorded too.

## Export a support bundle

1. Reproduce the issue in simulator mode or with the drone.
2. Open **Flight log** to inspect recent commands and errors.
3. Click **Save diagnostics** and save the ZIP.
4. Review the ZIP and share it with your report.

Include: operating system, app version, simulator/live mode, exact steps, expected result, actual result,
and approximate time of the problem. For a real drone, add model and firmware if known, whether its
official app works, and which Wi-Fi adapter is connected. Attach a screenshot separately if relevant.

## What is collected

- UTC timestamps, session IDs, thread names, application and dependency versions.
- Connection IPv4 addresses, UDP sends/replies and command elapsed times.
- Telemetry samples, freshness transitions, timeouts, watchdog actions and exceptions.
- Video decoder errors and session shutdowns.

Bundles contain `manifest.json`, a short explanation, and `logs/*.jsonl*`.
They do not include camera frames, videos, Wi-Fi passwords, or serial-number queries.
Exception traces can contain local filesystem paths. Review before sharing.
`hardware_validated: false` describes this release's validation status, not whether a live connection occurred;
the connection's `simulator` field identifies the actual session mode.

## Persistent logs

| Platform | Default directory |
| --- | --- |
| Windows | `%LOCALAPPDATA%/TelloFlight/logs` |
| Linux | `${XDG_STATE_HOME:-~/.local/state}/TelloFlight/logs` |

Each process log rotates at 5 MB with three backups. The ten newest process log sets are retained.
Use `--log-dir PATH` to choose another location. Logs stay on your computer until you export/share them.

## Headless diagnostics

```bash
TelloFlight --diagnose --seconds 3 --bundle simulator-debug.zip
TelloFlight --diagnose --live --seconds 10 --bundle drone-debug.zip
```

From source, replace `TelloFlight` with `python -m tello_flight`.
These checks enter SDK mode and read telemetry/battery. They never take off or move the drone.
Exit code 0 means the handshake and fresh telemetry succeeded; 1 means they did not.

In simulator mode, **Flight log → Simulate signal loss** stops simulated replies and telemetry.
During simulated flight this exercises the watchdog. Disconnect/reconnect to restore the simulator.

## First hardware session

Start with the read-only diagnostic and retain its bundle. Then test video while grounded, and only then
a controlled takeoff/hover/land session. Report problems before enabling more commands.
No hardware flight or camera latency has been verified for this initial release.
