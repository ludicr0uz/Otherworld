"""Plant the bushes from the grass sidecar as per-cell HISMs, and verify them.

Called by the generated import_<Level>.py (step 5c) and verify_<Level>.py.
Placement is forest_generator/bush_placement.py; the meshes are generated
(forest_generator/foliage_meshes.py) and built by foliage_assets.py.

A bush cell is a grass cell in every way that matters (grass.spawn_cell): no
collision and no navmesh footprint, so the player and the wanderers walk
through it; saved unlit, and tagged OW_Grass so Ultra lights it with the grass.
It is drawn at every preset -- there are no bush tiers.
"""

import json
from collections import defaultdict

import unreal

from forest_generator.grass_cells import (
    BUSH_CELL_MAX_DRAW_CM, BUSH_CULL_END_CM, BUSH_CULL_START_CM, GRASS_TAG,
    cell_label, cell_of, spec_of_label)
from forest_import.grass import spawn_cell, verify_cells


def _log(msg):
    unreal.log_warning(f"[GEN] {msg}")


def plant_bushes(data_path, configs, actor_sub, asset_sub):
    """Plant ``payload["bushes"]`` from the sidecar at ``data_path``.

    ``configs`` maps spec name -> {"mesh": path, "mats": [paths]}.
    Returns (bushes planted, cell actors spawned).
    """
    with open(data_path, "r") as f:
        bushes = json.load(f).get("bushes") or {"specs": [], "instances": []}
    names = bushes["specs"]

    groups = defaultdict(list)       # (spec, cell) -> instances
    for inst in bushes["instances"]:
        groups[(names[inst[0]], cell_of(inst[1], inst[2]))].append(inst)

    assets = {}
    for spec in sorted({s for s, _ in groups}):
        config = configs.get(spec)
        mesh = asset_sub.load_asset(config["mesh"]) if config else None
        if not mesh:
            unreal.log_error(f"[GEN] Missing bush mesh for {spec}")
            continue
        assets[spec] = (mesh, [m for m in (asset_sub.load_asset(p)
                                           for p in config["mats"]) if m])

    planted, cells = 0, 0
    for (spec, cell), instances in sorted(groups.items()):
        if spec not in assets:
            continue
        mesh, mats = assets[spec]
        comp = spawn_cell(actor_sub, cell_label(spec, cell), mesh, mats,
                          [GRASS_TAG], BUSH_CULL_START_CM, BUSH_CULL_END_CM,
                          BUSH_CELL_MAX_DRAW_CM)
        comp.add_instances([unreal.Transform(
            location=unreal.Vector(x, y, z),
            rotation=unreal.Rotator(pitch=pitch, yaw=yaw, roll=roll),
            scale=unreal.Vector(s_xy, s_xy, s_z))
            for _, x, y, z, yaw, pitch, roll, s_xy, s_z in instances],
            False, True, False)
        cells += 1
        planted += len(instances)
    _log(f"Planted {planted} bushes in {cells} cells")
    return planted, cells


def verify_bushes(check, actors, expected_counts, expected_total):
    """Checks over the saved bush cells, in the verify script's harness."""
    cells = defaultdict(list)
    for a in actors:
        label = a.get_actor_label()
        if label.startswith("HISM_Bush") and "__" in label:
            root = a.get_editor_property("root_component")
            if isinstance(root, unreal.HierarchicalInstancedStaticMeshComponent):
                cells[spec_of_label(label)].append((a, root))

    total = 0
    for spec, expected in expected_counts.items():
        comps = cells.get(spec, [])
        check(f"{spec} Cells Exist", bool(comps), f"({len(comps)} cells)")
        count = sum(c.get_instance_count() for _, c in comps)
        total += count
        check(f"{spec} Instance Count", count == expected,
              f"(expected {expected}, got {count})")
        verify_cells(check, spec, comps, [GRASS_TAG], BUSH_CULL_START_CM,
                     BUSH_CULL_END_CM, BUSH_CELL_MAX_DRAW_CM, hidden_in_game=False)
    check("Total Bush Instances", total == expected_total,
          f"(expected {expected_total}, got {total})")
