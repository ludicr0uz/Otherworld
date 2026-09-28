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

from combat.audio import SND_DRY_FIRE
from combat.graph import (
    BEL, BGE, _add_component, _apply_defaults, _assets, _component_object,
    _create_blueprint, _declare, _drop_components, _find_handle, _float_type,
    _log, _must_load, _root_handle, _struct_type,
)
from combat.paths import ITEM_BP_PATH
from combat.tuning import COMBAT
from combat.weapon_specs import _weapon_icon


def build_weapon_item():
    """The base weapon Actor: no geometry, no graph, just the data a gun has.

    Every property the weapon component reads is declared here so that Inventory
    can be a plain array of BP_WeaponItem and the firing code needs exactly one
    cast. The muzzle is a *variable*, not a component: a component would have to
    live either on this class (and then be un-overridable per child) or on each
    child (and then be ambiguous to look up), whereas an offset transformed by
    the actor's transform costs one node and is settable per child.
    """
    bp = _create_blueprint(ITEM_BP_PATH, unreal.Actor)
    ed = BGE.get_graph_editor_by_name(bp, "EventGraph")

    _drop_components(bp, {"Body"})
    _add_component(bp, _root_handle(bp), unreal.SceneComponent, "Body")

    for name in ("Damage", "SpreadDegrees", "WeaponRange",
                 # When this weapon may next be fired, as a world time in
                 # seconds. One number does both jobs the shotgun needs: the
                 # interval between shots, and the pause a reload costs. A
                 # "reloading" bool plus a timer would need an interrupt rule
                 # and could disagree with itself; a deadline cannot.
                 "FireInterval", "NextFireTime", "ReloadSeconds"):
        _declare(ed, name, _float_type())
    for name, kind in (("DisplayName", "string"),
                       ("PelletCount", "int"),
                       ("Dropped", "bool"),
                       # Ammunition. UsesAmmo false means the other three are
                       # never read -- the pistol is deliberately unlimited, and
                       # the fire gate short-circuits on this rather than on a
                       # magazine that would have to be topped up forever.
                       ("UsesAmmo", "bool"),
                       ("MagazineSize", "int"),
                       ("Loaded", "int"),
                       ("Reserve", "int"),
                       # Held trigger or tapped trigger. Read only behind the
                       # fire gate, where Held is known valid -- a pure Get off
                       # a null self is an Accessed None every frame, and the
                       # outer gate's condition is pulled on frames where
                       # nothing is equipped at all.
                       ("Automatic", "bool")):
        _declare(ed, name, BEL.get_basic_type_by_name(kind))
    _declare(ed, "MuzzleOffset", _struct_type(unreal.Vector.static_struct()))
    _declare(ed, "GripLocation", _struct_type(unreal.Vector.static_struct()))
    _declare(ed, "GripRotation", _struct_type(unreal.Rotator.static_struct()))
    _declare(ed, "SlotColor", _struct_type(unreal.LinearColor.static_struct()))
    # The weapon's own silhouette for the inventory strip, drawn by
    # build_graphics_menu.py. On the item rather than in a table in the HUD for
    # the same reason SlotColor and DisplayName are: adding a weapon stays a
    # row in _weapon_specs() and the HUD never learns any weapon's name.
    _declare(ed, "Icon",
             BEL.get_object_reference_type(unreal.Texture2D.static_class()))
    # Three sounds, not one, and all three live on the weapon for the same
    # reason FireSound does: the graphs read them off Held, so a new weapon is
    # a row in _weapon_specs() and nothing else. The dry-fire and reload
    # assets happen to be shared by every weapon today -- that is a fact about
    # the defaults, not about the shape of the data.
    for name in ("FireSound", "DryFireSound", "ReloadSound"):
        _declare(ed, name,
                 BEL.get_object_reference_type(unreal.SoundBase.static_class()))
    _declare(ed, "AimPose",
             BEL.get_object_reference_type(unreal.AnimSequence.static_class()))
    # How far this weapon zooms when the right button is held. On the item for
    # the same reason SpreadDegrees is -- the component reads it off Held and
    # knows nothing about which weapon it is holding.
    _declare(ed, "AdsZoom", _float_type())
    # Whether aiming this weapon puts a scope over the screen. A flag rather
    # than "AdsZoom >= COMBAT.ads_zoom_scope": the zoom is how far the camera moves
    # and the scope is what the sight looks like, and a future weapon is free
    # to be a 4x with irons or a 2x with glass without either answer moving.
    _declare(ed, "Scoped", BEL.get_basic_type_by_name("bool"))
    # Degrees of upward kick this weapon puts on the view per shot. On the item
    # for the same reason AdsZoom and SpreadDegrees are: the component reads it
    # off Held and knows nothing about which weapon it is holding. The
    # horizontal half is not a second column -- it is a fraction of this one,
    # drawn per shot, and the fraction is the same for every gun (see
    # COMBAT.recoil_horizontal_ratio).
    _declare(ed, "RecoilPitch", _float_type())

    if not BEL.compile_blueprint(bp):
        raise RuntimeError("BP_WeaponItem failed to compile")
    _assets().save_loaded_asset(bp)
    _log(f"built {ITEM_BP_PATH}")
    return bp


def build_weapon(spec, item_bp):
    """One concrete weapon: the parts, plus the defaults for the base's variables."""
    eas = _assets()
    bp = _create_blueprint(spec["path"], BEL.generated_class(item_bp))

    body = _find_handle(bp, "Body")
    if not body:
        raise RuntimeError(f"{spec['path']} has no inherited Body component")

    _drop_components(bp, {p[0] for p in spec["parts"]})
    for name, mesh_path, location, rotation, scale, material in spec["parts"]:
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

    if not BEL.compile_blueprint(bp):
        raise RuntimeError(f"{spec['path']} failed to compile")

    # The HUD fades the scope on (BaseFOV/CurrentFOV - 1) / (AdsZoom - 1), so a
    # scoped weapon that does not zoom is a divide by zero once per frame while
    # it is aimed. Caught here rather than guarded there: it is a nonsense row
    # in the table, not a state the game can reach.
    if spec.get("scoped") and float(spec.get("ads_zoom", COMBAT.ads_zoom_irons)) <= 1.0:
        raise RuntimeError(f"{spec['display']} is scoped but does not zoom")

    _apply_defaults(bp, {
        "DisplayName": spec["display"],
        "Damage": float(spec["damage"]),
        "PelletCount": int(spec["pellets"]),
        "SpreadDegrees": float(spec["spread"]),
        "WeaponRange": float(spec["range"]),
        "Dropped": False,
        "UsesAmmo": bool(spec["uses_ammo"]),
        "Automatic": bool(spec["automatic"]),
        "MagazineSize": int(spec["magazine"]),
        # Starts loaded. A weapon that had to be reloaded before its first shot
        # would be a puzzle, not a mechanic.
        "Loaded": int(spec["magazine"]),
        "Reserve": int(spec["reserve"]),
        "FireInterval": float(spec["interval"]),
        "ReloadSeconds": float(spec["reload_s"]),
        # World time 0 is "now" at level start, so the first shot is free.
        "NextFireTime": 0.0,
        "MuzzleOffset": unreal.Vector(*spec["muzzle"]),
        "GripLocation": unreal.Vector(*spec["grip_loc"]),
        "GripRotation": spec["grip_rot"],
        "SlotColor": unreal.LinearColor(*spec["colour"], 1.0),
        "AdsZoom": float(spec.get("ads_zoom", COMBAT.ads_zoom_irons)),
        "Scoped": bool(spec.get("scoped", False)),
        "RecoilPitch": float(spec["recoil"]),
        "Icon": _weapon_icon(spec["display"]),
        "FireSound": _must_load(spec["sound"]),
        "DryFireSound": _must_load(SND_DRY_FIRE),
        "ReloadSound": _must_load(spec["reload_sound"]),
        "AimPose": _must_load(spec["aim"]),
    })
    _log(f"built {spec['path']} ({len(spec['parts'])} parts, "
         f"{spec['pellets']}x{spec['damage']:.0f} dmg, "
         f"{spec['recoil']:.2f} deg kick, "
         + (f"{spec['magazine']}+{spec['reserve']} rounds, "
            f"{spec['interval']:.2f}s between shots"
            if spec["uses_ammo"] else "unlimited ammo")
         + (", automatic)" if spec["automatic"] else ")"))
    return bp
