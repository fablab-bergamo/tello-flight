import json
import logging
import zipfile

from tello_flight.diagnostics import configure_logging, export_bundle
from tello_flight.model import Connection, FlightState, ProgramProgress


def test_support_bundle_contains_logs_and_manifest_without_video(tmp_path):
    logger = logging.getLogger("tello_flight")
    previous = list(logger.handlers)
    try:
        directory = configure_logging(tmp_path / "logs")
        logger.warning("synthetic_timeout", extra={"data": {"command": "battery?"}})
        path = tmp_path / "support.zip"
        state = FlightState(
            program=ProgramProgress(
                status="failed", index=1, total=3, cards=[{"kind": "forward", "value": 240}]
            )
        )
        export_bundle(path, directory, state, Connection(), notes="No drone available")
        with zipfile.ZipFile(path) as bundle:
            manifest = json.loads(bundle.read("manifest.json"))
            assert manifest["connection"]["simulator"] is True
            assert manifest["notes"] == "No drone available"
            assert manifest["state"]["program"]["cards"][0]["value"] == 240
            assert manifest["state"]["program"]["status"] == "failed"
            logs = [name for name in bundle.namelist() if name.startswith("logs/")]
            assert logs
            lines = [json.loads(line) for line in bundle.read(logs[0]).splitlines()]
            assert any(row["message"] == "synthetic_timeout" for row in lines)
            assert all("session" in row and "thread" in row for row in lines)
            assert not any(name.endswith((".png", ".mp4")) for name in bundle.namelist())
    finally:
        for handler in list(logger.handlers):
            if handler not in previous:
                logger.removeHandler(handler)
                handler.close()
