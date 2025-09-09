import os
import shutil
from pathlib import Path

def replace_optiark_icons():
    """
    Searches for folders containing 'OptiArk' in their name, replaces
    the 'icon.png' file inside them with 'new.png' from the script's directory,
    and updates version numbers in instance.cfg files.
    """
    # Get the directory where the script is located
    script_dir = Path(__file__).parent.absolute()
    new_icon_path = script_dir / "new.png"
    
    # Get user input for version replacement
    old_version = input("Enter the version to replace (e.g., '1.7'): ").strip()
    new_version = input("Enter the new version (e.g., '1.8'): ").strip()
    
    if not old_version or not new_version:
        print("Error: Both old and new versions must be provided.")
        return
    
    # Check if the new.png file exists
    if not new_icon_path.exists():
        print(f"Error: 'new.png' not found in {script_dir}")
        return
    
    print(f"Script directory: {script_dir}")
    print(f"Looking for folders containing 'OptiArk'...")
    print(f"Will replace '{old_version}' with '{new_version}' in instance.cfg files")
    
    folders_found = 0
    icons_replaced = 0
    configs_updated = 0
    
    # Walk through all subdirectories in the script's directory
    for root, dirs, files in os.walk(script_dir):
        for dir_name in dirs:
            # Check if the folder name contains "OptiArk"
            if "OptiArk" in dir_name:
                folders_found += 1
                folder_path = Path(root) / dir_name
                minecraft_dir = folder_path / "minecraft"
                icon_path = minecraft_dir / "icon.png"
                
                print(f"\nFound OptiArk folder: {folder_path}")
                
                # Check if minecraft directory exists and icon.png exists directly in it
                if minecraft_dir.exists() and minecraft_dir.is_dir():
                    if icon_path.exists() and icon_path.is_file():
                        # Ensure we're only replacing icon.png in the root of minecraft directory
                        # (not in subdirectories like texturepacks)
                        if icon_path.parent == minecraft_dir:
                            try:
                                # Replace the icon.png file with new.png (keeping the name as icon.png)
                                shutil.copy2(new_icon_path, icon_path)
                                print(f"  Successfully replaced minecraft/icon.png")
                                icons_replaced += 1
                                
                            except Exception as e:
                                print(f"  Error replacing icon: {e}")
                        else:
                            print(f"  Skipped icon.png (not in minecraft root directory)")
                    else:
                        print(f"  No icon.png found in minecraft root directory")
                else:
                    print(f"  No minecraft directory found in {folder_path}")
                
                # Update instance.cfg file
                config_path = folder_path / "instance.cfg"
                if config_path.exists():
                    try:
                        # Read the file
                        with open(config_path, 'r', encoding='utf-8') as f:
                            lines = f.readlines()
                        
                        # Track if any changes were made
                        changes_made = False
                        
                        # Process each line
                        for i, line in enumerate(lines):
                            if old_version in line:
                                old_line = line
                                new_line = line.replace(old_version, new_version)
                                lines[i] = new_line
                                changes_made = True
                                print(f"  Updated config line: '{old_line.strip()}' -> '{new_line.strip()}'")
                        
                        # Write back to file if changes were made
                        if changes_made:
                            with open(config_path, 'w', encoding='utf-8') as f:
                                f.writelines(lines)
                            configs_updated += 1
                            print(f"  Successfully updated instance.cfg")
                        else:
                            print(f"  No '{old_version}' found in instance.cfg")
                            
                    except Exception as e:
                        print(f"  Error updating config: {e}")
                else:
                    print(f"  No instance.cfg found in {folder_path}")
    
    print(f"\n--- Summary ---")
    print(f"OptiArk folders found: {folders_found}")
    print(f"Icons successfully replaced: {icons_replaced}")
    print(f"Config files updated: {configs_updated}")
    
    if folders_found == 0:
        print("No folders containing 'OptiArk' were found.")
    elif icons_replaced == 0 and configs_updated == 0:
        print("No files were found to replace or update.")

if __name__ == "__main__":
    replace_optiark_icons()