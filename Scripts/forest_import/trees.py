"""Plant the trees into the open level as per-cell HISMs, and verify them.

Called by the generated import_<Level>.py (step 5) and verify_<Level>.py
(step 4). The cells, labels and cull distances come from
forest_generator/tree_cells.py; see there for why trees are cut into cells.

Nanite is pinned on. The tree meshes are dense scans (hundreds of thousands of
triangles and up) with masked, two-sided leaf cards, and that is expensive on
Nanite -- looking up into the canopy is where the frame rate falls. The obvious
escape, ``disallow_nanite`` on the component, draws the mesh's fallback
instead, and it was tried: the fallbacks (auto-built, relative error 1.0) have
**zero triangles in the leaf section** -- the simplifier deletes small
disconnected cards first -- so every tree rendered bare. Turning Nanite off on
the asset renders the full scan instead, which is worse. So the component stays
on Nanite until the leaves have a real classic-render mesh.

What Nanite does allow is dropping the leaves' opacity mask past a distance
(TREE_LEAF_MASK_DISTANCE_CM, see tree_cells.py), which takes distant canopy off
Nanite's expensive masked raster path.
"""

from collections import defaultdict

import unreal

from forest_generator.tree_cells import (
    TREE_CELL_MAX_DRAW_CM, TREE_CULL_END_CM, TREE_CULL_START_CM,
    TREE_LEAF_MASK_DISTANCE_CM, cell_label, cell_of, spec_of_label)


def _log(msg):
    unreal.log_warning(f"[GEN] {msg}")


def _spawn_cell(actor_sub, label, mesh, materials):
    actor = actor_sub.spawn_actor_from_class(unreal.Actor, unreal.Vector(0, 0, 0))
    actor.set_actor_label(label)
    comp = unreal.HierarchicalInstancedStaticMeshComponent(actor)
    comp.set_static_mesh(mesh)
    actor.set_editor_property("root_component", comp)
    comp.set_collision_profile_name("BlockAll")
    comp.set_collision_enabled(unreal.CollisionEnabled.QUERY_AND_PHYSICS)
    comp.set_mobility(unreal.ComponentMobility.STATIC)
    comp.set_editor_property("cast_shadow", True)
    comp.set_editor_property("disallow_nanite", False)
    # Leaves drawn unmasked (solid) past this distance -- see tree_cells.py.
    comp.set_editor_property("nanite_pixel_programmable_distance",
                             TREE_LEAF_MASK_DISTANCE_CM)
    # Render culling only: collision (and so the navmesh) is unaffected.
    comp.set_editor_property("instance_start_cull_distance", TREE_CULL_START_CM)
    comp.set_editor_property("instance_end_cull_distance", TREE_CULL_END_CM)
    comp.set_cull_distance(TREE_CELL_MAX_DRAW_CM)
    for idx, mat in enumerate(materials):
        comp.set_material(idx, mat)
    return comp


def plant_trees(tree_data, configs, actor_sub, asset_sub):
    """Plant ``tree_data`` (dicts with spec, x, y, z, yaw, scale).

    ``configs`` maps spec name -> {"mesh": path, "mats": [paths]}.
    Returns (trees planted, cell actors spawned).
    """
    groups = defaultdict(list)       # (spec, cell) -> placements
    for td in tree_data:
        groups[(td["spec"], cell_of(td["x"], td["y"]))].append(td)

    assets = {}
    for spec in sorted({s for s, _ in groups}):
        config = configs.get(spec)
        mesh = asset_sub.load_asset(config["mesh"]) if config else None
        if not mesh:
            unreal.log_error(f"[GEN] Missing tree mesh for {spec}")
            continue
        assets[spec] = (mesh, [asset_sub.load_asset(p) for p in config["mats"]])

    planted, cells = 0, 0
    for (spec, cell), placements in sorted(groups.items()):
        if spec not in assets:
            continue
        mesh, mats = assets[spec]
        comp = _spawn_cell(actor_sub, cell_label(spec, cell), mesh,
                           [m for m in mats if m])
        cells += 1
        comp.add_instances([unreal.Transform(
            location=unreal.Vector(td["x"], td["y"], td["z"]),
            rotation=unreal.Rotator(pitch=0, yaw=td["yaw"], roll=0),
            scale=unreal.Vector(td["scale"], td["scale"], td["scale"]))
            for td in placements], False, True, False)
        planted += len(placements)
    _log(f"Planted {planted} trees in {cells} cells")
    return planted, cells


# ─── Verification ────────────────────────────────────────────────────────────

def verify_trees(check, actors, expected_counts, expected_total):
    """Checks over the saved tree cells. ``check(name, ok, detail)`` is the
    verify script's own harness, so these tally with everything else."""
    cells = defaultdict(list)
    for a in actors:
        label = a.get_actor_label()
        if label.startswith("HISM_Tree") and "__" in label:
            root = a.get_editor_property("root_component")
            if isinstance(root, unreal.HierarchicalInstancedStaticMeshComponent):
                cells[spec_of_label(label)].append((label, root))

    total = 0
    for spec, expected in expected_counts.items():
        comps = cells.get(spec, [])
        check(f"{spec} Cells Exist", bool(comps), f"({len(comps)} cells)")
        count = sum(c.get_instance_count() for _, c in comps)
        total += count
        check(f"{spec} Instance Count", count == expected,
              f"(expected {expected}, got {count})")

        # Every cell, not a sample: one wrong cell is a bug a sample would
        # only catch by luck.
        passable = [l for l, c in comps
                    if str(c.get_collision_profile_name()) != "BlockAll"]
        check(f"{spec} Collision Profile BlockAll", not passable, str(passable[:3]))
        classic = [l for l, c in comps if c.get_editor_property("disallow_nanite")]
        check(f"{spec} Renders Nanite (fallback has no leaves)", not classic,
              str(classic[:3]))
        unmasked = {c.get_editor_property("nanite_pixel_programmable_distance")
                    for _, c in comps}
        check(f"{spec} Leaves Unmasked Past {TREE_LEAF_MASK_DISTANCE_CM / 100:g} m",
              unmasked == {TREE_LEAF_MASK_DISTANCE_CM}, str(sorted(unmasked)))
        distances = {(c.get_editor_property("ld_max_draw_distance"),
                      c.get_editor_property("instance_start_cull_distance"),
                      c.get_editor_property("instance_end_cull_distance"))
                     for _, c in comps}
        check(f"{spec} Draw Distances",
              distances == {(TREE_CELL_MAX_DRAW_CM, TREE_CULL_START_CM,
                             TREE_CULL_END_CM)},
              str(sorted(distances)[:3]))
        mesh = comps[0][1].get_editor_property("static_mesh") if comps else None
        settings = mesh.get_editor_property("nanite_settings") if mesh else None
        check(f"{spec} Mesh Keeps Nanite Data",
              bool(settings and settings.get_editor_property("enabled")))

    check("Total Tree Instances", total == expected_total,
          f"(expected {expected_total}, got {total})")
    # Nothing left over from the one-HISM-per-species layout.
    legacy = [a.get_actor_label() for a in actors
              if a.get_actor_label().startswith("HISM_Tree")
              and "__" not in a.get_actor_label()]
    check("No Whole-Map Tree HISMs Left", not legacy, str(legacy[:3]))
