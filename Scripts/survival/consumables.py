"""BP_ConsumableItem and one child per consumable (BP_Mushroom,
BP_WaterCanteen), plus their flat materials.

A consumable IS a BP_WeaponItem -- a child of it, with Consumable set -- and
that is deliberate rather than a naming accident. Everything the inventory
already does is keyed on BP_WeaponItem: Inventory is an array of it, E picks
up anything of it flagged Dropped, G drops it, Q cycles it, the HUD strip draws
its Icon/SlotColor/DisplayName. A sibling class would need a second array or a
cast in every one of those graphs. What the base class has that food does not
need (damage, a magazine) is simply zero here, and the fire key never reaches
it: the weapon component branches on Consumable before the gun code runs.

BP_ConsumableItem adds the two numbers GA_ConsumeItem reads off the payload,
HungerRestore and ThirstRestore.
"""

import unreal

from combat.graph import (
    BEL, BGE, _apply_defaults, _assets, _create_blueprint, _declare,
    _float_type, _log, _must_load,
)
from combat.materials import build_flat_material
from combat.paths import ITEM_BP_PATH
from combat.skin import player_skin
from combat.grip import _grip_location, _grip_rotation
from combat.tuning import COMBAT
from combat.weapon_items import build_parts
from combat.weapon_specs import _weapon_icon
from survival.consumable_specs import MATERIALS, consumable_specs
from survival.paths import CONSUMABLE_BP_PATH


def build_consumable_materials():
    for path, colour, metallic, roughness, emissive in MATERIALS:
        build_flat_material(path, colour, metallic, roughness, emissive)


def build_consumable_item():
    """The consumable base: BP_WeaponItem + HungerRestore/ThirstRestore."""
    item_bp = _must_load(ITEM_BP_PATH)
    bp = _create_blueprint(CONSUMABLE_BP_PATH, BEL.generated_class(item_bp))
    ed = BGE.get_graph_editor_by_name(bp, "EventGraph")
    for name in ("HungerRestore", "ThirstRestore"):
        _declare(ed, name, _float_type())
    if not BEL.compile_blueprint(bp):
        raise RuntimeError("BP_ConsumableItem failed to compile")
    _apply_defaults(bp, {"Consumable": True, "HungerRestore": 0.0,
                         "ThirstRestore": 0.0})
    _log(f"built {CONSUMABLE_BP_PATH}")
    return bp


def build_consumable(spec, base_bp):
    """One consumable: its parts, and the base classes' defaults for it.

    Held like the pistol -- the pistol's ready pose and its solved grip -- so
    the item is carried out in front in one hand, by its `grip_part`. There is no eating
    animation: nothing in the project can author one (see CLAUDE.md, *The
    player's body*).
    """
    bp = _create_blueprint(spec["path"], BEL.generated_class(base_bp))
    build_parts(bp, spec["parts"])
    if not BEL.compile_blueprint(bp):
        raise RuntimeError(f"{spec['path']} failed to compile")
    aim = player_skin().aim_pistol
    grip_rot = _grip_rotation(aim)
    _apply_defaults(bp, {
        "DisplayName": spec["display"],
        "Consumable": True,
        "HungerRestore": float(spec["hunger"]),
        "ThirstRestore": float(spec["thirst"]),
        # True, unlike every weapon: a consumable starts life on the ground,
        # which is exactly what E looks for. place_forage.py therefore needs no
        # per-instance override (Python refuses to write a Blueprint variable
        # on an instance unless it is Instance Editable), and picking one up
        # clears it like any weapon.
        "Dropped": True,
        "UsesAmmo": False,
        "Automatic": False,
        "Damage": 0.0,
        "PelletCount": 0,
        "MagazineSize": 0,
        "Loaded": 0,
        "Reserve": 0,
        "NextFireTime": 0.0,
        "MuzzleOffset": unreal.Vector(0.0, 0.0, 0.0),
        "GripLocation": unreal.Vector(*_grip_location(aim, grip_rot, spec["parts"],
                                                       spec["grip_part"])),
        "GripRotation": grip_rot,
        "SlotColor": unreal.LinearColor(*spec["colour"], 1.0),
        # Not 1.0: the ADS speed and scope fade divide by (AdsZoom - 1), and
        # right-click still aims with food in hand. The irons zoom is the
        # harmless value every unscoped weapon already uses.
        "AdsZoom": float(COMBAT.ads_zoom_irons),
        "Scoped": False,
        "RecoilPitch": 0.0,
        "ShotVolume": 0.0,
        "Icon": _weapon_icon(spec["display"]),
        "AimPose": _must_load(aim),
    })
    _log(f"built {spec['path']} ({spec['display']}: +{spec['hunger']:.0f} hunger, "
         f"+{spec['thirst']:.0f} thirst)")
    return bp


def build_consumables():
    """Materials, the base class, then every row of consumable_specs()."""
    build_consumable_materials()
    base = build_consumable_item()
    built = {spec["display"]: build_consumable(spec, base)
             for spec in consumable_specs()}
    _assets().save_loaded_asset(base)
    return base, built
