"""Desktop entry point plus a headless, read-only connection diagnostic."""

import argparse
import json
import logging
import os
import sys
import time
from pathlib import Path

from . import __version__
from .diagnostics import configure_logging, export_bundle
from .engine import FlightEngine
from .model import Connection


def diagnose(config, seconds, log_dir, bundle=None):
    engine = FlightEngine(config)
    engine.start()
    deadline = time.monotonic() + seconds
    try:
        while time.monotonic() < deadline:
            engine.operator()
            time.sleep(0.05)
        state = engine.snapshot()
        healthy = state.mode == "ready" and time.monotonic() - state.telemetry.received_at < 3
        report = {
            "mode": state.mode,
            "simulator": config.simulator,
            "battery": state.telemetry.battery if healthy else None,
            "telemetry": state.telemetry.values,
            "message": state.message,
            "logs": str(log_dir),
            "healthy": healthy,
        }
        if bundle:
            export_bundle(bundle, log_dir, state, config)
        print(json.dumps(report, indent=2))
        return 0 if healthy else 1
    finally:
        engine.close()


def main(argv=None):
    parser = argparse.ArgumentParser(description="Tello Flight — Windows/Linux flight console")
    parser.add_argument("--version", action="version", version=__version__)
    parser.add_argument("--live", action="store_true", help="Connect to a real Tello (default: simulator)")
    parser.add_argument("--host", default="192.168.10.1", help="Drone IPv4 address")
    parser.add_argument("--bind", default="0.0.0.0", help="Local adapter IPv4 address")
    parser.add_argument("--diagnose", action="store_true", help="Read-only connection check without GUI")
    parser.add_argument("--seconds", type=float, default=7, help="Diagnostic duration (1–60 seconds)")
    parser.add_argument("--bundle", type=Path, help="Save a ZIP support bundle after --diagnose")
    parser.add_argument("--log-dir", type=Path, help="Override the persistent log directory")
    parser.add_argument("--screenshot", type=Path, help="Save a simulator UI preview and exit")
    parser.add_argument("--program", action="store_true", help="Open the command-card editor")
    parser.add_argument(
        "--language",
        choices=("en", "it"),
        help="Interface language (default: saved choice or system language)",
    )
    args = parser.parse_args(argv)
    import ipaddress

    try:
        ipaddress.IPv4Address(args.host)
        ipaddress.IPv4Address(args.bind)
    except ValueError:
        parser.error("--host and --bind must be IPv4 addresses")
    if not 1 <= args.seconds <= 60:
        parser.error("--seconds must be between 1 and 60")
    if args.screenshot and args.live:
        parser.error("Screenshots run only in simulator mode")
    log_dir = configure_logging(args.log_dir)
    config = Connection(simulator=not args.live, host=args.host, local_address=args.bind)
    if args.diagnose:
        return diagnose(config, args.seconds, log_dir, args.bundle)
    if args.screenshot:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QApplication

    from .ui import FlightWindow

    app = QApplication([sys.argv[0]])
    app.setApplicationName("Tello Flight")
    app.setOrganizationName("TelloFlight")
    window = FlightWindow(log_dir, config, ui_language=args.language)
    if args.program:
        window.tabs.setCurrentIndex(1)
    window.show()
    if args.screenshot:

        def capture():
            args.screenshot.parent.mkdir(parents=True, exist_ok=True)
            if not window.grab().save(str(args.screenshot)):
                logging.getLogger(__name__).error("screenshot_save_failed")
                app.exit(1)
            else:
                window.close()

        QTimer.singleShot(1200, capture)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
