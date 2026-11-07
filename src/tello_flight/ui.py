"""Camera-first Qt desktop console, inspired by the Tello app's Mode 2 layout."""

import ipaddress
import logging
import math
import os
import time
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import (
    QColor,
    QFont,
    QFontDatabase,
    QImage,
    QKeyEvent,
    QLinearGradient,
    QPainter,
    QPen,
    QPolygonF,
)
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from . import __version__
from .diagnostics import SESSION, export_bundle
from .engine import TELEMETRY_TIMEOUT, FlightEngine
from .model import Connection, FlightState
from .video import VideoReceiver

LOG = logging.getLogger(__name__)
CYAN = QColor("#6de5d2")
WHITE = QColor("#ecf3f7")


def ensure_fonts():
    # Windows' offscreen Qt plugin has no automatic font discovery. Load local
    # system fonts for readable headless screenshots without shipping font files.
    if not QFontDatabase.families():
        fonts = Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts"
        for path in (
            fonts / "segoeui.ttf",
            fonts / "segoeuib.ttf",
            fonts / "segoeuil.ttf",
            Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
        ):
            if path.is_file():
                QFontDatabase.addApplicationFont(str(path))


STYLE = """
QMainWindow, QDialog { background: #0d141d; color: #ecf3f7; }
QWidget { color: #ecf3f7; font-family: 'Segoe UI', 'DejaVu Sans'; font-size: 13px; }
QLabel { background: transparent; }
QPushButton { background: #192631; border: 1px solid #34434e; border-radius: 8px;
              padding: 10px 17px; color: #e5edf3; }
QPushButton:hover { background: #263c48; border-color: #6de5d2; }
QPushButton:pressed { background: #315961; }
QPushButton:disabled { color: #65747d; border-color: #26333e; background: #15202a; }
QPushButton#primary { color: #092923; background: #6de5d2; border: 0; font-weight: 700; }
QPushButton#primary:hover { background: #9df1e4; }
QPushButton#danger { color: #ffaaa7; background: #302027; border-color: #69383e; }
QPushButton#ghost { background: transparent; }
QLabel#muted { color: #8295a4; font-size: 11px; }
QLabel#badge { color: #6de5d2; background: #18332f; border-radius: 5px; padding: 6px 10px;
              font-size: 11px; font-weight: 700; }
QLineEdit, QComboBox, QPlainTextEdit { background: #16232e; border: 1px solid #34434e;
                                   border-radius: 6px; padding: 8px; }
QComboBox QAbstractItemView { background: #16232e; selection-background-color: #315961; }
QDialogButtonBox QPushButton { min-width: 70px; }
"""


def button(text, callback, name=""):
    result = QPushButton(text)
    result.setObjectName(name)
    result.clicked.connect(callback)
    result.setFocusPolicy(Qt.FocusPolicy.NoFocus)
    return result


class Joystick(QWidget):
    changed = Signal(float, float)

    def __init__(self, title, horizontal, vertical, parent=None):
        super().__init__(parent)
        self.title, self.horizontal, self.vertical = title, horizontal, vertical
        self.x = self.y = 0.0
        self.dragging = False
        self.setFixedSize(210, 245)
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        self.setToolTip("Hold and drag to move. Release to center.")

    def reset(self):
        self.dragging = False
        self.x = self.y = 0
        self.changed.emit(0, 0)
        self.update()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.isEnabled():
            self.dragging = True
            self.mouseMoveEvent(event)

    def mouseMoveEvent(self, event):
        if not self.dragging:
            return
        x, y = (event.position().x() - 105) / 70, (event.position().y() - 112) / 70
        radius = max(1, math.hypot(x, y))
        self.x, self.y = x / radius, y / radius
        self.changed.emit(self.x, -self.y)
        self.update()

    def mouseReleaseEvent(self, event):
        self.reset()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        center = QPointF(105, 112)
        p.setBrush(QColor(8, 18, 26, 150))
        p.setPen(QPen(QColor(230, 244, 250, 100), 1.3))
        p.drawEllipse(center, 82, 82)
        p.setPen(QPen(QColor(230, 244, 250, 35), 1))
        p.drawEllipse(center, 61, 61)
        p.drawLine(QPointF(44, 112), QPointF(166, 112))
        p.drawLine(QPointF(105, 51), QPointF(105, 173))
        p.setPen(QColor("#bfccd3"))
        p.setFont(QFont("Segoe UI", 11))
        for rect, label in [
            (QRectF(75, 30, 60, 22), "+"),
            (QRectF(75, 172, 60, 22), "−"),
            (QRectF(23, 100, 25, 24), "‹"),
            (QRectF(162, 100, 25, 24), "›"),
        ]:
            p.drawText(rect, Qt.AlignmentFlag.AlignCenter, label)
        p.setBrush(QColor("#6de5d2") if self.dragging else QColor(224, 238, 243, 235))
        p.setPen(QPen(QColor(255, 255, 255, 120), 3))
        p.drawEllipse(center + QPointF(self.x * 61, self.y * 61), 19, 19)
        p.setFont(QFont("Segoe UI", 9, QFont.Weight.DemiBold))
        p.setPen(WHITE)
        p.drawText(QRectF(0, 205, 210, 20), Qt.AlignmentFlag.AlignCenter, self.title)
        p.setFont(QFont("Segoe UI", 8))
        p.setPen(QColor("#9bafb9"))
        p.drawText(
            QRectF(0, 225, 210, 17), Qt.AlignmentFlag.AlignCenter, self.horizontal + "  /  " + self.vertical
        )
        p.end()


class CameraView(QWidget):
    def __init__(self):
        super().__init__()
        self.setMinimumHeight(430)
        self.state = FlightState()
        self.simulator = True
        self.frame = None
        self.frame_at = 0.0
        self.grid = True
        self.left = Joystick("THROTTLE / YAW", "A · D", "W · S", self)
        self.right = Joystick("PITCH / ROLL", "← · →", "↑ · ↓", self)

    def resizeEvent(self, event):
        self.left.move(35, self.height() - 270)
        self.right.move(self.width() - 245, self.height() - 270)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        if self.frame is not None:
            p.fillRect(self.rect(), QColor("#080f16"))
            scaled = self.frame.scaled(self.size(), Qt.AspectRatioMode.KeepAspectRatio)
            p.drawImage((w - scaled.width()) // 2, (h - scaled.height()) // 2, scaled)
        elif self.simulator:
            self._room(p, w, h)
        else:
            p.fillRect(self.rect(), QColor("#101c26"))
        shade = QLinearGradient(0, h * 0.5, 0, h)
        shade.setColorAt(0, QColor(4, 12, 20, 0))
        shade.setColorAt(1, QColor(4, 12, 20, 200))
        p.fillRect(self.rect(), shade)
        # Official-style camera HUD, with a restrained cyan accent.
        p.setPen(QColor("#d7e6ed"))
        p.setFont(QFont("Segoe UI", 9, QFont.Weight.DemiBold))
        label = "SIMULATED CAMERA  /  NO DRONE CONNECTED" if self.simulator else "TELLO CAMERA"
        p.drawText(27, 34, label)
        p.setPen(CYAN)
        p.drawEllipse(QPointF(w - 132, 29), 3, 3)
        p.setFont(QFont("Segoe UI", 8))
        video_age = time.monotonic() - self.frame_at
        status = "SIMULATION" if self.simulator else ("LIVE" if video_age < 2 else "NO VIDEO")
        p.drawText(w - 120, 34, status)
        p.setPen(QPen(QColor(230, 244, 250, 90), 1))
        cx, cy = w / 2, h * 0.45
        if self.grid:
            p.setPen(QPen(QColor(220, 240, 248, 22), 1))
            for x in (w / 3, w * 2 / 3):
                p.drawLine(QPointF(x, 60), QPointF(x, h - 50))
            for y in (h / 3, h * 2 / 3):
                p.drawLine(QPointF(20, y), QPointF(w - 20, y))
        p.setPen(QPen(QColor(230, 244, 250, 140), 1))
        p.drawLine(QPointF(cx - 13, cy), QPointF(cx - 4, cy))
        p.drawLine(QPointF(cx + 4, cy), QPointF(cx + 13, cy))
        p.drawLine(QPointF(cx, cy - 13), QPointF(cx, cy - 4))
        p.drawLine(QPointF(cx, cy + 4), QPointF(cx, cy + 13))
        p.drawEllipse(QPointF(cx, cy), 2, 2)
        if not self.simulator and (self.frame is None or video_age > 2):
            p.fillRect(QRectF(cx - 190, cy + 30, 380, 60), QColor(8, 18, 27, 220))
            p.setPen(WHITE)
            p.drawText(
                QRectF(cx - 190, cy + 35, 380, 25),
                Qt.AlignmentFlag.AlignCenter,
                "Camera unavailable" if self.frame else "Camera is off",
            )
            p.setPen(QColor("#91a5b2"))
            p.drawText(
                QRectF(cx - 190, cy + 60, 380, 20),
                Qt.AlignmentFlag.AlignCenter,
                "Enable video while grounded to start the preview",
            )
        # Two values sit between the virtual sticks.
        for offset, value, unit, caption in [
            (-92, self.state.telemetry.height, "m", "HEIGHT"),
            (92, self.state.telemetry.speed, "m/s", "SPEED"),
        ]:
            rect = QRectF(cx + offset - 80, h - 132, 160, 38)
            p.setPen(WHITE)
            p.setFont(QFont("Segoe UI", 25, QFont.Weight.Light))
            valid = (
                self.state.telemetry.received_at
                and time.monotonic() - self.state.telemetry.received_at < TELEMETRY_TIMEOUT
            )
            p.drawText(rect, Qt.AlignmentFlag.AlignCenter, f"{value:.1f}" if valid else "—")
            p.setFont(QFont("Segoe UI", 9))
            p.setPen(QColor("#94aab7"))
            p.drawText(rect.translated(0, 35), Qt.AlignmentFlag.AlignCenter, unit + "  ·  " + caption)
        p.setPen(QColor("#7d96a5"))
        p.setFont(QFont("Segoe UI", 8))
        p.drawText(
            QRectF(0, h - 34, w, 20),
            Qt.AlignmentFlag.AlignCenter,
            "MODE 2     •     HOLD TO MOVE     •     RELEASE TO HOVER",
        )
        p.end()

    def _room(self, p, w, h):
        # Procedural indoor scene, deliberately labeled simulation; no stock camera footage.
        wall = QLinearGradient(0, 0, 0, h)
        wall.setColorAt(0, QColor("#182b38"))
        wall.setColorAt(0.55, QColor("#36525c"))
        wall.setColorAt(1, QColor("#10232d"))
        p.fillRect(self.rect(), wall)
        horizon = h * 0.48 + min(self.state.telemetry.height, 2.5) * 18
        shift = self.state.telemetry.values.get("yaw", 0) * 0.4
        p.setPen(QPen(QColor("#48606a"), 1))
        for i in range(-1, 9):
            x = i * w / 7 - shift
            p.drawLine(QPointF(x, 0), QPointF(x, horizon))
        p.setPen(Qt.PenStyle.NoPen)
        for i in range(4):
            x = w * (0.17 + i * 0.20) - shift
            p.setBrush(QColor("#294653"))
            p.drawRoundedRect(QRectF(x, h * 0.16, w * 0.12, h * 0.25), 2, 2)
            p.setBrush(QColor("#789690"))
            p.drawRect(QRectF(x + 5, h * 0.16 + 5, w * 0.12 - 10, h * 0.25 - 10))
            p.setPen(QPen(QColor("#36515b"), 4))
            p.drawLine(QPointF(x + w * 0.06, h * 0.16), QPointF(x + w * 0.06, h * 0.41))
            p.setPen(Qt.PenStyle.NoPen)
        floor = QLinearGradient(0, horizon, 0, h)
        floor.setColorAt(0, QColor("#415459"))
        floor.setColorAt(1, QColor("#172e38"))
        p.fillRect(QRectF(0, horizon, w, h - horizon), floor)
        p.setPen(QPen(QColor(145, 168, 170, 50), 1))
        for i in range(-5, 9):
            p.drawLine(QPointF(w / 2 + (i - 2) * 30, horizon), QPointF(i * w / 5, h))
        for depth in (0.08, 0.19, 0.36, 0.62, 0.96):
            y = horizon + (h - horizon) * depth
            p.drawLine(QPointF(0, y), QPointF(w, y))
        p.setPen(QPen(QColor(180, 201, 194, 70), 2))
        p.drawEllipse(QPointF(w / 2, horizon + (h - horizon) * 0.55), w * 0.10, h * 0.035)
        p.setFont(QFont("Segoe UI", 14, QFont.Weight.DemiBold))
        p.setPen(QColor(220, 236, 229, 75))
        p.drawText(
            QRectF(w / 2 - 80, horizon + (h - horizon) * 0.55 - 15, 160, 30),
            Qt.AlignmentFlag.AlignCenter,
            "H",
        )
        p.setBrush(QColor(4, 15, 24, 80))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawPolygon(
            QPolygonF(
                [QPointF(0, 0), QPointF(w * 0.12, h * 0.1), QPointF(w * 0.12, horizon), QPointF(0, h * 0.8)]
            )
        )


class SessionDialog(QDialog):
    def __init__(self, config, parent):
        super().__init__(parent)
        self.setWindowTitle("Flight session")
        self.setMinimumWidth(430)
        layout = QVBoxLayout(self)
        title = QLabel("Choose your flight session")
        title.setStyleSheet("font-size: 20px; font-weight: 600; margin: 10px 0;")
        layout.addWidget(title)
        form = QFormLayout()
        self.mode = QComboBox()
        self.mode.addItems(["Simulator — no drone required", "Live Tello — connected over Wi-Fi"])
        self.mode.setCurrentIndex(0 if config.simulator else 1)
        self.host = QLineEdit(config.host)
        self.local = QLineEdit(config.local_address)
        form.addRow("Session", self.mode)
        form.addRow("Drone IPv4 address", self.host)
        form.addRow("Local bind IPv4", self.local)
        layout.addLayout(form)
        hint = QLabel(
            "Connect your computer to TELLO Wi-Fi before choosing live mode.\n"
            "Leave local bind as 0.0.0.0 unless selecting a specific adapter.\n"
            "Live hardware behavior has not yet been validated."
        )
        hint.setObjectName("muted")
        hint.setWordWrap(True)
        layout.addWidget(hint)
        actions = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        actions.accepted.connect(self.accept)
        actions.rejected.connect(self.reject)
        layout.addWidget(actions)

    def accept(self):
        try:
            ipaddress.IPv4Address(self.host.text().strip())
            ipaddress.IPv4Address(self.local.text().strip())
        except ValueError:
            QMessageBox.warning(self, "Invalid address", "Enter valid IPv4 addresses.")
            return
        super().accept()

    def connection(self):
        return Connection(
            simulator=self.mode.currentIndex() == 0,
            host=self.host.text().strip(),
            local_address=self.local.text().strip(),
        )


class FlightWindow(QMainWindow):
    def __init__(self, log_dir, config=None, autostart=True):
        super().__init__()
        ensure_fonts()
        self.log_dir = Path(log_dir)
        self.config = config or Connection()
        self.engine = None
        self.video = None
        self.keys = set()
        self._tick_count = 0
        self._last_frame_at = 0.0
        self._started = time.monotonic()
        self._last_state = None
        self._log_lines = []
        self._log_dialog = None
        self._log_view = None
        self.setWindowTitle("Tello Flight · Local flight console")
        self.resize(1280, 850)
        self.setMinimumSize(1024, 740)
        self.setStyleSheet(STYLE)
        root = QWidget()
        self.setCentralWidget(root)
        layout = QVBoxLayout(root)
        layout.setContentsMargins(26, 18, 26, 14)
        layout.setSpacing(12)
        header = QHBoxLayout()
        wordmark = QLabel("TELLO <span style='color:#849aa9;font-weight:300'>FLIGHT</span>")
        wordmark.setStyleSheet("font-size: 23px; font-weight: 700; letter-spacing: 3px;")
        header.addWidget(wordmark)
        header.addSpacing(18)
        self.badge = QLabel("SIMULATOR")
        self.badge.setObjectName("badge")
        header.addWidget(self.badge)
        header.addStretch()
        self.session_button = button("Session settings", self.session_dialog, "ghost")
        header.addWidget(self.session_button)
        self.connect_button = button("Connect", self.toggle_connection)
        header.addWidget(self.connect_button)
        layout.addLayout(header)
        status = QHBoxLayout()
        self.link_label = QLabel("●  DISCONNECTED")
        self.link_label.setStyleSheet("color: #6de5d2; font-size: 11px; font-weight: 600;")
        status.addWidget(self.link_label)
        status.addStretch()
        self.flight_label = QLabel("GROUNDED")
        self.battery_label = QLabel("BAT  —")
        self.temp_label = QLabel("TEMP  —")
        self.age_label = QLabel("DATA  —")
        for label in (self.flight_label, self.battery_label, self.temp_label, self.age_label):
            label.setStyleSheet("color:#a9bac6; font-size:11px; padding-left:24px;")
            status.addWidget(label)
        layout.addLayout(status)
        self.camera = CameraView()
        layout.addWidget(self.camera, 1)
        self.camera.left.changed.connect(lambda *_: self.send_intent())
        self.camera.right.changed.connect(lambda *_: self.send_intent())
        toolbar = QHBoxLayout()
        self.takeoff = button("↑  Take off", self.take_off, "primary")
        self.takeoff.setMinimumWidth(144)
        self.land = button("↓  Land", lambda: self.command("land"))
        self.hover = button("Hover · Space", self.hover_now)
        self.video_button = button("Camera on", self.toggle_video)
        self.grid_button = button("Grid", self.toggle_grid, "ghost")
        self.snapshot_button = button("Snapshot", self.save_snapshot, "ghost")
        self.emergency = button("Motor cut", self.motor_cut, "danger")
        for control in (
            self.takeoff,
            self.land,
            self.hover,
            self.video_button,
            self.snapshot_button,
            self.emergency,
        ):
            control.setEnabled(False)
        for control in (self.takeoff, self.land, self.hover):
            toolbar.addWidget(control)
        toolbar.addStretch()
        for control in (self.video_button, self.grid_button, self.snapshot_button, self.emergency):
            toolbar.addWidget(control)
        layout.addLayout(toolbar)
        self.message = QLabel("Starting simulator…")
        self.message.setObjectName("muted")
        self.message.setWordWrap(True)
        layout.addWidget(self.message)
        footer = QHBoxLayout()
        hint = QLabel("LOCAL FLIGHT CONSOLE   /   v" + __version__ + "   /   " + SESSION)
        hint.setObjectName("muted")
        footer.addWidget(hint)
        footer.addStretch()
        footer.addWidget(button("Flight log", self.show_logs, "ghost"))
        footer.addWidget(button("Save diagnostics", self.save_diagnostics, "ghost"))
        layout.addLayout(footer)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh)
        self.timer.start(50)
        QApplication.instance().applicationStateChanged.connect(self.application_state)
        if autostart:
            QTimer.singleShot(0, self.connect_session)

    def application_state(self, state):
        if state != Qt.ApplicationState.ApplicationActive:
            self.release_input()

    def release_input(self):
        self.keys.clear()
        self.camera.left.reset()
        self.camera.right.reset()
        if self.engine:
            self.engine.neutral()

    def send_intent(self):
        if not self.engine:
            return
        k = self.keys

        def axis(positive, negative):
            return int(positive in k) - int(negative in k)

        # Beginner-friendly limit: 30% stick range. Mode 2 mirrors the official app.
        channels = (
            30 * axis(Qt.Key.Key_Right, Qt.Key.Key_Left) + 30 * self.camera.right.x,
            30 * axis(Qt.Key.Key_Up, Qt.Key.Key_Down) - 30 * self.camera.right.y,
            30 * axis(Qt.Key.Key_W, Qt.Key.Key_S) - 30 * self.camera.left.y,
            30 * axis(Qt.Key.Key_D, Qt.Key.Key_A) + 30 * self.camera.left.x,
        )
        self.engine.operator(tuple(max(-30, min(30, v)) for v in channels))

    def keyPressEvent(self, event: QKeyEvent):
        if event.isAutoRepeat():
            return
        if event.key() == Qt.Key.Key_Space:
            self.hover_now()
        elif event.key() in (
            Qt.Key.Key_W,
            Qt.Key.Key_S,
            Qt.Key.Key_A,
            Qt.Key.Key_D,
            Qt.Key.Key_Up,
            Qt.Key.Key_Down,
            Qt.Key.Key_Left,
            Qt.Key.Key_Right,
        ):
            self.keys.add(event.key())
            self.send_intent()
        else:
            super().keyPressEvent(event)

    def keyReleaseEvent(self, event):
        if not event.isAutoRepeat():
            self.keys.discard(event.key())
            self.send_intent()

    def connect_session(self):
        self.engine = FlightEngine(self.config)
        self.engine.start()
        self._started = time.monotonic()
        self.camera.simulator = self.config.simulator
        self.badge.setText("SIMULATOR" if self.config.simulator else "LIVE TELLO")
        self.badge.setStyleSheet("" if self.config.simulator else "color:#ffca82;background:#403021;")
        self.connect_button.setText("Disconnect")

    def stop_session(self):
        if not self.engine:
            return True
        self.release_input()
        state = self.engine.snapshot()
        force = False
        if state.flight != "grounded":
            if not self.config.simulator:
                answer = QMessageBox.warning(
                    self,
                    "Flight status is not grounded",
                    "Land first. If the link is lost, inspect the drone.\n\n"
                    "Disconnect only after physically confirming the motors are stopped.",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
                    QMessageBox.StandardButton.Cancel,
                )
                if answer != QMessageBox.StandardButton.Yes:
                    return False
            force = True
        if self.video:
            self.video.close()
            self.video = None
        self.engine.close(force=force)
        self._collect_events()
        self.engine = None
        self.camera.frame = None
        self.connect_button.setText("Connect")
        return True

    def toggle_connection(self):
        if self.engine:
            self.stop_session()
        else:
            self.connect_session()

    def session_dialog(self):
        self.release_input()
        if self.engine and self.engine.snapshot().flight != "grounded":
            QMessageBox.information(self, "Land first", "Session settings are available while grounded.")
            return
        dialog = SessionDialog(self.config, self)
        if dialog.exec() == QDialog.DialogCode.Accepted and self.stop_session():
            self.config = dialog.connection()
            self.connect_session()

    def command(self, command):
        if command in ("land", "emergency"):
            self.release_input()
        if self.engine:
            self.engine.request(command)

    def take_off(self):
        self.release_input()
        if not self.config.simulator and (
            QMessageBox.question(
                self,
                "Take off",
                "Clear area, propeller guards fitted, and drone in sight?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.Cancel,
            )
            != QMessageBox.StandardButton.Yes
        ):
            return
        self.command("takeoff")

    def hover_now(self):
        self.release_input()

    def motor_cut(self):
        self.release_input()
        if (
            QMessageBox.warning(
                self,
                "Immediate motor cut",
                "This stops the motors immediately. An airborne drone will fall.\nSend motor cut?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.Cancel,
            )
            == QMessageBox.StandardButton.Yes
        ):
            self.command("emergency")

    def toggle_grid(self):
        self.camera.grid = not self.camera.grid
        self.camera.update()

    def toggle_video(self):
        if self.config.simulator:
            QMessageBox.information(self, "Simulated camera", "The simulator uses a generated indoor scene.")
            return
        if not self.engine:
            return
        if self.video:
            self.command("streamoff")
            self.video.close()
            self.video = None
            self.camera.frame = None
        else:
            try:
                self.video = VideoReceiver(self.config)
                self.video.start()
                self.command("streamon")
            except Exception as exc:
                LOG.exception("video_start_failed")
                self.video = None
                QMessageBox.warning(self, "Camera unavailable", str(exc))

    def save_snapshot(self):
        if self.camera.frame is None:
            QMessageBox.information(self, "No live frame", "Start the live camera before saving a snapshot.")
            return
        self.release_input()
        path, _ = QFileDialog.getSaveFileName(
            self, "Save camera snapshot", "tello-snapshot.png", "PNG (*.png)"
        )
        if path and not self.camera.frame.save(path):
            QMessageBox.warning(self, "Save failed", "Could not save the image.")

    def _collect_events(self):
        if not self.engine:
            return
        for timestamp, message in self.engine.events():
            line = datetime.fromtimestamp(timestamp).strftime("%H:%M:%S") + "  " + message
            self._log_lines.append(line)
            if self._log_view is not None:
                self._log_view.appendPlainText(line)
        self._log_lines = self._log_lines[-500:]

    def show_logs(self):
        self.release_input()
        dialog = QDialog(self)
        dialog.setWindowTitle("Flight log & diagnostics")
        dialog.resize(820, 520)
        layout = QVBoxLayout(dialog)
        label = QLabel("Persistent logs: " + str(self.log_dir))
        label.setWordWrap(True)
        label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(label)
        view = QPlainTextEdit()
        view.setReadOnly(True)
        view.setMaximumBlockCount(500)
        view.setPlainText("\n".join(self._log_lines))
        layout.addWidget(view)
        row = QHBoxLayout()
        if self.config.simulator:
            row.addWidget(button("Simulate signal loss", lambda: self.command("simulate_link_loss")))
        row.addStretch()
        row.addWidget(button("Save diagnostic bundle", self.save_diagnostics, "primary"))
        layout.addLayout(row)
        self._log_view = view
        dialog.exec()
        self._log_view = None

    def save_diagnostics(self):
        self.release_input()
        if self.engine and self.engine.snapshot().flight != "grounded" and not self.config.simulator:
            QMessageBox.information(
                self, "Land first", "Land before exporting diagnostics. Logs continue automatically."
            )
            return
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Save diagnostic bundle",
            "tello-diagnostics-" + datetime.now().strftime("%Y%m%d-%H%M%S") + ".zip",
            "ZIP (*.zip)",
        )
        if path:
            try:
                export_bundle(
                    path, self.log_dir, self.engine.snapshot() if self.engine else None, self.config
                )
                QMessageBox.information(
                    self,
                    "Diagnostics saved",
                    "Bundle includes logs, command timing, telemetry, connection IPs and system versions.\n"
                    "No camera images are included. Review it before sharing.",
                )
            except Exception as exc:
                LOG.exception("diagnostic_export_failed")
                QMessageBox.warning(self, "Export failed", str(exc))

    def refresh(self):
        state = self.engine.snapshot() if self.engine else FlightState()
        self._collect_events()
        active = QApplication.applicationState() == Qt.ApplicationState.ApplicationActive
        if active:
            if QApplication.activeModalWidget() is None:
                self.send_intent()
            elif self.engine:
                self.engine.operator()  # A responsive modal dialog intentionally holds neutral.
        elif self.engine:
            self.engine.neutral()
        age = time.monotonic() - state.telemetry.received_at
        fresh = age < TELEMETRY_TIMEOUT
        ready = state.mode == "ready" and fresh
        self.link_label.setText(
            "●  "
            + (
                "SIMULATOR CONNECTED"
                if ready and self.config.simulator
                else "TELLO CONNECTED"
                if ready
                else "TELEMETRY STALE"
                if state.mode == "ready"
                else state.mode.upper()
            )
        )
        self.link_label.setStyleSheet("color:" + ("#6de5d2" if ready else "#ffbd81") + ";font-size:11px;")
        self.flight_label.setText(state.flight.upper())
        self.battery_label.setText(f"BAT  {state.telemetry.battery:.0f}%" if fresh else "BAT  —")
        temp = state.telemetry.values.get("temph")
        self.temp_label.setText(f"TEMP  {temp:.0f}°C" if fresh and temp is not None else "TEMP  —")
        self.age_label.setText(f"DATA  {age:.1f}s" if state.telemetry.received_at else "DATA  —")
        self.takeoff.setEnabled(ready and state.flight == "grounded" and state.telemetry.battery >= 25)
        self.land.setEnabled(self.engine is not None and state.mode not in ("disconnected", "connecting"))
        self.hover.setEnabled(self.engine is not None)
        self.emergency.setEnabled(self.engine is not None)
        self.video_button.setEnabled(ready and state.flight == "grounded")
        self.video_button.setText("Camera off" if self.video else "Camera on")
        self.snapshot_button.setEnabled(
            self.camera.frame is not None and time.monotonic() - self.camera.frame_at < 2
        )
        self.camera.left.setEnabled(ready and state.flight == "airborne")
        self.camera.right.setEnabled(ready and state.flight == "airborne")
        self.message.setText(state.message)
        self.camera.state = state
        if self.video:
            latest = self.video.latest()
            if latest and latest[4] != self._last_frame_at:
                data, width, height, stride, timestamp = latest
                self.camera.frame = QImage(data, width, height, stride, QImage.Format.Format_RGB888).copy()
                self._last_frame_at = self.camera.frame_at = timestamp
            if self.video.error:
                self.message.setText("Video error: " + self.video.error)
        self.camera.update()
        marker = (state.mode, state.flight, fresh)
        if marker != self._last_state:
            LOG.info(
                "ui_state",
                extra={"data": {"mode": state.mode, "flight": state.flight, "telemetry_fresh": fresh}},
            )
            self._last_state = marker

    def closeEvent(self, event):
        if self.stop_session():
            LOG.info("application_closed")
            event.accept()
        else:
            event.ignore()
