# Changelog
All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html) (starting from 1.0.0-Alpha).

## [1.1.0-Beta] - 2024-04-25 

### Added
- **Collection Path Feature**:
    - Added a new "Collection" tab to the UI.
    - Option to enable/disable the collection path macro.
    - Calibration system (single click) to define the teleport button location.
    - Coordinates displayed below the calibration button.
    - Collection process runs concurrently with rift scanning.
    - Uses `autoit.mouse_click` via `pyautoit` wrapper.
    - 3-second delay added after teleport click.
- Global hotkeys (F1 Start, F2 Stop) using `pynput` listener, replacing `QShortcut` to work when the window isn't focused.
- Added Ping Selection

### Changed
- Updated application version constant to `1.1.0-Beta`.
- Required dependencies now include `pynput`, `pyautogui`, and `pyautoit` (which itself requires AutoIt to be installed).
- Moved "Credits" tab to be the last tab in the UI.
- Updated text in the Credits tab.

### Fixed
- Fixed various bugs related to calibration state management (`AttributeError` and `NoneType` errors).
- Fixed `UnboundLocalError` related to `launcher_frame` in `build_ui`.

## [1.0.1-Beta] - 2025-04-23

### Added
- Gum Rift detection for the message "Bring us your gum, Earthlings!" with pink notification color and bubble emoji (🫧).
- Added better FFLags addition
- Added Log Detection Modes

## [1.0.0-Alpha2] - 2025-04-21  

### Added
- Automatic configuration of Roblox FastFlags (`ClientAppSettings.json`) on startup to enable necessary logging for detection.
- Input field for "Discord Ping ID" (User or Role) to specify mentions for Royal Chest notifications.
- First-launch warning `QMessageBox` instructing users to ensure Roblox is closed before starting RiftScope initially to allow for proper FastFlag setup.

### Changed
- Aura Egg notifications now always ping `@everyone` instead of a specific ID.
- Updated application version constant to `1.0.0-Alpha2`.

### Fixed
- Resolved a startup crash where the FastFlag configuration logic tried to update UI elements (`status_label`) before they were created.

### Removed
- The status label widget previously displayed below the buttons on the "Scanner" tab. Status updates are now only shown in the "Logs" tab and console output.

## [1.0.0-Alpha] - 2025-04-21

### Added
- Initial project structure setup.
- Core log monitoring functionality.
- PyQt6 graphical user interface (GUI) with a dark theme.
- Tabbed interface: Scanner, Logs, Credits.
- Discord webhook notifications for detected events, start, stop, test, and errors.
- Configuration saving/loading to `%APPDATA%\RiftScope\config.json` (stores webhook URL and private server link).
- `Worker` QThread class to run background tasks (monitoring, testing, update checking) without freezing the UI.
- Input fields for Discord Webhook URL and optional Private Server Link.
- Buttons: Start Scanning, Stop Scanning, Test Scanner, Lock Log File.
- Status label for feedback.
- Keybinds: F1 for Start, F2 for Stop.
- Test Scanner functionality to verify webhook and log detection.
- Log File Locking option to stick to the initial log file.
- Integrated Logs tab showing timestamped application status messages.
- Auto-updater: Checks GitHub releases, prompts user, downloads, and runs installer script.
- `requirements.txt` file listing dependencies (requests, psutil, PyQt6, packaging).
- `README.md` with project description, features, installation, usage, etc.
- `LICENSE` file (AGPL-3.0).
- This `CHANGELOG.md` file.
- Support section in `README.md` with Discord link.
- Support Server link field added to start/stop Discord webhook embeds.
- Dynamic timestamp and optional Private Server link fields in Discord embeds.
- Custom icon in Discord embed footer.
- Application icon (`icon.ico`).

### Changed
- Migrated UI from previous implementation Tkinter to PyQt6.
- Refactored background tasks into `Worker` QThread.
- Updated application version to `1.0.0-Alpha`.
- Updated webhook messages for start/stop events.
- Reordered UI tabs (`Logs` tab placed before `Credits`).
- Reordered labels in the Credits tab.
- Improved log reading robustness (`read_last_n_lines`).
- Updated `README.md` to correctly reference "Bubble Gum Simulator Infinity" and general Roblox logs, removing specific "Fishstrap" mentions.
- Specified AGPL-3.0 license in `README.md`.
- Made status updates display timestamps.

### Fixed
- Resolved errors related to incorrect signal emissions from worker threads.
- Corrected configuration saving location to use `%APPDATA%`. 