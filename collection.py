import time
import pynput
from pynput import keyboard as pynput_keyboard

# Check if AutoIt is available
try:
    import autoit 
    AUTOIT_AVAILABLE = True
except ImportError:
    AUTOIT_AVAILABLE = False
    print("WARNING: pyautoit module not found or AutoIt installation missing. Teleport click will likely fail.")
    print("Install AutoIt from https://www.autoitscript.com/site/autoit/downloads/ and run 'pip install pyautoit'")

class CollectionManager:
    """Class for handling collection path functionality in RiftScope"""
    
    def __init__(self, app=None):
        self.app = app
        self.collection_running = False
        self.teleport_coords = None
        self.collection_worker = None
        
    def start_calibration(self):
        """Start calibration process for teleport button"""
        if hasattr(self.app, 'calibrating') and self.app.calibrating:
            print("Calibration already in progress.")
            return
            
        if hasattr(self.app, 'running') and self.app.running:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.warning(self.app, "Calibration Error", "Please stop the scanner before calibrating.")
            return

        if hasattr(self.app, 'calibration_overlay') and self.app.calibration_overlay is not None:
            print("Warning: Previous calibration overlay object detected unexpectedly.")
            try:
                self.app.calibration_overlay.destroyed.disconnect(self.on_calibration_closed)
                self.app.calibration_overlay.point_selected.disconnect(self.finish_calibration)
            except (TypeError, RuntimeError): 
                pass
            self.app.calibration_overlay = None

        self.app.calibrating = True
        self.app.update_status("Starting teleport button calibration...")

        from models import CalibrationOverlay
        new_overlay = CalibrationOverlay()

        try:
            new_overlay.point_selected.connect(self.finish_calibration)
            new_overlay.destroyed.connect(self.on_calibration_closed)
        except Exception as e:
            print(f"Error connecting signals for new overlay: {e}")
            self.app.calibrating = False 
            return

        self.app.calibration_overlay = new_overlay
        self.app.calibration_overlay.show()
        
    def finish_calibration(self, point):
        """Handle the finish of calibration when a point is selected"""
        if hasattr(self.app, 'calibration_overlay') and self.app.calibration_overlay:
            self.app.teleport_coords = (point.x(), point.y()) 
            self.teleport_coords = self.app.teleport_coords
            self.app.update_status(f"Teleport point calibrated: ({point.x()},{point.y()})")
            self._update_calibrate_button_text()
            if hasattr(self.app, 'config'):
                self.app.config.teleport_coords = self.app.teleport_coords
                self.app.config.save()
            else:
                self.app.save_config()

            self.app.calibrating = False
            self.app.calibration_overlay.close() 
        else:
            self.app.update_status("Calibration finished unexpectedly.")
            self.app.calibrating = False
            
    def on_calibration_closed(self):
        """Handle cleanup when calibration overlay is closed"""
        self.app.update_status("Calibration window closed.")
        self.app.calibrating = False
        self.app.calibration_overlay = None
        
    def _update_calibrate_button_text(self):
        """Update the calibrate button text based on teleport_coords"""
        if hasattr(self.app, 'calibrate_button'):
            if self.app.teleport_coords and len(self.app.teleport_coords) == 2:
                x, y = self.app.teleport_coords
                self.app.calibrate_button.setText(f"Recalibrate Teleport ({x}, {y})")
                if hasattr(self.app, 'calibrate_coords_label'):
                    self.app.calibrate_coords_label.setText(f"Calibrated at: ({x}, {y})")
                    self.app.calibrate_coords_label.setVisible(True)
            else:
                self.app.calibrate_button.setText("Calibrate Teleport Button")
                if hasattr(self.app, 'calibrate_coords_label'):
                    self.app.calibrate_coords_label.setText("")
                    self.app.calibrate_coords_label.setVisible(False)
                    
    def run_collection_loop(self):
        """Main collection path loop worker function"""
        if not hasattr(self.app, 'collection_running'):
            return
            
        keyboard_controller = pynput_keyboard.Controller()

        while self.app.collection_running:
            # Execute the path steps
            path_completed = self._execute_collection_path()
            if not path_completed or not self.app.collection_running:
                break 

            if self.collection_worker:
                self.collection_worker.update_status_signal.emit("⏳ Waiting after path...")
            time.sleep(2)
            if not self.app.collection_running: 
                break

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
            if not self.app.collection_running:
                break

            # Handle teleport
            if self.app.teleport_coords and len(self.app.teleport_coords) == 2: 
                center_x, center_y = self.app.teleport_coords 
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
            
    def _execute_collection_path(self):
        """Simulates the sequence of key presses for collection."""
        controller = pynput.keyboard.Controller()

        def press_release(key_char, press_time_ms, sleep_after_ms):
            if not hasattr(self.app, 'collection_running') or not self.app.collection_running:
                return False 
            try:
                key = pynput.keyboard.KeyCode.from_char(key_char)
                controller.press(key)
                time.sleep(press_time_ms / 1000.0)
                controller.release(key)
                time.sleep(sleep_after_ms / 1000.0)
            except Exception as e:
                print(f"Error pressing key '{key_char}': {e}")

            return True

        # Collection path key sequence
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
            if not hasattr(self.app, 'collection_running') or not self.app.collection_running:
                if self.collection_worker:
                    self.collection_worker.update_status_signal.emit("🚶 Collection path interrupted.")
                return False 
            if not press_release(key, press_time, sleep_after):
                return False
                
        if self.collection_worker:
            self.collection_worker.update_status_signal.emit("🚶 Collection path finished.")
        return True 