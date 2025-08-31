

import os
import json
import re
import time
import sys

# Attempt to import required libraries, provide instructions if they fail.
try:
    from mcrcon import MCRcon
    import tailer
except ImportError as e:
    print(f"Error: A required library is not installed: {e.name}")
    if e.name == "mcrcon":
        print("Please install it by running: pip install mcrcon")
    elif e.name == "tailer":
        print("Please install it by running: pip install tailer")
    sys.exit(1)

class DecorationBuilderListener:
    def __init__(self):
        self.config = self._load_config()
        if not self.config:
            sys.exit(1)
        
        self.rcon_client = MCRcon(self.config['server_address'], self.config['rcon_password'])
        # New regex to capture commands: "list" and "add <number>"
        self.chat_pattern = re.compile(r'<([a-zA-Z0-9_-]+)> (list|add (\d+))')
        self.box_dir = os.path.join(os.path.dirname(__file__), '..', 'box')

    def _load_config(self):
        config_path = os.path.join(os.path.dirname(__file__), '..', 'config', 'rcon_settings.json')
        try:
            with open(config_path, 'r') as f:
                print("Configuration loaded.")
                return json.load(f)
        except Exception as e:
            print(f"Error loading configuration: {e}")
            return None

    def _get_player_position(self, player_name):
        try:
            response = self.rcon_client.command(f"data get entity {player_name} Pos")
            match = re.search(r'\[([\d\.\-e]+)d, ([\d\.\-e]+)d, ([\d\.\-e]+)d\]', response)
            if match:
                x, y, z = int(float(match.group(1))), int(float(match.group(2))), int(float(match.group(3)))
                print(f"Player {player_name} position: ({x}, {y}, {z})")
                return x, y, z
            else:
                self._tell_player(player_name, "Could not determine your position.", "red")
                return None
        except Exception as e:
            print(f"Error getting player position: {e}")
            return None

    def _tell_player(self, player_name, message, color="gold"):
        msg_json = f'{{"text":"[Builder] {message}","color":"{color}"}}'
        self.rcon_client.command(f"tellraw {player_name} {msg_json}")

    def _get_decorations(self):
        """Scans the box directory for valid .json files and returns a sorted list of filenames."""
        if not os.path.exists(self.box_dir):
            return []
        files = [f for f in os.listdir(self.box_dir) if f.endswith('.json')]
        return sorted(files)

    def _list_decorations(self, player_name):
        """Lists available decorations to the player in chat."""
        decorations = self._get_decorations()
        if not decorations:
            self._tell_player(player_name, "No decorations found in the 'box' folder.", "yellow")
            return

        self._tell_player(player_name, "--- Available Decorations ---", "yellow")
        for i, filename in enumerate(decorations):
            try:
                with open(os.path.join(self.box_dir, filename), 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    description = data.get('description', 'No description')
                self._tell_player(player_name, f"[{i+1}] {description}", "white")
            except Exception:
                self._tell_player(player_name, f"[{i+1}] Error reading: {filename}", "dark_red")
        self._tell_player(player_name, "Use 'add <number>' to build.", "aqua")

    def _build_decoration(self, player_name, decoration_filename):
        base_coords = self._get_player_position(player_name)
        if not base_coords:
            return
        base_x, base_y, base_z = base_coords

        json_path = os.path.join(self.box_dir, decoration_filename)
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            blocks = data.get("blocks", [])
            description = data.get("description", decoration_filename)
        except Exception as e:
            self._tell_player(player_name, "Failed to read or parse decoration file.", "red")
            print(f"Error reading JSON {json_path}: {e}")
            return

        if not blocks:
            self._tell_player(player_name, "Decoration file is empty.", "yellow")
            return

        self._tell_player(player_name, f"Starting to build '{description}'... ({len(blocks)} blocks)")
        for i, block in enumerate(blocks):
            abs_x = base_x + block['x']
            abs_y = base_y + block['y']
            abs_z = base_z + block['z']
            block_type = block['block_type']
            cmd = f"setblock {abs_x} {abs_y} {abs_z} {block_type}"
            self.rcon_client.command(cmd)
            if (i + 1) % 100 == 0:
                time.sleep(0.1)
        
        self._tell_player(player_name, f"Successfully built '{description}'!", "green")
        print(f"Finished building {description} for {player_name}.")

    def listen(self):
        log_path = self.config.get('log_file_path')
        if not log_path or not os.path.exists(log_path):
            print(f"Error: Log file not found at path specified in config: {log_path}")
            return

        print(f"Listener active. In-game commands: 'list', 'add <number>'")
        
        try:
            self.rcon_client.connect()
            self._tell_player("@a", "Decoration listener is now active.", "aqua")
            
            for line in tailer.follow(open(log_path, encoding='gbk', errors='replace')):
                if '<' not in line or '>' not in line:
                    continue
                
                match = self.chat_pattern.search(line)
                if not match:
                    continue

                player = match.group(1)
                command = match.group(2)
                print(f"Detected command from {player}: {command}")

                if command == "list":
                    self._list_decorations(player)
                else: # It must be "add <number>"
                    try:
                        index = int(match.group(3)) - 1
                        decorations = self._get_decorations()
                        if 0 <= index < len(decorations):
                            self._build_decoration(player, decorations[index])
                        else:
                            self._tell_player(player, f"Invalid number. Use 'list' to see available decorations.", "red")
                    except (ValueError, IndexError):
                        self._tell_player(player, "Invalid command format. Use 'list' or 'add <number>'.", "red")

        except Exception as e:
            print(f"A critical error occurred: {e}")
        finally:
            print("Listener shutting down.")
            if self.rcon_client.socket:
                self.rcon_client.disconnect()

if __name__ == '__main__':
    listener = DecorationBuilderListener()
    listener.listen()