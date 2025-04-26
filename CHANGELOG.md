# Changelog
All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html) (starting from 1.0.0-Alpha).

## [1.2.0-Stable] - 2025-04-26

### Added
- **Hatch Detection Features**:
    - Added a new "Hatch" tab with settings for username, secret pet ping toggle, and user ID for pinging.
    - Implemented detection logic for Secret and Legendary pets based on provided lists.
    - Handles pet mutations (e.g., "Shiny", "Mythic") when checking against lists.
    - Sends Discord webhook notifications for rare hatches, including embed color based on rarity.
    - Option to ping a specific user ID when *their own* configured username hatches a Secret pet.
    - Added a checkbox to enable/disable all hatch detection.
    - Implemented a cooldown period (`last_hatch_ping_time`) for hatch notifications.
    - Configuration saving/loading for all Hatch tab settings.
- **Event Cooldown System**: Implemented a global cooldown (`EVENT_COOLDOWN_SECONDS`) to prevent duplicate webhook pings for Royal Chest and Gum Rift. (Aura Egg excluded from cooldown).
- Automatic FFlags configuration, reducing reliance on external tools like Fishstrap.
- Tutorial link for Collection

### Changed
- Updated application version to `1.2.0-Stable`.
- **Autoupdater Process**: Modified the updater script (`_updater.bat`) generation to instruct the user to manually close the application before the update process replaces the executable.
- Refined FastFlag application logic (`apply_roblox_fastflags`).
- **First-Time Setup Notice**: 
    - Now uses a `tutorial_shown` flag in `config.json` to determine if it should be displayed, instead of just checking for the config file's existence.
    - The "OK" button is disabled for 10 seconds via a `QTimer`.
    - The notice text informs the user about the 10-second delay.
    - The `tutorial_shown` flag is only set to `True` (and saved) if the user explicitly clicks the "OK" button, not if the dialog is closed via the 'X' button.

### Fixed
- Re-added accidentally removed detection logic for Gum Rift and Aura Egg events.
- Improved hatch detection regex to correctly identify pets with mutations (e.g., "Shiny Neon Elemental", "Mythic Seraphic Bunny").
- Resolved an `AttributeError` crash that occurred when `save_config` was called during the first-time setup notice (before the main UI elements were created).

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
- Refactored background tasks into `