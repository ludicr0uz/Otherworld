"""
build_weapons_and_combat.py -- weapons, inventory, aiming, damage and death.

Run inside the editor:
    UnrealEditor-Cmd <uproject> \
      -ExecutePythonScript="<abs>/Scripts/build_weapons_and_combat.py" -NoUI -stdout

Supersedes build_shotgun_and_health.py, which built a single shotgun welded to
the character. Everything that file installed is removed by this one (see
_uninstall_old_shotgun) -- keep the old script only as history.

WHAT THIS BUILDS
----------------
/Game/Weapons
  M_Gunmetal, M_GunWood, M_Blood   flat materials
  Audio/A_ShotgunFire, A_PistolFire  imported from Scripts/generated_assets/sounds
  BP_WeaponItem     Actor. The base class: every variable the weapon component
                    reads lives here, so the component casts once and never
                    branches per weapon type.
  BP_Shotgun        child of BP_WeaponItem: 7 primitives, 8 pellets, 5 deg cone
  BP_Pistol         child of BP_WeaponItem: 5 primitives, 1 shot, tight, held
                    at a different angle with a different ready pose
  BP_HealthComponent  Health/MaxHealth + death, despawn and respawn
  BP_WeaponComponent  inventory of 5, equip/switch/fire/drop/pick up
  BP_BloodSplash    short-lived red burst spawned at each impact

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

THE AIM POSE (the part with a real constraint behind it)
--------------------------------------------------------
The project ships a full Mannequin animation set: MF_Rifle_Idle_ADS,
MF_Pistol_Idle_ADS, directional rifle/pistol walk and jog, aim offsets. What it
does *not* ship is any Anim Blueprint that uses them -- ABP_Unarmed is the only
one, and it drives the unarmed locomotion state machines only.

Authoring a rifle locomotion state machine from Python is not possible: UBlendSpace
exposes no sample-authoring API at all, so the directional walk/jog sets cannot be
assembled into the blend spaces a locomotion graph would need.

What *is* possible is playing an animation into a slot. ABP_Unarmed's AnimGraph
has exactly one Slot node, DefaultSlot, sitting full-body between the locomotion
state machine and the Control Rig. Played as-is, an ADS idle would override the
legs too and the character would slide around in a frozen aim pose.

So patch_anim_blueprint() inserts a Layered blend per bone between the state
machine and the Control Rig: base pose = locomotion, blend pose = DefaultSlot,
branch filter = spine_01. DefaultSlot becomes upper-body-only, and
PlaySlotAnimationAsDynamicMontage(MF_Rifle_Idle_ADS, "DefaultSlot") then puts
the arms and chest in the ready pose while the legs keep walking, running and
jumping normally. One new node, one rewire, and it compiles.

Consequence worth knowing: every montage played on DefaultSlot is now
upper-body-only for this skeleton. Nothing in this project plays a full-body
montage (the NPC despawns rather than playing a death animation), but a future
death or knockdown animation would need its own slot.

BP_WeaponComponent event graph:

  [BeginPlay] --> cache Character + Mesh
              --> spawn BP_Shotgun and BP_Pistol into Inventory
              --> Equip(0)

  [Tick] --> Branch WasInputKeyJustPressed(LeftMouseButton) --> Fire
         --> Branch WasInputKeyJustPressed(Q)               --> cycle equipped
         --> Branch WasInputKeyJustPressed(G)               --> drop held
         --> Branch WasInputKeyJustPressed(E)               --> pick up nearest

  Fire: muzzle world location  -> Start
        camera aim point       -> direction
        N pellets in a cone    -> LineTraceSingle each
        hit -> BP_BloodSplash at the impact + Health -= Damage
"""

import math
import os

import unreal

# ─── Paths ───────────────────────────────────────────────────────────────────

WEAPON_DIR = "/Game/Weapons"
AUDIO_DIR = f"{WEAPON_DIR}/Audio"
MAT_METAL = f"{WEAPON_DIR}/M_Gunmetal"
MAT_WOOD = f"{WEAPON_DIR}/M_GunWood"
MAT_BLOOD = f"{WEAPON_DIR}/M_Blood"

ITEM_BP_PATH = f"{WEAPON_DIR}/BP_WeaponItem"
SHOTGUN_BP_PATH = f"{WEAPON_DIR}/BP_Shotgun"
PISTOL_BP_PATH = f"{WEAPON_DIR}/BP_Pistol"
HEALTH_BP_PATH = f"{WEAPON_DIR}/BP_HealthComponent"
WEAPON_COMP_BP_PATH = f"{WEAPON_DIR}/BP_WeaponComponent"
BLOOD_BP_PATH = f"{WEAPON_DIR}/BP_BloodSplash"

CHARACTER_BP_PATH = "/Game/ThirdPerson/Blueprints/BP_ThirdPersonCharacter"
NPC_BP_PATH = "/Game/Forest/NPC/BP_ForestWanderer"
ABP_PATH = "/Game/Characters/Mannequins/Anims/Unarmed/ABP_Unarmed"

CHARACTER_CLASS_PATH = f"{CHARACTER_BP_PATH}.BP_ThirdPersonCharacter_C"
NPC_CLASS_PATH = f"{NPC_BP_PATH}.BP_ForestWanderer_C"
ITEM_CLASS_PATH = f"{ITEM_BP_PATH}.BP_WeaponItem_C"
HEALTH_CLASS_PATH = f"{HEALTH_BP_PATH}.BP_HealthComponent_C"
WEAPON_COMP_CLASS_PATH = f"{WEAPON_COMP_BP_PATH}.BP_WeaponComponent_C"
BLOOD_CLASS_PATH = f"{BLOOD_BP_PATH}.BP_BloodSplash_C"

AIM_RIFLE = "/Game/Characters/Mannequins/Anims/Rifle/MF_Rifle_Idle_ADS"
AIM_PISTOL = "/Game/Characters/Mannequins/Anims/Pistol/MF_Pistol_Idle_ADS"

CUBE = "/Engine/BasicShapes/Cube"          # 100 cm box
CYLINDER = "/Engine/BasicShapes/Cylinder"  # 100 cm tall, 50 cm radius, axis +Z
SPHERE = "/Engine/BasicShapes/Sphere"      # 100 cm diameter

SOUND_SRC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                             "generated_assets", "sounds")

# ─── Tuning ──────────────────────────────────────────────────────────────────

START_HEALTH = 100.0
INVENTORY_SIZE = 5

# Polled keys.  1/2/3 and M belong to the graphics menu, so the weapon keys stay
# clear of them.
FIRE_KEY = "LeftMouseButton"
SWITCH_KEY = "Q"
DROP_KEY = "G"
PICKUP_KEY = "E"

PICKUP_RADIUS = 250.0      # cm; how close you must be to press E
DROP_FORWARD = 120.0       # cm in front of the player a dropped weapon lands
# Pellet traces drawn in the world for this many seconds; 0 turns them off.
# On, because they are the only way to see *where* a shot went -- sound and blood
# tell you a shot happened and that it connected, but not that it missed high.
TRACE_DEBUG_SECONDS = 1.5

# NPC respawn: a new wanderer appears within this radius of where the dead one
# *started*, not where it died, so the forest does not slowly drain toward
# wherever the player does their shooting. The replacement is immediate.
RESPAWN_RADIUS = 4000.0

GRIP_SOCKET = "HandGrip_R"

# Where the skeleton says a held weapon's muzzle belongs, measured in
# HandGrip_R's own space by querying the reference pose. Weapons are modelled
# along local +X, so aiming +X at this point puts the barrel where Epic's rig
# expects it instead of at a guessed angle.
MUZZLE_IN_GRIP_SPACE = (99.108845, 45.728250, -19.447308)

# The bone the upper body blend starts at. spine_01 is the lowest spine joint,
# so arms + chest follow the aim pose and the hips and legs keep locomotion.
UPPER_BODY_ROOT = "spine_01"
UPPER_BODY_BLEND_DEPTH = 4
AIM_SLOT = "DefaultSlot"

BGE = unreal.BlueprintGraphEditor
BEL = unreal.BlueprintEditorLibrary
PIN = unreal.BlueprintGraphPinLibrary
SDL = unreal.SubobjectDataBlueprintFunctionLibrary


def _log(msg):
    unreal.log_warning(f"[GUN] {msg}")


def _assets():
    return unreal.get_editor_subsystem(unreal.EditorAssetSubsystem)


def _subobjects():
    return unreal.get_engine_subsystem(unreal.SubobjectDataSubsystem)


# ─── Graph helpers ───────────────────────────────────────────────────────────
# Duplicated from build_graphics_menu.py on purpose: every builder in Scripts/
# has to run standalone under -ExecutePythonScript, which imports no package.

def _node(ed, function_path):
    """add_call_function_node, but loud when the path does not resolve.

    An unresolvable path yields a *pinless* node rather than None, and the
    failure then surfaces much later as "pin 'self' not found on ''".
    """
    n = ed.add_call_function_node(function_path)
    if not n or not BEL.list_all_pins(n):
        raise RuntimeError(f"{function_path} is not a Blueprint-callable function")
    return n


def _palette(ed, name, x=0.0, y=0.0):
    n = ed.create_node_from_name(name, unreal.Vector2D(float(x), float(y)), [])
    if not n:
        raise RuntimeError(f"palette node {name!r} could not be created")
    return n


def _pin(node, name, is_input=True):
    p = (BEL.find_input_pin(node, name) if is_input
         else BEL.find_output_pin(node, name))
    if not p or not p.is_valid():
        raise RuntimeError(f"pin {name!r} ({'in' if is_input else 'out'}) not found; "
                           f"node has {_pin_names(node)}")
    return p


def _pin_names(node):
    return ([str(PIN.get_pin_name(p)) for p in BEL.list_input_pins(node)],
            [str(PIN.get_pin_name(p)) for p in BEL.list_output_pins(node)])


def _loose_pin(node, wanted, is_input=True):
    """Find a pin ignoring spaces and case.

    Macro nodes name their pins "First Index" / "Loop Body", and whether the
    space is there is not something to rely on.
    """
    key = wanted.replace(" ", "").lower()
    for p in (BEL.list_input_pins(node) if is_input else BEL.list_output_pins(node)):
        if str(PIN.get_pin_name(p)).replace(" ", "").lower() == key:
            return p
    raise RuntimeError(f"no pin like {wanted!r} on node; has {_pin_names(node)}")


def _connect(a, b):
    if not a.try_create_connection(b):
        raise RuntimeError("could not connect pins")


def _set(node, name, value):
    _pin(node, name).set_pin_value(str(value))


def _at(node, x, y):
    BEL.set_node_pos(node, unreal.IntPoint(int(x), int(y)))
    return node


def _create_blueprint(path, parent_class):
    eas = _assets()
    if eas.does_asset_exist(path):
        existing = eas.load_asset(path)
        if existing:
            return existing
    package_path, asset_name = path.rsplit("/", 1)
    factory = unreal.BlueprintFactory()
    factory.set_editor_property("parent_class", parent_class)
    bp = unreal.AssetToolsHelpers.get_asset_tools().create_asset(
        asset_name, package_path, unreal.Blueprint, factory)
    if not bp:
        raise RuntimeError(f"could not create Blueprint {path}")
    return bp


def _float_type():
    """The pin type for a Blueprint float.

    NOT get_basic_type_by_name("float") -- that name is not recognised and the
    library silently falls back to **int**, logging only
    `Primitive type: float not recognized, defaulting to int`. "double" does the
    same. UE 5 calls the Blueprint float type "real", and it is the only spelling
    that produces a float property. Integral defaults like 100.0 or 4000.0 hide
    the bug completely, so it surfaces only once something needs a fraction.
    """
    return BEL.get_basic_type_by_name("real")


def _declare(ed, name, pin_type):
    """Re-declare a member variable so a type change in this file actually lands."""
    ed.remove_member_variable(name)
    if not ed.add_member_variable(name, pin_type):
        raise RuntimeError(f"could not declare {name}")


def _same(a, b):
    """Compare a read-back default with what was written.

    str() on a UE struct embeds its address, so two identical Vectors never
    compare equal that way -- to_tuple() is the field-wise view. Objects compare
    by path, since the read-back is a different wrapper around the same asset.
    """
    if isinstance(b, bool):
        return bool(a) == b
    if isinstance(b, float):
        return abs(float(a) - b) < 1e-6
    if isinstance(b, int):
        return int(a) == b
    if hasattr(b, "get_path_name"):
        return a is not None and a.get_path_name() == b.get_path_name()
    if hasattr(b, "to_tuple"):
        return (a is not None and hasattr(a, "to_tuple")
                and all(abs(x - y) < 1e-4 for x, y in zip(a.to_tuple(), b.to_tuple())))
    return str(a) == str(b)


def _apply_defaults(bp, defaults):
    """Write variable defaults onto the CDO, because add_member_variable cannot.

    ``add_member_variable(name, type, "100.0")`` returns True, and then the
    compiler logs `Can't parse default value '100.0'` and leaves the property at
    zero -- a default that reads as set everywhere except where it matters. UE
    5.8 exposes no Python API for a *member* variable's default (only
    set_local_variable_default_value, for locals), so the value is written to
    the compiled class's default object and baked in by recompiling.

    The read-back is the point: a weapon that silently does 0 damage, or a
    health component that starts dead, looks exactly like a working one until
    something shoots at it.
    """
    cdo = unreal.get_default_object(BEL.generated_class(bp))
    for name, value in defaults.items():
        cdo.set_editor_property(name, value)
    if not BEL.compile_blueprint(bp):
        raise RuntimeError(f"{bp.get_name()} failed to recompile after defaults")
    _assets().save_loaded_asset(bp)
    fresh = unreal.get_default_object(BEL.generated_class(bp))
    for name, value in defaults.items():
        got = fresh.get_editor_property(name)
        if not _same(got, value):
            raise RuntimeError(f"default for {name} did not stick: {got!r} != {value!r}")


# ─── Component helpers ───────────────────────────────────────────────────────

def _handles(bp):
    out = []
    for h in _subobjects().k2_gather_subobject_data_for_blueprint(bp):
        data = _subobjects().k2_find_subobject_data_from_handle(h)
        if not data:
            continue
        out.append((h, str(SDL.get_variable_name(data))))
    return out


def _find_handle(bp, name):
    for h, var in _handles(bp):
        if var == name:
            return h
    return None


def _root_handle(bp):
    handles = _subobjects().k2_gather_subobject_data_for_blueprint(bp)
    if not handles:
        raise RuntimeError("blueprint has no subobject root")
    return handles[0]


def _drop_components(bp, names):
    """Delete each named component *and everything hanging off it*.

    Deleting the root alone is not enough. delete_subobject does not cascade,
    and the orphans it leaves behind come back on the next run under generated
    names (StaticMesh7, StaticMesh13, ...) which then hold the names the real
    parts want -- so rename_subobject quietly fails and the actor accumulates a
    second, nameless copy of the weapon on every run.
    """
    sds = _subobjects()
    targets = set(names)
    # One delete per gather: every handle in a batch goes stale as soon as the
    # first of them is removed, and reusing one trips an ensure inside
    # USimpleConstructionScript::RemoveNodeAndPromoteChildren.
    for _ in range(200):
        entries = []
        for h in sds.k2_gather_subobject_data_for_blueprint(bp):
            data = sds.k2_find_subobject_data_from_handle(h)
            if not data:
                continue
            parent = SDL.get_parent_handle(data)
            parent_data = (sds.k2_find_subobject_data_from_handle(parent)
                           if parent else None)
            entries.append((str(SDL.get_variable_name(data)),
                            str(SDL.get_variable_name(parent_data))
                            if parent_data else "",
                            h))
        grew = True
        while grew:
            grew = False
            for var, parent, _h in entries:
                if parent in targets and var not in targets:
                    targets.add(var)
                    grew = True
        doomed = [(var, h) for var, parent, h in entries if var in targets]
        if not doomed:
            return
        claimed = {parent for _v, parent, _h in entries}
        leaves = [h for var, h in doomed if var not in claimed]
        sds.delete_subobject(_root_handle(bp), (leaves or [doomed[0][1]])[0], bp)
    raise RuntimeError(f"could not clear components {sorted(targets)}")


def _add_component(bp, parent_handle, cls, name):
    params = unreal.AddNewSubobjectParams()
    params.set_editor_property("parent_handle", parent_handle)
    params.set_editor_property("new_class", cls)
    params.set_editor_property("blueprint_context", bp)
    handle, failure = _subobjects().add_new_subobject(params)
    if failure and str(failure):
        raise RuntimeError(f"could not add {name}: {failure}")
    _subobjects().rename_subobject(handle, name)
    # Renaming onto a name something else already holds fails silently and
    # leaves the generated one, which is how duplicates went unnoticed before.
    got = str(SDL.get_variable_name(
        _subobjects().k2_find_subobject_data_from_handle(handle)))
    if got != name:
        raise RuntimeError(
            f"component came out named {got!r}, not {name!r} -- something stale "
            "is still holding that name")
    return handle


def _component_object(handle):
    return SDL.get_object(_subobjects().k2_find_subobject_data_from_handle(handle))


# ─── Weapon geometry ─────────────────────────────────────────────────────────

def _rotate_vector(rotator, vector):
    try:
        return rotator.rotate_vector(vector)
    except AttributeError:
        return unreal.MathLibrary.greater_greater_vector_rotator(vector, rotator)


def _grip_rotation():
    """Rotator that points a weapon's local +X at the hand's muzzle socket."""
    x, y, z = MUZZLE_IN_GRIP_SPACE
    length = math.sqrt(x * x + y * y + z * z)
    r = unreal.Rotator()
    r.yaw = math.degrees(math.atan2(y, x))
    r.pitch = math.degrees(math.asin(z / length))
    r.roll = 0.0
    return r


def _barrel_rotation():
    """Rotation that turns a Cylinder's +Z axis into the weapon's +X.

    Derived rather than hard-coded: the sign of the required pitch depends on
    UE's rotator handedness, which is easier to test than to argue about.
    """
    for pitch in (-90.0, 90.0):
        r = unreal.Rotator()
        r.pitch = pitch
        if _rotate_vector(r, unreal.Vector(0.0, 0.0, 1.0)).x > 0.9:
            return r
    raise RuntimeError("no pitch maps a cylinder's +Z onto +X")


def _rot(pitch=0.0, yaw=0.0, roll=0.0):
    r = unreal.Rotator()
    r.pitch, r.yaw, r.roll = pitch, yaw, roll
    return r


# Each part: (name, mesh, location, rotation, scale, material).
# Local frame: +X is the muzzle direction, +Z is up, origin sits in the fist.
# A Cube is 100 cm, so scale is the size in metres; a Cylinder is 100 cm tall
# with a 50 cm radius, so scale 0.02 gives a 1 cm radius.

def _shotgun_parts():
    barrel = _barrel_rotation()
    return (
        ("Receiver",     CUBE,     (25.0, 0.0, 0.0),   _rot(),          (0.30, 0.055, 0.075),  MAT_METAL),
        ("Barrel",       CYLINDER, (70.0, 0.0, 2.2),   barrel,          (0.024, 0.024, 0.60),  MAT_METAL),
        ("MagTube",      CYLINDER, (66.0, 0.0, -2.6),  barrel,          (0.020, 0.020, 0.52),  MAT_METAL),
        ("Pump",         CUBE,     (55.0, 0.0, -2.6),  _rot(),          (0.20, 0.050, 0.050),  MAT_WOOD),
        ("Stock",        CUBE,     (-8.0, 0.0, -2.5),  _rot(pitch=6.0), (0.34, 0.048, 0.070),  MAT_WOOD),
        ("Grip",         CUBE,     (8.0, 0.0, -6.0),   _rot(pitch=20.0),(0.055, 0.042, 0.085), MAT_WOOD),
        ("TriggerGuard", CUBE,     (14.0, 0.0, -4.5),  _rot(),          (0.070, 0.030, 0.020), MAT_METAL),
    )


def _pistol_parts():
    """Shorter, all-metal, and with the grip raked back under the receiver.

    The silhouette is what sells which weapon is in hand at a glance, so the
    pistol is deliberately a third the shotgun's length with no wood on it.
    """
    barrel = _barrel_rotation()
    return (
        ("Slide",        CUBE,     (14.0, 0.0, 1.5),   _rot(),           (0.17, 0.035, 0.040), MAT_METAL),
        ("Frame",        CUBE,     (10.0, 0.0, -2.0),  _rot(),           (0.14, 0.032, 0.030), MAT_METAL),
        ("Barrel",       CYLINDER, (24.0, 0.0, 1.5),   barrel,           (0.011, 0.011, 0.10), MAT_METAL),
        ("Grip",         CUBE,     (1.0, 0.0, -7.5),   _rot(pitch=15.0), (0.045, 0.036, 0.095), MAT_WOOD),
        ("TriggerGuard", CUBE,     (7.0, 0.0, -4.5),   _rot(),           (0.050, 0.026, 0.016), MAT_METAL),
    )


# Muzzle tip in the weapon's own space: where the barrel actually ends, so the
# pellet cone starts at the gun rather than inside the player's chest.
SHOTGUN_MUZZLE = (101.0, 0.0, 2.2)
PISTOL_MUZZLE = (30.0, 0.0, 1.5)


def _weapon_specs():
    """Everything that differs between the two weapons, in one table."""
    grip = _grip_rotation()
    return (
        dict(path=SHOTGUN_BP_PATH, parts=_shotgun_parts(), muzzle=SHOTGUN_MUZZLE,
             display="Shotgun", damage=9.0, pellets=8, spread=5.0, range=4000.0,
             sound=f"{AUDIO_DIR}/A_ShotgunFire", aim=AIM_RIFLE,
             grip_loc=(0.0, 0.0, 0.0), grip_rot=grip,
             colour=(0.85, 0.45, 0.10)),
        # Held higher in the hand and rolled slightly, so the two weapons do not
        # sit in the fist at the same angle; the bigger visual difference comes
        # from the pistol ready pose, which is a different animation entirely.
        dict(path=PISTOL_BP_PATH, parts=_pistol_parts(), muzzle=PISTOL_MUZZLE,
             display="Pistol", damage=26.0, pellets=1, spread=1.0, range=6000.0,
             sound=f"{AUDIO_DIR}/A_PistolFire", aim=AIM_PISTOL,
             grip_loc=(2.0, 0.0, 1.0),
             grip_rot=_rot(pitch=grip.pitch + 4.0, yaw=grip.yaw, roll=-8.0),
             colour=(0.35, 0.65, 0.95)),
    )


# ─── Materials and sounds ────────────────────────────────────────────────────

def build_materials():
    """Flat constant materials, so the parts read as a gun and not as white boxes.

    Material *instances* of BasicShapeMaterial would be cheaper, but that engine
    material exposes no parameters, so there is nothing to instance.
    """
    eas = _assets()
    mel = unreal.MaterialEditingLibrary
    for path, (colour, metallic, roughness, emissive) in (
            (MAT_METAL, ((0.055, 0.058, 0.065), 1.0, 0.32, None)),
            (MAT_WOOD, ((0.115, 0.062, 0.030), 0.0, 0.62, None)),
            # Blood is emissive so a splash reads at night, which is the only
            # lighting this project currently ships.
            (MAT_BLOOD, ((0.30, 0.005, 0.005), 0.0, 0.35, (0.55, 0.01, 0.01)))):
        if eas.does_asset_exist(path):
            continue
        package_path, name = path.rsplit("/", 1)
        mat = unreal.AssetToolsHelpers.get_asset_tools().create_asset(
            name, package_path, unreal.Material, unreal.MaterialFactoryNew())
        base = mel.create_material_expression(
            mat, unreal.MaterialExpressionConstant3Vector, -400, 0)
        base.set_editor_property("constant", unreal.LinearColor(*colour, 1.0))
        mel.connect_material_property(base, "", unreal.MaterialProperty.MP_BASE_COLOR)
        for value, prop, offset in ((metallic, unreal.MaterialProperty.MP_METALLIC, 160),
                                    (roughness, unreal.MaterialProperty.MP_ROUGHNESS, 300)):
            c = mel.create_material_expression(
                mat, unreal.MaterialExpressionConstant, -400, offset)
            c.set_editor_property("r", value)
            mel.connect_material_property(c, "", prop)
        if emissive:
            e = mel.create_material_expression(
                mat, unreal.MaterialExpressionConstant3Vector, -400, 440)
            e.set_editor_property("constant", unreal.LinearColor(*emissive, 1.0))
            mel.connect_material_property(e, "", unreal.MaterialProperty.MP_EMISSIVE_COLOR)
        mel.recompile_material(mat)
        eas.save_loaded_asset(mat)
        _log(f"built {path}")


def import_sounds():
    """Import the synthesised WAVs as SoundWave assets.

    The .wav files come from Scripts/make_weapon_sounds.py, which is pure Python
    and has already run by the time this does -- see main(). Nothing in
    /Engine/Content is a usable gunshot, so they are generated rather than
    referenced.
    """
    eas = _assets()
    made = []
    for name in ("A_ShotgunFire", "A_PistolFire"):
        dest = f"{AUDIO_DIR}/{name}"
        if eas.does_asset_exist(dest):
            made.append(dest)
            continue
        src = os.path.join(SOUND_SRC_DIR, f"{name}.wav")
        if not os.path.isfile(src):
            raise RuntimeError(f"missing {src} -- run Scripts/make_weapon_sounds.py")
        task = unreal.AssetImportTask()
        task.set_editor_property("filename", src)
        task.set_editor_property("destination_path", AUDIO_DIR)
        task.set_editor_property("destination_name", name)
        task.set_editor_property("automated", True)
        task.set_editor_property("replace_existing", True)
        task.set_editor_property("save", True)
        unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
        if not eas.does_asset_exist(dest):
            raise RuntimeError(f"import produced no asset at {dest}")
        made.append(dest)
        _log(f"imported {dest}")
    return made


# ─── The AnimGraph patch ─────────────────────────────────────────────────────

def patch_anim_blueprint():
    """Make DefaultSlot upper-body-only in ABP_Unarmed.

    ABP_Unarmed ships as:

        StateMachine(locomotion) -> Slot(DefaultSlot) -> ControlRig -> Root

    so anything played into DefaultSlot replaces the *whole* body and the
    character slides around frozen in the aim pose. This inserts a layered blend
    so the slot only reaches the upper body:

        StateMachine --+-------------------> LayeredBoneBlend.BasePose ---+
                       |                                                  |--> ControlRig
                       +--> Slot(DefaultSlot) -> LayeredBoneBlend.Blend ---+

    with a spine_01 branch filter. Legs keep walking; arms and chest take the
    ready pose.

    Re-running is safe: an existing LayeredBoneBlend means the patch is already
    in, and the function returns without touching anything. The check is by node
    class rather than by a flag, so a hand-reverted graph is re-patched.
    """
    bp = _assets().load_asset(ABP_PATH)
    if not bp:
        raise RuntimeError(f"could not load {ABP_PATH}")
    ed = BGE.get_graph_editor_by_name(bp, "AnimGraph")
    if not ed:
        raise RuntimeError("ABP_Unarmed has no AnimGraph")

    def by_class(name):
        return [n for n in ed.list_all_nodes() if n.get_class().get_name() == name]

    if by_class("AnimGraphNode_LayeredBoneBlend"):
        _log("ABP_Unarmed already has the upper-body blend — leaving it alone")
        return bp

    slots = by_class("AnimGraphNode_Slot")
    rigs = by_class("AnimGraphNode_ControlRig")
    if len(slots) != 1 or len(rigs) != 1:
        raise RuntimeError(
            f"expected exactly one Slot and one ControlRig in ABP_Unarmed's "
            f"AnimGraph, found {len(slots)} and {len(rigs)}")
    slot, rig = slots[0], rigs[0]

    feeding = PIN.list_connected_pins(_pin(slot, "Source"))
    if not feeding:
        raise RuntimeError("Slot.Source is unconnected; graph is not what we expect")
    loco = PIN.get_owning_node(feeding[0])

    blend = _at(_palette(ed, "Animation|Blends|Layeredblendperbone"), -420, 620)

    # A pose output legally drives more than one input here, so the locomotion
    # pose reaches both the blend's base and the slot's source without needing
    # a cached-pose pair.
    _connect(_pin(loco, "Pose", is_input=False), _pin(blend, "BasePose"))
    PIN.break_pin_links(_pin(rig, "Source"))
    _connect(_pin(slot, "Pose", is_input=False), _pin(blend, "BlendPoses_0"))
    _connect(_pin(blend, "Pose", is_input=False), _pin(rig, "Source"))

    bone = unreal.BranchFilter()
    bone.set_editor_property("bone_name", UPPER_BODY_ROOT)
    bone.set_editor_property("blend_depth", UPPER_BODY_BLEND_DEPTH)
    layer = unreal.InputBlendPose()
    layer.set_editor_property("branch_filters", [bone])
    # layer_setup lives on the inner FAnimNode struct, not on the graph node, and
    # the struct read back is a copy -- so it has to be written back wholesale.
    inner = blend.get_editor_property("node")
    inner.set_editor_property("layer_setup", [layer])
    inner.set_editor_property("blend_weights", [1.0])
    blend.set_editor_property("node", inner)

    if not BEL.compile_blueprint(bp):
        raise RuntimeError("ABP_Unarmed failed to compile after the blend patch")
    _assets().save_loaded_asset(bp)

    got = blend.get_editor_property("node").get_editor_property("layer_setup")
    filters = [str(f.get_editor_property("bone_name"))
               for l in got for f in l.get_editor_property("branch_filters")]
    if filters != [UPPER_BODY_ROOT]:
        raise RuntimeError(f"branch filter did not stick: {filters}")
    _log(f"ABP_Unarmed: DefaultSlot is now upper-body only (from {UPPER_BODY_ROOT})")
    return bp


# ─── BP_WeaponItem and its two children ──────────────────────────────────────

def _struct_type(struct):
    return BEL.get_struct_type(struct)


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

    for name in ("Damage", "SpreadDegrees", "WeaponRange"):
        _declare(ed, name, _float_type())
    for name, kind in (("DisplayName", "string"),
                       ("PelletCount", "int"),
                       ("Dropped", "bool")):
        _declare(ed, name, BEL.get_basic_type_by_name(kind))
    _declare(ed, "MuzzleOffset", _struct_type(unreal.Vector.static_struct()))
    _declare(ed, "GripLocation", _struct_type(unreal.Vector.static_struct()))
    _declare(ed, "GripRotation", _struct_type(unreal.Rotator.static_struct()))
    _declare(ed, "SlotColor", _struct_type(unreal.LinearColor.static_struct()))
    _declare(ed, "FireSound",
             BEL.get_object_reference_type(unreal.SoundBase.static_class()))
    _declare(ed, "AimPose",
             BEL.get_object_reference_type(unreal.AnimSequence.static_class()))

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

    _apply_defaults(bp, {
        "DisplayName": spec["display"],
        "Damage": float(spec["damage"]),
        "PelletCount": int(spec["pellets"]),
        "SpreadDegrees": float(spec["spread"]),
        "WeaponRange": float(spec["range"]),
        "Dropped": False,
        "MuzzleOffset": unreal.Vector(*spec["muzzle"]),
        "GripLocation": unreal.Vector(*spec["grip_loc"]),
        "GripRotation": spec["grip_rot"],
        "SlotColor": unreal.LinearColor(*spec["colour"], 1.0),
        "FireSound": eas.load_asset(spec["sound"]),
        "AimPose": eas.load_asset(spec["aim"]),
    })
    _log(f"built {spec['path']} ({len(spec['parts'])} parts, "
         f"{spec['pellets']}x{spec['damage']:.0f} dmg)")
    return bp


# ─── Graph node paths ────────────────────────────────────────────────────────

FN_GET_OWNER = "/Script/Engine.ActorComponent.GetOwner"
FN_GET_PC = "/Script/Engine.GameplayStatics.GetPlayerController"
FN_WAS_PRESSED = "/Script/Engine.PlayerController.WasInputKeyJustPressed"
FN_GET_CAM = "/Script/Engine.GameplayStatics.GetPlayerCameraManager"
FN_CAM_LOC = "/Script/Engine.PlayerCameraManager.GetCameraLocation"
FN_CAM_ROT = "/Script/Engine.PlayerCameraManager.GetCameraRotation"
FN_FORWARD = "/Script/Engine.KismetMathLibrary.GetForwardVector"
FN_RAND_CONE = "/Script/Engine.KismetMathLibrary.RandomUnitVectorInConeInRadians"
FN_TRACE = "/Script/Engine.KismetSystemLibrary.LineTraceSingle"
FN_GET_COMP = "/Script/Engine.Actor.GetComponentByClass"
FN_IS_VALID = "/Script/Engine.KismetSystemLibrary.IsValid"
# A class reference is a different pin category from an object reference, so
# IsValid refuses to connect to one; IsValidClass is the class-pin twin.
FN_IS_VALID_CLASS = "/Script/Engine.KismetSystemLibrary.IsValidClass"
FN_TRANSFORM_LOC = "/Script/Engine.KismetMathLibrary.TransformLocation"
FN_GET_TRANSFORM = "/Script/Engine.Actor.GetTransform"
FN_ACTOR_LOC = "/Script/Engine.Actor.K2_GetActorLocation"
FN_MAKE_TRANSFORM = "/Script/Engine.KismetMathLibrary.MakeTransform"
FN_MAKE_VECTOR = "/Script/Engine.KismetMathLibrary.MakeVector"
FN_NORMAL = "/Script/Engine.KismetMathLibrary.Normal"
FN_DEG2RAD = "/Script/Engine.KismetMathLibrary.DegreesToRadians"
FN_PLAY_SOUND = "/Script/Engine.GameplayStatics.PlaySoundAtLocation"
FN_ATTACH = "/Script/Engine.Actor.K2_AttachToComponent"
FN_DETACH = "/Script/Engine.Actor.K2_DetachFromActor"
FN_SET_HIDDEN = "/Script/Engine.Actor.SetActorHiddenInGame"
FN_SET_ACTOR_LOC = "/Script/Engine.Actor.K2_SetActorLocation"
FN_SET_REL_LOC = "/Script/Engine.Actor.K2_SetActorRelativeLocation"
FN_SET_REL_ROT = "/Script/Engine.Actor.K2_SetActorRelativeRotation"
FN_SET_SCALE = "/Script/Engine.Actor.SetActorScale3D"
FN_DESTROY = "/Script/Engine.Actor.K2_DestroyActor"
FN_LIFESPAN = "/Script/Engine.Actor.SetLifeSpan"
FN_ALL_ACTORS = "/Script/Engine.GameplayStatics.GetAllActorsOfClass"
FN_ANIM_INSTANCE = "/Script/Engine.SkeletalMeshComponent.GetAnimInstance"
FN_PLAY_SLOT = "/Script/Engine.AnimInstance.PlaySlotAnimationAsDynamicMontage"
FN_STOP_SLOT = "/Script/Engine.AnimInstance.StopSlotAnimation"
FN_RANDOM_NAV = ("/Script/NavigationSystem.NavigationSystemV1"
                 ".K2_GetRandomReachablePointInRadius")

FN_ARR_LEN = "/Script/Engine.KismetArrayLibrary.Array_Length"
FN_ARR_ADD = "/Script/Engine.KismetArrayLibrary.Array_Add"
FN_ARR_REMOVE = "/Script/Engine.KismetArrayLibrary.Array_Remove"

FN_ADD_VV = "/Script/Engine.KismetMathLibrary.Add_VectorVector"
FN_SUB_VV = "/Script/Engine.KismetMathLibrary.Subtract_VectorVector"
FN_MUL_VF = "/Script/Engine.KismetMathLibrary.Multiply_VectorFloat"
FN_ADD_II = "/Script/Engine.KismetMathLibrary.Add_IntInt"
FN_SUB_II = "/Script/Engine.KismetMathLibrary.Subtract_IntInt"
FN_MOD_II = "/Script/Engine.KismetMathLibrary.Percent_IntInt"
FN_EQ_II = "/Script/Engine.KismetMathLibrary.EqualEqual_IntInt"
FN_LESS_II = "/Script/Engine.KismetMathLibrary.Less_IntInt"
FN_AND = "/Script/Engine.KismetMathLibrary.BooleanAND"
FN_ADD_FF = "/Script/Engine.KismetMathLibrary.Add_DoubleDouble"
FN_SUB_FF = "/Script/Engine.KismetMathLibrary.Subtract_DoubleDouble"
FN_LE_FF = "/Script/Engine.KismetMathLibrary.LessEqual_DoubleDouble"
FN_LESS_FF = "/Script/Engine.KismetMathLibrary.Less_DoubleDouble"
FN_CLAMP = "/Script/Engine.KismetMathLibrary.FClamp"
FN_DISTANCE = "/Script/Engine.KismetMathLibrary.Vector_Distance"

NODE_TICK = "AddEvent|EventTick"
NODE_BEGIN_PLAY = "AddEvent|EventBeginPlay"
NODE_BREAK_HIT = "Collision|BreakHitResult"
NODE_SPAWN = "Game|SpawnActorfromClass"
NODE_CAST_CHAR = "Utilities|Casting|CastToBP_ThirdPersonCharacter"
NODE_CAST_HEALTH = "Utilities|Casting|CastToBP_HealthComponent"
MACRO_FOR_LOOP = "/Engine/EditorBlueprintResources/StandardMacros.StandardMacros:ForLoop"
MACRO_FOR_EACH = "/Engine/EditorBlueprintResources/StandardMacros.StandardMacros:ForEachLoop"

INF = 1.0e9


def _vec(ed, x, y, z, px, py):
    """A constant vector, as a MakeVector node rather than as a pin default.

    A struct pin refuses set_pin_value outright -- every format returns False
    and the pin keeps an empty default, which the compiler then reads as the
    zero vector. A zero scale on a spawn transform makes the actor invisible,
    so these have to be real nodes.
    """
    n = _at(_node(ed, FN_MAKE_VECTOR), px, py)
    for axis, value in (("X", x), ("Y", y), ("Z", z)):
        _set(n, axis, float(value))
    return _pin(n, "ReturnValue", is_input=False)


def _events(ed, rebuild):
    """Return (tick, begin_play), wiping the graph first when rebuilding.

    A builder whose "already authored, reusing" guard has no escape hatch means
    no edit to the builder ever reaches the asset, so rebuild is the default
    everywhere in this file.
    """
    if rebuild:
        nodes = ed.list_all_nodes()
        if nodes:
            ed.remove_nodes(nodes)
    tick = ed.find_event_node("ReceiveTick")
    if not tick:
        tick = _palette(ed, NODE_TICK, 0, 0)
    begin = ed.find_event_node("ReceiveBeginPlay")
    if not begin:
        begin = _palette(ed, NODE_BEGIN_PLAY, 0, -900)
    return tick, begin


def _post_physics_tick(bp):
    """Tick after the player controller has processed input this frame.

    WasInputKeyJustPressed reads EventCounts, which UPlayerInput::
    ProcessInputStack swaps out once per frame during the controller's
    TG_PrePhysics tick. A component defaults to TG_PrePhysics too, with no
    defined order against the controller, so a trigger polled there fires or
    does not fire depending on registration order.

    Nothing here enables ticking, and nothing needs to: bCanEverTick is not a
    UPROPERTY, but FKismetCompilerContext::SetCanEverTick turns it on at compile
    time for any Blueprint whose first native parent is UActorComponent and
    whose Tick event has its exec pin connected. Leave Tick wired.
    """
    cdo = unreal.get_default_object(BEL.generated_class(bp))
    tick_fn = cdo.get_editor_property("primary_component_tick")
    tick_fn.set_editor_property("tick_group", unreal.TickingGroup.TG_POST_PHYSICS)
    cdo.set_editor_property("primary_component_tick", tick_fn)


# ─── BP_BloodSplash ──────────────────────────────────────────────────────────

BLOOD_BLOBS = (
    (0.0, 0.0, 0.0, 0.10),
    (4.0, 3.0, 2.0, 0.07),
    (-3.0, 4.0, -2.0, 0.06),
    (2.0, -4.0, 3.0, 0.055),
    (-4.0, -2.0, -3.0, 0.05),
)
BLOOD_LIFETIME = 0.45
BLOOD_GROWTH = 5.0      # scale units per second


def build_blood_splash(rebuild=True):
    """A handful of emissive red spheres that swell and vanish.

    Not a particle system: Niagara systems cannot be authored from Python at
    all, and a Cascade emitter is no better. Five spheres that scale up over
    0.45 s and destroy themselves read as a splash at the distance you actually
    see them from, and they cost one Blueprint.
    """
    eas = _assets()
    bp = _create_blueprint(BLOOD_BP_PATH, unreal.Actor)
    names = {f"Blob{i}" for i in range(len(BLOOD_BLOBS))}
    _drop_components(bp, {"Burst"} | names)
    root = _add_component(bp, _root_handle(bp), unreal.SceneComponent, "Burst")
    for i, (x, y, z, scale) in enumerate(BLOOD_BLOBS):
        handle = _add_component(bp, root, unreal.StaticMeshComponent, f"Blob{i}")
        obj = _component_object(handle)
        obj.set_editor_property("static_mesh", eas.load_asset(SPHERE))
        obj.set_editor_property("relative_location", unreal.Vector(x, y, z))
        obj.set_editor_property("relative_scale3d", unreal.Vector(scale, scale, scale))
        obj.set_editor_property("override_materials", [eas.load_asset(MAT_BLOOD)])
        try:
            obj.set_collision_profile_name("NoCollision")
        except Exception as exc:                                  # noqa: BLE001
            _log(f"  note: could not set NoCollision on Blob{i}: {exc}")

    ed = BGE.get_graph_editor_by_name(bp, "EventGraph")
    tick, begin = _events(ed, rebuild)
    _declare(ed, "Age", _float_type())

    # BeginPlay: let the engine clean the actor up rather than tracking it.
    life = _at(_node(ed, FN_LIFESPAN), 320, -900)
    _set(life, "InLifespan", BLOOD_LIFETIME)
    _connect(BEL.find_then_pin(begin), _pin(life, "execute"))

    # Tick: Age += DeltaSeconds, scale = 1 + Age * growth.
    age_get = _at(ed.add_get_member_variable_node("Age"), 260, 200)
    add = _at(_node(ed, FN_ADD_FF), 470, 200)
    _connect(_pin(age_get, "Age", is_input=False), _pin(add, "A"))
    _connect(_pin(tick, "DeltaSeconds", is_input=False), _pin(add, "B"))
    age_set = _at(ed.add_set_member_variable_node("Age"), 700, 0)
    _connect(_pin(add, "ReturnValue", is_input=False), _pin(age_set, "Age"))
    _connect(BEL.find_then_pin(tick), _pin(age_set, "execute"))

    scale_v = _at(_node(ed, FN_MUL_VF), 940, 260)
    _connect(_vec(ed, BLOOD_GROWTH, BLOOD_GROWTH, BLOOD_GROWTH, 700, 400),
             _pin(scale_v, "A"))
    _connect(_pin(add, "ReturnValue", is_input=False), _pin(scale_v, "B"))
    bump = _at(_node(ed, FN_ADD_VV), 1160, 260)
    _connect(_vec(ed, 1.0, 1.0, 1.0, 940, 420), _pin(bump, "A"))
    _connect(_pin(scale_v, "ReturnValue", is_input=False), _pin(bump, "B"))

    set_scale = _at(_node(ed, FN_SET_SCALE), 1400, 0)
    _connect(_pin(bump, "ReturnValue", is_input=False), _pin(set_scale, "NewScale3D"))
    _connect(BEL.find_then_pin(age_set), _pin(set_scale, "execute"))

    ed.add_comment_to_nodes(
        f"Swells from 1x to about {1 + BLOOD_GROWTH * BLOOD_LIFETIME:.1f}x over "
        f"{BLOOD_LIFETIME}s, then SetLifeSpan removes the actor. Scaling on Tick "
        "rather than with a Timeline because a Timeline's curve asset cannot be "
        "authored from Python.",
        [age_get, add, age_set, scale_v, bump, set_scale, life])

    if not BEL.compile_blueprint(bp):
        raise RuntimeError("BP_BloodSplash failed to compile")
    eas.save_loaded_asset(bp)
    _log(f"built {BLOOD_BP_PATH} ({len(BLOOD_BLOBS)} blobs, {BLOOD_LIFETIME}s)")
    return bp


# ─── BP_HealthComponent ──────────────────────────────────────────────────────

def build_health_component(rebuild=True):
    """Health, plus what happens when it runs out.

    Health is a component rather than a variable on each character so that the
    shooter and the HUD share one lookup -- GetComponentByClass -> Cast ->
    Health -- that works on the player, on the NPC, and on anything given the
    component later.

    Death lives here too, and is driven by three defaults rather than by
    subclassing:

        DespawnOnDeath   destroy the owner at 0 HP. False on the player, so the
                         player simply sits at 0 rather than vanishing.
        RespawnClass     what to spawn in the dead actor's place. Set to
                         BP_ForestWanderer on the NPC, left empty on the player.
        SpawnOrigin      captured on BeginPlay; the replacement appears within
                         RESPAWN_RADIUS of where this one *started*, not where
                         it died, so the forest does not slowly drain toward
                         wherever the player does their shooting.

    Because the replacement carries the same component with the same defaults,
    one death begets one respawn indefinitely with nothing tracking it.

    Damage is applied by the weapon writing Health directly rather than through
    ApplyDamage / Event AnyDamage. AnyDamage is an *Actor* event, so routing
    through it would mean authoring a graph on both characters -- and
    BP_ThirdPersonCharacter's graph is the Enhanced Input template, which the
    graph API cannot partially rebuild.
    """
    bp = _create_blueprint(HEALTH_BP_PATH, unreal.ActorComponent)
    ed = BGE.get_graph_editor_by_name(bp, "EventGraph")
    tick, begin = _events(ed, rebuild)

    for name in ("Health", "MaxHealth"):
        _declare(ed, name, _float_type())
    for name in ("Dead", "DespawnOnDeath"):
        _declare(ed, name, BEL.get_basic_type_by_name("bool"))
    _declare(ed, "SpawnOrigin", _struct_type(unreal.Vector.static_struct()))
    _declare(ed, "RespawnClass",
             BEL.get_class_reference_type(unreal.Actor.static_class()))

    # --- BeginPlay: remember where this actor started ------------------------
    owner_b = _at(_node(ed, FN_GET_OWNER), 260, -740)
    loc_b = _at(_node(ed, FN_ACTOR_LOC), 500, -740)
    _connect(_pin(owner_b, "ReturnValue", is_input=False), _pin(loc_b, "self"))
    set_origin = _at(ed.add_set_member_variable_node("SpawnOrigin"), 760, -900)
    _connect(_pin(loc_b, "ReturnValue", is_input=False), _pin(set_origin, "SpawnOrigin"))
    _connect(BEL.find_then_pin(begin), _pin(set_origin, "execute"))

    # --- Tick: has it died this frame? ---------------------------------------
    health = _at(ed.add_get_member_variable_node("Health"), 240, 240)
    dying = _at(_node(ed, FN_LE_FF), 460, 240)
    _connect(_pin(health, "Health", is_input=False), _pin(dying, "A"))
    _set(dying, "B", 0.0)

    at_zero = _at(ed.add_branch_node(), 700, 0)
    _connect(_pin(dying, "ReturnValue", is_input=False), _pin(at_zero, "Condition"))
    _connect(BEL.find_then_pin(tick), _pin(at_zero, "execute"))

    # Branch on Dead and use its *False* pin -- one node cheaper than a NOT, and
    # it is what stops the death path running again every frame after the first.
    dead_get = _at(ed.add_get_member_variable_node("Dead"), 700, 240)
    already = _at(ed.add_branch_node(), 940, 0)
    _connect(_pin(dead_get, "Dead", is_input=False), _pin(already, "Condition"))
    _connect(BEL.find_then_pin(at_zero), _pin(already, "execute"))

    mark = _at(ed.add_set_member_variable_node("Dead"), 1180, 0)
    _set(mark, "Dead", "true")
    _connect(BEL.find_else_pin(already), _pin(mark, "execute"))

    despawn_get = _at(ed.add_get_member_variable_node("DespawnOnDeath"), 1180, 240)
    should = _at(ed.add_branch_node(), 1420, 0)
    _connect(_pin(despawn_get, "DespawnOnDeath", is_input=False), _pin(should, "Condition"))
    _connect(BEL.find_then_pin(mark), _pin(should, "execute"))

    # --- respawn, then destroy ----------------------------------------------
    cls_get = _at(ed.add_get_member_variable_node("RespawnClass"), 1660, 300)
    can_respawn = _at(_node(ed, FN_IS_VALID_CLASS), 1900, 300)
    _connect(_pin(cls_get, "RespawnClass", is_input=False), _pin(can_respawn, "Class"))
    respawns = _at(ed.add_branch_node(), 2120, 0)
    _connect(_pin(can_respawn, "ReturnValue", is_input=False), _pin(respawns, "Condition"))
    _connect(BEL.find_then_pin(should), _pin(respawns, "execute"))

    origin_get = _at(ed.add_get_member_variable_node("SpawnOrigin"), 2120, 300)
    where = _at(_node(ed, FN_RANDOM_NAV), 2360, 300)
    _connect(_pin(origin_get, "SpawnOrigin", is_input=False), _pin(where, "Origin"))
    _set(where, "Radius", RESPAWN_RADIUS)

    xform = _at(_node(ed, FN_MAKE_TRANSFORM), 2620, 300)
    _connect(_pin(where, "RandomLocation", is_input=False), _pin(xform, "Location"))
    _connect(_vec(ed, 1.0, 1.0, 1.0, 2360, 500), _pin(xform, "Scale"))

    spawn = _at(_palette(ed, NODE_SPAWN), 2880, 0)
    _connect(_pin(cls_get, "RespawnClass", is_input=False), _pin(spawn, "Class"))
    _connect(_pin(xform, "ReturnValue", is_input=False), _pin(spawn, "SpawnTransform"))
    # AlwaysSpawn: the random nav point is on the navmesh but may still overlap
    # a tree's collision, and a respawn that silently returns null would empty
    # the forest one death at a time.
    _set(spawn, "CollisionHandlingOverride", "AlwaysSpawn")
    _connect(BEL.find_then_pin(respawns), _pin(spawn, "execute"))

    owner_t = _at(_node(ed, FN_GET_OWNER), 2880, 380)
    destroy = _at(_node(ed, FN_DESTROY), 3140, 0)
    _connect(_pin(owner_t, "ReturnValue", is_input=False), _pin(destroy, "self"))
    # Both the respawned and the no-respawn-class paths end in the same destroy;
    # an exec *input* takes more than one link, so no Sequence node is needed.
    _connect(BEL.find_then_pin(spawn), _pin(destroy, "execute"))
    _connect(BEL.find_else_pin(respawns), _pin(destroy, "execute"))

    ed.add_comment_to_nodes(
        f"At 0 HP: mark Dead once, then (if DespawnOnDeath) spawn a replacement "
        f"on a random navmesh point within {RESPAWN_RADIUS / 100:.0f} m of where "
        "this actor spawned and destroy this one. The replacement carries the "
        "same component, so the cycle sustains itself with nothing tracking it. "
        "The player's copy has DespawnOnDeath false and no RespawnClass.",
        [health, dying, at_zero, dead_get, already, mark, despawn_get, should,
         cls_get, can_respawn, respawns, origin_get, where, xform, spawn,
         owner_t, destroy])

    _post_physics_tick(bp)
    if not BEL.compile_blueprint(bp):
        raise RuntimeError("BP_HealthComponent failed to compile")
    _apply_defaults(bp, {
        "Health": START_HEALTH,
        "MaxHealth": START_HEALTH,
        "Dead": False,
        "DespawnOnDeath": False,
    })
    _log(f"built {HEALTH_BP_PATH} (Health = MaxHealth = {START_HEALTH})")
    return bp


# ─── BP_WeaponComponent ──────────────────────────────────────────────────────

AIM_LOOPS = 9999          # PlaySlotAnimation has no "loop forever"; 9999 x 8 s
                          # is about a day, which outlasts any play session.
AIM_BLEND = 0.25


def _prop(ed, name, self_pin, x, y, class_path=ITEM_CLASS_PATH):
    """Read a variable off another object: Get <name> with its self pin driven.

    A data output pin takes any number of links, so one Held getter can feed
    every one of these.
    """
    n = _at(ed.add_get_member_variable_node(name, class_path), x, y)
    _connect(self_pin, _pin(n, "self"))
    return _pin(n, name, is_input=False), n


def _author_fire(ed, held, owner_loc_src, exec_in, x0, y0):
    """One trigger pull: sound, then one trace per pellet from the muzzle.

    The cone starts at the *muzzle*, not at the camera. Tracing from the camera
    is the usual third-person trick -- it guarantees the shot goes where the
    crosshair is -- but the camera sits on a boom behind the player, so the cone
    visibly fans out from behind their shoulder. Here the origin is the barrel
    tip (the weapon's MuzzleOffset through its own transform) and only the
    *direction* comes from the camera: aim at the point the camera is looking
    at, from where the gun actually is.
    """
    made = []

    def keep(n):
        made.append(n)
        return n

    xform = keep(_at(_node(ed, FN_GET_TRANSFORM), x0, y0 + 300))
    _connect(held, _pin(xform, "self"))
    off_pin, off_n = _prop(ed, "MuzzleOffset", held, x0, y0 + 440)
    keep(off_n)
    muzzle_n = keep(_at(_node(ed, FN_TRANSFORM_LOC), x0 + 260, y0 + 300))
    _connect(_pin(xform, "ReturnValue", is_input=False), _pin(muzzle_n, "T"))
    _connect(off_pin, _pin(muzzle_n, "Location"))
    muzzle = _pin(muzzle_n, "ReturnValue", is_input=False)

    cam = keep(_at(_node(ed, FN_GET_CAM), x0, y0 + 600))
    _set(cam, "PlayerIndex", 0)
    cam_out = _pin(cam, "ReturnValue", is_input=False)
    cam_loc = keep(_at(_node(ed, FN_CAM_LOC), x0 + 240, y0 + 580))
    _connect(cam_out, _pin(cam_loc, "self"))
    cam_rot = keep(_at(_node(ed, FN_CAM_ROT), x0 + 240, y0 + 700))
    _connect(cam_out, _pin(cam_rot, "self"))
    fwd = keep(_at(_node(ed, FN_FORWARD), x0 + 460, y0 + 700))
    _connect(_pin(cam_rot, "ReturnValue", is_input=False), _pin(fwd, "InRot"))

    rng_pin, rng_n = _prop(ed, "WeaponRange", held, x0 + 460, y0 + 840)
    keep(rng_n)
    far = keep(_at(_node(ed, FN_MUL_VF), x0 + 700, y0 + 700))
    _connect(_pin(fwd, "ReturnValue", is_input=False), _pin(far, "A"))
    _connect(rng_pin, _pin(far, "B"))
    aim = keep(_at(_node(ed, FN_ADD_VV), x0 + 940, y0 + 620))
    _connect(_pin(cam_loc, "ReturnValue", is_input=False), _pin(aim, "A"))
    _connect(_pin(far, "ReturnValue", is_input=False), _pin(aim, "B"))
    delta = keep(_at(_node(ed, FN_SUB_VV), x0 + 1180, y0 + 560))
    _connect(_pin(aim, "ReturnValue", is_input=False), _pin(delta, "A"))
    _connect(muzzle, _pin(delta, "B"))
    direction_n = keep(_at(_node(ed, FN_NORMAL), x0 + 1420, y0 + 560))
    _connect(_pin(delta, "ReturnValue", is_input=False), _pin(direction_n, "A"))
    direction = _pin(direction_n, "ReturnValue", is_input=False)

    snd_pin, snd_n = _prop(ed, "FireSound", held, x0 + 240, y0 + 140)
    keep(snd_n)
    play = keep(_at(_node(ed, FN_PLAY_SOUND), x0 + 520, y0))
    _connect(snd_pin, _pin(play, "Sound"))
    _connect(muzzle, _pin(play, "Location"))
    _connect(exec_in, _pin(play, "execute"))

    pel_pin, pel_n = _prop(ed, "PelletCount", held, x0 + 760, y0 + 180)
    keep(pel_n)
    last = keep(_at(_node(ed, FN_SUB_II), x0 + 980, y0 + 180))
    _connect(pel_pin, _pin(last, "A"))
    _set(last, "B", 1)

    loop = ed.add_macro_node(MACRO_FOR_LOOP)
    if not loop:
        raise RuntimeError("could not create the ForLoop macro node")
    keep(_at(loop, x0 + 1240, y0))
    _loose_pin(loop, "FirstIndex").set_pin_value("0")
    _connect(_pin(last, "ReturnValue", is_input=False), _loose_pin(loop, "LastIndex"))
    _connect(BEL.find_then_pin(play), _loose_pin(loop, "execute"))

    spread_pin, spread_n = _prop(ed, "SpreadDegrees", held, x0 + 1420, y0 + 840)
    keep(spread_n)
    rad = keep(_at(_node(ed, FN_DEG2RAD), x0 + 1660, y0 + 840))
    _connect(spread_pin, _pin(rad, "A"))

    cone = keep(_at(_node(ed, FN_RAND_CONE), x0 + 1900, y0 + 620))
    _connect(direction, _pin(cone, "ConeDir"))
    _connect(_pin(rad, "ReturnValue", is_input=False),
             _pin(cone, "ConeHalfAngleInRadians"))
    reach = keep(_at(_node(ed, FN_MUL_VF), x0 + 2140, y0 + 620))
    _connect(_pin(cone, "ReturnValue", is_input=False), _pin(reach, "A"))
    _connect(rng_pin, _pin(reach, "B"))
    end = keep(_at(_node(ed, FN_ADD_VV), x0 + 2380, y0 + 560))
    _connect(muzzle, _pin(end, "A"))
    _connect(_pin(reach, "ReturnValue", is_input=False), _pin(end, "B"))

    trace = keep(_at(_node(ed, FN_TRACE), x0 + 2620, y0))
    _connect(muzzle, _pin(trace, "Start"))
    _connect(_pin(end, "ReturnValue", is_input=False), _pin(trace, "End"))
    _set(trace, "TraceChannel", "TraceTypeQuery1")   # Visibility
    _set(trace, "bTraceComplex", "false")
    # Ignores the pawn this component hangs off. The weapon actor is separate
    # and *not* ignored, but every one of its parts is NoCollision, so a pellet
    # cannot hit the gun it came out of.
    _set(trace, "bIgnoreSelf", "true")
    if TRACE_DEBUG_SECONDS > 0:
        _set(trace, "DrawDebugType", "ForDuration")
        _set(trace, "DrawTime", TRACE_DEBUG_SECONDS)
    else:
        _set(trace, "DrawDebugType", "None")
    _connect(_loose_pin(loop, "LoopBody", is_input=False), _pin(trace, "execute"))

    hit = keep(_at(ed.add_branch_node(), x0 + 2900, y0))
    _connect(_pin(trace, "ReturnValue", is_input=False), _pin(hit, "Condition"))
    _connect(BEL.find_then_pin(trace), _pin(hit, "execute"))
    brk = keep(_at(_palette(ed, NODE_BREAK_HIT), x0 + 2900, y0 + 300))
    _connect(_pin(trace, "OutHit", is_input=False), _loose_pin(brk, "Hit"))

    ed.add_comment_to_nodes(
        "Fire: the cone's origin is the muzzle (MuzzleOffset through the "
        "weapon's transform) and only its direction comes from the camera. "
        "Tracing from the camera instead -- the usual third-person shortcut -- "
        "is what made the spread appear to come from behind the player.",
        made)

    _author_impact(ed, brk, held, BEL.find_then_pin(hit), x0 + 3180, y0)
    return _loose_pin(loop, "Completed", is_input=False)


def _author_impact(ed, brk, held, exec_in, x0, y0):
    """A pellet that hit something: blood, then subtract the damage.

    Both are behind the health cast, so trees and terrain cost nothing and
    produce no blood -- only things carrying BP_HealthComponent bleed.
    """
    comp = _at(_node(ed, FN_GET_COMP), x0, y0 + 260)
    _connect(_loose_pin(brk, "HitActor", is_input=False), _pin(comp, "self"))
    _pin(comp, "ComponentClass").set_pin_value(HEALTH_CLASS_PATH)

    cast = _at(_palette(ed, NODE_CAST_HEALTH), x0 + 260, y0)
    _connect(_pin(comp, "ReturnValue", is_input=False), _pin(cast, "Object"))
    _connect(exec_in, _pin(cast, "execute"))
    as_health = _loose_pin(cast, "AsBPHealthComponent", is_input=False)

    blood_cls = _at(ed.add_get_member_variable_node("BloodClass"), x0 + 520, y0 + 520)
    where = _at(_node(ed, FN_MAKE_TRANSFORM), x0 + 520, y0 + 380)
    _connect(_loose_pin(brk, "Location", is_input=False), _pin(where, "Location"))
    _connect(_vec(ed, 1.0, 1.0, 1.0, x0 + 260, y0 + 520), _pin(where, "Scale"))
    splash = _at(_palette(ed, NODE_SPAWN), x0 + 800, y0)
    _connect(_pin(blood_cls, "BloodClass", is_input=False), _pin(splash, "Class"))
    _connect(_pin(where, "ReturnValue", is_input=False), _pin(splash, "SpawnTransform"))
    _set(splash, "CollisionHandlingOverride", "AlwaysSpawn")
    _connect(BEL.find_then_pin(cast), _pin(splash, "execute"))

    get_h = _at(ed.add_get_member_variable_node("Health", HEALTH_CLASS_PATH),
                x0 + 1080, y0 + 300)
    _connect(as_health, _pin(get_h, "self"))
    dmg_pin, dmg_n = _prop(ed, "Damage", held, x0 + 1080, y0 + 440)
    sub = _at(_node(ed, FN_SUB_FF), x0 + 1320, y0 + 300)
    _connect(_pin(get_h, "Health", is_input=False), _pin(sub, "A"))
    _connect(dmg_pin, _pin(sub, "B"))
    clamp = _at(_node(ed, FN_CLAMP), x0 + 1560, y0 + 300)
    _connect(_pin(sub, "ReturnValue", is_input=False), _pin(clamp, "Value"))
    _set(clamp, "Min", 0.0)
    _set(clamp, "Max", INF)
    set_h = _at(ed.add_set_member_variable_node("Health", HEALTH_CLASS_PATH),
                x0 + 1820, y0)
    _connect(as_health, _pin(set_h, "self"))
    _connect(_pin(clamp, "ReturnValue", is_input=False), _pin(set_h, "Health"))
    _connect(BEL.find_then_pin(splash), _pin(set_h, "execute"))

    ed.add_comment_to_nodes(
        "Clamped at zero so an overkill shot cannot drive Health negative -- "
        "the HUD bar divides by MaxHealth and the death check is Health <= 0, "
        "and both want a floor.",
        [comp, cast, blood_cls, where, splash, get_h, dmg_n, sub, clamp, set_h])


def _detach_rules(node):
    # KeepWorld everywhere: a dropped weapon should stay exactly where it was in
    # world space and then be moved deliberately, not snap back to the origin.
    for rule in ("LocationRule", "RotationRule", "ScaleRule"):
        _set(node, rule, "KeepWorld")


def _author_drop(ed, held, owner, exec_in, x0, y0):
    """Detach the held weapon, drop it on the ground in front of the player."""
    made = []

    def keep(n):
        made.append(n)
        return n

    flag = keep(_at(ed.add_set_member_variable_node("Dropped", ITEM_CLASS_PATH), x0, y0))
    _connect(held, _pin(flag, "self"))
    _set(flag, "Dropped", "true")
    _connect(exec_in, _pin(flag, "execute"))

    off = keep(_at(_node(ed, FN_DETACH), x0 + 280, y0))
    _connect(held, _pin(off, "self"))
    _detach_rules(off)
    _connect(BEL.find_then_pin(flag), _pin(off, "execute"))

    loc = keep(_at(_node(ed, FN_ACTOR_LOC), x0, y0 + 300))
    _connect(owner, _pin(loc, "self"))
    rot = keep(_at(_node(ed, "/Script/Engine.Actor.K2_GetActorRotation"), x0, y0 + 420))
    _connect(owner, _pin(rot, "self"))
    fwd = keep(_at(_node(ed, FN_FORWARD), x0 + 240, y0 + 420))
    _connect(_pin(rot, "ReturnValue", is_input=False), _pin(fwd, "InRot"))
    ahead = keep(_at(_node(ed, FN_MUL_VF), x0 + 480, y0 + 420))
    _connect(_pin(fwd, "ReturnValue", is_input=False), _pin(ahead, "A"))
    _set(ahead, "B", DROP_FORWARD)
    start = keep(_at(_node(ed, FN_ADD_VV), x0 + 720, y0 + 340))
    _connect(_pin(loc, "ReturnValue", is_input=False), _pin(start, "A"))
    _connect(_pin(ahead, "ReturnValue", is_input=False), _pin(start, "B"))

    down = keep(_at(_node(ed, FN_ADD_VV), x0 + 960, y0 + 460))
    _connect(_pin(start, "ReturnValue", is_input=False), _pin(down, "A"))
    _connect(_vec(ed, 0.0, 0.0, -400.0, x0 + 720, y0 + 580), _pin(down, "B"))

    # Trace down so the weapon lands on the terrain instead of hanging at hip
    # height. The forest floor is a mesh, not a plane, so a fixed Z would float
    # or bury it depending on where the player is standing.
    ground = keep(_at(_node(ed, FN_TRACE), x0 + 1220, y0))
    _connect(_pin(start, "ReturnValue", is_input=False), _pin(ground, "Start"))
    _connect(_pin(down, "ReturnValue", is_input=False), _pin(ground, "End"))
    _set(ground, "TraceChannel", "TraceTypeQuery1")
    _set(ground, "bTraceComplex", "false")
    _set(ground, "bIgnoreSelf", "true")
    _set(ground, "DrawDebugType", "None")
    _connect(BEL.find_then_pin(off), _pin(ground, "execute"))

    landed = keep(_at(ed.add_branch_node(), x0 + 1500, y0))
    _connect(_pin(ground, "ReturnValue", is_input=False), _pin(landed, "Condition"))
    _connect(BEL.find_then_pin(ground), _pin(landed, "execute"))
    brk = keep(_at(_palette(ed, NODE_BREAK_HIT), x0 + 1500, y0 + 300))
    _connect(_pin(ground, "OutHit", is_input=False), _loose_pin(brk, "Hit"))

    lift = keep(_at(_node(ed, FN_ADD_VV), x0 + 1760, y0 + 300))
    _connect(_loose_pin(brk, "Location", is_input=False), _pin(lift, "A"))
    _connect(_vec(ed, 0.0, 0.0, 12.0, x0 + 1520, y0 + 440), _pin(lift, "B"))

    on_ground = keep(_at(_node(ed, FN_SET_ACTOR_LOC), x0 + 2020, y0 - 120))
    _connect(held, _pin(on_ground, "self"))
    _connect(_pin(lift, "ReturnValue", is_input=False), _pin(on_ground, "NewLocation"))
    _connect(BEL.find_then_pin(landed), _pin(on_ground, "execute"))

    in_air = keep(_at(_node(ed, FN_SET_ACTOR_LOC), x0 + 2020, y0 + 120))
    _connect(held, _pin(in_air, "self"))
    _connect(_pin(start, "ReturnValue", is_input=False), _pin(in_air, "NewLocation"))
    _connect(BEL.find_else_pin(landed), _pin(in_air, "execute"))

    # Both placements rejoin here; an exec input takes more than one link.
    inv = keep(_at(ed.add_get_member_variable_node("Inventory"), x0 + 2300, y0 + 240))
    idx = keep(_at(ed.add_get_member_variable_node("EquippedIndex"), x0 + 2300, y0 + 360))
    remove = keep(_at(_node(ed, FN_ARR_REMOVE), x0 + 2540, y0))
    _connect(_pin(inv, "Inventory", is_input=False), _pin(remove, "TargetArray"))
    _connect(_pin(idx, "EquippedIndex", is_input=False), _pin(remove, "IndexToRemove"))
    _connect(BEL.find_then_pin(on_ground), _pin(remove, "execute"))
    _connect(BEL.find_then_pin(in_air), _pin(remove, "execute"))

    # Held is set with its input pin left unconnected, which is how a Blueprint
    # object variable is cleared to None.
    clear = keep(_at(ed.add_set_member_variable_node("Held"), x0 + 2800, y0))
    _connect(BEL.find_then_pin(remove), _pin(clear, "execute"))
    reset = keep(_at(ed.add_set_member_variable_node("EquippedIndex"), x0 + 3060, y0))
    _set(reset, "EquippedIndex", 0)
    _connect(BEL.find_then_pin(clear), _pin(reset, "execute"))

    ed.add_comment_to_nodes(
        f"{DROP_KEY} drops the equipped weapon {DROP_FORWARD:.0f} cm ahead, "
        "traced down onto the terrain, and takes it out of Inventory. It stays "
        "in the world as an ordinary actor with Dropped set, which is the only "
        "thing pick-up looks for.",
        made)
    return BEL.find_then_pin(reset)


def _author_pickup(ed, owner, exec_in, x0, y0):
    """E: take the nearest dropped weapon, if there is room for it."""
    made = []

    def keep(n):
        made.append(n)
        return n

    cls = keep(_at(ed.add_get_member_variable_node("ItemClass"), x0, y0 + 240))
    every = keep(_at(_node(ed, FN_ALL_ACTORS), x0 + 240, y0))
    _connect(_pin(cls, "ItemClass", is_input=False), _pin(every, "ActorClass"))
    _connect(exec_in, _pin(every, "execute"))

    loop = ed.add_macro_node(MACRO_FOR_EACH)
    if not loop:
        raise RuntimeError("could not create the ForEachLoop macro node")
    keep(_at(loop, x0 + 520, y0))
    _connect(_pin(every, "OutActors", is_input=False), _loose_pin(loop, "Array"))
    _connect(BEL.find_then_pin(every), _loose_pin(loop, "Exec"))
    element = _loose_pin(loop, "ArrayElement", is_input=False)

    cast = keep(_at(_palette(ed, "Utilities|Casting|CastToBP_WeaponItem"), x0 + 820, y0))
    _connect(element, _pin(cast, "Object"))
    _connect(_loose_pin(loop, "LoopBody", is_input=False), _pin(cast, "execute"))
    item = _loose_pin(cast, "AsBPWeaponItem", is_input=False)

    dropped_pin, dropped_n = _prop(ed, "Dropped", item, x0 + 1100, y0 + 260)
    keep(dropped_n)

    there = keep(_at(_node(ed, FN_ACTOR_LOC), x0 + 1100, y0 + 400))
    _connect(item, _pin(there, "self"))
    here = keep(_at(_node(ed, FN_ACTOR_LOC), x0 + 1100, y0 + 520))
    _connect(owner, _pin(here, "self"))
    gap = keep(_at(_node(ed, FN_DISTANCE), x0 + 1360, y0 + 440))
    _connect(_pin(there, "ReturnValue", is_input=False), _pin(gap, "V1"))
    _connect(_pin(here, "ReturnValue", is_input=False), _pin(gap, "V2"))
    near = keep(_at(_node(ed, FN_LESS_FF), x0 + 1600, y0 + 440))
    _connect(_pin(gap, "ReturnValue", is_input=False), _pin(near, "A"))
    _set(near, "B", PICKUP_RADIUS)

    inv = keep(_at(ed.add_get_member_variable_node("Inventory"), x0 + 1100, y0 + 660))
    count = keep(_at(_node(ed, FN_ARR_LEN), x0 + 1360, y0 + 660))
    _connect(_pin(inv, "Inventory", is_input=False), _pin(count, "TargetArray"))
    room = keep(_at(_node(ed, FN_LESS_II), x0 + 1600, y0 + 660))
    _connect(_pin(count, "ReturnValue", is_input=False), _pin(room, "A"))
    _set(room, "B", INVENTORY_SIZE)

    # The room check is inside the loop, not before it: without it a player
    # standing on a pile would pick up every weapon at once and overflow the
    # five slots the HUD draws.
    and1 = keep(_at(_node(ed, FN_AND), x0 + 1840, y0 + 340))
    _connect(dropped_pin, _pin(and1, "A"))
    _connect(_pin(near, "ReturnValue", is_input=False), _pin(and1, "B"))
    and2 = keep(_at(_node(ed, FN_AND), x0 + 2080, y0 + 420))
    _connect(_pin(and1, "ReturnValue", is_input=False), _pin(and2, "A"))
    _connect(_pin(room, "ReturnValue", is_input=False), _pin(and2, "B"))

    take = keep(_at(ed.add_branch_node(), x0 + 2320, y0))
    _connect(_pin(and2, "ReturnValue", is_input=False), _pin(take, "Condition"))
    _connect(BEL.find_then_pin(cast), _pin(take, "execute"))

    clear = keep(_at(ed.add_set_member_variable_node("Dropped", ITEM_CLASS_PATH),
                     x0 + 2580, y0))
    _connect(item, _pin(clear, "self"))
    _set(clear, "Dropped", "false")
    _connect(BEL.find_then_pin(take), _pin(clear, "execute"))

    inv2 = keep(_at(ed.add_get_member_variable_node("Inventory"), x0 + 2580, y0 + 300))
    add = keep(_at(_node(ed, FN_ARR_ADD), x0 + 2840, y0))
    _connect(_pin(inv2, "Inventory", is_input=False), _pin(add, "TargetArray"))
    _connect(item, _pin(add, "NewItem"))
    _connect(BEL.find_then_pin(clear), _pin(add, "execute"))

    # Equip what was just picked up: its index is the new last one.
    at = keep(_at(ed.add_set_member_variable_node("EquippedIndex"), x0 + 3100, y0))
    _connect(_pin(add, "ReturnValue", is_input=False), _pin(at, "EquippedIndex"))
    _connect(BEL.find_then_pin(add), _pin(at, "execute"))

    ed.add_comment_to_nodes(
        f"{PICKUP_KEY} picks up any weapon within {PICKUP_RADIUS:.0f} cm that is "
        f"flagged Dropped, while fewer than {INVENTORY_SIZE} are carried, and "
        "equips it. Array_Add returns the new item's index, which is exactly "
        "the slot to switch to.",
        made)
    return _loose_pin(loop, "Completed", is_input=False)


def _author_equip(ed, exec_in, x0, y0):
    """Show exactly one weapon in the hand, hide the rest, play its ready pose.

    Weapons are spawned once and kept: equipping hides and shows actors rather
    than destroying and respawning them, so a weapon keeps its identity (and
    could keep its ammo, condition, anything) across switches, and so dropping
    can hand the very same actor to the world.
    """
    made = []

    def keep(n):
        made.append(n)
        return n

    inv = keep(_at(ed.add_get_member_variable_node("Inventory"), x0, y0 + 240))
    loop = ed.add_macro_node(MACRO_FOR_EACH)
    if not loop:
        raise RuntimeError("could not create the ForEachLoop macro node")
    keep(_at(loop, x0 + 260, y0))
    _connect(_pin(inv, "Inventory", is_input=False), _loose_pin(loop, "Array"))
    _connect(exec_in, _loose_pin(loop, "Exec"))
    item = _loose_pin(loop, "ArrayElement", is_input=False)

    idx = keep(_at(ed.add_get_member_variable_node("EquippedIndex"), x0 + 560, y0 + 320))
    same = keep(_at(_node(ed, FN_EQ_II), x0 + 800, y0 + 260))
    _connect(_loose_pin(loop, "ArrayIndex", is_input=False), _pin(same, "A"))
    _connect(_pin(idx, "EquippedIndex", is_input=False), _pin(same, "B"))

    chosen = keep(_at(ed.add_branch_node(), x0 + 1040, y0))
    _connect(_pin(same, "ReturnValue", is_input=False), _pin(chosen, "Condition"))
    _connect(_loose_pin(loop, "LoopBody", is_input=False), _pin(chosen, "execute"))

    show = keep(_at(_node(ed, FN_SET_HIDDEN), x0 + 1300, y0 - 160))
    _connect(item, _pin(show, "self"))
    _set(show, "bNewHidden", "false")
    _connect(BEL.find_then_pin(chosen), _pin(show, "execute"))

    hide = keep(_at(_node(ed, FN_SET_HIDDEN), x0 + 1300, y0 + 420))
    _connect(item, _pin(hide, "self"))
    _set(hide, "bNewHidden", "true")
    _connect(BEL.find_else_pin(chosen), _pin(hide, "execute"))

    mesh = keep(_at(ed.add_get_member_variable_node("OwnerMesh"), x0 + 1300, y0 + 40))
    attach = keep(_at(_node(ed, FN_ATTACH), x0 + 1580, y0 - 160))
    _connect(item, _pin(attach, "self"))
    _connect(_pin(mesh, "OwnerMesh", is_input=False), _pin(attach, "Parent"))
    _set(attach, "SocketName", GRIP_SOCKET)
    # Snap first, then apply the weapon's own grip offset explicitly. Snapping
    # gives a known starting transform; KeepRelative would carry over whatever
    # the actor happened to be at, which after a drop is a world position.
    for rule in ("LocationRule", "RotationRule", "ScaleRule"):
        _set(attach, rule, "SnapToTarget")
    _connect(BEL.find_then_pin(show), _pin(attach, "execute"))

    gl_pin, gl_n = _prop(ed, "GripLocation", item, x0 + 1580, y0 + 120)
    keep(gl_n)
    put = keep(_at(_node(ed, FN_SET_REL_LOC), x0 + 1860, y0 - 160))
    _connect(item, _pin(put, "self"))
    _connect(gl_pin, _pin(put, "NewRelativeLocation"))
    _connect(BEL.find_then_pin(attach), _pin(put, "execute"))

    gr_pin, gr_n = _prop(ed, "GripRotation", item, x0 + 1860, y0 + 120)
    keep(gr_n)
    turn = keep(_at(_node(ed, FN_SET_REL_ROT), x0 + 2140, y0 - 160))
    _connect(item, _pin(turn, "self"))
    _connect(gr_pin, _pin(turn, "NewRelativeRotation"))
    _connect(BEL.find_then_pin(put), _pin(turn, "execute"))

    hold = keep(_at(ed.add_set_member_variable_node("Held"), x0 + 2420, y0 - 160))
    _connect(item, _pin(hold, "Held"))
    _connect(BEL.find_then_pin(turn), _pin(hold, "execute"))

    # --- once the loop is done, drive the ready pose -------------------------
    held_get = keep(_at(ed.add_get_member_variable_node("Held"), x0 + 2700, y0 + 300))
    held = _pin(held_get, "Held", is_input=False)
    armed = keep(_at(_node(ed, FN_IS_VALID), x0 + 2940, y0 + 300))
    _connect(held, _pin(armed, "Object"))
    posing = keep(_at(ed.add_branch_node(), x0 + 3180, y0))
    _connect(_pin(armed, "ReturnValue", is_input=False), _pin(posing, "Condition"))
    _connect(_loose_pin(loop, "Completed", is_input=False), _pin(posing, "execute"))

    mesh2 = keep(_at(ed.add_get_member_variable_node("OwnerMesh"), x0 + 3180, y0 + 440))
    anim = keep(_at(_node(ed, FN_ANIM_INSTANCE), x0 + 3420, y0 + 440))
    _connect(_pin(mesh2, "OwnerMesh", is_input=False), _pin(anim, "self"))
    anim_out = _pin(anim, "ReturnValue", is_input=False)

    pose_pin, pose_n = _prop(ed, "AimPose", held, x0 + 3420, y0 + 200)
    keep(pose_n)
    play = keep(_at(_node(ed, FN_PLAY_SLOT), x0 + 3700, y0 - 100))
    _connect(anim_out, _pin(play, "self"))
    _connect(pose_pin, _pin(play, "Asset"))
    _set(play, "SlotNodeName", AIM_SLOT)
    _set(play, "BlendInTime", AIM_BLEND)
    _set(play, "BlendOutTime", AIM_BLEND)
    _set(play, "InPlayRate", 1.0)
    _set(play, "LoopCount", AIM_LOOPS)
    _connect(BEL.find_then_pin(posing), _pin(play, "execute"))

    stop = keep(_at(_node(ed, FN_STOP_SLOT), x0 + 3700, y0 + 200))
    _connect(anim_out, _pin(stop, "self"))
    _set(stop, "InBlendOutTime", AIM_BLEND)
    _set(stop, "SlotNodeName", AIM_SLOT)
    _connect(BEL.find_else_pin(posing), _pin(stop, "execute"))

    ed.add_comment_to_nodes(
        f"The ready pose is the weapon's own AimPose played into {AIM_SLOT}, "
        f"looping {AIM_LOOPS} times because PlaySlotAnimationAsDynamicMontage "
        "has no infinite option. It reads as a pose rather than a full-body "
        "animation only because patch_anim_blueprint() put a spine_01 layered "
        "blend around that slot in ABP_Unarmed -- without it the legs would "
        "freeze mid-stride. Empty hands stop the slot and locomotion returns.",
        made)


def _author_wc_begin_play(ed, begin):
    """Cache the character's mesh, spawn the starting loadout, equip slot 0."""
    made = []

    def keep(n):
        made.append(n)
        return n

    owner = keep(_at(_node(ed, FN_GET_OWNER), 240, -1060))
    cast = keep(_at(_palette(ed, NODE_CAST_CHAR), 500, -1200))
    _connect(_pin(owner, "ReturnValue", is_input=False), _pin(cast, "Object"))
    _connect(BEL.find_then_pin(begin), _pin(cast, "execute"))
    as_char = _loose_pin(cast, "AsBPThirdPersonCharacter", is_input=False)

    mesh = keep(_at(ed.add_get_member_variable_node("Mesh", "/Script/Engine.Character"),
                    780, -1020))
    _connect(as_char, _pin(mesh, "self"))
    remember = keep(_at(ed.add_set_member_variable_node("OwnerMesh"), 1040, -1200))
    _connect(_pin(mesh, "Mesh", is_input=False), _pin(remember, "OwnerMesh"))
    _connect(BEL.find_then_pin(cast), _pin(remember, "execute"))

    where = keep(_at(_node(ed, FN_GET_TRANSFORM), 1040, -1000))
    _connect(as_char, _pin(where, "self"))
    spawn_at = _pin(where, "ReturnValue", is_input=False)

    prev = BEL.find_then_pin(remember)
    for i, var in enumerate(("ShotgunClass", "PistolClass")):
        cls = keep(_at(ed.add_get_member_variable_node(var), 1300, -1020 + i * 460))
        spawn = keep(_at(_palette(ed, NODE_SPAWN), 1560, -1200 + i * 460))
        _connect(_pin(cls, var, is_input=False), _pin(spawn, "Class"))
        _connect(spawn_at, _pin(spawn, "SpawnTransform"))
        _set(spawn, "CollisionHandlingOverride", "AlwaysSpawn")
        _connect(prev, _pin(spawn, "execute"))

        inv = keep(_at(ed.add_get_member_variable_node("Inventory"),
                       1840, -1000 + i * 460))
        add = keep(_at(_node(ed, FN_ARR_ADD), 2100, -1200 + i * 460))
        _connect(_pin(inv, "Inventory", is_input=False), _pin(add, "TargetArray"))
        _connect(_pin(spawn, "ReturnValue", is_input=False), _pin(add, "NewItem"))
        _connect(BEL.find_then_pin(spawn), _pin(add, "execute"))
        prev = BEL.find_then_pin(add)

    first = keep(_at(ed.add_set_member_variable_node("EquippedIndex"), 2400, -1200))
    _set(first, "EquippedIndex", 0)
    _connect(prev, _pin(first, "execute"))
    dirty = keep(_at(ed.add_set_member_variable_node("NeedsRefresh"), 2660, -1200))
    _set(dirty, "NeedsRefresh", "true")
    _connect(BEL.find_then_pin(first), _pin(dirty, "execute"))

    ed.add_comment_to_nodes(
        "The player starts carrying both weapons. They are spawned here rather "
        "than placed in the level so that a generated map needs no weapon "
        "actors in it -- nothing in Scripts/generated_levels knows weapons "
        "exist. NeedsRefresh makes Tick do the actual equipping, so the attach "
        "logic is authored exactly once.",
        made)


def _author_wc_tick(ed, tick):
    """Four polled keys and a refresh, chained so each block rejoins the next.

    There is no Sequence node here: an exec *input* accepts any number of links,
    so every block's exit and its guard branch's False pin both run into the
    next guard. That keeps the chain flat and means a block can be inserted or
    removed without re-fanning a Sequence's pins.

    Refresh runs last so a switch, drop or pick-up earlier in the same frame is
    already applied when it does.
    """
    pc = _at(_node(ed, FN_GET_PC), 240, 260)
    _set(pc, "PlayerIndex", 0)
    pc_out = _pin(pc, "ReturnValue", is_input=False)

    owner = _at(_node(ed, FN_GET_OWNER), 240, 400)
    owner_out = _pin(owner, "ReturnValue", is_input=False)

    held_get = _at(ed.add_get_member_variable_node("Held"), 240, 520)
    held = _pin(held_get, "Held", is_input=False)
    armed = _at(_node(ed, FN_IS_VALID), 480, 520)
    _connect(held, _pin(armed, "Object"))
    armed_out = _pin(armed, "ReturnValue", is_input=False)

    def pressed(key, y):
        n = _at(_node(ed, FN_WAS_PRESSED), 480, y)
        _connect(pc_out, _pin(n, "self"))
        # Bare key name, never struct text: FKey exports as just its name, so
        # '(KeyName="Q")' would import back as a key literally called "(".
        _set(n, "Key", key)
        return _pin(n, "ReturnValue", is_input=False)

    def both(a, b, y):
        n = _at(_node(ed, FN_AND), 760, y)
        _connect(a, _pin(n, "A"))
        _connect(b, _pin(n, "B"))
        return _pin(n, "ReturnValue", is_input=False)

    # --- fire ----------------------------------------------------------------
    fire_gate = _at(ed.add_branch_node(), 1040, 0)
    _connect(both(pressed(FIRE_KEY, 640), armed_out, 640), _pin(fire_gate, "Condition"))
    _connect(BEL.find_then_pin(tick), _pin(fire_gate, "execute"))
    after_fire = _author_fire(ed, held, owner_out, BEL.find_then_pin(fire_gate),
                              1400, 0)

    # --- switch --------------------------------------------------------------
    switch_gate = _at(ed.add_branch_node(), 1040, 1400)
    inv = _at(ed.add_get_member_variable_node("Inventory"), 240, 1560)
    count = _at(_node(ed, FN_ARR_LEN), 480, 1560)
    _connect(_pin(inv, "Inventory", is_input=False), _pin(count, "TargetArray"))
    count_out = _pin(count, "ReturnValue", is_input=False)
    any_held = _at(_node(ed, FN_LESS_II), 760, 1680)
    _set(any_held, "A", 0)
    _connect(count_out, _pin(any_held, "B"))
    _connect(both(pressed(SWITCH_KEY, 1560), _pin(any_held, "ReturnValue", is_input=False),
                  1620), _pin(switch_gate, "Condition"))
    _connect(after_fire, _pin(switch_gate, "execute"))
    _connect(BEL.find_else_pin(fire_gate), _pin(switch_gate, "execute"))

    idx = _at(ed.add_get_member_variable_node("EquippedIndex"), 1300, 1600)
    step = _at(_node(ed, FN_ADD_II), 1540, 1600)
    _connect(_pin(idx, "EquippedIndex", is_input=False), _pin(step, "A"))
    _set(step, "B", 1)
    wrap = _at(_node(ed, FN_MOD_II), 1780, 1600)
    _connect(_pin(step, "ReturnValue", is_input=False), _pin(wrap, "A"))
    _connect(count_out, _pin(wrap, "B"))
    to = _at(ed.add_set_member_variable_node("EquippedIndex"), 2020, 1400)
    _connect(_pin(wrap, "ReturnValue", is_input=False), _pin(to, "EquippedIndex"))
    _connect(BEL.find_then_pin(switch_gate), _pin(to, "execute"))
    switch_dirty = _at(ed.add_set_member_variable_node("NeedsRefresh"), 2280, 1400)
    _set(switch_dirty, "NeedsRefresh", "true")
    _connect(BEL.find_then_pin(to), _pin(switch_dirty, "execute"))

    ed.add_comment_to_nodes(
        f"{SWITCH_KEY} cycles: (index + 1) mod count, so it wraps and works for "
        "any number of carried weapons. 1/2/3 and M would have been the obvious "
        "keys but they already belong to the graphics menu.",
        [inv, count, any_held, idx, step, wrap, to, switch_dirty, switch_gate])

    # --- drop ----------------------------------------------------------------
    drop_gate = _at(ed.add_branch_node(), 1040, 2200)
    _connect(both(pressed(DROP_KEY, 2360), armed_out, 2300), _pin(drop_gate, "Condition"))
    _connect(BEL.find_then_pin(switch_dirty), _pin(drop_gate, "execute"))
    _connect(BEL.find_else_pin(switch_gate), _pin(drop_gate, "execute"))
    after_drop = _author_drop(ed, held, owner_out, BEL.find_then_pin(drop_gate),
                              1400, 2200)
    drop_dirty = _at(ed.add_set_member_variable_node("NeedsRefresh"), 4700, 2200)
    _set(drop_dirty, "NeedsRefresh", "true")
    _connect(after_drop, _pin(drop_dirty, "execute"))

    # --- pick up -------------------------------------------------------------
    pick_gate = _at(ed.add_branch_node(), 1040, 3400)
    _connect(pressed(PICKUP_KEY, 3560), _pin(pick_gate, "Condition"))
    _connect(BEL.find_then_pin(drop_dirty), _pin(pick_gate, "execute"))
    _connect(BEL.find_else_pin(drop_gate), _pin(pick_gate, "execute"))
    after_pick = _author_pickup(ed, owner_out, BEL.find_then_pin(pick_gate),
                                1400, 3400)
    pick_dirty = _at(ed.add_set_member_variable_node("NeedsRefresh"), 4900, 3400)
    _set(pick_dirty, "NeedsRefresh", "true")
    _connect(after_pick, _pin(pick_dirty, "execute"))

    # --- refresh -------------------------------------------------------------
    dirty_get = _at(ed.add_get_member_variable_node("NeedsRefresh"), 1040, 4760)
    refresh_gate = _at(ed.add_branch_node(), 1300, 4600)
    _connect(_pin(dirty_get, "NeedsRefresh", is_input=False),
             _pin(refresh_gate, "Condition"))
    _connect(BEL.find_then_pin(pick_dirty), _pin(refresh_gate, "execute"))
    _connect(BEL.find_else_pin(pick_gate), _pin(refresh_gate, "execute"))
    settle = _at(ed.add_set_member_variable_node("NeedsRefresh"), 1560, 4600)
    _set(settle, "NeedsRefresh", "false")
    _connect(BEL.find_then_pin(refresh_gate), _pin(settle, "execute"))
    _author_equip(ed, BEL.find_then_pin(settle), 1900, 4600)


def build_weapon_component(item_bp, shotgun_bp, pistol_bp, blood_bp, rebuild=True):
    # Cast nodes only appear in the palette for classes that are already loaded,
    # and this graph casts to all three. Without these loads
    # create_node_from_name returns None and the failure reads as a typo in the
    # node name rather than as a missing asset.
    for path in (CHARACTER_BP_PATH, ITEM_BP_PATH, HEALTH_BP_PATH):
        if not _assets().load_asset(path):
            raise RuntimeError(f"could not load {path} for its cast node")

    bp = _create_blueprint(WEAPON_COMP_BP_PATH, unreal.ActorComponent)
    ed = BGE.get_graph_editor_by_name(bp, "EventGraph")
    tick, begin = _events(ed, rebuild)

    item_class = BEL.generated_class(item_bp)
    _declare(ed, "Inventory",
             BEL.get_array_type(BEL.get_object_reference_type(item_class)))
    _declare(ed, "Held", BEL.get_object_reference_type(item_class))
    _declare(ed, "EquippedIndex", BEL.get_basic_type_by_name("int"))
    _declare(ed, "NeedsRefresh", BEL.get_basic_type_by_name("bool"))
    _declare(ed, "OwnerMesh", BEL.get_object_reference_type(
        unreal.SkeletalMeshComponent.static_class()))
    # Typed as "class of BP_WeaponItem", not "class of Actor": SpawnActor's
    # return pin takes its type from its Class pin, and an Actor-typed return
    # cannot be added to an array of BP_WeaponItem.
    for name in ("ShotgunClass", "PistolClass", "ItemClass"):
        _declare(ed, name, BEL.get_class_reference_type(item_class))
    _declare(ed, "BloodClass",
             BEL.get_class_reference_type(unreal.Actor.static_class()))

    _author_wc_begin_play(ed, begin)
    _author_wc_tick(ed, tick)

    _post_physics_tick(bp)
    if not BEL.compile_blueprint(bp):
        raise RuntimeError("BP_WeaponComponent failed to compile")
    _apply_defaults(bp, {
        "EquippedIndex": 0,
        "NeedsRefresh": True,
        "ShotgunClass": BEL.generated_class(shotgun_bp),
        "PistolClass": BEL.generated_class(pistol_bp),
        "ItemClass": item_class,
        "BloodClass": BEL.generated_class(blood_bp),
    })
    _log(f"built {WEAPON_COMP_BP_PATH}")
    return bp


# ─── Installing on the characters ────────────────────────────────────────────

OLD_SHOTGUN_PARTS = {"Shotgun", "Receiver", "Barrel", "MagTube", "Pump", "Stock",
                     "Grip", "TriggerGuard", "ShotgunComponent"}
OLD_SHOTGUN_BP = "/Game/Weapons/BP_ShotgunComponent"


def _uninstall_old_shotgun(bp):
    """Strip what build_shotgun_and_health.py welded onto the character.

    The old design hung the weapon's seven primitives off the character's mesh
    directly. Those have to go, or the player carries a second shotgun that no
    longer responds to anything.
    """
    present = {var for _h, var in _handles(bp)} & OLD_SHOTGUN_PARTS
    if present:
        _drop_components(bp, present)
        _log(f"removed the old welded shotgun: {sorted(present)}")


def make_shootable(bp):
    """Let a Visibility trace hit this character's capsule.

    This is the bug that made the NPC unkillable. UE's stock `Pawn` profile sets
    Visibility to **Ignore** (and `CharacterMesh` does too), while the pellets
    trace on TraceTypeQuery1, which *is* Visibility -- so every shot passed
    straight through the NPC and no hit was ever registered. Nothing logs this:
    the trace simply reports no hit, exactly as it would for a genuine miss.

    The capsule alone is made to block, not the skeletal mesh: the capsule is
    guaranteed present and correctly sized, whereas hitting the mesh depends on
    the physics asset's shapes being well fitted. Capsule-only hit detection is
    coarse but predictable.

    Setting a single channel response switches the profile off its preset and
    onto "Custom", which is expected.
    """
    capsule = _find_handle(bp, "CapsuleComponent")
    if not capsule:
        _log(f"note: {bp.get_name()} has no CapsuleComponent — not made shootable")
        return
    obj = _component_object(capsule)
    obj.set_collision_response_to_channel(
        unreal.CollisionChannel.ECC_VISIBILITY, unreal.CollisionResponseType.ECR_BLOCK)
    got = obj.get_collision_response_to_channel(unreal.CollisionChannel.ECC_VISIBILITY)
    if got != unreal.CollisionResponseType.ECR_BLOCK:
        raise RuntimeError(
            f"{bp.get_name()}'s capsule still ignores Visibility ({got}) — "
            "shots would pass through it")
    _log(f"{bp.get_name()}: capsule now blocks Visibility (shootable)")


def install_on_character(health_bp, weapon_bp):
    eas = _assets()
    bp = eas.load_asset(CHARACTER_BP_PATH)
    if not bp:
        raise RuntimeError(f"could not load {CHARACTER_BP_PATH}")
    _uninstall_old_shotgun(bp)
    _drop_components(bp, {"HealthComponent", "WeaponComponent"})
    for name, source in (("HealthComponent", health_bp),
                         ("WeaponComponent", weapon_bp)):
        _add_component(bp, _root_handle(bp), BEL.generated_class(source), name)
    # Symmetry, and forward planning: the player carries health too, so anything
    # that shoots back later needs to be able to hit them.
    make_shootable(bp)
    if not BEL.compile_blueprint(bp):
        raise RuntimeError("BP_ThirdPersonCharacter failed to compile")
    eas.save_loaded_asset(bp)
    _log("player: HealthComponent + WeaponComponent installed")


def install_on_npc(health_bp):
    """The NPC gets health that despawns and respawns it.

    DespawnOnDeath and RespawnClass are set on *this* Blueprint's component
    template rather than on BP_HealthComponent's defaults, which is what keeps
    the same component class usable on the player without the player vanishing
    at 0 HP.
    """
    eas = _assets()
    bp = eas.load_asset(NPC_BP_PATH)
    if not bp:
        _log(f"note: {NPC_BP_PATH} not found — skipping the NPC")
        return None
    _drop_components(bp, {"HealthComponent"})
    handle = _add_component(bp, _root_handle(bp),
                            BEL.generated_class(health_bp), "HealthComponent")
    comp = _component_object(handle)
    comp.set_editor_property("DespawnOnDeath", True)
    comp.set_editor_property("RespawnClass", unreal.load_class(None, NPC_CLASS_PATH))

    # A respawned wanderer is spawned, not placed, so the default
    # "Placed in World" would leave it with no AI controller and no movement.
    cdo = unreal.get_default_object(BEL.generated_class(bp))
    try:
        cdo.set_editor_property(
            "auto_possess_ai", unreal.AutoPossessAI.PLACED_IN_WORLD_OR_SPAWNED)
    except Exception as exc:                                      # noqa: BLE001
        _log(f"note: could not set auto_possess_ai: {exc}")

    make_shootable(bp)

    if not BEL.compile_blueprint(bp):
        raise RuntimeError("BP_ForestWanderer failed to compile")
    eas.save_loaded_asset(bp)
    _log("NPC: HealthComponent installed (despawns and respawns at 0 HP)")
    return bp


def retire_old_assets():
    """Delete BP_ShotgunComponent once nothing references it."""
    eas = _assets()
    if not eas.does_asset_exist(OLD_SHOTGUN_BP):
        return
    try:
        if eas.delete_asset(OLD_SHOTGUN_BP):
            _log(f"deleted the superseded {OLD_SHOTGUN_BP}")
    except Exception as exc:                                      # noqa: BLE001
        _log(f"note: {OLD_SHOTGUN_BP} still referenced, left in place: {exc}")


# ─── Entry point ─────────────────────────────────────────────────────────────

def main():
    build_materials()
    import_sounds()
    patch_anim_blueprint()

    item_bp = build_weapon_item()
    weapons = {}
    for spec in _weapon_specs():
        weapons[spec["display"]] = build_weapon(spec, item_bp)

    blood_bp = build_blood_splash()
    health_bp = build_health_component()
    weapon_bp = build_weapon_component(item_bp, weapons["Shotgun"],
                                       weapons["Pistol"], blood_bp)

    install_on_character(health_bp, weapon_bp)
    install_on_npc(health_bp)
    retire_old_assets()

    _log("done — shotgun + pistol, inventory, aiming, blood, death and respawn")


if __name__ == "__main__":
    main()
