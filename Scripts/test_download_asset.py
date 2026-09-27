import os
import json
import urllib.request
import ssl

PROJECT_DIR = "/Users/alexeysukhov/Documents/Unreal Projects/Otherworld"
DOWNLOAD_DIR = os.path.join(PROJECT_DIR, "assets", "cache", "scanned")
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

# Ignore SSL verification issues if any
ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

def download_file(url, dest_path):
    print(f"[AGY] Downloading {os.path.basename(dest_path)}...")
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req, context=ctx, timeout=60) as resp, open(dest_path, 'wb') as out:
        out.write(resp.read())

def download_polyhaven_gltf(asset_id, res="1k"):
    meta_url = f"https://api.polyhaven.com/files/{asset_id}"
    req = urllib.request.Request(meta_url, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req, context=ctx, timeout=15) as resp:
        meta = json.loads(resp.read().decode())
    
    gltf_info = meta.get("gltf", {}).get(res, {}).get("gltf", {})
    if not gltf_info:
        print(f"Error: gltf {res} not found for {asset_id}")
        return None
    
    asset_dir = os.path.join(DOWNLOAD_DIR, asset_id)
    os.makedirs(asset_dir, exist_ok=True)
    os.makedirs(os.path.join(asset_dir, "textures"), exist_ok=True)
    
    # Download main .gltf
    gltf_file = os.path.join(asset_dir, f"{asset_id}_{res}.gltf")
    download_file(gltf_info["url"], gltf_file)
    
    # Download includes (.bin and textures)
    for inc_name, inc_data in gltf_info.get("include", {}).items():
        inc_dest = os.path.join(asset_dir, inc_name)
        download_file(inc_data["url"], inc_dest)
        
    print(f"[AGY] Successfully downloaded {asset_id} to {asset_dir}")
    return gltf_file

if __name__ == "__main__":
    download_polyhaven_gltf("rock_07")
