# Changelog
All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html) (starting from 1.0.0-Alpha).

## [1.3.5-Stable] - 2025-05-09

### Added
- **Currency Updates Feature**:
    - Added screenshot capability to track currency amounts
    - Implemented delay setting for update frequency
    - Added calibration area for currency display location
    - Added Discord webhook integration for currency screenshots
- **Ticket Collection Feature**:
    - Added new "Ticket Collection" path for farming tickets
    - Implemented "Open Cyber While Farming" option to spam the 'R' key during execution
- **Merchant Auto Buy**:
    - Added auto buy for all 3 shops
- **UI Enhancement**:
    - Added a Contributors section to the Credits tab
    - Added "Digital" and "Manas" (for Path Creation) to the Contributors section

### Changed
- **Calibration Tab**: 
    - Reworked the calibration tab to be more compact
    - Improved layout with grid design for better space utilization
    - Optimized spacing and reduced margins for a cleaner appearance
- **Screenshot Handling**:
    - Changed screenshot storage to save directly in the application data directory
    - Improved webhook attachment handling for more reliable delivery

### Fixed
- Fixed "Open Cyber While Farming" checkbox visibility and state persistence
- Resolved issues with webhook not properly sending screenshots as attachments
- Fixed parameter order in the send_webhook method for proper file path handling

## [1.3.0-Stable] - 2025-05-07

### Added
- **Collection Path Management**:
    - Organized collection paths into a "Paths" folder for better structure.
    - Updated code to read paths from JSON files in the Paths folder.
- **Claw Machine**:
    - Added calibration buttons for "Claw Machine Skip", "Claw Machine Claim", and "Claw Machine Start".
    - Implemented automated sequence for claw machine: start → execute path → claim → jump → skip.
    - Added specific timing controls between actions.
- **Updated Pet Lists**:
    - Added additional pets to Secret and Legendary detection lists.

### Changed
- **Event Notification System**:
    - Replaced time-based cooldown with content-based detection to prevent double-sending notifications.
    - Implemented line-content tracking to ensure each log line only triggers a notification once per batch.
- **Configuration Handling**:
    - Fixed issue with "Enable Automation" toggle not saving its state.
    - Ensured configuration is properly saved when application closes.

### Fixed
- Fixed indentation errors in notification system code.
- Resolved configuration key inconsistencies between UI elements and config file.

## [1.2.5-Beta] - 2025-04-29

### Added
- **Public Server Mode**:
    - Added auto-detection of server changes using JobID and PlaceID.
    - Implemented fetching of RoPro short links for public server notifications.
    - Added popup warning when switching to Public Server mode, reminding user to start RiftScope before Roblox.
    - Improved logging for server detection events.
- **Updated Pet Lists**: Added new Secret (Royal Trophy, Silly Doggy :) ) and Legendary pets (Chocolate Bunny, Diamond Hexarium, Diamond Serpent, DOOF, Electra Hydra, Elite Challenger, Elite Soul, Enraged Phoenix, King Pufferfish, Overseer, Parasite, ROUND, Starlight) to detection lists.

### Changed
- **Event Notification System**: Replaced fixed cooldown with timestamp-based deduplication for Royal Chest, Gum Rift, and Silly Egg events to prevent missed pings.
- **Public Server Popup**: Popup now only appears on user interaction, not on initial startup if Public Server mode is already selected.
- Improved robustness of auto-updater version comparison.
- Refactored the whole codebase in preperation for bigger updates.

### Fixed
- Resolved issue where the "Stop Scanning" button required two clicks to fully stop processes.
- Fixed `NameError: name 'time' is not defined` in `detection.py`.
- Corrected removal of `processed_hatch_timestamps` during Aura Egg removal.

## [1.2.1-Stable] - 2025-04-27

### Added
- **Silly Egg Detection**: Detects the "we're so silly and fun" message, sending a webhook with 😂 emoji and forcing an `@everyone` ping.
- Added Silly Egg entry to the "Pings" tab UI, indicating its forced `@everyone` ping.
- Changed "Username" in hatch tab to "Roblox Username:"

### Changed
- Removed cooldown checks for Aura Egg and Silly Egg webhook notifications. They will now ping every time they are detected.

## [1.2.0-Hotfix] - 2025-04-26

### Fixed
- Ensured hatch notifications (status update and webhook) are only sent if the username found in the log message matches the username configured in the 'Hatch Settings' tab.
- Corrected Discord embed formatting for hatch notifications, ensuring newlines (`\n`) are properly rendered instead of appearing as literal `\\n`.

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
- Gum Rift detection for the message "Bring us your gum, Earthlings!" with pink notification color and bubble emoji (��).
- Added better FFLags addition
- Added Log Detection Modes

## [1.0.0-Alpha2] - 2025-04-21  

### Added
- Automatic configuration of Roblox FastFlags (`ClientAppSettings.json`) on startup to enable necessary logging for detection.
- Input field for "Discord Ping ID" (User or Role) to specify mentions for Royal Chest notifications.
- First-launch warning `