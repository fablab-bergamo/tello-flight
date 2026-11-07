import os
import time

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QModelIndex, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from tello_flight.program import Card, load_program, save_program
from tello_flight.ui import FlightWindow


def test_cards_can_be_added_edited_reordered_duplicated_saved_and_removed(tmp_path):
    app = QApplication.instance() or QApplication([])
    window = FlightWindow(tmp_path, autostart=False)
    panel = window.program_panel
    window.show()
    window.tabs.setCurrentIndex(1)
    app.processEvents()
    try:
        panel.clear_cards()
        QTest.mouseClick(panel.palette_buttons["takeoff"], Qt.MouseButton.LeftButton)
        QTest.mouseClick(panel.palette_buttons["forward"], Qt.MouseButton.LeftButton)
        panel.parameter.setValue(240)
        assert panel.cards()[1] == Card("forward", 240)
        panel.duplicate_card()
        assert panel.cards()[2] == Card("forward", 240)
        panel.move_card(-1)
        panel.parameter.setValue(300)
        assert panel.cards()[1] == Card("forward", 300)
        panel.remove_card()
        panel.add_card(Card("cw", 180))
        panel.add_card(Card("land"))
        # Qt's model move is also the operation used by an internal drag/drop.
        assert panel.queue.model().moveRows(QModelIndex(), 1, 1, QModelIndex(), 3)
        assert panel.cards() == (Card("takeoff"), Card("cw", 180), Card("forward", 240), Card("land"))
        path = tmp_path / "lesson.json"
        save_program(path, panel.cards())
        panel.clear_cards()
        panel.set_cards(load_program(path))
        assert panel.cards()[2].value == 240
        assert not panel.run.isEnabled()  # Editing works offline; flight needs a connection.
        assert window.grab().save(str(tmp_path / "program.png"))
    finally:
        window.close()


@pytest.mark.parametrize("stop_action", ["button", "space"])
def test_program_run_highlights_cards_locks_editing_and_stop_discards_queue(tmp_path, stop_action):
    app = QApplication.instance() or QApplication([])
    window = FlightWindow(tmp_path)
    window.show()
    window.tabs.setCurrentIndex(1)
    panel = window.program_panel
    panel.set_cards((Card("takeoff"), Card("wait", 20), Card("forward", 100), Card("land")))
    try:
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline and not panel.run.isEnabled():
            app.processEvents()
            time.sleep(0.02)
        assert panel.run.isEnabled()
        QTest.mouseClick(panel.run, Qt.MouseButton.LeftButton)
        deadline = time.monotonic() + 2
        while time.monotonic() < deadline:
            window.engine.operator()
            app.processEvents()
            if window.engine.snapshot().program.index == 1:
                break
            time.sleep(0.02)
        window.refresh()
        assert panel.delegate.progress.index == 1
        assert not panel.parameter.isEnabled()
        assert not panel.palette_widget.isEnabled()
        assert panel.stop.isEnabled()
        if stop_action == "button":
            QTest.mouseClick(panel.stop, Qt.MouseButton.LeftButton)
        else:
            QTest.keyClick(panel.queue, Qt.Key.Key_Space)
        deadline = time.monotonic() + 2
        while time.monotonic() < deadline:
            window.engine.operator()
            app.processEvents()
            if window.engine.snapshot().flight == "grounded":
                break
            time.sleep(0.02)
        assert window.engine.snapshot().program.status == "cancelled"
        assert window.engine.snapshot().telemetry.values["sim_x"] == 0
    finally:
        window.close()
