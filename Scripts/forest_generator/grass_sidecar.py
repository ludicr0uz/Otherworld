"""
grass_sidecar.py — Write the grass and bush instances to the JSON sidecar
the level import reads (forest_import/grass.py, bushes.py): hundreds of
thousands of transforms would bloat the generated script.
"""

import json
import os


def write_grass_data(path: str, placed_grass, placed_bushes) -> None:
    """
    Write grass and bush instance transforms to a compact JSON sidecar.

    One record per patch, and there are hundreds of thousands of them on a
    big map — so spec names are interned into an index table and each
    instance is a flat rounded array:
        [spec_idx, x, y, z, yaw, pitch, roll, height_mul, width_mul,
         target_h_cm, tier]
    Bushes, under "bushes", carry their final scale instead:
        [spec_idx, x, y, z, yaw, pitch, roll, scale_xy, scale_z]
    """
    spec_names = sorted({g.spec_name for g in placed_grass})
    spec_idx = {n: i for i, n in enumerate(spec_names)}
    payload = {
        "specs": spec_names,
        "instances": [
            [
                spec_idx[g.spec_name],
                round(g.x, 1), round(g.y, 1), round(g.placed_z, 1),
                round(g.yaw_deg, 1), round(g.pitch_deg, 2), round(g.roll_deg, 2),
                round(g.height_scale, 3), round(g.width_scale, 3),
                round(g.target_height_cm, 2), g.tier,
            ]
            for g in placed_grass
        ],
    }
    bush_names = sorted({b.spec_name for b in placed_bushes})
    bush_idx = {n: i for i, n in enumerate(bush_names)}
    payload["bushes"] = {
        "specs": bush_names,
        "instances": [
            [bush_idx[b.spec_name], round(b.x, 1), round(b.y, 1),
             round(b.placed_z, 1), round(b.yaw_deg, 1), round(b.pitch_deg, 2),
             round(b.roll_deg, 2), round(b.scale_xy, 3), round(b.scale_z, 3)]
            for b in placed_bushes
        ],
    }
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(payload, f, separators=(",", ":"))
