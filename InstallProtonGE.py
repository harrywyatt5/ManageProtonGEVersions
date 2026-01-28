#!/usr/bin/env python3 
import re 
import requests
import os
import tempfile
import tarfile

# Environment variables
STEAM_INSTALL_DIR = os.environ["STEAM_INSTALL"]
VERSIONS_TO_KEEP = int(os.environ["VERSIONS_TO_KEEP"])
UPDATE_DEFAULT_CONFIG = os.environ["UPDATE_DEFAULT_CONFIG"].lower() == "true"
IGNORED_VERSIONS = os.environ["IGNORED_GE_VERSIONS"].replace(" ", "").split(",")

# Other globals
VERSION_REGEX = "GE-Proton(\\d+)-(\\d+)"
LATEST_RELEASE_ENDPOINT = "https://api.github.com/repos/GloriousEggroll/proton-ge-custom/releases/latest"
GITHUB_HEADERS = {
        "Accept": "application/vnd.github+json"
}

def get_paths():
    abs_steam_path = os.path.abspath(STEAM_INSTALL_DIR)
    compat_folder = os.path.join(abs_steam_path, "compatibilitytools.d")
    config_file = os.path.join(abs_steam_path, "config/config.vdf")

    # Check the steam folder, compat folder and config exist first
    if not os.path.exists(abs_steam_path) or not os.path.exists(compat_folder) or not os.path.exists(config_file):
        raise Exception("Steam folder does not exist or does not have compatibility/config folders inside")
    
    return (
        abs_steam_path,
        compat_folder,
        config_file
    )

def get_latest_release():
    response = requests.get(LATEST_RELEASE_ENDPOINT, headers=GITHUB_HEADERS)
    response.raise_for_status()
    data = response.json()
    
    version_match = re.match(VERSION_REGEX, data["tag_name"])
    return {
        "full_name": data["tag_name"],
        "major": int(version_match.group(1)),
        "minor": int(version_match.group(2)),
        "download_url": [item["browser_download_url"] for item in data["assets"] if re.match("GE-Proton\\d+-\\d+.tar.gz", item["name"])][0]
    }

def get_installed_versions(compat_folder):
    folder_items = os.listdir(compat_folder)
    # {"full_name": "GE-Proton10-23", "major": 10, "minor": 23, "full_path": "<path>"}
    final_items = []

    for item in folder_items:
        m = re.match(VERSION_REGEX, item)
        if m:
            final_items.append({
                "full_name": item,
                "major": int(m.group(1)),
                "minor": int(m.group(2)),
                "full_path": os.path.join(compat_folder, item)
            })

    return sorted(final_items, key=lambda item: (item["major"], item["minor"]))

def compare_versions(lhs, rhs):
    if "major" not in lhs or "minor" not in rhs:
        print("Objects to be compared must have a minor and major field")
        return False

    return lhs["major"] == rhs["major"] and lhs["minor"] == rhs["minor"]

def remove_ignored_versions(original_list):
    # Given a list of versions, return a new list which contains only the ones which are not set to be removed
    new_list = []

    for item in original_list:
        if item["full_name"] not in IGNORED_VERSIONS:
            new_list.append(item)

    return new_list

def remove_expired_versions(versions_to_delete):
    for version in versions_to_delete:
        print(f"Deleting {version['full_name']}")
        os.remove(version["full_path"])

def install_latest_version(compat_folder, file_format, url):
    with tempfile.SpooledTemporaryFile(mode="r+b") as tmp_file:
        with requests.get(url, stream=True) as response:
            response.raise_for_status()
            for chunk in response.iter_content(chunk_size=8192):
                tmp_file.write(chunk)
        
        tmp_file.seek(0, 0)
        with tarfile.open(mode=f"r:{file_format}", fileobj=tmp_file) as tar_file:
            tar_file.extractall(path=compat_folder)

def main():
   steam_path, compat_folder, config_file = get_paths()

   # Get what compatibility tools we have configured
   installed_versions = get_installed_versions(compat_folder)
   # and get the latest version
   latest_release = get_latest_release()

   # If we have the lastest release, no work needs to be done
   if any([compare_versions(latest_release, release) for release in installed_versions]):
      print(f"The latest version {latest_release['full_name']} is already installed")
      return

   # Install the new version
   print(f"Installing latest verrsion {latest_release['full_name']}")
   install_latest_version(compat_folder, "gz", latest_release["download_url"])

   new_available_list = remove_ignored_versions(IGNORED_VERSIONS)
   to_delete = new_available_list[VERSIONS_TO_KEEP - 1:]
   if to_delete:
       print("Deleting old versions...")
       remove_expired_versions(to_delete)
   else:
       print("Nothing to delete!")

if __name__ == "__main__":
    main()

