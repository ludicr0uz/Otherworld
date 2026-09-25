import os
import json
import urllib.request
import zipfile

OUTPUT_DIR = "/Users/alexeysukhov/Documents/Unreal Projects/Otherworld/Scripts/downloaded_scanned_assets"
os.makedirs(OUTPUT_DIR, exist_ok=True)

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}

def download_file(url, target_path):
    print(f"Downloading {url} -> {target_path}")
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req) as resp, open(target_path, 'wb') as out_file:
        out_file.write(resp.read())

def fetch_model(asset_id):
    asset_dir = os.path.join(OUTPUT_DIR, asset_id)
    os.makedirs(asset_dir, exist_ok=True)
    
    # Check files via API
    api_url = f"https://api.polyhaven.com/files/{asset_id}"
    req = urllib.request.Request(api_url, headers=HEADERS)
    data = json.loads(urllib.request.urlopen(req).read().decode('utf-8'))
    
    # Get 1k gltf zip if available
    gltf_info = data.get("gltf", {}).get("1k", {})
    if gltf_info and "url" in gltf_info:
        zip_url = gltf_info["url"]
        zip_path = os.path.join(asset_dir, f"{asset_id}_1k.zip")
        download_file(zip_url, zip_path)
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(asset_dir)
        print(f"[OK] Downloaded and extracted model {asset_id}")
    else:
        print(f"[WARN] No 1k gltf found for {asset_id}, keys: {list(data.keys())}")

def fetch_texture(asset_id):
    tex_dir = os.path.join(OUTPUT_DIR, "textures", asset_id)
    os.makedirs(tex_dir, exist_ok=True)
    
    api_url = f"https://api.polyhaven.com/files/{asset_id}"
    req = urllib.request.Request(api_url, headers=HEADERS)
    data = json.loads(urllib.request.urlopen(req).read().decode('utf-8'))
    
    # Try 2k textures
    tex_info = data.get("textures", {}).get("2k", {})
    if not tex_info:
        tex_info = data.get("textures", {}).get("1k", {})
        
    for tex_type, details in tex_info.items():
        if isinstance(details, dict) and "url" in details:
            ext = details.get("format", "png")
            file_url = details["url"]
            dest_file = os.path.join(tex_dir, f"{asset_id}_{tex_type}_2k.{ext}")
            download_file(file_url, dest_file)
            print(f"[OK] Downloaded texture {asset_id} - {tex_type}")

# Models to fetch: grass clumps, tall grass, ferns, moss
models_to_fetch = ["grass_medium_01", "grass_medium_02", "fern_02", "moss_01"]
for m in models_to_fetch:
    try:
        fetch_model(m)
    except Exception as e:
        print(f"Error fetching {m}: {e}")

# Textures to fetch: forest floor & leafy grass
textures_to_fetch = ["forest_floor", "leafy_grass", "leaves_forest_ground"]
for t in textures_to_fetch:
    try:
        fetch_texture(t)
    except Exception as e:
        print(f"Error fetching {t}: {e}")

print("ALL DOWNLOADS COMPLETED!")
