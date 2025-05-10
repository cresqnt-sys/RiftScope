#!/usr/bin/env python3
# RiftScope - Data Models and Worker Classes
# GitHub: https://github.com/cresqnt-sys/RiftScope

from PyQt6.QtCore import QThread, pyqtSignal, Qt, QPoint, QRect
from PyQt6.QtWidgets import QWidget
from PyQt6.QtGui import QPainter, QColor, QFont, QPen
import time
import threading
import queue
import re
import os # For path joining in CurrencyScreenshotWorker
from datetime import datetime
from enum import Enum
from utils import read_log_file, find_log_path, get_latest_log_file, log_message, APP_DATA_DIR # Added APP_DATA_DIR

# Attempt to import Pillow (PIL) for screenshots
try:
    from PIL import ImageGrab
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False
    print("WARNING: Pillow (PIL) module not found. Screenshot functionality will be disabled.")

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

    def __init__(self, parent=None, calibration_target_text="Click on the target location."):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.SplashScreen)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setWindowState(Qt.WindowState.WindowFullScreen)
        self.target_text = calibration_target_text

    def paintEvent(self, event):
        painter = QPainter(self)

        painter.fillRect(self.rect(), QColor(40, 40, 40, 180))

        painter.setPen(QColor(220, 220, 220))
        font = QFont("Segoe UI", 16)
        font.setBold(True)
        painter.setFont(font)
        if "\\n" in self.target_text:
            lines = self.target_text.split("\\n")
            text_to_draw = "\\n".join(lines) + "\\nPress ESC to cancel."
        else:
            text_to_draw = self.target_text + "\\nPress ESC to cancel."
            
        painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, text_to_draw)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton: 
            self.point_selected.emit(event.pos())
            self.close() 

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            print("Calibration cancelled by user.")
            self.close() 

class AreaCalibrationOverlay(QWidget):
    area_selected = pyqtSignal(QPoint, QPoint) # Emits top-left and bottom-right points

    def __init__(self, parent=None, calibration_target_text="Drag to select area."):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.SplashScreen)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setWindowState(Qt.WindowState.WindowFullScreen)
        self.target_text = calibration_target_text
        self.start_point = QPoint()
        self.end_point = QPoint()
        self.drawing = False

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Semi-transparent overlay
        painter.fillRect(self.rect(), QColor(40, 40, 40, 170))

        # Instruction text
        painter.setPen(QColor(220, 220, 220))
        font = QFont("Segoe UI", 16)
        font.setBold(True)
        painter.setFont(font)
        
        instruction_text = self.target_text
        if "\\n" not in instruction_text: # Ensure multi-line for consistency
            instruction_text += "\\nClick and drag to define the area."
        instruction_text += "\\nPress ESC to cancel."
        
        painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, instruction_text)

        # Draw the selection rectangle if currently drawing
        if self.drawing:
            rect = QRect(self.start_point, self.end_point).normalized()
            painter.setPen(QPen(QColor(60, 170, 250, 200), 2, Qt.PenStyle.SolidLine)) # Blueish, slightly thicker
            painter.setBrush(QColor(90, 180, 255, 70)) # Light blue fill
            painter.drawRect(rect)
            
            # Optional: Draw coordinates at corners or mouse position
            debug_text_font = QFont("Segoe UI", 10)
            painter.setFont(debug_text_font)
            painter.setPen(QColor(230,230,230))
            painter.drawText(self.end_point.x() + 5, self.end_point.y() - 5, f"({self.end_point.x()}, {self.end_point.y()})")


    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.start_point = event.pos()
            self.end_point = event.pos()
            self.drawing = True
            self.update() # Trigger repaint

    def mouseMoveEvent(self, event):
        if self.drawing:
            self.end_point = event.pos()
            self.update() # Trigger repaint

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.drawing:
            self.drawing = False
            # Ensure start_point is top-left and end_point is bottom-right before emitting
            rect = QRect(self.start_point, self.end_point).normalized()
            self.area_selected.emit(rect.topLeft(), rect.bottomRight())
            self.close()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            print("Area calibration cancelled by user.")
            self.close()

class EventType(Enum):
    """Enum for different types of events detected in logs."""
    RIFT = "rift"
    HATCH = "hatch"
    WARNING = "warning"
    ERROR = "error"
    INFO = "info"

class LogEvent:
    """Data class representing a detected event from the log."""
    def __init__(self, event_type, message, timestamp=None, details=None):
        self.event_type = event_type
        self.message = message
        self.timestamp = timestamp or datetime.now()
        self.details = details or {}
    
    def __str__(self):
        return f"{self.timestamp.strftime('%H:%M:%S')} - {self.event_type.name}: {self.message}"

class RiftEvent(LogEvent):
    """Specialized event for rift detections."""
    def __init__(self, message, location=None, timestamp=None):
        details = {"location": location} if location else {}
        super().__init__(EventType.RIFT, message, timestamp, details)

class HatchEvent(LogEvent):
    """Specialized event for hatch detections."""
    def __init__(self, message, location=None, timestamp=None):
        details = {"location": location} if location else {}
        super().__init__(EventType.HATCH, message, timestamp, details)

class LogMonitorWorker(threading.Thread):
    """Worker thread for monitoring the log file for events."""
    def __init__(self, event_queue, config):
        super().__init__(daemon=True)
        self.event_queue = event_queue
        self.config = config
        self.running = True
        self.last_position = 0
        self.log_file = None
        self.log_dir = None
        self.check_interval = 0.5  # Check logs every 0.5 seconds
        
        # Compile regex patterns for faster matching
        self.rift_pattern = re.compile(r"(?i)rift.*appeared|spawned", re.IGNORECASE)
        self.hatch_pattern = re.compile(r"(?i)hatch", re.IGNORECASE)
        
    def run(self):
        """Main worker thread loop."""
        log_message("Log monitor worker started", "INFO")
        
        while self.running:
            try:
                # Find the log directory if we don't have it yet
                if not self.log_dir:
                    self.log_dir = find_log_path()
                    if not self.log_dir:
                        # If we can't find the log directory, wait and try again
                        time.sleep(10)
                        continue
                        
                # Get the latest log file
                self.log_file = get_latest_log_file(self.log_dir)
                if not self.log_file:
                    # If no log file is found, wait and try again
                    time.sleep(5)
                    continue
                    
                # Read new content from the log file
                new_content, self.last_position = read_log_file(self.log_file, self.last_position)
                
                # Process new content if any
                if new_content:
                    self.process_log_content(new_content)
                    
                # Wait before checking again
                time.sleep(self.check_interval)
                
            except Exception as e:
                log_message(f"Error in log monitor: {str(e)}", "ERROR")
                # Reset on error to allow recovery
                self.last_position = 0
                self.log_file = None
                time.sleep(5)
                
    def process_log_content(self, content):
        """Process new log content and detect events."""
        # Split content into lines and process each line
        for line in content.splitlines():
            # Skip empty lines
            if not line.strip():
                continue
                
            # Check for rift events if detection is enabled
            if self.config.get("detect_rifts", True) and self.rift_pattern.search(line):
                event = RiftEvent("A new Rift has appeared!")
                self.event_queue.put(event)
                log_message(f"Detected rift event: {line}", "INFO")
                
            # Check for hatch events if detection is enabled
            if self.config.get("detect_hatches", True) and self.hatch_pattern.search(line):
                event = HatchEvent("A Hatch has been detected!")
                self.event_queue.put(event)
                log_message(f"Detected hatch event: {line}", "INFO")
                
    def stop(self):
        """Stop the worker thread."""
        self.running = False
        
class CollectionPathPoint:
    """Data class representing a point in a collection path."""
    def __init__(self, name, x, y, z, notes=""):
        self.name = name
        self.x = x
        self.y = y
        self.z = z
        self.notes = notes
        
    def to_dict(self):
        """Convert point to dictionary for serialization."""
        return {
            "name": self.name,
            "x": self.x,
            "y": self.y,
            "z": self.z,
            "notes": self.notes
        }
        
    @classmethod
    def from_dict(cls, data):
        """Create point from dictionary."""
        return cls(
            name=data.get("name", "Unnamed"),
            x=data.get("x", 0),
            y=data.get("y", 0),
            z=data.get("z", 0),
            notes=data.get("notes", "")
        ) 

class CurrencyScreenshotWorker(QThread):
    update_status_signal = pyqtSignal(str)
    send_webhook_signal = pyqtSignal(str, str, str, int, str, str) # title, desc, image_url, color, ping, file_path

    def __init__(self, app_instance):
        super().__init__()
        self.app = app_instance
        self._is_running = False

    def run(self):
        self._is_running = True
        self.update_status_signal.emit("💰 Currency Screenshot Worker started.")
        # screenshots_dir = os.path.join(APP_DATA_DIR, "Screenshots") # Old path
        # os.makedirs(screenshots_dir, exist_ok=True) # Ensure main APP_DATA_DIR is created by config/utils

        while self._is_running:
            if not self.app.running: # If main scanning/app is stopped, worker should stop
                self.update_status_signal.emit("💰 Currency Screenshot Worker: Main app stopped, exiting worker.")
                break

            delay_minutes = 0
            currency_updates_enabled = False
            area_coords = None

            if hasattr(self.app, 'config'):
                currency_updates_enabled = self.app.config.currency_updates_enabled
                delay_minutes = self.app.config.currency_updates_delay_minutes
                area_coords = self.app.config.currency_display_area_coords
            
            if not currency_updates_enabled or delay_minutes <= 0:
                # If disabled or invalid delay, sleep for a bit and re-check config
                self.update_status_signal.emit(f"💰 Currency updates disabled or delay is 0. Worker sleeping for 60s.")
                for _ in range(60): # Sleep for 60 seconds, but check _is_running every second
                    if not self._is_running: break
                    time.sleep(1)
                if not self._is_running: break
                continue

            if not area_coords or len(area_coords) != 4:
                self.update_status_signal.emit(f"💰 Currency display area not calibrated. Waiting for calibration...")
                time.sleep(30) # Wait for calibration
                continue

            if not PIL_AVAILABLE:
                self.update_status_signal.emit("❌ Pillow (PIL) module not available. Cannot take screenshots.")
                self._is_running = False # Stop the worker if PIL is not there
                break
            
            # Main loop: take screenshot, send webhook, then sleep for configured delay
            try:
                self.update_status_signal.emit(f"💰 Taking currency screenshot... Area: {area_coords}")
                # area_coords is (x1, y1, x2, y2)
                bbox = (area_coords[0], area_coords[1], area_coords[2], area_coords[3])
                screenshot = ImageGrab.grab(bbox=bbox)
                
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"currency_{timestamp}.png"
                # filepath = os.path.join(screenshots_dir, filename) # Old path
                filepath = os.path.join(APP_DATA_DIR, filename) # New path: directly in APP_DATA_DIR
                screenshot.save(filepath, "PNG")
                self.update_status_signal.emit(f"💰 Screenshot saved to {filepath}")

                # Emit signal to send webhook with the file
                self.send_webhook_signal.emit(
                    "💰 Currency Update",
                    f"Current currency status at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                    None, # No separate image_url, the file is the image
                    0xfee75c, # Yellowish color
                    None, # No ping content for now, can be added later if needed
                    filepath # Pass the filepath of the screenshot
                )
            except Exception as e:
                self.update_status_signal.emit(f"❌ Error taking/sending currency screenshot: {str(e)}")
                # Log to main console as well for more visibility during errors
                print(f"[CurrencyScreenshotWorker] Error: {str(e)}")

            # Sleep for the configured delay, checking for stop signal periodically
            self.update_status_signal.emit(f"💰 Currency worker sleeping for {delay_minutes} minute(s).")
            sleep_total_seconds = delay_minutes * 60
            for _ in range(sleep_total_seconds):
                if not self._is_running:
                    break
                time.sleep(1) # Check every second
            
            if not self._is_running: # Check if an external stop was requested during sleep
                break
        
        self.update_status_signal.emit("💰 Currency Screenshot Worker stopped.")

    def stop(self):
        self.update_status_signal.emit("💰 Requesting Currency Screenshot Worker to stop...")
        self._is_running = False 