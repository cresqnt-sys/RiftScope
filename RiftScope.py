import os
import time
import json
import threading
import requests
import psutil
import sys  
import subprocess
import packaging.version
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                           QHBoxLayout, QLabel, QLineEdit, QPushButton, 
                           QFrame, QMessageBox, QStyleFactory, QTabWidget, 
                           QTextEdit) 
from PyQt6.QtGui import QPalette, QColor, QFont, QKeySequence, QShortcut, QIcon 
from PyQt6.QtCore import Qt, QThread, pyqtSignal 
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
    webhook_signal = pyqtSignal(str, str, str, int)

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

class FishstrapWatcherApp(QMainWindow):
    APP_VERSION = "1.0.0-Alpha" 
    REPO_URL = "cresqnt-sys/RiftScope"

    update_prompt_signal = pyqtSignal(str, str)

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
        self.build_ui()

        self.setup_keybinds()

        self.update_prompt_signal.connect(self.prompt_update)

        self.update_checker_worker = Worker(self.check_for_updates)

        self.update_checker_worker.start()

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

        self.status_label = QLabel("Ready to scan...")
        status_font = QFont("Segoe UI", 9)
        status_font.setItalic(True)
        self.status_label.setFont(status_font)
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        scanner_layout.addWidget(self.status_label)

        scanner_layout.addStretch() 

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

        cresqnt_label = QLabel("<b>cresqnt:</b> Macro maintainer")
        cresqnt_label.setTextFormat(Qt.TextFormat.RichText)
        cresqnt_label.setWordWrap(True)
        credits_layout.addWidget(cresqnt_label)

        digital_label = QLabel("<b>Digital:</b> Original macro creator")
        digital_label.setTextFormat(Qt.TextFormat.RichText) 
        digital_label.setWordWrap(True)
        credits_layout.addWidget(digital_label)

        credits_layout.addStretch() 

    def setup_keybinds(self):
        start_shortcut = QShortcut(QKeySequence(Qt.Key.Key_F1), self)
        stop_shortcut = QShortcut(QKeySequence(Qt.Key.Key_F2), self)

        start_shortcut.activated.connect(self.start_macro)
        stop_shortcut.activated.connect(self.stop_macro)

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

        self.status_label.setText(message) 

        if hasattr(self, 'log_console'):
            self.log_console.append(formatted_log_message)
            self.log_console.ensureCursorVisible() 

        print(formatted_log_message) 

    def load_config(self):
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r') as f:
                    config = json.load(f)
                    self.webhook_url = config.get('webhook_url', '')
                    self.ps_link = config.get('ps_link', '')

                    if hasattr(self, 'webhook_entry'):
                         self.webhook_entry.setText(self.webhook_url)
                    if hasattr(self, 'pslink_entry'):
                         self.pslink_entry.setText(self.ps_link)
            else:
                self.webhook_url = ''
                self.ps_link = ''
        except Exception as e:
            print(f"Error loading config: {e}")
            self.webhook_url = ''
            self.ps_link = ''

    def save_config(self):
        try:
            config_dir = os.path.dirname(self.config_file)
            os.makedirs(config_dir, exist_ok=True)

            config = {
                'webhook_url': self.webhook_entry.text().strip(), 
                'ps_link': self.pslink_entry.text().strip() 
            }
            with open(self.config_file, 'w') as f:
                json.dump(config, f, indent=4)
        except Exception as e:
            print(f"Error saving config: {e}")
            self.update_status(f"Error saving config: {e}")

    def get_log_dir(self):
        home = os.path.expanduser("~")
        log_dir = os.path.join(home, "AppData", "Local", "Fishstrap", "Logs")

        return log_dir

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

    def send_webhook(self, title, description, image_url=None, color=0x7289DA, worker_instance=None):

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
                0x7289DA
            )
        self.last_line_time = time.time()
        self.last_timestamp = None 
        self.processed_lines.clear() 

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

                    if "🔮" in line: 
                        if self.monitor_thread:
                            self.monitor_thread.update_status_signal.emit("✨ Royal chest detected!")
                            self.monitor_thread.webhook_signal.emit(
                                "✨ ROYAL CHEST DETECTED! ✨",
                                f"A royal chest has been found in the chat!", 
                                self.royal_image_url,
                                0x9b59b6
                            )

                    elif "aura" in line.lower(): 
                        if self.monitor_thread:
                            self.monitor_thread.update_status_signal.emit("🌟 Aura egg detected!")
                            self.monitor_thread.webhook_signal.emit(
                                "🌟 AURA EGG DETECTED! 🌟",
                                f"An aura egg has been found in the chat!", 
                                self.aura_image_url,
                                0x3498db
                            )

                    if timestamp:
                        self.last_timestamp = max(self.last_timestamp or 0, timestamp)

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
                                0xe74c3c
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
        self.update_status("🔍 Scanning started...")

    def stop_macro(self):
        if not self.running:
            return

        self.running = False 

        if self.monitor_thread and self.monitor_thread.isRunning():

             self.monitor_thread.wait(1000) 

        self.send_webhook(
            "⏹️ RiftScope Stopped",
            "RiftScope has been stopped manually.",
            None,
            0x95a5a6
        )

    def on_monitor_finished(self):
        self.running = False 
        self.monitor_thread = None 

        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.test_button.setEnabled(True)
        self.lock_button.setEnabled(True)
        self.webhook_entry.setEnabled(True)
        self.pslink_entry.setEnabled(True)
        self.update_status("Scanner stopped. Ready to scan again.")

    def closeEvent(self, event):
        if self.running:
            self.stop_macro() 

            if self.monitor_thread and self.monitor_thread.isRunning():
                self.monitor_thread.wait(500)

        if self.test_running and self.test_worker and self.test_worker.isRunning():
             self.test_running = False 
             self.test_worker.wait(500)

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
echo Waiting for RiftScope to close...
timeout /t 4 /nobreak > NUL
echo Replacing executable...

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

            self.update_status("Update downloaded. Restarting application to apply...")

            subprocess.Popen(['cmd.exe', '/c', updater_bat_path], 
                             creationflags=subprocess.CREATE_NEW_CONSOLE, 
                             close_fds=True) 

            QApplication.instance().quit()

        except requests.exceptions.RequestException as e:
            self.update_status(f"Update failed: Download error ({e})")
            print(f"Error downloading update: {e}")
        except IOError as e:
            self.update_status(f"Update failed: File error ({e})")
            print(f"Error writing update file or batch script: {e}")
        except Exception as e:
            self.update_status(f"Update failed: An unexpected error occurred ({e})")
            print(f"An unexpected error occurred during update process: {e}")

            if os.path.exists(new_exe_temp_path):
                try: os.remove(new_exe_temp_path) 
                except OSError: pass
            if os.path.exists(updater_bat_path):
                try: os.remove(updater_bat_path) 
                except OSError: pass

if __name__ == "__main__":
    app = QApplication(sys.argv)
    main_window = FishstrapWatcherApp()
    main_window.show()
    sys.exit(app.exec()) 