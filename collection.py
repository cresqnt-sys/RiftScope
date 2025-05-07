import time
import pynput
import json
import os
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
        self.claw_skip_coords = None
        self.claw_claim_coords = None
        self.claw_start_coords = None
        self.collection_worker = None
        self.paths_dir = "Paths"
        self.available_paths = {}
        self.current_path = None
        self.load_available_paths()
        
        # Load current_path from config if available
        if app and hasattr(app, 'config') and hasattr(app.config, 'current_path'):
            # Set the path if it exists in available paths
            if app.config.current_path in self.available_paths:
                self.current_path = app.config.current_path
                print(f"Loaded path '{self.current_path}' from config")
        
        # Load claw machine coordinates from config if available
        if app and hasattr(app, 'config'):
            if hasattr(app.config, 'claw_skip_coords'):
                self.claw_skip_coords = app.config.claw_skip_coords
                print(f"Loaded claw_skip_coords: {self.claw_skip_coords}")
            if hasattr(app.config, 'claw_claim_coords'):
                self.claw_claim_coords = app.config.claw_claim_coords
                print(f"Loaded claw_claim_coords: {self.claw_claim_coords}")
            if hasattr(app.config, 'claw_start_coords'):
                self.claw_start_coords = app.config.claw_start_coords
                print(f"Loaded claw_start_coords: {self.claw_start_coords}")
            # Existing teleport_coords loading (ensure it's also present or add it)
            if hasattr(app.config, 'teleport_coords') and app.config.teleport_coords:
                self.teleport_coords = app.config.teleport_coords
                if hasattr(self.app, 'teleport_coords'): # app might not be fully initialized
                    self.app.teleport_coords = app.config.teleport_coords
                print(f"Loaded teleport_coords: {self.teleport_coords}")
        
    def load_available_paths(self):
        """Load all available paths from the Paths directory"""
        self.available_paths = {}
        if not os.path.exists(self.paths_dir):
            os.makedirs(self.paths_dir)
            print(f"Created paths directory: {self.paths_dir}")
            return
            
        for filename in os.listdir(self.paths_dir):
            if filename.endswith('.json'):
                path_id = os.path.splitext(filename)[0]
                file_path = os.path.join(self.paths_dir, filename)
                try:
                    with open(file_path, 'r') as f:
                        path_data = json.load(f)
                        self.available_paths[path_id] = path_data
                        print(f"Loaded path: {path_data.get('name', path_id)}")
                except Exception as e:
                    print(f"Error loading path {filename}: {e}")
        
        # Default to gem_path if it exists
        if 'gem_path' in self.available_paths:
            self.current_path = 'gem_path'
            
        # Update path selector in UI if available
        if hasattr(self.app, 'update_path_selector'):
            self.app.update_path_selector()
        
    def set_current_path(self, path_id):
        """Set the current path to use"""
        if path_id in self.available_paths:
            self.current_path = path_id
            
            # Save to config if available
            if self.app and hasattr(self.app, 'config'):
                self.app.config.current_path = path_id
                self.app.config.save()
                
            return True
        return False
        
    def _start_generic_calibration(self, calibration_type_name: str):
        """Helper function to start calibration for a generic point type."""
        if hasattr(self.app, 'calibrating') and self.app.calibrating:
            print(f"Calibration already in progress (calibrating for {self.app.calibrating_for}). Cannot start new calibration for {calibration_type_name}.")
            return

        if hasattr(self.app, 'running') and self.app.running:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.warning(self.app, "Calibration Error", "Please stop the scanner before calibrating.")
            return

        if hasattr(self.app, 'calibration_overlay') and self.app.calibration_overlay is not None:
            print("Warning: Previous calibration overlay object detected unexpectedly.")
            try:
                # Ensure all potential connections are handled or use a more robust cleanup
                self.app.calibration_overlay.destroyed.disconnect()
                self.app.calibration_overlay.point_selected.disconnect()
            except (TypeError, RuntimeError):
                pass # May already be disconnected or never connected
            self.app.calibration_overlay = None

        self.app.calibrating = True
        self.app.calibrating_for = calibration_type_name  # Store what we are calibrating
        self.app.update_status(f"Starting {calibration_type_name} calibration...")

        from models import CalibrationOverlay # Assuming models.py contains CalibrationOverlay
        
        # Construct the dynamic text for the overlay
        target_name_readable = calibration_type_name.replace('_', ' ').title()
        overlay_text = f"Click on the exact location of the {target_name_readable} Button."
        if calibration_type_name == "teleport": # Keep original wording for teleport for now or adjust as needed
            overlay_text = f"Click on the exact location of the Teleport Button."
            
        new_overlay = CalibrationOverlay(calibration_target_text=overlay_text)

        try:
            new_overlay.point_selected.connect(self.finish_calibration)
            new_overlay.destroyed.connect(self.on_calibration_closed)
        except Exception as e:
            print(f"Error connecting signals for new overlay: {e}")
            self.app.calibrating = False
            self.app.calibrating_for = None
            return

        self.app.calibration_overlay = new_overlay
        self.app.calibration_overlay.show()

    def start_calibration(self):
        """Start calibration process for teleport button"""
        self._start_generic_calibration("teleport")
        
    def start_claw_skip_calibration(self):
        """Start calibration process for claw machine skip button"""
        self._start_generic_calibration("claw_skip")

    def start_claw_claim_calibration(self):
        """Start calibration process for claw machine claim button"""
        self._start_generic_calibration("claw_claim")

    def start_claw_start_calibration(self):
        """Start calibration process for claw machine start button"""
        self._start_generic_calibration("claw_start")

    def finish_calibration(self, point):
        """Handle the finish of calibration when a point is selected"""
        if not hasattr(self.app, 'calibrating_for') or not self.app.calibrating_for:
            print("Error: finish_calibration called but 'calibrating_for' is not set.")
            self.app.calibrating = False # Ensure state is reset
            if hasattr(self.app, 'calibration_overlay') and self.app.calibration_overlay:
                self.app.calibration_overlay.close()
            return

        calibration_type = self.app.calibrating_for
        coords = (point.x(), point.y())

        if hasattr(self.app, 'calibration_overlay') and self.app.calibration_overlay:
            self.app.update_status(f"{calibration_type.replace('_', ' ').title()} point calibrated: {coords}")

            if calibration_type == "teleport":
                self.app.teleport_coords = coords
                self.teleport_coords = coords
                if hasattr(self.app, 'config'): self.app.config.teleport_coords = coords
                self._update_calibrate_button_text()
            elif calibration_type == "claw_skip":
                self.app.claw_skip_coords = coords # Assuming app also stores these
                self.claw_skip_coords = coords
                if hasattr(self.app, 'config'): self.app.config.claw_skip_coords = coords
                self._update_claw_skip_button_text()
            elif calibration_type == "claw_claim":
                self.app.claw_claim_coords = coords
                self.claw_claim_coords = coords
                if hasattr(self.app, 'config'): self.app.config.claw_claim_coords = coords
                self._update_claw_claim_button_text()
            elif calibration_type == "claw_start":
                self.app.claw_start_coords = coords
                self.claw_start_coords = coords
                if hasattr(self.app, 'config'): self.app.config.claw_start_coords = coords
                self._update_claw_start_button_text()
            else:
                print(f"Unknown calibration type: {calibration_type}")

            if hasattr(self.app, 'config'):
                self.app.config.save()
            else: # Fallback if app.config isn't directly available for saving
                if hasattr(self.app, 'save_config'):
                    self.app.save_config()


            self.app.calibrating = False
            self.app.calibrating_for = None # Reset
            self.app.calibration_overlay.close()
        else:
            self.app.update_status(f"Calibration for {calibration_type} finished unexpectedly.")
            self.app.calibrating = False
            self.app.calibrating_for = None # Reset

    def on_calibration_closed(self):
        """Handle cleanup when calibration overlay is closed"""
        # Get the current calibration type. It might be None if finish_calibration already cleared it.
        calibration_type_value = getattr(self.app, 'calibrating_for', None) 

        type_str_for_message = "Unknown"
        if isinstance(calibration_type_value, str):
            type_str_for_message = calibration_type_value.replace('_',' ').title()
        # If calibration_type_value is None (e.g. after successful calibration followed by overlay.close()),
        # the message will use "Unknown", which is acceptable as a specific success message was already sent.
        # If calibration was cancelled (e.g. ESC), calibration_type_value should still hold the string.

        self.app.update_status(f"Calibration window for {type_str_for_message} closed.")
        
        # Ensure state is consistently reset
        self.app.calibrating = False
        self.app.calibrating_for = None 
        self.app.calibration_overlay = None
        
        # Optionally, refresh button texts if needed, especially if a calibration was cancelled
        # self.update_all_calibration_buttons_text()

    def _update_calibrate_button_text(self):
        """Update the calibrate button text based on teleport_coords"""
        if hasattr(self.app, 'calibrate_button'):
            coords_tuple = getattr(self.app, 'teleport_coords', None) or self.teleport_coords
            label_widget = getattr(self.app, 'calibrate_coords_label', None)

            if coords_tuple and len(coords_tuple) == 2:
                x, y = coords_tuple
                self.app.calibrate_button.setText(f"Recalibrate Teleport ({x}, {y})")
                if label_widget:
                    label_widget.setText(f"Teleport Calibrated at: ({x}, {y})")
                    label_widget.setVisible(True)
            else:
                self.app.calibrate_button.setText("Calibrate Teleport Button")
                if label_widget:
                    label_widget.setText("")
                    label_widget.setVisible(False)

    def _update_claw_skip_button_text(self):
        """Update the claw skip calibrate button text."""
        if hasattr(self.app, 'calibrate_claw_skip_button'):
            coords_tuple = getattr(self.app, 'claw_skip_coords', None) or self.claw_skip_coords
            label_widget = getattr(self.app, 'claw_skip_coords_label', None)

            if coords_tuple and len(coords_tuple) == 2:
                x, y = coords_tuple
                self.app.calibrate_claw_skip_button.setText(f"Recalibrate Skip ({x}, {y})")
                if label_widget:
                    label_widget.setText(f"Skip Calibrated at: ({x}, {y})")
                    label_widget.setVisible(True)
            else:
                self.app.calibrate_claw_skip_button.setText("Calibrate Claw Skip")
                if label_widget:
                    label_widget.setText("")
                    label_widget.setVisible(False)
                    
    def _update_claw_claim_button_text(self):
        """Update the claw claim calibrate button text."""
        if hasattr(self.app, 'calibrate_claw_claim_button'):
            coords_tuple = getattr(self.app, 'claw_claim_coords', None) or self.claw_claim_coords
            label_widget = getattr(self.app, 'claw_claim_coords_label', None)

            if coords_tuple and len(coords_tuple) == 2:
                x, y = coords_tuple
                self.app.calibrate_claw_claim_button.setText(f"Recalibrate Claim ({x}, {y})")
                if label_widget:
                    label_widget.setText(f"Claim Calibrated at: ({x}, {y})")
                    label_widget.setVisible(True)
            else:
                self.app.calibrate_claw_claim_button.setText("Calibrate Claw Claim")
                if label_widget:
                    label_widget.setText("")
                    label_widget.setVisible(False)

    def _update_claw_start_button_text(self):
        """Update the claw start calibrate button text."""
        if hasattr(self.app, 'calibrate_claw_start_button'):
            coords_tuple = getattr(self.app, 'claw_start_coords', None) or self.claw_start_coords
            label_widget = getattr(self.app, 'claw_start_coords_label', None)

            if coords_tuple and len(coords_tuple) == 2:
                x, y = coords_tuple
                self.app.calibrate_claw_start_button.setText(f"Recalibrate Start ({x}, {y})")
                if label_widget:
                    label_widget.setText(f"Start Calibrated at: ({x}, {y})")
                    label_widget.setVisible(True)
            else:
                self.app.calibrate_claw_start_button.setText("Calibrate Claw Start")
                if label_widget:
                    label_widget.setText("")
                    label_widget.setVisible(False)

    def update_all_calibration_buttons_text(self):
        """Updates text for all calibration-related buttons."""
        self._update_calibrate_button_text()
        self._update_claw_skip_button_text()
        self._update_claw_claim_button_text()
        self._update_claw_start_button_text()
        
    def run_collection_loop(self):
        """Main collection path loop worker function"""
        if not hasattr(self.app, 'collection_running'): # Should be app.automation_running if we rename state
            return
            
        keyboard_controller = pynput_keyboard.Controller()
        # Path ID for the special claw machine logic
        CLAW_MACHINE_PATH_ID = 'clawmachine' # Assuming the ID in Paths/clawmachine.json is 'clawmachine'

        while self.app.collection_running: # Consider renaming self.app.collection_running to self.app.automation_running
            
            # Check if the current path is the Claw Machine path
            is_claw_machine_path = self.current_path == CLAW_MACHINE_PATH_ID

            if is_claw_machine_path:
                # --- Claw Machine Specific Logic ---
                if not self.app.collection_running: break

                # 1. Click Claw Machine Start
                if self.app.claw_start_coords and len(self.app.claw_start_coords) == 2:
                    start_x, start_y = self.app.claw_start_coords
                    if AUTOIT_AVAILABLE:
                        try:
                            if self.collection_worker: self.collection_worker.update_status_signal.emit(f"🖱️ Clicking Claw Machine Start at ({int(start_x)}, {int(start_y)}) via AutoIt...")
                            autoit.mouse_click("left", int(start_x), int(start_y), 1, speed=5)
                            
                            if self.collection_worker: self.collection_worker.update_status_signal.emit(f"⏳ Starting 4s wait after Start click...")
                            s_time = time.monotonic()
                            time.sleep(4)
                            e_time = time.monotonic()
                            if self.collection_worker: self.collection_worker.update_status_signal.emit(f"✅ Finished 4s wait (actual: {e_time - s_time:.2f}s).")
                        except Exception as e:
                            if self.collection_worker: self.collection_worker.update_status_signal.emit(f"❌ Error clicking Claw Start (AutoIt): {e}")
                            time.sleep(1) # Brief pause on error
                    else:
                        if self.collection_worker: self.collection_worker.update_status_signal.emit(f"⚠️ AutoIt not available. Cannot perform Claw Start click.")
                        time.sleep(1)
                else:
                    if self.collection_worker: self.collection_worker.update_status_signal.emit("⚠️ Claw Machine Start coordinates not set, skipping click.")
                
                if not self.app.collection_running: break

                # 2. Execute the path steps (movement within claw machine area)
                path_completed = self._execute_collection_path() 
                if not path_completed or not self.app.collection_running:
                    break
                
                # 3. Wait 20 seconds after path (changed from 15s)
                if self.collection_worker: self.collection_worker.update_status_signal.emit("⏳ Starting 20s wait after path execution...")
                s_time = time.monotonic()
                time.sleep(20) # Changed from 15 to 20
                e_time = time.monotonic()
                if self.collection_worker: self.collection_worker.update_status_signal.emit(f"✅ Finished 20s wait (actual: {e_time - s_time:.2f}s).")
                if not self.app.collection_running: break

                # 4. Click Claim Button & Jump
                if self.app.claw_claim_coords and len(self.app.claw_claim_coords) == 2:
                    base_claim_x, base_claim_y = self.app.claw_claim_coords
                    if AUTOIT_AVAILABLE:
                        try:
                            if self.collection_worker: self.collection_worker.update_status_signal.emit(f"🖱️ Starting multi-click sequence for Claw Machine Claim around ({int(base_claim_x)}, {int(base_claim_y)})...")
                            
                            claim_y_offsets = [0, -25, 25, -57, 57] # Order: calibrated, closer, further
                            
                            for offset in claim_y_offsets:
                                if not self.app.collection_running: break # Check before each click
                                click_y = base_claim_y + offset
                                if self.collection_worker: 
                                    self.collection_worker.update_status_signal.emit(f"  🖱️ Clicking Claim at ({int(base_claim_x)}, {int(click_y)}) [Offset: {offset}] via AutoIt...")
                                autoit.mouse_click("left", int(base_claim_x), int(click_y), clicks=1, speed=10) # Changed speed from 1 to 10 for visible movement
                                time.sleep(0.15) # 150ms pause between rapid clicks
                            
                            if not self.app.collection_running: break # Check after all clicks

                            if self.collection_worker: self.collection_worker.update_status_signal.emit(f"✅ Multi-click sequence for Claim finished.")
                            
                            if self.collection_worker: self.collection_worker.update_status_signal.emit(f"⏳ Starting 2s wait after Claim clicks...") # Log refers to all claim clicks now
                            s_time = time.monotonic()
                            time.sleep(2)
                            e_time = time.monotonic()
                            if self.collection_worker: self.collection_worker.update_status_signal.emit(f"✅ Finished 2s wait (actual: {e_time - s_time:.2f}s).")

                            if not self.app.collection_running: break
                            # Simulate Jump (Spacebar)
                            if self.collection_worker: self.collection_worker.update_status_signal.emit("⌨️ Simulating Jump (Spacebar)...")
                            keyboard_controller.press(pynput_keyboard.Key.space)
                            time.sleep(0.1) 
                            keyboard_controller.release(pynput_keyboard.Key.space)
                            
                            # MODIFIED: Wait 10 seconds after jump before skip
                            if self.collection_worker: self.collection_worker.update_status_signal.emit(f"⏳ Starting 10s wait after jump...")
                            s_time_after_jump = time.monotonic()
                            time.sleep(10) 
                            e_time_after_jump = time.monotonic()
                            if self.collection_worker: self.collection_worker.update_status_signal.emit(f"✅ Finished 10s wait after jump (actual: {e_time_after_jump - s_time_after_jump:.2f}s).")

                        except Exception as e:
                            if self.collection_worker: self.collection_worker.update_status_signal.emit(f"❌ Error clicking Claw Claim or Jumping (AutoIt/Pynput): {e}")
                            time.sleep(1)
                    else:
                        if self.collection_worker: self.collection_worker.update_status_signal.emit(f"⚠️ AutoIt not available. Cannot perform Claw Claim click.")
                        time.sleep(1)
                else:
                    if self.collection_worker: self.collection_worker.update_status_signal.emit("⚠️ Claw Machine Claim coordinates not set, skipping click and jump.")

                if not self.app.collection_running: break

                # 5. Click Skip button
                if self.app.claw_skip_coords and len(self.app.claw_skip_coords) == 2:
                    skip_x, skip_y = self.app.claw_skip_coords
                    if AUTOIT_AVAILABLE:
                        try:
                            if self.collection_worker: self.collection_worker.update_status_signal.emit(f"🖱️ Clicking Claw Machine Skip at ({int(skip_x)}, {int(skip_y)}) via AutoIt...")
                            autoit.mouse_click("left", int(skip_x), int(skip_y), 1, speed=5)

                            if self.collection_worker: self.collection_worker.update_status_signal.emit(f"⏳ Starting 3s wait after Skip click...")
                            s_time = time.monotonic()
                            time.sleep(3)
                            e_time = time.monotonic()
                            if self.collection_worker: self.collection_worker.update_status_signal.emit(f"✅ Finished 3s wait (actual: {e_time - s_time:.2f}s).")
                        except Exception as e:
                            if self.collection_worker: self.collection_worker.update_status_signal.emit(f"❌ Error clicking Claw Skip (AutoIt): {e}")
                            time.sleep(1)
                    else:
                        if self.collection_worker: self.collection_worker.update_status_signal.emit(f"⚠️ AutoIt not available. Cannot perform Claw Skip click.")
                        time.sleep(1)
                else:
                    if self.collection_worker: self.collection_worker.update_status_signal.emit("⚠️ Claw Machine Skip coordinates not set, skipping click.")
                
                # End of Claw Machine specific cycle, loop back
                if self.collection_worker: self.collection_worker.update_status_signal.emit("Claw machine cycle finished, looping...") # Corrected to English
                time.sleep(1) # Small pause before next Claw Machine cycle iteration / or before the new 15s delay

                # ADDED 15s DELAY HERE: This delay occurs AFTER the current cycle is marked as finished 
                # and BEFORE the next cycle's "Start" click effectively begins.
                if not self.app.collection_running: break # Check again before long wait
                if self.collection_worker: self.collection_worker.update_status_signal.emit(f"⏳ Starting 3s inter-cycle wait for Claw Machine...")
                s_time_inter_cycle_wait = time.monotonic()
                time.sleep(3)
                e_time_inter_cycle_wait = time.monotonic()
                if self.collection_worker: self.collection_worker.update_status_signal.emit(f"✅ Finished 3s inter-cycle wait (actual: {e_time_inter_cycle_wait - s_time_inter_cycle_wait:.2f}s).")
                # Loop will now continue to the top, and if still self.app.collection_running, will proceed to "Click Claw Machine Start"

            else:
                # --- Generic Path Logic (existing logic) ---
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

                # Handle teleport (for generic paths)
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
                        self.collection_worker.update_status_signal.emit("⚠️ Teleport coordinates not set or invalid, skipping click for generic path.")
                time.sleep(1)
            # End of generic path or claw machine specific logic, loop continues if self.app.collection_running is true

        if self.collection_worker:
            self.collection_worker.update_status_signal.emit("🚶 Automation loop stopped.") # Renamed from Collection loop stopped
            
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

        # Check if we have a current path selected
        if not self.current_path or self.current_path not in self.available_paths:
            if self.collection_worker:
                self.collection_worker.update_status_signal.emit("❌ No collection path selected.")
            return False
            
        # Get the actions from the selected path
        path_data = self.available_paths[self.current_path]
        actions = path_data.get('actions', [])
        path_name = path_data.get('name', self.current_path)

        if self.collection_worker: 
            self.collection_worker.update_status_signal.emit(f"🚶 Starting {path_name} path...")

        for action in actions:
            if not hasattr(self.app, 'collection_running') or not self.app.collection_running:
                if self.collection_worker:
                    self.collection_worker.update_status_signal.emit("🚶 Collection path interrupted.")
                return False 
                
            if len(action) != 3:
                print(f"Invalid action format: {action}")
                continue
                
            key, press_time, sleep_after = action
            if not press_release(key, press_time, sleep_after):
                return False
                
        if self.collection_worker:
            self.collection_worker.update_status_signal.emit(f"🚶 {path_name} path finished.")
        return True 