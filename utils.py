#!/usr/bin/env python3
# RiftScope - Utility Functions
# GitHub: https://github.com/cresqnt-sys/RiftScope

import os
import sys
import json
import time
import random
import platform
import subprocess
from datetime import datetime, timedelta
from pathlib import Path

# Try to import psutil
try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False
    print("WARNING: psutil module not found. Process detection features will be limited.")

# App data directory paths
APP_NAME = "RiftScope"
APP_DATA_DIR = os.path.join(os.getenv('APPDATA'), APP_NAME) if platform.system() == "Windows" else os.path.join(os.path.expanduser("~"), f".{APP_NAME.lower()}")
CONFIG_FILE = os.path.join(APP_DATA_DIR, "config.json")
LOG_FILE = os.path.join(APP_DATA_DIR, "app.log")

def ensure_app_data_dir():
    """Create application data directory if it doesn't exist."""
    if not os.path.exists(APP_DATA_DIR):
        os.makedirs(APP_DATA_DIR)
        return True
    return False

def get_roblox_location():
    """Get the location of the Roblox installation."""
    if platform.system() == "Windows":
        local_app_data = os.getenv('LOCALAPPDATA')
        roblox_path = os.path.join(local_app_data, "Roblox", "Versions")
        if os.path.exists(roblox_path):
            # Find the latest version folder
            versions = [f for f in os.listdir(roblox_path) if os.path.isdir(os.path.join(roblox_path, f))]
            if versions:
                for version in versions:
                    version_path = os.path.join(roblox_path, version)
                    if os.path.exists(os.path.join(version_path, "RobloxPlayerBeta.exe")):
                        return version_path
    return None

def find_log_path():
    """Find Roblox log file path based on platform."""
    if platform.system() == "Windows":
        local_app_data = os.getenv('LOCALAPPDATA')
        return os.path.join(local_app_data, "Roblox", "logs")
    # Add support for other platforms if needed
    return None

def get_latest_log_file(log_dir):
    """Get the most recent log file in the given directory."""
    if not log_dir or not os.path.exists(log_dir):
        return None
    
    log_files = [os.path.join(log_dir, f) for f in os.listdir(log_dir) if f.endswith('.log')]
    if not log_files:
        return None
    
    latest_file = max(log_files, key=os.path.getmtime)
    return latest_file

def read_log_file(log_file, last_position=0):
    """Read a log file from the last position and return new content and new position."""
    if not log_file or not os.path.exists(log_file):
        return "", 0
    
    try:
        with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
            f.seek(last_position)
            new_content = f.read()
            return new_content, f.tell()
    except Exception as e:
        print(f"Error reading log file: {e}")
        return "", last_position

def log_message(message, level="INFO"):
    """Log a message to the application log file."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_line = f"[{timestamp}] [{level}] {message}\n"
    
    try:
        with open(LOG_FILE, 'a', encoding='utf-8') as f:
            f.write(log_line)
    except Exception as e:
        print(f"Error writing to log file: {e}")

def resource_path(relative_path):
    """Get absolute path to resource, works for dev and for PyInstaller."""
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)

def read_last_n_lines(path, n=20):
    """Read the last n lines from a file"""
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
        return []

def extract_timestamp(line):
    """Extract timestamp from a log line"""
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

def is_roblox_running():
    """Check if Roblox is currently running"""
    if not HAS_PSUTIL:
        # If psutil is not available, assume Roblox is running
        print("Cannot check if Roblox is running: psutil module not available")
        return True
        
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
        return True  # Assume running on error

def apply_roblox_fastflags(update_status_callback=None):
    """Apply Roblox FastFlag settings for logging"""
    local_app_data = os.getenv('LOCALAPPDATA')
    if not local_app_data:
        if update_status_callback:
            update_status_callback("Error: LOCALAPPDATA environment variable not found.")
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
                    if update_status_callback:
                        update_status_callback(f"Warning: Corrupt JSON found at {json_file_path}. Overwriting for {launcher_info_str}.")
                    current_settings = {}
                    needs_update = True
                except Exception as read_err:
                    if update_status_callback:
                        update_status_callback(f"Warning: Error reading {json_file_path}: {read_err}. Overwriting for {launcher_info_str}.")
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
                    if update_status_callback:
                        update_status_callback(f"Updated FastFlags in {launcher_info_str} file")
                else:
                    applied_count += 1
                    if update_status_callback:
                        update_status_callback(f"Applied FastFlags to new file in {launcher_info_str}")

        except Exception as e:
            if update_status_callback:
                update_status_callback(f"Error processing FastFlags for {launcher_info_str}: {e}")

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
            if update_status_callback:
                update_status_callback(f"Error accessing Roblox versions directory: {e}")

    if applied_count > 0 or updated_count > 0:
        if update_status_callback:
            update_status_callback(f"Finished applying/updating FastFlags ({applied_count} new, {updated_count} updated)." )
    else:
        if update_status_callback:
            update_status_callback("FastFlags check complete. No changes needed or relevant folders found.") 