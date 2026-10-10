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

BP_ConsumableItem adds the numbers GA_ConsumeItem reads off the payload:
HungerRestore, ThirstRestore, and HealthRestoreEasy (applied on EASY only).
"""

from uebp.vars import declare, defaults
from survival import consumable_vars as CV
import unreal

from combat.log import _log
from uebp.graph import BEL, BGE, _apply_defaults, _assets, _create_blueprint, _must_load
from uebp.layout import arrange
from combat.materials import build_flat_material
from combat.paths import HOLD_ITEM_ANIM_PATH, ITEM_BP_PATH
from combat.grip_handle import seed_grip
from combat.grip import _grip_location, _grip_rotation
from combat.tuning import COMBAT
from combat.weapon_items import build_parts
from combat.weapon_specs import _weapon_icon
from item_icons.items import ICON_TINT
from survival.consumable_specs import MATERIALS, consumable_specs
from survival.paths import CONSUMABLE_BP_PATH
from Sound.bind import defaults_for
from Sound.sound_items import BINDINGS as ITEM_SOUNDS
from combat import item_vars as IV


def build_consumable_materials():
    for path, colour, metallic, roughness, emissive in MATERIALS:
        build_flat_material(path, colour, metallic, roughness, emissive)


def build_consumable_item():
    """The consumable base: BP_WeaponItem + the three restores."""
    item_bp = _must_load(ITEM_BP_PATH)
    bp = _create_blueprint(CONSUMABLE_BP_PATH, BEL.generated_class(item_bp))
    ed = BGE.get_graph_editor_by_name(bp, "EventGraph")
    declare(ed, CV.TABLE)
    arrange(ed)
    if not BEL.compile_blueprint(bp):
        raise RuntimeError("BP_ConsumableItem failed to compile")
    _apply_defaults(bp, {IV.Consumable: True, **defaults(CV.TABLE)})
    _log(f"built {CONSUMABLE_BP_PATH}")
    return bp


def build_consumable(spec, base_bp):
    """One consumable: its parts, and the base classes' defaults for it.

    Carried in A_HoldItem (combat/hold_pose.py) with the grip solved against
    it: in one hand at the waist, by its `grip_part`, not aimed like a gun. There is no eating
    animation: nothing in the project can author one (see CLAUDE.md, *The
    player's body*).
    """
    bp = _create_blueprint(spec["path"], BEL.generated_class(base_bp))
    build_parts(bp, spec["parts"])
    if not BEL.compile_blueprint(bp):
        raise RuntimeError(f"{spec['path']} failed to compile")
    aim = HOLD_ITEM_ANIM_PATH
    grip_rot = _grip_rotation(aim)
    grip_loc = unreal.Vector(*_grip_location(aim, grip_rot, spec["parts"], spec["grip_part"]))
    seed_grip(bp, grip_loc, grip_rot)
    _apply_defaults(bp, {
        **defaults_for(spec["path"], ITEM_SOUNDS),
        IV.DisplayName: spec["display"],
        IV.Consumable: True,
        CV.HungerRestore: float(spec["hunger"]),
        CV.ThirstRestore: float(spec["thirst"]),
        CV.HealthRestoreEasy: float(spec["health_easy"]),
        # True, unlike every weapon: a consumable starts life on the ground,
        # which is exactly what E looks for. place_forage.py therefore needs no
        # per-instance override (Python refuses to write a Blueprint variable
        # on an instance unless it is Instance Editable), and picking one up
        # clears it like any weapon.
        IV.Dropped: True,
        IV.UsesAmmo: False,
        IV.Automatic: False,
        IV.Damage: 0.0,
        IV.PelletCount: 0,
        IV.MagazineSize: 0,
        IV.Loaded: 0,
        IV.Reserve: 0,
        IV.NextFireTime: 0.0,
        IV.MuzzleOffset: unreal.Vector(0.0, 0.0, 0.0),
        IV.GripLocation: grip_loc,
        IV.GripRotation: grip_rot,
        IV.SlotColor: unreal.LinearColor(*ICON_TINT, 1.0),
        # Not 1.0: the ADS speed and scope fade divide by (AdsZoom - 1), and
        # right-click still aims with food in hand. The irons zoom is the
        # harmless value every unscoped weapon already uses.
        IV.AdsZoom: float(COMBAT.ads_zoom_irons),
        IV.Scoped: False,
        IV.RecoilPitch: 0.0,
        IV.ShotVolume: 0.0,
        IV.Icon: _weapon_icon(spec["display"]),
        IV.AimPose: _must_load(aim),
    })
    _log(f"built {spec['path']} ({spec['display']}: +{spec['hunger']:.0f} hunger, "
         f"+{spec['thirst']:.0f} thirst, +{spec['health_easy']:.0f} health on easy)")
    return bp


def build_consumables():
    """Materials, the base class, then every row of consumable_specs()."""
    build_consumable_materials()
    base = build_consumable_item()
    built = {spec["display"]: build_consumable(spec, base)
             for spec in consumable_specs()}
    _assets().save_loaded_asset(base)
    return base, built
