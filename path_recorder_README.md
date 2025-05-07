# RiftScope Path Recorder

A standalone application for recording custom collection paths for RiftScope.

## Overview

The Path Recorder allows you to create your own collection paths by recording keyboard movements. These paths can then be used in RiftScope's collection feature.

## Requirements

- Python 3.6 or higher
- PyQt6 (`pip install PyQt6`)
- pynput (`pip install pynput`)

## How to Use

1. **Start the application:**
   ```
   python path_recorder.py
   ```

2. **Record a path:**
   - Enter a name and optional description for your path
   - Click "Start Recording" or press F1 key
   - Use WASD keys or arrow keys to record your movement
   - Press F1 or ESC to stop recording

3. **Test your path:**
   - After recording, click "Test Path" to see the path in action
   - The recorder will simulate the key presses to test your path
   - You can also test existing paths by selecting them from the dropdown
   - Press "Stop Test" to interrupt a running test

4. **Save your path:**
   - After recording, click "Save Path"
   - The path will be saved to the "Paths" folder in JSON format

5. **Use in RiftScope:**
   - The saved path will automatically appear in RiftScope's path selection dropdown
   - Select your path in the Collection tab of RiftScope

## Keyboard Shortcuts

- **F1**: Start or stop recording (F1 keypresses won't be included in the recorded path)
- **ESC**: Stop recording
- **WASD or Arrow Keys**: Movement keys that will be recorded

## How It Works

The Path Recorder captures:
- Which keys you press (W, A, S, D)
- How long each key is pressed
- The delay between keypresses

This data is saved in the same format that RiftScope uses for its collection paths.

## Tips for Good Paths

- Plan your path before recording to avoid mistakes
- Keep paths efficient with minimal backtracking
- Test your path thoroughly after creating it
- Remember that the last movement should end where teleport returns you

## Troubleshooting

- If keys aren't being detected, ensure you have permission to monitor keyboard input
- If paths don't appear in RiftScope, make sure they're saved to the correct "Paths" directory
- Relaunch RiftScope after creating new paths to ensure they appear in the selection dropdown 