import sys
import os
import time
import requests
import subprocess
import re
from PyQt6.QtWidgets import QMessageBox
from PyQt6.QtGui import QIcon
from PyQt6.QtCore import QTimer

# Try importing packaging.version, fall back to simple comparison if not available
try:
    import packaging.version
    HAS_PACKAGING = True
except ImportError:
    HAS_PACKAGING = False

class UpdateManager:
    """Class for checking and applying updates to RiftScope"""
    
    def __init__(self, app=None, app_version=None, repo_url=None):
        self.app = app
        self.app_version = app_version
        self.repo_url = repo_url
        self.update_worker = None
    
    def _parse_version(self, version_str):
        """Parse version string to comparable components, handling formats like X.Y.Z-tag"""
        # Remove 'v' prefix if present
        version_str = version_str.lstrip('v')
        
        # Split by dash to separate version number from tags like "-Stable"
        parts = version_str.split('-', 1)
        version_nums = parts[0]
        
        # Split version into components and convert to integers
        try:
            return [int(x) for x in version_nums.split('.')]
        except ValueError:
            # If conversion fails, return the original string for simple string comparison
            return version_str
    
    def _compare_versions(self, ver1, ver2):
        """Compare two version strings, returns 1 if ver1 > ver2, -1 if ver1 < ver2, 0 if equal"""
        if HAS_PACKAGING:
            try:
                v1 = packaging.version.parse(ver1)
                v2 = packaging.version.parse(ver2)
                if v1 > v2:
                    return 1
                elif v1 < v2:
                    return -1
                else:
                    return 0
            except packaging.version.InvalidVersion:
                # Fall back to manual comparison if packaging can't parse
                pass
                
        # Manual comparison as fallback
        v1_parts = self._parse_version(ver1)
        v2_parts = self._parse_version(ver2)
        
        # If parsing returned strings (not successful numeric parsing), do string comparison
        if isinstance(v1_parts, str) or isinstance(v2_parts, str):
            if ver1 == ver2:
                return 0
            return 1 if ver1 > ver2 else -1
        
        # Compare numeric components
        for i in range(min(len(v1_parts), len(v2_parts))):
            if v1_parts[i] > v2_parts[i]:
                return 1
            elif v1_parts[i] < v2_parts[i]:
                return -1
        
        # If we get here, all compared components are equal
        # Longer version is considered newer (e.g., 1.2.0 > 1.2)
        if len(v1_parts) > len(v2_parts):
            return 1
        elif len(v1_parts) < len(v2_parts):
            return -1
        
        return 0
    
    def check_for_updates(self):
        """Checks GitHub for the latest release.
        Runs in a background thread.
        Emits update_prompt_signal if an update is found.
        """
        if not self.app or not self.app_version or not self.repo_url:
            print("Update check skipped: missing app reference or version information")
            return
            
        api_url = f"https://api.github.com/repos/{self.repo_url}/releases/latest"
        self.app.update_status("Checking for updates...")
        try:
            response = requests.get(api_url, timeout=10)
            response.raise_for_status() 

            release_data = response.json()
            latest_version_str = release_data.get("tag_name", "").lstrip('v') 
            current_version_str = self.app_version

            # Compare versions using our method
            comparison_result = self._compare_versions(latest_version_str, current_version_str)

            if comparison_result > 0:  # latest > current
                self.app.update_status(f"New version available: v{latest_version_str}")
                assets = release_data.get("assets", [])
                download_url = None
                for asset in assets:
                    if asset.get("name", "").lower().endswith(".exe"):
                        download_url = asset.get("browser_download_url")
                        break

                if download_url:
                    self.app.update_prompt_signal.emit(latest_version_str, download_url)
                else:
                    self.app.update_status("Update found, but no .exe asset link available.")
                    print("Error: No .exe download URL found in the latest release assets.")

            else:
                self.app.update_status("RiftScope is up to date.")

        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404 and api_url in str(e):
                self.app.update_status("No releases found to check for updates.")
                print("Info: No releases published yet on the repository.")
            else:
                self.app.update_status(f"Update check failed: Server error ({e})")
                print(f"Error checking for updates (HTTPError): {e}")
        except requests.exceptions.RequestException as e:
            self.app.update_status(f"Update check failed: Network error ({e})")
            print(f"Error checking for updates: {e}")
        except Exception as e:
            self.app.update_status(f"Update check failed: An unexpected error occurred ({e})")
            print(f"An unexpected error occurred during update check: {e}")
            
    def prompt_update(self, new_version, download_url):
        """Asks the user if they want to update (runs in main thread)."""
        if not self.app:
            return
            
        msg_box = QMessageBox(self.app) 
        msg_box.setWindowTitle("Update Available")
        msg_box.setText(f"A new version of RiftScope (v{new_version}) is available.\n" 
                        f"Your current version is v{self.app_version}.\n\n" 
                        f"Do you want to download and install it now?")
        msg_box.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        msg_box.setDefaultButton(QMessageBox.StandardButton.Yes)

        icon_path = "icon.ico"
        if os.path.exists(icon_path):
            msg_box.setWindowIcon(QIcon(icon_path))

        reply = msg_box.exec()

        if reply == QMessageBox.StandardButton.Yes:
            self.app.update_status(f"Starting update to v{new_version}...")

            from models import Worker
            self.update_worker = Worker(self.perform_update, download_url)
            self.update_worker.update_status_signal.connect(self.app.update_status)
            self.update_worker.finished_signal.connect(lambda: print("Update worker finished.")) 
            self.update_worker.start()
        else:
            self.app.update_status("Update declined by user.")
            
    def perform_update(self, download_url):
        """Downloads and attempts to install the update (runs in worker thread)."""
        try:
            current_exe_path = sys.executable
            if not current_exe_path or not current_exe_path.lower().endswith(".exe"):
                self.app.update_status("Update Error: Cannot determine running executable path.")
                print("Update Error: Not running from a detectable .exe file.")
                return

            exe_dir = os.path.dirname(current_exe_path)
            exe_filename = os.path.basename(current_exe_path)
            new_exe_temp_path = os.path.join(exe_dir, f"_{exe_filename}_new")
            updater_bat_path = os.path.join(exe_dir, "_updater.bat")

            self.app.update_status(f"Downloading {os.path.basename(download_url)}...")
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
                        self.app.update_status(f"Downloading update... {percent}%")
                        last_update_time = current_time

            self.app.update_status("Download complete.")

            quoted_current_exe = f'"{current_exe_path}"'
            quoted_new_exe = f'"{new_exe_temp_path}"'
            quoted_original_filename = f'"{exe_filename}"'

            batch_script_content = f"""
@echo off
echo Update downloaded.
echo Please close the main RiftScope application now.

echo Press any key AFTER closing RiftScope to continue the update...
pause > NUL 

echo Attempting to replace executable...

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

            self.app.update_status("Update downloaded. Please close RiftScope now to apply the update.")

            subprocess.Popen(['cmd.exe', '/c', updater_bat_path],
                             creationflags=subprocess.CREATE_NEW_CONSOLE,
                             close_fds=True)

        except requests.exceptions.RequestException as e:
            self.app.update_status(f"Update failed: Download error ({e})") 