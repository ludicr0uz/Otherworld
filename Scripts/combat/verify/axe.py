"""verify.axe -- the axe (combat/axe.py): the item, its model in the fist, and
its place in the starting loadout. The swing is the knife's (verify/knife.py):
the one Held.Melee Branch takes either."""

import unreal

from combat.axe import AXE_DISPLAY, AXE_MESH, AXE_SCALE, axe_outline
from combat.paths import AXE_BP_PATH, HOLD_KNIFE_ANIM_PATH, ITEM_BP_PATH
from combat.verify.common import (
    BEL, by_pins, cdo, check, component_template, load,
)
from combat.verify.fixtures import w, wg
from combat.verify.grip_fit import check_handles_in_fist
from combat.verify.punch import _feeders, _title
from combat.weapon_component.inventory import STARTER_CLASS_VARS
from combat.weapon_component.knife import MELEE_VAR

# A one-handed camp axe, head to knob (cm).
AXE_LENGTH_CM = (50.0, 80.0)


def check_axe_item():
    bp = load(AXE_BP_PATH)
    check("BP_Axe exists", bp is not None)
    if bp is None:
        return
    check("...a child of BP_WeaponItem, so the bag, Q, G, E and the HUD take it",
          bp.get_blueprint_parent_class() == BEL.generated_class(load(ITEM_BP_PATH)))
    d = cdo(bp)
    flags = {k: d.get_editor_property(k) for k in
             (MELEE_VAR, "Consumable", "UsesAmmo", "Automatic", "Dropped")}
    check("...Melee, so the fire key swings it, and not a consumable, a gun or "
          "lying about",
          flags == {MELEE_VAR: True, "Consumable": False, "UsesAmmo": False,
                    "Automatic": False, "Dropped": False}, str(flags))
    model = component_template(bp, "Model")
    mesh = model.get_editor_property("static_mesh") if model else None
    check("...drawn by Quaternius's Survival Pack axe (SM_Axe)",
          mesh is not None and mesh == load(AXE_MESH), str(mesh))
    if model is None or mesh is None:
        return
    box = mesh.get_bounding_box()
    scale = model.get_editor_property("relative_scale3d")
    length = (box.max.z - box.min.z) * scale.z
    check(f"...at {AXE_SCALE}, a one-handed axe "
          f"({AXE_LENGTH_CM[0]:.0f}-{AXE_LENGTH_CM[1]:.0f} cm long)",
          abs(scale.x - AXE_SCALE) < 1e-4 and scale.x == scale.y == scale.z
          and AXE_LENGTH_CM[0] < length < AXE_LENGTH_CM[1], f"{length:.1f} cm")
    rot = model.get_editor_property("relative_rotation")
    turn = unreal.MathLibrary.greater_greater_vector_rotator
    head, bit = turn(unreal.Vector(0.0, 0.0, 1.0), rot), turn(unreal.Vector(-1.0, 0.0, 0.0), rot)
    check("...head up and forward out of the fist, the bit leading",
          head.z > 0.8 and head.x > 0.1 and bit.x > 0.8, f"head {head} bit {bit}")
    check("...and blocking nothing in the hand or on the ground",
          str(model.get_collision_profile_name()) == "NoCollision",
          str(model.get_collision_profile_name()))
    pose = d.get_editor_property("AimPose")
    check("...held in A_HoldKnife, with an icon and its name",
          pose is not None and pose == load(HOLD_KNIFE_ANIM_PATH)
          and d.get_editor_property("Icon") is not None
          and str(d.get_editor_property("DisplayName")) == AXE_DISPLAY,
          f"{pose} {d.get_editor_property('Icon')}")
    check_handles_in_fist([("Axe", AXE_BP_PATH, HOLD_KNIFE_ANIM_PATH,
                            axe_outline(), "Grip", None)])


def check_axe_loadout():
    got = w.get_editor_property("AxeClass")
    check("AxeClass points at BP_Axe_C",
          got is not None and got.get_name() == "BP_Axe_C", str(got))
    spawned = [_title(f) for n in by_pins(wg, "Class", "SpawnTransform")
               for f in _feeders(n, "Class")]
    starters = [f"Get {v}" for v in STARTER_CLASS_VARS]
    check(f"BeginPlay spawns each of the {len(starters)} issued items once, the "
          "axe among them",
          "Get AxeClass" in starters
          and all(spawned.count(s) == 1 for s in starters), str(sorted(spawned)))


def run():
    check_axe_item()
    check_axe_loadout()
