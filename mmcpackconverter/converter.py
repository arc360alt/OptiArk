#!/usr/bin/env python3
"""
MultiMC/Prism Launcher Instance to MRPack Converter
Converts MultiMC/Prism Launcher instances to Modrinth modpack format (.mrpack)
Supports CLI, TUI, and GUI modes

Run with -gui tag in terminal to get a GUI
"""

import json
import os
import sys
import zipfile
import hashlib
import requests
import shutil
from pathlib import Path
from typing import Dict, List, Optional, Any
import configparser
import argparse
from urllib.parse import urlparse
import time
import threading

# GUI imports
try:
    import tkinter as tk
    from tkinter import ttk, filedialog, messagebox, scrolledtext
    GUI_AVAILABLE = True
except ImportError:
    GUI_AVAILABLE = False

# TUI imports
try:
    import curses
    TUI_AVAILABLE = True
except ImportError:
    TUI_AVAILABLE = False

class MultiMCToMRPackConverter:
    def __init__(self, progress_callback=None, log_callback=None):
        self.modrinth_api_base = "https://api.modrinth.com/v2"
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'MultiMC-MRPack-Converter/1.0'
        })
        self.progress_callback = progress_callback
        self.log_callback = log_callback
        
    def log(self, message: str):
        """Log a message"""
        if self.log_callback:
            self.log_callback(message)
        else:
            print(message)
    
    def update_progress(self, current: int, total: int, message: str = ""):
        """Update progress"""
        if self.progress_callback:
            self.progress_callback(current, total, message)
        
    def read_instance_config(self, instance_path: Path) -> Dict[str, Any]:
        """Read MultiMC/Prism instance configuration"""
        config_file = instance_path / "instance.cfg"
        mmc_pack = instance_path / "mmc-pack.json"
        
        config = {}
        
        # Read instance.cfg
        if config_file.exists():
            parser = configparser.ConfigParser()
            parser.read(config_file)
            
            for section in parser.sections():
                for key, value in parser.items(section):
                    config[f"{section}.{key}"] = value
            
            # Also read root level configs
            if parser.has_section('General'):
                for key, value in parser.items('General'):
                    config[key] = value
        
        # Read mmc-pack.json if it exists (for exported instances)
        if mmc_pack.exists():
            with open(mmc_pack, 'r', encoding='utf-8') as f:
                pack_data = json.load(f)
                config.update(pack_data)
        
        return config
    
    def get_minecraft_version(self, config: Dict[str, Any]) -> str:
        """Extract Minecraft version from instance config"""
        version_keys = [
            'IntendedVersion',
            'MinecraftVersion', 
            'minecraft_version',
            'General.IntendedVersion',
            'General.MinecraftVersion'
        ]
        
        for key in version_keys:
            if key in config:
                return str(config[key])
        
        return "1.20.1"  # Default fallback
    
    def get_forge_version(self, config: Dict[str, Any]) -> Optional[str]:
        """Extract Forge version if present"""
        forge_keys = [
            'ForgeVersion',
            'forge_version', 
            'General.ForgeVersion'
        ]
        
        for key in forge_keys:
            if key in config:
                return str(config[key])
        return None
    
    def get_fabric_version(self, config: Dict[str, Any]) -> Optional[str]:
        """Extract Fabric version if present"""
        fabric_keys = [
            'FabricLoaderVersion',
            'fabric_version',
            'General.FabricLoaderVersion'
        ]
        
        for key in fabric_keys:
            if key in config:
                return str(config[key])
        return None
    
    def calculate_file_hash(self, file_path: Path) -> Dict[str, str]:
        """Calculate SHA1 and SHA512 hashes for a file"""
        sha1 = hashlib.sha1()
        sha512 = hashlib.sha512()
        
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(4096), b""):
                sha1.update(chunk)
                sha512.update(chunk)
        
        return {
            'sha1': sha1.hexdigest(),
            'sha512': sha512.hexdigest()
        }
    
    def search_modrinth_mod(self, filename: str, file_hash: str) -> Optional[Dict[str, Any]]:
        """Search for a mod on Modrinth by filename and hash"""
        try:
            # First try to find by hash
            response = self.session.get(
                f"{self.modrinth_api_base}/version_file/{file_hash}?algorithm=sha1"
            )
            
            if response.status_code == 200:
                return response.json()
            
            # If hash search fails, try searching by filename
            search_query = filename.replace('.jar', '').replace('_', ' ').replace('-', ' ')
            response = self.session.get(
                f"{self.modrinth_api_base}/search",
                params={
                    'query': search_query,
                    'limit': 5,
                    'facets': '[["project_type:mod"]]'
                }
            )
            
            if response.status_code == 200:
                results = response.json()
                if results['hits']:
                    project = results['hits'][0]
                    versions_response = self.session.get(
                        f"{self.modrinth_api_base}/project/{project['project_id']}/version"
                    )
                    if versions_response.status_code == 200:
                        versions = versions_response.json()
                        for version in versions:
                            for file in version['files']:
                                if file['filename'].lower() == filename.lower():
                                    return version
            
            time.sleep(0.1)  # Rate limiting
            return None
            
        except Exception as e:
            self.log(f"Error searching for mod {filename}: {e}")
            return None
    
    def process_mods_directory(self, mods_path: Path, minecraft_version: str) -> List[Dict[str, Any]]:
        """Process mods directory and create mod entries for mrpack"""
        mod_entries = []
        
        if not mods_path.exists():
            return mod_entries
        
        mod_files = list(mods_path.glob("*.jar"))
        total_mods = len(mod_files)
        
        for i, mod_file in enumerate(mod_files):
            self.log(f"Processing mod: {mod_file.name}")
            self.update_progress(i, total_mods, f"Processing {mod_file.name}")
            
            # Calculate file hash
            hashes = self.calculate_file_hash(mod_file)
            file_size = mod_file.stat().st_size
            
            # Search for mod on Modrinth
            modrinth_data = self.search_modrinth_mod(mod_file.name, hashes['sha1'])
            
            if modrinth_data:
                # Found on Modrinth - use download URL
                primary_file = None
                for file in modrinth_data['files']:
                    if file['primary']:
                        primary_file = file
                        break
                
                if not primary_file:
                    primary_file = modrinth_data['files'][0]
                
                mod_entry = {
                    "path": f"mods/{mod_file.name}",
                    "hashes": {
                        "sha1": primary_file['hashes']['sha1'],
                        "sha512": primary_file['hashes']['sha512']
                    },
                    "env": {
                        "client": "required",
                        "server": "required"
                    },
                    "downloads": [primary_file['url']],
                    "fileSize": primary_file['size']
                }
                mod_entries.append(mod_entry)
                self.log(f"  Found on Modrinth: {mod_file.name}")
            else:
                self.log(f"  Not found on Modrinth, will include as override: {mod_file.name}")
        
        return mod_entries
    
    def create_mrpack_index(self, instance_path: Path, config: Dict[str, Any]) -> Dict[str, Any]:
        """Create the modrinth.index.json structure"""
        minecraft_version = self.get_minecraft_version(config)
        forge_version = self.get_forge_version(config)
        fabric_version = self.get_fabric_version(config)
        
        # Determine loader
        if forge_version:
            loader = "forge"
            loader_version = forge_version
        elif fabric_version:
            loader = "fabric"
            loader_version = fabric_version
        else:
            loader = "minecraft"
            loader_version = minecraft_version
        
        # Process mods
        mods_path = instance_path / "minecraft" / "mods"
        if not mods_path.exists():
            mods_path = instance_path / "mods"
        
        mod_files = self.process_mods_directory(mods_path, minecraft_version)
        
        # Get instance name
        name = config.get('name', config.get('General.name', instance_path.name))
        summary = f"Converted from MultiMC/Prism instance: {name}"
        
        mrpack_index = {
            "formatVersion": 1,
            "game": "minecraft",
            "versionId": "1.0.0",
            "name": name,
            "summary": summary,
            "files": mod_files,
            "dependencies": {
                "minecraft": minecraft_version
            }
        }
        
        # Add loader dependency
        if loader != "minecraft":
            mrpack_index["dependencies"][loader] = loader_version
        
        return mrpack_index
    
    def copy_overrides(self, instance_path: Path, temp_dir: Path):
        """Copy non-Modrinth files to overrides directory"""
        overrides_dir = temp_dir / "overrides"
        overrides_dir.mkdir(exist_ok=True)
        
        # Copy minecraft directory contents (excluding mods that are on Modrinth)
        minecraft_dir = instance_path / "minecraft"
        if not minecraft_dir.exists():
            minecraft_dir = instance_path
        
        for item in minecraft_dir.iterdir():
            if item.name in ['.minecraft', 'mods']:
                if item.name == 'mods':
                    # Only copy mods that weren't found on Modrinth
                    mods_override_dir = overrides_dir / "mods"
                    mods_override_dir.mkdir(exist_ok=True)
                    
                    for mod_file in item.glob("*.jar"):
                        hashes = self.calculate_file_hash(mod_file)
                        modrinth_data = self.search_modrinth_mod(mod_file.name, hashes['sha1'])
                        
                        if not modrinth_data:
                            shutil.copy2(mod_file, mods_override_dir)
                            self.log(f"Copied {mod_file.name} to overrides")
                else:
                    continue
            elif item.is_dir() and item.name not in ['logs', 'crash-reports', 'saves']:
                shutil.copytree(item, overrides_dir / item.name, dirs_exist_ok=True)
            elif item.is_file() and item.suffix in ['.json', '.txt', '.cfg', '.properties', '.toml']:
                shutil.copy2(item, overrides_dir)
    
    def convert_instance(self, instance_path: Path, output_path: Path) -> bool:
        """Convert a MultiMC/Prism instance to mrpack format"""
        try:
            self.log(f"Converting instance: {instance_path}")
            self.update_progress(0, 100, "Starting conversion...")
            
            # Read instance configuration
            config = self.read_instance_config(instance_path)
            if not config:
                self.log("Error: Could not read instance configuration")
                return False
            
            self.update_progress(10, 100, "Reading configuration...")
            
            # Create temporary directory
            import tempfile
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)
                
                # Create mrpack index
                self.log("Creating modrinth.index.json...")
                self.update_progress(20, 100, "Creating index...")
                mrpack_index = self.create_mrpack_index(instance_path, config)
                
                # Write index file
                index_path = temp_path / "modrinth.index.json"
                with open(index_path, 'w', encoding='utf-8') as f:
                    json.dump(mrpack_index, f, indent=2, ensure_ascii=False)
                
                self.update_progress(80, 100, "Copying overrides...")
                # Copy overrides
                self.log("Copying override files...")
                self.copy_overrides(instance_path, temp_path)
                
                # Create mrpack zip file
                self.update_progress(90, 100, "Creating mrpack...")
                self.log(f"Creating mrpack: {output_path}")
                with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                    for file_path in temp_path.rglob('*'):
                        if file_path.is_file():
                            arcname = file_path.relative_to(temp_path)
                            zipf.write(file_path, arcname)
                
                self.update_progress(100, 100, "Complete!")
                self.log(f"Successfully created mrpack: {output_path}")
                return True
                
        except Exception as e:
            self.log(f"Error converting instance: {e}")
            return False


class TUIAPP:
    def __init__(self, stdscr):
        self.stdscr = stdscr
        self.height, self.width = stdscr.getmaxyx()
        curses.curs_set(0)
        curses.init_pair(1, curses.COLOR_WHITE, curses.COLOR_BLUE)
        curses.init_pair(2, curses.COLOR_BLACK, curses.COLOR_WHITE)
        curses.init_pair(3, curses.COLOR_GREEN, curses.COLOR_BLACK)
        curses.init_pair(4, curses.COLOR_RED, curses.COLOR_BLACK)
        
    def draw_box(self, y, x, h, w, title=""):
        """Draw a box with optional title"""
        for i in range(h):
            for j in range(w):
                if i == 0 or i == h-1:
                    char = "─"
                elif j == 0 or j == w-1:
                    char = "│"
                else:
                    char = " "
                    
                if i == 0 and j == 0:
                    char = "┌"
                elif i == 0 and j == w-1:
                    char = "┐"
                elif i == h-1 and j == 0:
                    char = "└"
                elif i == h-1 and j == w-1:
                    char = "┘"
                    
                try:
                    self.stdscr.addch(y + i, x + j, char)
                except curses.error:
                    pass
                    
        if title:
            title_x = x + (w - len(title)) // 2
            try:
                self.stdscr.addstr(y, title_x, f" {title} ", curses.color_pair(1))
            except curses.error:
                pass
    
    def get_input(self, prompt, y, x):
        """Get user input"""
        curses.curs_set(1)
        self.stdscr.addstr(y, x, prompt)
        self.stdscr.refresh()
        
        input_str = ""
        while True:
            ch = self.stdscr.getch()
            if ch == 10 or ch == 13:  # Enter
                break
            elif ch == 27:  # Escape
                input_str = ""
                break
            elif ch == curses.KEY_BACKSPACE or ch == 127:
                if input_str:
                    input_str = input_str[:-1]
                    self.stdscr.addstr(y, x + len(prompt), " " * 50)
                    self.stdscr.addstr(y, x + len(prompt), input_str)
            elif 32 <= ch <= 126:  # Printable characters
                input_str += chr(ch)
                self.stdscr.addstr(y, x + len(prompt), input_str)
            
            self.stdscr.refresh()
        
        curses.curs_set(0)
        return input_str
    
    def show_progress(self, current, total, message):
        """Show progress bar"""
        if total == 0:
            return
            
        progress_y = self.height // 2 + 3
        bar_width = min(50, self.width - 20)
        filled = int((current / total) * bar_width)
        
        # Clear progress area
        self.stdscr.addstr(progress_y, 10, " " * (self.width - 20))
        self.stdscr.addstr(progress_y + 1, 10, " " * (self.width - 20))
        
        # Draw progress bar
        bar = "█" * filled + "░" * (bar_width - filled)
        self.stdscr.addstr(progress_y, 10, f"Progress: [{bar}] {current}/{total}")
        self.stdscr.addstr(progress_y + 1, 10, message[:self.width-20])
        self.stdscr.refresh()
    
    def log_message(self, message):
        """Add message to log area"""
        # Simple implementation - could be enhanced with scrolling
        pass
    
    def run(self):
        """Run the TUI application"""
        while True:
            self.stdscr.clear()
            
            # Draw title
            title = "MultiMC/Prism to MRPack Converter"
            self.stdscr.addstr(2, (self.width - len(title)) // 2, title, curses.color_pair(1) | curses.A_BOLD)
            
            # Draw main box
            box_height = self.height - 6
            box_width = self.width - 4
            self.draw_box(4, 2, box_height, box_width, "Converter")
            
            # Instructions
            instructions = [
                "1. Enter the path to your MultiMC/Prism instance",
                "2. Choose output location (optional)",
                "3. Press Enter to convert",
                "",
                "Press 'q' to quit"
            ]
            
            for i, instruction in enumerate(instructions):
                self.stdscr.addstr(6 + i, 4, instruction)
            
            # Get instance path
            instance_path = self.get_input("Instance path: ", 12, 4)
            if not instance_path:
                continue
                
            instance_path = Path(instance_path)
            if not instance_path.exists():
                self.stdscr.addstr(14, 4, "Error: Path does not exist!", curses.color_pair(4))
                self.stdscr.addstr(15, 4, "Press any key to continue...")
                self.stdscr.getch()
                continue
            
            if not (instance_path / "instance.cfg").exists():
                self.stdscr.addstr(14, 4, "Error: Not a valid instance!", curses.color_pair(4))
                self.stdscr.addstr(15, 4, "Press any key to continue...")
                self.stdscr.getch()
                continue
            
            # Get output path
            output_path = self.get_input("Output path (optional): ", 13, 4)
            if not output_path:
                output_path = instance_path.parent / f"{instance_path.name}.mrpack"
            else:
                output_path = Path(output_path)
            
            # Convert
            self.stdscr.addstr(15, 4, "Converting...")
            self.stdscr.refresh()
            
            converter = MultiMCToMRPackConverter(
                progress_callback=self.show_progress,
                log_callback=self.log_message
            )
            
            success = converter.convert_instance(instance_path, output_path)
            
            if success:
                self.stdscr.addstr(self.height - 4, 4, "Conversion successful!", curses.color_pair(3))
                self.stdscr.addstr(self.height - 3, 4, f"Saved to: {output_path}")
            else:
                self.stdscr.addstr(self.height - 4, 4, "Conversion failed!", curses.color_pair(4))
            
            self.stdscr.addstr(self.height - 2, 4, "Press any key to continue or 'q' to quit...")
            ch = self.stdscr.getch()
            if ch == ord('q'):
                break


class GUIAPP:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("MultiMC/Prism to MRPack Converter")
        self.root.geometry("700x600")
        self.root.resizable(True, True)
        
        # Variables
        self.instance_path = tk.StringVar()
        self.output_path = tk.StringVar()
        
        self.create_widgets()
        
    def create_widgets(self):
        """Create GUI widgets"""
        # Main frame
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)
        main_frame.rowconfigure(5, weight=1)
        
        # Title
        title_label = ttk.Label(main_frame, text="MultiMC/Prism to MRPack Converter", 
                               font=("Arial", 16, "bold"))
        title_label.grid(row=0, column=0, columnspan=3, pady=(0, 20))
        
        # Instance path selection
        ttk.Label(main_frame, text="Instance Path:").grid(row=1, column=0, sticky=tk.W, pady=5)
        instance_entry = ttk.Entry(main_frame, textvariable=self.instance_path, width=50)
        instance_entry.grid(row=1, column=1, sticky=(tk.W, tk.E), pady=5, padx=(5, 5))
        ttk.Button(main_frame, text="Browse", 
                  command=self.browse_instance).grid(row=1, column=2, pady=5)
        
        # Output path selection
        ttk.Label(main_frame, text="Output Path:").grid(row=2, column=0, sticky=tk.W, pady=5)
        output_entry = ttk.Entry(main_frame, textvariable=self.output_path, width=50)
        output_entry.grid(row=2, column=1, sticky=(tk.W, tk.E), pady=5, padx=(5, 5))
        ttk.Button(main_frame, text="Browse", 
                  command=self.browse_output).grid(row=2, column=2, pady=5)
        
        # Convert button
        self.convert_button = ttk.Button(main_frame, text="Convert to MRPack", 
                                        command=self.start_conversion)
        self.convert_button.grid(row=3, column=0, columnspan=3, pady=20)
        
        # Progress bar
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(main_frame, variable=self.progress_var, 
                                           maximum=100, length=400)
        self.progress_bar.grid(row=4, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=5)
        
        # Log area
        log_frame = ttk.LabelFrame(main_frame, text="Log", padding="5")
        log_frame.grid(row=5, column=0, columnspan=3, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(10, 0))
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)
        
        self.log_text = scrolledtext.ScrolledText(log_frame, height=15, width=70)
        self.log_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
    def browse_instance(self):
        """Browse for instance directory"""
        directory = filedialog.askdirectory(title="Select MultiMC/Prism Instance Directory")
        if directory:
            self.instance_path.set(directory)
            # Auto-generate output path
            if not self.output_path.get():
                output = Path(directory).parent / f"{Path(directory).name}.mrpack"
                self.output_path.set(str(output))
    
    def browse_output(self):
        """Browse for output file"""
        filename = filedialog.asksaveasfilename(
            title="Save MRPack As",
            defaultextension=".mrpack",
            filetypes=[("MRPack files", "*.mrpack"), ("All files", "*.*")]
        )
        if filename:
            self.output_path.set(filename)
    
    def log_message(self, message):
        """Add message to log"""
        self.log_text.insert(tk.END, message + "\n")
        self.log_text.see(tk.END)
        self.root.update_idletasks()
    
    def update_progress(self, current, total, message=""):
        """Update progress bar"""
        if total > 0:
            progress = (current / total) * 100
            self.progress_var.set(progress)
        if message:
            self.log_message(message)
        self.root.update_idletasks()
    
    def conversion_worker(self, instance_path, output_path):
        """Worker thread for conversion"""
        try:
            converter = MultiMCToMRPackConverter(
                progress_callback=self.update_progress,
                log_callback=self.log_message
            )
            
            success = converter.convert_instance(instance_path, output_path)
            
            if success:
                self.root.after(0, lambda: messagebox.showinfo("Success", 
                    f"Conversion completed successfully!\nSaved to: {output_path}"))
            else:
                self.root.after(0, lambda: messagebox.showerror("Error", 
                    "Conversion failed! Check the log for details."))
                    
        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror("Error", f"Conversion failed: {e}"))
        finally:
            self.root.after(0, lambda: self.convert_button.config(state="normal"))
    
    def start_conversion(self):
        """Start the conversion process"""
        instance_path_str = self.instance_path.get()
        output_path_str = self.output_path.get()
        
        if not instance_path_str:
            messagebox.showerror("Error", "Please select an instance directory")
            return
        
        if not output_path_str:
            messagebox.showerror("Error", "Please specify an output path")
            return
        
        instance_path = Path(instance_path_str)
        output_path = Path(output_path_str)
        
        if not instance_path.exists():
            messagebox.showerror("Error", "Instance directory does not exist")
            return
        
        if not (instance_path / "instance.cfg").exists():
            messagebox.showerror("Error", "Not a valid MultiMC/Prism instance")
            return
        
        # Disable button and start conversion in thread
        self.convert_button.config(state="disabled")
        self.log_text.delete(1.0, tk.END)
        self.progress_var.set(0)
        
        thread = threading.Thread(target=self.conversion_worker, 
                                args=(instance_path, output_path))
        thread.daemon = True
        thread.start()
    
    def run(self):
        """Run the GUI application"""
        self.root.mainloop()


def run_tui():
    """Run TUI mode"""
    if not TUI_AVAILABLE:
        print("TUI not available. Install curses module.")
        return
    
    try:
        curses.wrapper(lambda stdscr: TUIAPP(stdscr).run())
    except KeyboardInterrupt:
        pass

def run_gui():
    """Run GUI mode"""
    if not GUI_AVAILABLE:
        print("GUI not available. Install tkinter module.")
        return
    
    app = GUIAPP()
    app.run()

def main():
    parser = argparse.ArgumentParser(description='Convert MultiMC/Prism Launcher instances to MRPack format')
    parser.add_argument('instance_path', nargs='?', help='Path to MultiMC/Prism instance directory')
    parser.add_argument('-o', '--output', help='Output mrpack file path')
    parser.add_argument('--gui', action='store_true', help='Run GUI mode')
    parser.add_argument('--tui', action='store_true', help='Run TUI mode')
    
    args = parser.parse_args()
    
    # GUI mode
    if args.gui:
        run_gui()
        return
    
    # TUI mode
    if args.tui:
        run_tui()
        return
    
    # CLI mode
    if not args.instance_path:
        print("Usage: python script.py <instance_path> [-o output] [--gui] [--tui]")
        print("Or run with --gui or --tui for interactive modes")
        sys.exit(1)
        
        instance_path = Path(args.instance_path)
        if not instance_path.exists():
            print(f"Error: Instance path does not exist: {instance_path}")
            sys.exit(1)
        
        if not (instance_path / "instance.cfg").exists():
            print(f"Error: Not a valid MultiMC/Prism instance (missing instance.cfg)")
            sys.exit(1)
        
        # Determine output path
        if args.output:
            output_path = Path(args.output)
        else:
            output_path = instance_path.parent / f"{instance_path.name}.mrpack"
        
        # Ensure output directory exists
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Convert instance
        converter = MultiMCToMRPackConverter()
        success = converter.convert_instance(instance_path, output_path)
        
        if success:
            print(f"\nConversion completed successfully!")
            print(f"MRPack saved to: {output_path}")
            print(f"You can now upload this file to Modrinth or use it with compatible launchers.")
        else:
            print("Conversion failed!")
            sys.exit(1)
        return
    
    # Default to GUI mode if no specific mode is chosen
    run_gui()

if __name__ == "__main__":
    main()
