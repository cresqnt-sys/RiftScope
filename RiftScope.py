import os
import time
import json
import threading
import requests
import psutil
import sys  
import subprocess
import packaging.version
import pynput 
import pyautogui 
from pynput import keyboard as pynput_keyboard 
from pynput import mouse as pynput_mouse       
import re 
try:
    import autoit 
    AUTOIT_AVAILABLE = True
except ImportError:
    AUTOIT_AVAILABLE = False
    print("WARNING: pyautoit module not found or AutoIt installation missing. Teleport click will likely fail.")
    print("Install AutoIt from https://www.autoitscript.com/site/autoit/downloads/ and run 'pip install pyautoit'")
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                           QHBoxLayout, QLabel, QLineEdit, QPushButton, 
                           QFrame, QMessageBox, QStyleFactory, QTabWidget, 
                           QTextEdit, QComboBox, QGridLayout, QCheckBox) 
from PyQt6.QtGui import QPalette, QColor, QFont, QKeySequence, QShortcut, QIcon, QPainter, QPen, QBrush 
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QRect, QPoint, QTimer 
from datetime import datetime

dark_palette = QPalette()
dark_palette.setColor(QPalette.ColorRole.Window, QColor(43, 43, 43))
dark_palette.setColor(QPalette.ColorRole.WindowText, QColor(224, 224, 224))
dark_palette.setColor(QPalette.ColorRole.Base, QColor(60, 60, 60))
dark_palette.setColor(QPalette.ColorRole.AlternateBase, QColor(53, 53, 53))
dark_palette.setColor(QPalette.ColorRole.ToolTipBase, Qt.GlobalColor.white)
dark_palette.setColor(QPalette.ColorRole.ToolTipText, Qt.GlobalColor.white)
dark_palette.setColor(QPalette.ColorRole.Text, QColor(224, 224, 224))
dark_palette.setColor(QPalette.ColorRole.Button, QColor(68, 68, 68))
dark_palette.setColor(QPalette.ColorRole.ButtonText, QColor(224, 224, 224))
dark_palette.setColor(QPalette.ColorRole.BrightText, Qt.GlobalColor.red)
dark_palette.setColor(QPalette.ColorRole.Link, QColor(114, 137, 218)) 
dark_palette.setColor(QPalette.ColorRole.Highlight, QColor(114, 137, 218))
dark_palette.setColor(QPalette.ColorRole.HighlightedText, Qt.GlobalColor.black)

dark_palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Button, QColor(45, 45, 45))
dark_palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.ButtonText, QColor(112, 112, 112))
dark_palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Text, QColor(112, 112, 112))
dark_palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.WindowText, QColor(112, 112, 112))

button_stylesheet = """
QPushButton {{
    background-color: {bg_color};
    color: {fg_color};
    border: none;
    padding: 8px 16px;
    font-size: 10pt;
    font-weight: bold;
    border-radius: 4px;
}}
QPushButton:hover {{
    background-color: {hover_bg_color};
}}
QPushButton:pressed {{
    background-color: {pressed_bg_color};
}}
QPushButton:disabled {{
    background-color: 
    color: 
}}
"""

class Worker(QThread):
    update_status_signal = pyqtSignal(str)
    finished_signal = pyqtSignal()
    webhook_signal = pyqtSignal(str, str, str, int, str)

    def __init__(self, func, *args, **kwargs):
        super().__init__()
        self._func = func
        self._args = args
        self._kwargs = kwargs

    def run(self):
        try:
            self._func(*self._args, **self._kwargs)
        except Exception as e:
            self.update_status_signal.emit(f"Error in worker thread: {e}")
            print(f"Error in worker thread: {e}") 
        finally:
            self.finished_signal.emit()

class CalibrationOverlay(QWidget):
    point_selected = pyqtSignal(QPoint) 

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.SplashScreen)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setWindowState(Qt.WindowState.WindowFullScreen)

    def paintEvent(self, event):
        painter = QPainter(self)

        painter.fillRect(self.rect(), QColor(40, 40, 40, 180))

        painter.setPen(QColor(220, 220, 220))
        font = QFont("Segoe UI", 16)
        font.setBold(True)
        painter.setFont(font)
        painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter,
                         "Click on the exact location of the Teleport Button.\nPress ESC to cancel.")

    def mousePressEvent(self, event):

        if event.button() == Qt.MouseButton.LeftButton:
            self.point_selected.emit(event.pos())
            self.close() 

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            print("Calibration cancelled by user.")
            self.close()

class RiftScopeApp(QMainWindow):
    APP_VERSION = "1.2.0-Stable"
    REPO_URL = "cresqnt-sys/RiftScope"
    EVENT_COOLDOWN_SECONDS = 10 

    update_prompt_signal = pyqtSignal(str, str)

    start_hotkey_signal = pyqtSignal()
    stop_hotkey_signal = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"RiftScope v{self.APP_VERSION}")
        self.setGeometry(100, 100, 500, 350) 

        icon_path = "icon.ico"
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
        else:
            print(f"Warning: Icon file not found at '{icon_path}'")

        self.setPalette(dark_palette) 
        QApplication.setStyle(QStyleFactory.create("Fusion")) 

        self.running = False
        self.last_line_time = time.time()
        self.current_log = None
        self.monitor_thread = None 
        self.last_timestamp = None
        self.processed_lines = set()
        self.lock_log_file = False
        self.test_running = False
        self.test_worker = None 

        self.collection_enabled = False
        self.teleport_coords = None 
        self.collection_worker = None
        self.collection_running = False
        self.calibration_overlay = None
        self.calibrating = False

        self.hatch_username = ""
        self.hatch_secret_ping_enabled = False
        self.hatch_secret_ping_user_id = ""

        self.last_royal_chest_time = 0
        self.last_gum_rift_time = 0
        self.last_aura_egg_time = 0
        self.last_hatch_ping_time = 0 

        self.royal_image_url = "https://ps99.biggamesapi.io/image/76803303814891"
        self.aura_image_url = "https://ps99.biggamesapi.io/image/95563056090518"

        app_data_dir = os.getenv('APPDATA')
        if app_data_dir:
            config_dir = os.path.join(app_data_dir, "RiftScope")
            self.config_file = os.path.join(config_dir, "config.json")
        else:
            print("Warning: APPDATA environment variable not found. Saving config locally.")
            config_dir = os.path.dirname(os.path.abspath(__file__)) 
            self.config_file = os.path.join(config_dir, "config.json")

        self.load_config() 
        if not self.tutorial_shown:

            msg_box = QMessageBox(self) 
            msg_box.setIcon(QMessageBox.Icon.Warning)
            msg_box.setWindowTitle("First Time Setup Notice")

            msg_box.setText(
                "Important: For RiftScope to correctly configure Roblox logging \n"
                "on first launch, **Roblox must be closed before starting RiftScope.**\n\n"
                "If Roblox is currently open, please:\n"
                "1. Wait 10 seconds, then click OK on this message.\n" 
                "2. Close RiftScope.\n"
                "3. Close Roblox.\n"
                "4. Relaunch RiftScope (before starting Roblox).\n\n"
                "This initial setup ensures detection works correctly with any Roblox launcher \n"
                "(Fishstrap, Bloxstrap, or standard Roblox).\n"
                "You only need to do this once. If you are using STOCK Roblox you must do this every update."
            )
            ok_button = msg_box.addButton(QMessageBox.StandardButton.Ok)
            ok_button.setEnabled(False) 

            timer = QTimer(self)
            timer.setSingleShot(True)
            timer.timeout.connect(lambda: ok_button.setEnabled(True))

            self.update_status("Please read the first-time setup notice. OK button enabled in 10 seconds...")
            timer.start(10000) 

            clicked_button = msg_box.exec()

            if clicked_button == QMessageBox.StandardButton.Ok:
                self.tutorial_shown = True
                self.save_config()
                self.update_status("First-time setup notice acknowledged and saved.")
            else:

                self.update_status("First-time setup notice dismissed without acknowledging.")

        self.hotkey_listener = None

        self.build_ui()
        self.apply_roblox_fastflags()

        self.start_hotkey_signal.connect(self.start_macro)
        self.stop_hotkey_signal.connect(self.stop_macro)

        listener_thread = threading.Thread(target=self._start_pynput_listener, daemon=True)
        listener_thread.start()

        self.update_prompt_signal.connect(self.prompt_update)
        self.update_checker_worker = Worker(self.check_for_updates)
        self.update_checker_worker.start()

        self.SECRET_PETS = {
            "Giant Chocolate Chicken", "Easter Basket", "MAN FACE GOD", "King Doggy",
            "The Overlord", "Avernus", "Dementor", "Godly Gem"
        }
        self.LEGENDARY_PETS = {
            "NULLVoid", "Cardinal Bunny", "Rainbow Marshmellow", "Rainbow Shock",
            "Ethereal Bunny", "Hexarium", "Seraph", "Sweet Treat", "Abyssal Dragon",
            "Beta TV", "Crescent Empress", "Dark Phoenix", "Dark Serpent", "Demonic Dogcat",
            "Demonic Hydra", "Discord Imp", "Dowodle", "Dualcorn", "Easter Fluffle",
            "Easter Serpent", "Electra", "Emerald Golem", "Evil Shock", "Flying Gem",
            "Flying Pig", "Green Hydra", "Hacker Prism", "Holy Egg", "Holy Shock",
            "Inferno Cube", "Inferno Dragon", "Infernus", "King Soul", "Kitsune",
            "Lunar Deity", "Lunar Serpent", "Manarium", "Midas", "Moonburst",
            "Neon Elemental", "Ophanim", "Patronus", "Rainbow Blitz", "Seraphic Bunny",
            "Sigma Serpent", "Solar Deity", "Sunburst", "Trio Cube", "Umbra",
            "Unicorn", "Virus"
        }

    def build_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(15)

        title_label = QLabel(f"🏝️ RiftScope v{self.APP_VERSION}")
        title_font = QFont("Segoe UI", 16)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_label.setStyleSheet("color: #7289da;") 
        main_layout.addWidget(title_label)

        self.tab_widget = QTabWidget()
        main_layout.addWidget(self.tab_widget)

        self.scanner_tab = QWidget()
        scanner_layout = QVBoxLayout(self.scanner_tab)
        scanner_layout.setContentsMargins(10, 15, 10, 10) 
        scanner_layout.setSpacing(10)
        self.tab_widget.addTab(self.scanner_tab, "Scanner")

        input_frame = QFrame()
        input_layout = QVBoxLayout(input_frame)
        input_layout.setContentsMargins(0, 0, 0, 0)
        input_layout.setSpacing(5)

        self.launcher_label = QLabel("Roblox Launcher:")
        input_layout.addWidget(self.launcher_label)

        launcher_frame = QFrame()
        launcher_layout = QHBoxLayout(launcher_frame)
        launcher_layout.setContentsMargins(0, 0, 0, 0)
        launcher_layout.setSpacing(5)

        self.launcher_combo = QComboBox()
        self.launcher_combo.addItem("Auto (Detect)")
        self.launcher_combo.addItem("Fishstrap")
        self.launcher_combo.addItem("Bloxstrap")
        self.launcher_combo.addItem("Roblox")

        if hasattr(self, 'launcher_choice'):
            index = self.launcher_combo.findText(self.launcher_choice)
            if index >= 0:
                self.launcher_combo.setCurrentIndex(index)
            elif self.launcher_choice == "Auto":
                self.launcher_combo.setCurrentIndex(0)

        launcher_layout.addWidget(self.launcher_combo)

        self.launcher_status = QLabel("")
        self.launcher_status.setStyleSheet("color: #43b581;")
        launcher_layout.addWidget(self.launcher_status)

        input_layout.addWidget(launcher_frame)

        self.webhook_label = QLabel("Discord Webhook URL:")
        input_layout.addWidget(self.webhook_label)
        self.webhook_entry = QLineEdit()
        self.webhook_entry.setPlaceholderText("Enter your Discord webhook URL here")
        if hasattr(self, 'webhook_url') and self.webhook_url:
            self.webhook_entry.setText(self.webhook_url)
        input_layout.addWidget(self.webhook_entry)

        self.pslink_label = QLabel("Private Server Link (Optional):")
        input_layout.addWidget(self.pslink_label)
        self.pslink_entry = QLineEdit()
        self.pslink_entry.setPlaceholderText("Enter the private server link for notifications")
        if hasattr(self, 'ps_link') and self.ps_link:
            self.pslink_entry.setText(self.ps_link)
        input_layout.addWidget(self.pslink_entry)

        scanner_layout.addWidget(input_frame)

        button_frame = QFrame()
        button_layout = QHBoxLayout(button_frame)
        button_layout.setContentsMargins(0, 10, 0, 5)
        button_layout.setSpacing(10)

        self.start_button = QPushButton("Start Scanning (F1)")
        self.start_button.setStyleSheet(button_stylesheet.format(
            bg_color="#7289da", fg_color="white", hover_bg_color="#677bc4", pressed_bg_color="#5b6eae"
        ))
        self.start_button.clicked.connect(self.start_macro)
        button_layout.addWidget(self.start_button)

        self.stop_button = QPushButton("Stop Scanning (F2)")
        self.stop_button.setStyleSheet(button_stylesheet.format(
            bg_color="#f04747", fg_color="white", hover_bg_color="#d84141", pressed_bg_color="#c03939"
        ))
        self.stop_button.clicked.connect(self.stop_macro)
        self.stop_button.setEnabled(False)
        button_layout.addWidget(self.stop_button)

        scanner_layout.addWidget(button_frame)

        secondary_button_frame = QFrame()
        secondary_button_layout = QHBoxLayout(secondary_button_frame)
        secondary_button_layout.setContentsMargins(0, 0, 0, 0)
        secondary_button_layout.setSpacing(10)

        self.test_button = QPushButton("Test Scanner")
        self.test_button.setStyleSheet(button_stylesheet.format(
            bg_color="#43b581", fg_color="white", hover_bg_color="#3ca374", pressed_bg_color="#359066"
        ))
        self.test_button.clicked.connect(self.run_test_scan)
        secondary_button_layout.addWidget(self.test_button)

        self.lock_button = QPushButton("Lock Log File: OFF")
        self.lock_button.setStyleSheet(button_stylesheet.format(
            bg_color="#faa61a", fg_color="white", hover_bg_color="#e09517", pressed_bg_color="#c78414"
        ))
        self.lock_button.setCheckable(True)
        self.lock_button.toggled.connect(self.toggle_lock_log)
        secondary_button_layout.addWidget(self.lock_button)

        scanner_layout.addWidget(secondary_button_frame)

        scanner_layout.addStretch() 

        credits_tab_widget = QWidget()
        credits_layout = QVBoxLayout(credits_tab_widget)
        credits_layout.setContentsMargins(15, 20, 15, 15)
        credits_layout.setSpacing(10)

        credits_title_label = QLabel("Credits")
        credits_title_font = QFont("Segoe UI", 12)
        credits_title_font.setBold(True)
        credits_title_label.setFont(credits_title_font)
        credits_title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        credits_layout.addWidget(credits_title_label)

        cresqnt_label = QLabel("<b>cresqnt:</b> Macro Maintainer")
        cresqnt_label.setTextFormat(Qt.TextFormat.RichText)
        cresqnt_label.setWordWrap(True)
        credits_layout.addWidget(cresqnt_label)

        digital_label = QLabel("<b>Digital:</b> Creator of detection, pathing, and some of UI. ")
        digital_label.setTextFormat(Qt.TextFormat.RichText) 
        digital_label.setWordWrap(True)
        credits_layout.addWidget(digital_label)

        credits_layout.addStretch() 

        self.pings_tab = QWidget()
        pings_layout = QVBoxLayout(self.pings_tab)
        pings_layout.setContentsMargins(10, 10, 10, 10)
        self.tab_widget.addTab(self.pings_tab, "Pings")

        pings_title_label = QLabel("Pings")
        pings_title_font = QFont("Segoe UI", 12)
        pings_title_font.setBold(True)
        pings_title_label.setFont(pings_title_font)
        pings_title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        pings_layout.addWidget(pings_title_label)

        pings_grid_layout = QGridLayout()
        pings_grid_layout.setContentsMargins(10, 10, 10, 10) 
        pings_grid_layout.setSpacing(10) 

        self.royal_chest_ping_label = QLabel("Royal Chest Ping:")
        self.royal_chest_ping_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        pings_grid_layout.addWidget(self.royal_chest_ping_label, 0, 0)

        self.royal_chest_ping_entry = QLineEdit()
        self.royal_chest_ping_entry.setPlaceholderText("Enter User/Role ID (Optional)")
        if hasattr(self, 'royal_chest_ping_id') and self.royal_chest_ping_id:
            self.royal_chest_ping_entry.setText(self.royal_chest_ping_id)
        pings_grid_layout.addWidget(self.royal_chest_ping_entry, 0, 1)

        self.royal_chest_ping_type_combo = QComboBox()
        self.royal_chest_ping_type_combo.addItem("User")
        self.royal_chest_ping_type_combo.addItem("Role")
        self.royal_chest_ping_type_combo.setFixedWidth(60) 
        if hasattr(self, 'royal_chest_ping_type'):
            index = self.royal_chest_ping_type_combo.findText(self.royal_chest_ping_type)
            if index >= 0:
                self.royal_chest_ping_type_combo.setCurrentIndex(index)
        pings_grid_layout.addWidget(self.royal_chest_ping_type_combo, 0, 2)

        self.gum_rift_ping_label = QLabel("Gum Rift Ping:")
        self.gum_rift_ping_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        pings_grid_layout.addWidget(self.gum_rift_ping_label, 1, 0)

        self.gum_rift_ping_entry = QLineEdit()
        self.gum_rift_ping_entry.setPlaceholderText("Enter User/Role ID (Optional)")
        if hasattr(self, 'gum_rift_ping_id') and self.gum_rift_ping_id:
            self.gum_rift_ping_entry.setText(self.gum_rift_ping_id)
        pings_grid_layout.addWidget(self.gum_rift_ping_entry, 1, 1)

        self.gum_rift_ping_type_combo = QComboBox()
        self.gum_rift_ping_type_combo.addItem("User")
        self.gum_rift_ping_type_combo.addItem("Role")
        self.gum_rift_ping_type_combo.setFixedWidth(60) 
        if hasattr(self, 'gum_rift_ping_type'):
            index = self.gum_rift_ping_type_combo.findText(self.gum_rift_ping_type)
            if index >= 0:
                self.gum_rift_ping_type_combo.setCurrentIndex(index)
        pings_grid_layout.addWidget(self.gum_rift_ping_type_combo, 1, 2)

        self.aura_egg_ping_label = QLabel("Aura Egg Ping:")
        self.aura_egg_ping_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        pings_grid_layout.addWidget(self.aura_egg_ping_label, 2, 0)

        self.aura_egg_ping_display = QLabel("<code>@everyone</code> (Cannot be changed)")
        self.aura_egg_ping_display.setTextFormat(Qt.TextFormat.RichText)
        pings_grid_layout.addWidget(self.aura_egg_ping_display, 2, 1, 1, 2) 

        pings_grid_layout.setColumnStretch(1, 1) 

        pings_layout.addLayout(pings_grid_layout) 
        pings_layout.addStretch()

        self.collection_tab = QWidget()
        collection_layout = QVBoxLayout(self.collection_tab)
        collection_layout.setContentsMargins(15, 20, 15, 15)
        collection_layout.setSpacing(10)
        pings_tab_index = self.tab_widget.indexOf(self.pings_tab)
        self.tab_widget.insertTab(pings_tab_index + 1, self.collection_tab, "Collection")

        collection_title_label = QLabel("Collection Path")
        collection_title_font = QFont("Segoe UI", 12)
        collection_title_font.setBold(True)
        collection_title_label.setFont(collection_title_font)
        collection_title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        collection_layout.addWidget(collection_title_label)

        self.collection_enabled_checkbox = QCheckBox("Enable Collection Path")
        self.collection_enabled_checkbox.setChecked(self.collection_enabled) 
        collection_layout.addWidget(self.collection_enabled_checkbox)

        self.calibrate_button = QPushButton() 
        self._update_calibrate_button_text() 
        self.calibrate_button.setStyleSheet(button_stylesheet.format(
             bg_color="#43b581", fg_color="white", hover_bg_color="#3ca374", pressed_bg_color="#359066"
        ))
        self.calibrate_button.clicked.connect(self.start_calibration) 
        collection_layout.addWidget(self.calibrate_button)

        self.calibrate_coords_label = QLabel("")
        self.calibrate_coords_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.calibrate_coords_label.setStyleSheet("font-size: 8pt; color: #aaa;")
        collection_layout.addWidget(self.calibrate_coords_label)
        self._update_calibrate_button_text() 

        collection_tutorial_label = QLabel(
            'Collection Tutorial: <a href="https://www.youtube.com/watch?v=YOQQR3n8VE4">Watch Video</a>'
        )
        collection_tutorial_label.setTextFormat(Qt.TextFormat.RichText)
        collection_tutorial_label.setOpenExternalLinks(True)
        collection_tutorial_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        collection_layout.addWidget(collection_tutorial_label)

        collection_layout.addStretch()

        self.hatch_tab = QWidget()
        hatch_layout = QVBoxLayout(self.hatch_tab)
        hatch_layout.setContentsMargins(15, 20, 15, 15)
        hatch_layout.setSpacing(10)
        collection_tab_index = self.tab_widget.indexOf(self.collection_tab) 
        self.tab_widget.insertTab(collection_tab_index + 1, self.hatch_tab, "Hatch") 

        hatch_title_label = QLabel("Hatch Settings")
        hatch_title_font = QFont("Segoe UI", 12)
        hatch_title_font.setBold(True)
        hatch_title_label.setFont(hatch_title_font)
        hatch_title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hatch_layout.addWidget(hatch_title_label)

        self.hatch_detection_enabled_checkbox = QCheckBox("Enable Hatch Detection")
        if hasattr(self, 'hatch_detection_enabled'): 
            self.hatch_detection_enabled_checkbox.setChecked(self.hatch_detection_enabled)
        else:
            self.hatch_detection_enabled_checkbox.setChecked(True) 
        hatch_layout.addWidget(self.hatch_detection_enabled_checkbox)

        self.hatch_username_label = QLabel("Username (for Secret Ping):") 
        hatch_layout.addWidget(self.hatch_username_label)
        self.hatch_username_entry = QLineEdit()
        self.hatch_username_entry.setPlaceholderText("Enter the username for hatching")
        if hasattr(self, 'hatch_username'):
            self.hatch_username_entry.setText(self.hatch_username)
        hatch_layout.addWidget(self.hatch_username_entry)

        self.hatch_secret_ping_checkbox = QCheckBox("Secret Pets Ping")
        if hasattr(self, 'hatch_secret_ping_enabled'):
            self.hatch_secret_ping_checkbox.setChecked(self.hatch_secret_ping_enabled)
        hatch_layout.addWidget(self.hatch_secret_ping_checkbox)

        self.hatch_userid_label = QLabel("User ID to Ping:")
        hatch_layout.addWidget(self.hatch_userid_label)
        self.hatch_userid_entry = QLineEdit()
        self.hatch_userid_entry.setPlaceholderText("Enter User ID to ping for secret pets")
        if hasattr(self, 'hatch_secret_ping_user_id'):
            self.hatch_userid_entry.setText(self.hatch_secret_ping_user_id)
        hatch_layout.addWidget(self.hatch_userid_entry)

        hatch_layout.addStretch()

        self.logs_tab = QWidget()
        logs_layout = QVBoxLayout(self.logs_tab)
        logs_layout.setContentsMargins(10, 10, 10, 10)
        self.tab_widget.addTab(self.logs_tab, "Logs")

        self.log_console = QTextEdit()
        self.log_console.setReadOnly(True)
        log_font = QFont("Consolas", 9) 
        if log_font.family() == "Consolas": 
             self.log_console.setFont(log_font)
        logs_layout.addWidget(self.log_console)

        self.credits_tab = credits_tab_widget 
        self.tab_widget.addTab(self.credits_tab, "Credits")

    def run_test_scan(self):
        if self.test_running:
            return

        self.save_config() 

        webhook_url = self.webhook_entry.text().strip() 
        if not webhook_url:
            self.update_status("Please enter a webhook URL before testing")

            return

        self.test_running = True
        self.test_button.setEnabled(False) 
        self.update_status("🔍 Running test scan... please wait")

        self.send_webhook(
            "⌛️ Testing Scanner",
            "The scanner is now checking for test emoji...",
            None,
            0xfaa61a  
        )

        self.test_worker = Worker(self.perform_test_scan)
        self.test_worker.update_status_signal.connect(self.update_status)

        self.test_worker.finished_signal.connect(self.on_test_finished)
        self.test_worker.start()

    def on_test_finished(self):
        self.test_button.setEnabled(True)
        self.test_running = False

    def perform_test_scan(self):

        try:
            latest_log = self.get_latest_log_file()
            if not latest_log:

                if self.test_worker:
                    self.test_worker.update_status_signal.emit("No log file found. Make sure Roblox is running.")

                self.send_webhook(
                    "❌ Macro is not detecting correctly (nothing detected)",
                    "Please check fishstrap to see if you left the settings off or check if you left the wrong settings on in the scanner.",
                    None,
                    0xe74c3c,
                    worker_instance=self.test_worker 
                )
                return 

            if self.test_worker:
                self.test_worker.update_status_signal.emit(f"Testing with log file: {os.path.basename(latest_log)}")

            found = False
            start_time = time.time()
            while not found and time.time() - start_time < 20: 

                if not self.test_running: 
                     if self.test_worker:
                        self.test_worker.update_status_signal.emit("Test scan cancelled.")
                     return

                lines = self.read_last_n_lines(latest_log, n=50)

                for line in lines:
                    if "🌎" in line and "font" in line:
                        if self.test_worker:
                            self.test_worker.update_status_signal.emit("✅ Scanner is working.")
                        self.send_webhook(
                            "✅ Macro Working!",
                            "Macro is ready to find rifts when you start scanning...",
                            None,
                            0x2ecc71,
                            worker_instance=self.test_worker 
                        )
                        found = True
                        break

                if not found:
                    time.sleep(0.5) 

            if not found:
                 if self.test_worker:
                     self.test_worker.update_status_signal.emit("❌ Test failed. Incorrect game or faulty macro.")
                 self.send_webhook(
                    "❌ Macro is not detecting correctly (nothing detected)",
                    "Please check fishstrap to see if you left the settings off or check if you left the wrong settings on in the scanner.",
                    None,
                    0xe74c3c,
                    worker_instance=self.test_worker 
                )

        except Exception as e:
            error_msg = f"Test error: {e}"
            if self.test_worker:
                self.test_worker.update_status_signal.emit(error_msg)
            self.send_webhook(
                "❌ Macro is not detecting correctly (error)",
                f"Error during test: {str(e)}",
                None,
                0xe74c3c,
                worker_instance=self.test_worker 
            )

    def toggle_lock_log(self, checked): 
        self.lock_log_file = checked
        status_text = "Lock Log File: ON" if checked else "Lock Log File: OFF"
        self.lock_button.setText(status_text) 
        self.update_status(f"Log file locking {'enabled' if self.lock_log_file else 'disabled'}.")

    def update_status(self, message):
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        formatted_log_message = f"[{timestamp}] {message}"

        if hasattr(self, 'log_console'):
            self.log_console.append(formatted_log_message)
            self.log_console.ensureCursorVisible() 

        print(formatted_log_message) 

    def apply_roblox_fastflags(self):
        """Finds Roblox installations and applies/updates FastFlag settings,
           handling Bloxstrap/Fishstrap modification folders.
        """
        local_app_data = os.getenv('LOCALAPPDATA')
        if not local_app_data:
            self.update_status("Error: LOCALAPPDATA environment variable not found.")
            return

        required_flags = {
            "FStringDebugLuaLogLevel": "trace",
            "FStringDebugLuaLogPattern": "ExpChat/mountClientApp"
        }
        applied_count = 0
        updated_count = 0

        def update_json_file(json_file_path, launcher_info_str):
            nonlocal applied_count, updated_count
            current_settings = {}
            needs_update = False
            file_existed = False
            file_dir = os.path.dirname(json_file_path)

            try:

                os.makedirs(file_dir, exist_ok=True)

                if os.path.exists(json_file_path):
                    file_existed = True
                    try:
                        with open(json_file_path, 'r') as f:
                            content = f.read()
                            if content.strip(): 
                                current_settings = json.loads(content)
                            else:
                                current_settings = {} 
                    except json.JSONDecodeError:
                        self.update_status(f"Warning: Corrupt JSON found at {json_file_path}. Overwriting for {launcher_info_str}.")
                        current_settings = {}
                        needs_update = True
                    except Exception as read_err:
                        self.update_status(f"Warning: Error reading {json_file_path}: {read_err}. Overwriting for {launcher_info_str}.")
                        current_settings = {}
                        needs_update = True
                else:

                    needs_update = True

                for key, value in required_flags.items():
                    if key not in current_settings or current_settings[key] != value:
                        current_settings[key] = value
                        needs_update = True

                if needs_update:
                    with open(json_file_path, 'w') as f:
                        json.dump(current_settings, f, indent=2)
                    if file_existed:
                        updated_count += 1
                        self.update_status(f"Updated FastFlags in {launcher_info_str} file")
                    else:
                        applied_count += 1
                        self.update_status(f"Applied FastFlags to new file in {launcher_info_str}")

            except Exception as e:

                self.update_status(f"Error processing FastFlags for {launcher_info_str}: {e}")

        mod_launchers_config_files = {
            'Bloxstrap': os.path.join(local_app_data, 'Bloxstrap', 'Modifications', 'ClientSettings', 'ClientAppSettings.json'),
            'Fishstrap': os.path.join(local_app_data, 'Fishstrap', 'Modifications', 'ClientSettings', 'ClientAppSettings.json')
        }

        for launcher_name, target_json_path in mod_launchers_config_files.items():

            launcher_base_dir = os.path.dirname(os.path.dirname(os.path.dirname(target_json_path)))
            if os.path.isdir(launcher_base_dir):
                update_json_file(target_json_path, f"{launcher_name} Modifications")

        roblox_versions_path = os.path.join(local_app_data, 'Roblox', 'Versions')
        if os.path.isdir(roblox_versions_path):
            try:
                for item_name in os.listdir(roblox_versions_path):
                    item_path = os.path.join(roblox_versions_path, item_name)

                    if os.path.isdir(item_path) and item_name.startswith("version-"):
                        version_folder_path = item_path
                        client_settings_path = os.path.join(version_folder_path, 'ClientSettings')
                        json_file_path = os.path.join(client_settings_path, 'ClientAppSettings.json')

                        update_json_file(json_file_path, f"Roblox/{item_name}")
            except OSError as e:
                self.update_status(f"Error accessing Roblox versions directory: {e}")

        if applied_count > 0 or updated_count > 0:
            self.update_status(f"Finished applying/updating FastFlags ({applied_count} new, {updated_count} updated)." )
        else:
            self.update_status("FastFlags check complete. No changes needed or relevant folders found.")

    def load_config(self):
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r') as f:
                    config = json.load(f)
                    self.webhook_url = config.get('webhook_url', '')
                    self.ps_link = config.get('ps_link', '')
                    self.royal_chest_ping_id = config.get('royal_chest_ping_id', '')
                    self.royal_chest_ping_type = config.get('royal_chest_ping_type', 'User')
                    self.gum_rift_ping_id = config.get('gum_rift_ping_id', '')
                    self.gum_rift_ping_type = config.get('gum_rift_ping_type', 'User')
                    self.launcher_choice = config.get('launcher_choice', 'Auto')

                    self.collection_enabled = config.get('collection_enabled', False)
                    loaded_coords = config.get('teleport_coords', None)

                    if isinstance(loaded_coords, (list, tuple)):
                        if len(loaded_coords) == 2:
                            self.teleport_coords = tuple(loaded_coords) 
                        elif len(loaded_coords) == 4:

                            self.teleport_coords = tuple(loaded_coords[:2])
                            print("Note: Old calibration format detected, using only x, y.")
                        else:
                             self.teleport_coords = None 
                    else:
                        self.teleport_coords = None

                    self.hatch_username = config.get('hatch_username', '')
                    self.hatch_secret_ping_enabled = config.get('hatch_secret_ping_enabled', False)
                    self.hatch_secret_ping_user_id = config.get('hatch_secret_ping_user_id', '')
                    self.hatch_detection_enabled = config.get('hatch_detection_enabled', True) 

                    self.tutorial_shown = config.get('tutorial_shown', False)

                    if hasattr(self, 'webhook_entry'):
                         self.webhook_entry.setText(self.webhook_url)
                    if hasattr(self, 'pslink_entry'):
                         self.pslink_entry.setText(self.ps_link)
                    if hasattr(self, 'royal_chest_ping_entry'):
                         self.royal_chest_ping_entry.setText(self.royal_chest_ping_id)
                    if hasattr(self, 'royal_chest_ping_type_combo'):
                         index = self.royal_chest_ping_type_combo.findText(self.royal_chest_ping_type)
                         if index >= 0:
                             self.royal_chest_ping_type_combo.setCurrentIndex(index)
                    if hasattr(self, 'gum_rift_ping_entry'):
                         self.gum_rift_ping_entry.setText(self.gum_rift_ping_id)
                    if hasattr(self, 'gum_rift_ping_type_combo'):
                         index = self.gum_rift_ping_type_combo.findText(self.gum_rift_ping_type)
                         if index >= 0:
                             self.gum_rift_ping_type_combo.setCurrentIndex(index)
            else:
                self.webhook_url = ''
                self.ps_link = ''
                self.royal_chest_ping_id = ''
                self.royal_chest_ping_type = 'User'
                self.gum_rift_ping_id = ''
                self.gum_rift_ping_type = 'User'
                self.launcher_choice = 'Auto'

                self.collection_enabled = False
                self.teleport_coords = None

                self.hatch_username = ''
                self.hatch_secret_ping_enabled = False
                self.hatch_secret_ping_user_id = ''
                self.hatch_detection_enabled = True 
                self.tutorial_shown = False 

        except Exception as e:
            print(f"Error loading config: {e}")
            self.webhook_url = ''
            self.ps_link = ''
            self.royal_chest_ping_id = ''
            self.royal_chest_ping_type = 'User'
            self.gum_rift_ping_id = ''
            self.gum_rift_ping_type = 'User'
            self.launcher_choice = 'Auto'

            self.collection_enabled = False
            self.teleport_coords = None

            self.hatch_username = ''
            self.hatch_secret_ping_enabled = False
            self.hatch_secret_ping_user_id = ''
            self.hatch_detection_enabled = True 
            self.tutorial_shown = False 

    def save_config(self):
        try:
            config_dir = os.path.dirname(self.config_file)
            os.makedirs(config_dir, exist_ok=True)

            config = {

                'webhook_url': self.webhook_entry.text().strip() if hasattr(self, 'webhook_entry') else getattr(self, 'webhook_url', ''),
                'ps_link': self.pslink_entry.text().strip() if hasattr(self, 'pslink_entry') else getattr(self, 'ps_link', ''),
                'royal_chest_ping_id': self.royal_chest_ping_entry.text().strip() if hasattr(self, 'royal_chest_ping_entry') else getattr(self, 'royal_chest_ping_id', ''),
                'royal_chest_ping_type': self.royal_chest_ping_type_combo.currentText() if hasattr(self, 'royal_chest_ping_type_combo') else getattr(self, 'royal_chest_ping_type', 'User'),
                'gum_rift_ping_id': self.gum_rift_ping_entry.text().strip() if hasattr(self, 'gum_rift_ping_entry') else getattr(self, 'gum_rift_ping_id', ''),
                'gum_rift_ping_type': self.gum_rift_ping_type_combo.currentText() if hasattr(self, 'gum_rift_ping_type_combo') else getattr(self, 'gum_rift_ping_type', 'User'),
                'launcher_choice': self.launcher_combo.currentText() if hasattr(self, 'launcher_combo') else getattr(self, 'launcher_choice', 'Auto'),

                'collection_enabled': self.collection_enabled_checkbox.isChecked() if hasattr(self, 'collection_enabled_checkbox') else getattr(self, 'collection_enabled', False),
                'teleport_coords': self.teleport_coords, 

                'hatch_username': self.hatch_username_entry.text().strip() if hasattr(self, 'hatch_username_entry') else getattr(self, 'hatch_username', ''),
                'hatch_secret_ping_enabled': self.hatch_secret_ping_checkbox.isChecked() if hasattr(self, 'hatch_secret_ping_checkbox') else getattr(self, 'hatch_secret_ping_enabled', False),
                'hatch_secret_ping_user_id': self.hatch_userid_entry.text().strip() if hasattr(self, 'hatch_userid_entry') else getattr(self, 'hatch_secret_ping_user_id', ''),
                'hatch_detection_enabled': self.hatch_detection_enabled_checkbox.isChecked() if hasattr(self, 'hatch_detection_enabled_checkbox') else getattr(self, 'hatch_detection_enabled', True),
                'tutorial_shown': getattr(self, 'tutorial_shown', False) 
            }
            with open(self.config_file, 'w') as f:
                json.dump(config, f, indent=4)
        except Exception as e:
            print(f"Error saving config: {e}")
            self.update_status(f"Error saving config: {e}")

    def _update_calibrate_button_text(self):
        if hasattr(self, 'calibrate_button'):
            if self.teleport_coords and len(self.teleport_coords) == 2:
                x, y = self.teleport_coords

                self.calibrate_button.setText(f"Recalibrate Teleport ({x}, {y})")

                if hasattr(self, 'calibrate_coords_label'):
                     self.calibrate_coords_label.setText(f"Calibrated at: ({x}, {y})")
                     self.calibrate_coords_label.setVisible(True)
            else:
                self.calibrate_button.setText("Calibrate Teleport Button")

                if hasattr(self, 'calibrate_coords_label'):
                    self.calibrate_coords_label.setText("")
                    self.calibrate_coords_label.setVisible(False)

    def get_log_dir(self):
        """Returns the appropriate log directory based on available Roblox launchers."""
        home = os.path.expanduser("~")

        log_paths = {
            "Fishstrap": os.path.join(home, "AppData", "Local", "Fishstrap", "Logs"),
            "Bloxstrap": os.path.join(home, "AppData", "Local", "Roblox", "Logs"),  
            "Roblox": os.path.join(home, "AppData", "Local", "Roblox", "Logs")
        }

        if hasattr(self, 'launcher_combo'):
            choice = self.launcher_combo.currentText()
            if choice in log_paths:
                return log_paths[choice]
            elif choice == "Auto (Detect)":

                pass

        valid_paths = []
        for launcher, path in log_paths.items():
            if os.path.isdir(path):
                try:
                    if any(os.path.isfile(os.path.join(path, f)) for f in os.listdir(path)):
                        valid_paths.append((launcher, path))

                        if hasattr(self, 'launcher_status'):
                            self.launcher_status.setText(f"Found {launcher} logs")
                except Exception:
                    continue

        if self.is_roblox_running() and valid_paths:
            most_recent = None
            most_recent_time = 0
            most_recent_launcher = None

            for launcher, path in valid_paths:
                try:
                    files = [os.path.join(path, f) for f in os.listdir(path) if os.path.isfile(os.path.join(path, f))]
                    if files:
                        latest = max(files, key=os.path.getmtime)
                        mod_time = os.path.getmtime(latest)
                        if mod_time > most_recent_time:
                            most_recent = path
                            most_recent_time = mod_time
                            most_recent_launcher = launcher
                except Exception:
                    continue

            if most_recent:

                if hasattr(self, 'launcher_status'):
                    self.launcher_status.setText(f"Active: {most_recent_launcher}")
                return most_recent

        for launcher_name in ["Fishstrap", "Bloxstrap", "Roblox"]:
            for launcher, path in valid_paths:
                if launcher == launcher_name:
                    if hasattr(self, 'launcher_status'):
                        self.launcher_status.setText(f"Using: {launcher}")
                    return path

        if hasattr(self, 'launcher_status'):
            self.launcher_status.setText("No logs found")

        return log_paths["Fishstrap"]

    def get_latest_log_file(self):
        try:
            log_dir = self.get_log_dir()
            if not os.path.isdir(log_dir):
                 print(f"Log directory not found: {log_dir}")
                 return None
            files = [os.path.join(log_dir, f) for f in os.listdir(log_dir) if os.path.isfile(os.path.join(log_dir, f))]
            return max(files, key=os.path.getmtime) if files else None
        except Exception as e:
            print(f"Error finding latest log file: {e}")
            self.update_status(f"Error finding log file: {e}")
            return None

    def read_last_n_lines(self, path, n=20):
        try:

            with open(path, "rb") as f:
                f.seek(0, os.SEEK_END)
                file_size = f.tell()
                buffer_size = 1024 * n 
                buffer = bytearray()

                while f.tell() > 0 and len(buffer.splitlines()) <= n + 1:
                    seek_pos = max(0, f.tell() - buffer_size)
                    f.seek(seek_pos, os.SEEK_SET)
                    chunk = f.read(min(buffer_size, file_size - seek_pos))
                    buffer = chunk + buffer
                    f.seek(seek_pos, os.SEEK_SET) 
                    if f.tell() == 0:
                         break 

                lines = buffer.decode('utf-8', errors='ignore').splitlines()

            return lines[-n:] if len(lines) >= n else lines

        except FileNotFoundError:
             print(f"Log file not found during read: {path}")

             return []
        except Exception as e:
            print(f"Error reading log: {e}")
            self.update_status(f"Error reading log: {e}")
            return []

    def extract_timestamp(self, line):

        parts = line.split(" ", 1)
        if len(parts) >= 2:
            try:

                dt = datetime.fromisoformat(parts[0])
                return time.mktime(dt.timetuple())
            except ValueError:
                try:

                    return time.mktime(time.strptime(parts[0], "%Y-%m-%d %H:%M:%S"))
                except ValueError:

                    try:
                        return time.mktime(time.strptime(parts[0], "%H:%M:%S")) 
                    except ValueError:
                        return None 
        return None

    def send_webhook(self, title, description, image_url=None, color=0x7289DA, ping_content=None, worker_instance=None):

        webhook_url = self.webhook_entry.text().strip() 
        if not webhook_url:
            status_message = "Webhook URL is missing, cannot send notification."
            if worker_instance:
                worker_instance.update_status_signal.emit(status_message)
            else:
                self.update_status(status_message)
            return

        unix_timestamp = int(time.time())
        discord_timestamp = f"<t:{unix_timestamp}:F>" 

        embed = {
            "title": title,
            "description": description, 
            "color": color,

            "footer": {
                "text": f"RiftScope | v{self.APP_VERSION}", 
                "icon_url": "https://i.postimg.cc/9MWNYd6y/Aura-Egg.png" 
            }
        }

        embed["fields"] = []

        embed["fields"].append({
            "name": "Time",
            "value": discord_timestamp,
            "inline": False 
        })

        if image_url:
            embed["thumbnail"] = {"url": image_url}

        ps_link = self.pslink_entry.text().strip()
        if ps_link:

             embed["fields"].append({
                 "name": "Server Link",
                 "value": f"[Click Here]({ps_link})",
                 "inline": False
             })

        if title in ("▶️ RiftScope Started", "⏹️ RiftScope Stopped"):
            embed["fields"].append({
                "name": "Support Server",
                "value": "[Join Here](https://discord.gg/6cuCu6ymkX)", 
                "inline": False
            })

        payload = {"embeds": [embed]}
        if ping_content:
            payload["content"] = ping_content

        try:

            response = requests.post(webhook_url, json=payload, timeout=10)
            response.raise_for_status() 
        except requests.exceptions.RequestException as e:
            error_message = f"Webhook error: {e}"
            print(error_message)

            if worker_instance and hasattr(worker_instance, 'update_status_signal'):
                 worker_instance.update_status_signal.emit(error_message)

            elif not worker_instance:
                 self.update_status(error_message)

    def is_roblox_running(self):

        try:
            for proc in psutil.process_iter(['pid', 'name']):

                try:
                    if 'RobloxPlayerBeta.exe' in proc.info['name']:
                        return True
                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                    continue 
            return False
        except Exception as e:
            print(f"Error checking Roblox process: {e}")

            return False 

    def monitor_log(self):
        if self.monitor_thread:
            self.monitor_thread.webhook_signal.emit(
                "▶️ RiftScope Started",
                "RiftScope is now monitoring for rare rifts!",
                None,
                0x7289DA,
                None
            )
        self.last_line_time = time.time()
        self.last_timestamp = None 
        self.processed_lines.clear() 

        log_dir = self.get_log_dir()
        launcher_used = "Unknown"
        for name in ["Fishstrap", "Bloxstrap", "Roblox"]:
            if name.lower() in log_dir.lower():
                launcher_used = name
                break

        if self.monitor_thread:
            self.monitor_thread.update_status_signal.emit(f"Monitoring using {launcher_used} logs at {log_dir}")

        if self.lock_log_file:
            locked_log = self.get_latest_log_file()
            if locked_log:
                self.current_log = locked_log
                if self.monitor_thread:
                    self.monitor_thread.update_status_signal.emit(f"Locked onto log file: {os.path.basename(locked_log)}")
            else:
                if self.monitor_thread:
                    self.monitor_thread.update_status_signal.emit("No log file found to lock onto. Waiting...")
                return 

        while self.running: 
            if not self.lock_log_file or not self.current_log:
                latest_log = self.get_latest_log_file()
                if latest_log and latest_log != self.current_log:
                    self.current_log = latest_log
                    if self.monitor_thread:
                        self.monitor_thread.update_status_signal.emit(f"Monitoring log file: {os.path.basename(latest_log)}")
                    self.processed_lines.clear() 
                    self.last_timestamp = None 

            if not self.current_log:
                if self.monitor_thread:
                    self.monitor_thread.update_status_signal.emit("No log file found. Waiting...")
                time.sleep(5) 
                self.last_line_time = time.time() 
                continue

            try:
                lines = self.read_last_n_lines(self.current_log, n=15)
                new_line_found = False

                for line in lines:

                    if not line.strip() or "font" not in line: 
                        continue

                    line_hash = hash(line) 
                    if line_hash in self.processed_lines:
                        continue

                    new_line_found = True 
                    self.processed_lines.add(line_hash) 

                    if len(self.processed_lines) > 500:

                         try:
                            self.processed_lines.pop()
                         except KeyError:
                            pass 

                    timestamp = self.extract_timestamp(line)
                    current_time = time.time() 

                    hatch_pattern = re.compile(r'<b><font color="#[0-9a-fA-F]{6}">([^<]+)</font> just hatched a <font color="([^"]+)">([^<]+?)(?: \(([^)]+%)\))?</font></b>') 

                    if "🔮" in line:
                        if current_time - self.last_royal_chest_time > self.EVENT_COOLDOWN_SECONDS:
                            if self.monitor_thread:
                                self.monitor_thread.update_status_signal.emit("✨ Royal chest detected!")
                                ping_id = self.royal_chest_ping_entry.text().strip()
                                ping_type = self.royal_chest_ping_type_combo.currentText()
                                ping_mention = f"<@{ping_id}>" if ping_type == "User" else f"<@&{ping_id}>"
                                self.monitor_thread.webhook_signal.emit(
                                    "✨ ROYAL CHEST DETECTED! ✨",
                                    f"A royal chest has been found in the chat!",
                                    self.royal_image_url,
                                    0x9b59b6,
                                    ping_mention if ping_id else None
                                )
                            self.last_royal_chest_time = current_time 
                        else:
                             if self.monitor_thread:
                                self.monitor_thread.update_status_signal.emit("Royal chest detected (Cooldown). Skipping ping.")

                    elif "Bring us your gum, Earthlings!" in line:
                         if current_time - self.last_gum_rift_time > self.EVENT_COOLDOWN_SECONDS:
                            if self.monitor_thread:
                                self.monitor_thread.update_status_signal.emit("🫧 Gum Rift detected!")
                                ping_id = self.gum_rift_ping_entry.text().strip()
                                ping_type = self.gum_rift_ping_type_combo.currentText()
                                ping_mention = f"<@{ping_id}>" if ping_type == "User" else f"<@&{ping_id}>"
                                self.monitor_thread.webhook_signal.emit(
                                    "🫧 GUM RIFT DETECTED! 🫧",
                                    f"A gum rift has been found in the chat!",
                                    None,
                                    0xFF69B4,
                                    ping_mention if ping_id else None
                                )
                            self.last_gum_rift_time = current_time 
                         else:
                             if self.monitor_thread:
                                self.monitor_thread.update_status_signal.emit("Gum rift detected (Cooldown). Skipping ping.")

                    elif "aura" in line.lower():

                        if self.monitor_thread:
                            self.monitor_thread.update_status_signal.emit("🌟 Aura egg detected!")
                            self.monitor_thread.webhook_signal.emit(
                                "🌟 AURA EGG DETECTED! 🌟",
                                f"An aura egg has been found in the chat!",
                                self.aura_image_url,
                                0x3498db,
                                "@everyone" 
                            )
                        self.last_aura_egg_time = current_time 

                    elif self.hatch_detection_enabled_checkbox.isChecked() and "just hatched a" in line:
                        print(f"[DEBUG] Found 'just hatched a' in line: {line.strip()}") 
                        match = hatch_pattern.search(line)
                        if match:
                            print("[DEBUG] Regex match successful!") 
                            hatched_username = match.group(1)
                            pet_color_hex = match.group(2)
                            pet_name = match.group(3).strip() 
                            rarity_match = match.group(4) 

                            rarity = rarity_match if rarity_match else "Unknown Rarity"

                            print(f"[DEBUG] Extracted: User='{hatched_username}', Pet='{pet_name}', Rarity='{rarity}'") 

                            base_pet_name = pet_name
                            mutation_prefix = ""
                            if pet_name.startswith("Shiny Mythic "):
                                mutation_prefix = "Shiny Mythic "
                                base_pet_name = pet_name[len(mutation_prefix):]
                            elif pet_name.startswith("Mythic "):
                                mutation_prefix = "Mythic "
                                base_pet_name = pet_name[len(mutation_prefix):]
                            elif pet_name.startswith("Shiny "):
                                mutation_prefix = "Shiny "
                                base_pet_name = pet_name[len(mutation_prefix):]

                            if mutation_prefix:
                                print(f"[DEBUG] Mutation detected. Base Pet Name for check: '{base_pet_name}'")

                            is_secret = base_pet_name in self.SECRET_PETS
                            is_legendary = base_pet_name in self.LEGENDARY_PETS
                            print(f"[DEBUG] Is Base Secret: {is_secret}, Is Base Legendary: {is_legendary}") 

                            if is_secret or is_legendary:
                                print(f"[DEBUG] Base Pet ('{base_pet_name}') is Secret or Legendary.") 

                                cooldown_check = current_time - self.last_hatch_ping_time
                                print(f"[DEBUG] Time since last hatch: {cooldown_check:.2f}s (Cooldown: {self.EVENT_COOLDOWN_SECONDS}s)") 
                                if cooldown_check > self.EVENT_COOLDOWN_SECONDS:
                                    print("[DEBUG] Cooldown passed.") 
                                    if self.monitor_thread:
                                        print("[DEBUG] Monitor thread exists. Sending status/webhook.") 
                                        pet_type = "Secret" if is_secret else "Legendary"

                                        self.monitor_thread.update_status_signal.emit(f"🎉 {pet_type} Pet Hatched by {hatched_username}: {pet_name} ({rarity})") 

                                        ping_content = None
                                        target_username = self.hatch_username_entry.text().strip()
                                        ping_user_id = self.hatch_userid_entry.text().strip()

                                        if is_secret and self.hatch_secret_ping_checkbox.isChecked() and ping_user_id and target_username and hatched_username.lower() == target_username.lower():
                                            ping_content = f"<@{ping_user_id}>"

                                        try:
                                            embed_color = int(pet_color_hex.lstrip('#'), 16)
                                        except ValueError:
                                            embed_color = 0x7289DA 

                                        self.monitor_thread.webhook_signal.emit(
                                            f"🎉 {pet_type.upper()} PET HATCHED! 🎉",
                                            f"**User:** {hatched_username}\n"
                                            f"**Pet:** {pet_name}\n"
                                            f"**Rarity:** {rarity}",
                                            None, 
                                            embed_color,
                                            ping_content 
                                        )
                                    self.last_hatch_ping_time = current_time 
                                else: 
                                    if self.monitor_thread:
                                        pet_type = "Secret" if is_secret else "Legendary"

                                        self.monitor_thread.update_status_signal.emit(f"{pet_type} hatch detected for {hatched_username} (Cooldown). Skipping ping.")

                if new_line_found:
                    self.last_line_time = time.time() 

                if time.time() - self.last_line_time > 60:
                     if not self.is_roblox_running():
                        if self.monitor_thread:
                            self.monitor_thread.update_status_signal.emit("⚠️ Roblox appears to be closed.")
                            self.monitor_thread.webhook_signal.emit(
                                "⚠️ Roblox Closed",
                                "No new log lines detected recently and Roblox process not found.",
                                None,
                                0xe74c3c,
                                None
                            )
                        self.last_line_time = time.time() 

            except Exception as e:
                 error_msg = f"Error during monitoring: {e}"
                 print(error_msg)
                 if self.monitor_thread:
                     self.monitor_thread.update_status_signal.emit(error_msg)

                 time.sleep(2)

            time.sleep(0.75) 

    def start_macro(self):
        print("--- F1 Shortcut/Start Button Activated ---") 
        self.save_config() 

        webhook_url = self.webhook_entry.text().strip()
        if not webhook_url:
            QMessageBox.warning(self, "Missing Webhook", "Please enter a webhook URL before starting.")
            return

        if self.running:
            return 

        self.running = True

        self.monitor_thread = Worker(self.monitor_log)

        self.monitor_thread.update_status_signal.connect(self.update_status)
        self.monitor_thread.webhook_signal.connect(self.send_webhook) 
        self.monitor_thread.finished_signal.connect(self.on_monitor_finished) 
        self.monitor_thread.start()

        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.test_button.setEnabled(False) 
        self.lock_button.setEnabled(False) 
        self.webhook_entry.setEnabled(False) 
        self.pslink_entry.setEnabled(False)
        self.royal_chest_ping_entry.setEnabled(False)
        self.royal_chest_ping_type_combo.setEnabled(False)
        self.gum_rift_ping_entry.setEnabled(False)
        self.gum_rift_ping_type_combo.setEnabled(False)

        self.collection_enabled_checkbox.setEnabled(False)
        self.calibrate_button.setEnabled(False)

        self.hatch_detection_enabled_checkbox.setEnabled(False) 
        self.hatch_username_entry.setEnabled(False)
        self.hatch_secret_ping_checkbox.setEnabled(False)
        self.hatch_userid_entry.setEnabled(False)

        self.update_status("🔍 Scanning started...")

        if self.collection_enabled_checkbox.isChecked():
            self.collection_enabled = True 
            if self.teleport_coords:
                self.update_status("🏁 Collection path enabled. Starting worker...")
                self.collection_running = True
                self.collection_worker = Worker(self.run_collection_loop)

                self.collection_worker.update_status_signal.connect(self.update_status)

                self.collection_worker.start()
            else:
                self.update_status("⚠️ Collection path enabled, but teleport button not calibrated. Skipping collection.")
                QMessageBox.warning(self, "Collection Warning",
                                    "Collection path is enabled, but the teleport button position hasn't been calibrated.\n"
                                    "Please calibrate before starting if you want collection active.")

        else:
            self.collection_enabled = False

    def stop_macro(self):
        print("--- F2 Shortcut/Stop Button Activated ---") 

        if not self.running and not self.collection_running: 
            print("Stop ignored: Neither scanner nor collection is running.") 
            return
        was_running = self.running
        self.running = False 
        self.collection_running = False 

        if self.monitor_thread and self.monitor_thread.isRunning():

             pass 

        if self.collection_worker and self.collection_worker.isRunning():
            self.update_status("Stopping collection worker...")
            self.collection_worker.wait(2000) 
            if self.collection_worker.isRunning(): 
                 print("Collection worker did not stop gracefully, terminating.")
                 self.collection_worker.terminate() 
            self.collection_worker = None 

        if was_running:
            self.send_webhook(
                "⏹️ RiftScope Stopped",
                "RiftScope has been stopped manually.",
                None,
                0x95a5a6,
                None
            )

        if not was_running:

            self.start_button.setEnabled(True)
            self.stop_button.setEnabled(False)
            self.test_button.setEnabled(True)
            self.lock_button.setEnabled(True)
            self.webhook_entry.setEnabled(True)
            self.pslink_entry.setEnabled(True)
            self.royal_chest_ping_entry.setEnabled(True)
            self.royal_chest_ping_type_combo.setEnabled(True)
            self.gum_rift_ping_entry.setEnabled(True)
            self.gum_rift_ping_type_combo.setEnabled(True)

            self.collection_enabled_checkbox.setEnabled(True)
            self.calibrate_button.setEnabled(True)

            self.hatch_detection_enabled_checkbox.setEnabled(True) 
            self.hatch_username_entry.setEnabled(True)
            self.hatch_secret_ping_checkbox.setEnabled(True)
            self.hatch_userid_entry.setEnabled(True)

            self.update_status("Scanner/Collection stopped. Ready again.")

    def on_monitor_finished(self):

        self.monitor_thread = None
        self.update_status("Log monitoring worker finished.")

        if not self.running and not self.collection_running:
            self.start_button.setEnabled(True)
            self.stop_button.setEnabled(False)
            self.test_button.setEnabled(True)
            self.lock_button.setEnabled(True)
            self.webhook_entry.setEnabled(True)
            self.pslink_entry.setEnabled(True)
            self.royal_chest_ping_entry.setEnabled(True)
            self.royal_chest_ping_type_combo.setEnabled(True)
            self.gum_rift_ping_entry.setEnabled(True)
            self.gum_rift_ping_type_combo.setEnabled(True)

            self.collection_enabled_checkbox.setEnabled(True)
            self.calibrate_button.setEnabled(True)

            self.hatch_detection_enabled_checkbox.setEnabled(True) 
            self.hatch_username_entry.setEnabled(True)
            self.hatch_secret_ping_checkbox.setEnabled(True)
            self.hatch_userid_entry.setEnabled(True)

            self.update_status("Scanner stopped. Ready to scan again.")

    def closeEvent(self, event):
        if self.calibrating and self.calibration_overlay:
             self.calibration_overlay.close() 

        if self.hotkey_listener:
            print("Stopping global hotkey listener...")
            self.hotkey_listener.stop()

        if self.running or self.collection_running:
            self.update_status("Close requested. Stopping processes...")
            self.stop_macro() 

            time.sleep(0.1)

            if self.monitor_thread and self.monitor_thread.isRunning():
                 self.monitor_thread.wait(500)
            if self.collection_worker and self.collection_worker.isRunning():
                 self.collection_worker.wait(500)

        if self.test_running and self.test_worker and self.test_worker.isRunning():
             self.test_running = False

        event.accept() 

    def check_for_updates(self):
        """Checks GitHub for the latest release.

        Runs in a background thread.
        Emits update_prompt_signal if an update is found.
        """
        api_url = f"https://api.github.com/repos/{self.REPO_URL}/releases/latest"
        self.update_status("Checking for updates...")
        try:
            response = requests.get(api_url, timeout=10)
            response.raise_for_status() 

            release_data = response.json()
            latest_version_str = release_data.get("tag_name", "").lstrip('v') 
            current_version_str = self.APP_VERSION

            latest_version = packaging.version.parse(latest_version_str)
            current_version = packaging.version.parse(current_version_str)

            if latest_version > current_version:
                self.update_status(f"New version available: v{latest_version_str}")
                assets = release_data.get("assets", [])
                download_url = None
                for asset in assets:

                    if asset.get("name", "").lower().endswith(".exe"):
                        download_url = asset.get("browser_download_url")
                        break

                if download_url:

                    self.update_prompt_signal.emit(latest_version_str, download_url)
                else:
                    self.update_status("Update found, but no .exe asset link available.")
                    print("Error: No .exe download URL found in the latest release assets.")

            else:
                self.update_status("RiftScope is up to date.")

        except requests.exceptions.HTTPError as e:

            if e.response.status_code == 404 and api_url in str(e):
                self.update_status("No releases found to check for updates.")
                print("Info: No releases published yet on the repository.")
            else:

                self.update_status(f"Update check failed: Server error ({e})")
                print(f"Error checking for updates (HTTPError): {e}")
        except requests.exceptions.RequestException as e:
            self.update_status(f"Update check failed: Network error ({e})")
            print(f"Error checking for updates: {e}")
        except packaging.version.InvalidVersion:
            self.update_status("Update check failed: Invalid version format found.")
            print(f"Error parsing version strings: current='{current_version_str}', latest='{latest_version_str}'")
        except Exception as e:
            self.update_status(f"Update check failed: An unexpected error occurred ({e})")
            print(f"An unexpected error occurred during update check: {e}")

    def prompt_update(self, new_version, download_url):
        """Asks the user if they want to update (runs in main thread)."""
        msg_box = QMessageBox(self) 
        msg_box.setWindowTitle("Update Available")
        msg_box.setText(f"A new version of RiftScope (v{new_version}) is available.\n" 
                        f"Your current version is v{self.APP_VERSION}.\n\n" 
                        f"Do you want to download and install it now?")
        msg_box.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        msg_box.setDefaultButton(QMessageBox.StandardButton.Yes)

        icon_path = "icon.ico"
        if os.path.exists(icon_path):
             msg_box.setWindowIcon(QIcon(icon_path))

        reply = msg_box.exec()

        if reply == QMessageBox.StandardButton.Yes:
            self.update_status(f"Starting update to v{new_version}...")

            self.update_worker = Worker(self.perform_update, download_url)
            self.update_worker.update_status_signal.connect(self.update_status)
            self.update_worker.finished_signal.connect(lambda: print("Update worker finished.")) 
            self.update_worker.start()
        else:
            self.update_status("Update declined by user.")

    def perform_update(self, download_url):
        """Downloads and attempts to install the update (runs in worker thread)."""
        try:

            current_exe_path = sys.executable
            if not current_exe_path or not current_exe_path.lower().endswith(".exe"):

                 self.update_status("Update Error: Cannot determine running executable path.")
                 print("Update Error: Not running from a detectable .exe file.")

                 return

            exe_dir = os.path.dirname(current_exe_path)
            exe_filename = os.path.basename(current_exe_path)
            new_exe_temp_path = os.path.join(exe_dir, f"_{exe_filename}_new")
            updater_bat_path = os.path.join(exe_dir, "_updater.bat")

            self.update_status(f"Downloading {os.path.basename(download_url)}...")
            response = requests.get(download_url, stream=True, timeout=60) 
            response.raise_for_status()

            total_size = int(response.headers.get('content-length', 0))
            downloaded_size = 0
            last_update_time = time.time()

            with open(new_exe_temp_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
                    downloaded_size += len(chunk)

                    current_time = time.time()
                    if current_time - last_update_time > 1: 
                        percent = int(100 * downloaded_size / total_size) if total_size > 0 else 0
                        self.update_status(f"Downloading update... {percent}%")
                        last_update_time = current_time

            self.update_status("Download complete.")

            quoted_current_exe = f'"{current_exe_path}"'
            quoted_new_exe = f'"{new_exe_temp_path}"'
            quoted_original_filename = f'"{exe_filename}"'

            batch_script_content = f"""
@echo off
echo Update downloaded.
echo Please close the main RiftScope application now.

echo Press any key AFTER closing RiftScope to continue the update...
pause > NUL 

echo Attempting to replace executable...

:delete_loop
del {quoted_current_exe} > nul 2>&1
if exist {quoted_current_exe} (
    echo Retrying delete...
    timeout /t 1 /nobreak > NUL
    goto delete_loop
)

echo Deleting old version complete.

:rename_loop
ren {quoted_new_exe} {quoted_original_filename}
if exist {quoted_new_exe} (
    echo Retrying rename...
    timeout /t 1 /nobreak > NUL
    goto rename_loop
)

echo Renaming new version complete.
echo Update complete. Starting new version...
start "" {quoted_current_exe}

echo Exiting updater script...
(goto) 2>nul & del "%~f0"
"""

            with open(updater_bat_path, 'w') as f:
                f.write(batch_script_content)

            self.update_status("Update downloaded. Please close RiftScope now to apply the update.")

            subprocess.Popen(['cmd.exe', '/c', updater_bat_path],
                             creationflags=subprocess.CREATE_NEW_CONSOLE,
                             close_fds=True)

        except requests.exceptions.RequestException as e:
            self.update_status(f"Update failed: Download error ({e})")

    def start_calibration(self):
        if self.calibrating:
             print("Calibration already in progress.")
             return
        if self.running:
             QMessageBox.warning(self, "Calibration Error", "Please stop the scanner before calibrating.")
             return

        if self.calibration_overlay is not None:
             print("Warning: Previous calibration overlay object detected unexpectedly.")

             try:
                 self.calibration_overlay.destroyed.disconnect(self.on_calibration_closed)
                 self.calibration_overlay.point_selected.disconnect(self.finish_calibration)
             except (TypeError, RuntimeError): pass
             self.calibration_overlay = None

        self.calibrating = True
        self.update_status("Starting teleport button calibration...")

        new_overlay = CalibrationOverlay()

        try:
            new_overlay.point_selected.connect(self.finish_calibration)
            new_overlay.destroyed.connect(self.on_calibration_closed)
        except Exception as e:
            print(f"Error connecting signals for new overlay: {e}")
            self.calibrating = False 
            return

        self.calibration_overlay = new_overlay
        self.calibration_overlay.show()

    def finish_calibration(self, point):
        if self.calibration_overlay:
            self.teleport_coords = (point.x(), point.y()) 
            self.update_status(f"Teleport point calibrated: ({point.x()},{point.y()})")
            self._update_calibrate_button_text()
            self.save_config() 

            self.calibrating = False
            self.calibration_overlay.close() 
        else:
             self.update_status("Calibration finished unexpectedly.")
             self.calibrating = False 

    def on_calibration_closed(self):
        self.update_status("Calibration window closed.")
        self.calibrating = False
        self.calibration_overlay = None 

    def _execute_collection_path(self):
        """Simulates the sequence of key presses for collection."""
        controller = pynput.keyboard.Controller()

        def press_release(key_char, press_time_ms, sleep_after_ms):
            if not self.collection_running: return False 
            try:

                 key = pynput.keyboard.KeyCode.from_char(key_char)
                 controller.press(key)
                 time.sleep(press_time_ms / 1000.0)
                 controller.release(key)
                 time.sleep(sleep_after_ms / 1000.0)
            except Exception as e:
                 print(f"Error pressing key '{key_char}': {e}")

            return True

        actions = [
            ('a', 330, 10), ('s', 450, 10), ('d', 330, 10), ('w', 530, 10),
            ('d', 440, 10), ('a', 200, 10), ('s', 500, 10), ('d', 500, 10),
            ('s', 270, 10), ('a', 560, 10), ('s', 250, 10), ('d', 530, 10),
            ('s', 500, 10), ('d', 200, 10), ('w', 620, 10), ('d', 200, 10),
            ('s', 620, 10), ('d', 70, 10), ('s', 300, 10), ('d', 100, 10),
            ('w', 1000, 10), ('d', 200, 10), ('s', 700, 10), ('a', 100, 10),
            ('s', 300, 10), ('d', 330, 10), ('w', 300, 10), ('d', 300, 10),
            ('w', 550, 10), ('a', 270, 10), ('s', 330, 10), ('a', 1000, 10),
            ('w', 750, 10), ('a', 1000, 10), ('w', 2250, 10), ('w', 200, 10),
            ('d', 350, 10), ('w', 570, 10), ('a', 500, 10), ('d', 1000, 10),
            ('s', 150, 10), ('w', 500, 10), ('a', 600, 10), ('d', 600, 10),
            ('w', 700, 10), ('d', 150, 10), ('s', 1000, 10), ('d', 300, 10),
            ('w', 1000, 10), ('d', 300, 10), ('s', 840, 10), ('d', 300, 10),
            ('w', 800, 10), ('s', 150, 10), ('d', 200, 10), ('s', 400, 10),
            ('d', 250, 10), ('w', 500, 10), ('s', 200, 0) 
        ]

        if self.collection_worker: 
            self.collection_worker.update_status_signal.emit("🚶 Starting collection path...")

        for key, press_time, sleep_after in actions:
            if not self.collection_running:
                 if self.collection_worker:
                    self.collection_worker.update_status_signal.emit("🚶 Collection path interrupted.")
                 return False 
            if not press_release(key, press_time, sleep_after):

                 return False
        if self.collection_worker:
             self.collection_worker.update_status_signal.emit("🚶 Collection path finished.")
        return True 

    def run_collection_loop(self):
        """The main loop for the collection worker thread."""
        keyboard_controller = pynput_keyboard.Controller()

        while self.collection_running:

            path_completed = self._execute_collection_path()
            if not path_completed or not self.collection_running:
                break 

            if self.collection_worker:
                self.collection_worker.update_status_signal.emit("⏳ Waiting after path...")
            time.sleep(2)
            if not self.collection_running: break

            try:
                if self.collection_worker:
                    self.collection_worker.update_status_signal.emit("⌨️ Pressing 'M'...")
                keyboard_controller.press('m')
                time.sleep(0.1) 
                keyboard_controller.release('m')
            except Exception as e:
                if self.collection_worker:
                     self.collection_worker.update_status_signal.emit(f"❌ Error pressing 'M': {e}")
                time.sleep(1) 
                continue 

            time.sleep(2)
            if not self.collection_running: break

            if self.teleport_coords and len(self.teleport_coords) == 2: 
                center_x, center_y = self.teleport_coords 
                if AUTOIT_AVAILABLE:
                    try:
                        if self.collection_worker:
                            self.collection_worker.update_status_signal.emit(f"🖱️ Clicking teleport at ({int(center_x)}, {int(center_y)}) via AutoIt...")

                        autoit.mouse_click("left", int(center_x), int(center_y), 1, speed=5) 

                        if self.collection_worker:
                             self.collection_worker.update_status_signal.emit(f"⏳ Waiting 3 seconds after click...")
                        time.sleep(3)

                    except Exception as e:
                         if self.collection_worker:
                            self.collection_worker.update_status_signal.emit(f"❌ Error clicking teleport (AutoIt): {e}")
                         time.sleep(1)
                else:

                     if self.collection_worker:
                         self.collection_worker.update_status_signal.emit(f"⚠️ AutoIt not available. Cannot perform click.")
                     time.sleep(1) 

            else:
                 if self.collection_worker:
                    self.collection_worker.update_status_signal.emit("⚠️ Teleport coordinates not set or invalid, skipping click.")

            time.sleep(1)

        if self.collection_worker:
            self.collection_worker.update_status_signal.emit("🚶 Collection loop stopped.")

    def _on_hotkey_press(self, key):
        """Callback function for pynput listener."""
        try:

            if key == pynput_keyboard.Key.f1:
                print("--- F1 Detected (pynput) ---")
                self.start_hotkey_signal.emit() 
            elif key == pynput_keyboard.Key.f2:
                print("--- F2 Detected (pynput) ---")
                self.stop_hotkey_signal.emit() 
        except AttributeError:

            pass
        except Exception as e:

            print(f"Error in pynput listener callback: {e}")

    def _start_pynput_listener(self):
        """Runs in a separate thread to listen for global hotkeys."""
        print("Starting global hotkey listener...")
        try:

            with pynput_keyboard.Listener(on_press=self._on_hotkey_press) as listener:
                self.hotkey_listener = listener 
                listener.join() 
        except Exception as e:
            print(f"Failed to start pynput listener: {e}")
            self.update_status(f"Error: Failed to start global hotkey listener: {e}")
        finally:
            print("Global hotkey listener thread finished.")
            self.hotkey_listener = None 

if __name__ == "__main__":
    app = QApplication(sys.argv)
    main_window = RiftScopeApp()
    main_window.show()
    sys.exit(app.exec())