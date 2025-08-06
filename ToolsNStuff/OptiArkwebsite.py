import requests
import json
import re
from collections import defaultdict

def get_github_releases(repo_owner, repo_name):
    """Fetch all releases from GitHub API"""
    url = f"https://api.github.com/repos/{repo_owner}/{repo_name}/releases"
    response = requests.get(url)
    if response.status_code == 200:
        return response.json()
    else:
        print(f"Error fetching releases: {response.status_code}")
        return []

def parse_asset_name(asset_name):
    """Parse asset name to extract version info and renderer type"""
    # Pattern: OptiArk.{mc_version}.{pack_version}.{renderer}.{extension}
    pattern = r"OptiArk\.(\d+\.\d+\.\d+)\.(\d+\.\d+)\.([^.]+)\.(zip|mrpack)"
    match = re.match(pattern, asset_name)
    
    if match:
        mc_version = match.group(1)
        pack_version = match.group(2)
        renderer_code = match.group(3)
        extension = match.group(4)
        
        # Map renderer codes to full names
        renderer_map = {
            'Sodium': 'Sodium',
            'VK': 'VulkanMod', 
            'NV': 'Nividium',
            'EB': 'Embeddium',
            'OptiFine': 'Old'
        }
        
        renderer = renderer_map.get(renderer_code, renderer_code)
        
        return {
            'mc_version': mc_version,
            'pack_version': pack_version,
            'renderer': renderer,
            'renderer_code': renderer_code,
            'extension': extension
        }
    
    return None

def format_releases(repo_owner, repo_name):
    """Main function to fetch and format releases"""
    releases = get_github_releases(repo_owner, repo_name)
    
    if not releases:
        return
    
    # Get the latest release info
    latest_release = releases[0]
    latest_tag = latest_release['tag_name']
    latest_url = latest_release['html_url']
    
    print(f"Latest Release: {latest_url}")
    print()
    
    # Track the latest version of each MC version + renderer combo
    latest_assets = {}  # Key: (renderer, mc_version), Value: (pack_version, url, release_date)
    
    # Process all releases to find the latest version of each combo
    for release in releases:
        release_date = release['published_at']
        
        for asset in release['assets']:
            asset_name = asset['name']
            download_url = asset['browser_download_url']
            
            parsed = parse_asset_name(asset_name)
            if parsed:
                renderer = parsed['renderer']
                mc_version = parsed['mc_version']
                pack_version = parsed['pack_version']
                renderer_code = parsed['renderer_code']
                
                # Create a key for this combination
                combo_key = (renderer, mc_version, renderer_code)
                
                # Check if this is newer than what we have
                if combo_key not in latest_assets:
                    latest_assets[combo_key] = (pack_version, download_url, release_date)
                else:
                    # Compare pack versions (assuming higher number = newer)
                    current_pack_version = latest_assets[combo_key][0]
                    if float(pack_version) > float(current_pack_version):
                        latest_assets[combo_key] = (pack_version, download_url, release_date)
    
    # Organize the latest assets by renderer and version
    organized_data = defaultdict(dict)
    
    for (renderer, mc_version, renderer_code), (pack_version, url, release_date) in latest_assets.items():
        # Special handling for Old category
        if renderer == 'Old':
            if 'OptiFine' in renderer_code:
                key = f"{mc_version} OptiFine"
            else:
                key = f"{mc_version} {renderer_code}"
            organized_data[renderer][key] = url
        else:
            # Check if this version should be marked as unsupported
            version_key = mc_version
            if mc_version in ["1.21.4", "1.20.1"] and renderer in ["Sodium", "Nividium"]:
                version_key = f"{mc_version} (Unsupported)"
            
            organized_data[renderer][version_key] = url
    
    # Add the static Embeddium and Old categories
    organized_data["Embeddium"] = {
        "1.20.1": "https://github.com/arc360alt/arcswebsite/releases/download/oa1.7/OptiArk.1.20.1.1.7.EB.mrpack",
        "1.16.5": "https://github.com/arc360alt/arcswebsite/releases/download/oa1.7/OptiArk.1.16.5.1.7.EB.mrpack"
    }
    
    organized_data["Old"] = {
        "1.8.9 OptiFine": "https://github.com/arc360alt/arcswebsite/releases/download/oa1.7OLD/OptiArk.1.8.9.1.7.OptiFine.mrpack",
        "1.12.2 Sodium": "https://github.com/arc360alt/arcswebsite/releases/download/oa1.7OLD/OptiArk.1.12.2.1.7.Sodium.mrpack",
        "1.12.2 OptiFine": "https://github.com/arc360alt/arcswebsite/releases/download/oa1.7OLD/OptiArk.1.12.2.1.7.OptiFine.mrpack"
    }

    # Generate the formatted output
    print("Layout:")
    print("{")
    
    renderer_order = ["Sodium", "VulkanMod", "Nividium", "Embeddium", "Old"]
    
    for i, renderer in enumerate(renderer_order):
        if renderer in organized_data:
            print(f'    "{renderer}": {{')
            
            versions = organized_data[renderer]
            version_items = list(versions.items())
            
            for j, (version, url) in enumerate(version_items):
                comma = "," if j < len(version_items) - 1 else ""
                print(f'        "{version}": "{url}"{comma}')
            
            closing_comma = "," if i < len([r for r in renderer_order if r in organized_data]) - 1 else ""
            print(f'    }}{closing_comma}')
    
    print("};")

def main():
    # Configuration
    repo_owner = "arc360alt"  # Your GitHub username
    repo_name = "OptiArk"     # Your repository name
    
    print("Fetching OptiArk releases...")
    format_releases(repo_owner, repo_name)

if __name__ == "__main__":
    main()