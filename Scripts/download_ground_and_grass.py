import os
import json
import urllib.request

OUTPUT_DIR = "/Users/alexeysukhov/Documents/Unreal Projects/Otherworld/assets/cache/scanned"
os.makedirs(OUTPUT_DIR, exist_ok=True)

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}

def download_file(url, target_path):
    os.makedirs(os.path.dirname(target_path), exist_ok=True)
    if os.path.exists(target_path) and os.path.getsize(target_path) > 0:
        return
    print(f"Downloading {url} -> {target_path}")
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req) as resp, open(target_path, 'wb') as out_file:
        out_file.write(resp.read())

def fetch_model(asset_id):
    asset_dir = os.path.join(OUTPUT_DIR, asset_id)
    os.makedirs(asset_dir, exist_ok=True)
    
    api_url = f"https://api.polyhaven.com/files/{asset_id}"
    req = urllib.request.Request(api_url, headers=HEADERS)
    data = json.loads(urllib.request.urlopen(req).read().decode('utf-8'))
    
    gltf_entry = data.get("gltf", {}).get("1k", {}).get("gltf", {})
    if gltf_entry:
        main_url = gltf_entry.get("url")
        if main_url:
            download_file(main_url, os.path.join(asset_dir, f"{asset_id}_1k.gltf"))
        includes = gltf_entry.get("include", {})
        for rel_path, inc_info in includes.items():
            inc_url = inc_info.get("url")
            if inc_url:
                download_file(inc_url, os.path.join(asset_dir, rel_path))
        print(f"[OK] Successfully downloaded model {asset_id}")

def fetch_texture(asset_id):
    tex_dir = os.path.join(OUTPUT_DIR, "textures", asset_id)
    os.makedirs(tex_dir, exist_ok=True)
    
    api_url = f"https://api.polyhaven.com/files/{asset_id}"
    req = urllib.request.Request(api_url, headers=HEADERS)
    data = json.loads(urllib.request.urlopen(req).read().decode('utf-8'))
    
    # Map channels
    for channel in ["Diffuse", "nor_gl", "nor_dx", "Rough", "AO", "arm"]:
        ch_data = data.get(channel, {})
        # try 2k, fallback 1k
        res_entry = ch_data.get("2k", {}) or ch_data.get("1k", {})
        # res_entry can have png/jpg
        if isinstance(res_entry, dict):
            fmt_info = res_entry.get("png") or res_entry.get("jpg")
            if fmt_info and "url" in fmt_info:
                ext = "png" if "png" in res_entry else "jpg"
                dest_file = os.path.join(tex_dir, f"{asset_id}_{channel}_2k.{ext}")
                download_file(fmt_info["url"], dest_file)
                print(f"[OK] Downloaded texture {asset_id} - {channel} ({ext})")

# Fetch models: grass clumps, tall grass, ferns, moss
models = ["grass_medium_01", "grass_medium_02", "fern_02", "moss_01"]
for m in models:
    try:
        fetch_model(m)
    except Exception as e:
        print(f"Error fetching model {m}: {e}")

# Fetch realistic forest terrain textures
textures = ["forest_floor", "leafy_grass", "leaves_forest_ground"]
for t in textures:
    try:
        fetch_texture(t)
    except Exception as e:
        print(f"Error fetching texture {t}: {e}")

print("GROUND ASSETS DOWNLOAD COMPLETED!")
