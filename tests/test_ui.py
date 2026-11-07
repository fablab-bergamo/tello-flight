import os
import time

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from tello_flight.ui import FlightWindow


def test_simulator_ui_controls_focus_reset_and_render(tmp_path):
    app = QApplication.instance() or QApplication([])
    window = FlightWindow(tmp_path)
    window.show()
    try:
        end = time.monotonic() + 3
        while time.monotonic() < end and not window.takeoff.isEnabled():
            app.processEvents()
            time.sleep(0.02)
        assert window.takeoff.isEnabled()
        QTest.mouseClick(window.takeoff, Qt.MouseButton.LeftButton)
        end = time.monotonic() + 1
        while time.monotonic() < end and window.engine.snapshot().flight != "airborne":
            window.engine.operator()
            app.processEvents()
            time.sleep(0.02)
        assert window.engine.snapshot().flight == "airborne"
        QTest.keyPress(window, Qt.Key.Key_W)
        assert Qt.Key.Key_W in window.keys
        window.application_state(Qt.ApplicationState.ApplicationInactive)
        assert not window.keys
        assert window.camera.left.x == 0
        assert window.grab().save(str(tmp_path / "console.png"))
        window.command("land")
        end = time.monotonic() + 1
        while time.monotonic() < end and window.engine.snapshot().flight != "grounded":
            window.engine.operator()
            app.processEvents()
            time.sleep(0.02)
        assert window.engine.snapshot().flight == "grounded"
    finally:
        window.close()
        app.processEvents()
