import json
import subprocess
import sys
import zipfile


def test_headless_diagnostic_exports_session_and_never_moves_drone(tmp_path):
    bundle = tmp_path / "nested" / "debug.zip"
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "tello_flight",
            "--diagnose",
            "--seconds",
            "1",
            "--log-dir",
            str(tmp_path / "logs"),
            "--bundle",
            str(bundle),
        ],
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["healthy"]
    with zipfile.ZipFile(bundle) as archive:
        assert json.loads(archive.read("manifest.json"))["connection"]["simulator"]
        records = [
            json.loads(line)
            for name in archive.namelist()
            if name.startswith("logs/")
            for line in archive.read(name).splitlines()
        ]
        sent = [row["data"]["command"] for row in records if row["message"] == "simulator_tx"]
        assert "command" in sent
        assert set(sent).issubset({"command", "battery?"})
