import os
import time
from string import Formatter

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication, QDialogButtonBox
from PySide6.QtWidgets import QFileDialog as NativeFileDialog
from PySide6.QtWidgets import QMessageBox as NativeMessageBox

from tello_flight.i18n import ITALIAN, language, message, number, preferred_language, set_language, tr
from tello_flight.program import SPECS, Card, load_program, save_program
from tello_flight.ui import FlightWindow, SessionDialog


@pytest.fixture(autouse=True)
def restore_language():
    previous = language()
    set_language("en")
    yield
    set_language(previous)


def preferences(tmp_path):
    return QSettings(str(tmp_path / "language.ini"), QSettings.Format.IniFormat)


def test_all_card_names_and_parameters_have_italian_translations():
    set_language("it")
    for spec in SPECS.values():
        assert tr(spec.title) != spec.title
        if spec.parameter:
            assert tr(spec.parameter) != spec.parameter
    assert number(1.5) == "1,5"
    set_language("en")
    assert tr("Take off") == "Take off"
    assert number(1.5) == "1.5"


def test_translation_templates_preserve_all_interpolated_values():
    def fields(text):
        return {field for _, field, _, _ in Formatter().parse(text) if field}

    for source, translated in ITALIAN.items():
        assert fields(source) == fields(translated), source


@pytest.mark.parametrize(
    "source,expected",
    [
        ("↑  Take off", "↑  Decolla"),
            ("1 cards", "1 scheda"),
        ("Program started — 6 cards", "Programma avviato — 6 schede"),
        ("Card 2/6 · Fly up · 50 cm", "Scheda 2/6 · Sali · 50 cm"),
        ("14:05:00  Card 3/6: Fly forward · 240 cm", "14:05:00  Scheda 3/6: Avanti · 240 cm"),
        ("Sent: forward 240", "Inviato: forward 240"),
        (
            "Card rejected (forward 240: error); program aborted",
            "Scheda rifiutata (forward 240: error); programma interrotto",
        ),
    ],
)
def test_dynamic_status_text_translates_without_changing_sdk_commands(source, expected):
    set_language("it")
    assert message(source) == expected


def test_language_preference_system_detection_and_invalid_saved_value(tmp_path):
    settings = preferences(tmp_path)
    assert preferred_language(settings, "it_IT") == "it"
    assert preferred_language(settings, "en_GB") == "en"
    settings.setValue("language", "en")
    assert preferred_language(settings, "it_IT") == "en"
    settings.setValue("language", ["invalid"])
    assert preferred_language(settings, "it_IT") == "it"
    with pytest.raises(ValueError):
        set_language("invalid")


def test_language_switch_preserves_edited_cards_and_saved_file_bytes(tmp_path):
    app = QApplication.instance() or QApplication([])
    settings = preferences(tmp_path)
    window = FlightWindow(tmp_path, autostart=False, ui_language="en", settings=settings)
    panel = window.program_panel
    panel.queue.setCurrentRow(2)
    panel.parameter.setValue(240)
    original = panel.cards()
    path = tmp_path / "lesson.json"
    save_program(path, original)
    before = path.read_bytes()
    try:
        window.language_selector.setCurrentIndex(window.language_selector.findData("it"))
        assert window.tabs.tabText(1) == "Programma con le schede"
        assert "Decolla" in window.takeoff.text()
        assert panel.selected_title.text() == "Avanti"
        assert panel.parameter_label.text() == "Distanza"
        assert panel.parameter.value() == 240
        assert panel.cards() == original
        assert load_program(path) == original
        save_program(path, original)
        assert path.read_bytes() == before
        assert settings.value("language") == "it"
    finally:
        window.close()
    reopened = FlightWindow(tmp_path, autostart=False, settings=settings)
    assert reopened.language_selector.currentData() == "it"
    assert reopened.program_panel.run.text() == "▶  Esegui dall’inizio"
    reopened.language_selector.setCurrentIndex(reopened.language_selector.findData("en"))
    assert reopened.tabs.tabText(1) == "Program with cards"
    assert reopened.program_panel.run.text() == "▶  Run from top"
    reopened.close()
    app.processEvents()


def test_italian_session_dialog_and_standard_cancel_button(tmp_path):
    app = QApplication.instance() or QApplication([])
    window = FlightWindow(tmp_path, autostart=False, ui_language="it", settings=preferences(tmp_path))
    try:
        dialog = SessionDialog(window.config, window)
        assert dialog.windowTitle() == "Sessione di volo"
        assert dialog.mode.itemText(0).startswith("Simulatore")
        buttons = dialog.findChild(QDialogButtonBox)
        assert buttons.button(QDialogButtonBox.StandardButton.Cancel).text() == "Annulla"
        dialog.close()
    finally:
        window.close()
        app.processEvents()


def test_safety_confirmation_and_file_dialog_are_translated(tmp_path, monkeypatch):
    app = QApplication.instance() or QApplication([])
    window = FlightWindow(tmp_path, autostart=False, ui_language="it", settings=preferences(tmp_path))
    prompts = []

    def warning(parent, title, text, *args, **kwargs):
        prompts.append((title, text))
        return NativeMessageBox.StandardButton.Cancel

    monkeypatch.setattr(NativeMessageBox, "warning", warning)
    monkeypatch.setattr(
        NativeFileDialog, "getSaveFileName", lambda *args, **kwargs: prompts.append(args[1:4]) or ("", "")
    )
    try:
        window.motor_cut()
        assert prompts[0][0] == "Arresto immediato dei motori"
        assert "cadrà" in prompts[0][1]
        window.program_panel.save_file()
        assert prompts[1][0] == "Salva programma"
        assert prompts[1][2] == "Programma Tello (*.json)"
    finally:
        window.close()
        app.processEvents()


def test_switching_language_during_program_does_not_restart_or_reorder_it(tmp_path):
    app = QApplication.instance() or QApplication([])
    window = FlightWindow(tmp_path, ui_language="en", settings=preferences(tmp_path))
    window.show()
    cards = (Card("takeoff"), Card("wait", 20), Card("land"))
    window.program_panel.set_cards(cards)
    try:
        deadline = time.monotonic() + 3
        queued = False
        while time.monotonic() < deadline:
            app.processEvents()
            window.engine.operator()
            state = window.engine.snapshot()
            if state.mode == "ready" and state.telemetry.received_at and not queued:
                window.engine.run_program(cards)
                queued = True
            if state.program.index == 1:
                break
            time.sleep(0.02)
        engine = window.engine
        wait_until = engine._program_wait_until
        assert wait_until is not None
        window.language_selector.setCurrentIndex(window.language_selector.findData("it"))
        assert window.engine is engine
        assert engine._program_wait_until == wait_until
        assert engine.snapshot().program.status == "running"
        assert engine.snapshot().program.index == 1
        assert window.program_panel.cards() == cards
        assert "Scheda 2/3" in window.program_panel.status.text()
        assert "Attendi / staziona" in window.program_panel.status.text()
    finally:
        window.close()
        app.processEvents()
