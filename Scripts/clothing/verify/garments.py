"""Each garment's Blueprint, read back."""

import unreal

from combat.paths import HOLD_ITEM_ANIM_PATH, ITEM_BP_PATH
from combat.verify.common import BEL, cdo, check, component_template, components, load
from combat.wear_tuning import (
    CLOTHING_SLOT_VAR, NOT_CLOTHING, WEAR_SLOTS, WORN_MESH_VAR, WORN_PART_VAR,
)
from asset_pipeline.metahuman_paths import CLOTHING
from clothing.ground_model import MODEL, lying_box
from clothing.items import parts_of
from combat.grip import _grip_location, _grip_rotation
from clothing.specs import GARMENTS

# The three garments drawn worn, and the MetaHuman component each fills.
WORN_PARTS = {"Jacket": "Torso", "Pants": "Legs", "Boots": "Feet"}


def _path(asset):
    return asset.get_path_name().split(".")[0] if asset else None


def _check_ground_model(bp, g, stand_ins):
    """A garment with a mesh to be worn as lies on the ground as that mesh."""
    name, model = g.display, component_template(bp, MODEL)
    mesh = (model.get_editor_property("skeletal_mesh_asset")
            if isinstance(model, unreal.SkeletalMeshComponent) else None)
    check(f"{name} lies as its worn mesh, one skeletal mesh component, no cube",
          mesh is not None and _path(mesh) == g.worn[1] and not stand_ins,
          f"{_path(mesh)} {sorted(stand_ins)}")
    if mesh is None:
        return
    check(f"{name}'s ground model holds its reference pose (no animation, no "
          "post-process Blueprint)",
          model.get_editor_property("anim_class") is None
          and model.get_editor_property("animation_data").get_editor_property(
              "anim_to_play") is None
          and model.get_editor_property("disable_post_process_blueprint") is True)
    centre, half = lying_box(mesh, model.get_editor_property("relative_rotation"),
                             model.get_editor_property("relative_location"))
    check(f"{name}'s ground model lies flat (its thin side up)",
          half.z <= min(half.x, half.y), f"half {half.to_tuple()}")
    check(f"{name}'s ground model is centred on the item's origin and rests on it",
          abs(centre.x) < 0.1 and abs(centre.y) < 0.1 and abs(centre.z - half.z) < 0.1,
          f"centre {centre.to_tuple()} half {half.to_tuple()}")
    # In the hand it is held where its stand-in was: the fist on the middle
    # of the stand-in's first part, solved again here.
    rot = _grip_rotation(HOLD_ITEM_ANIM_PATH)
    want = _grip_location(HOLD_ITEM_ANIM_PATH, rot, parts_of(g), g.parts[0][0])
    got = cdo(bp).get_editor_property("GripLocation").to_tuple()
    check(f"{name} is held at its stand-in's grip point",
          all(abs(a - b) < 0.01 for a, b in zip(got, want)), f"{got} against {want}")
    scale = model.get_editor_property("relative_scale3d")
    check(f"{name}'s ground model is the size it is worn at",
          all(abs(c - 1.0) < 1e-4 for c in scale.to_tuple()), str(scale.to_tuple()))


def run():
    item = load(ITEM_BP_PATH)
    check("BP_WeaponItem is no garment (ClothingSlot NOT_CLOTHING)",
          item is not None and cdo(item).get_editor_property(CLOTHING_SLOT_VAR)
          == NOT_CLOTHING)
    check("one garment per slot, in the slots' order",
          [g.slot_index for g in GARMENTS] == list(range(len(WEAR_SLOTS))))
    check("BP_WeaponItem is drawn as nothing worn (no WornPart, no WornMesh)",
          item is not None and cdo(item).get_editor_property(WORN_MESH_VAR) is None
          and str(cdo(item).get_editor_property(WORN_PART_VAR)) == "None")
    check(f"the garments drawn worn are {WORN_PARTS}",
          {g.display: g.worn[0] for g in GARMENTS if g.worn} == WORN_PARTS
          and all(g.worn[1] == CLOTHING[g.worn[0]] for g in GARMENTS if g.worn))
    for g in GARMENTS:
        bp = load(g.path)
        name = g.display
        check(f"{name} exists", bp is not None, g.path)
        if not bp:
            continue
        check(f"{name} is a BP_WeaponItem, so the bag takes it",
              bp.get_blueprint_parent_class() == BEL.generated_class(item))
        d = cdo(bp)
        check(f"{name} is worn as the {g.slot} (ClothingSlot {g.slot_index})",
              d.get_editor_property(CLOTHING_SLOT_VAR) == g.slot_index,
              repr(d.get_editor_property(CLOTHING_SLOT_VAR)))
        part, mesh = (str(d.get_editor_property(WORN_PART_VAR)),
                      d.get_editor_property(WORN_MESH_VAR))
        if g.worn:
            check(f"{name} fills {g.worn[0]} worn, as {g.worn[1].rsplit('/', 1)[1]}",
                  part == g.worn[0] and isinstance(mesh, unreal.SkeletalMesh)
                  and _path(mesh) == g.worn[1], f"{part} {_path(mesh)}")
        else:
            check(f"{name} is drawn as nothing worn (WornMesh empty, no WornPart)",
                  mesh is None and part == "None", f"{part} {_path(mesh)}")
        check(f"{name} is Consumable, so the fire key uses it",
              d.get_editor_property("Consumable") is True)
        check(f"{name} starts Dropped, so a placed one can be picked up",
              d.get_editor_property("Dropped") is True)
        check(f"{name} is named {name!r}", d.get_editor_property("DisplayName") == name)
        check(f"{name} is carried in A_HoldItem",
              d.get_editor_property("AimPose") == load(HOLD_ITEM_ANIM_PATH))
        check(f"{name}'s AdsZoom is above 1", d.get_editor_property("AdsZoom") > 1.0)
        check(f"{name} has an inventory icon", d.get_editor_property("Icon") is not None)
        present = set(components(bp))
        stand_in = [p[0] for p in g.parts]
        if g.worn:
            _check_ground_model(bp, g, present & set(stand_in))
            parts = [MODEL]
        else:
            parts = stand_in
            check(f"{name} has its parts {parts}", set(parts) <= present,
                  str(sorted(present)))
        blocking = [p for p in parts
                    if (t := component_template(bp, p)) is not None
                    and t.get_collision_enabled() != unreal.CollisionEnabled.NO_COLLISION]
        check(f"{name}'s parts collide with nothing", not blocking, str(blocking))
    # No check_handles_in_fist here, unlike the forage: the fist is closed on
    # a handle, and a folded shirt or a pack has none, so the fingers stand in
    # the cloth. The grip only seats the first part's middle in the fist.
