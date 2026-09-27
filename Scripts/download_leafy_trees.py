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
        print(f"[OK] Successfully downloaded tree model {asset_id}")

leafy_trees = ["island_tree_01", "island_tree_02", "fir_tree_01", "pine_tree_01", "pine_sapling_medium"]
for t in leafy_trees:
    try:
        fetch_model(t)
    except Exception as e:
        print(f"Error fetching tree {t}: {e}")

print("ALL LEAFY TREES DOWNLOADED!")
