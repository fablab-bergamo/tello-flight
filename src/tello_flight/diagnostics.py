"""Rotating JSONL diagnostics and portable support bundles (no camera images)."""

import importlib.metadata
import json
import logging
import os
import platform
import sys
import threading
import uuid
import zipfile
from contextlib import suppress
from dataclasses import asdict
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler
from pathlib import Path

from . import __version__

SESSION = uuid.uuid4().hex[:12]


def log_directory():
    if sys.platform == "win32":
        root = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData/Local"))
    else:
        root = Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local/state"))
    return root / "TelloFlight" / "logs"


def system_info():
    versions = {}
    for name in ("PySide6-Essentials", "av"):
        try:
            versions[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            versions[name] = "unavailable"
    return {
        "app_version": __version__,
        "session": SESSION,
        "platform": platform.platform(),
        "python": platform.python_version(),
        "dependencies": versions,
    }


class JsonFormatter(logging.Formatter):
    def format(self, record):
        data = {
            "time": datetime.fromtimestamp(record.created, timezone.utc).isoformat(),
            "session": SESSION,
            "level": record.levelname,
            "logger": record.name,
            "thread": record.threadName,
            "message": record.getMessage(),
        }
        if hasattr(record, "data"):
            data["data"] = record.data
        if record.exc_info:
            data["exception"] = self.formatException(record.exc_info)
        return json.dumps(data, ensure_ascii=True, default=str)


def configure_logging(directory=None):
    directory = Path(directory) if directory else log_directory()
    directory.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("tello_flight")
    logger.setLevel(logging.DEBUG)
    # Process-specific files avoid concurrent applications corrupting rotation.
    path = directory / f"flight-{os.getpid()}.jsonl"
    handler = RotatingFileHandler(path, maxBytes=5_000_000, backupCount=3, encoding="utf-8")
    handler.setFormatter(JsonFormatter())
    logger.addHandler(handler)
    logger.info("application_start", extra={"data": system_info()})
    # Retain the ten most recent process log sets, each capped at 20 MB.
    bases = sorted(directory.glob("flight-*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True)
    for base in bases[10:]:
        for old in directory.glob(base.name + "*"):
            with suppress(OSError):
                old.unlink()
    original = sys.excepthook

    def exception_hook(kind, value, tb):
        logger.critical("uncaught_exception", exc_info=(kind, value, tb))
        original(kind, value, tb)

    sys.excepthook = exception_hook

    def thread_hook(args):
        logger.critical("worker_exception", exc_info=(args.exc_type, args.exc_value, args.exc_traceback))

    threading.excepthook = thread_hook
    return directory


def export_bundle(destination, directory, state=None, config=None, notes=""):
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("tello_flight")
    logger.info("diagnostic_export_requested")
    for handler in logger.handlers:
        handler.flush()
    manifest = system_info() | {"notes": notes, "hardware_validated": False}
    if config:
        manifest["connection"] = asdict(config)
    if state:
        manifest["state"] = asdict(state)
        # monotonic timestamps are only meaningful within the originating process.
        import time

        manifest["telemetry_age_seconds"] = (
            time.monotonic() - state.telemetry.received_at if state.telemetry.received_at else None
        )
    with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
        bundle.writestr("manifest.json", json.dumps(manifest, indent=2))
        bundle.writestr(
            "READ-ME.txt",
            "Tello Flight diagnostic bundle\n"
            "Contains timestamps, OS/dependency versions, connection IPs, commands, telemetry,\n"
            "and exception traces. No video, screenshots, Wi-Fi passwords or serial-number queries.\n"
            "Review before sharing. Include what you expected and what happened.\n",
        )
        for path in Path(directory).glob("flight-*.jsonl*"):
            # A concurrent log rotation may rename a file.
            with suppress(FileNotFoundError):
                bundle.write(path, "logs/" + path.name)
