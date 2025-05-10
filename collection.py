import time
import pynput
import json
import os
import sys
import shutil
from pynput import keyboard as pynput_keyboard
from PyQt6.QtCore import QThread, pyqtSignal # Make sure QThread and pyqtSignal are imported
from PyQt6.QtWidgets import QMessageBox # Added for potential error popups
from utils import APP_DATA_DIR # New: Import APP_DATA_DIR for screenshot saving
from models import PIL_AVAILABLE, ImageGrab # New: Import PIL_AVAILABLE and ImageGrab for screenshots
from datetime import datetime # New: Import datetime for timestamping screenshots

# Check if AutoIt is available
try:
    import autoit 
    AUTOIT_AVAILABLE = True
except ImportError:
    AUTOIT_AVAILABLE = False
    print("WARNING: pyautoit module not found or AutoIt installation missing. Teleport click will likely fail.")
    print("Install AutoIt from https://www.autoitscript.com/site/autoit/downloads/ and run 'pip install pyautoit'")

class ESpamWorker(QThread):
    """Worker thread to spam the 'E' key."""
    def __init__(self, collection_manager_instance, spam_interval_ms=10):
        super().__init__()
        self.collection_manager = collection_manager_instance
        self.app = self.collection_manager.app # Reference to the main app
        self._is_running = False
        self.spam_interval_s = spam_interval_ms / 1000.0

        # Initialize pynput keyboard controller if AutoIt is not available
        self.keyboard_controller = None
        if not AUTOIT_AVAILABLE:
            try:
                self.keyboard_controller = pynput_keyboard.Controller()
            except Exception as e:
                print(f"Failed to initialize pynput keyboard controller: {e}")
                if self.collection_manager.collection_worker:
                    self.collection_manager.collection_worker.update_status_signal.emit("⚠️ E-Spam: pynput controller failed.")

    def run(self):
        self._is_running = True
        if self.collection_manager.collection_worker: # Use the main collection worker for status updates
            self.collection_manager.collection_worker.update_status_signal.emit("⚙️ E-Spam Worker started.")
        
        while self._is_running and self.app.collection_running: # Check both local flag and global app flag
            try:
                if AUTOIT_AVAILABLE:
                    autoit.send("e")
                elif self.keyboard_controller:
                    self.keyboard_controller.press('e')
                    time.sleep(0.001) # Minimal press time for pynput
                    self.keyboard_controller.release('e')
                else:
                    # This case should ideally not be reached if initialized properly
                    if self.collection_manager.collection_worker:
                        self.collection_manager.collection_worker.update_status_signal.emit("⚠️ E-Spam: No input method available.")
                    break # Stop if no method to send keys
                time.sleep(self.spam_interval_s) 
            except Exception as e:
                if self.collection_manager.collection_worker:
                    self.collection_manager.collection_worker.update_status_signal.emit(f"❌ E-Spam Error: {e}")
                # Optionally, stop on error or just log and continue
                # self.stop() # Uncomment to stop spamming on any error
                time.sleep(0.1) # Pause if error before retrying or stopping

        if self.collection_manager.collection_worker:
            self.collection_manager.collection_worker.update_status_signal.emit("⚙️ E-Spam Worker stopped.")
        self._is_running = False # Ensure flag is reset

    def stop(self):
        self._is_running = False

class CollectionManager:
    """Class for handling collection path functionality in RiftScope"""
    
    # New Constants for Merchant Paths
    BLACK_MARKET_PATH_ID = 'black_market_merchant_path'
    ALIEN_MERCHANT_PATH_ID = 'alien_merchant_path'
    DICE_MERCHANT_PATH_ID = 'dice_merchant_path'
    MERCHANT_RUN_INTERVAL = 1.5 * 60 * 60  # 90 minutes in seconds

    def __init__(self, app=None):
        self.app = app
        self.collection_running = False
        self.teleport_coords = None
        self.claw_skip_coords = None
        self.claw_claim_coords = None
        self.claw_start_coords = None
        self.map_up_arrow_coords = None
        self.map_down_arrow_coords = None
        self.collection_worker = None
        self.initial_navigation_complete_for_session = False
        self.CLAW_MACHINE_PATH_ID = 'clawmachine'  # New: Define as instance variable
        self.shop_item1_coords = None # New
        self.shop_item2_coords = None # New
        self.shop_item3_coords = None # New
        self.currency_display_area_coords = None # New for currency screenshot area
        self.current_path = None  # Explicitly initialize
        self.configured_path_id = None  # To store path_id from config
        self.e_spam_worker = None # Initialize ESpamWorker attribute
        self.merchant_shop_area_coords = None # New for merchant shop screenshots
        
        # New state variables for scheduled merchant run
        self.last_merchant_run_time = 0.0 
        self.initial_macro_merchant_run_done = False
        
        # Get the app data directory for RiftScope
        self.app_data_dir = os.path.join(os.getenv('APPDATA', ''), "RiftScope")
        
        # Define paths directory in appdata
        self.paths_dir = os.path.join(self.app_data_dir, "Paths")
        
        # Bundled paths directory (for when running from executable)
        if getattr(sys, 'frozen', False):
            # If running as bundled executable
            self.bundled_paths_dir = os.path.join(sys._MEIPASS, "Paths")
        else:
            # If running from source
            self.bundled_paths_dir = "Paths"
        
        self.available_paths = {}
        # self.current_path = None # Moved up and initialized explicitly

        # Store configured path ID BEFORE loading available paths
        # This value will be used in load_available_paths to set the current_path
        if app and hasattr(app, 'config') and hasattr(app.config, 'current_path'):
            self.configured_path_id = app.config.current_path
        
        self.load_available_paths() # This will now use self.configured_path_id if set
        
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
            if hasattr(app.config, 'map_up_arrow_coords'):
                self.map_up_arrow_coords = app.config.map_up_arrow_coords
                print(f"Loaded map_up_arrow_coords: {self.map_up_arrow_coords}")
            if hasattr(app.config, 'map_down_arrow_coords'):
                self.map_down_arrow_coords = app.config.map_down_arrow_coords
                print(f"Loaded map_down_arrow_coords: {self.map_down_arrow_coords}")
            if hasattr(app.config, 'shop_item1_coords'): # New
                self.shop_item1_coords = app.config.shop_item1_coords # New
                print(f"Loaded shop_item1_coords: {self.shop_item1_coords}") # New
            if hasattr(app.config, 'shop_item2_coords'): # New
                self.shop_item2_coords = app.config.shop_item2_coords # New
                print(f"Loaded shop_item2_coords: {self.shop_item2_coords}") # New
            if hasattr(app.config, 'shop_item3_coords'): # New
                self.shop_item3_coords = app.config.shop_item3_coords # New
                print(f"Loaded shop_item3_coords: {self.shop_item3_coords}") # New
            if hasattr(app.config, 'currency_display_area_coords'): # New
                self.currency_display_area_coords = app.config.currency_display_area_coords
                if hasattr(self.app, 'currency_display_area_coords'): # app might not be fully initialized
                    self.app.currency_display_area_coords = app.config.currency_display_area_coords
                print(f"Loaded currency_display_area_coords: {self.currency_display_area_coords}")
            if hasattr(app.config, 'merchant_shop_area_coords'): # New
                self.merchant_shop_area_coords = app.config.merchant_shop_area_coords
                if hasattr(self.app, 'merchant_shop_area_coords'): 
                    self.app.merchant_shop_area_coords = app.config.merchant_shop_area_coords
                print(f"Loaded merchant_shop_area_coords: {self.merchant_shop_area_coords}")
            # Existing teleport_coords loading (ensure it's also present or add it)
            if hasattr(app.config, 'teleport_coords') and app.config.teleport_coords:
                self.teleport_coords = app.config.teleport_coords
                if hasattr(self.app, 'teleport_coords'): # app might not be fully initialized
                    self.app.teleport_coords = app.config.teleport_coords
                print(f"Loaded teleport_coords: {self.teleport_coords}")
        
    def load_available_paths(self):
        """Load all available paths from the Paths directory and set current_path appropriately."""
        self.available_paths = {}
        
        # Ensure app data directory and the specific Paths subdirectory within it exist
        os.makedirs(self.app_data_dir, exist_ok=True) 
        os.makedirs(self.paths_dir, exist_ok=True) # self.paths_dir is APPDATA/RiftScope/Paths
                                                 # If it didn't exist, it's created. If it did, this does nothing.

        # Always attempt to copy any missing bundled paths from the source/bundled
        # directory to the appdata paths directory. The _copy_bundled_paths method
        # itself contains logic to only copy files if they don't already exist at the destination.
        if os.path.exists(self.bundled_paths_dir):
            # print(f"Ensuring bundled paths from {self.bundled_paths_dir} are present in {self.paths_dir}") # Optional: for more verbose logging
            self._copy_bundled_paths()
        # else: # Optional: for logging if bundled_paths_dir is missing
            # print(f"Warning: Bundled paths directory not found: {self.bundled_paths_dir}. Cannot synchronize paths.")
        
        # Load paths from appdata directory (self.paths_dir)
        if os.path.exists(self.paths_dir):
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
        
        # Set current_path based on priority:
        # 1. Configured path (if valid and loaded from self.configured_path_id)
        # 2. 'gem_path' (if exists)
        # 3. First available path (if any)
        # 4. None (if no paths available)

        if self.configured_path_id and self.configured_path_id in self.available_paths:
            self.current_path = self.configured_path_id
            print(f"Set current_path to '{self.current_path}' from configuration.")
        elif 'gem_path' in self.available_paths:
            self.current_path = 'gem_path'
            print(f"Set current_path to default 'gem_path'.")
        elif self.available_paths:
            # Fallback to the first loaded path if gem_path isn't available and no valid config path
            self.current_path = next(iter(self.available_paths))
            print(f"Set current_path to first available path: '{self.current_path}'.")
        else:
            # self.current_path should already be None if initialized so, but being explicit.
            self.current_path = None 
            print("No paths available to set as current_path.")
            
        # Update path selector in UI if available
        if hasattr(self.app, 'update_path_selector'):
            self.app.update_path_selector()
    
    def _copy_bundled_paths(self):
        """Copy bundled path files to the appdata paths directory"""
        try:
            if not os.path.exists(self.bundled_paths_dir):
                print(f"Bundled paths directory not found: {self.bundled_paths_dir}")
                return
                
            for filename in os.listdir(self.bundled_paths_dir):
                if filename.endswith('.json'):
                    src_path = os.path.join(self.bundled_paths_dir, filename)
                    dst_path = os.path.join(self.paths_dir, filename)
                    
                    # Only copy if the file doesn't already exist
                    if not os.path.exists(dst_path):
                        shutil.copy2(src_path, dst_path)
                        print(f"Copied path file: {filename}")
        except Exception as e:
            print(f"Error copying bundled paths: {e}")
        
    def save_path_file(self, path_id, path_data):
        """Save a path file to the appdata paths directory"""
        try:
            # Ensure the paths directory exists
            os.makedirs(self.paths_dir, exist_ok=True)
            
            # Save the path file
            file_path = os.path.join(self.paths_dir, f"{path_id}.json")
            with open(file_path, 'w') as f:
                json.dump(path_data, f, indent=4)
            
            # Update available paths
            self.available_paths[path_id] = path_data
            
            # Update UI if available
            if hasattr(self.app, 'update_path_selector'):
                self.app.update_path_selector()
                
            return True
        except Exception as e:
            print(f"Error saving path file {path_id}: {e}")
            return False
        
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

    def start_map_up_arrow_calibration(self):
        """Start calibration process for map up arrow button"""
        self._start_generic_calibration("map_up_arrow")

    def start_map_down_arrow_calibration(self):
        """Start calibration process for map down arrow button"""
        self._start_generic_calibration("map_down_arrow")

    def start_shop_item1_calibration(self): # New
        """Start calibration process for shop item 1 button""" # New
        self._start_generic_calibration("shop_item1") # New

    def start_shop_item2_calibration(self): # New
        """Start calibration process for shop item 2 button""" # New
        self._start_generic_calibration("shop_item2") # New

    def start_shop_item3_calibration(self): # New
        """Start calibration process for shop item 3 button""" # New
        self._start_generic_calibration("shop_item3") # New

    def start_currency_area_calibration(self):
        """Start calibration process for currency display area (rectangle selection)."""
        self._start_generic_area_calibration("currency_display_area")

    def start_merchant_shop_area_calibration(self): # New
        """Start calibration process for merchant shop area (rectangle selection).""" # New
        self._start_generic_area_calibration("merchant_shop_area") # New

    def _start_generic_area_calibration(self, calibration_type_name: str):
        """Helper function to start calibration for a generic area (rectangle)."""
        if hasattr(self.app, 'calibrating') and self.app.calibrating:
            print(f"Calibration already in progress (calibrating for {self.app.calibrating_for}). Cannot start new area calibration for {calibration_type_name}.")
            return

        if hasattr(self.app, 'running') and self.app.running:
            QMessageBox.warning(self.app, "Calibration Error", "Please stop the scanner before calibrating.")
            return

        if hasattr(self.app, 'calibration_overlay') and self.app.calibration_overlay is not None:
            print("Warning: Previous calibration overlay object detected unexpectedly.")
            try:
                if hasattr(self.app.calibration_overlay, 'area_selected'):
                    self.app.calibration_overlay.area_selected.disconnect()
                self.app.calibration_overlay.destroyed.disconnect()
            except (TypeError, RuntimeError):
                pass 
            self.app.calibration_overlay = None

        self.app.calibrating = True
        self.app.calibrating_for = calibration_type_name
        self.app.update_status(f"Starting {calibration_type_name} area calibration...")

        from models import AreaCalibrationOverlay
        
        target_name_readable = calibration_type_name.replace('_', ' ').title()
        overlay_text = f"Drag to select the {target_name_readable}.\nClick and drag from top-left to bottom-right."
        
        new_overlay = AreaCalibrationOverlay(calibration_target_text=overlay_text)

        try:
            new_overlay.area_selected.connect(self.finish_area_calibration)
            new_overlay.destroyed.connect(self.on_calibration_closed)
        except Exception as e:
            print(f"Error connecting signals for new area overlay: {e}")
            self.app.calibrating = False
            self.app.calibrating_for = None
            return

        self.app.calibration_overlay = new_overlay
        self.app.calibration_overlay.show()

    def finish_area_calibration(self, p1, p2):
        """Handle the finish of area calibration when a rectangle (p1, p2) is selected."""
        if not hasattr(self.app, 'calibrating_for') or not self.app.calibrating_for:
            print("Error: finish_area_calibration called but 'calibrating_for' is not set.")
            self.app.calibrating = False
            if hasattr(self.app, 'calibration_overlay') and self.app.calibration_overlay:
                self.app.calibration_overlay.close()
            return

        calibration_type = self.app.calibrating_for
        x1 = min(p1.x(), p2.x())
        y1 = min(p1.y(), p2.y())
        x2 = max(p1.x(), p2.x())
        y2 = max(p1.y(), p2.y())
        coords_rect = (x1, y1, x2, y2)

        if hasattr(self.app, 'calibration_overlay') and self.app.calibration_overlay:
            self.app.update_status(f"{calibration_type.replace('_', ' ').title()} area calibrated: {coords_rect}")

            if calibration_type == "currency_display_area":
                self.app.currency_display_area_coords = coords_rect
                self.currency_display_area_coords = coords_rect
                if hasattr(self.app, 'config'): self.app.config.currency_display_area_coords = coords_rect
                self._update_currency_area_button_text()
            elif calibration_type == "merchant_shop_area":
                self.app.merchant_shop_area_coords = coords_rect
                self.merchant_shop_area_coords = coords_rect
                if hasattr(self.app, 'config'): self.app.config.merchant_shop_area_coords = coords_rect
                self._update_merchant_shop_area_button_text()
            else:
                print(f"Unknown area calibration type: {calibration_type}")

            if hasattr(self.app, 'config'):
                self.app.config.save()

            self.app.calibrating = False
            self.app.calibrating_for = None
            self.app.calibration_overlay.close()
        else:
            self.app.update_status(f"Area calibration for {calibration_type} finished unexpectedly.")
            self.app.calibrating = False
            self.app.calibrating_for = None

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
            elif calibration_type == "map_up_arrow":
                self.app.map_up_arrow_coords = coords
                self.map_up_arrow_coords = coords
                if hasattr(self.app, 'config'): self.app.config.map_up_arrow_coords = coords
                self._update_map_up_arrow_button_text()
            elif calibration_type == "map_down_arrow":
                self.app.map_down_arrow_coords = coords
                self.map_down_arrow_coords = coords
                if hasattr(self.app, 'config'): self.app.config.map_down_arrow_coords = coords
                self._update_map_down_arrow_button_text()
            elif calibration_type == "shop_item1": # New
                self.app.shop_item1_coords = coords # New
                self.shop_item1_coords = coords # New
                if hasattr(self.app, 'config'): self.app.config.shop_item1_coords = coords # New
                self._update_shop_item1_button_text() # New
            elif calibration_type == "shop_item2": # New
                self.app.shop_item2_coords = coords # New
                self.shop_item2_coords = coords # New
                if hasattr(self.app, 'config'): self.app.config.shop_item2_coords = coords # New
                self._update_shop_item2_button_text() # New
            elif calibration_type == "shop_item3": # New
                self.app.shop_item3_coords = coords # New
                self.shop_item3_coords = coords # New
                if hasattr(self.app, 'config'): self.app.config.shop_item3_coords = coords # New
                self._update_shop_item3_button_text() # New
            elif calibration_type == "currency_display_area":
                self.app.currency_display_area_coords = coords_rect
                self.currency_display_area_coords = coords_rect
                if hasattr(self.app, 'config'): self.app.config.currency_display_area_coords = coords_rect
                self._update_currency_area_button_text() # New method to update button text
            elif calibration_type == "merchant_shop_area": # New
                self.app.merchant_shop_area_coords = coords_rect # New
                self.merchant_shop_area_coords = coords_rect # New
                if hasattr(self.app, 'config'): self.app.config.merchant_shop_area_coords = coords_rect # New
                self._update_merchant_shop_area_button_text() # New
            else:
                print(f"Unknown point calibration type: {calibration_type}") # Clarified message

            if hasattr(self.app, 'config'):
                self.app.config.save()
            else: # Fallback if app.config isn't directly available for saving
                if hasattr(self.app, 'save_config'):
                    self.app.save_config()


            self.app.calibrating = False
            self.app.calibrating_for = None
            self.app.calibration_overlay.close()
        else:
            self.app.update_status(f"Calibration for {calibration_type} finished unexpectedly.")
            self.app.calibrating = False
            self.app.calibrating_for = None

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
                self.app.calibrate_button.setText(f"Calibrate Teleport")
                if label_widget:
                    label_widget.setText(f"Coords: ({x}, {y})")
                    label_widget.setVisible(True)
            else:
                self.app.calibrate_button.setText("Calibrate Teleport")
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
                self.app.calibrate_claw_skip_button.setText(f"Calibrate Skip")
                if label_widget:
                    label_widget.setText(f"Coords: ({x}, {y})")
                    label_widget.setVisible(True)
            else:
                self.app.calibrate_claw_skip_button.setText("Calibrate Skip")
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
                self.app.calibrate_claw_claim_button.setText(f"Calibrate Claim")
                if label_widget:
                    label_widget.setText(f"Coords: ({x}, {y})")
                    label_widget.setVisible(True)
            else:
                self.app.calibrate_claw_claim_button.setText("Calibrate Claim")
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
                self.app.calibrate_claw_start_button.setText(f"Calibrate Start")
                if label_widget:
                    label_widget.setText(f"Coords: ({x}, {y})")
                    label_widget.setVisible(True)
            else:
                self.app.calibrate_claw_start_button.setText("Calibrate Start")
                if label_widget:
                    label_widget.setText("")
                    label_widget.setVisible(False)

    def _update_map_up_arrow_button_text(self):
        """Update the map up arrow calibrate button text."""
        if hasattr(self.app, 'calibrate_map_up_arrow_button'):
            coords_tuple = getattr(self.app, 'map_up_arrow_coords', None) or self.map_up_arrow_coords
            label_widget = getattr(self.app, 'map_up_arrow_coords_label', None)

            if coords_tuple and len(coords_tuple) == 2:
                x, y = coords_tuple
                self.app.calibrate_map_up_arrow_button.setText(f"Calibrate Up")
                if label_widget:
                    label_widget.setText(f"Coords: ({x}, {y})")
                    label_widget.setVisible(True)
            else:
                self.app.calibrate_map_up_arrow_button.setText("Calibrate Up")
                if label_widget:
                    label_widget.setText("")
                    label_widget.setVisible(False)

    def _update_map_down_arrow_button_text(self):
        """Update the map down arrow calibrate button text."""
        if hasattr(self.app, 'calibrate_map_down_arrow_button'):
            coords_tuple = getattr(self.app, 'map_down_arrow_coords', None) or self.map_down_arrow_coords
            label_widget = getattr(self.app, 'map_down_arrow_coords_label', None)

            if coords_tuple and len(coords_tuple) == 2:
                x, y = coords_tuple
                self.app.calibrate_map_down_arrow_button.setText(f"Calibrate Down")
                if label_widget:
                    label_widget.setText(f"Coords: ({x}, {y})")
                    label_widget.setVisible(True)
            else:
                self.app.calibrate_map_down_arrow_button.setText("Calibrate Down")
                if label_widget:
                    label_widget.setText("")
                    label_widget.setVisible(False)

    def _update_shop_item1_button_text(self): # New
        """Update the shop item 1 calibrate button text.""" # New
        if hasattr(self.app, 'calibrate_shop_item1_button'): # New
            coords_tuple = getattr(self.app, 'shop_item1_coords', None) or self.shop_item1_coords # New
            label_widget = getattr(self.app, 'shop_item1_coords_label', None) # New

            if coords_tuple and len(coords_tuple) == 2: # New
                x, y = coords_tuple # New
                self.app.calibrate_shop_item1_button.setText(f"Calibrate Item 1") # New
                if label_widget: # New
                    label_widget.setText(f"Coords: ({x}, {y})") # New
                    label_widget.setVisible(True) # New
            else: # New
                self.app.calibrate_shop_item1_button.setText("Calibrate Item 1") # New
                if label_widget: # New
                    label_widget.setText("") # New
                    label_widget.setVisible(False) # New

    def _update_shop_item2_button_text(self): # New
        """Update the shop item 2 calibrate button text.""" # New
        if hasattr(self.app, 'calibrate_shop_item2_button'): # New
            coords_tuple = getattr(self.app, 'shop_item2_coords', None) or self.shop_item2_coords # New
            label_widget = getattr(self.app, 'shop_item2_coords_label', None) # New

            if coords_tuple and len(coords_tuple) == 2: # New
                x, y = coords_tuple # New
                self.app.calibrate_shop_item2_button.setText(f"Calibrate Item 2") # New
                if label_widget: # New
                    label_widget.setText(f"Coords: ({x}, {y})") # New
                    label_widget.setVisible(True) # New
            else: # New
                self.app.calibrate_shop_item2_button.setText("Calibrate Item 2") # New
                if label_widget: # New
                    label_widget.setText("") # New
                    label_widget.setVisible(False) # New

    def _update_shop_item3_button_text(self): # New
        """Update the shop item 3 calibrate button text.""" # New
        if hasattr(self.app, 'calibrate_shop_item3_button'): # New
            coords_tuple = getattr(self.app, 'shop_item3_coords', None) or self.shop_item3_coords # New
            label_widget = getattr(self.app, 'shop_item3_coords_label', None) # New

            if coords_tuple and len(coords_tuple) == 2: # New
                x, y = coords_tuple # New
                self.app.calibrate_shop_item3_button.setText(f"Calibrate Item 3") # New
                if label_widget: # New
                    label_widget.setText(f"Coords: ({x}, {y})") # New
                    label_widget.setVisible(True) # New
            else: # New
                self.app.calibrate_shop_item3_button.setText("Calibrate Item 3") # New
                if label_widget: # New
                    label_widget.setText("") # New
                    label_widget.setVisible(False) # New

    def _update_currency_area_button_text(self): # New
        """Update the currency display area calibrate button text.""" # New
        if hasattr(self.app, 'calibrate_currency_area_button'): # New
            coords_tuple = getattr(self.app, 'currency_display_area_coords', None) or self.currency_display_area_coords # New
            label_widget = getattr(self.app, 'currency_area_coords_label', None) # New

            if coords_tuple and len(coords_tuple) == 4: # Expecting (x1, y1, x2, y2)
                x1, y1, x2, y2 = coords_tuple # New
                self.app.calibrate_currency_area_button.setText(f"Calibrate Currency Area") # New
                if label_widget: # New
                    label_widget.setText(f"Area: ({x1},{y1})-({x2},{y2})") # New
                    label_widget.setVisible(True) # New
            else: # New
                self.app.calibrate_currency_area_button.setText("Calibrate Currency Area") # New
                if label_widget: # New
                    label_widget.setText("") # New
                    label_widget.setVisible(False) # New

    def _update_merchant_shop_area_button_text(self): # New
        """Update the merchant shop area calibrate button text.""" # New
        if hasattr(self.app, 'calibrate_merchant_shop_area_button'): # New
            coords_tuple = getattr(self.app, 'merchant_shop_area_coords', None) or self.merchant_shop_area_coords # New
            label_widget = getattr(self.app, 'merchant_shop_area_coords_label', None) # New

            if coords_tuple and len(coords_tuple) == 4: # Expecting (x1, y1, x2, y2)
                x1, y1, x2, y2 = coords_tuple # New
                self.app.calibrate_merchant_shop_area_button.setText(f"Calibrate Merchant Shop Area") # New
                if label_widget: # New
                    label_widget.setText(f"Area: ({x1},{y1})-({x2},{y2})") # New
                    label_widget.setVisible(True) # New
            else: # New
                self.app.calibrate_merchant_shop_area_button.setText("Calibrate Merchant Shop Area") # New
                if label_widget: # New
                    label_widget.setText("") # New
                    label_widget.setVisible(False) # New

    def update_all_calibration_buttons_text(self):
        """Updates text for all calibration-related buttons."""
        self._update_calibrate_button_text()
        self._update_claw_skip_button_text()
        self._update_claw_claim_button_text()
        self._update_claw_start_button_text()
        self._update_map_up_arrow_button_text()
        self._update_map_down_arrow_button_text()
        self._update_shop_item1_button_text()
        self._update_shop_item2_button_text()
        self._update_shop_item3_button_text()
        self._update_currency_area_button_text() # New
        self._update_merchant_shop_area_button_text() # New
        
    def _perform_initial_map_navigation(self):
        """Performs the initial sequence of map arrow clicks and teleport."""
        if not self.collection_worker:
            print("Error: _perform_initial_map_navigation called without collection_worker.")
            if hasattr(self.app, 'update_status'): self.app.update_status("❌ Error: Initial navigation failed (no worker).")
            return

        self.collection_worker.update_status_signal.emit("🤖 Performing initial map navigation...")

        if not AUTOIT_AVAILABLE:
            self.collection_worker.update_status_signal.emit("⚠️ AutoIt not available. Skipping initial map navigation clicks.")
            self.initial_navigation_complete_for_session = True
            return

        # Click Map Down Arrow 10 times
        if self.app.map_down_arrow_coords and len(self.app.map_down_arrow_coords) == 2:
            self.collection_worker.update_status_signal.emit("🖱️ Clicking Map Down Arrow 10 times...")
            dx, dy = self.app.map_down_arrow_coords
            for i in range(10):
                if not self.app.collection_running: return
                try:
                    autoit.mouse_click("left", int(dx), int(dy), 1, speed=10)
                    time.sleep(0.2)
                except Exception as e:
                    self.collection_worker.update_status_signal.emit(f"❌ Error clicking Map Down Arrow: {e}")
                    break
            self.collection_worker.update_status_signal.emit("✅ Map Down Arrow clicks finished.")
        else:
            self.collection_worker.update_status_signal.emit("⚠️ Map Down Arrow coordinates not set. Skipping.")

        if not self.app.collection_running: return

        # Conditional Map Up Arrow clicks
        num_up_clicks = 0
        if self.current_path == 'gem_path':
            num_up_clicks = 5
        elif self.current_path in ['clawmachine', 'ticket_grind_path']:
            num_up_clicks = 10

        if num_up_clicks > 0 and self.app.map_up_arrow_coords and len(self.app.map_up_arrow_coords) == 2:
            self.collection_worker.update_status_signal.emit(f"🖱️ Clicking Map Up Arrow {num_up_clicks} times...")
            ux, uy = self.app.map_up_arrow_coords
            for i in range(num_up_clicks):
                if not self.app.collection_running: return
                try:
                    autoit.mouse_click("left", int(ux), int(uy), 1, speed=10)
                    time.sleep(0.2)
                except Exception as e:
                    self.collection_worker.update_status_signal.emit(f"❌ Error clicking Map Up Arrow: {e}")
                    break
            self.collection_worker.update_status_signal.emit("✅ Map Up Arrow clicks finished.")
        elif num_up_clicks > 0:
            self.collection_worker.update_status_signal.emit("⚠️ Map Up Arrow coordinates not set. Skipping.")
        
        if not self.app.collection_running: return

        # Teleport
        if self.app.teleport_coords and len(self.app.teleport_coords) == 2:
            self.collection_worker.update_status_signal.emit("🖱️ Clicking Teleport button...")
            tx, ty = self.app.teleport_coords
            try:
                autoit.mouse_click("left", int(tx), int(ty), 1, speed=5)
                self.collection_worker.update_status_signal.emit("⏳ Waiting 3s after teleport...")
                time.sleep(3)
                self.collection_worker.update_status_signal.emit("✅ Teleport click and wait finished.")
            except Exception as e:
                self.collection_worker.update_status_signal.emit(f"❌ Error clicking Teleport: {e}")
        else:
            self.collection_worker.update_status_signal.emit("⚠️ Teleport coordinates not set. Skipping initial teleport.")
        
        # New: Execute one-time travel path for claw machine after initial teleport
        if self.app.collection_running and self.current_path == self.CLAW_MACHINE_PATH_ID: # Check if still running and current path is claw
            self.collection_worker.update_status_signal.emit("🤖 Executing initial travel path to Claw Machine...")
            original_path_for_claw_machine_loop = self.current_path # Should be 'clawmachine'
            travel_path_id = 'clawmachine_path' # The ID of the JSON file for travel

            if travel_path_id in self.available_paths:
                self.current_path = travel_path_id # Temporarily switch to the travel path
                path_completed_to_claw = self._execute_collection_path()
                if not path_completed_to_claw:
                    self.collection_worker.update_status_signal.emit("⚠️ Initial travel to Claw Machine failed or was interrupted.")
                else:
                    self.collection_worker.update_status_signal.emit("✅ Initial travel to Claw Machine finished.")
            else:
                self.collection_worker.update_status_signal.emit(f"⚠️ Travel path '{travel_path_id}.json' not found. Skipping travel to Claw Machine.")
            
            self.current_path = original_path_for_claw_machine_loop # Restore to 'clawmachine' for the main operational loop
            self.collection_worker.update_status_signal.emit(f"🤖 Current path restored to '{self.current_path}' for Claw Machine operations.")

        self.collection_worker.update_status_signal.emit("🤖 Initial map navigation sequence finished.")
        self.initial_navigation_complete_for_session = True

    def _click_shop_items(self):
        """Clicks the 3 calibrated shop items, 15 times each over ~2s, with delays."""
        if not self.app or not self.collection_worker:
            print("Error: _click_shop_items called without app or worker.")
            return

        shop_items_coords = [
            self.app.shop_item1_coords,
            self.app.shop_item2_coords,
            self.app.shop_item3_coords
        ]
        item_names = ["Shop Item 1", "Shop Item 2", "Shop Item 3"]
        num_clicks_per_item = 60 # Changed from 40 to 60 (20 clicks/sec * 3 sec)
        duration_per_item_sec = 3.0 # Changed from 2.0 to 3.0
        delay_between_clicks_sec = 1.0 / 20.0 # 20 clicks per second

        for i, coords in enumerate(shop_items_coords):
            if not self.app.collection_running: return
            item_name = item_names[i]
            if coords and len(coords) == 2:
                self.collection_worker.update_status_signal.emit(f"🖱️ Clicking {item_name} {num_clicks_per_item} times over ~{duration_per_item_sec}s...")
                x, y = coords
                try:
                    for click_num in range(num_clicks_per_item):
                        if not self.app.collection_running: return
                        if AUTOIT_AVAILABLE:
                            autoit.mouse_click("left", int(x), int(y), 1, speed=10) # Speed 10 is fast
                        else:
                            self.collection_worker.update_status_signal.emit(f"⚠️ AutoIt not available. Cannot click {item_name}.")
                            break 
                        if click_num < num_clicks_per_item - 1:
                            time.sleep(delay_between_clicks_sec)
                    self.collection_worker.update_status_signal.emit(f"✅ {item_name} clicks finished.")
                except Exception as e:
                    self.collection_worker.update_status_signal.emit(f"❌ Error clicking {item_name}: {e}")
            else:
                self.collection_worker.update_status_signal.emit(f"⚠️ {item_name} coordinates not set. Skipping clicks.")
            
            if i < len(shop_items_coords) - 1:
                if not self.app.collection_running: return
                self.collection_worker.update_status_signal.emit(f"⏳ Waiting 1s before next shop item...")
                time.sleep(1)
        self.collection_worker.update_status_signal.emit("🛍️ All shop item clicks finished for this merchant.")

    def _perform_full_merchant_run_sequence(self, is_initial_run_at_macro_start=False):
        """Performs the entire 3-merchant run sequence."""
        if not self.app or not self.collection_worker or not AUTOIT_AVAILABLE:
            if self.collection_worker: self.collection_worker.update_status_signal.emit("⚠️ Merchant run cannot start: Missing app, worker, or AutoIt.")
            return

        self.collection_worker.update_status_signal.emit("🤖 Starting Scheduled Merchant Run Sequence...")
        self.last_merchant_run_time = time.monotonic() # Reset timer at the start of the sequence

        original_current_path = self.current_path # Save original path
        original_current_path_name = "Unknown Path"
        if original_current_path and original_current_path in self.available_paths:
            original_current_path_name = self.available_paths[original_current_path].get('name', original_current_path)

        # --- Stage 0: Initial Map Nav (only if is_initial_run_at_macro_start is True) ---
        if is_initial_run_at_macro_start:
            self.collection_worker.update_status_signal.emit("🗺️ Performing initial map navigation for merchant run...")
            if self.app.map_down_arrow_coords and len(self.app.map_down_arrow_coords) == 2:
                dx, dy = self.app.map_down_arrow_coords
                for _ in range(10):
                    if not self.app.collection_running: return
                    autoit.mouse_click("left", int(dx), int(dy), 1, speed=10); time.sleep(0.2)
            else: self.collection_worker.update_status_signal.emit("⚠️ Map Down Arrow not calibrated for merchant run.")

            if self.app.map_up_arrow_coords and len(self.app.map_up_arrow_coords) == 2:
                ux, uy = self.app.map_up_arrow_coords
                for _ in range(4):
                    if not self.app.collection_running: return
                    autoit.mouse_click("left", int(ux), int(uy), 1, speed=10); time.sleep(0.2)
            else: self.collection_worker.update_status_signal.emit("⚠️ Map Up Arrow not calibrated for merchant run.")
            
            if self.app.teleport_coords and len(self.app.teleport_coords) == 2:
                tx, ty = self.app.teleport_coords
                autoit.mouse_click("left", int(tx), int(ty), 1, speed=5); time.sleep(3)
            else: self.collection_worker.update_status_signal.emit("⚠️ Teleport not calibrated for merchant run.")
        if not self.app.collection_running: return

        # --- Stage 1: Black Market Merchant ---
        self.collection_worker.update_status_signal.emit("🏪 Starting Black Market Merchant...")
        self.current_path = self.BLACK_MARKET_PATH_ID
        if self.current_path in self.available_paths:
            path_completed = self._execute_collection_path()
            if path_completed and self.app.collection_running:
                self._click_shop_items()
                if self.app.collection_running: # Check after clicks
                    self._send_merchant_purchase_webhook("Black Market Merchant", self.BLACK_MARKET_PATH_ID)
                    if self.app.collection_running: # Check after webhook attempt
                        autoit.send("m"); time.sleep(1)
        else: self.collection_worker.update_status_signal.emit(f"⚠️ Path {self.BLACK_MARKET_PATH_ID} not found.")
        if not self.app.collection_running: self.current_path = original_current_path; return

        # --- Stage 2: Alien Merchant ---
        self.collection_worker.update_status_signal.emit("👽 Starting Alien Merchant...")
        autoit.send("m"); time.sleep(1)
        if self.app.map_up_arrow_coords and len(self.app.map_up_arrow_coords) == 2:
            ux, uy = self.app.map_up_arrow_coords
            autoit.mouse_click("left", int(ux), int(uy), 1, speed=10); time.sleep(0.2)
        else: self.collection_worker.update_status_signal.emit("⚠️ Map Up Arrow not calibrated for Alien Merchant.")
        if self.app.teleport_coords and len(self.app.teleport_coords) == 2:
            tx, ty = self.app.teleport_coords
            autoit.mouse_click("left", int(tx), int(ty), 1, speed=5); time.sleep(3)
        else: self.collection_worker.update_status_signal.emit("⚠️ Teleport not calibrated for Alien Merchant.")
        if not self.app.collection_running: self.current_path = original_current_path; return
        
        self.current_path = self.ALIEN_MERCHANT_PATH_ID
        if self.current_path in self.available_paths:
            path_completed = self._execute_collection_path()
            if path_completed and self.app.collection_running:
                self._click_shop_items()
                if self.app.collection_running:
                    self._send_merchant_purchase_webhook("Alien Merchant", self.ALIEN_MERCHANT_PATH_ID)
                    if self.app.collection_running:
                        autoit.send("m"); time.sleep(1)
        else: self.collection_worker.update_status_signal.emit(f"⚠️ Path {self.ALIEN_MERCHANT_PATH_ID} not found.")
        if not self.app.collection_running: self.current_path = original_current_path; return

        # --- Stage 3: Dice Merchant ---
        self.collection_worker.update_status_signal.emit("🎲 Starting Dice Merchant...")
        autoit.send("m"); time.sleep(1) # Ensure 1s wait after M
        if self.app.map_up_arrow_coords and len(self.app.map_up_arrow_coords) == 2:
            ux, uy = self.app.map_up_arrow_coords
            # Changed from 5 clicks to 1 click for Dice Merchant
            if not self.app.collection_running: self.current_path = original_current_path; return
            autoit.mouse_click("left", int(ux), int(uy), 1, speed=10); time.sleep(0.2)
            self.collection_worker.update_status_signal.emit("🗺️ Clicked Map Up Arrow once for Dice Merchant.")
        else: self.collection_worker.update_status_signal.emit("⚠️ Map Up Arrow not calibrated for Dice Merchant.")
        if self.app.teleport_coords and len(self.app.teleport_coords) == 2:
            tx, ty = self.app.teleport_coords
            autoit.mouse_click("left", int(tx), int(ty), 1, speed=5); time.sleep(3)
        else: self.collection_worker.update_status_signal.emit("⚠️ Teleport not calibrated for Dice Merchant.")
        if not self.app.collection_running: self.current_path = original_current_path; return

        self.current_path = self.DICE_MERCHANT_PATH_ID
        if self.current_path in self.available_paths:
            path_completed = self._execute_collection_path()
            if path_completed and self.app.collection_running:
                self._click_shop_items()
                if self.app.collection_running: # Check if still running after shop clicks
                    self._send_merchant_purchase_webhook("Dice Merchant", self.DICE_MERCHANT_PATH_ID)
                    # The existing M press for Dice merchant after purchase is already here, so no need to add another explicitly
                    if self.app.collection_running:
                        self.collection_worker.update_status_signal.emit("⌨️ Pressing 'M' after Dice Merchant purchases...")
                        autoit.send("m")
                        time.sleep(1) # Wait 1s after M press
        else: self.collection_worker.update_status_signal.emit(f"⚠️ Path {self.DICE_MERCHANT_PATH_ID} not found.")
        
        # Webhook for returning from merchant run
        if self.app.collection_running: # Only send if macro wasn't stopped
            self.app.send_webhook(
                title="🗺️ Returning to Main Path",
                description=f"Finished merchant run. Returning to '{original_current_path_name}'.",
                color=0x3498db # A blue color
            )

        self.current_path = original_current_path # Restore original path
        self.collection_worker.update_status_signal.emit("✅ Scheduled Merchant Run Sequence Finished.")

    def _send_merchant_purchase_webhook(self, merchant_name, path_id):
        """Helper to take screenshot and send webhook for merchant purchases."""
        if not self.app or not self.collection_worker:
            return

        filepath = None
        status_message = f"🛍️ Items purchased from {merchant_name}."

        if hasattr(self.app, 'merchant_shop_area_coords') and self.app.merchant_shop_area_coords and \
           len(self.app.merchant_shop_area_coords) == 4 and PIL_AVAILABLE:
            try:
                self.collection_worker.update_status_signal.emit(f"📸 Taking screenshot for {merchant_name}...")
                bbox = self.app.merchant_shop_area_coords # (x1, y1, x2, y2)
                screenshot = ImageGrab.grab(bbox=bbox)
                
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                # Sanitize path_id for filename
                safe_path_id = path_id.replace(" ", "_").replace("/", "_").replace("\\", "_") 
                filename = f"merchant_{safe_path_id}_{timestamp}.png"
                # Ensure APP_DATA_DIR is defined (should be imported from utils)
                filepath = os.path.join(APP_DATA_DIR, filename) 
                screenshot.save(filepath, "PNG")
                self.collection_worker.update_status_signal.emit(f"📸 Screenshot for {merchant_name} saved: {filename}")
                status_message = f"Items purchased from {merchant_name}. See screenshot for details."
            except Exception as e:
                self.collection_worker.update_status_signal.emit(f"❌ Error taking screenshot for {merchant_name}: {e}")
                filepath = None # Ensure filepath is None if screenshot fails
        elif not (hasattr(self.app, 'merchant_shop_area_coords') and self.app.merchant_shop_area_coords and len(self.app.merchant_shop_area_coords) == 4):
            self.collection_worker.update_status_signal.emit(f"⚠️ Merchant shop area not calibrated. Skipping screenshot for {merchant_name}.")
        elif not PIL_AVAILABLE:
            self.collection_worker.update_status_signal.emit(f"⚠️ Pillow (PIL) not available. Skipping screenshot for {merchant_name}.")

        self.app.send_webhook(
            title=f"🛍️ {merchant_name} Purchases",
            description=status_message,
            color=0x58D68D, # A greenish color
            file_path=filepath # Will be None if screenshot failed or wasn't taken
        )
        # File deletion is handled by send_webhook if filepath is provided and it's a temp currency/merchant file

    def run_collection_loop(self):
        """Main collection path loop worker function"""
        if not hasattr(self.app, 'collection_running'): # Should be app.automation_running if we rename state
            return
            
        # Perform initial merchant run if enabled and not done yet
        if self.app.config.enable_scheduled_merchant_run and \
           self.current_path != self.CLAW_MACHINE_PATH_ID and \
           not self.initial_macro_merchant_run_done:
            self._perform_full_merchant_run_sequence(is_initial_run_at_macro_start=True)
            self.initial_macro_merchant_run_done = True # Mark as done for this macro session
            if not self.app.collection_running: # Check if stopped during merchant run
                if self.collection_worker: self.collection_worker.update_status_signal.emit("🚶 Automation loop stopped during initial merchant run.")
                if self.e_spam_worker and self.e_spam_worker.isRunning(): self.e_spam_worker.stop(); self.e_spam_worker.wait()
                self.e_spam_worker = None
                return
        
        # Perform initial navigation if not done yet for this session (standard, non-merchant)
        if self.app.collection_running and not self.initial_navigation_complete_for_session and \
           (not self.app.config.enable_scheduled_merchant_run or self.initial_macro_merchant_run_done):
            # This standard initial navigation only runs if merchant run is disabled, OR if it's enabled AND already done its initial part.
            self._perform_initial_map_navigation()
            if not self.app.collection_running:
                if self.collection_worker: self.collection_worker.update_status_signal.emit("🚶 Automation loop stopped during initial navigation.")
                if self.e_spam_worker and self.e_spam_worker.isRunning(): self.e_spam_worker.stop(); self.e_spam_worker.wait()
                self.e_spam_worker = None
                return
        
        keyboard_controller = pynput_keyboard.Controller()
        # Path ID for the special claw machine logic
        # CLAW_MACHINE_PATH_ID = 'clawmachine' # Assuming the ID in Paths/clawmachine.json is 'clawmachine' # Removed local definition

        while self.app.collection_running:
            is_claw_machine_path = self.current_path == self.CLAW_MACHINE_PATH_ID

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

                # Press 'M' to open map
                map_opened_successfully = False
                if AUTOIT_AVAILABLE:
                    try:
                        if self.collection_worker:
                            self.collection_worker.update_status_signal.emit("⌨️ Pressing 'M' (AutoIt) to open map...")
                        autoit.send("m")
                        map_opened_successfully = True
                        if self.collection_worker:
                            self.collection_worker.update_status_signal.emit("✅ 'M' key pressed (AutoIt).")
                    except Exception as e:
                        if self.collection_worker:
                            self.collection_worker.update_status_signal.emit(f"❌ Error pressing 'M' (AutoIt): {e}. Falling back to pynput.")
                        # Fallback to pynput if AutoIt fails
                        try:
                            if self.collection_worker:
                                self.collection_worker.update_status_signal.emit("⌨️ Pressing 'M' (pynput fallback) to open map...")
                            keyboard_controller.press('m')
                            time.sleep(0.1) 
                            keyboard_controller.release('m')
                            map_opened_successfully = True
                            if self.collection_worker:
                                self.collection_worker.update_status_signal.emit("✅ 'M' key pressed (pynput fallback).")
                        except Exception as e_pynput:
                            if self.collection_worker:
                                self.collection_worker.update_status_signal.emit(f"❌ Error pressing 'M' (pynput fallback): {e_pynput}")
                else: # AutoIt not available, use pynput directly
                    try:
                        if self.collection_worker:
                            self.collection_worker.update_status_signal.emit("⌨️ Pressing 'M' (pynput) to open map...")
                        keyboard_controller.press('m')
                        time.sleep(0.1) 
                        keyboard_controller.release('m')
                        map_opened_successfully = True
                        if self.collection_worker:
                            self.collection_worker.update_status_signal.emit("✅ 'M' key pressed (pynput).")
                    except Exception as e:
                        if self.collection_worker:
                            self.collection_worker.update_status_signal.emit(f"❌ Error pressing 'M' (pynput): {e}")
                
                # Brief pause regardless of M press success, then proceed to teleport
                # The 'continue' that was here previously would skip teleport on M-press error, which is not desired.
                time.sleep(0.5) # Small pause after M-press attempt

                # Proceed to teleport even if M key press had an issue, 
                # but maybe log if it wasn't successful for debugging.
                if not map_opened_successfully and self.collection_worker:
                    self.collection_worker.update_status_signal.emit("⚠️ Map may not have opened due to 'M' key press issue. Proceeding with teleport.")

                # New: Conditional Map Up Arrow clicks for Ticket Grind Path
                if self.app.collection_running and self.current_path == 'ticket_grind_path':
                    if self.app.map_up_arrow_coords and len(self.app.map_up_arrow_coords) == 2:
                        self.collection_worker.update_status_signal.emit("🎟️ Ticket Path: Clicking Map Up Arrow 5 times...")
                        ux, uy = self.app.map_up_arrow_coords
                        for i in range(5):
                            if not self.app.collection_running: break
                            try:
                                autoit.mouse_click("left", int(ux), int(uy), 1, speed=10)
                                time.sleep(0.2)
                            except Exception as e:
                                self.collection_worker.update_status_signal.emit(f"❌ Error clicking Map Up Arrow (Ticket Path): {e}")
                                break
                        if self.app.collection_running: # Only emit if loop wasn't broken by stop or error
                             self.collection_worker.update_status_signal.emit("✅ Ticket Path: Map Up Arrow clicks finished.")
                    else:
                        self.collection_worker.update_status_signal.emit("⚠️ Ticket Path: Map Up Arrow coordinates not set. Skipping up arrow clicks.")

                # Wait before teleport
                if self.collection_worker:
                    self.collection_worker.update_status_signal.emit("⏳ Waiting before teleport...")
                time.sleep(2) # This was the original wait time after 'M' before teleport logic
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

            # Scheduled Merchant Run Check (after a full cycle of the main path)
            if self.app.collection_running and self.app.config.enable_scheduled_merchant_run and \
               self.current_path != self.CLAW_MACHINE_PATH_ID and \
               (time.monotonic() - self.last_merchant_run_time > self.MERCHANT_RUN_INTERVAL):
                self.collection_worker.update_status_signal.emit("⏰ Time for scheduled merchant run.")
                self._perform_full_merchant_run_sequence(is_initial_run_at_macro_start=False)
                if not self.app.collection_running: # Check if stopped during merchant run
                    break # Exit while loop
            # Loop continues if self.app.collection_running is true

        if self.collection_worker:
            self.collection_worker.update_status_signal.emit("🚶 Automation loop stopped.") # Renamed from Collection loop stopped
            
        # Ensure E-Spam worker is stopped if it was running
        if self.e_spam_worker and self.e_spam_worker.isRunning():
            self.e_spam_worker.stop()
            self.e_spam_worker.wait() # Wait for thread to finish
        self.e_spam_worker = None
            
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

        # Start E-Spamming if conditions are met
        should_spam_e = (
            self.current_path == 'ticket_grind_path' and 
            hasattr(self.app, 'config') and 
            getattr(self.app.config, 'spam_e_for_ticket_path', False)
        )
        
        spam_stopped_early = False # New flag

        if should_spam_e:
            if not self.e_spam_worker or not self.e_spam_worker.isRunning():
                self.e_spam_worker = ESpamWorker(self) # Use ESpamWorker
                self.e_spam_worker.start()

        # Calculate total path duration for early stop logic
        total_path_duration_s = 0
        if should_spam_e and actions: # Only calculate if needed and actions exist
            total_path_duration_s = sum((action[1] + action[2] for action in actions if len(action) == 3)) / 1000.0
        
        elapsed_time_s = 0.0

        for action in actions:
            if not hasattr(self.app, 'collection_running') or not self.app.collection_running:
                if self.collection_worker:
                    self.collection_worker.update_status_signal.emit("🚶 Collection path interrupted.")
                
                # Stop E-Spam worker if it's running
                if self.e_spam_worker and self.e_spam_worker.isRunning():
                    self.e_spam_worker.stop()
                return False 
                
            if len(action) != 3:
                print(f"Invalid action format: {action}")
                continue
                
            key, press_time, sleep_after = action
            
            # Action execution
            if not press_release(key, press_time, sleep_after):
                return False # Path interrupted during press_release
            
            # Update elapsed time
            if should_spam_e:
                action_duration_s = (press_time + sleep_after) / 1000.0
                elapsed_time_s += action_duration_s

                # Check if E-Spam needs to be stopped early
                if self.e_spam_worker and self.e_spam_worker.isRunning() and not spam_stopped_early:
                    if total_path_duration_s - elapsed_time_s <= 7.0:
                        if self.collection_worker:
                            self.collection_worker.update_status_signal.emit("⚙️ Stopping E-Spam (nearing end of path)...")
                        self.e_spam_worker.stop()
                        spam_stopped_early = True
                        
        if self.collection_worker:
            self.collection_worker.update_status_signal.emit(f"🚶 {path_name} path finished.")
        
        # Stop E-Spam worker if it was started for this path execution and not stopped early
        if should_spam_e and self.e_spam_worker and self.e_spam_worker.isRunning() and not spam_stopped_early:
            if self.collection_worker:
                self.collection_worker.update_status_signal.emit("⚙️ Stopping E-Spam (path finished normally).")
            self.e_spam_worker.stop()

        return True 