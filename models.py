#!/usr/bin/env python3
# RiftScope - Data Models and Worker Classes
# GitHub: https://github.com/cresqnt-sys/RiftScope

from PyQt6.QtCore import QThread, pyqtSignal, Qt, QPoint
from PyQt6.QtWidgets import QWidget
from PyQt6.QtGui import QPainter, QColor, QFont
import time
import threading
import queue
import re
from datetime import datetime
from enum import Enum
from utils import read_log_file, find_log_path, get_latest_log_file, log_message

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