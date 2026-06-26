import sys, os, json
import multiprocessing, logging
from dataclasses import dataclass
from typing import Any, Callable, Optional, Tuple

from PySide6.QtCore import Qt, Slot, QTimer, QRegularExpression, QObject, Signal
from PySide6.QtGui import QAction, QCloseEvent, QPalette, QColor, QRegularExpressionValidator, QTextCursor, QIcon
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QDoubleSpinBox, QFrame,
    QGridLayout, QGroupBox, QHBoxLayout, QLabel, QLineEdit,
    QListWidget, QListWidgetItem, QMainWindow, QMessageBox,
    QPushButton, QSpinBox, QStackedWidget, QStatusBar,
    QVBoxLayout, QWidget, QMenu, QSystemTrayIcon, QStyle,
    QColorDialog, QDialog, QFormLayout, QTextEdit
)

@dataclass
class RunRequest:
    mode: str
    config: dict[str, Any]

def get_resource_path(relative_path):
    """Resolve asset paths for bundled builds and local runs."""
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)

def process_wrapper(target_func, args, log_queue):
    """Route child-process output into the GUI log queue."""
    import sys
    import logging
    
    class StreamToQueue:
        def __init__(self, q): 
            self.q = q
        def write(self, text):
            if text and text.strip(): 
                self.q.put(str(text))
        def flush(self): 
            pass
    queue_stream = StreamToQueue(log_queue)
    sys.stdout = queue_stream
    sys.stderr = queue_stream
    root_logger = logging.getLogger()
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    proc_handler = logging.StreamHandler(queue_stream)
    proc_handler.setFormatter(logging.Formatter('%(asctime)s - [%(levelname)s] - %(message)s', '%Y-%m-%d %H:%M:%S'))
    root_logger.addHandler(proc_handler)
    root_logger.setLevel(logging.INFO)
    try:
        target_func(*args)
    except Exception as e:
        import traceback
        sys.stderr.write(f"❌ Process Crash: {e}\n{traceback.format_exc()}")
class BackendAdapter:
    """Map UI requests to the correct backend effect handler."""
    
    def __init__(self, error_queue):
        self.error_queue = error_queue

    def get_target_and_args(self, request: RunRequest) -> Tuple[Callable, tuple]:
        mode = request.mode
        cfg = request.config

        if mode == "off":
            from modules.off import OffModule
            module_instance = OffModule()
            return module_instance.run, ()

        elif mode == "static":
            from modules.static import StaticModule
            module_instance = StaticModule()
            return module_instance.run, (cfg.get("color", "RANDOM"), cfg.get("brightness", 100))

        elif mode == "cycle":
            from modules.cycle import CycleModule
            module_instance = CycleModule()
            return module_instance.run, (
                cfg.get("custom_colors"), 
                cfg.get("std_palette"), 
                cfg.get("speed", 10), 
                cfg.get("brightness", 100)
            )
        
        elif mode == "sys_monitor":
            from modules.sys_monitor import run_system_monitor
            return run_system_monitor, (cfg,)

        elif mode == "reactive":
            from modules.reactive import run_reactive_mode
            return run_reactive_mode, (cfg,)
        
        elif mode == "screen_sync":
            from modules.screen_sync import run_screen_sync
            return run_screen_sync, (cfg,)

        elif mode == "time_focus":
            from modules.time_focus import run_time_focus
            return run_time_focus, (cfg,)
        
        elif mode == "spotify_sync":
            from modules.spotify_sync import run_spotify_sync
            return run_spotify_sync, (cfg, self.error_queue)

        raise ValueError(f"Unknown mode: {mode}")

class SpotifyConfigDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("🔐 Spotify API Credentials")
        self.setFixedWidth(380)
        self.config_file = "spotify_config.json"

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.client_id_input = QLineEdit()
        self.client_secret_input = QLineEdit()
        self.client_secret_input.setEchoMode(QLineEdit.EchoMode.Password)
        
        form.addRow("Client ID:", self.client_id_input)
        form.addRow("Client Secret:", self.client_secret_input)
        layout.addLayout(form)
        save_btn = QPushButton("Save Credentials")
        save_btn.clicked.connect(self._save_config)
        layout.addWidget(save_btn)

        self._load_config()

    def _load_config(self):
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, "r") as f:
                    data = json.load(f)
                    self.client_id_input.setText(data.get("client_id", ""))
                    self.client_secret_input.setText(data.get("client_secret", ""))
            except: pass

    def _save_config(self):
        data = {
            "client_id": self.client_id_input.text().strip(),
            "client_secret": self.client_secret_input.text().strip()
        }
        try:
            with open(self.config_file, "w") as f:
                json.dump(data, f)
            QMessageBox.information(self, "Success", "Spotify credentials saved successfully!")
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save: {e}")

class ModePage(QWidget):
    """Base widget for mode-specific configuration pages."""
    def __init__(self, title: str):
        super().__init__()
        self.title = title
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(16, 16, 16, 16)
        self.layout.setSpacing(12)

        header = QLabel(title)
        header.setObjectName("pageTitle")
        self.layout.addWidget(header)

        self.form = QVBoxLayout()
        self.form.setSpacing(10)
        self.layout.addLayout(self.form)
        self.layout.addStretch(1)

    def add_group(self, group: QGroupBox) -> None:
        self.form.addWidget(group)

    def get_config(self) -> dict[str, Any]:
        """Return the current configuration from this page."""
        return {}

    def _make_brightness_spin(self) -> QSpinBox:
        spin = QSpinBox()
        spin.setRange(1, 100)
        spin.setValue(100)
        spin.setSuffix(" %")
        return spin

    def create_hex_input(self, default="#FF0000"):
        edit = QLineEdit(default)

        regex = QRegularExpression("^#[0-9A-Fa-f]{0,6}$")
        validator = QRegularExpressionValidator(regex)

        edit.setValidator(validator)
        edit.setMaxLength(7)

        edit.textChanged.connect(
            lambda text, e=edit: e.setText(text.upper())
        )

        return edit




class OffPage(ModePage):
    def __init__(self):
        super().__init__("Turn LEDs off")
        info = QLabel("Stops the keyboard lighting.\nUseful as an instant default state.")
        box = QGroupBox("Description")
        box_layout = QVBoxLayout(box)
        box_layout.addWidget(info)
        self.add_group(box)

    def get_config(self) -> dict[str, Any]:
        return {}


class StaticPage(ModePage):
    def __init__(self):
        super().__init__("Static Color")

        grp = QGroupBox("Static Settings")
        grid = QGridLayout(grp)

        self.color_input = self.create_hex_input("#FFFFFF")
        self.pick_btn = QPushButton("🎨")
        self.pick_btn.clicked.connect(self.pick_color)
        self.use_random = QCheckBox("Random Color")
        self.brightness = self._make_brightness_spin()
        self.use_random.toggled.connect(self.toggle_random)

        grid.addWidget(QLabel("HEX Color"), 0, 0)
        grid.addWidget(self.color_input, 0, 1)
        grid.addWidget(self.pick_btn, 0, 2)
        grid.addWidget(self.use_random, 1, 1)
        grid.addWidget(QLabel("Brightness"), 2, 0)
        grid.addWidget(self.brightness, 2, 1)

        self.add_group(grp)

    def toggle_random(self, checked):
        self.color_input.setEnabled(not checked)
        self.pick_btn.setEnabled(not checked)

    def pick_color(self):
        color = QColorDialog.getColor()
        if color.isValid():
            self.color_input.setText(color.name().upper())

    def get_config(self) -> dict[str, Any]:
        color = (
            "RANDOM"
            if self.use_random.isChecked()
            else self.color_input.text().strip().upper()
        )

        return {
            "color": color,
            "brightness": self.brightness.value()
        }

class CyclePage(ModePage):
    def __init__(self):
        super().__init__("Color Cycle")

        grp = QGroupBox("Cycle Settings")
        grid = QGridLayout(grp)

        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["Standard Colors", "Custom Colors"])
        self.mode_stack = QStackedWidget()

        # ===== PAGE 0 : STD =====
        std_page = QWidget()
        std_layout = QHBoxLayout(std_page)

        self.palette_combo = QComboBox()
        self.palette_combo.addItems([
            "stdcol3",
            "stdcol6",
            "stdcol12",
            "stdcol24"
        ])

        std_layout.addWidget(self.palette_combo)

        # ===== PAGE 1 : CUSTOM =====
        custom_page = QWidget()
        custom_layout = QHBoxLayout(custom_page)

        self.custom_hex1 = self.create_hex_input("#FF0000")

        self.custom_hex2 = self.create_hex_input("#0000FF")

        self.pick_btn1 = QPushButton("🎨")
        self.pick_btn2 = QPushButton("🎨")

        self.pick_btn1.clicked.connect(self.pick_color1)
        self.pick_btn2.clicked.connect(self.pick_color2)

        custom_layout.addWidget(self.custom_hex1)
        custom_layout.addWidget(self.pick_btn1)

        custom_layout.addWidget(self.custom_hex2)
        custom_layout.addWidget(self.pick_btn2)

        self.mode_stack.addWidget(std_page)
        self.mode_stack.addWidget(custom_page)

        self.mode_combo.currentIndexChanged.connect(
            self.mode_stack.setCurrentIndex
        )

        # --------------------
        # Common Settings
        # --------------------
        self.speed_spin = QDoubleSpinBox()
        self.speed_spin.setRange(1.0, 7200.0)
        self.speed_spin.setValue(10.0)
        self.speed_spin.setSuffix(" sec")

        self.brightness = self._make_brightness_spin()

        # --------------------
        # Layout
        # --------------------
        grid.addWidget(QLabel("Color Source"), 0, 0)
        grid.addWidget(self.mode_combo, 0, 1)

        grid.addWidget(QLabel("Palette"), 1, 0)
        grid.addWidget(self.mode_stack, 1, 1)

        grid.addWidget(QLabel("Speed (Full Loop)"), 2, 0)
        grid.addWidget(self.speed_spin, 2, 1)

        grid.addWidget(QLabel("Brightness"), 3, 0)
        grid.addWidget(self.brightness, 3, 1)

        self.add_group(grp)

    def pick_color1(self):
        from PySide6.QtWidgets import QColorDialog

        color = QColorDialog.getColor()

        if color.isValid():
            self.custom_hex1.setText(color.name().upper())


    def pick_color2(self):
        from PySide6.QtWidgets import QColorDialog

        color = QColorDialog.getColor()

        if color.isValid():
            self.custom_hex2.setText(color.name().upper())

    def get_config(self) -> dict[str, Any]:

        if self.mode_combo.currentIndex() == 0:
            std_palette = self.palette_combo.currentText()
            custom_colors = None

        else:
            std_palette = None
            custom_colors = [
                self.custom_hex1.text().strip().upper(),
                self.custom_hex2.text().strip().upper()
            ]

        return {
            "std_palette": std_palette,
            "custom_colors": custom_colors,
            "speed": self.speed_spin.value(),
            "brightness": self.brightness.value()
        }

class SystemMonitorPage(ModePage):
    def __init__(self):
        super().__init__("System Hardware Monitor")

        grp = QGroupBox("Monitor Settings")
        grid = QGridLayout(grp)
        self.metric_combo = QComboBox()
        self.metric_combo.addItems([
            "CPU Temperature (°C)",
            "GPU Temperature (°C)",
            "CPU Usage (%)",
            "GPU Usage (%)",
            "Memory Usage (%)",
            "Battery Status (%)"
        ])
        self.metric_combo.currentIndexChanged.connect(self._update_range_suffixes)
        self.min_spin = QSpinBox()
        self.min_spin.setRange(0, 100)
        self.min_spin.setValue(35)

        self.max_spin = QSpinBox()
        self.max_spin.setRange(20, 150)
        self.max_spin.setValue(80)
        self.color_mode_combo = QComboBox()
        self.color_mode_combo.addItems(["Standard (Green to Red)", "Custom Gradient"])
        self.color_mode_combo.currentIndexChanged.connect(self._toggle_custom_colors)
        self.custom_color_widget = QWidget()
        custom_layout = QHBoxLayout(self.custom_color_widget)
        custom_layout.setContentsMargins(0, 0, 0, 0)

        self.hex_min_color = self.create_hex_input("#00FF00")
        self.hex_max_color = self.create_hex_input("#FF0000")
        self.btn_pick_min = QPushButton("🎨")
        self.btn_pick_max = QPushButton("🎨")

        self.btn_pick_min.clicked.connect(lambda: self._pick_color(self.hex_min_color))
        self.btn_pick_max.clicked.connect(lambda: self._pick_color(self.hex_max_color))

        custom_layout.addWidget(QLabel("Min Color:"))
        custom_layout.addWidget(self.hex_min_color)
        custom_layout.addWidget(self.btn_pick_min)
        custom_layout.addWidget(QLabel("Max Color:"))
        custom_layout.addWidget(self.hex_max_color)
        custom_layout.addWidget(self.btn_pick_max)
        
        self.custom_color_widget.setVisible(False)
        self.brightness = self._make_brightness_spin()
        
        self.interval_spin = QDoubleSpinBox()
        self.interval_spin.setRange(0.2, 5.0)
        self.interval_spin.setValue(1.0)
        self.interval_spin.setSuffix(" sec")
        self.alert_title_label = QLabel("Critical Alert")
        self.alert_checkbox = QCheckBox("Enable Blinking Alert when Threshold exceeded")
        self.alert_checkbox.setChecked(False)
        
        self.alert_threshold_spin = QSpinBox()
        self.alert_threshold_spin.setRange(1, 200)
        self.alert_threshold_spin.setValue(110)
        self.alert_threshold_spin.setSuffix(" %")
        
        self.alert_threshold_spin.setEnabled(False)
        self.alert_checkbox.toggled.connect(self.alert_threshold_spin.setEnabled)

        alert_widget = QWidget()
        alert_layout = QHBoxLayout(alert_widget)
        alert_layout.setContentsMargins(0, 0, 0, 0)
        alert_layout.addWidget(self.alert_checkbox)
        alert_layout.addWidget(self.alert_threshold_spin)
        grid.addWidget(QLabel("System Metric"), 0, 0)
        grid.addWidget(self.metric_combo, 0, 1, 1, 2)

        grid.addWidget(QLabel("Trigger Range"), 1, 0)
        grid.addWidget(self.min_spin, 1, 1)
        grid.addWidget(self.max_spin, 1, 2)

        grid.addWidget(QLabel("Color Profile"), 2, 0)
        grid.addWidget(self.color_mode_combo, 2, 1, 1, 2)

        grid.addWidget(QLabel("Custom Palette"), 3, 0)
        grid.addWidget(self.custom_color_widget, 3, 1, 1, 2)

        grid.addWidget(QLabel("Update Interval"), 4, 0)
        grid.addWidget(self.interval_spin, 4, 1, 1, 2)

        grid.addWidget(QLabel("Brightness"), 5, 0)
        grid.addWidget(self.brightness, 5, 1, 1, 2)

        grid.addWidget(self.alert_title_label, 6, 0)
        grid.addWidget(alert_widget, 6, 1, 1, 2)

        self.add_group(grp)
        self._update_range_suffixes(0)

    def _update_range_suffixes(self, index: int) -> None:
        """Adjust range labels and defaults based on the selected metric."""
        suffix = " °C" if index in (0, 1) else " %"
        self.min_spin.setSuffix(suffix)
        self.max_spin.setSuffix(suffix)
        
        if index == 5:
            self.min_spin.setValue(0)
            self.max_spin.setValue(100)
            
            self.alert_title_label.setText("Battery Alert")
            self.alert_checkbox.setText("Blinking Alert when Battery drops below")
            self.alert_threshold_spin.setValue(15)
        else:
            self.alert_title_label.setText("Critical Alert")
            self.alert_checkbox.setText("Blinking Alert when Threshold exceeded") 
            
            if index in (0, 1): 
                self.min_spin.setValue(40)
                self.max_spin.setValue(80)
                self.alert_threshold_spin.setValue(110) 
            else: 
                self.min_spin.setValue(0)
                self.max_spin.setValue(100)
                self.alert_threshold_spin.setValue(90) 

    def _toggle_custom_colors(self, index: int) -> None:
        self.custom_color_widget.setVisible(index == 1)

    def _pick_color(self, line_edit: QLineEdit) -> None:
        color = QColorDialog.getColor()
        if color.isValid():
            line_edit.setText(color.name().upper())

    def get_config(self) -> dict[str, Any]:
        metric_map = {
            0: "cpu_temp",
            1: "gpu_temp",
            2: "cpu_usage",
            3: "gpu_usage",
            4: "mem_usage",
            5: "battery"
        }
        
        return {
            "metric": metric_map.get(self.metric_combo.currentIndex(), "cpu_usage"),
            "min_val": self.min_spin.value(),
            "max_val": self.max_spin.value(),
            "is_custom_color": self.color_mode_combo.currentIndex() == 1,
            "min_color": self.hex_min_color.text().strip().upper(),
            "max_color": self.hex_max_color.text().strip().upper(),
            "interval": self.interval_spin.value(),
            "brightness": self.brightness.value(),
            "enable_alert": self.alert_checkbox.isChecked(),
            "alert_threshold": self.alert_threshold_spin.value() / 100.0
        }

class ReactivePage(ModePage):
    def __init__(self):
        super().__init__("Reactive & Network Effects")

        grp = QGroupBox("Reactive Settings")
        grid = QGridLayout(grp)
        self.reactive_combo = QComboBox()
        self.reactive_combo.addItems([
            "Type Speed (CPS / WPM)",
            "Network Ping (Latency)"
        ])
        self.reactive_combo.currentIndexChanged.connect(self._on_mode_changed)
        self.host_label = QLabel("Target Host:")
        self.host_input = QLineEdit("google.com")
        self.host_label.setVisible(False)
        self.host_input.setVisible(False)
        self.min_spin = QSpinBox()
        self.min_spin.setRange(0, 1000)
        self.min_spin.setValue(0)

        self.max_spin = QSpinBox()
        self.max_spin.setRange(5, 5000)
        self.max_spin.setValue(15)
        self.color_mode_combo = QComboBox()
        self.color_mode_combo.addItems(["Standard (Green to Red)", "Custom Gradient"])
        self.color_mode_combo.currentIndexChanged.connect(self._toggle_custom_colors)
        self.custom_color_widget = QWidget()
        custom_layout = QHBoxLayout(self.custom_color_widget)
        custom_layout.setContentsMargins(0, 0, 0, 0)

        self.hex_min_color = self.create_hex_input("#00FF00")
        self.hex_max_color = self.create_hex_input("#FF0000")
        self.btn_pick_min = QPushButton("🎨")
        self.btn_pick_max = QPushButton("🎨")

        self.btn_pick_min.clicked.connect(lambda: self._pick_color(self.hex_min_color))
        self.btn_pick_max.clicked.connect(lambda: self._pick_color(self.hex_max_color))

        custom_layout.addWidget(QLabel("Min Color:"))
        custom_layout.addWidget(self.hex_min_color)
        custom_layout.addWidget(self.btn_pick_min)
        custom_layout.addWidget(QLabel("Max Color:"))
        custom_layout.addWidget(self.hex_max_color)
        custom_layout.addWidget(self.btn_pick_max)
        self.custom_color_widget.setVisible(False)
        self.brightness = self._make_brightness_spin()
        self.interval_spin = QDoubleSpinBox()
        self.interval_spin.setRange(0.1, 10.0)
        self.interval_spin.setValue(2.0)
        self.interval_spin.setSuffix(" sec")
        grid.addWidget(QLabel("Reactive Mode"), 0, 0)
        grid.addWidget(self.reactive_combo, 0, 1, 1, 2)

        grid.addWidget(self.host_label, 1, 0)
        grid.addWidget(self.host_input, 1, 1, 1, 2)

        grid.addWidget(QLabel("Trigger Range"), 2, 0)
        grid.addWidget(self.min_spin, 2, 1)
        grid.addWidget(self.max_spin, 2, 2)

        grid.addWidget(QLabel("Color Profile"), 3, 0)
        grid.addWidget(self.color_mode_combo, 3, 1, 1, 2)

        grid.addWidget(QLabel("Custom Palette"), 4, 0)
        grid.addWidget(self.custom_color_widget, 4, 1, 1, 2)

        grid.addWidget(QLabel("Update Interval"), 5, 0)
        grid.addWidget(self.interval_spin, 5, 1, 1, 2)

        grid.addWidget(QLabel("Brightness"), 6, 0)
        grid.addWidget(self.brightness, 6, 1, 1, 2)

        self.add_group(grp)
        self._on_mode_changed(0)

    def _on_mode_changed(self, index: int) -> None:
        """Switch the visible controls when the reactive mode changes."""
        is_ping = (index == 1)
        self.host_label.setVisible(is_ping)
        self.host_input.setVisible(is_ping)

        if is_ping:
            self.min_spin.setSuffix(" ms")
            self.max_spin.setSuffix(" ms")
            self.min_spin.setValue(30)
            self.max_spin.setValue(250)
            self.interval_spin.setEnabled(True)
        else:
            self.min_spin.setSuffix(" CPS")
            self.max_spin.setSuffix(" CPS")
            self.min_spin.setValue(0)
            self.max_spin.setValue(12)
            self.interval_spin.setEnabled(False)

    def _toggle_custom_colors(self, index: int) -> None:
        self.custom_color_widget.setVisible(index == 1)

    def _pick_color(self, line_edit: QLineEdit) -> None:
        color = QColorDialog.getColor()
        if color.isValid():
            line_edit.setText(color.name().upper())

    def get_config(self) -> dict[str, Any]:
        return {
            "mode": "typespeed" if self.reactive_combo.currentIndex() == 0 else "ping",
            "host": self.host_input.text().strip(),
            "min_val": self.min_spin.value(),
            "max_val": self.max_spin.value(),
            "is_custom_color": self.color_mode_combo.currentIndex() == 1,
            "min_color": self.hex_min_color.text().strip().upper(),
            "max_color": self.hex_max_color.text().strip().upper(),
            "interval": self.interval_spin.value(),
            "brightness": self.brightness.value()
        }

class ScreenSyncPage(ModePage):
    def __init__(self):
        super().__init__("Screen & Mouse Sync")

        grp = QGroupBox("Visual Capture Settings")
        grid = QGridLayout(grp)
        self.sync_combo = QComboBox()
        self.sync_combo.addItems([
            "Mouse Pointer Color (Under Cursor)",
            "Screen Dominant Color (Precise Mode)",
            "Screen Average Color (Smooth Blur)"
        ])
        self.sync_combo.currentIndexChanged.connect(self._on_method_changed)
        self.enhance_check = QCheckBox("Enable Color Enhancing (Boost Saturation)")
        self.enhance_check.setChecked(True)
        self.interval_spin = QDoubleSpinBox()
        self.interval_spin.setRange(0.01, 2.0)
        self.interval_spin.setValue(0.1)
        self.interval_spin.setSingleStep(0.05)
        self.interval_spin.setSuffix(" sec")
        self.brightness = self._make_brightness_spin()
        grid.addWidget(QLabel("Capture Method"), 0, 0)
        grid.addWidget(self.sync_combo, 0, 1)

        grid.addWidget(QLabel("Image Processing"), 1, 0)
        grid.addWidget(self.enhance_check, 1, 1)

        grid.addWidget(QLabel("Refresh Interval"), 2, 0)
        grid.addWidget(self.interval_spin, 2, 1)

        grid.addWidget(QLabel("Brightness"), 3, 0)
        grid.addWidget(self.brightness, 3, 1)

        self.add_group(grp)

    def _on_method_changed(self, index: int) -> None:
        """Adjust the default refresh interval for each capture method."""
        if index == 0: 
            self.interval_spin.setValue(0.05)
        elif index == 1: 
            self.interval_spin.setValue(0.3)
        else:             # Average Color
            self.interval_spin.setValue(0.1)

    def get_config(self) -> dict[str, Any]:
        method_map = {
            0: "mouse",
            1: "scrn_dom",
            2: "scrn_avg"
        }
        return {
            "method": method_map.get(self.sync_combo.currentIndex(), "scrn_avg"),
            "do_enhancing": self.enhance_check.isChecked(),
            "interval": self.interval_spin.value(),
            "brightness": self.brightness.value()
        }
class TimeFocusPage(ModePage):
    def __init__(self):
        super().__init__("Time & Focus Controls")

        grp = QGroupBox("Mode Configurations")
        grid = QGridLayout(grp)
        self.mode_combo = QComboBox()
        self.mode_combo.addItems([
            "Daylight Cycle (Sync with Clock)",
            "Focus Timer (Pomodoro Style)"
        ])
        self.mode_combo.currentIndexChanged.connect(self._on_submode_changed)
        self.timer_widget = QWidget()
        t_layout = QGridLayout(self.timer_widget)
        t_layout.setContentsMargins(0, 0, 0, 0)

        self.duration_spin = QSpinBox()
        self.duration_spin.setRange(1, 180)
        self.duration_spin.setValue(25)
        self.duration_spin.setSuffix(" minutes")

        self.gradual_check = QCheckBox("Gradual Color Transition (X ➔ Y)")
        self.gradual_check.setChecked(False)

        self.hex_x = self.create_hex_input("#00FF00")
        self.hex_y = self.create_hex_input("#FF0000") 
        self.btn_x = QPushButton("🎨 Start (X)")
        self.btn_y = QPushButton("🎨 End (Y)")
        
        self.btn_x.clicked.connect(lambda: self._pick_color(self.hex_x))
        self.btn_y.clicked.connect(lambda: self._pick_color(self.hex_y))
        self.break_check = QCheckBox("Enable Break Mode after Focus")
        self.break_check.setChecked(True)
        self.break_check.toggled.connect(self._toggle_break_section)
        self.break_widget = QWidget()
        b_layout = QHBoxLayout(self.break_widget)
        b_layout.setContentsMargins(0, 0, 0, 0)

        self.break_spin = QSpinBox()
        self.break_spin.setRange(1, 60)
        self.break_spin.setValue(5)
        self.break_spin.setSuffix(" min")

        self.hex_z = self.create_hex_input("#00BFFF")
        self.btn_z = QPushButton("🎨 Break (Z)")
        self.btn_z.clicked.connect(lambda: self._pick_color(self.hex_z))

        b_layout.addWidget(QLabel("Duration:"))
        b_layout.addWidget(self.break_spin)
        b_layout.addWidget(QLabel("Color Z:"))
        b_layout.addWidget(self.hex_z)
        b_layout.addWidget(self.btn_z)
        t_layout.addWidget(QLabel("Focus Duration:"), 0, 0)
        t_layout.addWidget(self.duration_spin, 0, 1, 1, 2)
        t_layout.addWidget(self.gradual_check, 1, 0, 1, 3)
        t_layout.addWidget(QLabel("Focus Colors:"), 2, 0)
        t_layout.addWidget(self.hex_x, 2, 1)
        t_layout.addWidget(self.btn_x, 2, 2)
        t_layout.addWidget(self.hex_y, 3, 1)
        t_layout.addWidget(self.btn_y, 3, 2)
        
        t_layout.addWidget(self.break_check, 4, 0, 1, 3)
        t_layout.addWidget(self.break_widget, 5, 0, 1, 3)

        self.timer_widget.setVisible(False)
        self.brightness = self._make_brightness_spin()
        grid.addWidget(QLabel("Select Function"), 0, 0)
        grid.addWidget(self.mode_combo, 0, 1)
        grid.addWidget(self.timer_widget, 1, 0, 1, 2)
        grid.addWidget(QLabel("Brightness"), 2, 0)
        grid.addWidget(self.brightness, 2, 1)

        self.add_group(grp)

    def _on_submode_changed(self, index: int) -> None:
        self.timer_widget.setVisible(index == 1)

    def _toggle_break_section(self, checked: bool) -> None:
        self.break_widget.setVisible(checked)

    def _pick_color(self, line_edit: QLineEdit) -> None:
        color = QColorDialog.getColor()
        if color.isValid():
            line_edit.setText(color.name().upper())

    def get_config(self) -> dict[str, Any]:
        return {
            "sub_mode": "daylight" if self.mode_combo.currentIndex() == 0 else "timer",
            "timer_duration": self.duration_spin.value(),
            "timer_gradual": self.gradual_check.isChecked(),
            "color_x": self.hex_x.text().strip().upper(),
            "color_y": self.hex_y.text().strip().upper(),
            "has_break": self.break_check.isChecked(),
            "break_duration": self.break_spin.value(),
            "color_z": self.hex_z.text().strip().upper(),
            "interval": 1.0,
            "brightness": self.brightness.value()
        }

class SpotifyPage(ModePage):
    def __init__(self):
        super().__init__("Spotify Sync Controls")

        grp = QGroupBox("Spotify Audio Link")
        grid = QGridLayout(grp)
        self.palette_combo = QComboBox()
        self.palette_combo.addItems(["stdcol3", "stdcol6", "stdcol12", "stdcol24"])
        self.palette_combo.setCurrentText("stdcol6")
        self.vol_check = QCheckBox("Link Brightness to System/Spotify Volume")
        self.vol_check.setChecked(True)
        self.setup_btn = QPushButton("⚙️ Setup Spotify API Keys")
        self.setup_btn.clicked.connect(self._open_settings)
        self.brightness = self._make_brightness_spin()
        grid.addWidget(QLabel("Color Palette"), 0, 0)
        grid.addWidget(self.palette_combo, 0, 1)
        grid.addWidget(self.vol_check, 1, 0, 1, 2)
        grid.addWidget(QLabel("API Authentication"), 2, 0)
        grid.addWidget(self.setup_btn, 2, 1)
        grid.addWidget(QLabel("Max Brightness"), 3, 0)
        grid.addWidget(self.brightness, 3, 1)

        self.add_group(grp)

    def _open_settings(self):
        dialog = SpotifyConfigDialog(self)
        dialog.exec()

    def get_config(self) -> dict[str, Any]:
        return {
            "palette": self.palette_combo.currentText(),
            "no_vol": not self.vol_check.isChecked(),
            "brightness": self.brightness.value()
        }


# 4. Main Application Window

class LogWindow(QDialog):
    """Popup window for live console output."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Live Console Logs")
        self.resize(550, 350)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)

        self.log_viewer = QTextEdit()
        self.log_viewer.setReadOnly(True)
        self.log_viewer.setStyleSheet("""
            QTextEdit {
                background-color: #111114;
                border: 1px solid #2a2a33;
                border-radius: 6px;
                color: #a6a6b3;
                font-family: 'Consolas', 'Courier New', monospace;
                font-size: 11px;
            }
        """)
        layout.addWidget(self.log_viewer)

    def append_text(self, text: str):
        """Append new text and keep the view scrolled to the bottom."""
        self.log_viewer.insertPlainText(text)
        self.log_viewer.moveCursor(QTextCursor.MoveOperation.End)

class TextStream(QObject):
    text_written = Signal(str)

    def write(self, text):
        if text:
            self.text_written.emit(str(text))

    def flush(self):
        pass

class MainWindow(QMainWindow):
    def __init__(self, shared_memory=None):
        super().__init__()
        self.setWindowTitle("TUF RGB Controller")
        icon_path = get_resource_path("app_icon.ico")
        self.setWindowIcon(QIcon(icon_path))
        self.resize(720, 560)
        self.setMinimumSize(720, 560)
        self.shared_memory = shared_memory
        self.error_queue = multiprocessing.Queue()
        self.backend = BackendAdapter(self.error_queue)
        self.current_process: Optional[multiprocessing.Process] = None
        self.monitor_timer = QTimer(self)
        self.monitor_timer.timeout.connect(self.check_process_state)
        self.monitor_timer.start(500)
        self.error_timer = QTimer(self)
        self.error_timer.timeout.connect(self.check_backend_errors)

        self.log_window = LogWindow(self)
        sys.stdout = TextStream(text_written=self._handle_incoming_log)

        self.child_log_queue = multiprocessing.Queue()
        self.log_timer = QTimer(self)
        self.log_timer.timeout.connect(self._read_child_logs)
        self.log_timer.start(100)

        self._build_ui()
        self._build_tray()
        self._apply_style()
        self._set_status("Ready")

    def _handle_incoming_log(self, text: str):
            self.log_window.append_text(text)

    def _build_ui(self) -> None:
        root = QWidget()
        self.setCentralWidget(root)
        outer = QHBoxLayout(root)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(180)
        side_layout = QVBoxLayout(sidebar)
        side_layout.setContentsMargins(12, 12, 12, 12)
        side_layout.setSpacing(10)

        brand = QLabel("TUF RGB")
        brand.setObjectName("brand")
        subtitle = QLabel("Customize Your Keyboard,\nHowever You Want.")
        subtitle.setObjectName("subtitle")
        side_layout.addWidget(brand)
        side_layout.addWidget(subtitle)

        self.mode_list = QListWidget()
        self.mode_list.setObjectName("modeList")
        self.mode_list.setSpacing(4)
        self.mode_list.currentRowChanged.connect(self._on_mode_changed)
        side_layout.addWidget(self.mode_list, 1)
        side_layout.addWidget(self._build_quick_actions())
        content = QFrame()
        content.setObjectName("content")
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        
        self.pages = QStackedWidget()
        self.pages.setObjectName("pages")
        content_layout.addWidget(self.pages, 1)

        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)

        outer.addWidget(sidebar)
        outer.addWidget(content, 1)
        self.registered_modes = {
            "Off": {"type": "off", "page": OffPage()},
            "Static": {"type": "static", "page": StaticPage()},
            "Cycle": {"type": "cycle", "page": CyclePage()},
            "System Monitor": {"type": "sys_monitor", "page": SystemMonitorPage()},
            "Reactive Mode": {"type": "reactive", "page": ReactivePage()},
            "Screen Sync": {"type": "screen_sync", "page": ScreenSyncPage()},
            "Time & Focus": {"type": "time_focus", "page": TimeFocusPage()}, 
            "Spotify Sync": {"type": "spotify_sync", "page": SpotifyPage()}
        }

        for label, data in self.registered_modes.items():
            self.mode_list.addItem(QListWidgetItem(label))
            self.pages.addWidget(data["page"])

        self.mode_list.setCurrentRow(1)

    def _build_quick_actions(self) -> QWidget:
            box = QGroupBox("Quick Actions")
            layout = QVBoxLayout(box)
            layout.setSpacing(8)

            self.btn_start = QPushButton("Start Effect")
            self.btn_stop = QPushButton("Stop Effect")
            self.btn_stop.setEnabled(False)
            self.btn_logs = QPushButton("View Live Logs")
            
            self.btn_start.clicked.connect(self.start_selected_mode)
            self.btn_stop.clicked.connect(self.stop_running)
            self.btn_logs.clicked.connect(self._show_logs_popup)

            layout.addWidget(self.btn_start)
            layout.addWidget(self.btn_stop)
            layout.addWidget(self.btn_logs)
            return box

    def _on_mode_changed(self, index: int) -> None:
            self.pages.setCurrentIndex(index)

    def _show_logs_popup(self):
        """باز کردن پنجره پاپ‌آپ لاگ‌ها به صورت غیر مودال (Non-blocking)"""
        self.log_window.show()
        self.log_window.raise_()
        self.log_window.activateWindow()

    @Slot()
    def start_selected_mode(self) -> None:
        self.stop_running()
        
        current_item = self.mode_list.currentItem()
        if not current_item:
            return
            
        label = current_item.text()
        mode_data = self.registered_modes[label]
        
        config_data = mode_data["page"].get_config()
        request = RunRequest(mode=mode_data["type"], config=config_data)

        try:
            target_func, args = self.backend.get_target_and_args(request)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load module: {e}")
            return
        if mode_data["type"] == "spotify_sync":
            args = (config_data, self.error_queue)
        self.error_timer.stop()
        # Start the selected effect in a background process.
        self.current_process = multiprocessing.Process(
            target=process_wrapper, 
            args=(target_func, args, self.child_log_queue)
        )
        self.current_process.daemon = True
        self.current_process.start()
        if mode_data["type"] == "spotify_sync":
            print("⏳ UI Error Timer Started...")
            self.error_timer.start(500)

        self._set_busy(True)
        self._set_status(f"Active Mode: {label}")

    @Slot()
    def stop_running(self) -> None:
        self.error_timer.stop()
        
        if self.current_process and self.current_process.is_alive():
            self.current_process.terminate()
            self.current_process.join()
            
        self.current_process = None
        self._set_busy(False)
        self._set_status("Stopped")

    def check_process_state(self) -> None:
        if self.current_process is not None:
            if not self.current_process.is_alive():
                self.current_process = None
                self._set_busy(False)
                self._set_status("Finished / Ready")

    def _set_busy(self, busy: bool) -> None:
        self.btn_start.setEnabled(not busy)
        self.btn_stop.setEnabled(busy)

    def _set_status(self, text: str) -> None:
        self.status_bar.showMessage(text)

    # ---------- System Tray Handling ----------
    def _build_tray(self) -> None:
        icon_path = get_resource_path("app_icon.ico")
        tray_icon = QIcon(icon_path)
        if tray_icon.isNull():
            tray_icon = self.style().standardIcon(QStyle.StandardPixmap.SP_ComputerIcon)

        self.tray = QSystemTrayIcon(tray_icon, self)
        self.tray.setIcon(tray_icon)
        self.tray.setToolTip("TUF RGB")

        menu = QMenu()
        act_restore = QAction("Open UI", self)
        act_quit = QAction("Exit", self)

        act_restore.triggered.connect(self.show_normal)
        act_quit.triggered.connect(self.hard_exit)

        menu.addAction(act_restore)
        menu.addSeparator()
        menu.addAction(act_quit)

        self.tray.setContextMenu(menu)
        self.tray.activated.connect(self._tray_activated)

        if QSystemTrayIcon.isSystemTrayAvailable():
            self.tray.show()

    def _tray_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason in (QSystemTrayIcon.ActivationReason.Trigger, QSystemTrayIcon.ActivationReason.DoubleClick):
            self.show_normal()

    def _read_child_logs(self):
            """Read queued output from background modules and forward it to the UI."""
            if hasattr(self, 'child_log_queue'):
                while not self.child_log_queue.empty():
                    try:
                        text = self.child_log_queue.get_nowait()
                        self.log_window.append_text(text)
                    except:
                        break

    def show_normal(self) -> None:
        self.show()
        self.raise_()
        self.activateWindow()

    def hard_exit(self) -> None:
        self.stop_running()
        if self.shared_memory:
            self.shared_memory.detach()
        if hasattr(self, "tray") and self.tray.isVisible():
            self.tray.hide()
        QApplication.instance().quit()

    def closeEvent(self, event: QCloseEvent) -> None:
        if QSystemTrayIcon.isSystemTrayAvailable() and hasattr(self, "tray"):
            event.ignore()
            self.hide()
            self._set_status("Hidden to tray. Use tray icon to restore or exit.")
        else:
            self.stop_running()
            event.accept()

    def check_backend_errors(self):
        if hasattr(self, 'error_queue'):
            try:
                error_msg = self.error_queue.get_nowait()
                if error_msg == "PREMIUM_REQUIRED":
                    self.error_timer.stop()
                    self.stop_running()
                    #self.show_premium_warning_popup()
            except:
                pass

    # ---------- UI/UX Styling ----------
    def _apply_style(self) -> None:
        app = QApplication.instance()
        palette = QPalette()
        palette.setColor(QPalette.ColorRole.Window, QColor(24, 24, 28))
        palette.setColor(QPalette.ColorRole.WindowText, QColor(235, 235, 235))
        palette.setColor(QPalette.ColorRole.Base, QColor(17, 17, 20))
        palette.setColor(QPalette.ColorRole.Text, QColor(235, 235, 235))
        palette.setColor(QPalette.ColorRole.Button, QColor(40, 40, 48))
        palette.setColor(QPalette.ColorRole.ButtonText, QColor(245, 245, 245))
        palette.setColor(QPalette.ColorRole.Highlight, QColor(80, 120, 255))
        app.setPalette(palette)

        self.setStyleSheet("""
            QMainWindow { background: #18181c; }
            QFrame#sidebar { background: #121216; border-right: 1px solid #2a2a33; }
            QLabel#brand { font-size: 22px; font-weight: bold; color: #00e676; }
            QLabel#subtitle { color: #8a8a9d; font-size: 11px; margin-bottom: 8px; }
            QLabel#pageTitle { font-size: 20px; font-weight: bold; color: #ffffff; }
            QListWidget#modeList { background: transparent; border: none; outline: 0; }
            QListWidget#modeList::item { padding: 6px; border-radius: 6px; color: #cfcfda; }
            QListWidget#modeList::item:selected { background: #232834; color: #00e676; font-weight: bold; }
            QGroupBox { border: 1px solid #2a2a33; border-radius: 10px; margin-top: 12px; padding-top: 16px; font-weight: bold; }
            QGroupBox::title { subcontrol-origin: margin; subcontrol-position: top left; padding: 0 5px; color: #a6a6b3; }
            QPushButton { background: #232834; border: 1px solid #313849; padding: 8px; border-radius: 6px; color: white; }
            QPushButton:hover { background: #2d3444; border-color: #00e676; }
            QPushButton:disabled { color: #5a5a66; background: #1c1c22; border-color: #222226; }
            QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox { background: #111114; border: 1px solid #2a2a33; border-radius: 6px; color: #f2f2f2; padding-left: 5px; padding-right: 20px; }
            QLineEdit:disabled { background: #1a1a1f; border: 1px solid #222226; color: #666666; }
            QLineEdit:focus, QComboBox:focus { border: 1px solid #00e676; }
        """)

def main() -> None:
    app = QApplication(sys.argv)
    app.setApplicationName("TUF RGB Engine")
    app.setQuitOnLastWindowClosed(False)

    window = MainWindow()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    multiprocessing.freeze_support()
    
    app = QApplication(sys.argv)
    
    instance_id = "TUF_RGB_Controller_Unique_Instance_ID_14298"
    
    from PySide6.QtCore import QSharedMemory
    
    shared_memory = QSharedMemory(instance_id)
    
    if shared_memory.attach():
        msg = QMessageBox()
        msg.setIcon(QMessageBox.Icon.Information)
        msg.setWindowIcon(QIcon(get_resource_path("app_icon.ico")))
        msg.setWindowTitle("Application Already Running")
        msg.setText("TUF RGB Controller is already running in the background.\nCheck your system tray!")
        msg.exec()
        sys.exit(0)
    else:
        shared_memory.create(1)

    window = MainWindow(shared_memory=shared_memory)
    window.show()

    sys.exit(app.exec())