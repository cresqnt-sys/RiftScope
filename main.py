#!/usr/bin/env python3
# RiftScope - Main Entry Point
# GitHub: https://github.com/cresqnt-sys/RiftScope

import sys
import os
from PyQt6.QtWidgets import QApplication

from ui import RiftScopeApp
from utils import ensure_app_data_dir

def main():
    """Main entry point for RiftScope application."""
    # Ensure app data directory exists
    ensure_app_data_dir()
    
    # Create Qt application
    app = QApplication(sys.argv)
    
    # Create and show main window
    main_window = RiftScopeApp()
    main_window.show()
    
    # Start application event loop
    sys.exit(app.exec())

if __name__ == "__main__":
    main() 