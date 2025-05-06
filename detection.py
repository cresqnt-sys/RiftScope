import os
import time
import re
from datetime import datetime
from utils import read_last_n_lines, extract_timestamp, is_roblox_running

class RiftDetector:
    """Class for detecting various rifts and events in Roblox logs"""
    
    def __init__(self, app=None):
        self.app = app
        self.processed_lines = set()
        self.current_log = None
        self.last_line_time = time.time()
        self.last_timestamp = None
        self.lock_log_file = False
        self.last_notification_time = {} # Store last notification time per event type
        
        # Server tracking
        self.current_job_id = None
        self.current_place_id = None
        self.last_server_change_time = None  # Timestamp of last server change (will be stored as string)
        self.initial_server_scan_done = False  # Flag to track if we've done a full scan
        
        # Image URLs for embeds
        self.royal_image_url = "https://ps99.biggamesapi.io/image/76803303814891"
        self.aura_image_url = "https://ps99.biggamesapi.io/image/95563056090518"
        
        # Pet lists for detection
        self.secret_pets = {
            "Giant Chocolate Chicken", "Easter Basket", "MAN FACE GOD", "King Doggy",
            "The Overlord", "Avernus", "Dementor", "Godly Gem", "Royal Trophy", "Silly Doggy :)"
        }
        
        self.legendary_pets = {
            "NULLVoid", "Cardinal Bunny", "Rainbow Marshmellow", "Rainbow Shock",
            "Ethereal Bunny", "Hexarium", "Seraph", "Sweet Treat", "Abyssal Dragon",
            "Beta TV", "Crescent Empress", "Dark Phoenix", "Dark Serpent", "Demonic Dogcat",
            "Demonic Hydra", "Discord Imp", "Dowodle", "Dualcorn", "Easter Fluffle",
            "Easter Serpent", "Electra", "Emerald Golem", "Evil Shock", "Flying Gem",
            "Flying Pig", "Green Hydra", "Hacker Prism", "Holy Egg", "Holy Shock",
            "Inferno Cube", "Inferno Dragon", "Infernus", "King Soul", "Kitsune",
            "Lunar Deity", "Lunar Serpent", "Manarium", "Midas", "Moonburst",
            "Neon Elemental", "Ophanim", "Patronus", "Rainbow Blitz", "Seraphic Bunny",
            "Sigma Serpent", "Solar Deity", "Sunburst", "Trio Cube", "Umbra",
            "Unicorn", "Virus", "Chocolate Bunny", "Diamond Hexarium", "Diamond Serpent", 
            "DOOF", "Electra Hydra", "Elite Challenger", "Elite Soul", "Enraged Phoenix", 
            "King Pufferfish", "Overseer", "Parasite", "ROUND", "Starlight"
        }
        
    def get_log_dir(self):
        """Returns the appropriate log directory based on available Roblox launchers."""
        home = os.path.expanduser("~")

        log_paths = {
            "Fishstrap": os.path.join(home, "AppData", "Local", "Fishstrap", "Logs"),
            "Bloxstrap": os.path.join(home, "AppData", "Local", "Roblox", "Logs"),  
            "Roblox": os.path.join(home, "AppData", "Local", "Roblox", "Logs")
        }

        if self.app and hasattr(self.app, 'launcher_combo'):
            choice = self.app.launcher_combo.currentText()
            if choice in log_paths:
                return log_paths[choice]
            elif choice == "Auto (Detect)":
                pass  # Fall through to auto-detection

        valid_paths = []
        for launcher, path in log_paths.items():
            if os.path.isdir(path):
                try:
                    if any(os.path.isfile(os.path.join(path, f)) for f in os.listdir(path)):
                        valid_paths.append((launcher, path))

                        if self.app and hasattr(self.app, 'launcher_status'):
                            self.app.launcher_status.setText(f"Found {launcher} logs")
                except Exception:
                    continue

        if is_roblox_running() and valid_paths:
            most_recent = None
            most_recent_time = 0
            most_recent_launcher = None

            for launcher, path in valid_paths:
                try:
                    files = [os.path.join(path, f) for f in os.listdir(path) if os.path.isfile(os.path.join(path, f))]
                    if files:
                        latest = max(files, key=os.path.getmtime)
                        mod_time = os.path.getmtime(latest)
                        if mod_time > most_recent_time:
                            most_recent = path
                            most_recent_time = mod_time
                            most_recent_launcher = launcher
                except Exception:
                    continue

            if most_recent:
                if self.app and hasattr(self.app, 'launcher_status'):
                    self.app.launcher_status.setText(f"Active: {most_recent_launcher}")
                return most_recent

        for launcher_name in ["Fishstrap", "Bloxstrap", "Roblox"]:
            for launcher, path in valid_paths:
                if launcher == launcher_name:
                    if self.app and hasattr(self.app, 'launcher_status'):
                        self.app.launcher_status.setText(f"Using: {launcher}")
                    return path

        if self.app and hasattr(self.app, 'launcher_status'):
            self.app.launcher_status.setText("No logs found")

        return log_paths["Fishstrap"]
    
    def get_latest_log_file(self):
        """Get the most recently modified log file"""
        try:
            log_dir = self.get_log_dir()
            if not os.path.isdir(log_dir):
                 print(f"Log directory not found: {log_dir}")
                 return None
            files = [os.path.join(log_dir, f) for f in os.listdir(log_dir) if os.path.isfile(os.path.join(log_dir, f))]
            return max(files, key=os.path.getmtime) if files else None
        except Exception as e:
            print(f"Error finding latest log file: {e}")
            if self.app:
                self.app.update_status(f"Error finding log file: {e}")
            return None
    
    def monitor_log(self):
        """Main monitoring loop for detecting events in logs"""
        if hasattr(self, 'monitor_thread') and self.monitor_thread:
            self.monitor_thread.webhook_signal.emit(
                "▶️ RiftScope Started",
                "RiftScope is now monitoring for rare rifts!",
                None,
                0x7289DA,
                None
            )
        self.last_line_time = time.time()
        self.last_timestamp = None 
        self.processed_lines.clear() 

        log_dir = self.get_log_dir()
        launcher_used = "Unknown"
        for name in ["Fishstrap", "Bloxstrap", "Roblox"]:
            if name.lower() in log_dir.lower():
                launcher_used = name
                break

        if hasattr(self, 'monitor_thread') and self.monitor_thread:
            self.monitor_thread.update_status_signal.emit(f"Monitoring using {launcher_used} logs at {log_dir}")

        if self.lock_log_file:
            locked_log = self.get_latest_log_file()
            if locked_log:
                self.current_log = locked_log
                if hasattr(self, 'monitor_thread') and self.monitor_thread:
                    self.monitor_thread.update_status_signal.emit(f"Locked onto log file: {os.path.basename(locked_log)}")
            else:
                if hasattr(self, 'monitor_thread') and self.monitor_thread:
                    self.monitor_thread.update_status_signal.emit("No log file found to lock onto. Waiting...")
                return 

        # Debug flag - set to true to log all lines for debugging server detection
        debug_log_all_lines = False
        
        # Keep track of the last time we checked for server changes
        last_server_check_time = time.time()
        
        # Time interval between full log scans for server changes (in seconds)
        server_check_interval = 90  # Less frequent to reduce spam
        
        # If using public server mode and no current server, perform an initial full scan
        if (self.app and hasattr(self.app, 'server_mode_combo') and 
            self.app.server_mode_combo.currentText() == "Public Server" and 
            not self.current_job_id and not self.initial_server_scan_done):
            
            if hasattr(self, 'monitor_thread') and self.monitor_thread:
                self.monitor_thread.update_status_signal.emit("🔍 Performing initial full log scan for server ID...")
            
            # Get the latest log
            if self.current_log:
                try:
                    # Read the entire log file
                    with open(self.current_log, 'r', encoding='utf-8', errors='ignore') as f:
                        full_log_lines = f.readlines()
                    
                    if hasattr(self, 'monitor_thread') and self.monitor_thread:
                        self.monitor_thread.update_status_signal.emit(f"Scanning {len(full_log_lines)} lines for server info...")
                    
                    # Check for server info
                    self.check_for_server_changes(full_log_lines)
                    
                    # Mark the initial scan as complete
                    self.initial_server_scan_done = True
                    
                    if self.current_job_id:
                        if hasattr(self, 'monitor_thread') and self.monitor_thread:
                            self.monitor_thread.update_status_signal.emit(f"✅ Found server in initial scan: {self.current_job_id[:8]}...")
                    else:
                        if hasattr(self, 'monitor_thread') and self.monitor_thread:
                            self.monitor_thread.update_status_signal.emit("⚠️ No server info found in initial scan. Will continue monitoring...")
                except Exception as e:
                    if hasattr(self, 'monitor_thread') and self.monitor_thread:
                        self.monitor_thread.update_status_signal.emit(f"Error during initial scan: {e}")
                    
                # Reset the last check time after the initial scan
                last_server_check_time = time.time()

        while self.app and self.app.running: 
            if not self.lock_log_file or not self.current_log:
                latest_log = self.get_latest_log_file()
                if latest_log and latest_log != self.current_log:
                    self.current_log = latest_log
                    if hasattr(self, 'monitor_thread') and self.monitor_thread:
                        self.monitor_thread.update_status_signal.emit(f"Monitoring log file: {os.path.basename(latest_log)}")
                    self.processed_lines.clear() 
                    self.last_timestamp = None 

            # Check again if the app is still running
            if not self.app or not self.app.running:
                break

            if not self.current_log:
                if hasattr(self, 'monitor_thread') and self.monitor_thread:
                    self.monitor_thread.update_status_signal.emit("No log file found. Waiting...")
                time.sleep(5) 
                self.last_line_time = time.time() 
                continue

            try:
                # Check if app is still running before expensive operations
                if not self.app or not self.app.running:
                    break
                    
                # Increase the number of lines to read to improve chances of catching server joins
                lines = read_last_n_lines(self.current_log, n=30)
                new_line_found = False
                
                # Check again if app is still running after file read
                if not self.app or not self.app.running:
                    break
                    
                # Periodically do a full scan for server changes, but only if using public server mode
                current_time = time.time()
                if (current_time - last_server_check_time > server_check_interval and 
                    self.app and hasattr(self.app, 'server_mode_combo') and 
                    self.app.server_mode_combo.currentText() == "Public Server"):
                    
                    if hasattr(self, 'monitor_thread') and self.monitor_thread:
                        self.monitor_thread.update_status_signal.emit("Performing periodic server check...")
                    
                    # Do a deep scan with more lines to find server changes (limited to 500 lines)
                    deep_scan_lines = read_last_n_lines(self.current_log, n=500)
                    
                    # Check again if app is still running before expensive operation
                    if not self.app or not self.app.running:
                        break
                        
                    self.check_for_server_changes(deep_scan_lines)
                    last_server_check_time = current_time

                for line in lines:
                    # Check if app is still running periodically
                    if not self.app or not self.app.running:
                        break
                        
                    if not line.strip():
                        continue

                    # Debug option to print all lines for troubleshooting
                    if debug_log_all_lines and hasattr(self, 'monitor_thread') and self.monitor_thread:
                        self.monitor_thread.update_status_signal.emit(f"DEBUG Line: {line[:100]}...")
                        
                    # Extract timestamp from line
                    line_timestamp = extract_timestamp(line)
                    
                    # Create a hash for deduplication
                    line_hash = hash(line) 
                    if line_hash in self.processed_lines:
                        continue

                    new_line_found = True 
                    self.processed_lines.add(line_hash) 

                    if len(self.processed_lines) > 500:
                        try:
                            self.processed_lines.pop()
                        except KeyError:
                            pass 

                    timestamp = extract_timestamp(line)
                    current_real_time = time.time() # Use current time for cooldown checks
                    cooldown_seconds = 2.0 # Cooldown period in seconds
                    
                    # Regex pattern for hatch detection
                    hatch_pattern = re.compile(r'<b><font color="#[0-9a-fA-F]{6}">([^<]+)</font> just hatched a <font color="([^"]+)">([^<]+?)(?: \(([^)]+%)\))?</font></b>')
                    
                    # Check for server changes only in specific type of lines to reduce false positives
                    if any(keyword in line for keyword in ["Joining game", "JoinGame", "Game (", "TeleportService:Teleport", "Disconnected from Game", "Connected to Game"]):
                        # Only process server join events if we're in public server mode
                        if self.app and hasattr(self.app, 'server_mode_combo') and self.app.server_mode_combo.currentText() == "Public Server":
                            self.check_for_server_changes([line])
                    
                    # Royal chest detection
                    if "🔮" in line:
                        # Check cooldown before processing
                        last_sent = self.last_notification_time.get('royal_chest', 0)
                        if current_real_time - last_sent >= cooldown_seconds:
                            if hasattr(self, 'monitor_thread') and self.monitor_thread:
                                self.monitor_thread.update_status_signal.emit("✨ Royal chest detected!")
                                ping_id = self.app.royal_chest_ping_entry.text().strip()
                                ping_type = self.app.royal_chest_ping_type_combo.currentText()
                                ping_mention = f"<@{ping_id}>" if ping_type == "User" else f"<@&{ping_id}>"
                                self.monitor_thread.webhook_signal.emit(
                                    "✨ ROYAL CHEST DETECTED! ✨",
                                    f"A royal chest has been found in the chat!",
                                    self.royal_image_url,
                                    0x9b59b6,
                                    ping_mention if ping_id else None
                                )
                                self.last_notification_time['royal_chest'] = current_real_time # Update last sent time
                        # else: # Optional: Log cooldown skip
                        #    if hasattr(self, 'monitor_thread') and self.monitor_thread:
                        #        self.monitor_thread.update_status_signal.emit("Royal chest detected (cooldown). Skipping ping.")

                    # Gum rift detection
                    elif "Bring us your gum, Earthlings!" in line:
                        # Check cooldown before processing
                        last_sent = self.last_notification_time.get('gum_rift', 0)
                        if current_real_time - last_sent >= cooldown_seconds:
                            if hasattr(self, 'monitor_thread') and self.monitor_thread:
                                self.monitor_thread.update_status_signal.emit("🫧 Gum Rift detected!")
                                ping_id = self.app.gum_rift_ping_entry.text().strip()
                                ping_type = self.app.gum_rift_ping_type_combo.currentText()
                                ping_mention = f"<@{ping_id}>" if ping_type == "User" else f"<@&{ping_id}>"
                                self.monitor_thread.webhook_signal.emit(
                                    "🫧 GUM RIFT DETECTED! 🫧",
                                    f"A gum rift has been found in the chat!",
                                    None,
                                    0xFF69B4,
                                    ping_mention if ping_id else None
                                )
                                self.last_notification_time['gum_rift'] = current_real_time # Update last sent time
                        # else: # Optional: Log cooldown skip
                        #    if hasattr(self, 'monitor_thread') and self.monitor_thread:
                        #        self.monitor_thread.update_status_signal.emit("Gum rift detected (cooldown). Skipping ping.")

                    # Silly egg detection
                    elif "we're so silly and fun" in line:
                        # Check cooldown before processing
                        last_sent = self.last_notification_time.get('silly_egg', 0)
                        if current_real_time - last_sent >= cooldown_seconds:
                            if hasattr(self, 'monitor_thread') and self.monitor_thread:
                                self.monitor_thread.update_status_signal.emit("😂 Silly Egg detected!")
                                self.monitor_thread.webhook_signal.emit(
                                    "😂 SILLY EGG DETECTED! 😂",
                                    f"A Silly Egg has been found in the chat!",
                                    None, 
                                    0xf1c40f, 
                                    "@everyone" 
                                )
                                self.last_notification_time['silly_egg'] = current_real_time # Update last sent time
                        # else: # Optional: Log cooldown skip
                        #    if hasattr(self, 'monitor_thread') and self.monitor_thread:
                        #        self.monitor_thread.update_status_signal.emit("Silly egg detected (cooldown). Skipping ping.")

                    # Dice Chest detection
                    elif "Feeling lucky..?" in line:
                        # Check cooldown before processing
                        last_sent = self.last_notification_time.get('dice_chest', 0)
                        if current_real_time - last_sent >= cooldown_seconds:
                            if hasattr(self, 'monitor_thread') and self.monitor_thread:
                                self.monitor_thread.update_status_signal.emit("🎲 Dice Chest detected!")
                                ping_id = self.app.dice_chest_ping_entry.text().strip()
                                ping_type = self.app.dice_chest_ping_type_combo.currentText()
                                ping_mention = f"<@{ping_id}>" if ping_type == "User" else f"<@&{ping_id}>"
                                self.monitor_thread.webhook_signal.emit(
                                    "🎲 DICE CHEST DETECTED! 🎲",
                                    f"A dice chest has been found in the chat!",
                                    None,
                                    0x3498db,
                                    ping_mention if ping_id else None
                                )
                                self.last_notification_time['dice_chest'] = current_real_time # Update last sent time
                        # else: # Optional: Log cooldown skip
                        #    if hasattr(self, 'monitor_thread') and self.monitor_thread:
                        #        self.monitor_thread.update_status_signal.emit("Dice chest detected (cooldown). Skipping ping.")

                    # Hatch detection
                    elif (self.app and hasattr(self.app, 'hatch_detection_enabled_checkbox') and 
                         self.app.hatch_detection_enabled_checkbox.isChecked() and "just hatched a" in line):
                        print(f"[DEBUG] Found 'just hatched a' in line: {line.strip()}") 
                        match = hatch_pattern.search(line)
                        if match:
                            # Pass current_real_time for cooldown check within the function
                            self.process_hatch_match(match, current_time, line_timestamp, current_real_time)
                            
                if new_line_found:
                    self.last_line_time = time.time() 

                if time.time() - self.last_line_time > 60:
                    if not is_roblox_running():
                        if hasattr(self, 'monitor_thread') and self.monitor_thread:
                            self.monitor_thread.update_status_signal.emit("⚠️ Roblox appears to be closed.")
                            self.monitor_thread.webhook_signal.emit(
                                "⚠️ Roblox Closed",
                                "No new log lines detected recently and Roblox process not found.",
                                None,
                                0xe74c3c,
                                None
                            )
                        self.last_line_time = time.time() 

            except Exception as e:
                error_msg = f"Error during monitoring: {e}"
                print(error_msg)
                if hasattr(self, 'monitor_thread') and self.monitor_thread:
                    self.monitor_thread.update_status_signal.emit(error_msg)

                time.sleep(2)

            time.sleep(0.75)
            
    def check_for_server_changes(self, lines):
        """Check for server changes in the given lines"""
        # Generic server detection keywords that work for all launchers
        server_join_keywords = [
            "Joining game", "JoinGame", 
            "Game (", "ServerInstance", 
            "Disconnected from Game", "Connected to Game",
            "TeleportService:Teleport"
        ]
        
        # Process lines in reverse chronological order (newest first)
        for line in reversed(lines):
            # Skip empty lines and lines without server-related keywords
            if not line.strip() or not any(keyword in line for keyword in server_join_keywords):
                continue
            
            # Extract timestamp from the line
            line_timestamp = extract_timestamp(line)
            
            # Skip older timestamps if we've already detected a server change
            if line_timestamp and self.last_server_change_time:
                # Convert timestamp to string for comparison if it's a datetime
                if isinstance(line_timestamp, datetime):
                    line_timestamp_str = line_timestamp.isoformat()
                else:
                    line_timestamp_str = str(line_timestamp)
                    
                if line_timestamp_str <= self.last_server_change_time:
                    continue
                
            # Try to detect a server change in this line
            if hasattr(self, 'monitor_thread') and self.monitor_thread:
                self.monitor_thread.update_status_signal.emit(f"Checking for server info: {line[:100]}...")
                
            result = self.detect_server_join(line, line_timestamp)
            if result:
                # A new server was found after our last detected change, so we can stop
                break
            
    def detect_server_join(self, line, line_timestamp=None):
        """Detect when the user joins a server and extract JobID and PlaceID"""
        try:
            # Universal patterns that work for all launchers
            patterns = [
                # Standard JobID and PlaceID patterns
                re.compile(r"Joining game '([^']+)' place (\d+)"),
                re.compile(r"JoinGame.+?jobId=([0-9a-f\-]+).+?placeId=(\d+)"),
                re.compile(r"TeleportService:Teleport.+?([0-9a-f\-]+).+?(\d+)"),
                re.compile(r"ServerInstance:\s*([0-9a-f\-]+).+?PlaceId:\s*(\d+)"),
                
                # Reversed order (PlaceID first, then JobID)
                re.compile(r"Game \((\d+)/([0-9a-f\-]+)"),
                re.compile(r"Connected to Game \((\d+)/([0-9a-f\-]+)"),
                re.compile(r"Disconnected from Game \((\d+)/([0-9a-f\-]+)"),
                re.compile(r"Teleporting to \((\d+)/([0-9a-f\-]+)"),
                re.compile(r"placeId=(\d+).+?jobId=([0-9a-f\-]+)"),
                
                # General pattern to find UUID and PlaceID in the same line
                re.compile(r"([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}).*?(\d{8,})")
            ]
            
            match = None
            pattern_used = None
            job_id = None
            place_id = None
            
            # Try each pattern until we find a match
            for i, pattern in enumerate(patterns):
                match = pattern.search(line)
                if match:
                    pattern_used = i + 1
                    # Check pattern order - some patterns have reversed group order
                    if i >= 4 and i <= 8:  # Reversed order patterns
                        place_id = match.group(1)
                        job_id = match.group(2)
                    else:
                        # Standard order: JobID first, then PlaceID
                        job_id = match.group(1)
                        place_id = match.group(2)
                    break
            
            if job_id and place_id:
                # Debug output
                if hasattr(self, 'monitor_thread') and self.monitor_thread:
                    self.monitor_thread.update_status_signal.emit(
                        f"Server match found with pattern {pattern_used}: JobID={job_id}, PlaceID={place_id}"
                    )
                
                # Check if this is a new server
                is_new_server = job_id != self.current_job_id
                
                # Print for debugging
                print(f"[DEBUG] Detected server join: JobID={job_id}, PlaceID={place_id}, IsNew={is_new_server}")
                
                # Check if the timestamp is newer than our last server change
                # If no timestamp provided, assume it's current
                is_newer_timestamp = True
                if line_timestamp and self.last_server_change_time:
                    # Convert timestamp to string for safe comparison
                    if isinstance(line_timestamp, datetime):
                        line_timestamp_str = line_timestamp.isoformat()
                    else:
                        line_timestamp_str = str(line_timestamp)
                        
                    is_newer_timestamp = line_timestamp_str > self.last_server_change_time
                
                if is_new_server and is_newer_timestamp:
                    # Update current server info
                    old_job_id = self.current_job_id
                    self.current_job_id = job_id
                    self.current_place_id = place_id
                    
                    # Update timestamp of server change - store as string to avoid type comparison issues
                    if isinstance(line_timestamp, datetime):
                        self.last_server_change_time = line_timestamp.isoformat()
                    elif line_timestamp:
                        self.last_server_change_time = str(line_timestamp)
                    else:
                        self.last_server_change_time = datetime.now().isoformat()
                    
                    # Log the server detection
                    if hasattr(self, 'monitor_thread') and self.monitor_thread:
                        self.monitor_thread.update_status_signal.emit(f"🎮 Detected server change: JobID {job_id}")
                        
                        # Only send webhook if using public server mode
                        if self.app and hasattr(self.app, 'server_mode_combo') and \
                           self.app.server_mode_combo.currentText() == "Public Server":
                            
                            # Get the RoPro link from the API
                            server_link = ""
                            try:
                                import requests
                                api_url = f"https://api.ropro.io/createInvite.php?universeid=6504986360&serverid={job_id}"
                                response = requests.get(api_url, timeout=5)
                                
                                if response.status_code == 200 and response.text.strip().startswith("http"):
                                    server_link = response.text.strip()
                                else:
                                    # Fallback to API URL
                                    server_link = api_url
                            except Exception as e:
                                print(f"Error getting RoPro link: {e}")
                                # Fallback to API URL
                                server_link = f"https://api.ropro.io/createInvite.php?universeid=6504986360&serverid={job_id}"
                            
                            # Customize message based on whether this is a new server or first detection
                            title = "🌐 New Server Detected"
                            message = f"Joined a new Bubble Gum Simulator server.\nJobID: `{job_id}`"
                            
                            if old_job_id:
                                title = "🔄 Server Changed"
                                message = f"Server has changed from {old_job_id[:8]}... to new server.\nNew JobID: `{job_id}`"
                            
                            self.monitor_thread.webhook_signal.emit(
                                title,
                                message,
                                None,
                                0x3498db,
                                None
                            )
                            
                            # Update the UI with the new server info
                            if hasattr(self.app, 'server_status') and hasattr(self.app, 'pslink_entry'):
                                truncated_id = job_id[:8] + "..." if len(job_id) > 8 else job_id
                                self.app.server_status.setText(f"Current Server: {truncated_id}")
                                if self.app.server_mode_combo.currentText() == "Public Server":
                                    self.app.pslink_entry.setText(server_link)
                    
                    return job_id, place_id
                elif is_new_server:
                    # This is a new server but with an older timestamp
                    if hasattr(self, 'monitor_thread') and self.monitor_thread:
                        self.monitor_thread.update_status_signal.emit(
                            f"Ignoring older server info: JobID={job_id} (timestamp not newer than last change)"
                        )
                
        except Exception as e:
            print(f"Error processing server join: {e}")
            if hasattr(self, 'monitor_thread') and self.monitor_thread:
                self.monitor_thread.update_status_signal.emit(f"Error processing server join: {e}")
                
        return None
    
    def get_server_link(self):
        """Get the appropriate server link based on current settings"""
        if self.app and hasattr(self.app, 'server_mode_combo'):
            mode = self.app.server_mode_combo.currentText()
            
            if mode == "Private Server" and hasattr(self.app, 'pslink_entry'):
                return self.app.pslink_entry.text().strip()
            elif mode == "Public Server" and self.current_job_id:
                # Check if we already have a ro.pro URL in the UI
                if hasattr(self.app, 'pslink_entry'):
                    current_link = self.app.pslink_entry.text().strip()
                    if current_link and "ro.pro" in current_link:
                        return current_link
                
                # Otherwise fetch from API
                try:
                    import requests
                    api_url = f"https://api.ropro.io/createInvite.php?universeid=6504986360&serverid={self.current_job_id}"
                    response = requests.get(api_url, timeout=5)
                    
                    if response.status_code == 200 and response.text.strip().startswith("http"):
                        return response.text.strip()
                    
                    # Fallback to API URL
                    return api_url
                except Exception as e:
                    print(f"Error in get_server_link: {e}")
                    # Fallback to API URL
                    return f"https://api.ropro.io/createInvite.php?universeid=6504986360&serverid={self.current_job_id}"
                
        return ""
    
    def process_hatch_match(self, match, current_time, line_timestamp=None, current_real_time=None):
        """Process a regex match for hatched pet"""
        print("[DEBUG] Regex match successful!") 
        hatched_username = match.group(1)
        pet_color_hex = match.group(2)
        pet_name = match.group(3).strip() 
        rarity_match = match.group(4) 

        rarity = rarity_match if rarity_match else "Unknown Rarity"

        print(f"[DEBUG] Extracted: User='{hatched_username}', Pet='{pet_name}', Rarity='{rarity}'") 

        base_pet_name = pet_name
        mutation_prefix = ""
        if pet_name.startswith("Shiny Mythic "):
            mutation_prefix = "Shiny Mythic "
            base_pet_name = pet_name[len(mutation_prefix):]
        elif pet_name.startswith("Mythic "):
            mutation_prefix = "Mythic "
            base_pet_name = pet_name[len(mutation_prefix):]
        elif pet_name.startswith("Shiny "):
            mutation_prefix = "Shiny "
            base_pet_name = pet_name[len(mutation_prefix):]

        if mutation_prefix:
            print(f"[DEBUG] Mutation detected. Base Pet Name for check: '{base_pet_name}'")

        is_secret = base_pet_name in self.secret_pets
        is_legendary = base_pet_name in self.legendary_pets
        print(f"[DEBUG] Is Base Secret: {is_secret}, Is Base Legendary: {is_legendary}")

        if is_secret or is_legendary:
            print(f"[DEBUG] Base Pet ('{base_pet_name}') is Secret or Legendary.")

            target_username = self.app.hatch_username_entry.text().strip()
            if target_username and hatched_username.lower() == target_username.lower():
                print(f"[DEBUG] Username '{hatched_username}' matches target '{target_username}'. Proceeding...")

                # Check cooldown before processing hatch notification
                if current_real_time is None: # Fallback if not passed
                     current_real_time = time.time()
                cooldown_seconds = 2.0
                last_sent = self.last_notification_time.get('hatch', 0)

                if current_real_time - last_sent >= cooldown_seconds:
                    print("[DEBUG] Cooldown passed for hatch event.")
                    if hasattr(self, 'monitor_thread') and self.monitor_thread:
                        print("[DEBUG] Monitor thread exists. Sending status/webhook.")
                        pet_type = "Secret" if is_secret else "Legendary"

                        self.monitor_thread.update_status_signal.emit(f"🎉 {pet_type} Pet Hatched by {hatched_username}: {pet_name} ({rarity})")

                        ping_content = None
                        ping_user_id = self.app.hatch_userid_entry.text().strip()

                        if is_secret and self.app.hatch_secret_ping_checkbox.isChecked() and ping_user_id:
                            ping_content = f"<@{ping_user_id}>"

                        try:
                            embed_color = int(pet_color_hex.lstrip('#'), 16)
                        except ValueError:
                            embed_color = 0x7289DA

                        self.monitor_thread.webhook_signal.emit(
                            f"🎉 {pet_type.upper()} PET HATCHED! 🎉",
                            f"**User:** {hatched_username}\n"
                            f"**Pet:** {pet_name}\n"
                            f"**Rarity:** {rarity}",
                            None,
                            embed_color,
                            ping_content
                        )
                        # Update last sent time only after successfully sending
                        self.last_notification_time['hatch'] = current_real_time 
                else:
                     print("[DEBUG] Hatch event skipped due to cooldown.")
                     # Optional: Log cooldown skip
                     if hasattr(self, 'monitor_thread') and self.monitor_thread:
                         pet_type = "Secret" if is_secret else "Legendary"
                         self.monitor_thread.update_status_signal.emit(f"{pet_type} hatch detected for {hatched_username} (cooldown). Skipping ping.")

            else:
                print(f"[DEBUG] Username '{hatched_username}' does not match target '{target_username}' or target is empty. Skipping notification.")
                
    def run_test_scan(self):
        """Run a test scan to verify detection is working"""
        latest_log = self.get_latest_log_file()
        if not latest_log:
            if hasattr(self, 'test_worker') and self.test_worker:
                self.test_worker.update_status_signal.emit("No log file found. Make sure Roblox is running.")
            
            if self.app:
                self.app.send_webhook(
                    "❌ Macro is not detecting correctly (nothing detected)",
                    "Please check fishstrap to see if you left the settings off or check if you left the wrong settings on in the scanner.",
                    None,
                    0xe74c3c,
                    worker_instance=self.test_worker if hasattr(self, 'test_worker') else None
                )
            return False

        if hasattr(self, 'test_worker') and self.test_worker:
            self.test_worker.update_status_signal.emit(f"Testing with log file: {os.path.basename(latest_log)}")

        found = False
        start_time = time.time()
        while not found and time.time() - start_time < 20: 
            if not hasattr(self, 'app') or not self.app or not self.app.test_running:
                if hasattr(self, 'test_worker') and self.test_worker:
                    self.test_worker.update_status_signal.emit("Test scan cancelled.")
                return False

            lines = read_last_n_lines(latest_log, n=50)

            for line in lines:
                if "🌎" in line and "font" in line:
                    if hasattr(self, 'test_worker') and self.test_worker:
                        self.test_worker.update_status_signal.emit("✅ Scanner is working.")
                    if self.app:
                        self.app.send_webhook(
                            "✅ Macro Working!",
                            "Macro is ready to find rifts when you start scanning...",
                            None,
                            0x2ecc71,
                            worker_instance=self.test_worker if hasattr(self, 'test_worker') else None
                        )
                    found = True
                    break

            if not found:
                time.sleep(0.5)

        if not found:
            if hasattr(self, 'test_worker') and self.test_worker:
                self.test_worker.update_status_signal.emit("❌ Test failed. Incorrect game or faulty macro.")
            if self.app:
                self.app.send_webhook(
                    "❌ Macro is not detecting correctly (nothing detected)",
                    "Please check fishstrap to see if you left the settings off or check if you left the wrong settings on in the scanner.",
                    None,
                    0xe74c3c,
                    worker_instance=self.test_worker if hasattr(self, 'test_worker') else None
                )
            return False
            
        return True 