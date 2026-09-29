"""Plant the grass sidecar into the open level as per-cell HISMs, and verify it.

Called by the generated import_<Level>.py (step 5b) and verify_<Level>.py
(step 5). The cell layout, tag and distances come from
forest_generator/grass_cells.py; see there for why grass is cut into cells.

Grass is saved UNLIT: no shadow, no distance-field lighting, no dynamic
indirect lighting. Those are what the Ultra preset pays for, and the graphics
menu (graphics_menu/presets.py) switches them on at runtime per preset. Saving
the cheap state means a level with no menu in front of it runs cheap too.

For the same reason every density tier above Low (grass_cells.GRASS_TIERS) is
saved hidden in game, and the menu unhides the tiers its preset draws. So a
cell is one species, one tier, one 100 m square.

The meshes are opaque generated patches (forest_generator/foliage_meshes.py),
built by forest_import/foliage_assets.py before this runs.
"""

import json
from collections import defaultdict

import unreal

from forest_generator.grass_cells import (
    GRASS_TAG, GRASS_TIER_MAX_DRAW_CM, GRASS_TIERS, cell_label, cell_of,
    spec_of_label, tier_of_label, tier_spec, tier_tag)

# One add_instances call per chunk, not one add_instance per clump: a 1000 m
# map has over a million, and each single add is a round trip into the HISM.
_BATCH = 50000

# The lighting a cell is saved with -- all off; see the module docstring.
_UNLIT = (("cast_shadow", False),
          ("affect_distance_field_lighting", False),
          ("affect_dynamic_indirect_lighting", False))


def _log(msg):
    unreal.log_warning(f"[GEN] {msg}")


def _mesh_height(mesh, name):
    """The mesh's own bounds height. The scanned clumps carry no authored
    real-world size, so the scale that makes a clump its target height is
    derived here, at plant time, rather than baked anywhere."""
    try:
        return float(mesh.get_bounds().box_extent.z) * 2.0
    except Exception as exc:
        _log(f"Could not read bounds for {name}: {exc}")
        return 0.0


def spawn_cell(actor_sub, label, mesh, materials, tags, cull_start_cm,
               cull_end_cm, max_draw_cm, hidden_in_game=False):
    """One undergrowth cell: an actor whose root is a walk-through, unlit HISM.
    Shared with forest_import/bushes.py."""
    actor = actor_sub.spawn_actor_from_class(unreal.Actor, unreal.Vector(0, 0, 0))
    actor.set_actor_label(label)
    actor.set_editor_property("tags", [unreal.Name(t) for t in tags])
    comp = unreal.HierarchicalInstancedStaticMeshComponent(actor)
    comp.set_static_mesh(mesh)
    actor.set_editor_property("root_component", comp)
    # Undergrowth never blocks the player, the wanderers or the navmesh.
    comp.set_collision_profile_name("NoCollision")
    comp.set_collision_enabled(unreal.CollisionEnabled.NO_COLLISION)
    comp.set_editor_property("can_ever_affect_navigation", False)
    comp.set_mobility(unreal.ComponentMobility.STATIC)
    for prop, value in _UNLIT:
        comp.set_editor_property(prop, value)
    comp.set_editor_property("instance_start_cull_distance", cull_start_cm)
    comp.set_editor_property("instance_end_cull_distance", cull_end_cm)
    comp.set_cull_distance(max_draw_cm)
    for idx, mat in enumerate(materials):
        comp.set_material(idx, mat)
    # On the ACTOR, because that is what the menu's SetActorHiddenInGame
    # flips; a hidden component under a shown actor would stay hidden.
    actor.set_actor_hidden_in_game(hidden_in_game)
    return comp


def _spawn_tier_cell(actor_sub, spec, tier, cell, mesh, materials):
    t = GRASS_TIERS[tier]
    tags = [GRASS_TAG] + ([tier_tag(tier)] if t.min_preset > 0 else [])
    return spawn_cell(actor_sub, cell_label(tier_spec(spec, tier), cell), mesh,
                      materials, tags, t.cull_start_cm, t.cull_end_cm,
                      GRASS_TIER_MAX_DRAW_CM[tier],
                      hidden_in_game=t.min_preset > 0)


def plant_grass(data_path, configs, actor_sub, asset_sub):
    """Plant every clump in ``data_path`` (the grass_<Level>.json sidecar).

    ``configs`` maps species name -> {"mesh": path, "mats": [paths]}.
    Returns (clumps planted, cell actors spawned).
    """
    with open(data_path, "r") as f:
        payload = json.load(f)
    spec_names = payload["specs"]

    groups = defaultdict(list)       # (spec, tier, cell) -> instances
    for inst in payload["instances"]:
        groups[(spec_names[inst[0]], inst[10],
                cell_of(inst[1], inst[2]))].append(inst)

    meshes = {}
    for spec in sorted({s for s, _, _ in groups}):
        config = configs.get(spec)
        mesh = asset_sub.load_asset(config["mesh"]) if config else None
        if not mesh:
            unreal.log_error(f"[GEN] Missing grass mesh for {spec}")
            continue
        mats = [m for m in (asset_sub.load_asset(p) for p in config["mats"]) if m]
        height = _mesh_height(mesh, spec)
        if height <= 1.0:
            unreal.log_error(f"[GEN] {spec} has unusable bounds height {height}; "
                             "falling back to scale 1.0")
        meshes[spec] = (mesh, mats, height)

    planted, cells = 0, 0
    per_spec = defaultdict(int)
    for (spec, tier, cell), instances in sorted(groups.items()):
        if spec not in meshes:
            continue
        mesh, mats, height = meshes[spec]
        comp = _spawn_tier_cell(actor_sub, spec, tier, cell, mesh, mats)
        cells += 1
        batch = []
        for _, gx, gy, gz, yaw, pitch, roll, h_mul, w_mul, target_h, _t in instances:
            if height > 1.0:
                s_z = target_h / height
                s_xy = (target_h / max(h_mul, 1e-3)) / height * w_mul
            else:
                s_z, s_xy = 1.0, 1.0
            batch.append(unreal.Transform(
                location=unreal.Vector(gx, gy, gz),
                rotation=unreal.Rotator(pitch=pitch, yaw=yaw, roll=roll),
                scale=unreal.Vector(s_xy, s_xy, s_z)))
            if len(batch) >= _BATCH:
                comp.add_instances(batch, False, True, False)
                batch = []
        if batch:
            comp.add_instances(batch, False, True, False)
        planted += len(instances)
        per_spec[spec] += len(instances)

    for spec, n in sorted(per_spec.items()):
        _log(f"   {spec}: {n} patches (mesh height {meshes[spec][2]:.1f} cm)")
    return planted, cells


# ─── Verification ────────────────────────────────────────────────────────────

def _knee_heights(comp, samples=50):
    """World heights of up to ``samples`` clumps: bounds height x Z scale."""
    mesh = comp.get_editor_property("static_mesh")
    count = comp.get_instance_count()
    if not mesh or count == 0:
        return []
    mesh_h = float(mesh.get_bounds().box_extent.z) * 2.0
    step = max(1, count // samples)
    return [float(comp.get_instance_transform(i, world_space=False).scale3d.z)
            * mesh_h for i in range(0, count, step)]


def verify_cells(check, spec, comps, tags, cull_start_cm, cull_end_cm,
                 max_draw_cm, hidden_in_game):
    """What every undergrowth cell of ``spec`` must be; shared with bushes.

    Every cell, not a sample: one cell left blocking, lit or showing is a bug
    a sample would only catch by luck.
    """
    blocking = [a.get_actor_label() for a, c in comps
                if str(c.get_collision_profile_name()) != "NoCollision"
                or c.get_editor_property("can_ever_affect_navigation")]
    check(f"{spec} Walk-Through (no collision, no navmesh)", not blocking,
          str(blocking[:3]))
    lit = [a.get_actor_label() for a, c in comps
           if any(c.get_editor_property(p) != v for p, v in _UNLIT)]
    check(f"{spec} Saved Unlit (Ultra lights it at runtime)", not lit,
          str(lit[:3]))
    want = {unreal.Name(t) for t in tags}
    mistagged = [a.get_actor_label() for a, _ in comps
                 if set(a.get_editor_property("tags")) != want]
    check(f"{spec} Tagged {', '.join(tags)}", not mistagged, str(mistagged[:3]))
    shown = [a.get_actor_label() for a, _ in comps
             if a.get_editor_property("hidden") != hidden_in_game]
    check(f"{spec} Saved {'Hidden' if hidden_in_game else 'Shown'} In Game",
          not shown, str(shown[:3]))
    distances = {(c.get_editor_property("ld_max_draw_distance"),
                  c.get_editor_property("instance_start_cull_distance"),
                  c.get_editor_property("instance_end_cull_distance"))
                 for _, c in comps}
    check(f"{spec} Draw Distances",
          distances == {(max_draw_cm, cull_start_cm, cull_end_cm)},
          str(sorted(distances)[:3]))


def verify_grass(check, actors, expected_counts, expected_heights, expected_total):
    """Checks over the saved grass cells. ``check(name, ok, detail)`` is the
    verify script's own harness, so these tally with everything else."""
    cells = defaultdict(list)
    for a in actors:
        label = a.get_actor_label()
        if label.startswith("HISM_Grass") and "__" in label:
            cells[spec_of_label(label)].append(a)

    total = 0
    for spec, expected in expected_counts.items():
        comps = []
        for a in cells.get(spec, []):
            root = a.get_editor_property("root_component")
            if isinstance(root, unreal.HierarchicalInstancedStaticMeshComponent):
                comps.append((a, root))
        check(f"{spec} Cells Exist", bool(comps), f"({len(comps)} cells)")
        count = sum(c.get_instance_count() for _, c in comps)
        total += count
        check(f"{spec} Instance Count", count == expected,
              f"(expected {expected}, got {count})")

        tier = tier_of_label(spec)
        t = GRASS_TIERS[tier]
        tags = [GRASS_TAG] + ([tier_tag(tier)] if t.min_preset > 0 else [])
        verify_cells(check, spec, comps, tags, t.cull_start_cm, t.cull_end_cm,
                     GRASS_TIER_MAX_DRAW_CM[tier], hidden_in_game=t.min_preset > 0)

        # Prove the clumps really land at knee height. The largest cell has
        # the most to sample.
        lo_hi = expected_heights.get(spec)
        if comps and lo_hi:
            _, biggest = max(comps, key=lambda ac: ac[1].get_instance_count())
            sampled = _knee_heights(biggest)
            lo, hi = lo_hi
            off = [h for h in sampled if not (lo - 1.0 <= h <= hi + 1.0)]
            check(f"{spec} Knee Height", sampled and not off,
                  f"(expected {lo:.1f}-{hi:.1f} cm, sampled "
                  f"{min(sampled, default=0):.1f}-{max(sampled, default=0):.1f} cm)")

    check("Total Grass Instances", total == expected_total,
          f"(expected {expected_total}, got {total})")
    # Nothing left over from the one-HISM-per-species layout.
    legacy = [a.get_actor_label() for a in actors
              if a.get_actor_label().startswith("HISM_Grass")
              and "__" not in a.get_actor_label()]
    check("No Whole-Map Grass HISMs Left", not legacy, str(legacy[:3]))
