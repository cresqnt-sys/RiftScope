# Changelog
All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html) (starting from 1.0.0-Alpha).

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