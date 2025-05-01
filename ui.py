import os
import time
import json
import threading
import requests
import sys
import re
from datetime import datetime
from PyQt6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, 
                           QHBoxLayout, QLabel, QLineEdit, QPushButton, 
                           QFrame, QMessageBox, QStyleFactory, QTabWidget, 
                           QTextEdit, QComboBox, QGridLayout, QCheckBox)
from PyQt6.QtGui import QPalette, QColor, QFont, QKeySequence, QShortcut, QIcon
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer

try:
    import pynput 
    from pynput import keyboard as pynput_keyboard 
    PYNPUT_AVAILABLE = True
except ImportError:
    PYNPUT_AVAILABLE = False
    print("WARNING: pynput module not found. Hotkeys will not work.")

from models import Worker, CalibrationOverlay
from config import Config
from utils import is_roblox_running, apply_roblox_fastflags, read_last_n_lines
from detection import RiftDetector
from collection import CollectionManager
from updater import UpdateManager

# Define dark theme palette
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

# Define button styling
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

class RiftScopeApp(QMainWindow):
    """Main application window for RiftScope"""
    
    APP_VERSION = "1.2.6-Hotfix"
    REPO_URL = "cresqnt-sys/RiftScope"
    
    update_prompt_signal = pyqtSignal(str, str)
    start_hotkey_signal = pyqtSignal()
    stop_hotkey_signal = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"RiftScope v{self.APP_VERSION}")
        self.setGeometry(100, 100, 500, 350) 

        # Set window icon
        icon_path = "icon.ico"
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
        else:
            print(f"Warning: Icon file not found at '{icon_path}'")

        # Apply dark theme
        self.setPalette(dark_palette) 
        QStyleFactory.create("Fusion") 

        # Flag to track initial app startup
        self.initializing = True

        # Initialize state variables
        self.running = False
        self.test_running = False
        self.test_worker = None 
        self.calibrating = False
        self.calibration_overlay = None
        self.hotkey_listener = None
        self.monitor_thread = None 
        self.teleport_coords = None  # Initialize teleport_coords attribute
        self.collection_running = False  # Initialize collection_running attribute
        
        # Initialize config
        self.config = Config(self)
        self.config.load()
        
        # Load teleport_coords from config
        if hasattr(self.config, 'teleport_coords') and self.config.teleport_coords:
            self.teleport_coords = self.config.teleport_coords
            print(f"Loaded teleport coords from config: {self.teleport_coords}")
        
        # Initialize managers
        self.detector = RiftDetector(self)
        self.collection_manager = CollectionManager(self)
        self.update_manager = UpdateManager(self, self.APP_VERSION, self.REPO_URL)
        
        # Build UI
        self.build_ui()
        
        # Apply Roblox configuration
        apply_roblox_fastflags(self.update_status)
        
        # Apply loaded config to UI
        self.config.apply_to_ui()
        
        # Application is now fully initialized
        self.initializing = False
        
        # Connect update signal
        self.update_prompt_signal.connect(self.update_manager.prompt_update)
        
        # Connect hotkey signals
        self.start_hotkey_signal.connect(self.start_macro)
        self.stop_hotkey_signal.connect(self.stop_macro)

        # Start hotkey listener thread
        if PYNPUT_AVAILABLE:
            listener_thread = threading.Thread(target=self._start_pynput_listener, daemon=True)
            listener_thread.start()
        
        # Start update check
        self.update_checker_worker = Worker(self.update_manager.check_for_updates)
        self.update_checker_worker.start()
        
    def build_ui(self):
        """Construct the main application UI"""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(15)

        # Title
        title_label = QLabel(f"🏝️ RiftScope v{self.APP_VERSION}")
        title_font = QFont("Segoe UI", 16)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_label.setStyleSheet("color: #7289da;") 
        main_layout.addWidget(title_label)

        # Create tab widget
        self.tab_widget = QTabWidget()
        main_layout.addWidget(self.tab_widget)

        # Add the Scanner tab
        self._build_scanner_tab()
        
        # Add the Pings tab
        self._build_pings_tab()
        
        # Add the Collection tab
        self._build_collection_tab()
        
        # Add the Hatch tab
        self._build_hatch_tab()
        
        # Add the Logs tab
        self._build_logs_tab()
        
        # Add the Credits tab
        self._build_credits_tab()
    
    def _build_scanner_tab(self):
        """Build the Scanner tab UI"""
        self.scanner_tab = QWidget()
        scanner_layout = QVBoxLayout(self.scanner_tab)
        scanner_layout.setContentsMargins(10, 15, 10, 10) 
        scanner_layout.setSpacing(10)
        self.tab_widget.addTab(self.scanner_tab, "Scanner")

        # Input fields section
        input_frame = QFrame()
        input_layout = QVBoxLayout(input_frame)
        input_layout.setContentsMargins(0, 0, 0, 0)
        input_layout.setSpacing(5)

        # Launcher selection
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
        launcher_layout.addWidget(self.launcher_combo)

        self.launcher_status = QLabel("")
        self.launcher_status.setStyleSheet("color: #43b581;")
        launcher_layout.addWidget(self.launcher_status)

        input_layout.addWidget(launcher_frame)

        # Server Mode selection
        self.server_mode_label = QLabel("Server Mode:")
        input_layout.addWidget(self.server_mode_label)
        
        server_mode_frame = QFrame()
        server_mode_layout = QHBoxLayout(server_mode_frame)
        server_mode_layout.setContentsMargins(0, 0, 0, 0)
        server_mode_layout.setSpacing(5)
        
        self.server_mode_combo = QComboBox()
        self.server_mode_combo.addItem("Private Server")
        self.server_mode_combo.addItem("Public Server")
        self.server_mode_combo.currentIndexChanged.connect(self.on_server_mode_changed)
        server_mode_layout.addWidget(self.server_mode_combo)
        
        self.server_status = QLabel("")
        self.server_status.setStyleSheet("color: #43b581;")
        server_mode_layout.addWidget(self.server_status)
        
        input_layout.addWidget(server_mode_frame)

        # Discord webhook URL
        self.webhook_label = QLabel("Discord Webhook URL:")
        input_layout.addWidget(self.webhook_label)
        self.webhook_entry = QLineEdit()
        self.webhook_entry.setPlaceholderText("Enter your Discord webhook URL here")
        input_layout.addWidget(self.webhook_entry)

        # Private server link
        self.pslink_label = QLabel("Private Server Link:")
        input_layout.addWidget(self.pslink_label)
        self.pslink_entry = QLineEdit()
        self.pslink_entry.setPlaceholderText("Enter the private server link for notifications")
        input_layout.addWidget(self.pslink_entry)

        scanner_layout.addWidget(input_frame)

        # Main buttons (start/stop)
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

        # Secondary buttons (test/lock)
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
        
    def _build_pings_tab(self):
        """Build the Pings tab UI"""
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

        # Royal Chest ping settings
        self.royal_chest_ping_label = QLabel("Royal Chest Ping:")
        self.royal_chest_ping_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        pings_grid_layout.addWidget(self.royal_chest_ping_label, 0, 0)

        self.royal_chest_ping_entry = QLineEdit()
        self.royal_chest_ping_entry.setPlaceholderText("Enter User/Role ID (Optional)")
        pings_grid_layout.addWidget(self.royal_chest_ping_entry, 0, 1)

        self.royal_chest_ping_type_combo = QComboBox()
        self.royal_chest_ping_type_combo.addItem("User")
        self.royal_chest_ping_type_combo.addItem("Role")
        self.royal_chest_ping_type_combo.setFixedWidth(60) 
        pings_grid_layout.addWidget(self.royal_chest_ping_type_combo, 0, 2)

        # Gum Rift ping settings
        self.gum_rift_ping_label = QLabel("Gum Rift Ping:")
        self.gum_rift_ping_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        pings_grid_layout.addWidget(self.gum_rift_ping_label, 1, 0)

        self.gum_rift_ping_entry = QLineEdit()
        self.gum_rift_ping_entry.setPlaceholderText("Enter User/Role ID (Optional)")
        pings_grid_layout.addWidget(self.gum_rift_ping_entry, 1, 1)

        self.gum_rift_ping_type_combo = QComboBox()
        self.gum_rift_ping_type_combo.addItem("User")
        self.gum_rift_ping_type_combo.addItem("Role")
        self.gum_rift_ping_type_combo.setFixedWidth(60) 
        pings_grid_layout.addWidget(self.gum_rift_ping_type_combo, 1, 2)

        # Silly Egg ping (fixed to @everyone)
        self.silly_egg_ping_label = QLabel("Silly Egg Ping:")
        self.silly_egg_ping_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        pings_grid_layout.addWidget(self.silly_egg_ping_label, 3, 0)

        self.silly_egg_ping_display = QLabel("<code>@everyone</code> (Cannot be changed)")
        self.silly_egg_ping_display.setTextFormat(Qt.TextFormat.RichText)
        pings_grid_layout.addWidget(self.silly_egg_ping_display, 3, 1, 1, 2)

        pings_grid_layout.setColumnStretch(1, 1)
        pings_layout.addLayout(pings_grid_layout) 
        pings_layout.addStretch()
        
    def _build_collection_tab(self):
        """Build the Collection tab UI"""
        self.collection_tab = QWidget()
        collection_layout = QVBoxLayout(self.collection_tab)
        collection_layout.setContentsMargins(15, 20, 15, 15)
        collection_layout.setSpacing(10)
        self.tab_widget.addTab(self.collection_tab, "Collection")

        collection_title_label = QLabel("Collection Path")
        collection_title_font = QFont("Segoe UI", 12)
        collection_title_font.setBold(True)
        collection_title_label.setFont(collection_title_font)
        collection_title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        collection_layout.addWidget(collection_title_label)

        # Collection path settings
        self.collection_enabled_checkbox = QCheckBox("Enable Collection Path")
        collection_layout.addWidget(self.collection_enabled_checkbox)

        self.calibrate_button = QPushButton() 
        self.calibrate_button.setStyleSheet(button_stylesheet.format(
             bg_color="#43b581", fg_color="white", hover_bg_color="#3ca374", pressed_bg_color="#359066"
        ))
        self.calibrate_button.clicked.connect(self.collection_manager.start_calibration) 
        collection_layout.addWidget(self.calibrate_button)

        self.calibrate_coords_label = QLabel("")
        self.calibrate_coords_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.calibrate_coords_label.setStyleSheet("font-size: 8pt; color: #aaa;")
        collection_layout.addWidget(self.calibrate_coords_label)
        self.collection_manager._update_calibrate_button_text() 

        # Collection tutorial link
        collection_tutorial_label = QLabel(
            'Collection Tutorial: <a href="https://www.youtube.com/watch?v=YOQQR3n8VE4">Watch Video</a>'
        )
        collection_tutorial_label.setTextFormat(Qt.TextFormat.RichText)
        collection_tutorial_label.setOpenExternalLinks(True)
        collection_tutorial_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        collection_layout.addWidget(collection_tutorial_label)

        collection_layout.addStretch()
        
    def _build_hatch_tab(self):
        """Build the Hatch tab UI"""
        self.hatch_tab = QWidget()
        hatch_layout = QVBoxLayout(self.hatch_tab)
        hatch_layout.setContentsMargins(15, 20, 15, 15)
        hatch_layout.setSpacing(10)
        self.tab_widget.addTab(self.hatch_tab, "Hatch") 

        hatch_title_label = QLabel("Hatch Settings")
        hatch_title_font = QFont("Segoe UI", 12)
        hatch_title_font.setBold(True)
        hatch_title_label.setFont(hatch_title_font)
        hatch_title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hatch_layout.addWidget(hatch_title_label)

        # Hatch detection settings
        self.hatch_detection_enabled_checkbox = QCheckBox("Enable Hatch Detection")
        self.hatch_detection_enabled_checkbox.setChecked(True) 
        hatch_layout.addWidget(self.hatch_detection_enabled_checkbox)

        self.hatch_username_label = QLabel("Roblox Username (for Secret Ping):") 
        hatch_layout.addWidget(self.hatch_username_label)
        self.hatch_username_entry = QLineEdit()
        self.hatch_username_entry.setPlaceholderText("Enter the username for hatching")
        hatch_layout.addWidget(self.hatch_username_entry)

        self.hatch_secret_ping_checkbox = QCheckBox("Secret Pets Ping")
        hatch_layout.addWidget(self.hatch_secret_ping_checkbox)

        self.hatch_userid_label = QLabel("User ID to Ping:")
        hatch_layout.addWidget(self.hatch_userid_label)
        self.hatch_userid_entry = QLineEdit()
        self.hatch_userid_entry.setPlaceholderText("Enter User ID to ping for secret pets")
        hatch_layout.addWidget(self.hatch_userid_entry)

        hatch_layout.addStretch()
        
    def _build_logs_tab(self):
        """Build the Logs tab UI"""
        self.logs_tab = QWidget()
        logs_layout = QVBoxLayout(self.logs_tab)
        logs_layout.setContentsMargins(10, 10, 10, 10)
        self.tab_widget.addTab(self.logs_tab, "Logs")

        # Log console
        self.log_console = QTextEdit()
        self.log_console.setReadOnly(True)
        log_font = QFont("Consolas", 9) 
        if log_font.family() == "Consolas": 
             self.log_console.setFont(log_font)
        logs_layout.addWidget(self.log_console)
        
    def _build_credits_tab(self):
        """Build the Credits tab UI"""
        self.credits_tab = QWidget()
        credits_layout = QVBoxLayout(self.credits_tab)
        credits_layout.setContentsMargins(15, 20, 15, 15)
        credits_layout.setSpacing(10)
        self.tab_widget.addTab(self.credits_tab, "Credits")

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

    def update_status(self, message):
        """Update the status in the log console"""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        formatted_log_message = f"[{timestamp}] {message}"

        if hasattr(self, 'log_console'):
            self.log_console.append(formatted_log_message)
            self.log_console.ensureCursorVisible() 

        print(formatted_log_message)
        
    def toggle_lock_log(self, checked):
        """Toggle the log file locking state"""
        self.detector.lock_log_file = checked
        status_text = "Lock Log File: ON" if checked else "Lock Log File: OFF"
        self.lock_button.setText(status_text) 
        self.update_status(f"Log file locking {'enabled' if self.detector.lock_log_file else 'disabled'}.")
        
    def run_test_scan(self):
        """Run a test scan to verify detection is working"""
        if self.test_running:
            return

        self.config.save() 

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

        self.detector.test_worker = Worker(self.detector.run_test_scan)
        self.test_worker = self.detector.test_worker
        self.test_worker.update_status_signal.connect(self.update_status)
        self.test_worker.finished_signal.connect(self.on_test_finished)
        self.test_worker.start()
        
    def on_test_finished(self):
        """Called when test scan finishes"""
        self.test_button.setEnabled(True)
        self.test_running = False
        
    def send_webhook(self, title, description, image_url=None, color=0x7289DA, ping_content=None, worker_instance=None):
        """Send a notification to the Discord webhook"""
        webhook_url = self.webhook_entry.text().strip() 
        if not webhook_url:
            status_message = "Webhook URL is missing, cannot send notification."
            if worker_instance and hasattr(worker_instance, 'update_status_signal'):
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

        # Get appropriate server link based on mode
        server_link = ""
        if hasattr(self, 'server_mode_combo'):
            server_mode = self.server_mode_combo.currentText()
            if server_mode == "Private Server":
                server_link = self.pslink_entry.text().strip()
            elif server_mode == "Public Server" and hasattr(self, 'detector') and self.detector.current_job_id:
                job_id = self.detector.current_job_id
                
                # First check if we already have a ro.pro URL in the text field
                current_link = self.pslink_entry.text().strip()
                if current_link and current_link.startswith("http") and "ro.pro" in current_link:
                    server_link = current_link
                else:
                    # Need to fetch the URL from the API
                    try:
                        # Make sure requests is imported
                        import requests
                        api_url = f"https://api.ropro.io/createInvite.php?universeid=6504986360&serverid={job_id}"
                        response = requests.get(api_url, timeout=5)
                        
                        if response.status_code == 200 and response.text.strip().startswith("http"):
                            server_link = response.text.strip()
                            # Also update the UI
                            self.pslink_entry.setText(server_link)
                        else:
                            # Fallback to API URL
                            server_link = api_url
                    except Exception:
                        # Fallback to API URL on exception
                        server_link = f"https://api.ropro.io/createInvite.php?universeid=6504986360&serverid={job_id}"
        
        if server_link:
            # Add server type text based on mode
            server_type = "Server Link"
            if hasattr(self, 'server_mode_combo'):
                server_type = f"{self.server_mode_combo.currentText()} Link"
                
            embed["fields"].append({
                "name": server_type,
                "value": f"[Click Here]({server_link})",
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
            # Make sure requests is imported
            import requests
            response = requests.post(webhook_url, json=payload, timeout=10)
            response.raise_for_status() 
        except Exception as e:
            error_message = f"Webhook error: {e}"
            print(error_message)

            if worker_instance and hasattr(worker_instance, 'update_status_signal'):
                worker_instance.update_status_signal.emit(error_message)
            elif not worker_instance:
                self.update_status(error_message)
    
    def start_macro(self):
        """Start the scanning process"""
        print("--- F1 Shortcut/Start Button Activated ---") 
        self.config.save() 

        webhook_url = self.webhook_entry.text().strip()
        if not webhook_url:
            QMessageBox.warning(self, "Missing Webhook", "Please enter a webhook URL before starting.")
            return

        if self.running:
            return 

        self.running = True
        
        # Configure detector with UI components
        self.detector.monitor_thread = Worker(self.detector.monitor_log)
        self.monitor_thread = self.detector.monitor_thread
        self.monitor_thread.update_status_signal.connect(self.update_status)
        self.monitor_thread.webhook_signal.connect(self.send_webhook) 
        self.monitor_thread.finished_signal.connect(self.on_monitor_finished) 
        self.monitor_thread.start()

        # Update UI state
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
        self.server_mode_combo.setEnabled(False)

        self.update_status("🔍 Scanning started...")

        # Start collection if enabled
        if self.collection_enabled_checkbox.isChecked():
            self.collection_enabled = True 
            if self.teleport_coords:
                self.update_status("🏁 Collection path enabled. Starting worker...")
                self.collection_running = True
                self.collection_manager.collection_worker = Worker(self.collection_manager.run_collection_loop)
                self.collection_manager.collection_worker.update_status_signal.connect(self.update_status)
                self.collection_manager.collection_worker.start()
            else:
                self.update_status("⚠️ Collection path enabled, but teleport button not calibrated. Skipping collection.")
                QMessageBox.warning(self, "Collection Warning",
                                   "Collection path is enabled, but the teleport button position hasn't been calibrated.\n"
                                   "Please calibrate before starting if you want collection active.")
        else:
            self.collection_enabled = False
            
    def stop_macro(self):
        """Stop the scanning process"""
        print("--- F2 Shortcut/Stop Button Activated ---") 

        if not self.running and not hasattr(self, 'collection_running'): 
            print("Stop ignored: Neither scanner nor collection is running.") 
            return
            
        was_running = self.running
        self.running = False 
        
        if hasattr(self, 'collection_running'):
            self.collection_running = False 

        # Ensure the monitor thread stops
        if self.monitor_thread and self.monitor_thread.isRunning():
            print("Waiting for monitor thread to stop...")
            # Give the thread a short time to terminate gracefully
            if not self.monitor_thread.wait(500):  # Wait up to 500ms
                print("Monitor thread did not stop gracefully, terminating.")
                self.monitor_thread.terminate()
            self.monitor_thread = None

        # Stop collection worker if running
        if hasattr(self.collection_manager, 'collection_worker') and self.collection_manager.collection_worker and self.collection_manager.collection_worker.isRunning():
            self.update_status("Stopping collection worker...")
            if not self.collection_manager.collection_worker.wait(500):  # Wait up to 500ms 
                print("Collection worker did not stop gracefully, terminating.")
                self.collection_manager.collection_worker.terminate() 
            self.collection_manager.collection_worker = None 

        if was_running:
            self.send_webhook(
                "⏹️ RiftScope Stopped",
                "RiftScope has been stopped manually.",
                None,
                0x95a5a6,
                None
            )

        # Always enable UI controls when stop is clicked
        self._enable_ui_controls()
        self.update_status("Scanner/Collection stopped. Ready again.")
        
    def _enable_ui_controls(self):
        """Enable all UI controls when scanning stops"""
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
        self.server_mode_combo.setEnabled(True)
        
        # Re-apply server mode settings but don't show popup
        if hasattr(self, 'server_mode_combo'):
            self.on_server_mode_changed(self.server_mode_combo.currentIndex(), show_popup=False)

    def on_monitor_finished(self):
        """Called when monitor thread finishes"""
        self.monitor_thread = None
        self.update_status("Log monitoring worker finished.")

        if not self.running and not hasattr(self, 'collection_running'):
            self._enable_ui_controls()
            self.update_status("Scanner stopped. Ready to scan again.")
            
    def closeEvent(self, event):
        """Handle window close event"""
        if self.calibrating and self.calibration_overlay:
            self.calibration_overlay.close() 

        if self.hotkey_listener:
            print("Stopping global hotkey listener...")
            self.hotkey_listener.stop()

        if self.running or (hasattr(self, 'collection_running') and self.collection_running):
            self.update_status("Close requested. Stopping processes...")
            self.stop_macro() 
            time.sleep(0.1)

            if self.monitor_thread and self.monitor_thread.isRunning():
                self.monitor_thread.wait(500)
                
            if hasattr(self.collection_manager, 'collection_worker') and self.collection_manager.collection_worker and self.collection_manager.collection_worker.isRunning():
                self.collection_manager.collection_worker.wait(500)

        if self.test_running and self.test_worker and self.test_worker.isRunning():
            self.test_running = False

        event.accept()
        
    def _on_hotkey_press(self, key):
        """Callback function for pynput listener"""
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
        """Runs in a separate thread to listen for global hotkeys"""
        if not PYNPUT_AVAILABLE:
            print("Cannot start pynput listener: pynput module not available")
            self.update_status("Warning: Global hotkeys disabled - pynput module not available")
            return
            
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

    def on_server_mode_changed(self, index, show_popup=True):
        """Handle server mode selection changes"""
        mode = self.server_mode_combo.currentText()
        
        # Show popup when switching TO Public Server (index 1)
        # - Only when explicitly triggered by user (show_popup=True)
        # - Only when not during initial application startup
        # - Only when index is 1 (Public Server)
        if show_popup and not self.initializing and mode == "Public Server" and index == 1:
            # Show a popup warning about starting RiftScope before Roblox
            QMessageBox.information(
                self, 
                "Public Server Mode",
                "For best performance with public servers, RiftScope should be started before Roblox.\n\n"
                "This helps ensure accurate server detection.\n"
                "You may have to wait from 10 seconds to 2 minutes for the public server to be picked up or for RiftScope to pickup server changes.",
                QMessageBox.StandardButton.Ok
            )
        if mode == "Private Server":
            self.pslink_label.setText("Private Server Link:")
            self.pslink_entry.setPlaceholderText("Enter the private server link for notifications")
            self.pslink_entry.setReadOnly(False)
            self.server_status.setText("")
        else:  # Public Server
            self.pslink_label.setText("Public Server Link (Auto-detected):")
            self.pslink_entry.setPlaceholderText("Server link will be auto-detected when you join a game")
            self.pslink_entry.setReadOnly(True)
            
            # Show current server info if available
            if hasattr(self, 'detector') and self.detector.current_job_id:
                job_id = self.detector.current_job_id
                truncated_id = job_id[:8] + "..." if len(job_id) > 8 else job_id
                self.server_status.setText(f"Current Server: {truncated_id}")
                
                # Try to fetch the shortened link
                self.update_status("Fetching shortened server link...")
                
                # First set a fallback API URL
                api_url = f"https://api.ropro.io/createInvite.php?universeid=6504986360&serverid={job_id}"
                self.pslink_entry.setText(api_url)
                
                # Fetch the URL directly (synchronously) for immediate feedback
                self._fetch_and_display_url(job_id)
                
                # Now try to get the shortened URL in a background worker for ongoing attempts
                try:
                    # Make sure we don't create multiple workers
                    if hasattr(self, '_fetch_short_link_worker') and self._fetch_short_link_worker and self._fetch_short_link_worker.isRunning():
                        self._fetch_short_link_worker.wait(100)  # Give any running worker a chance to finish
                    
                    self._fetch_short_link_worker = Worker(self._fetch_short_link, job_id)
                    self._fetch_short_link_worker.start()
                except Exception as e:
                    self.update_status(f"Error starting link fetch worker: {str(e)}")
                
                # Log the current server information
                self.update_status(f"Current Public Server: JobID={job_id}")
            else:
                self.server_status.setText("No server detected yet")
                self.pslink_entry.clear()
                
        # Save configuration when mode changes
        if hasattr(self, 'config'):
            self.config.save()
            
    def _fetch_and_display_url(self, job_id):
        """Directly fetch and display the URL - sync version for immediate feedback"""
        try:
            import requests
            
            # First set the API URL
            api_url = f"https://api.ropro.io/createInvite.php?universeid=6504986360&serverid={job_id}"
            self.update_status(f"Making request to RoPro API: {api_url}")
            
            # Make the request to the RoPro API - the URL is returned directly as plain text
            response = requests.get(api_url, timeout=10)
            
            # Check if we got a successful response
            if response.status_code == 200:
                # Get the URL from the response text - should be a direct ro.pro URL
                if response.text.strip().startswith("http"):
                    # Clean up any whitespace
                    short_url = response.text.strip()
                    self.pslink_entry.setText(short_url)
                    self.update_status(f"✅ Got RoPro URL from API: {short_url}")
                    return
            
            # If we get here, something went wrong with the API
            self.update_status(f"API returned status {response.status_code}: {response.text[:100]}")
            self.pslink_entry.setText(api_url) # Fallback to API URL
            
        except Exception as e:
            self.update_status(f"Error fetching RoPro URL: {str(e)}")
            # Fallback to API URL
            api_url = f"https://api.ropro.io/createInvite.php?universeid=6504986360&serverid={job_id}"
            self.pslink_entry.setText(api_url)
            
    def _fetch_short_link(self, job_id):
        """Fetch the shortened ro.pro link from the RoPro API - used by the background worker"""
        try:
            import requests
            
            # Create the API URL
            api_url = f"https://api.ropro.io/createInvite.php?universeid=6504986360&serverid={job_id}"
            
            # Make the request to the RoPro API
            response = requests.get(api_url, timeout=10)
            
            # Check if we got a successful response
            if response.status_code == 200:
                # Get the URL from the response text
                if response.text.strip().startswith("http"):
                    short_url = response.text.strip()
                    self.pslink_entry.setText(short_url)
                    self.update_status(f"✅ Worker: Got RoPro URL from API: {short_url}")
                    return
                
            # Only log if something went wrong
            self.update_status(f"Worker: API returned status {response.status_code}")
            
        except Exception as e:
            self.update_status(f"Error in worker URL fetch: {str(e)}")