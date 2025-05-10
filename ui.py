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
                           QTextEdit, QComboBox, QGridLayout, QCheckBox, QScrollArea, QSpinBox)
from PyQt6.QtGui import QPalette, QColor, QFont, QKeySequence, QShortcut, QIcon
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer

try:
    import pynput 
    from pynput import keyboard as pynput_keyboard 
    PYNPUT_AVAILABLE = True
except ImportError:
    PYNPUT_AVAILABLE = False
    print("WARNING: pynput module not found. Hotkeys will not work.")

from models import Worker, CalibrationOverlay, AreaCalibrationOverlay, CurrencyScreenshotWorker, PIL_AVAILABLE
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
    
    APP_VERSION = "1.3.5-Stable"
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
        self.claw_skip_coords = None # New
        self.claw_claim_coords = None # New
        self.claw_start_coords = None # New
        self.map_up_arrow_coords = None # New
        self.map_down_arrow_coords = None # New
        self.collection_running = False  # Initialize collection_running attribute
        self.shop_item1_coords = None # New
        self.shop_item2_coords = None # New
        self.shop_item3_coords = None # New
        self.currency_display_area_coords = None # New for currency area
        self.merchant_shop_area_coords = None # New for merchant shop area
        self.currency_worker = None # New for currency screenshot worker
        
        # Initialize config
        self.config = Config(self)
        self.config.load()
        
        # Load teleport_coords from config
        if hasattr(self.config, 'teleport_coords') and self.config.teleport_coords:
            self.teleport_coords = self.config.teleport_coords
            print(f"Loaded teleport coords from config: {self.teleport_coords}")
        # Load other coords from config
        if hasattr(self.config, 'claw_skip_coords') and self.config.claw_skip_coords:
            self.claw_skip_coords = self.config.claw_skip_coords
            print(f"Loaded claw_skip_coords from config: {self.claw_skip_coords}")
        if hasattr(self.config, 'claw_claim_coords') and self.config.claw_claim_coords:
            self.claw_claim_coords = self.config.claw_claim_coords
            print(f"Loaded claw_claim_coords from config: {self.claw_claim_coords}")
        if hasattr(self.config, 'claw_start_coords') and self.config.claw_start_coords:
            self.claw_start_coords = self.config.claw_start_coords
            print(f"Loaded claw_start_coords from config: {self.claw_start_coords}")
        if hasattr(self.config, 'map_up_arrow_coords') and self.config.map_up_arrow_coords: # New
            self.map_up_arrow_coords = self.config.map_up_arrow_coords # New
            print(f"Loaded map_up_arrow_coords from config: {self.map_up_arrow_coords}") # New
        if hasattr(self.config, 'map_down_arrow_coords') and self.config.map_down_arrow_coords: # New
            self.map_down_arrow_coords = self.config.map_down_arrow_coords # New
            print(f"Loaded map_down_arrow_coords from config: {self.map_down_arrow_coords}") # New
        if hasattr(self.config, 'shop_item1_coords') and self.config.shop_item1_coords: # New
            self.shop_item1_coords = self.config.shop_item1_coords # New
            print(f"Loaded shop_item1_coords from config: {self.shop_item1_coords}") # New
        if hasattr(self.config, 'shop_item2_coords') and self.config.shop_item2_coords: # New
            self.shop_item2_coords = self.config.shop_item2_coords # New
            print(f"Loaded shop_item2_coords from config: {self.shop_item2_coords}") # New
        if hasattr(self.config, 'shop_item3_coords') and self.config.shop_item3_coords: # New
            self.shop_item3_coords = self.config.shop_item3_coords # New
            print(f"Loaded shop_item3_coords from config: {self.shop_item3_coords}") # New
        if hasattr(self.config, 'currency_display_area_coords') and self.config.currency_display_area_coords: # New
            self.currency_display_area_coords = self.config.currency_display_area_coords
            print(f"Loaded currency_display_area_coords from config: {self.currency_display_area_coords}")
        if hasattr(self.config, 'merchant_shop_area_coords') and self.config.merchant_shop_area_coords: # New
            self.merchant_shop_area_coords = self.config.merchant_shop_area_coords # New
            print(f"Loaded merchant_shop_area_coords from config: {self.merchant_shop_area_coords}") # New
        
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
        
        # Update calibration button text and path selector
        self.collection_manager.update_all_calibration_buttons_text()
        
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
        
        # Add the Automation tab (formerly Collection)
        self._build_automation_tab()
        
        # Add the Calibration tab
        self._build_calibration_tab()
        
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

        # Dice Chest ping settings
        self.dice_chest_ping_label = QLabel("Dice Chest Ping:")
        self.dice_chest_ping_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        pings_grid_layout.addWidget(self.dice_chest_ping_label, 2, 0)

        self.dice_chest_ping_entry = QLineEdit()
        self.dice_chest_ping_entry.setPlaceholderText("Enter User/Role ID (Optional)")
        pings_grid_layout.addWidget(self.dice_chest_ping_entry, 2, 1)

        self.dice_chest_ping_type_combo = QComboBox()
        self.dice_chest_ping_type_combo.addItem("User")
        self.dice_chest_ping_type_combo.addItem("Role")
        self.dice_chest_ping_type_combo.setFixedWidth(60) 
        pings_grid_layout.addWidget(self.dice_chest_ping_type_combo, 2, 2)

        # Silly Egg ping (fixed to @everyone)
        self.silly_egg_ping_label = QLabel("Silly Egg Ping:")
        self.silly_egg_ping_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        pings_grid_layout.addWidget(self.silly_egg_ping_label, 3, 0)

        self.silly_egg_ping_display = QLabel("<code>@everyone</code> (Cannot be changed)")
        self.silly_egg_ping_display.setTextFormat(Qt.TextFormat.RichText)
        pings_grid_layout.addWidget(self.silly_egg_ping_display, 3, 1, 1, 2)

        pings_grid_layout.setColumnStretch(1, 1)
        pings_layout.addLayout(pings_grid_layout) 
        
        # Separator before Currency Updates
        currency_separator = QFrame()
        currency_separator.setFrameShape(QFrame.Shape.HLine)
        currency_separator.setFrameShadow(QFrame.Shadow.Sunken)
        currency_separator.setMaximumHeight(5) # Make separator a bit thicker
        pings_layout.addWidget(currency_separator)

        # Currency Update Settings Section
        currency_title_label = QLabel("Currency Updates")
        currency_title_font = QFont("Segoe UI", 10) # Slightly smaller than main pings title
        currency_title_font.setBold(True)
        currency_title_label.setFont(currency_title_font)
        currency_title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        currency_title_label.setStyleSheet("margin-top: 10px;") # Add some top margin
        pings_layout.addWidget(currency_title_label)

        currency_grid_layout = QGridLayout()
        currency_grid_layout.setContentsMargins(10, 5, 10, 10) 
        currency_grid_layout.setSpacing(8)

        self.currency_updates_enabled_checkbox = QCheckBox("Enable Currency Updates")
        currency_grid_layout.addWidget(self.currency_updates_enabled_checkbox, 0, 0, 1, 2) # Span 2 columns

        self.currency_updates_delay_label = QLabel("Update Delay (minutes, 0 to disable):")
        self.currency_updates_delay_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        currency_grid_layout.addWidget(self.currency_updates_delay_label, 1, 0)

        self.currency_updates_delay_spinbox = QSpinBox()
        self.currency_updates_delay_spinbox.setMinimum(0) # 0 to disable
        self.currency_updates_delay_spinbox.setMaximum(1440) # Max 24 hours
        self.currency_updates_delay_spinbox.setValue(60) # Default 1 hour
        currency_grid_layout.addWidget(self.currency_updates_delay_spinbox, 1, 1)
        
        currency_grid_layout.setColumnStretch(1,1) # Ensure spinbox doesn't take all width
        pings_layout.addLayout(currency_grid_layout)

        pings_layout.addStretch()
        
    def _build_automation_tab(self):
        """Build the Automation tab UI"""
        self.automation_tab = QWidget()
        automation_layout = QVBoxLayout(self.automation_tab)
        automation_layout.setContentsMargins(15, 20, 15, 15)
        automation_layout.setSpacing(10)
        self.tab_widget.addTab(self.automation_tab, "Automation")

        automation_title_label = QLabel("Automation")
        automation_title_font = QFont("Segoe UI", 12)
        automation_title_font.setBold(True)
        automation_title_label.setFont(automation_title_font)
        automation_title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        automation_layout.addWidget(automation_title_label)

        # Automation settings
        self.automation_enabled_checkbox = QCheckBox("Enable Automation")
        automation_layout.addWidget(self.automation_enabled_checkbox)

        # Automation type selector
        automation_type_selector_label = QLabel("Select Automation Type:")
        automation_layout.addWidget(automation_type_selector_label)
        
        self.automation_type_selector_combo = QComboBox()
        automation_layout.addWidget(self.automation_type_selector_combo)
        
        self.spam_e_checkbox = QCheckBox("Open Cyber While Farming (Ticket Path Only - E Spam)")
        self.spam_e_checkbox.setChecked(self.config.spam_e_for_ticket_path if hasattr(self.config, 'spam_e_for_ticket_path') else False)
        self.spam_e_checkbox.stateChanged.connect(self.on_spam_e_checkbox_changed)
        self.spam_e_checkbox.setEnabled(False)
        automation_layout.addWidget(self.spam_e_checkbox)

        # New checkbox for Scheduled Merchant Run
        self.scheduled_merchant_run_checkbox = QCheckBox("Enable Scheduled Merchant Run (1.5hr interval, excludes Claw)")
        self.scheduled_merchant_run_checkbox.stateChanged.connect(self.on_scheduled_merchant_run_checkbox_changed)
        automation_layout.addWidget(self.scheduled_merchant_run_checkbox)
        
        self.update_automation_type_selector()
        
        # Collection tutorial link (keeping link, maybe update text later if a general automation tutorial exists)
        automation_tutorial_label = QLabel(
            'Automation Tutorial (General Pathing): <a href="https://www.youtube.com/watch?v=YOQQR3n8VE4">Watch Video</a>'
        )
        automation_tutorial_label.setTextFormat(Qt.TextFormat.RichText)
        automation_tutorial_label.setOpenExternalLinks(True)
        automation_tutorial_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        automation_layout.addWidget(automation_tutorial_label)

        # New Claw Machine tutorial link
        claw_machine_tutorial_label = QLabel(
            'Claw Machine Tutorial: <a href="https://www.youtube.com/watch?v=bnbvw2WFOO4">Watch Video</a>'
        )
        claw_machine_tutorial_label.setTextFormat(Qt.TextFormat.RichText)
        claw_machine_tutorial_label.setOpenExternalLinks(True)
        claw_machine_tutorial_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        automation_layout.addWidget(claw_machine_tutorial_label)

        # New informational message for auto open cyber egg
        info_cyber_egg_label = QLabel(
            "When auto open cyber egg is enabled sometimes cutscenes will make your character freeze then mess up that macro path, do not worry just wait and the macro will eventually self correct."
        )
        info_cyber_egg_label.setStyleSheet("color: #aaaaaa; font-size: 8pt;") # Grey color, smaller font
        info_cyber_egg_label.setWordWrap(True)
        info_cyber_egg_label.setAlignment(Qt.AlignmentFlag.AlignCenter) # Or Qt.AlignmentFlag.AlignLeft if preferred
        automation_layout.addWidget(info_cyber_egg_label)

        automation_layout.addStretch()
        
    def _build_calibration_tab(self):
        """Build the Calibration tab UI"""
        self.calibration_tab = QWidget()
        calibration_layout = QVBoxLayout(self.calibration_tab)
        calibration_layout.setContentsMargins(0, 0, 0, 0)
        calibration_layout.setSpacing(0)
        self.tab_widget.addTab(self.calibration_tab, "Calibration")

        # Create scroll area
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll_area.setStyleSheet("QScrollArea { border: none; }")
        
        # Create container widget for scroll area
        scroll_content = QWidget()
        content_layout = QGridLayout(scroll_content)
        content_layout.setContentsMargins(10, 10, 10, 10)
        content_layout.setSpacing(6)

        # Create section title font - smaller than before
        title_font = QFont("Segoe UI", 10)
        title_font.setBold(True)

        # Row counter
        row = 0

        # --- Teleport Button Calibration ---
        teleport_title = QLabel("Teleport Button")
        teleport_title.setFont(title_font)
        content_layout.addWidget(teleport_title, row, 0, 1, 2)
        row += 1

        self.calibrate_button = QPushButton()
        self.calibrate_button.setStyleSheet(button_stylesheet.format(
             bg_color="#43b581", fg_color="white", hover_bg_color="#3ca374", pressed_bg_color="#359066"
        ))
        self.calibrate_button.clicked.connect(self.collection_manager.start_calibration)
        content_layout.addWidget(self.calibrate_button, row, 0)
        
        self.calibrate_coords_label = QLabel("")
        self.calibrate_coords_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.calibrate_coords_label.setStyleSheet("font-size: 8pt; color: #aaa;")
        content_layout.addWidget(self.calibrate_coords_label, row, 1)
        row += 1
        
        # Separator
        separator1 = QFrame()
        separator1.setFrameShape(QFrame.Shape.HLine)
        separator1.setFrameShadow(QFrame.Shadow.Sunken)
        separator1.setMaximumHeight(1)
        content_layout.addWidget(separator1, row, 0, 1, 2)
        row += 1

        # --- Claw Machine Calibration ---
        claw_title = QLabel("Claw Machine")
        claw_title.setFont(title_font)
        content_layout.addWidget(claw_title, row, 0, 1, 2)
        row += 1

        # Claw Skip
        self.calibrate_claw_skip_button = QPushButton()
        self.calibrate_claw_skip_button.setStyleSheet(button_stylesheet.format(
             bg_color="#5865F2", fg_color="white", hover_bg_color="#4752C4", pressed_bg_color="#3C45A5"
        ))
        self.calibrate_claw_skip_button.clicked.connect(self.collection_manager.start_claw_skip_calibration)
        content_layout.addWidget(self.calibrate_claw_skip_button, row, 0)
        
        self.claw_skip_coords_label = QLabel("")
        self.claw_skip_coords_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.claw_skip_coords_label.setStyleSheet("font-size: 8pt; color: #aaa;")
        content_layout.addWidget(self.claw_skip_coords_label, row, 1)
        row += 1

        # Claw Claim
        self.calibrate_claw_claim_button = QPushButton()
        self.calibrate_claw_claim_button.setStyleSheet(button_stylesheet.format(
             bg_color="#5865F2", fg_color="white", hover_bg_color="#4752C4", pressed_bg_color="#3C45A5"
        ))
        self.calibrate_claw_claim_button.clicked.connect(self.collection_manager.start_claw_claim_calibration)
        content_layout.addWidget(self.calibrate_claw_claim_button, row, 0)
        
        self.claw_claim_coords_label = QLabel("")
        self.claw_claim_coords_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.claw_claim_coords_label.setStyleSheet("font-size: 8pt; color: #aaa;")
        content_layout.addWidget(self.claw_claim_coords_label, row, 1)
        row += 1

        # Claw Start
        self.calibrate_claw_start_button = QPushButton()
        self.calibrate_claw_start_button.setStyleSheet(button_stylesheet.format(
             bg_color="#5865F2", fg_color="white", hover_bg_color="#4752C4", pressed_bg_color="#3C45A5"
        ))
        self.calibrate_claw_start_button.clicked.connect(self.collection_manager.start_claw_start_calibration)
        content_layout.addWidget(self.calibrate_claw_start_button, row, 0)
        
        self.claw_start_coords_label = QLabel("")
        self.claw_start_coords_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.claw_start_coords_label.setStyleSheet("font-size: 8pt; color: #aaa;")
        content_layout.addWidget(self.claw_start_coords_label, row, 1)
        row += 1

        # Separator
        separator2 = QFrame()
        separator2.setFrameShape(QFrame.Shape.HLine)
        separator2.setFrameShadow(QFrame.Shadow.Sunken)
        separator2.setMaximumHeight(1)
        content_layout.addWidget(separator2, row, 0, 1, 2)
        row += 1

        # --- Map Arrow Calibration ---
        map_title = QLabel("Map Arrows")
        map_title.setFont(title_font)
        content_layout.addWidget(map_title, row, 0, 1, 2)
        row += 1

        # Map Up Arrow
        self.calibrate_map_up_arrow_button = QPushButton()
        self.calibrate_map_up_arrow_button.setStyleSheet(button_stylesheet.format(
             bg_color="#5865F2", fg_color="white", hover_bg_color="#4752C4", pressed_bg_color="#3C45A5"
        ))
        self.calibrate_map_up_arrow_button.clicked.connect(self.collection_manager.start_map_up_arrow_calibration)
        content_layout.addWidget(self.calibrate_map_up_arrow_button, row, 0)
        
        self.map_up_arrow_coords_label = QLabel("")
        self.map_up_arrow_coords_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.map_up_arrow_coords_label.setStyleSheet("font-size: 8pt; color: #aaa;")
        content_layout.addWidget(self.map_up_arrow_coords_label, row, 1)
        row += 1

        # Map Down Arrow
        self.calibrate_map_down_arrow_button = QPushButton()
        self.calibrate_map_down_arrow_button.setStyleSheet(button_stylesheet.format(
             bg_color="#5865F2", fg_color="white", hover_bg_color="#4752C4", pressed_bg_color="#3C45A5"
        ))
        self.calibrate_map_down_arrow_button.clicked.connect(self.collection_manager.start_map_down_arrow_calibration)
        content_layout.addWidget(self.calibrate_map_down_arrow_button, row, 0)
        
        self.map_down_arrow_coords_label = QLabel("")
        self.map_down_arrow_coords_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.map_down_arrow_coords_label.setStyleSheet("font-size: 8pt; color: #aaa;")
        content_layout.addWidget(self.map_down_arrow_coords_label, row, 1)
        row += 1

        # Separator for Shop Items
        separator3 = QFrame()
        separator3.setFrameShape(QFrame.Shape.HLine)
        separator3.setFrameShadow(QFrame.Shadow.Sunken)
        separator3.setMaximumHeight(1)
        content_layout.addWidget(separator3, row, 0, 1, 2)
        row += 1

        # --- Shop Item Calibration ---
        shop_title = QLabel("Shop Items")
        shop_title.setFont(title_font)
        content_layout.addWidget(shop_title, row, 0, 1, 2)
        row += 1

        # Shop Item 1
        self.calibrate_shop_item1_button = QPushButton("Calibrate Shop Item 1")
        self.calibrate_shop_item1_button.setStyleSheet(button_stylesheet.format(
             bg_color="#5865F2", fg_color="white", hover_bg_color="#4752C4", pressed_bg_color="#3C45A5"
        ))
        self.calibrate_shop_item1_button.clicked.connect(self.collection_manager.start_shop_item1_calibration)
        content_layout.addWidget(self.calibrate_shop_item1_button, row, 0)
        
        self.shop_item1_coords_label = QLabel("")
        self.shop_item1_coords_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.shop_item1_coords_label.setStyleSheet("font-size: 8pt; color: #aaa;")
        content_layout.addWidget(self.shop_item1_coords_label, row, 1)
        row += 1

        # Shop Item 2
        self.calibrate_shop_item2_button = QPushButton("Calibrate Shop Item 2")
        self.calibrate_shop_item2_button.setStyleSheet(button_stylesheet.format(
             bg_color="#5865F2", fg_color="white", hover_bg_color="#4752C4", pressed_bg_color="#3C45A5"
        ))
        self.calibrate_shop_item2_button.clicked.connect(self.collection_manager.start_shop_item2_calibration)
        content_layout.addWidget(self.calibrate_shop_item2_button, row, 0)
        
        self.shop_item2_coords_label = QLabel("")
        self.shop_item2_coords_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.shop_item2_coords_label.setStyleSheet("font-size: 8pt; color: #aaa;")
        content_layout.addWidget(self.shop_item2_coords_label, row, 1)
        row += 1

        # Shop Item 3
        self.calibrate_shop_item3_button = QPushButton("Calibrate Shop Item 3")
        self.calibrate_shop_item3_button.setStyleSheet(button_stylesheet.format(
             bg_color="#5865F2", fg_color="white", hover_bg_color="#4752C4", pressed_bg_color="#3C45A5"
        ))
        self.calibrate_shop_item3_button.clicked.connect(self.collection_manager.start_shop_item3_calibration)
        content_layout.addWidget(self.calibrate_shop_item3_button, row, 0)
        
        self.shop_item3_coords_label = QLabel("")
        self.shop_item3_coords_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.shop_item3_coords_label.setStyleSheet("font-size: 8pt; color: #aaa;")
        content_layout.addWidget(self.shop_item3_coords_label, row, 1)
        row += 1

        # Separator for Currency Area Calibration
        separator_currency = QFrame()
        separator_currency.setFrameShape(QFrame.Shape.HLine)
        separator_currency.setFrameShadow(QFrame.Shadow.Sunken)
        separator_currency.setMaximumHeight(1)
        content_layout.addWidget(separator_currency, row, 0, 1, 2)
        row += 1

        # --- Currency Display Area Calibration ---
        currency_area_title = QLabel("Currency Display Area")
        currency_area_title.setFont(title_font)
        content_layout.addWidget(currency_area_title, row, 0, 1, 2)
        row += 1

        self.calibrate_currency_area_button = QPushButton()
        self.calibrate_currency_area_button.setStyleSheet(button_stylesheet.format(
             bg_color="#FEE75C", fg_color="#303136", hover_bg_color="#E0CD4F", pressed_bg_color="#C7B444" # Yellowish
        ))
        self.calibrate_currency_area_button.clicked.connect(self.collection_manager.start_currency_area_calibration)
        content_layout.addWidget(self.calibrate_currency_area_button, row, 0)
        
        self.currency_area_coords_label = QLabel("")
        self.currency_area_coords_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.currency_area_coords_label.setStyleSheet("font-size: 8pt; color: #aaa;")
        content_layout.addWidget(self.currency_area_coords_label, row, 1)
        row += 1

        # Separator for Merchant Shop Area Calibration
        separator_merchant_shop = QFrame()
        separator_merchant_shop.setFrameShape(QFrame.Shape.HLine)
        separator_merchant_shop.setFrameShadow(QFrame.Shadow.Sunken)
        separator_merchant_shop.setMaximumHeight(1)
        content_layout.addWidget(separator_merchant_shop, row, 0, 1, 2)
        row += 1

        # --- Merchant Shop Area Calibration --- New Section
        merchant_shop_area_title = QLabel("Merchant Shop Area (for Screenshots)")
        merchant_shop_area_title.setFont(title_font)
        content_layout.addWidget(merchant_shop_area_title, row, 0, 1, 2)
        row += 1

        self.calibrate_merchant_shop_area_button = QPushButton()
        self.calibrate_merchant_shop_area_button.setStyleSheet(button_stylesheet.format(
             bg_color="#ED4245", fg_color="white", hover_bg_color="#D03F41", pressed_bg_color="#B7383A" # Reddish
        ))
        self.calibrate_merchant_shop_area_button.clicked.connect(self.collection_manager.start_merchant_shop_area_calibration)
        content_layout.addWidget(self.calibrate_merchant_shop_area_button, row, 0)
        
        self.merchant_shop_area_coords_label = QLabel("")
        self.merchant_shop_area_coords_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.merchant_shop_area_coords_label.setStyleSheet("font-size: 8pt; color: #aaa;")
        content_layout.addWidget(self.merchant_shop_area_coords_label, row, 1)
        row += 1

        # Set column stretch to make the grid more responsive
        content_layout.setColumnStretch(0, 1)
        content_layout.setColumnStretch(1, 1)

        # Set the scroll area widget
        scroll_area.setWidget(scroll_content)
        
        # Add scroll area to main layout
        calibration_layout.addWidget(scroll_area)
        
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

        self.hatch_secret_ping_checkbox = QCheckBox("Secret Hatch Ping (DM)")
        hatch_layout.addWidget(self.hatch_secret_ping_checkbox)

        self.hatch_userid_label = QLabel("User ID to Ping:")
        hatch_layout.addWidget(self.hatch_userid_label)
        self.hatch_userid_entry = QLineEdit()
        self.hatch_userid_entry.setPlaceholderText("Enter User ID for DM")
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

        # Add a separator
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setFrameShadow(QFrame.Shadow.Sunken)
        separator.setMaximumHeight(1)
        credits_layout.addWidget(separator)

        # Add Contributors section
        contributors_title = QLabel("Contributors")
        contributors_title_font = QFont("Segoe UI", 11)
        contributors_title_font.setBold(True)
        contributors_title.setFont(contributors_title_font)
        contributors_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        credits_layout.addWidget(contributors_title)

        digital_label = QLabel("<b>Digital:</b> Creator of detection, pathing, and some of UI")
        digital_label.setTextFormat(Qt.TextFormat.RichText) 
        digital_label.setWordWrap(True)
        credits_layout.addWidget(digital_label)

        manas_label = QLabel("<b>Manas:</b> Path Creation")
        manas_label.setTextFormat(Qt.TextFormat.RichText) 
        manas_label.setWordWrap(True)
        credits_layout.addWidget(manas_label)

        credits_layout.addStretch()

    def update_status(self, message):
        """Update the status in the log console"""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        formatted_log_message = f"[{timestamp}] {message}"

        if hasattr(self, 'log_console'):
            try:
                # Attempt to append to the log console only if it's a valid widget
                if self.log_console: # Basic check, RuntimeError will catch C++ deletion
                    self.log_console.append(formatted_log_message)
                    self.log_console.ensureCursorVisible() 
            except RuntimeError as e:
                # This error occurs if the C++ part of the widget has been deleted (e.g., during shutdown)
                if "deleted" in str(e).lower():
                    print(f"(UI Log Console unavailable: {e}) {formatted_log_message}")
                else:
                    # Re-raise if it's a different RuntimeError
                    print(f"(UI Log Console unexpected RuntimeError: {e}) {formatted_log_message}")
                    # Depending on desired behavior, you might re-raise e here
            except Exception as e:
                # Catch any other unexpected errors during UI update
                print(f"(UI Log Console general error: {e}) {formatted_log_message}")

        # Always print to the actual system console
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
        
    def send_webhook(self, title, description, image_url=None, color=0x7289DA, ping_content=None, file_path=None, worker_instance=None):
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

        if image_url and not file_path: # Only use image_url in embed if not sending a file
            embed["thumbnail"] = {"url": image_url}

        server_link = ""
        if hasattr(self, 'server_mode_combo'):
            server_mode = self.server_mode_combo.currentText()
            if server_mode == "Private Server":
                server_link = self.pslink_entry.text().strip()
            elif server_mode == "Public Server" and hasattr(self, 'detector') and self.detector.current_job_id:
                job_id = self.detector.current_job_id
                current_link = self.pslink_entry.text().strip()
                if current_link and current_link.startswith("http") and "ro.pro" in current_link:
                    server_link = current_link
                else:
                    try:
                        api_url = f"https://api.ropro.io/createInvite.php?universeid=6504986360&serverid={job_id}"
                        response_link = requests.get(api_url, timeout=5)
                        if response_link.status_code == 200 and response_link.text.strip().startswith("http"):
                            server_link = response_link.text.strip()
                            self.pslink_entry.setText(server_link)
                        else:
                            server_link = api_url
                    except Exception:
                        server_link = f"https://api.ropro.io/createInvite.php?universeid=6504986360&serverid={job_id}"
        
        if server_link:
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

        files_to_send = None
        response = None
        try:
            if file_path and os.path.exists(file_path):
                files_to_send = {'file': (os.path.basename(file_path), open(file_path, 'rb'), 'image/png')}
                response = requests.post(webhook_url, data={'payload_json': json.dumps(payload)}, files=files_to_send, timeout=15)
            else:
                response = requests.post(webhook_url, json=payload, timeout=10)
            
            response.raise_for_status() # This will raise an HTTPError if the HTTP request returned an unsuccessful status code
            # If we reach here, the webhook was sent successfully (or at least the request was accepted)
            # Proceed to delete the file if it was a currency screenshot
            if file_path and (("currency_" in os.path.basename(file_path)) or ("merchant_" in os.path.basename(file_path))) and files_to_send:
                try:
                    # Ensure file is closed before attempting to delete
                    if files_to_send and 'file' in files_to_send and files_to_send['file'] and hasattr(files_to_send['file'][1], 'close'):
                        files_to_send['file'][1].close() 
                        # Now that it's closed and (presumably) sent, delete it
                        os.remove(file_path)
                        self.update_status(f"Deleted screenshot: {file_path}")
                        # Set files_to_send to None after closing and deleting to prevent re-closing in finally
                        files_to_send = None 
                except Exception as e_delete:
                    self.update_status(f"Error deleting screenshot {file_path}: {e_delete}")
                    print(f"Error deleting screenshot {file_path}: {e_delete}")

        except requests.exceptions.RequestException as e: # More specific exception for requests
            error_message = f"Webhook request error: {e} (URL: {webhook_url[:30]}...)"
            print(error_message)
            if worker_instance and hasattr(worker_instance, 'update_status_signal'):
                worker_instance.update_status_signal.emit(error_message)
            elif not worker_instance:
                self.update_status(error_message)
        except Exception as e: # General fallback
            error_message = f"Webhook error (general): {e} (URL: {webhook_url[:30]}...)"
            print(error_message)
            if worker_instance and hasattr(worker_instance, 'update_status_signal'):
                worker_instance.update_status_signal.emit(error_message)
            elif not worker_instance:
                self.update_status(error_message)
        finally:
            if files_to_send and 'file' in files_to_send and files_to_send['file'] and hasattr(files_to_send['file'][1], 'close'):
                try:
                    files_to_send['file'][1].close()
                    # Optional: Clean up the screenshot if desired - MOVED specific deletion logic into try block after successful send
                    # if "currency_" in file_path: os.remove(file_path) 
                except Exception as e_close:
                    print(f"Error closing screenshot file: {e_close}")
    
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
        self.dice_chest_ping_entry.setEnabled(False)
        self.dice_chest_ping_type_combo.setEnabled(False)
        self.automation_enabled_checkbox.setEnabled(False)
        self.calibrate_button.setEnabled(False)
        if hasattr(self, 'calibrate_claw_skip_button'): self.calibrate_claw_skip_button.setEnabled(False)
        if hasattr(self, 'calibrate_claw_claim_button'): self.calibrate_claw_claim_button.setEnabled(False)
        if hasattr(self, 'calibrate_claw_start_button'): self.calibrate_claw_start_button.setEnabled(False)
        if hasattr(self, 'calibrate_map_up_arrow_button'): self.calibrate_map_up_arrow_button.setEnabled(False)
        if hasattr(self, 'calibrate_map_down_arrow_button'): self.calibrate_map_down_arrow_button.setEnabled(False)
        if hasattr(self, 'calibrate_shop_item1_button'): self.calibrate_shop_item1_button.setEnabled(False)
        if hasattr(self, 'calibrate_shop_item2_button'): self.calibrate_shop_item2_button.setEnabled(False)
        if hasattr(self, 'calibrate_shop_item3_button'): self.calibrate_shop_item3_button.setEnabled(False)
        if hasattr(self, 'calibrate_currency_area_button'): self.calibrate_currency_area_button.setEnabled(False)
        if hasattr(self, 'calibrate_merchant_shop_area_button'): self.calibrate_merchant_shop_area_button.setEnabled(False)
        self.hatch_detection_enabled_checkbox.setEnabled(False) 
        self.hatch_username_entry.setEnabled(False)
        self.hatch_secret_ping_checkbox.setEnabled(False)
        self.hatch_userid_entry.setEnabled(False)
        self.server_mode_combo.setEnabled(False)
        self.automation_type_selector_combo.setEnabled(False)
        self.spam_e_checkbox.setEnabled(False)
        self.scheduled_merchant_run_checkbox.setEnabled(False)
        self.currency_updates_enabled_checkbox.setEnabled(False)
        self.currency_updates_delay_spinbox.setEnabled(False)

        self.update_status("🤖 Macro started.")
        self.config.save()

        # Start automation if enabled (formerly collection)
        if self.automation_enabled_checkbox.isChecked():
            # Reset merchant run flags and timer before starting automation
            self.collection_manager.initial_macro_merchant_run_done = False
            self.collection_manager.last_merchant_run_time = time.monotonic() # Reset timer

            if PYNPUT_AVAILABLE:
                try:
                    keyboard_controller = pynput_keyboard.Controller()
                    self.update_status("🤖 Automation pre-sequence: Pressing M...")
                    keyboard_controller.press('m')
                    keyboard_controller.release('m')
                    time.sleep(1) # Wait 1 second after M
                    self.update_status("🤖 Automation pre-sequence finished.")
                    time.sleep(2) # New: Wait an additional 2 seconds

                except Exception as e:
                    self.update_status(f"❌ Error during automation pre-sequence: {e}")
            else:
                self.update_status("⚠️ PYNPUT not available. Skipping automation pre-sequence key presses.")

            self.automation_enabled = True
            self.collection_manager.initial_navigation_complete_for_session = False # New: Reset flag
            if self.teleport_coords or self.collection_manager.current_path == 'clawmachine': # Allow clawmachine path without teleport coords for now
                self.update_status("🏁 Automation enabled. Starting worker...")
                self.collection_running = True
                self.collection_manager.collection_worker = Worker(self.collection_manager.run_collection_loop)
                self.collection_manager.collection_worker.update_status_signal.connect(self.update_status)
                self.collection_manager.collection_worker.start()
            else:
                self.update_status("⚠️ Automation enabled, but teleport button not calibrated (required for non-Claw Machine paths). Skipping automation.")
                QMessageBox.warning(self, "Automation Warning",
                                   "Automation is enabled, but the teleport button position hasn't been calibrated.\n"
                                   "This is required for paths that use teleport. Please calibrate if needed.")
        else:
            self.automation_enabled = False
            
        # Start Currency Screenshot Worker if enabled
        if PIL_AVAILABLE and self.config.currency_updates_enabled and self.config.currency_updates_delay_minutes > 0 and self.config.currency_display_area_coords:
            if not self.currency_worker or not self.currency_worker.isRunning():
                self.update_status("Attempting to start Currency Screenshot Worker...")
                self.currency_worker = CurrencyScreenshotWorker(self)
                self.currency_worker.update_status_signal.connect(self.update_status)
                self.currency_worker.send_webhook_signal.connect(self.send_webhook) # Connect its webhook signal
                self.currency_worker.start()
            else:
                self.update_status("Currency Screenshot Worker already running or PIL not available.")
        elif self.config.currency_updates_enabled: # Reason for not starting if enabled
            if not PIL_AVAILABLE:
                self.update_status("Currency updates enabled, but Pillow (PIL) is not installed. Cannot start screenshot worker.")
            elif not self.config.currency_display_area_coords:
                self.update_status("Currency updates enabled, but display area not calibrated. Cannot start screenshot worker.")
            elif self.config.currency_updates_delay_minutes <= 0:
                self.update_status("Currency updates enabled, but delay is 0. Screenshot worker will not run.")

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

        # Stop Currency Screenshot Worker if running
        if self.currency_worker and self.currency_worker.isRunning():
            self.update_status("Stopping Currency Screenshot Worker...")
            self.currency_worker.stop()
            if not self.currency_worker.wait(2000): # Wait up to 2 seconds
                self.update_status("Currency Screenshot Worker did not stop gracefully, terminating.")
                self.currency_worker.terminate()
            self.currency_worker = None

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
        self.dice_chest_ping_entry.setEnabled(True)
        self.dice_chest_ping_type_combo.setEnabled(True)
        self.automation_enabled_checkbox.setEnabled(True)
        self.calibrate_button.setEnabled(True)
        if hasattr(self, 'calibrate_claw_skip_button'): self.calibrate_claw_skip_button.setEnabled(True)
        if hasattr(self, 'calibrate_claw_claim_button'): self.calibrate_claw_claim_button.setEnabled(True)
        if hasattr(self, 'calibrate_claw_start_button'): self.calibrate_claw_start_button.setEnabled(True)
        if hasattr(self, 'calibrate_map_up_arrow_button'): self.calibrate_map_up_arrow_button.setEnabled(True)
        if hasattr(self, 'calibrate_map_down_arrow_button'): self.calibrate_map_down_arrow_button.setEnabled(True)
        if hasattr(self, 'calibrate_shop_item1_button'): self.calibrate_shop_item1_button.setEnabled(True)
        if hasattr(self, 'calibrate_shop_item2_button'): self.calibrate_shop_item2_button.setEnabled(True)
        if hasattr(self, 'calibrate_shop_item3_button'): self.calibrate_shop_item3_button.setEnabled(True)
        if hasattr(self, 'calibrate_currency_area_button'): self.calibrate_currency_area_button.setEnabled(True)
        if hasattr(self, 'calibrate_merchant_shop_area_button'): self.calibrate_merchant_shop_area_button.setEnabled(True)
        self.hatch_detection_enabled_checkbox.setEnabled(True) 
        self.hatch_username_entry.setEnabled(True)
        self.hatch_secret_ping_checkbox.setEnabled(True)
        self.hatch_userid_entry.setEnabled(True)
        self.server_mode_combo.setEnabled(True)
        self.automation_type_selector_combo.setEnabled(True)
        self.on_automation_type_selected(self.automation_type_selector_combo.currentIndex())
        
        self.currency_updates_enabled_checkbox.setEnabled(True)
        self.currency_updates_delay_spinbox.setEnabled(True)
        
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

        # Stop currency worker on close if running
        if self.currency_worker and self.currency_worker.isRunning():
            self.update_status("Stopping Currency Screenshot Worker on exit...")
            self.currency_worker.stop()
            self.currency_worker.wait(1000) # Shorter wait on exit
            self.currency_worker = None

        # Save configuration before exiting
        if hasattr(self, 'config') and self.config:
            self.update_status("Saving configuration before exiting...")
            self.config.save()

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
        except AttributeError: # Add this to handle cases where key might not have .name or similar
            pass # Can occur for special keys or if key is None
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
        
        if show_popup and not self.initializing and mode == "Public Server" and index == 1:
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
            
            if hasattr(self, 'detector') and self.detector.current_job_id:
                job_id = self.detector.current_job_id
                truncated_id = job_id[:8] + "..." if len(job_id) > 8 else job_id
                self.server_status.setText(f"Current Server: {truncated_id}")
                self.update_status("Fetching shortened server link...")
                api_url = f"https://api.ropro.io/createInvite.php?universeid=6504986360&serverid={job_id}"
                self.pslink_entry.setText(api_url)
                self._fetch_and_display_url(job_id)
                try:
                    if hasattr(self, '_fetch_short_link_worker') and self._fetch_short_link_worker and self._fetch_short_link_worker.isRunning():
                        self._fetch_short_link_worker.wait(100)  
                    self._fetch_short_link_worker = Worker(self._fetch_short_link, job_id)
                    self._fetch_short_link_worker.start()
                except Exception as e:
                    self.update_status(f"Error starting link fetch worker: {str(e)}")
                self.update_status(f"Current Public Server: JobID={job_id}")
            else:
                self.server_status.setText("No server detected yet")
                self.pslink_entry.clear()
                
        if hasattr(self, 'config'):
            self.config.save()
            
    def _fetch_and_display_url(self, job_id):
        """Directly fetch and display the URL - sync version for immediate feedback"""
        try:
            api_url = f"https://api.ropro.io/createInvite.php?universeid=6504986360&serverid={job_id}"
            self.pslink_entry.setText(api_url)
            
            response = requests.get(api_url, timeout=10)
            if response.status_code == 200 and response.text.strip().startswith("http"):
                short_url = response.text.strip()
                self.pslink_entry.setText(short_url)
                self.update_status(f"✅ Got RoPro URL from API: {short_url}")
            else:
                self.update_status(f"API returned status {response.status_code}: {response.text[:100]}")
        except Exception as e:
            self.update_status(f"Error fetching RoPro URL: {str(e)}")
            
    def _fetch_short_link(self, job_id):
        """Fetch the shortened ro.pro link from the RoPro API - used by the background worker"""
        try:
            api_url = f"https://api.ropro.io/createInvite.php?universeid=6504986360&serverid={job_id}"
            self.pslink_entry.setText(api_url)
            
            response = requests.get(api_url, timeout=10)
            if response.status_code == 200 and response.text.strip().startswith("http"):
                short_url = response.text.strip()
                self.pslink_entry.setText(short_url)
                self.update_status(f"✅ Worker: Got RoPro URL from API: {short_url}")
            else:
                self.update_status(f"Worker: API returned status {response.status_code}")
        except Exception as e:
            self.update_status(f"Error in worker URL fetch: {str(e)}")

    def update_path_selector(self):
        """Update the path selector dropdown with available paths"""
        if hasattr(self, 'automation_type_selector_combo') and hasattr(self.collection_manager, 'available_paths'):
            self.automation_type_selector_combo.clear()
            for path_id, path_data in self.collection_manager.available_paths.items():
                path_name = path_data.get('name', path_id)
                self.automation_type_selector_combo.addItem(path_name, path_id)
                
            if self.collection_manager.current_path:
                for i in range(self.automation_type_selector_combo.count()):
                    if self.automation_type_selector_combo.itemData(i) == self.collection_manager.current_path:
                        self.automation_type_selector_combo.setCurrentIndex(i)
                        break
            try:
                self.automation_type_selector_combo.currentIndexChanged.disconnect(self.on_automation_type_selected)
            except TypeError:
                pass 
            self.automation_type_selector_combo.currentIndexChanged.connect(self.on_automation_type_selected)

    def update_automation_type_selector(self):
        """Update the automation type selector dropdown with available paths."""
        if hasattr(self, 'automation_type_selector_combo') and hasattr(self.collection_manager, 'available_paths'):
            current_selection_id = None
            if self.automation_type_selector_combo.count() > 0 and self.automation_type_selector_combo.currentIndex() != -1:
                 current_selection_id = self.automation_type_selector_combo.itemData(self.automation_type_selector_combo.currentIndex())

            self.automation_type_selector_combo.blockSignals(True)
            self.automation_type_selector_combo.clear()

            allowed_path_ids = ['gem_path', 'clawmachine', 'ticket_grind_path']

            for path_id, path_data in self.collection_manager.available_paths.items():
                if path_id in allowed_path_ids: 
                    path_name = path_data.get('name', path_id) 
                    self.automation_type_selector_combo.addItem(path_name, path_id)
            
            target_path_to_select = current_selection_id if current_selection_id in allowed_path_ids and current_selection_id is not None else self.collection_manager.current_path
            
            if target_path_to_select not in allowed_path_ids and self.collection_manager.available_paths:
                if 'gem_path' in allowed_path_ids and 'gem_path' in self.collection_manager.available_paths:
                    target_path_to_select = 'gem_path'
                elif 'clawmachine' in allowed_path_ids and 'clawmachine' in self.collection_manager.available_paths:
                    target_path_to_select = 'clawmachine'
                elif 'ticket_grind_path' in allowed_path_ids and 'ticket_grind_path' in self.collection_manager.available_paths:
                    target_path_to_select = 'ticket_grind_path'
                elif self.automation_type_selector_combo.count() > 0: 
                     target_path_to_select = self.automation_type_selector_combo.itemData(0)
                else: 
                    target_path_to_select = None

            if target_path_to_select:
                for i in range(self.automation_type_selector_combo.count()):
                    if self.automation_type_selector_combo.itemData(i) == target_path_to_select:
                        self.automation_type_selector_combo.setCurrentIndex(i)
                        if self.collection_manager.current_path != target_path_to_select:
                            self.collection_manager.set_current_path(target_path_to_select)
                        break
            elif self.automation_type_selector_combo.count() > 0:
                self.automation_type_selector_combo.setCurrentIndex(0)
                new_path_id = self.automation_type_selector_combo.itemData(0)
                if new_path_id: 
                    self.collection_manager.set_current_path(new_path_id)

            self.automation_type_selector_combo.blockSignals(False)
            
            try:
                self.automation_type_selector_combo.currentIndexChanged.disconnect(self.on_automation_type_selected)
            except TypeError:
                pass 
            self.automation_type_selector_combo.currentIndexChanged.connect(self.on_automation_type_selected)
            
            if self.automation_type_selector_combo.count() > 0 :
                self.on_automation_type_selected(self.automation_type_selector_combo.currentIndex())
            
    def on_automation_type_selected(self, index):
        """Handle selection of an automation type from the dropdown."""
        path_id = self.automation_type_selector_combo.itemData(index)

        # Update E-spam checkbox enabled state based on path_id
        if hasattr(self, 'spam_e_checkbox'):
            if path_id == 'ticket_grind_path':
                self.spam_e_checkbox.setEnabled(True)
            else:
                self.spam_e_checkbox.setEnabled(False)
                self.spam_e_checkbox.setChecked(False) # Also uncheck if disabled
        
        # Update Scheduled Merchant Run checkbox enabled state based on path_id
        if hasattr(self, 'scheduled_merchant_run_checkbox') and hasattr(self.collection_manager, 'CLAW_MACHINE_PATH_ID'):
            if path_id == self.collection_manager.CLAW_MACHINE_PATH_ID:
                self.scheduled_merchant_run_checkbox.setEnabled(False)
            else:
                self.scheduled_merchant_run_checkbox.setEnabled(True)

        if index >= 0 and not self.initializing:
            if path_id and self.collection_manager.set_current_path(path_id):
                self.update_status(f"Selected automation type: {self.automation_type_selector_combo.currentText()}")

    def on_spam_e_checkbox_changed(self, state):
        """Handle state change of the spam_e_checkbox."""
        if not self.initializing and hasattr(self.config, 'spam_e_for_ticket_path'):
            is_checked = state == Qt.CheckState.Checked.value
            self.config.spam_e_for_ticket_path = is_checked
            self.config.save()
            self.update_status(f"Open Cyber While Farming set to: {is_checked}")

    def on_scheduled_merchant_run_checkbox_changed(self, state):
        """Handle state change of the scheduled_merchant_run_checkbox."""
        if not self.initializing and hasattr(self.config, 'enable_scheduled_merchant_run'):
            is_checked = state == Qt.CheckState.Checked.value
            self.config.enable_scheduled_merchant_run = is_checked
            self.config.save()
            self.update_status(f"Scheduled Merchant Run set to: {is_checked}")
