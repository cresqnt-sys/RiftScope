#!/usr/bin/env python3
# RiftScope Path Recorder - Record custom paths for RiftScope
# Standalone application for recording keyboard macros

import os
import json
import time
import threading
import sys
from datetime import datetime
import glob

try:
    from pynput import keyboard
    from pynput.keyboard import Key, KeyCode
    from pynput.keyboard import Controller as KeyboardController
except ImportError:
    print("ERROR: pynput module not found. Please install using: pip install pynput")
    sys.exit(1)

try:
    from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                              QHBoxLayout, QLabel, QPushButton, QTextEdit,
                              QFrame, QFileDialog, QLineEdit, QMessageBox,
                              QComboBox, QProgressBar)
    from PyQt6.QtCore import Qt, pyqtSignal, QThread, QEvent
    from PyQt6.QtGui import QFont, QColor, QPalette
except ImportError:
    print("ERROR: PyQt6 not found. Please install using: pip install PyQt6")
    sys.exit(1)

# Path where recorded paths will be saved
DEFAULT_PATHS_DIR = "Paths"

# Mapping from our string representations back to pynput Keys
SPECIAL_KEY_MAP_REVERSE = {
    'shift': Key.shift, 'shift_r': Key.shift_r,
    'ctrl': Key.ctrl, 'ctrl_l': Key.ctrl_l, 'ctrl_r': Key.ctrl_r,
    'alt': Key.alt, 'alt_l': Key.alt_l, 'alt_r': Key.alt_r,
    'cmd': Key.cmd, 'cmd_l': Key.cmd_l, 'cmd_r': Key.cmd_r,
    'enter': Key.enter,
    'backspace': Key.backspace,
    'tab': Key.tab,
    'space': Key.space,
    'delete': Key.delete,
    'insert': Key.insert,
    'home': Key.home,
    'end': Key.end,
    'page_up': Key.page_up,
    'page_down': Key.page_down,
    'up': Key.up,
    'down': Key.down,
    'left': Key.left,
    'right': Key.right,
    'caps_lock': Key.caps_lock,
    'num_lock': Key.num_lock,
    'print_screen': Key.print_screen,
    'scroll_lock': Key.scroll_lock,
    'pause': Key.pause,
    # Map numpad strings back to KeyCode objects (vk codes)
    'num_0': KeyCode(vk=96), 'num_1': KeyCode(vk=97), 'num_2': KeyCode(vk=98),
    'num_3': KeyCode(vk=99), 'num_4': KeyCode(vk=100), 'num_5': KeyCode(vk=101),
    'num_6': KeyCode(vk=102), 'num_7': KeyCode(vk=103), 'num_8': KeyCode(vk=104),
    'num_9': KeyCode(vk=105),
    'num_*': KeyCode(vk=106), 'num_+': KeyCode(vk=107), 'num_-': KeyCode(vk=109),
    'num_.': KeyCode(vk=110), 'num_/': KeyCode(vk=111),
}

class RecordThread(QThread):
    """Thread for recording keystrokes - Records raw press/release events."""
    update_signal = pyqtSignal(str, str) # Signal for logging raw events: char, type ('press'/'release')
    finished_signal = pyqtSignal(list) # Emits the raw event list
    
    def __init__(self):
        super().__init__()
        self.recording = False
        self.raw_events = []
        self.start_time_ns = None
        # Keep track of currently pressed modifier keys to avoid redundant events
        self.pressed_modifiers = set()
    
    def get_key_representation(self, key_event):
        """Gets a consistent string representation for a key event."""
        # --- Escape Key (Special handling if needed, but excluded by caller now) ---
        # if key_event == Key.esc: return 'esc' 
        
        # --- Function Keys (F1-F12) --- 
        # Check if it's a Key object and if its name matches f1-f12 pattern
        if isinstance(key_event, Key) and key_event.name.startswith('f') and key_event.name[1:].isdigit():
             f_num = int(key_event.name[1:])
             if 1 <= f_num <= 12:
                 return None # Ignore function keys F1-F12
        
        # --- Special Keys (Mapped to string names) ---
        special_keys_map = {
            Key.shift: 'shift', Key.shift_r: 'shift_r',
            Key.ctrl: 'ctrl', Key.ctrl_l: 'ctrl_l', Key.ctrl_r: 'ctrl_r',
            Key.alt: 'alt', Key.alt_l: 'alt_l', Key.alt_r: 'alt_r',
            Key.cmd: 'cmd', Key.cmd_l: 'cmd_l', Key.cmd_r: 'cmd_r', # Windows/Super key
            Key.enter: 'enter',
            Key.backspace: 'backspace',
            Key.tab: 'tab',
            Key.space: 'space',
            Key.delete: 'delete',
            Key.insert: 'insert',
            Key.home: 'home',
            Key.end: 'end',
            Key.page_up: 'page_up',
            Key.page_down: 'page_down',
            Key.up: 'up',
            Key.down: 'down',
            Key.left: 'left',
            Key.right: 'right',
            Key.caps_lock: 'caps_lock',
            Key.num_lock: 'num_lock',
            Key.print_screen: 'print_screen',
            Key.scroll_lock: 'scroll_lock',
            Key.pause: 'pause'
            # Add other special keys as needed
        }
        if key_event in special_keys_map:
            return special_keys_map[key_event]
            
        # --- Regular Characters (from key.char if available) ---
        try:
            # Use key.char for letters, numbers, symbols if it exists
            # Use vk for numpad keys if char isn't descriptive
            if hasattr(key_event, 'vk') and 96 <= key_event.vk <= 105: # Numpad 0-9
                 return f'num_{key_event.vk - 96}' # represent as 'num_0', 'num_1', etc.
            # Check for other numpad keys by vk if needed
            # vk 106: numpad *, 107: numpad +, 109: numpad -, 110: numpad ., 111: numpad /
            if hasattr(key_event, 'vk') and key_event.vk == 106: return 'num_*'
            if hasattr(key_event, 'vk') and key_event.vk == 107: return 'num_+'
            if hasattr(key_event, 'vk') and key_event.vk == 109: return 'num_-'
            if hasattr(key_event, 'vk') and key_event.vk == 110: return 'num_.'
            if hasattr(key_event, 'vk') and key_event.vk == 111: return 'num_/'

            # Fallback to key.char if it exists
            return key_event.char
        except AttributeError:
             # If key doesn't have char (like some special keys not mapped above)
             # We might try getting its name, but pynput names can be weird
             # For now, return None to ignore unhandled keys
             # print(f"Unhandled key: {key_event}")
             return None

    def run(self):
        self.recording = True
        self.raw_events = []
        self.start_time_ns = time.perf_counter_ns() 
        self.pressed_modifiers = set()
        
        def on_press(key_event):
            if not self.recording:
                return False 
            
            try:
                if key_event == Key.esc:
                    self.recording = False
                    return False 
                
                key_repr = self.get_key_representation(key_event)
                if key_repr:
                    now_ns = time.perf_counter_ns()
                    # Avoid recording repeated presses for modifiers held down
                    is_modifier = key_repr in ['shift', 'shift_r', 'ctrl', 'ctrl_l', 'ctrl_r', 'alt', 'alt_l', 'alt_r', 'cmd', 'cmd_l', 'cmd_r']
                    if is_modifier and key_repr in self.pressed_modifiers:
                        return True # Already tracking this modifier as pressed
                    
                    self.raw_events.append([now_ns - self.start_time_ns, key_repr, True])
                    self.update_signal.emit(key_repr, "pressed")
                    if is_modifier:
                        self.pressed_modifiers.add(key_repr)

            except Exception as e:
                print(f"Error in key press handler: {e}")
            return True 
        
        def on_release(key_event):
            if not self.recording: 
                return False
            
            try:
                key_repr = self.get_key_representation(key_event)
                if key_repr:
                    now_ns = time.perf_counter_ns()
                    self.raw_events.append([now_ns - self.start_time_ns, key_repr, False])
                    self.update_signal.emit(key_repr, "released")
                    # Remove from pressed modifiers if it was one
                    if key_repr in self.pressed_modifiers:
                         self.pressed_modifiers.discard(key_repr)
            except Exception as e:
                print(f"Error in key release handler: {e}")
            return True
        
        # Suppress=False allows events to pass through to other apps during recording
        listener = keyboard.Listener(on_press=on_press, on_release=on_release, suppress=False)
        listener.start()
        
        while self.recording:
            time.sleep(0.05) 
            
        listener.stop()
        
        self.finished_signal.emit(self.raw_events)
    
    def stop(self):
        self.recording = False

class TestPathWorker(QThread):
    """Thread for testing a path by simulating key presses"""
    update_signal = pyqtSignal(str)  # Message updates
    progress_signal = pyqtSignal(int, int)  # Current action, total actions
    finished_signal = pyqtSignal()
    
    def __init__(self, actions):
        super().__init__()
        self.actions = actions
        self.running = False
        # Create keyboard controller in the run method to avoid cross-thread issues
    
    def run(self):
        self.running = True
        
        if not self.actions:
            self.update_signal.emit("No actions to test")
            self.finished_signal.emit()
            return
        
        try:
            kb_controller = KeyboardController()
            total_actions = len(self.actions)
            self.update_signal.emit(f"Testing path with {total_actions} actions...")
            
            for i, action in enumerate(self.actions):
                if not self.running:
                    self.update_signal.emit("Test stopped")
                    break
                    
                key_repr, press_duration_ms, sleep_after_ms = action
                
                self.progress_signal.emit(i + 1, total_actions)
                self.update_signal.emit(f"Pressing '{key_repr}' for {press_duration_ms}ms")
                
                try:
                    # Determine the actual key object/char to press
                    key_to_press = None
                    if key_repr in SPECIAL_KEY_MAP_REVERSE:
                        key_to_press = SPECIAL_KEY_MAP_REVERSE[key_repr]
                    elif len(key_repr) == 1: # Assume single character
                        key_to_press = key_repr
                    else:
                        self.update_signal.emit(f"Warning: Unknown key representation '{key_repr}', skipping.")
                        continue # Skip this action
                    
                    # Simulate press, hold, release
                    kb_controller.press(key_to_press)
                    time.sleep(press_duration_ms / 1000.0)
                    kb_controller.release(key_to_press)
                    
                    if sleep_after_ms > 0:
                        self.update_signal.emit(f"Waiting {sleep_after_ms}ms...")
                        time.sleep(sleep_after_ms / 1000.0)
                        
                except Exception as e:
                    self.update_signal.emit(f"Error pressing key '{key_repr}': {e}")
                    # Attempt to release the key just in case it got stuck
                    try: kb_controller.release(key_to_press) 
                    except: pass
                    
            if self.running: # Check if stopped during loop
                 self.update_signal.emit("Path test completed")
        except Exception as e:
            self.update_signal.emit(f"Test error: {e}")
        
        self.running = False
        self.finished_signal.emit()
        
    def stop(self):
        self.running = False

class PathRecorder(QMainWindow):
    """Main window for the path recorder application"""
    
    MIN_ACTION_DURATION_MS = 15 # Minimum duration (ms) for an action to be valid
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("RiftScope Path Recorder")
        self.setGeometry(100, 100, 600, 500)
        self.recorded_actions = []
        self.paths_dir = DEFAULT_PATHS_DIR
        self.recording_thread = None
        self.hotkey_listener = None
        self.test_worker = None
        
        # Apply dark theme
        self.setup_dark_theme()
        
        # Build UI
        self.setup_ui()
        
        # Check and create paths directory if needed
        self.ensure_paths_dir()
        
        # Start global hotkey listener in a separate thread
        self.start_hotkey_listener()
    
    # Add update_signal method to handle countdown messages
    def update_signal(self, message):
        """Handle signals from worker threads"""
        self.log(message)
        
    # Handle events, including our custom hotkey event
    def event(self, event):
        if event.type() == HotkeyPressEvent.EventType:
            if event.key == Qt.Key.Key_F1:
                self.toggle_recording()
                return True
        return super().event(event)
    
    def setup_dark_theme(self):
        """Set up dark theme for the application"""
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
        dark_palette.setColor(QPalette.ColorRole.Link, QColor(114, 137, 218))
        dark_palette.setColor(QPalette.ColorRole.Highlight, QColor(114, 137, 218))
        dark_palette.setColor(QPalette.ColorRole.HighlightedText, Qt.GlobalColor.black)
        self.setPalette(dark_palette)
    
    def setup_ui(self):
        """Set up the application UI"""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(15)
        
        # Title
        title_label = QLabel("RiftScope Path Recorder")
        title_font = QFont("Segoe UI", 16)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_label.setStyleSheet("color: #7289da;")
        main_layout.addWidget(title_label)
        
        # Description
        description = QLabel(
            "Record keyboard movements to create custom collection paths for RiftScope.\n"
            "Press Start Recording or F1 key to start/stop recording.\n"
            "Use WASD keys (or arrow keys) to record your path.\n"
            "Press ESC to stop recording. Then name your path and save it."
        )
        description.setAlignment(Qt.AlignmentFlag.AlignCenter)
        description.setWordWrap(True)
        main_layout.addWidget(description)
        
        # Path name and description inputs
        form_layout = QVBoxLayout()
        
        name_label = QLabel("Path Name:")
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("Enter a name for your path")
        form_layout.addWidget(name_label)
        form_layout.addWidget(self.name_input)
        
        description_label = QLabel("Path Description:")
        self.description_input = QLineEdit()
        self.description_input.setPlaceholderText("Enter a brief description of your path")
        form_layout.addWidget(description_label)
        form_layout.addWidget(self.description_input)
        
        main_layout.addLayout(form_layout)
        
        # Control buttons
        buttons_layout = QHBoxLayout()
        
        self.record_button = QPushButton("Start Recording")
        self.record_button.setStyleSheet("""
            QPushButton {
                background-color: #43b581;
                color: white;
                border: none;
                padding: 8px 16px;
                font-size: 10pt;
                font-weight: bold;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #3ca374;
            }
            QPushButton:pressed {
                background-color: #359066;
            }
        """)
        self.record_button.clicked.connect(self.toggle_recording)
        buttons_layout.addWidget(self.record_button)
        
        self.save_button = QPushButton("Save Path")
        self.save_button.setStyleSheet("""
            QPushButton {
                background-color: #7289da;
                color: white;
                border: none;
                padding: 8px 16px;
                font-size: 10pt;
                font-weight: bold;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #677bc4;
            }
            QPushButton:pressed {
                background-color: #5b6eae;
            }
        """)
        self.save_button.clicked.connect(self.save_path)
        self.save_button.setEnabled(False)
        buttons_layout.addWidget(self.save_button)
        
        self.clear_button = QPushButton("Clear")
        self.clear_button.setStyleSheet("""
            QPushButton {
                background-color: #f04747;
                color: white;
                border: none;
                padding: 8px 16px;
                font-size: 10pt;
                font-weight: bold;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #d84141;
            }
            QPushButton:pressed {
                background-color: #c03939;
            }
        """)
        self.clear_button.clicked.connect(self.clear_recording)
        self.clear_button.setEnabled(False)
        buttons_layout.addWidget(self.clear_button)
        
        main_layout.addLayout(buttons_layout)
        
        # Test path section
        test_section = QFrame()
        test_layout = QVBoxLayout(test_section)
        test_layout.setContentsMargins(0, 10, 0, 0)
        test_layout.setSpacing(10)
        
        test_header = QLabel("Test Path")
        test_header.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        test_header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        test_layout.addWidget(test_header)
        
        test_options_layout = QHBoxLayout()
        
        self.path_combo = QComboBox()
        self.path_combo.addItem("Current Recording")
        test_options_layout.addWidget(self.path_combo, 1)
        
        self.test_button = QPushButton("Test Path")
        self.test_button.setStyleSheet("""
            QPushButton {
                background-color: #faa61a;
                color: white;
                border: none;
                padding: 8px 16px;
                font-size: 10pt;
                font-weight: bold;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #e09517;
            }
            QPushButton:pressed {
                background-color: #c78414;
            }
        """)
        self.test_button.clicked.connect(self.test_path)
        self.test_button.setEnabled(False)
        test_options_layout.addWidget(self.test_button)
        
        self.stop_test_button = QPushButton("Stop Test")
        self.stop_test_button.setStyleSheet("""
            QPushButton {
                background-color: #f04747;
                color: white;
                border: none;
                padding: 8px 16px;
                font-size: 10pt;
                font-weight: bold;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #d84141;
            }
            QPushButton:pressed {
                background-color: #c03939;
            }
        """)
        self.stop_test_button.clicked.connect(self.stop_test)
        self.stop_test_button.setEnabled(False)
        test_options_layout.addWidget(self.stop_test_button)
        
        test_layout.addLayout(test_options_layout)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setFormat("%v/%m actions")
        test_layout.addWidget(self.progress_bar)
        
        main_layout.addWidget(test_section)
        
        # Recording log
        log_label = QLabel("Activity Log:")
        main_layout.addWidget(log_label)
        
        self.log_console = QTextEdit()
        self.log_console.setReadOnly(True)
        log_font = QFont("Consolas", 9)
        if log_font.family() == "Consolas":
            self.log_console.setFont(log_font)
        main_layout.addWidget(self.log_console)
        
        # Status bar
        self.status_label = QLabel("Ready to record")
        self.status_label.setStyleSheet("color: #43b581;")
        main_layout.addWidget(self.status_label)
        
        # Load available paths
        self.load_available_paths()
        
        # Connect path selection change signal
        self.path_combo.currentIndexChanged.connect(self.on_path_selection_changed)
        
        # Set initial state of Test button based on current selection
        self.on_path_selection_changed(self.path_combo.currentIndex())
    
    def ensure_paths_dir(self):
        """Ensure the Paths directory exists"""
        if not os.path.exists(self.paths_dir):
            try:
                os.makedirs(self.paths_dir)
                self.log(f"Created paths directory: {self.paths_dir}")
            except Exception as e:
                self.log(f"Error creating paths directory: {e}")
    
    def load_available_paths(self):
        """Load available paths from the Paths directory"""
        current_selection_text = self.path_combo.currentText()
        current_selection_data = self.path_combo.currentData()

        # Keep the first item ("Current Recording") and clear others
        while self.path_combo.count() > 1:
            self.path_combo.removeItem(1)
            
        try:
            path_files = glob.glob(os.path.join(self.paths_dir, "*.json"))
            for path_file in path_files:
                try:
                    with open(path_file, 'r') as f:
                        path_data = json.load(f)
                        path_name = path_data.get('name', os.path.basename(path_file))
                        # Store the full file path as item data
                        self.path_combo.addItem(path_name, path_file) 
                except Exception as e:
                    self.log(f"Skipping invalid path file {os.path.basename(path_file)}: {e}")
            
            if self.path_combo.count() > 1: # Means saved paths were added
                self.log(f"Loaded {self.path_combo.count() - 1} saved paths from '{self.paths_dir}'")

            # Try to restore previous selection if it still exists
            found_idx = self.path_combo.findData(current_selection_data) if current_selection_data else -1
            if found_idx != -1:
                self.path_combo.setCurrentIndex(found_idx)
            elif current_selection_text == "Current Recording":
                self.path_combo.setCurrentIndex(0)
            
        except Exception as e:
            self.log(f"Error loading paths: {e}")
        
        # Update test button state after loading/reloading paths
        self.on_path_selection_changed(self.path_combo.currentIndex())
    
    def toggle_recording(self):
        """Start or stop recording"""
        if self.recording_thread and self.recording_thread.isRunning():
            self.recording_thread.stop()
            self.record_button.setText("Start Recording")
            self.status_label.setText("Stopping recording...")
        else:
            self.recorded_actions = []
            self.log_console.clear()
            self.log("Recording started. Press F1 or ESC to stop.")
            self.status_label.setText("Recording in progress... press keys WASD or arrow keys")
            self.record_button.setText("Stop Recording")
            self.save_button.setEnabled(False)
            self.clear_button.setEnabled(False)
            
            self.recording_thread = RecordThread()
            self.recording_thread.update_signal.connect(self.update_log)
            self.recording_thread.finished_signal.connect(self.recording_finished)
            self.recording_thread.start()
    
    def update_log(self, key_repr, action_type):
        """Update the log with raw keystroke information"""
        # Simple logging for raw events during recording
        timestamp = datetime.now().strftime('%H:%M:%S.%f')[:-3]
        self.log(f"[{timestamp}] Key '{key_repr}' {action_type}")

    def recording_finished(self, raw_events):
        """Handle the end of recording: process raw events into actions."""
        self.record_button.setText("Start Recording")
        self.log("\nProcessing recorded events...")
        
        processed_actions = self._process_raw_events(raw_events)
        self.recorded_actions = processed_actions # Store the processed actions
        
        self.save_button.setEnabled(True)
        self.clear_button.setEnabled(True)
        self.status_label.setText(f"Recording completed: {len(self.recorded_actions)} actions processed")
        
        if self.recorded_actions:
            total_duration = sum(a[1] + a[2] for a in self.recorded_actions)
            self.log(f"Processed path: {len(self.recorded_actions)} actions, estimated duration {total_duration/1000:.2f}s")
            self.log("Path ready to save or test")
        else:
            self.log("No valid actions recorded (check minimum duration)." )
            
        self.on_path_selection_changed(self.path_combo.currentIndex())

    def _ns_to_ms(self, ns):
        """Utility to convert nanoseconds to milliseconds."""
        return int(ns / 1_000_000)

    def _process_raw_events(self, raw_events):
        """Processes a list of raw [timestamp_ns, char, is_press] events 
           into the RiftScope action format [[char, duration_ms, sleep_ms]]."""
        if not raw_events:
            return []

        final_actions = []
        # {char: start_time_ns, ...}
        active_presses = {}
        # Timestamp when the last valid action (release/interrupt) finished
        last_action_end_ns = 0 

        self.log("--- Processing Log --- ")
        for i, event in enumerate(raw_events):
            event_time_ns, char, is_press = event

            if is_press:
                # --- Handle Interruption --- 
                interrupted_action = None
                for active_char, press_start_ns in active_presses.items():
                    if active_char != char: # Found a different active key - interruption!
                        interrupted_duration_ms = self._ns_to_ms(event_time_ns - press_start_ns)
                        if interrupted_duration_ms >= self.MIN_ACTION_DURATION_MS:
                            # Calculate pause before the *interrupted* key was pressed
                            pause_ms = self._ns_to_ms(press_start_ns - last_action_end_ns)
                            if final_actions: final_actions[-1][2] = pause_ms
                            # Add interrupted action with 0 sleep after
                            interrupted_action = [active_char, interrupted_duration_ms, 0]
                            final_actions.append(interrupted_action)
                            self.log(f"  Processed Interrupt: {interrupted_action} (Pause before: {pause_ms}ms)")
                        else:
                             self.log(f"  Ignored short interrupted press: {active_char} ({interrupted_duration_ms}ms)")
                        # Remove interrupted key from active presses
                        del active_presses[active_char]
                        # Mark the end time (this interruption point)
                        last_action_end_ns = event_time_ns 
                        break # Only handle one interruption per press event
                
                # --- Record New Press --- 
                if char not in active_presses:
                    # Calculate pause before this new press started
                    pause_ms = self._ns_to_ms(event_time_ns - last_action_end_ns) if last_action_end_ns > 0 else 0
                    # We update the *previous* action's sleep value
                    if final_actions and not interrupted_action: # Don't update if we just added an interrupted action
                         final_actions[-1][2] = pause_ms
                    
                    active_presses[char] = event_time_ns
                    self.log(f"  Start Press: '{char}' (Pause before: {pause_ms}ms)")
                # else: Ignoring press event for key already active

            elif not is_press: # It's a release event
                if char in active_presses:
                    press_start_ns = active_presses[char]
                    duration_ms = self._ns_to_ms(event_time_ns - press_start_ns)

                    if duration_ms >= self.MIN_ACTION_DURATION_MS:
                        # Calculate pause before this key was pressed
                        pause_ms = self._ns_to_ms(press_start_ns - last_action_end_ns) if last_action_end_ns > 0 else 0
                        # Update sleep of previous action if it exists
                        if final_actions: 
                            final_actions[-1][2] = pause_ms
                        # Add this action with placeholder sleep
                        new_action = [char, duration_ms, 10]
                        final_actions.append(new_action)
                        self.log(f"  Processed Release: {new_action} (Pause before: {pause_ms}ms)")
                        last_action_end_ns = event_time_ns # Mark end time
                    else:
                         self.log(f"  Ignored short press/release: {char} ({duration_ms}ms)")

                    del active_presses[char] # Remove from active presses
        
        # --- Finalize any keys still active at the end --- 
        stop_time_ns = time.perf_counter_ns()
        # Convert start_time_ns from RecordThread (if available) or use first event time
        recording_start_ns = self.recording_thread.start_time_ns if self.recording_thread else raw_events[0][0]
        # Use last raw event time as a proxy if needed, but perf_counter is better
        effective_stop_ns = stop_time_ns - recording_start_ns
        
        for char, press_start_ns in active_presses.items():
            duration_ms = self._ns_to_ms(effective_stop_ns - press_start_ns)
            if duration_ms >= self.MIN_ACTION_DURATION_MS:
                pause_ms = self._ns_to_ms(press_start_ns - last_action_end_ns) if last_action_end_ns > 0 else 0
                if final_actions: final_actions[-1][2] = pause_ms
                # Final action has 0 sleep
                final_action = [char, duration_ms, 0]
                final_actions.append(final_action)
                self.log(f"  Processed final held key: {final_action} (Pause before: {pause_ms}ms)")
            else:
                 self.log(f"  Ignored short final held key: {char} ({duration_ms}ms)")

        # Ensure the very last action truly has 0 sleep
        if final_actions:
            if final_actions[-1][2] != 0:
                self.log(f"  Correcting final action sleep: {final_actions[-1]} -> 0ms")
                final_actions[-1][2] = 0
        
        self.log("--- Processing Complete --- ")
        return final_actions
    
    def log(self, message):
        """Add a message to the log console"""
        self.log_console.append(message)
        self.log_console.ensureCursorVisible()
    
    def clear_recording(self):
        """Clear the current recording"""
        self.recorded_actions = []
        self.log_console.clear()
        self.log("Recording cleared.")
        self.save_button.setEnabled(False)
        self.clear_button.setEnabled(False)
        self.status_label.setText("Ready to record")
        self.on_path_selection_changed(self.path_combo.currentIndex())
    
    def save_path(self):
        """Save the recorded path to a file"""
        if not self.recorded_actions:
            QMessageBox.warning(self, "Empty Path", "No actions recorded. Please record a path first.")
            return
        
        path_name = self.name_input.text().strip()
        if not path_name:
            QMessageBox.warning(self, "Missing Name", "Please enter a name for your path.")
            return
        
        # Create a file name from the path name
        file_name = path_name.lower().replace(' ', '_') + '.json'
        file_path = os.path.join(self.paths_dir, file_name)
        
        # Create the path data
        path_data = {
            'name': path_name,
            'description': self.description_input.text().strip() or f"Custom path recorded on {datetime.now().strftime('%Y-%m-%d')}",
            'actions': self.recorded_actions
        }
        
        try:
            with open(file_path, 'w') as f:
                json.dump(path_data, f, indent=4)
            
            self.log(f"Path saved to {file_path}")
            self.status_label.setText(f"Path saved successfully: {file_name}")
            
            QMessageBox.information(
                self, 
                "Path Saved", 
                f"Path saved successfully to {file_path}.\n\nYou can now use this path in RiftScope."
            )
            
            # After successfully saving, reload available paths
            self.load_available_paths()
        except Exception as e:
            self.log(f"Error saving path: {e}")
            QMessageBox.critical(self, "Error Saving", f"Error saving path: {str(e)}")
    
    def test_path(self):
        """Test the selected path"""
        if self.test_worker and self.test_worker.isRunning():
            QMessageBox.warning(self, "Test In Progress", "A path test is already running.")
            return
        
        # Get actions based on selection
        test_actions = []
        selected_index = self.path_combo.currentIndex()
        
        if selected_index == 0:  # Current Recording
            test_actions = self.recorded_actions
            path_name = "Current Recording"
            if not test_actions:
                QMessageBox.warning(self, "Empty Recording", "No actions recorded yet. Please record a path first.")
                return
        else:
            # Load path from file
            path_file = self.path_combo.currentData()
            try:
                with open(path_file, 'r') as f:
                    path_data = json.load(f)
                    test_actions = path_data.get('actions', [])
                    path_name = path_data.get('name', os.path.basename(path_file))
            except Exception as e:
                self.log(f"Error loading path for testing: {e}")
                QMessageBox.critical(self, "Path Load Error", f"Failed to load path for testing: {str(e)}")
                return
        
        if not test_actions:
            QMessageBox.warning(self, "Empty Path", "No actions to test.")
            return
        
        # Show warning and confirmation before testing
        confirm = QMessageBox.warning(
            self,
            "Confirm Path Test",
            "Testing will simulate key presses for the selected path.\n\n"
            "Please switch to your game window after clicking OK.\n"
            "You'll have 3 seconds before testing begins.\n\n"
            "Continue?",
            QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel
        )
        
        if confirm != QMessageBox.StandardButton.Ok:
            return
        
        # Create and start a worker thread for testing
        self.test_worker = TestPathWorker(test_actions)
        self.test_worker.update_signal.connect(self.log)
        self.test_worker.progress_signal.connect(self.update_progress)
        self.test_worker.finished_signal.connect(self.on_test_finished)
        
        # Update UI
        self.status_label.setText(f"Testing path: {path_name}")
        self.test_button.setEnabled(False)
        self.stop_test_button.setEnabled(True)
        self.record_button.setEnabled(False)
        self.save_button.setEnabled(False)
        self.clear_button.setEnabled(False)
        self.path_combo.setEnabled(False)
        self.progress_bar.setMaximum(len(test_actions))
        self.progress_bar.setValue(0)
        
        # Start the test with a countdown
        self.log(f"Starting test of path: {path_name}")
        self.log("Waiting 3 seconds before starting...")
        
        def delayed_start():
            time.sleep(1)
            self.log("Starting in 2...")
            time.sleep(1)
            self.log("Starting in 1...")
            time.sleep(1)
            self.test_worker.start()
        
        # Use a separate thread for the countdown to keep UI responsive
        threading.Thread(target=delayed_start, daemon=True).start()
    
    def stop_test(self):
        """Stop the current path test"""
        if self.test_worker and self.test_worker.isRunning():
            self.log("Stopping path test...")
            self.status_label.setText("Stopping test...")
            self.test_worker.stop()
    
    def update_progress(self, current, total):
        """Update the progress bar"""
        self.progress_bar.setValue(current)
    
    def on_test_finished(self):
        """Handle test completion"""
        self.stop_test_button.setEnabled(False)
        self.record_button.setEnabled(True)
        self.path_combo.setEnabled(True) # Re-enable path combo
        
        if self.recorded_actions: # Enable save/clear if there's a current recording
            self.save_button.setEnabled(True)
            self.clear_button.setEnabled(True)
        else:
            self.save_button.setEnabled(False)
            self.clear_button.setEnabled(False)
            
        # Update Test button state based on current selection and that test is no longer running
        self.on_path_selection_changed(self.path_combo.currentIndex())
        self.status_label.setText("Test completed")
    
    def start_hotkey_listener(self):
        """Start a listener for global hotkeys"""
        def on_hotkey_press(key):
            # Only respond to F1 key
            if key == Key.f1:
                # Use QApplication.postEvent to safely interact with UI from another thread
                QApplication.instance().postEvent(self, HotkeyPressEvent(Qt.Key.Key_F1))
                return

        def hotkey_listener_thread():
            with keyboard.Listener(on_press=on_hotkey_press) as listener:
                self.hotkey_listener = listener
                listener.join()
        
        # Start the listener in a separate thread
        threading.Thread(target=hotkey_listener_thread, daemon=True).start()
        self.log("Global hotkey listener started (F1 to start/stop recording)")

    def closeEvent(self, event):
        """Handle application close event"""
        # Stop the hotkey listener if it's running
        if self.hotkey_listener:
            self.hotkey_listener.stop()
        
        # Stop the recording thread if it's running
        if self.recording_thread and self.recording_thread.isRunning():
            self.recording_thread.stop()
            self.recording_thread.wait(500)  # Wait up to 500ms for the thread to finish
        
        # Stop the test thread if it's running
        if self.test_worker and self.test_worker.isRunning():
            self.test_worker.stop()
            self.test_worker.wait(500)
        
        event.accept()

    def on_path_selection_changed(self, index):
        """Enable/Disable Test Path button based on selected path content and test status."""
        actions_to_test = []
        path_has_content = False

        if index == 0:  # "Current Recording" is selected
            actions_to_test = self.recorded_actions
            path_has_content = bool(actions_to_test)
        elif index > 0 : # A saved path is selected
            path_file = self.path_combo.itemData(index)
            if path_file and os.path.exists(path_file):
                try:
                    with open(path_file, 'r') as f:
                        path_data = json.load(f)
                        actions_to_test = path_data.get('actions', [])
                        path_has_content = bool(actions_to_test)
                except Exception as e:
                    self.log(f"Error checking path content for {os.path.basename(path_file)}: {e}")
                    path_has_content = False
            else: # Path file might not exist or data is None
                path_has_content = False
        
        is_test_running = self.test_worker is not None and self.test_worker.isRunning()
        
        # Enable test_button if path has content AND no test is currently running
        self.test_button.setEnabled(path_has_content and not is_test_running)
        
        # Stop test button is managed by test_path and on_test_finished

# Custom event for handling hotkey presses
class HotkeyPressEvent(QEvent):
    # Define a custom event type
    EventType = QEvent.Type(QEvent.registerEventType())
    
    def __init__(self, key):
        super().__init__(HotkeyPressEvent.EventType)
        self.key = key

def main():
    app = QApplication(sys.argv)
    recorder = PathRecorder()
    recorder.show()
    sys.exit(app.exec())

if __name__ == '__main__':
    main() 