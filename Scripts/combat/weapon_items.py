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
from combat.chop_tuning import CHOPS_VAR
from combat.light_tuning import LIGHTS_VAR
from combat.graph import (
    BEL, BGE, _add_component, _apply_defaults, _assets, _component_object,
    _create_blueprint, _declare, _drop_components, _find_handle, _float_type,
    _handles, _log, _must_load, _root_handle, _struct_type,
)
from combat.paths import ITEM_BP_PATH
from combat.seat_tuning import HAS_SIGHTS_VAR
from combat.support_hand import SUPPORT_POINT_VAR
from combat.slot_tuning import (
    GUN_KINDS, LONG_GUN, NOT_A_WEAPON, SLOT_VAR, UNPLACED, WEAPON_KIND_VAR,
)
from combat.sway_tuning import SWAY_RATE, SWAY_RATE_COLUMN, SWAY_RATE_VAR
from combat.heat_tuning import COOL_VAR, HEAT_MATERIAL_VAR, HEATS_VAR, HOT_VAR
from combat.torch_tuning import BURN_OUT_VAR, BURNS_VAR, LIT_VAR, USE_POSE_VAR
from combat.throw_tuning import (
    LODGE_POINT_VAR, LODGE_TURN_VAR, THROW_DAMAGE_VAR,
    THROW_GRIP_LOC_VAR, THROW_GRIP_ROT_VAR, THROW_GRIP_VAR,
    THROW_EDGE_ON_VAR, THROW_PITCH_COLUMN, THROW_PITCH_UP_DEG, THROW_PITCH_VAR,
    THROW_SPEED, THROW_SPEED_VAR, THROW_SPIN_DEG_S, THROW_SPIN_VAR,
)
from combat.tuning import COMBAT
from combat.wear_tuning import CLOTHING_SLOT_VAR, NOT_CLOTHING
from combat.weapon_specs import ACCURACY_VARS, _weapon_icon
from item_icons.items import ICON_TINT


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
                       # Ammunition. UsesAmmo false means the other four are
                       # never read (the consumables), and the fire gate
                       # short-circuits on it. InfiniteReserve is the pistol:
                       # a real magazine to reload, over a reserve that is
                       # never charged and never credited by shell pickups.
                       ("UsesAmmo", "bool"),
                       ("MagazineSize", "int"),
                       ("Loaded", "int"),
                       ("Reserve", "int"),
                       ("InfiniteReserve", "bool"),
                       # Held trigger or tapped trigger. Read only behind the
                       # fire gate, where Held is known valid -- a pure Get off
                       # a null self is an Accessed None every frame, and the
                       # outer gate's condition is pulled on frames where
                       # nothing is equipped at all.
                       ("Automatic", "bool"),
                       # Used rather than fired: the fire key sends
                       # CONSUME_EVENT_TAG and the item is spent (see
                       # weapon_component/consume.py). On the base class, not
                       # on BP_ConsumableItem, so the weapon component can ask
                       # without naming a class that is built after it.
                       ("Consumable", "bool"),
                       # Swung rather than fired: the fire key slashes with it
                       # (weapon_component/knife.py). The knife (knife.py).
                       ("Melee", "bool"),
                       # Its blow bites a tree (weapon_component/chop.py): the
                       # axe. Read behind the blow's own IsValid(Held).
                       (CHOPS_VAR, "bool"),
                       # Struck rather than fired: the fire key lights a
                       # campfire with it (weapon_component/light.py). The
                       # matches. Read behind the fire gate, as Melee is.
                       (LIGHTS_VAR, "bool"),
                       # Aimed down its sights by the sights key: a gun. False
                       # on everything else, which that key aims over the
                       # shoulder (weapon_component/ads.py).
                       (HAS_SIGHTS_VAR, "bool"),
                       # Lit at a campfire by the use key, and burning: the
                       # stick (stick.py, weapon_component/torch.py).
                       (BURNS_VAR, "bool"),
                       (LIT_VAR, "bool"),
                       # Heated at a campfire by the interact key, and hot:
                       # the knife and the axe (heat.py,
                       # weapon_component/heat.py).
                       (HEATS_VAR, "bool"),
                       (HOT_VAR, "bool")):
        _declare(ed, name, BEL.get_basic_type_by_name(kind))
    # The slot a garment is worn in (wear_tuning.WEAR_SLOTS' index), or
    # NOT_CLOTHING: the weapon component wears an item whose slot is >= 0
    # (weapon_component/wear.py). Scripts/clothing sets it on each garment.
    _declare(ed, CLOTHING_SLOT_VAR, BEL.get_basic_type_by_name("int"))
    # Where it is carried (slot_tuning: the hand, a weapon slot, a bag slot,
    # or UNPLACED), and which weapon slot it belongs in (NOT_A_WEAPON on
    # everything but the guns and the blades). weapon_component/slot_*.py.
    _declare(ed, SLOT_VAR, BEL.get_basic_type_by_name("int"))
    _declare(ed, WEAPON_KIND_VAR, BEL.get_basic_type_by_name("int"))
    _declare(ed, BURN_OUT_VAR, _float_type())
    _declare(ed, COOL_VAR, _float_type())
    # The overlay a hot blade's model wears (heat.py). None on everything
    # that does not heat.
    _declare(ed, HEAT_MATERIAL_VAR, BEL.get_object_reference_type(
        unreal.MaterialInterface.static_class()))
    _declare(ed, "MuzzleOffset", _struct_type(unreal.Vector.static_struct()))
    # Where the eye goes when this weapon is aimed down its sights, in the
    # weapon's own space: on the sight line, behind the rear sight (on the
    # scope's axis for the sniper). The camera is moved there from the
    # shoulder boom; see weapon_component/sights.py. A variable for the same
    # reason MuzzleOffset is -- the component reads it off Held.
    _declare(ed, "SightOffset", _struct_type(unreal.Vector.static_struct()))
    # ...and what the eye looks at from there: the front sight's tip (the
    # scope's objective). The camera is turned onto it, so the view runs down
    # the sight line itself and the tip is the middle of the screen.
    _declare(ed, "SightAim", _struct_type(unreal.Vector.static_struct()))
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
    # The pose a lit stick is raised in while the use key holds it out
    # (weapon_component/torch.py). None on everything else.
    _declare(ed, USE_POSE_VAR,
             BEL.get_object_reference_type(unreal.AnimSequence.static_class()))
    # Held in both hands (the rifle ready pose). The guard reads it to raise
    # the gun across the body instead of the fists (body_pose.py). False on
    # the base, so the pistol and every consumable guard with the fists.
    _declare(ed, "TwoHanded", BEL.get_basic_type_by_name("bool"))
    # Where this gun's ready pose has the left hand, in the right hand's bone
    # space (support_hand.py): down the sights the hand is held there. Zero
    # on the base; nothing holds a hand on an item that has no sights.
    _declare(ed, SUPPORT_POINT_VAR, _struct_type(unreal.Vector.static_struct()))
    # How far this weapon zooms when the right button is held. On the item for
    # the same reason SpreadDegrees is -- the component reads it off Held and
    # knows nothing about which weapon it is holding.
    _declare(ed, "AdsZoom", _float_type())
    # Whether aiming this weapon puts a scope over the screen. A flag rather
    # than "AdsZoom >= COMBAT.ads_zoom_scope": the zoom is how far the camera moves
    # and the scope is what the sight looks like, and a future weapon is free
    # to be a 4x with irons or a 2x with glass without either answer moving.
    _declare(ed, "Scoped", BEL.get_basic_type_by_name("bool"))
    # Accuracy: the cloud a shot is drawn in and the kick it puts on the view,
    # with their stance and aim factors. One variable per GUN_ACCURACY column
    # (weapon_specs.py says what each means), on the item for the same reason
    # AdsZoom is: the component reads them off Held and knows nothing about
    # which weapon it is holding. SpreadDegrees is declared above with Damage.
    for _col, name in ACCURACY_VARS:
        if name != "SpreadDegrees":
            _declare(ed, name, _float_type())
    # How far this weapon's shot is heard by the wanderers, in cm (see
    # SHOT_VOLUME_CM in tuning.py). On the item so the shot's noise is read off
    # Held like every other per-weapon number.
    _declare(ed, "ShotVolume", _float_type())
    # How fast the sights wander down them (sway_tuning.py): the component
    # copies Held's each frame. The default is on the base, so an item with
    # no sights has one too, though it never sways.
    _declare(ed, SWAY_RATE_VAR, _float_type())
    # How far a throw of this item is tipped up from the view, where the
    # reticle rests on nothing it can reach (throw_launch.py reads it off
    # Held). The default is on the base, so the knife, the food and the
    # water throw on it too; a gun's own comes from its spec.
    _declare(ed, THROW_PITCH_VAR, _float_type())
    # How fast it leaves the hand and how fast it tumbles in the air, and
    # whether it leaves squared up to the throw, edge first: a melee weapon's
    # are its own (throw_tuning.MELEE_THROW).
    _declare(ed, THROW_SPEED_VAR, _float_type())
    _declare(ed, THROW_SPIN_VAR, _float_type())
    _declare(ed, THROW_EDGE_ON_VAR, BEL.get_basic_type_by_name("bool"))
    # What a throw of it takes off a body it strikes, and how it sits lodged
    # in a tree (weapon_component/throw_strike.py): a blade's are its own, and
    # the base's 0 damage is what keeps every other item from doing either.
    _declare(ed, THROW_DAMAGE_VAR, _float_type())
    _declare(ed, LODGE_TURN_VAR, _struct_type(unreal.Rotator.static_struct()))
    _declare(ed, LODGE_POINT_VAR, _struct_type(unreal.Vector.static_struct()))
    # Held by the blade while the throw is cocked (throw_tuning.THROW_GRIP_VAR).
    _declare(ed, THROW_GRIP_VAR, BEL.get_basic_type_by_name("bool"))
    _declare(ed, THROW_GRIP_LOC_VAR, _struct_type(unreal.Vector.static_struct()))
    _declare(ed, THROW_GRIP_ROT_VAR, _struct_type(unreal.Rotator.static_struct()))

    if not BEL.compile_blueprint(bp):
        raise RuntimeError("BP_WeaponItem failed to compile")
    _apply_defaults(bp, {CLOTHING_SLOT_VAR: NOT_CLOTHING,
                         SLOT_VAR: UNPLACED,
                         WEAPON_KIND_VAR: NOT_A_WEAPON,
                         THROW_PITCH_VAR: THROW_PITCH_UP_DEG,
                         SWAY_RATE_VAR: SWAY_RATE,
                         THROW_SPEED_VAR: THROW_SPEED,
                         THROW_SPIN_VAR: THROW_SPIN_DEG_S,
                         THROW_EDGE_ON_VAR: False,
                         THROW_DAMAGE_VAR: 0.0,
                         LODGE_TURN_VAR: unreal.Rotator(0.0, 0.0, 0.0),
                         LODGE_POINT_VAR: unreal.Vector(0.0, 0.0, 0.0),
                         THROW_GRIP_VAR: False,
                         THROW_GRIP_LOC_VAR: unreal.Vector(0.0, 0.0, 0.0),
                         THROW_GRIP_ROT_VAR: unreal.Rotator(0.0, 0.0, 0.0)})
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


# The components every weapon keeps: its own root and BP_WeaponItem's Body.
KEEP = {"None", "DefaultSceneRoot", "Body"}


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

    _apply_defaults(bp, {
        "DisplayName": spec["display"],
        "Damage": float(spec["damage"]),
        "PelletCount": int(spec["pellets"]),
        "WeaponRange": float(spec["range"]),
        "Dropped": False,
        "UsesAmmo": bool(spec["uses_ammo"]),
        "Automatic": bool(spec["automatic"]),
        "Consumable": False,
        "Melee": False,
        WEAPON_KIND_VAR: GUN_KINDS.get(spec["display"], LONG_GUN),
        HAS_SIGHTS_VAR: True,
        "MagazineSize": int(spec["magazine"]),
        # Starts loaded. A weapon that had to be reloaded before its first shot
        # would be a puzzle, not a mechanic.
        "Loaded": int(spec["magazine"]),
        "Reserve": int(spec["reserve"]),
        "InfiniteReserve": bool(spec.get("infinite_reserve", False)),
        "FireInterval": float(spec["interval"]),
        "ReloadSeconds": float(spec["reload_s"]),
        # World time 0 is "now" at level start, so the first shot is free.
        "NextFireTime": 0.0,
        "MuzzleOffset": unreal.Vector(*spec["muzzle"]),
        "SightOffset": unreal.Vector(*spec["sight"]),
        "SightAim": unreal.Vector(*spec["sight_front"]),
        "GripLocation": unreal.Vector(*spec["grip_loc"]),
        "GripRotation": spec["grip_rot"],
        "SlotColor": unreal.LinearColor(*ICON_TINT, 1.0),
        "AdsZoom": float(spec.get("ads_zoom", COMBAT.ads_zoom_irons)),
        "Scoped": bool(spec.get("scoped", False)),
        **{name: float(spec[col]) for col, name in ACCURACY_VARS},
        "ShotVolume": float(spec["shot_volume"]),
        THROW_PITCH_VAR: float(spec[THROW_PITCH_COLUMN]),
        SWAY_RATE_VAR: float(spec[SWAY_RATE_COLUMN]),
        "Icon": _weapon_icon(spec["display"]),
        "FireSound": _must_load(spec["sound"]),
        "DryFireSound": _must_load(SND_DRY_FIRE),
        "ReloadSound": _must_load(spec["reload_sound"]),
        "AimPose": _must_load(spec["aim"]),
        "TwoHanded": bool(spec["two_handed"]),
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
