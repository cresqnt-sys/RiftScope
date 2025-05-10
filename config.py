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
    "enable_scheduled_merchant_run": False,
    "currency_updates_enabled": False,
    "currency_updates_delay_minutes": 10,
    "currency_display_area_coords": None,
    "spam_e_for_ticket_path": False,
    "merchant_shop_area_coords": None,
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
        self.dice_chest_ping_id = ''
        self.dice_chest_ping_type = 'User'
        self.launcher_choice = 'Auto'
        self.server_mode = 'Private Server'
        self.teleport_coords = None
        self.claw_skip_coords = None
        self.claw_claim_coords = None
        self.claw_start_coords = None
        self.map_up_arrow_coords = None
        self.map_down_arrow_coords = None
        self.current_path = 'gem_path'  # Default path
        self.shop_item1_coords = None
        self.shop_item2_coords = None
        self.shop_item3_coords = None
        self.hatch_username = ''
        self.hatch_secret_ping_enabled = False
        self.hatch_secret_ping_user_id = ''
        self.hatch_detection_enabled = True
        self.tutorial_shown = False
        self.automation_enabled = DEFAULT_CONFIG.get('collection_path_enabled', False) # Use actual default from top
        self.spam_e_for_ticket_path = DEFAULT_CONFIG.get('spam_e_for_ticket_path', False)
        self.enable_scheduled_merchant_run = DEFAULT_CONFIG.get('enable_scheduled_merchant_run', False)
        self.merchant_shop_area_coords = DEFAULT_CONFIG.get('merchant_shop_area_coords', None)
        
        # New currency update settings
        self.currency_updates_enabled = DEFAULT_CONFIG.get('currency_updates_enabled', False)
        self.currency_updates_delay_minutes = DEFAULT_CONFIG.get('currency_updates_delay_minutes', 60)
        self.currency_display_area_coords = DEFAULT_CONFIG.get('currency_display_area_coords', None)
        
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
                    self.dice_chest_ping_id = config.get('dice_chest_ping_id', '')
                    self.dice_chest_ping_type = config.get('dice_chest_ping_type', 'User')
                    self.launcher_choice = config.get('launcher_choice', 'Auto')
                    self.server_mode = config.get('server_mode', 'Private Server')

                    self.automation_enabled = config.get('automation_enabled', config.get('collection_path_enabled', DEFAULT_CONFIG.get('collection_path_enabled', False)))
                    loaded_coords = config.get('teleport_coords', None)
                    self.current_path = config.get('current_path', 'gem_path')

                    # Load claw machine coordinates
                    self.claw_skip_coords = config.get('claw_skip_coords', None)
                    self.claw_claim_coords = config.get('claw_claim_coords', None)
                    self.claw_start_coords = config.get('claw_start_coords', None)
                    
                    # Load map arrow coordinates
                    self.map_up_arrow_coords = config.get('map_up_arrow_coords', None)
                    self.map_down_arrow_coords = config.get('map_down_arrow_coords', None)
                    
                    # Load shop item coordinates
                    self.shop_item1_coords = config.get('shop_item1_coords', None)
                    self.shop_item2_coords = config.get('shop_item2_coords', None)
                    self.shop_item3_coords = config.get('shop_item3_coords', None)

                    self.spam_e_for_ticket_path = config.get('spam_e_for_ticket_path', False)
                    self.enable_scheduled_merchant_run = config.get('enable_scheduled_merchant_run', DEFAULT_CONFIG.get('enable_scheduled_merchant_run', False))
                    self.merchant_shop_area_coords = config.get('merchant_shop_area_coords', None)

                    # Load new currency update settings
                    self.currency_updates_enabled = config.get('currency_updates_enabled', DEFAULT_CONFIG.get('currency_updates_enabled', False))
                    self.currency_updates_delay_minutes = config.get('currency_updates_delay_minutes', DEFAULT_CONFIG.get('currency_updates_delay_minutes', 60))
                    self.currency_display_area_coords = config.get('currency_display_area_coords', None) # Expects (x1, y1, x2, y2) or None

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
                # Get the current path from the collection manager if available
                current_path = self.current_path
                if hasattr(self.app_instance, 'collection_manager') and hasattr(self.app_instance.collection_manager, 'current_path'):
                    current_path = self.app_instance.collection_manager.current_path
                
                spam_e_setting = self.spam_e_for_ticket_path
                if hasattr(self.app_instance, 'spam_e_checkbox') and self.app_instance.spam_e_checkbox:
                     spam_e_setting = self.app_instance.spam_e_checkbox.isChecked()

                enable_merchant_run_setting = self.enable_scheduled_merchant_run
                if hasattr(self.app_instance, 'scheduled_merchant_run_checkbox') and self.app_instance.scheduled_merchant_run_checkbox:
                    enable_merchant_run_setting = self.app_instance.scheduled_merchant_run_checkbox.isChecked()

                # Anticipate new UI elements for currency updates
                currency_updates_enabled_setting = self.currency_updates_enabled
                if hasattr(self.app_instance, 'currency_updates_enabled_checkbox') and self.app_instance.currency_updates_enabled_checkbox:
                    currency_updates_enabled_setting = self.app_instance.currency_updates_enabled_checkbox.isChecked()
                
                currency_updates_delay_setting = self.currency_updates_delay_minutes
                if hasattr(self.app_instance, 'currency_updates_delay_spinbox'): # Assuming a QSpinBox or similar
                    try:
                        currency_updates_delay_setting = self.app_instance.currency_updates_delay_spinbox.value()
                    except AttributeError: # Fallback if .value() isn't the right method or widget doesn't exist
                        pass

                config = {
                    'webhook_url': self.app_instance.webhook_entry.text().strip() if hasattr(self.app_instance, 'webhook_entry') else self.webhook_url,
                    'ps_link': self.app_instance.pslink_entry.text().strip() if hasattr(self.app_instance, 'pslink_entry') else self.ps_link,
                    'royal_chest_ping_id': self.app_instance.royal_chest_ping_entry.text().strip() if hasattr(self.app_instance, 'royal_chest_ping_entry') else self.royal_chest_ping_id,
                    'royal_chest_ping_type': self.app_instance.royal_chest_ping_type_combo.currentText() if hasattr(self.app_instance, 'royal_chest_ping_type_combo') else self.royal_chest_ping_type,
                    'gum_rift_ping_id': self.app_instance.gum_rift_ping_entry.text().strip() if hasattr(self.app_instance, 'gum_rift_ping_entry') else self.gum_rift_ping_id,
                    'gum_rift_ping_type': self.app_instance.gum_rift_ping_type_combo.currentText() if hasattr(self.app_instance, 'gum_rift_ping_type_combo') else self.gum_rift_ping_type,
                    'dice_chest_ping_id': self.app_instance.dice_chest_ping_entry.text().strip() if hasattr(self.app_instance, 'dice_chest_ping_entry') else self.dice_chest_ping_id,
                    'dice_chest_ping_type': self.app_instance.dice_chest_ping_type_combo.currentText() if hasattr(self.app_instance, 'dice_chest_ping_type_combo') else self.dice_chest_ping_type,
                    'launcher_choice': self.app_instance.launcher_combo.currentText() if hasattr(self.app_instance, 'launcher_combo') else self.launcher_choice,
                    'server_mode': self.app_instance.server_mode_combo.currentText() if hasattr(self.app_instance, 'server_mode_combo') else self.server_mode,
                    'automation_enabled': self.app_instance.automation_enabled_checkbox.isChecked() if hasattr(self.app_instance, 'automation_enabled_checkbox') else self.automation_enabled,
                    'teleport_coords': self.teleport_coords,
                    'claw_skip_coords': self.claw_skip_coords,
                    'claw_claim_coords': self.claw_claim_coords,
                    'claw_start_coords': self.claw_start_coords,
                    'current_path': current_path,
                    'map_up_arrow_coords': self.map_up_arrow_coords,
                    'map_down_arrow_coords': self.map_down_arrow_coords,
                    'shop_item1_coords': self.shop_item1_coords,
                    'shop_item2_coords': self.shop_item2_coords,
                    'shop_item3_coords': self.shop_item3_coords,
                    'hatch_username': self.app_instance.hatch_username_entry.text().strip() if hasattr(self.app_instance, 'hatch_username_entry') else self.hatch_username,
                    'hatch_secret_ping_enabled': self.app_instance.hatch_secret_ping_checkbox.isChecked() if hasattr(self.app_instance, 'hatch_secret_ping_checkbox') else self.hatch_secret_ping_enabled,
                    'hatch_secret_ping_user_id': self.app_instance.hatch_userid_entry.text().strip() if hasattr(self.app_instance, 'hatch_userid_entry') else self.hatch_secret_ping_user_id,
                    'hatch_detection_enabled': self.app_instance.hatch_detection_enabled_checkbox.isChecked() if hasattr(self.app_instance, 'hatch_detection_enabled_checkbox') else self.hatch_detection_enabled,
                    'tutorial_shown': self.tutorial_shown,
                    'spam_e_for_ticket_path': spam_e_setting,
                    'enable_scheduled_merchant_run': enable_merchant_run_setting,
                    'currency_updates_enabled': currency_updates_enabled_setting,
                    'currency_updates_delay_minutes': currency_updates_delay_setting,
                    'currency_display_area_coords': self.currency_display_area_coords, # This will be set by calibration
                    'merchant_shop_area_coords': self.merchant_shop_area_coords, # New, set by calibration
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
                    'dice_chest_ping_id': self.dice_chest_ping_id,
                    'dice_chest_ping_type': self.dice_chest_ping_type,
                    'launcher_choice': self.launcher_choice,
                    'server_mode': self.server_mode,
                    'automation_enabled': self.automation_enabled,
                    'teleport_coords': self.teleport_coords,
                    'claw_skip_coords': self.claw_skip_coords,
                    'claw_claim_coords': self.claw_claim_coords,
                    'claw_start_coords': self.claw_start_coords,
                    'current_path': self.current_path,
                    'map_up_arrow_coords': self.map_up_arrow_coords,
                    'map_down_arrow_coords': self.map_down_arrow_coords,
                    'shop_item1_coords': self.shop_item1_coords,
                    'shop_item2_coords': self.shop_item2_coords,
                    'shop_item3_coords': self.shop_item3_coords,
                    'hatch_username': self.hatch_username,
                    'hatch_secret_ping_enabled': self.hatch_secret_ping_enabled,
                    'hatch_secret_ping_user_id': self.hatch_secret_ping_user_id,
                    'hatch_detection_enabled': self.hatch_detection_enabled,
                    'tutorial_shown': self.tutorial_shown,
                    'spam_e_for_ticket_path': self.spam_e_for_ticket_path,
                    'enable_scheduled_merchant_run': self.enable_scheduled_merchant_run,
                    'currency_updates_enabled': self.currency_updates_enabled,
                    'currency_updates_delay_minutes': self.currency_updates_delay_minutes,
                    'currency_display_area_coords': self.currency_display_area_coords,
                    'merchant_shop_area_coords': self.merchant_shop_area_coords, # New
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
        """Apply loaded configuration to UI elements"""
        if self.app_instance:
            if hasattr(self.app_instance, 'webhook_entry'):
                self.app_instance.webhook_entry.setText(self.webhook_url)
            if hasattr(self.app_instance, 'pslink_entry'):
                self.app_instance.pslink_entry.setText(self.ps_link)
            
            # Pings settings
            if hasattr(self.app_instance, 'royal_chest_ping_entry'):
                self.app_instance.royal_chest_ping_entry.setText(self.royal_chest_ping_id)
            if hasattr(self.app_instance, 'royal_chest_ping_type_combo'):
                self.app_instance.royal_chest_ping_type_combo.setCurrentText(self.royal_chest_ping_type)
            if hasattr(self.app_instance, 'gum_rift_ping_entry'):
                self.app_instance.gum_rift_ping_entry.setText(self.gum_rift_ping_id)
            if hasattr(self.app_instance, 'gum_rift_ping_type_combo'):
                self.app_instance.gum_rift_ping_type_combo.setCurrentText(self.gum_rift_ping_type)
            if hasattr(self.app_instance, 'dice_chest_ping_entry'):
                self.app_instance.dice_chest_ping_entry.setText(self.dice_chest_ping_id)
            if hasattr(self.app_instance, 'dice_chest_ping_type_combo'):
                self.app_instance.dice_chest_ping_type_combo.setCurrentText(self.dice_chest_ping_type)

            # Launcher and Server mode
            if hasattr(self.app_instance, 'launcher_combo'):
                self.app_instance.launcher_combo.setCurrentText(self.launcher_choice)
            if hasattr(self.app_instance, 'server_mode_combo'):
                self.app_instance.server_mode_combo.setCurrentText(self.server_mode)
            
            # Automation settings (formerly collection)
            if hasattr(self.app_instance, 'automation_enabled_checkbox'):
                self.app_instance.automation_enabled_checkbox.setChecked(self.automation_enabled)

            # Hatch settings
            if hasattr(self.app_instance, 'hatch_username_entry'):
                self.app_instance.hatch_username_entry.setText(self.hatch_username)
            if hasattr(self.app_instance, 'hatch_secret_ping_checkbox'):
                self.app_instance.hatch_secret_ping_checkbox.setChecked(self.hatch_secret_ping_enabled)
            if hasattr(self.app_instance, 'hatch_userid_entry'):
                self.app_instance.hatch_userid_entry.setText(self.hatch_secret_ping_user_id)
            if hasattr(self.app_instance, 'hatch_detection_enabled_checkbox'):
                self.app_instance.hatch_detection_enabled_checkbox.setChecked(self.hatch_detection_enabled)

            # Apply the new E spam setting to its checkbox if it exists
            if hasattr(self.app_instance, 'spam_e_checkbox') and self.app_instance.spam_e_checkbox:
                self.app_instance.spam_e_checkbox.setChecked(self.spam_e_for_ticket_path)

            # Apply the new scheduled merchant run setting to its checkbox if it exists
            if hasattr(self.app_instance, 'scheduled_merchant_run_checkbox') and self.app_instance.scheduled_merchant_run_checkbox:
                self.app_instance.scheduled_merchant_run_checkbox.setChecked(self.enable_scheduled_merchant_run)

            # Apply currency update settings to UI
            if hasattr(self.app_instance, 'currency_updates_enabled_checkbox'):
                self.app_instance.currency_updates_enabled_checkbox.setChecked(self.currency_updates_enabled)
            if hasattr(self.app_instance, 'currency_updates_delay_spinbox'): # Assuming QSpinBox
                self.app_instance.currency_updates_delay_spinbox.setValue(self.currency_updates_delay_minutes)
            # The currency_display_area_coords will affect a calibration button's text, handled in update_all_calibration_buttons_text
            # The merchant_shop_area_coords will also affect a calibration button's text

            # Update calibration button texts (which depend on loaded coords)
            if hasattr(self.app_instance, 'collection_manager'):
                self.app_instance.collection_manager.update_all_calibration_buttons_text()
            
            # Update path selector (which depends on loaded current_path)
            # Ensure this is called after collection_manager might have been initialized and paths loaded
            if hasattr(self.app_instance, 'update_automation_type_selector'):
                 self.app_instance.update_automation_type_selector() # This will set based on self.current_path

            # Auto start (which seems to be tied to automation_enabled_checkbox)
            # if hasattr(self.app_instance, 'automation_enabled_checkbox'):
            #    self.app_instance.automation_enabled_checkbox.setChecked(self.auto_start)
        print("Configuration applied to UI.") 