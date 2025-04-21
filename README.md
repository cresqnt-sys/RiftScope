# RiftScope

<p align="center">
  <img src="https://i.postimg.cc/9MWNYd6y/Aura-Egg.png" alt="RiftScope Icon" width="150"/>
</p>

<p align="center">
  <strong>Monitor Bubble Gum Simulator Infinity for rare rifts!</strong>
</p>

---

RiftScope is a user-friendly application for Windows made to monitor your Roblox logs for Bubble Gum Simulator Infinity. It watches for specific rare events, such as the appearance of a **Royal Chest** (🎁) or an **Aura Egg** (🥚), and sends a notification to your Discord webhook.

## Features

*   **Real-time Log Monitoring:** Actively scans the latest Roblox log file.
*   **Discord Webhook Notifications:** Get instant alerts in your Discord server when a Royal Chest or Aura Egg is detected.
*   **Customizable Notifications:** Includes event details, timestamps, and an optional link to your private server.
*   **User-Friendly Interface:** Built with PyQt6, featuring a clean dark theme.
*   **Hotkey Support:** Start (F1) and Stop (F2) scanning easily.
*   **Test Functionality:** Verify your webhook setup and log detection before starting.
*   **Log File Locking:** Option to monitor only the log file active when scanning started.
*   **Integrated Log Viewer:** See status updates and application logs directly within the app.
*   **Auto-Updater:** Checks for new versions on GitHub and guides you through the update process.
*   **Local Configuration:** Saves your settings (`webhook_url`, `ps_link`) in `%APPDATA%\\RiftScope`.


## Requirements

*   Windows OS (7, 8, 10, 11)
*   Roblox installed and open logging Bubble Gum Simulator Infinity.
*   The exectuable file or Source Code.
*   Python 3.x (only if running from source).

## Installation

**Recommended Method (Executable):**

1.  Go to the [**Releases**](https://github.com/cresqnt-sys/RiftScope/releases) page on GitHub.
2.  Download the latest `RiftScope-vX.X.X.exe` file.
3.  Place the executable in a convenient location and run it. No installation is required.

**From Source:**

1.  Ensure you have Python 3 and `pip` installed.
2.  Clone the repository:
    ```bash
    git clone https://github.com/cresqnt-sys/RiftScope.git
    ```
3.  Navigate to the project directory:
    ```bash
    cd RiftScope
    ```
4.  Install the required dependencies:
    ```bash
    pip install -r requirements.txt
    ```
5.  Run the application:
    ```bash
    python RiftScope.py
    ```

## Usage

1.  Launch `RiftScope.exe` (or run `python RiftScope.py` if installed from source).
2.  Navigate to the **Scanner** tab.
3.  Paste your **Discord Webhook URL** into the first input field. You can create one in your Discord server's settings (Integrations -> Webhooks -> New Webhook).
4.  (Optional) Paste your **Private Server Link** into the second input field if you want it included in notifications.
5.  Click **Start Scanning** or press **F1** to begin monitoring the logs.
6.  To stop monitoring, click **Stop Scanning** or press **F2**.
7.  Before starting, you can use the **Test Scanner** button to send test messages to your webhook and confirm RiftScope can read the log file correctly.
8.  Use the **Lock Log File** toggle (before starting) if you want RiftScope to *only* monitor the specific log file that was newest when you clicked Start. If unlocked, it will automatically switch to newer log files if they appear.
9.  Switch to the **Logs** tab to see detailed status messages and timestamps from the application itself.

## Configuration

Your Discord Webhook URL and Private Server link are automatically saved when you start scanning or test the scanner. The configuration file is located at:

```
%APPDATA%\RiftScope\config.json
```

You typically do not need to edit this file manually.

## Building from Source (Optional)

If you want to create your own `.exe` file from the source code:

1.  Make sure you have installed the dependencies from `requirements.txt`.
2.  Install PyInstaller:
    ```bash
    pip install pyinstaller
    ```
3.  Navigate to the `RiftScope` directory in your terminal.
4.  Run PyInstaller (ensure `icon.ico` is present in the directory):
    ```bash
    pyinstaller --onefile --windowed --icon=icon.ico RiftScope.py --name RiftScope
    ```
5.  Your executable will be located in the `dist` folder.

## Support

For help, questions, or suggestions, join the official Discord server: [RiftScope Support](https://discord.gg/6cuCu6ymkX)

## Credits

*   **cresqnt:** Project maintainer, UI development, and feature enhancements.
*   **Digital:** Original creator of the core log scanning concept.

## License

This project is licensed under the GNU Affero General Public License v3.0 - see the [LICENSE](LICENSE) file for details.
