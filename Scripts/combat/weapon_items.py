"""BP_WeaponItem, the base class every weapon derives from, and one child
Blueprint per weapon spec.

WHY WEAPONS ARE ACTORS NOW
--------------------------
The old shotgun was a component tree bolted onto the character's mesh, which
cannot be dropped: there is no way to leave a component behind in the world.
A weapon that has to exist both in a hand and on the ground is an Actor. That
one change is what makes drop, pick up and switching fall out naturally --
equipping is an attach, dropping is a detach.

BP_Shotgun and BP_Pistol derive from BP_WeaponItem rather than being two
unrelated Blueprints so that Inventory can be a single typed array and the
firing code can read Damage/Spread/Range/FireSound off whatever is held. The
alternative -- two sibling classes -- would need a cast and a duplicate branch
per weapon in every graph that touches a weapon.
"""

import unreal

from Sound.bind import defaults_for
from Sound.sound_items import BINDINGS as ITEM_SOUNDS
from Sound.sound_weapons import DRY_FIRE
from combat.glimmer import add_glimmer, author_glimmer
from combat.glimmer_tuning import GLIMMER
from combat.grip_handle import GRIP, seed_grip
from combat.item_world import relevance_item, replicate_item
from combat.log import _log
from uebp.graph import (
    BEL, BGE, _add_component, _apply_defaults, _assets, _component_object,
    _create_blueprint, _drop_components, _events, _find_handle, _handles, _must_load,
    _root_handle, then,
)
from uebp.layout import arrange
from combat.paths import ITEM_BP_PATH
from combat.seat_tuning import HAS_SIGHTS_VAR
from combat.support_hand import SUPPORT_POINT_VAR
from combat.slot_tuning import GUN_KINDS, LONG_GUN, WEAPON_KIND_VAR
from combat.sway_tuning import SWAY_RATE_COLUMN, SWAY_RATE_VAR
from combat.throw_tuning import THROW_PITCH_COLUMN, THROW_PITCH_VAR
from combat.tuning import COMBAT
from combat.weapon_specs import ACCURACY_VARS, _weapon_icon
from item_icons.items import ICON_TINT
from uebp.vars import declare, defaults
from combat import item_vars as IV


def build_weapon_item():
    """The base weapon Actor: no geometry, just the data a gun has, and the
    one thing every item does for itself: glimmer while it lies on the ground
    (glimmer.py, the Tick's only step).

    Every property the weapon component reads is declared here so that Inventory
    can be a plain array of BP_WeaponItem and the firing code needs exactly one
    cast. The muzzle is a *variable*, not a component: a component would have to
    live either on this class (and then be un-overridable per child) or on each
    child (and then be ambiguous to look up), whereas an offset transformed by
    the actor's transform costs one node and is settable per child.
    """
    bp = _create_blueprint(ITEM_BP_PATH, unreal.Actor)
    ed = BGE.get_graph_editor_by_name(bp, "EventGraph")

    # The graph is wiped before the components are rebuilt, for stick.py's
    # reason: its node names the Glimmer component.
    tick, _begin = _events(ed, True)
    _drop_components(bp, {"Body"})
    body = _add_component(bp, _root_handle(bp), unreal.SceneComponent, "Body")
    add_glimmer(bp, body)

    declare(ed, IV.TABLE)

    # What an item loose in the world shows every client (item_world.py):
    # after the declares, which drop the flags.
    replicate_item(bp)
    # The components are variables of the class only once it has compiled.
    if not BEL.compile_blueprint(bp):
        raise RuntimeError("BP_WeaponItem failed to compile")
    author_glimmer(ed, [then(tick)])
    arrange(ed)
    if not BEL.compile_blueprint(bp):
        raise RuntimeError("BP_WeaponItem failed to compile")
    _apply_defaults(bp, {**defaults(IV.TABLE), **defaults_for(ITEM_BP_PATH, ITEM_SOUNDS)})
    # How far an item in the world is sent, and how often (task A2): a class
    # default, after the compile _apply_defaults ends with; every child's.
    relevance_item(bp)
    _assets().save_loaded_asset(bp)
    _log(f"built {ITEM_BP_PATH}")
    return bp


def build_parts(bp, parts):
    """Hang an item's primitive parts off its inherited Body component.

    Each part is (name, mesh, location, rotation, scale, material). Shared by
    every child of BP_WeaponItem -- the weapons here, and the food and water in
    Scripts/survival -- so the collision rule below is stated once.
    """
    eas = _assets()
    path = bp.get_path_name()
    body = _find_handle(bp, "Body")
    if not body:
        raise RuntimeError(f"{path} has no inherited Body component")

    _drop_components(bp, {p[0] for p in parts})
    for name, mesh_path, location, rotation, scale, material in parts:
        handle = _add_component(bp, body, unreal.StaticMeshComponent, name)
        obj = _component_object(handle)
        obj.set_editor_property("static_mesh", eas.load_asset(mesh_path))
        obj.set_editor_property("relative_location", unreal.Vector(*location))
        obj.set_editor_property("relative_rotation", rotation)
        obj.set_editor_property("relative_scale3d", unreal.Vector(*scale))
        obj.set_editor_property("override_materials", [eas.load_asset(material)])
        # A held weapon must never block anything -- a collider on the barrel
        # would shove the player's capsule around -- and a dropped one is picked
        # up by distance, not by overlap, so it needs no collision either.
        try:
            obj.set_collision_profile_name("NoCollision")
        except Exception as exc:                                  # noqa: BLE001
            _log(f"  note: could not set NoCollision on {name}: {exc}")


# The components every weapon keeps: its own root, BP_WeaponItem's Body and
# Glimmer, and its Grip, which somebody may have placed (grip_handle.py).
KEEP = {"None", "DefaultSceneRoot", "Body", GLIMMER, GRIP}


def build_model(bp, model):
    """Hang a weapon's model off its inherited Body component.

    Each entry is (name, mesh, location, rotation, scale); a skeletal mesh gets
    a SkeletalMeshComponent and a static one a StaticMeshComponent, each with
    the mesh's own materials. No animation is set, so a skeletal gun holds its
    reference pose: the magazine in, the trigger forward.
    """
    body = _find_handle(bp, "Body")
    if not body:
        raise RuntimeError(f"{bp.get_path_name()} has no inherited Body component")
    _drop_components(bp, {m[0] for m in model})
    for name, mesh_path, location, rotation, scale in model:
        mesh = _must_load(mesh_path)
        skeletal = isinstance(mesh, unreal.SkeletalMesh)
        handle = _add_component(bp, body, unreal.SkeletalMeshComponent if skeletal
                                else unreal.StaticMeshComponent, name)
        obj = _component_object(handle)
        obj.set_editor_property("skeletal_mesh_asset" if skeletal else "static_mesh", mesh)
        obj.set_editor_property("relative_location", unreal.Vector(*location))
        obj.set_editor_property("relative_rotation", rotation)
        obj.set_editor_property("relative_scale3d", unreal.Vector(*scale))
        # The same rule as build_parts: a held or dropped gun blocks nothing.
        obj.set_collision_profile_name("NoCollision")


def build_weapon(spec, item_bp):
    """One concrete weapon: its model or its parts, plus the defaults for the
    base's variables. A model gun's parts are its measured outline (see
    weapon_models.py), which nothing builds."""
    bp = _create_blueprint(spec["path"], BEL.generated_class(item_bp))
    model = spec.get("model")
    built = [m[0] for m in model] if model else [p[0] for p in spec["parts"]]
    # Whatever the last build hung on the weapon and this one does not: the
    # rifle's primitive parts, the first time it is built as a model.
    _drop_components(bp, {n for _h, n in _handles(bp)} - set(built) - KEEP)
    if model:
        build_model(bp, model)
    else:
        build_parts(bp, spec["parts"])

    if not BEL.compile_blueprint(bp):
        raise RuntimeError(f"{spec['path']} failed to compile")

    # The HUD fades the scope on (BaseFOV/CurrentFOV - shoulder) /
    # (AdsZoom - shoulder), so a scoped weapon that does not zoom past the
    # shoulder aim is a divide by zero (or a glass that never shows) once per
    # frame while it is aimed. Caught here rather than guarded there: it is a
    # nonsense row in the table, not a state the game can reach.
    if (spec.get("scoped") and float(spec.get("ads_zoom", COMBAT.ads_zoom_irons))
            <= COMBAT.shoulder_zoom):
        raise RuntimeError(f"{spec['display']} is scoped but does not zoom past "
                           f"the shoulder aim")

    grip_loc = unreal.Vector(*spec["grip_loc"])
    seed_grip(bp, grip_loc, spec["grip_rot"])
    _apply_defaults(bp, {
        IV.DisplayName: spec["display"],
        IV.Damage: float(spec["damage"]),
        IV.PelletCount: int(spec["pellets"]),
        IV.WeaponRange: float(spec["range"]),
        IV.Dropped: False,
        IV.UsesAmmo: bool(spec["uses_ammo"]),
        IV.Automatic: bool(spec["automatic"]),
        IV.Consumable: False,
        IV.Melee: False,
        WEAPON_KIND_VAR: GUN_KINDS.get(spec["display"], LONG_GUN),
        HAS_SIGHTS_VAR: True,
        IV.MagazineSize: int(spec["magazine"]),
        # Starts loaded. A weapon that had to be reloaded before its first shot
        # would be a puzzle, not a mechanic.
        IV.Loaded: int(spec["magazine"]),
        IV.Reserve: int(spec["reserve"]),
        IV.InfiniteReserve: bool(spec.get("infinite_reserve", False)),
        IV.FireInterval: float(spec["interval"]),
        IV.ReloadSeconds: float(spec["reload_s"]),
        # World time 0 is "now" at level start, so the first shot is free.
        IV.NextFireTime: 0.0,
        IV.MuzzleOffset: unreal.Vector(*spec["muzzle"]),
        IV.SightOffset: unreal.Vector(*spec["sight"]),
        IV.SightAim: unreal.Vector(*spec["sight_front"]),
        IV.GripLocation: grip_loc,
        IV.GripRotation: spec["grip_rot"],
        IV.SlotColor: unreal.LinearColor(*ICON_TINT, 1.0),
        IV.AdsZoom: float(spec.get("ads_zoom", COMBAT.ads_zoom_irons)),
        IV.Scoped: bool(spec.get("scoped", False)),
        **{name: float(spec[col]) for col, name in ACCURACY_VARS},
        IV.ShotVolume: float(spec["shot_volume"]),
        THROW_PITCH_VAR: float(spec[THROW_PITCH_COLUMN]),
        SWAY_RATE_VAR: float(spec[SWAY_RATE_COLUMN]),
        IV.Icon: _weapon_icon(spec["display"]),
        **defaults_for(spec["path"], ITEM_SOUNDS),
        IV.FireSound: _must_load(spec["sound"]),
        IV.DryFireSound: _must_load(DRY_FIRE.paths[0]),
        IV.ReloadSound: _must_load(spec["reload_sound"]),
        IV.AimPose: _must_load(spec["aim"]),
        IV.TwoHanded: bool(spec["two_handed"]),
        SUPPORT_POINT_VAR: unreal.Vector(*spec["support_point"]),
    })
    _log(f"built {spec['path']} ("
         + (f"model {', '.join(m[1].rsplit('/', 1)[-1] for m in model)}, " if model
            else f"{len(spec['parts'])} parts, ")
         + f"{spec['pellets']}x{spec['damage']:.0f} dmg, "
         f"{spec['spread']:.1f} deg cloud, {spec['recoil']:.2f}/"
         f"{spec['recoil_yaw']:.3f} deg kick, "
         f"heard at {spec['shot_volume'] / 100.0:.0f} m, "
         + (f"{spec['magazine']}+"
            f"{'inf' if spec.get('infinite_reserve') else spec['reserve']} rounds, "
            f"{spec['interval']:.2f}s between shots"
            if spec["uses_ammo"] else "unlimited ammo")
         + (", automatic)" if spec["automatic"] else ")"))
    return bp
