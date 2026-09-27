import urllib.request
import json
import os

OUT_DIR = "/Users/alexeysukhov/Documents/Unreal Projects/Otherworld/assets/cache/scanned/textures"

def download_polyhaven_texture(tex_name):
    target_dir = os.path.join(OUT_DIR, tex_name)
    os.makedirs(target_dir, exist_ok=True)
    
    url = f"https://api.polyhaven.com/files/{tex_name}"
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req) as resp:
        data = json.loads(resp.read().decode())
    
    # We want Diffuse, nor_gl or nor_dx, Rough, AO
    map_types = ['Diffuse', 'nor_gl', 'nor_dx', 'Rough', 'AO', 'arm']
    for m in map_types:
        if m in data:
            # check 2k resolution
            res_dict = data[m]
            if '2k' in res_dict:
                fmt_dict = res_dict['2k']
                # Prefer png or jpg
                fmt = 'png' if 'png' in fmt_dict else ('jpg' if 'jpg' in fmt_dict else list(fmt_dict.keys())[0])
                file_info = fmt_dict[fmt]
                file_url = file_info['url']
                out_path = os.path.join(target_dir, f"{tex_name}_{m}_2k.{fmt}")
                if not os.path.exists(out_path):
                    print(f"Downloading {tex_name} {m} 2k from {file_url}...")
                    urllib.request.urlretrieve(file_url, out_path)
                else:
                    print(f"Already exists: {out_path}")

for t in ['grass_ground', 'forrest_ground_01', 'forest_ground_05']:
    download_polyhaven_texture(t)

print("Done downloading ground textures!")
