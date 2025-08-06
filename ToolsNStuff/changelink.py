import os
import re

def find_optiark_folders(root_dir):
    """Find all folders containing 'OptiArk' in their name within the root directory."""
    optiark_folders = []
    
    if not os.path.exists(root_dir):
        print(f"Error: Root directory '{root_dir}' does not exist.")
        return optiark_folders
    
    try:
        for item in os.listdir(root_dir):
            item_path = os.path.join(root_dir, item)
            if os.path.isdir(item_path) and "OptiArk" in item:
                optiark_folders.append(item_path)
                print(f"Found OptiArk folder: {item}")
    except PermissionError:
        print(f"Error: Permission denied accessing '{root_dir}'")
    
    return optiark_folders

def find_mutils_files(optiark_folder):
    """Find mutils.json5 files in the OptiArk folder structure."""
    mutils_files = []
    minecraft_path = os.path.join(optiark_folder, "minecraft")
    
    if not os.path.exists(minecraft_path):
        print(f"  No 'minecraft' folder found in {optiark_folder}")
        return mutils_files
    
    config_path = os.path.join(minecraft_path, "config")
    if not os.path.exists(config_path):
        print(f"  No 'config' folder found in {minecraft_path}")
        return mutils_files
    
    mutils_path = os.path.join(config_path, "mutils")
    if not os.path.exists(mutils_path):
        print(f"  No 'mutils' folder found in {config_path}")
        return mutils_files
    
    # Look for mutils.json5 file
    mutils_file = os.path.join(mutils_path, "mutils.json5")
    if os.path.exists(mutils_file):
        mutils_files.append(mutils_file)
        print(f"  Found mutils.json5: {mutils_file}")
    else:
        print(f"  No mutils.json5 file found in {mutils_path}")
    
    return mutils_files

def update_version_api(file_path, new_api_url):
    """Update the versionAPI URL in a mutils.json5 file."""
    try:
        # Read the file
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Pattern to match versionAPI line (handles various spacing and quote styles)
        pattern = r'(versionAPI\s*:\s*["\'])([^"\']+)(["\'])'
        
        # Check if pattern exists
        match = re.search(pattern, content)
        if not match:
            print(f"    Warning: versionAPI pattern not found in {file_path}")
            return False
        
        # Show what we found
        old_url = match.group(2)
        print(f"    Found current API URL: {old_url}")
        
        # Replace the API URL using a lambda function to avoid regex group reference issues
        def replacement(match):
            return match.group(1) + new_api_url + match.group(3)
        
        new_content = re.sub(pattern, replacement, content)
        
        # Write back to file
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(new_content)
        
        print(f"    Successfully updated versionAPI to '{new_api_url}' in {os.path.basename(file_path)}")
        return True
        
    except Exception as e:
        print(f"    Error updating {file_path}: {str(e)}")
        return False

def main():
    # Configuration - use the directory where this script is located
    PYTHON_FILES_ROOT = os.path.dirname(os.path.abspath(__file__))
    print(f"Using script directory as root: {PYTHON_FILES_ROOT}")
    
    # The new API URL
    new_api_url = "https://arc360hub.com/OptiArk/optiarkapi/pack.txt"
    
    print(f"New API URL will be: {new_api_url}\n")
    
    # Find OptiArk folders
    optiark_folders = find_optiark_folders(PYTHON_FILES_ROOT)
    
    if not optiark_folders:
        print("No OptiArk folders found.")
        return
    
    total_updated = 0
    
    # Process each OptiArk folder
    for folder in optiark_folders:
        print(f"\nProcessing: {os.path.basename(folder)}")
        mutils_files = find_mutils_files(folder)
        
        for mutils_file in mutils_files:
            if update_version_api(mutils_file, new_api_url):
                total_updated += 1
    
    print(f"\n=== Summary ===")
    print(f"Total OptiArk folders found: {len(optiark_folders)}")
    print(f"Total mutils.json5 files updated: {total_updated}")
    
    if total_updated > 0:
        print("\nAPI URL update completed successfully!")
    else:
        print("\nNo files were updated.")

if __name__ == "__main__":
    main()