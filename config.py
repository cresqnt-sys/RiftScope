#!/usr/bin/env python3
# RiftScope - Configuration Handling
# GitHub: https://github.com/cresqnt-sys/RiftScope

import os
import json
from utils import APP_DATA_DIR, CONFIG_FILE, log_message

# Default configuration
DEFAULT_CONFIG = {
    "first_run": True,
    "check_for_updates": True,
    "discord_webhook_url": "",
    "discord_webhook_enabled": False,
    "collection_path_enabled": False,
    "collection_path_points": [],
    "ui_theme": "dark",
    "notification_sounds": True,
    "auto_start": False,
    "minimize_to_tray": True,
    "start_minimized": False,
    "detect_rifts": True,
    "detect_hatches": True,
    "warning_pings": True,
    "webhook_cooldown": 5,
}

def load_config():
    """Load configuration from file or create with defaults if it doesn't exist."""
    try:
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, 'r') as f:
                config = json.load(f)
                
            # Add any missing keys from default config
            for key, value in DEFAULT_CONFIG.items():
                if key not in config:
                    config[key] = value
                    
            return config
        else:
            # Create the config directory if it doesn't exist
            os.makedirs(APP_DATA_DIR, exist_ok=True)
            
            # Save default config
            with open(CONFIG_FILE, 'w') as f:
                json.dump(DEFAULT_CONFIG, f, indent=4)
                
            log_message("Created new configuration file with defaults", "INFO")
            return DEFAULT_CONFIG.copy()
            
    except Exception as e:
        log_message(f"Error loading configuration: {str(e)}", "ERROR")
        return DEFAULT_CONFIG.copy()

def save_config(config):
    """Save configuration to file."""
    try:
        # Create directory if it doesn't exist
        os.makedirs(APP_DATA_DIR, exist_ok=True)
        
        with open(CONFIG_FILE, 'w') as f:
            json.dump(config, f, indent=4)
            
        log_message("Configuration saved successfully", "INFO")
        return True
        
    except Exception as e:
        log_message(f"Error saving configuration: {str(e)}", "ERROR")
        return False
        
def update_config(key, value):
    """Update a specific configuration value."""
    config = load_config()
    config[key] = value
    return save_config(config)
    
def get_config_value(key, default=None):
    """Get a specific configuration value with optional default."""
    config = load_config()
    return config.get(key, default)

def reset_config():
    """Reset configuration to defaults."""
    return save_config(DEFAULT_CONFIG.copy())

class Config:
    def __init__(self, app_instance=None):
        self.app_instance = app_instance
        
        # Set default config values
        self.webhook_url = ''
        self.ps_link = ''
        self.royal_chest_ping_id = ''
        self.royal_chest_ping_type = 'User'
        self.gum_rift_ping_id = ''
        self.gum_rift_ping_type = 'User'
        self.launcher_choice = 'Auto'
        self.server_mode = 'Private Server'
        self.collection_enabled = False
        self.teleport_coords = None
        self.hatch_username = ''
        self.hatch_secret_ping_enabled = False
        self.hatch_secret_ping_user_id = ''
        self.hatch_detection_enabled = True
        self.tutorial_shown = False
        
        # Determine config file path
        app_data_dir = os.getenv('APPDATA')
        if app_data_dir:
            config_dir = os.path.join(app_data_dir, "RiftScope")
            self.config_file = os.path.join(config_dir, "config.json")
        else:
            print("Warning: APPDATA environment variable not found. Saving config locally.")
            config_dir = os.path.dirname(os.path.abspath(__file__)) 
            self.config_file = os.path.join(config_dir, "config.json")
    
    def load(self):
        """Load configuration from file"""
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r') as f:
                    config = json.load(f)
                    self.webhook_url = config.get('webhook_url', '')
                    self.ps_link = config.get('ps_link', '')
                    self.royal_chest_ping_id = config.get('royal_chest_ping_id', '')
                    self.royal_chest_ping_type = config.get('royal_chest_ping_type', 'User')
                    self.gum_rift_ping_id = config.get('gum_rift_ping_id', '')
                    self.gum_rift_ping_type = config.get('gum_rift_ping_type', 'User')
                    self.launcher_choice = config.get('launcher_choice', 'Auto')
                    self.server_mode = config.get('server_mode', 'Private Server')

                    self.collection_enabled = config.get('collection_enabled', False)
                    loaded_coords = config.get('teleport_coords', None)

                    if isinstance(loaded_coords, (list, tuple)):
                        if len(loaded_coords) == 2:
                            self.teleport_coords = tuple(loaded_coords) 
                        elif len(loaded_coords) == 4:
                            self.teleport_coords = tuple(loaded_coords[:2])
                            print("Note: Old calibration format detected, using only x, y.")
                        else:
                             self.teleport_coords = None 
                    else:
                        self.teleport_coords = None

                    self.hatch_username = config.get('hatch_username', '')
                    self.hatch_secret_ping_enabled = config.get('hatch_secret_ping_enabled', False)
                    self.hatch_secret_ping_user_id = config.get('hatch_secret_ping_user_id', '')
                    self.hatch_detection_enabled = config.get('hatch_detection_enabled', True) 
                    self.tutorial_shown = config.get('tutorial_shown', False)
                    
                return True
        except Exception as e:
            print(f"Error loading config: {e}")
            return False

    def save(self):
        """Save configuration to file"""
        try:
            # Create config directory if it doesn't exist
            config_dir = os.path.dirname(self.config_file)
            os.makedirs(config_dir, exist_ok=True)
            
            # If we have an app instance, get values from UI components
            if self.app_instance:
                config = {
                    'webhook_url': self.app_instance.webhook_entry.text().strip() if hasattr(self.app_instance, 'webhook_entry') else self.webhook_url,
                    'ps_link': self.app_instance.pslink_entry.text().strip() if hasattr(self.app_instance, 'pslink_entry') else self.ps_link,
                    'royal_chest_ping_id': self.app_instance.royal_chest_ping_entry.text().strip() if hasattr(self.app_instance, 'royal_chest_ping_entry') else self.royal_chest_ping_id,
                    'royal_chest_ping_type': self.app_instance.royal_chest_ping_type_combo.currentText() if hasattr(self.app_instance, 'royal_chest_ping_type_combo') else self.royal_chest_ping_type,
                    'gum_rift_ping_id': self.app_instance.gum_rift_ping_entry.text().strip() if hasattr(self.app_instance, 'gum_rift_ping_entry') else self.gum_rift_ping_id,
                    'gum_rift_ping_type': self.app_instance.gum_rift_ping_type_combo.currentText() if hasattr(self.app_instance, 'gum_rift_ping_type_combo') else self.gum_rift_ping_type,
                    'launcher_choice': self.app_instance.launcher_combo.currentText() if hasattr(self.app_instance, 'launcher_combo') else self.launcher_choice,
                    'server_mode': self.app_instance.server_mode_combo.currentText() if hasattr(self.app_instance, 'server_mode_combo') else self.server_mode,
                    'collection_enabled': self.app_instance.collection_enabled_checkbox.isChecked() if hasattr(self.app_instance, 'collection_enabled_checkbox') else self.collection_enabled,
                    'teleport_coords': self.teleport_coords,
                    'hatch_username': self.app_instance.hatch_username_entry.text().strip() if hasattr(self.app_instance, 'hatch_username_entry') else self.hatch_username,
                    'hatch_secret_ping_enabled': self.app_instance.hatch_secret_ping_checkbox.isChecked() if hasattr(self.app_instance, 'hatch_secret_ping_checkbox') else self.hatch_secret_ping_enabled,
                    'hatch_secret_ping_user_id': self.app_instance.hatch_userid_entry.text().strip() if hasattr(self.app_instance, 'hatch_userid_entry') else self.hatch_secret_ping_user_id,
                    'hatch_detection_enabled': self.app_instance.hatch_detection_enabled_checkbox.isChecked() if hasattr(self.app_instance, 'hatch_detection_enabled_checkbox') else self.hatch_detection_enabled,
                    'tutorial_shown': self.tutorial_shown
                }
            else:
                # No app instance, save current config values
                config = {
                    'webhook_url': self.webhook_url,
                    'ps_link': self.ps_link,
                    'royal_chest_ping_id': self.royal_chest_ping_id,
                    'royal_chest_ping_type': self.royal_chest_ping_type,
                    'gum_rift_ping_id': self.gum_rift_ping_id,
                    'gum_rift_ping_type': self.gum_rift_ping_type,
                    'launcher_choice': self.launcher_choice,
                    'server_mode': self.server_mode,
                    'collection_enabled': self.collection_enabled,
                    'teleport_coords': self.teleport_coords,
                    'hatch_username': self.hatch_username,
                    'hatch_secret_ping_enabled': self.hatch_secret_ping_enabled,
                    'hatch_secret_ping_user_id': self.hatch_secret_ping_user_id,
                    'hatch_detection_enabled': self.hatch_detection_enabled,
                    'tutorial_shown': self.tutorial_shown
                }
                
            with open(self.config_file, 'w') as f:
                json.dump(config, f, indent=4)
                
            # Update instance variables from saved config
            for key, value in config.items():
                if hasattr(self, key):
                    setattr(self, key, value)
                    
            return True
        except Exception as e:
            print(f"Error saving config: {e}")
            if self.app_instance:
                self.app_instance.update_status(f"Error saving config: {e}")
            return False
            
    def apply_to_ui(self):
        """Apply loaded config values to UI components"""
        if not self.app_instance:
            return
            
        if hasattr(self.app_instance, 'webhook_entry'):
            self.app_instance.webhook_entry.setText(self.webhook_url)
        if hasattr(self.app_instance, 'pslink_entry'):
            self.app_instance.pslink_entry.setText(self.ps_link)
        if hasattr(self.app_instance, 'royal_chest_ping_entry'):
            self.app_instance.royal_chest_ping_entry.setText(self.royal_chest_ping_id)
        if hasattr(self.app_instance, 'royal_chest_ping_type_combo'):
            index = self.app_instance.royal_chest_ping_type_combo.findText(self.royal_chest_ping_type)
            if index >= 0:
                self.app_instance.royal_chest_ping_type_combo.setCurrentIndex(index)
        if hasattr(self.app_instance, 'gum_rift_ping_entry'):
            self.app_instance.gum_rift_ping_entry.setText(self.gum_rift_ping_id)
        if hasattr(self.app_instance, 'gum_rift_ping_type_combo'):
            index = self.app_instance.gum_rift_ping_type_combo.findText(self.gum_rift_ping_type)
            if index >= 0:
                self.app_instance.gum_rift_ping_type_combo.setCurrentIndex(index)
        if hasattr(self.app_instance, 'launcher_combo'):
            index = self.app_instance.launcher_combo.findText(self.launcher_choice)
            if index >= 0:
                self.app_instance.launcher_combo.setCurrentIndex(index)
            elif self.launcher_choice == "Auto":
                self.app_instance.launcher_combo.setCurrentIndex(0)
        if hasattr(self.app_instance, 'server_mode_combo'):
            index = self.app_instance.server_mode_combo.findText(self.server_mode)
            if index >= 0:
                self.app_instance.server_mode_combo.setCurrentIndex(index)
        if hasattr(self.app_instance, 'collection_enabled_checkbox'):
            self.app_instance.collection_enabled_checkbox.setChecked(self.collection_enabled)
        if hasattr(self.app_instance, 'hatch_username_entry'):
            self.app_instance.hatch_username_entry.setText(self.hatch_username)
        if hasattr(self.app_instance, 'hatch_secret_ping_checkbox'):
            self.app_instance.hatch_secret_ping_checkbox.setChecked(self.hatch_secret_ping_enabled)
        if hasattr(self.app_instance, 'hatch_userid_entry'):
            self.app_instance.hatch_userid_entry.setText(self.hatch_secret_ping_user_id)
        if hasattr(self.app_instance, 'hatch_detection_enabled_checkbox'):
            self.app_instance.hatch_detection_enabled_checkbox.setChecked(self.hatch_detection_enabled) 