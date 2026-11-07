"""A command palette, reorderable card queue, and visible parameter editor."""

from pathlib import Path

from PySide6.QtCore import QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLayout,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QStyledItemDelegate,
    QVBoxLayout,
    QWidget,
)

from .model import ProgramProgress
from .program import SPECS, Card, example_program, load_program, save_program, validate_program

ROLE = Qt.ItemDataRole.UserRole


def action(text, callback, name=""):
    control = QPushButton(text)
    control.setObjectName(name)
    control.clicked.connect(lambda checked=False: callback())
    return control


class CardDelegate(QStyledItemDelegate):
    def __init__(self, parent):
        super().__init__(parent)
        self.progress = None

    def sizeHint(self, option, index):
        return QSize(300, 86)

    def paint(self, painter: QPainter, option, index):
        card = index.data(ROLE)
        if not isinstance(card, Card):
            return
        spec = SPECS[card.kind]
        p = painter
        p.save()
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(option.rect).adjusted(2, 4, -7, -4)
        active = self.progress and self.progress.status == "running" and self.progress.index == index.row()
        done = self.progress and index.row() < self.progress.completed
        selected = self.parent().currentIndex() == index
        p.setBrush(QColor("#203b42" if active else "#1b2b39" if selected else "#15212d"))
        p.setPen(QPen(QColor(spec.color if active or selected else "#2b3a47"), 2 if active else 1))
        p.drawRoundedRect(rect, 10, 10)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(spec.color))
        p.drawRoundedRect(QRectF(rect.left(), rect.top() + 12, 4, rect.height() - 24), 2, 2)
        circle = QRectF(rect.left() + 16, rect.top() + 20, 34, 34)
        p.setBrush(QColor("#293d48"))
        p.drawEllipse(circle)
        p.setPen(QColor(spec.color))
        p.setFont(QFont("Segoe UI", 10, QFont.Weight.DemiBold))
        p.drawText(circle, Qt.AlignmentFlag.AlignCenter, "✓" if done else str(index.row() + 1).zfill(2))
        title = QRectF(rect.left() + 64, rect.top() + 15, rect.width() - 175, 24)
        p.setPen(QColor("#edf3f7"))
        p.setFont(QFont("Segoe UI", 11, QFont.Weight.DemiBold))
        p.drawText(
            title,
            Qt.AlignmentFlag.AlignVCenter,
            p.fontMetrics().elidedText(spec.title, Qt.TextElideMode.ElideRight, int(title.width())),
        )
        p.setFont(QFont("Segoe UI", 8))
        p.setPen(QColor("#92a9b7"))
        subtitle = (
            "Running…"
            if active
            else "Finished"
            if done
            else (f"{spec.parameter} · editable" if spec.default is not None else "Flight command")
        )
        p.drawText(
            QRectF(rect.left() + 64, rect.top() + 43, rect.width() - 150, 20),
            Qt.AlignmentFlag.AlignVCenter,
            subtitle,
        )
        p.setPen(QColor(spec.color))
        p.setFont(QFont("Segoe UI", 12, QFont.Weight.DemiBold))
        value = f"{card.value} {spec.unit}" if card.value is not None else spec.symbol
        p.drawText(
            QRectF(rect.right() - 100, rect.top() + 22, 80, 30),
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
            value,
        )
        p.restore()


class ProgramPanel(QWidget):
    run_requested = Signal(object)
    stop_requested = Signal()

    def __init__(self):
        super().__init__()
        self._busy = False
        self._ready = False
        self._progress = ProgramProgress()
        self.setMinimumHeight(430)
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 12, 0, 0)
        root.setSpacing(22)
        palette = QVBoxLayout()
        palette.setSpacing(8)
        title = QLabel("COMMAND CARDS")
        title.setStyleSheet("font-weight:700; color:#92a9b7; letter-spacing:2px;")
        palette.addWidget(title)
        hint = QLabel("Click a command to add a card.")
        hint.setObjectName("muted")
        palette.addWidget(hint)
        self.palette_widget = QWidget()
        self.palette_widget.setStyleSheet("background:#0d141d;")
        choices = QVBoxLayout(self.palette_widget)
        choices.setContentsMargins(0, 0, 7, 0)
        choices.setSpacing(5)
        self.palette_buttons = {}
        for kind, spec in SPECS.items():
            control = action(
                spec.symbol + "   " + spec.title, lambda checked=False, k=kind: self.add_card(Card.default(k))
            )
            control.setStyleSheet(f"text-align:left; border-left:3px solid {spec.color}; padding:9px 12px;")
            control.setToolTip(
                f"{spec.minimum}–{spec.maximum} {spec.unit}" if spec.default is not None else spec.title
            )
            choices.addWidget(control)
            self.palette_buttons[kind] = control
        choices.addStretch()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(self.palette_widget)
        scroll.setStyleSheet("QScrollArea { border:0; background:transparent; }")
        scroll.setFixedWidth(236)
        palette.addWidget(scroll)
        root.addLayout(palette)

        workspace = QVBoxLayout()
        workspace.setSpacing(8)
        head = QHBoxLayout()
        title = QLabel("Your flight")
        title.setStyleSheet("font-size:23px; font-weight:600;")
        head.addWidget(title)
        head.addStretch()
        self.count = QLabel("0 cards")
        self.count.setObjectName("muted")
        head.addWidget(self.count)
        workspace.addLayout(head)
        hint = QLabel("Read from top to bottom. Drag cards to change the order.")
        hint.setObjectName("muted")
        workspace.addWidget(hint)
        self.queue = QListWidget()
        self.queue.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.queue.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.queue.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.queue.setStyleSheet(
            "QListWidget { background:#101923; border:1px solid #263541; border-radius:10px; padding:7px; }"
        )
        self.queue.setSpacing(0)
        self.delegate = CardDelegate(self.queue)
        self.queue.setItemDelegate(self.delegate)
        self.queue.currentRowChanged.connect(self.selection_changed)
        self.queue.model().rowsMoved.connect(self.edited)
        workspace.addWidget(self.queue, 1)
        edits = QHBoxLayout()
        self.up = action("↑ Move", lambda: self.move_card(-1))
        self.down = action("↓ Move", lambda: self.move_card(1))
        self.copy = action("Duplicate", self.duplicate_card)
        self.remove = action("Remove", self.remove_card)
        for control in (self.up, self.down, self.copy, self.remove):
            edits.addWidget(control)
        edits.addStretch()
        workspace.addLayout(edits)
        self.progress = QProgressBar()
        self.progress.setTextVisible(False)
        self.progress.setFixedHeight(5)
        self.progress.setStyleSheet(
            "QProgressBar { background:#24333d; border:0; } QProgressBar::chunk { background:#6de5d2; }"
        )
        workspace.addWidget(self.progress)
        self.status = QLabel()
        self.status.setWordWrap(True)
        self.status.setMinimumHeight(32)
        self.status.setObjectName("muted")
        workspace.addWidget(self.status)
        runrow = QHBoxLayout()
        self.run = action("▶  Run from top", lambda: self.run_requested.emit(self.cards()), "primary")
        self.stop = action("■  Stop & land", self.stop_requested.emit, "danger")
        runrow.addWidget(self.run)
        runrow.addWidget(self.stop)
        workspace.addLayout(runrow)
        root.addLayout(workspace, 1)

        inspector = QVBoxLayout()
        inspector.setSizeConstraint(QLayout.SizeConstraint.SetMinimumSize)
        inspector.setContentsMargins(0, 0, 6, 0)
        inspector.setSpacing(10)
        title = QLabel("CARD SETTINGS")
        title.setStyleSheet("font-weight:700; color:#92a9b7; letter-spacing:2px;")
        inspector.addWidget(title)
        self.selected_title = QLabel("Select a card")
        self.selected_title.setStyleSheet("font-size:18px; font-weight:600;")
        self.selected_title.setWordWrap(True)
        inspector.addWidget(self.selected_title)
        self.parameter_label = QLabel()
        self.parameter = QSpinBox()
        self.parameter.setFixedHeight(56)
        self.parameter.setStyleSheet(
            "QSpinBox { background:#192b37; border:1px solid #537184; border-radius:8px; padding:12px; font-size:22px; }"
        )
        self.parameter.valueChanged.connect(self.parameter_changed)
        form = QFormLayout()
        form.addRow(self.parameter_label)
        form.addRow(self.parameter)
        inspector.addLayout(form)
        self.parameter_hint = QLabel("Select a card to adjust its parameter.")
        self.parameter_hint.setWordWrap(True)
        self.parameter_hint.setMinimumHeight(54)
        self.parameter_hint.setObjectName("muted")
        inspector.addWidget(self.parameter_hint)
        self.position = QLabel("Simulator position\nX 0.0 m   Y 0.0 m\nHeading 0°")
        self.position.setFixedHeight(76)
        self.position.setStyleSheet(
            "color:#a9c2cd; background:#172632; border-radius:8px; padding:10px; font-size:11px;"
        )
        inspector.addWidget(self.position)
        inspector.addStretch()
        body = QWidget()
        body.setLayout(inspector)
        body.setStyleSheet("background:#0d141d;")
        inspector_scroll = QScrollArea()
        inspector_scroll.setWidgetResizable(True)
        inspector_scroll.setWidget(body)
        inspector_scroll.setStyleSheet("QScrollArea { border:0; background:transparent; }")
        column = QWidget()
        column.setFixedWidth(225)
        column_layout = QVBoxLayout(column)
        column_layout.setContentsMargins(0, 0, 0, 0)
        column_layout.setSpacing(8)
        column_layout.addWidget(inspector_scroll, 1)
        self.example = action("Load example", self.load_example)
        self.open = action("Open program…", self.open_file)
        self.save = action("Save program…", self.save_file)
        self.clear = action("Clear all", self.clear_cards)
        for control in (self.example, self.open, self.save, self.clear):
            column_layout.addWidget(control)
        root.addWidget(column)
        self.load_example()

    def cards(self):
        return tuple(self.queue.item(i).data(ROLE) for i in range(self.queue.count()))

    def add_card(self, card, row=None):
        if self._busy:
            return
        if self.queue.count() >= 100:
            QMessageBox.information(self, "Program full", "A program can contain at most 100 cards.")
            return
        item = QListWidgetItem()
        item.setData(ROLE, card)
        if row is None:
            self.queue.addItem(item)
        else:
            self.queue.insertItem(row, item)
        self.queue.setCurrentItem(item)
        self.edited()

    def set_cards(self, cards):
        if self._busy:
            return
        self.queue.clear()
        for card in cards:
            self.add_card(card)
        self.queue.setCurrentRow(0)
        self.edited()

    def load_example(self):
        self.set_cards(example_program())
        self.queue.setCurrentRow(1)

    def clear_cards(self):
        if not self._busy:
            self.queue.clear()
            self.edited()

    def move_card(self, delta):
        if self._busy:
            return
        row = self.queue.currentRow()
        target = row + delta
        if row >= 0 and 0 <= target < self.queue.count():
            item = self.queue.takeItem(row)
            self.queue.insertItem(target, item)
            self.queue.setCurrentRow(target)
            self.edited()

    def duplicate_card(self):
        row = self.queue.currentRow()
        if row >= 0:
            self.add_card(self.queue.item(row).data(ROLE), row + 1)

    def remove_card(self):
        if not self._busy and self.queue.currentRow() >= 0:
            self.queue.takeItem(self.queue.currentRow())
            self.edited()

    def selection_changed(self, *_):
        item = self.queue.currentItem()
        card = item.data(ROLE) if item else None
        self.parameter.blockSignals(True)
        self.parameter.setVisible(card is not None and card.value is not None)
        self.parameter_label.setVisible(card is not None and card.value is not None)
        if card:
            spec = SPECS[card.kind]
            self.selected_title.setText(spec.title)
            if card.value is not None:
                self.parameter_label.setText(spec.parameter)
                self.parameter.setRange(spec.minimum, spec.maximum)
                self.parameter.setSuffix(" " + spec.unit)
                self.parameter.setValue(card.value)
                text = "Relative distance, not an absolute altitude.\n" if card.kind in ("up", "down") else ""
                self.parameter_hint.setText(text + f"Allowed: {spec.minimum}–{spec.maximum} {spec.unit}")
            else:
                self.parameter_hint.setText(
                    "No adjustable parameter."
                    + (" Flips need at least 50% battery." if card.kind.startswith("flip_") else "")
                )
        else:
            self.selected_title.setText("Select a card")
            self.parameter_hint.setText("Choose a card to adjust its parameter.")
        self.parameter.blockSignals(False)

    def parameter_changed(self, value):
        if not self._busy and self.queue.currentItem():
            card = self.queue.currentItem().data(ROLE)
            if card.value is not None:
                self.queue.currentItem().setData(ROLE, Card(card.kind, value))
                self.edited()

    def edited(self, *_):
        self.count.setText(f"{self.queue.count()} cards")
        self.update_controls()
        self.queue.viewport().update()

    def update_controls(self):
        try:
            validate_program(self.cards())
            valid, hint = True, "Ready to run. Each card finishes before the next starts."
        except ValueError as exc:
            valid, hint = False, str(exc)
        self.run.setEnabled(valid and self._ready and not self._busy)
        self.stop.setEnabled(self._busy)
        matching = self._progress.cards == [{"kind": c.kind, "value": c.value} for c in self.cards()]
        self.delegate.progress = self._progress if matching else None
        if self._busy:
            self.status.setText(
                f"Card {self._progress.index + 1}/{self._progress.total} · {self._progress.detail}"
            )
        elif matching and self._progress.status != "idle":
            self.status.setText(self._progress.detail)
        else:
            self.status.setText(
                hint if not valid or self._ready else "Connect to the simulator or drone to run."
            )
        self.progress.setRange(0, max(1, self._progress.total if matching else self.queue.count()))
        self.progress.setValue(self._progress.completed if matching else 0)

    def set_state(self, state, ready, simulator=True):
        self._busy = state.program.status == "running"
        self._ready = ready and state.flight == "grounded" and state.telemetry.battery >= 25
        self._progress = state.program
        for control in (
            self.palette_widget,
            self.parameter,
            self.up,
            self.down,
            self.copy,
            self.remove,
            self.example,
            self.open,
            self.save,
            self.clear,
        ):
            control.setEnabled(not self._busy)
        self.queue.setDragEnabled(not self._busy)
        self.queue.setAcceptDrops(not self._busy)
        self.position.setVisible(simulator)
        data = state.telemetry.values
        self.position.setText(
            f"SIMULATOR POSITION\nX {data.get('sim_x', 0) / 100:.1f} m   Y {data.get('sim_y', 0) / 100:.1f} m\nHeading {data.get('yaw', 0):.0f}°"
        )
        self.update_controls()
        self.queue.viewport().update()

    def open_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "Open program", "", "Tello program (*.json)")
        if path:
            try:
                self.set_cards(load_program(path))
            except (OSError, ValueError) as exc:
                QMessageBox.warning(self, "Could not open program", str(exc))

    def save_file(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Save program", "my-flight.tello.json", "Tello program (*.json)"
        )
        if path:
            try:
                save_program(Path(path), self.cards())
            except (OSError, ValueError) as exc:
                QMessageBox.warning(self, "Could not save program", str(exc))
