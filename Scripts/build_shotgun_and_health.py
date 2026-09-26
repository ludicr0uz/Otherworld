"""
build_shotgun_and_health.py — SUPERSEDED. Kept as history; do not run.

Replaced by build_weapons_and_combat.py, which builds the shotgun as a droppable
Actor alongside a pistol, an inventory and the aim pose. Running this file again
would weld the old component tree back onto the character.

It also carries a bug worth knowing about: every "float" variable here is really
an **int**, because get_basic_type_by_name("float") is not recognised and falls
back to int (the correct name is "real"). Every default in this file happens to
be integral, so nothing ever looked wrong.

Original header follows.

Shotgun weapon + health for the player and the NPC.

Run inside the editor:
    UnrealEditor-Cmd <uproject> -ExecutePythonScript="<abs>/Scripts/build_shotgun_and_health.py" -NoUI -stdout

Assets produced (all under /Game/Weapons):

  M_Gunmetal, M_GunWood    — two flat materials, so the weapon reads as a gun
                             rather than as a stack of white boxes.
  BP_HealthComponent       — ActorComponent, *no event graph*: two floats,
                             Health and MaxHealth, both 100.
  BP_ShotgunComponent      — ActorComponent, all the weapon behaviour.
The barrel/stock/receiver themselves are not a separate asset: they are engine
primitives added straight to the character (see _parts()).

Wiring changes:

  BP_ThirdPersonCharacter  gains a Shotgun component tree under its mesh, plus
                           BP_HealthComponent and BP_ShotgunComponent.
  BP_ForestWanderer        gains BP_HealthComponent.

Neither character's *event graph* is touched — only components are added. That
matters: BP_ThirdPersonCharacter's graph is the Enhanced Input template that
ships with the project, and the graph-authoring API has no way to remove "just
the nodes this script added", so anything written there could never be rebuilt
without wiping input handling too. Keeping every node this script owns inside
component Blueprints means the whole feature stays re-runnable.

Why health is a component and not a variable on each character:

  The shooter has to find the health of whatever it hit, and the HUD has to find
  the health of the player pawn. If Health lived on each character class, both
  would need a cast per character type and a separate branch for each. One
  component class means one lookup -- GetComponentByClass -> Cast -> Health --
  that works on the player, on the NPC, and on anything given the component
  later. It also keeps BP_ForestWanderer's builder (build_npc_blueprints.py)
  from having to grow a damage graph.

Damage is applied by writing Health directly rather than through ApplyDamage /
Event AnyDamage. AnyDamage is an *Actor* event, so routing through it would put
a graph on both characters -- exactly what the paragraph above avoids.

BP_ShotgunComponent event graph:

  [Event BeginPlay] --> Cast owner to BP_ThirdPersonCharacter
                        --> AttachToComponent(Shotgun -> Mesh @ HandGrip_R)

  [Event Tick] --> [Branch: WasInputKeyJustPressed(LeftMouseButton)]
                      True --> GetPlayerCameraManager -> camera location/rotation
                               --> [ForLoop 0..PelletCount-1]
                                     RandomUnitVectorInCone(forward, Spread)
                                     --> LineTraceSingle
                                     --> [Branch: hit]
                                           True --> BreakHitResult -> HitActor
                                                    -> GetComponentByClass(Health)
                                                    -> Cast -> Health =
                                                       Clamp(Health - Damage, 0, +inf)
"""

import math

import unreal

# ─── Paths ───────────────────────────────────────────────────────────────────

WEAPON_DIR = "/Game/Weapons"
MAT_METAL = f"{WEAPON_DIR}/M_Gunmetal"
MAT_WOOD = f"{WEAPON_DIR}/M_GunWood"
HEALTH_BP_PATH = f"{WEAPON_DIR}/BP_HealthComponent"
SHOTGUN_BP_PATH = f"{WEAPON_DIR}/BP_ShotgunComponent"

CHARACTER_BP_PATH = "/Game/ThirdPerson/Blueprints/BP_ThirdPersonCharacter"
NPC_BP_PATH = "/Game/Forest/NPC/BP_ForestWanderer"

CHARACTER_CLASS_PATH = f"{CHARACTER_BP_PATH}.BP_ThirdPersonCharacter_C"
HEALTH_CLASS_PATH = f"{HEALTH_BP_PATH}.BP_HealthComponent_C"

CUBE = "/Engine/BasicShapes/Cube"          # 100 cm box
CYLINDER = "/Engine/BasicShapes/Cylinder"  # 100 cm tall, 50 cm radius, axis +Z

# ─── Tuning ──────────────────────────────────────────────────────────────────

START_HEALTH = 100.0

# Left click is the weapon's trigger.  F fires too, deliberately: mouse buttons
# and keyboard keys reach UPlayerInput by different routes, so having both means
# a trigger that does nothing narrows to "input" vs "everything else" in one try
# instead of a round trip.  Drop "F" once left click is confirmed working.
FIRE_KEYS = ("LeftMouseButton", "F")

# Pellet traces are drawn in the world for this many seconds; 0 turns them off.
# On by default because the weapon otherwise has *no* feedback whatsoever -- no
# muzzle flash, no sound, no hit marker -- so a shot that works and a trigger
# that does nothing look exactly alike.
TRACE_DEBUG_SECONDS = 1.5
PELLET_COUNT = 8
PELLET_DAMAGE = 9.0      # 8 x 9 = 72 on a point-blank full hit; ~2 shots to kill.
WEAPON_RANGE = 4000.0    # 40 m, past which a shotgun would not plausibly carry.
SPREAD_DEGREES = 5.0     # half-angle of the pellet cone.

# The socket the weapon hangs from.  SKM_Quinn_Simple carries HandGrip_R and
# HandGrip_L as authored sockets (plus weapon_r_muzzle) -- there is no bone
# called weapon_r, and hand_r is a bone rather than a socket, so HandGrip_R is
# the only thing here actually designed to hold a gun.
GRIP_SOCKET = "HandGrip_R"

# Where the skeleton says a held weapon's muzzle belongs, measured in
# HandGrip_R's own space by querying the reference pose.  The weapon is built
# along its local +X, so aiming +X at this point is what puts the barrel where
# Epic's own rig expects it instead of at a guessed angle.
MUZZLE_IN_GRIP_SPACE = (99.108845, 45.728250, -19.447308)


def _grip_rotation():
    """Rotator that points the weapon's local +X at the muzzle socket."""
    x, y, z = MUZZLE_IN_GRIP_SPACE
    length = math.sqrt(x * x + y * y + z * z)
    r = unreal.Rotator()
    r.yaw = math.degrees(math.atan2(y, x))
    r.pitch = math.degrees(math.asin(z / length))
    r.roll = 0.0
    return r


# Each part: (name, mesh, location, rotation, scale, material).
# Local frame: +X is the muzzle direction, +Z is up, origin sits in the fist.
# A Cube is 100 cm, so scale is the size in metres; a Cylinder is 100 cm tall
# with a 50 cm radius, so scale 0.02 gives a 1 cm radius.
def _barrel_rotation():
    """Rotation that turns a Cylinder's +Z axis into the weapon's +X.

    Derived rather than hard-coded: the sign of the required pitch depends on
    UE's rotator handedness, which is easier to test than to argue about.
    """
    for pitch in (-90.0, 90.0):
        r = unreal.Rotator()
        r.pitch = pitch
        turned = _rotate_vector(r, unreal.Vector(0.0, 0.0, 1.0))
        if turned.x > 0.9:
            return r
    raise RuntimeError("no pitch maps a cylinder's +Z onto +X")


def _rotate_vector(rotator, vector):
    try:
        return rotator.rotate_vector(vector)
    except AttributeError:
        return unreal.MathLibrary.greater_greater_vector_rotator(vector, rotator)


def _parts():
    barrel = _barrel_rotation()
    flat = unreal.Rotator()
    stock_tilt = unreal.Rotator()
    stock_tilt.pitch = 6.0      # butt drops away from the line of the barrel
    grip_tilt = unreal.Rotator()
    grip_tilt.pitch = 20.0
    return (
        # name          mesh      location            rotation     scale                    material
        ("Receiver",    CUBE,     (25.0, 0.0, 0.0),   flat,        (0.30, 0.055, 0.075),    MAT_METAL),
        ("Barrel",      CYLINDER, (70.0, 0.0, 2.2),   barrel,      (0.024, 0.024, 0.60),    MAT_METAL),
        ("MagTube",     CYLINDER, (66.0, 0.0, -2.6),  barrel,      (0.020, 0.020, 0.52),    MAT_METAL),
        ("Pump",        CUBE,     (55.0, 0.0, -2.6),  flat,        (0.20, 0.050, 0.050),    MAT_WOOD),
        ("Stock",       CUBE,     (-8.0, 0.0, -2.5),  stock_tilt,  (0.34, 0.048, 0.070),    MAT_WOOD),
        ("Grip",        CUBE,     (8.0, 0.0, -6.0),   grip_tilt,   (0.055, 0.042, 0.085),   MAT_WOOD),
        ("TriggerGuard", CUBE,    (14.0, 0.0, -4.5),  flat,        (0.070, 0.030, 0.020),   MAT_METAL),
    )


SHOTGUN_ROOT = "Shotgun"

# ─── Graph node paths ────────────────────────────────────────────────────────

FN_GET_OWNER = "/Script/Engine.ActorComponent.GetOwner"
FN_ATTACH = "/Script/Engine.SceneComponent.K2_AttachToComponent"
FN_GET_PC = "/Script/Engine.GameplayStatics.GetPlayerController"
FN_WAS_PRESSED = "/Script/Engine.PlayerController.WasInputKeyJustPressed"
FN_OR = "/Script/Engine.KismetMathLibrary.BooleanOR"
FN_GET_CAM = "/Script/Engine.GameplayStatics.GetPlayerCameraManager"
FN_CAM_LOC = "/Script/Engine.PlayerCameraManager.GetCameraLocation"
FN_CAM_ROT = "/Script/Engine.PlayerCameraManager.GetCameraRotation"
FN_FORWARD = "/Script/Engine.KismetMathLibrary.GetForwardVector"
FN_RAND_CONE = "/Script/Engine.KismetMathLibrary.RandomUnitVectorInConeInRadians"
FN_MUL_VF = "/Script/Engine.KismetMathLibrary.Multiply_VectorFloat"
FN_ADD_VV = "/Script/Engine.KismetMathLibrary.Add_VectorVector"
FN_TRACE = "/Script/Engine.KismetSystemLibrary.LineTraceSingle"
FN_GET_COMP = "/Script/Engine.Actor.GetComponentByClass"
FN_SUB = "/Script/Engine.KismetMathLibrary.Subtract_DoubleDouble"
FN_CLAMP = "/Script/Engine.KismetMathLibrary.FClamp"

NODE_TICK = "AddEvent|EventTick"
NODE_BEGIN_PLAY = "AddEvent|EventBeginPlay"
NODE_BREAK_HIT = "Collision|BreakHitResult"
NODE_CAST_CHAR = "Utilities|Casting|CastToBP_ThirdPersonCharacter"
NODE_CAST_HEALTH = "Utilities|Casting|CastToBP_HealthComponent"
MACRO_FOR_LOOP = "/Engine/EditorBlueprintResources/StandardMacros.StandardMacros:ForLoop"

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
# Same shape as the ones in build_graphics_menu.py, and duplicated for the same
# reason: every builder in Scripts/ runs standalone.

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


# ─── Component helpers ───────────────────────────────────────────────────────

def _handles(bp):
    """(handle, variable name) for every subobject of ``bp``."""
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
    parts want -- so rename_subobject quietly fails and the character
    accumulates a second, nameless copy of the weapon on every run.

    So: anything descended from a target is itself a target, and the delete
    loop repeats because a parent cannot go before its children.
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
        sds.delete_subobject(_root_handle(bp),
                             (leaves or [doomed[0][1]])[0], bp)
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


def _apply_defaults(bp, defaults):
    """Write variable defaults onto the CDO, because add_member_variable cannot.

    ``add_member_variable(name, type, "100.0")`` returns True, and then the
    compiler logs `Can't parse default value '100.0'` and leaves the property at
    zero -- a default that reads as set everywhere except where it matters. UE
    5.8 exposes no Python API for a *member* variable's default (only
    set_local_variable_default_value, for locals), so the value is written to
    the compiled class's default object and baked in by recompiling.

    The read-back is the point: a health component that silently starts at 0 HP
    would look exactly like a working one until something shot at it.
    """
    cdo = unreal.get_default_object(BEL.generated_class(bp))
    for name, value in defaults.items():
        cdo.set_editor_property(name, value)
    if not BEL.compile_blueprint(bp):
        raise RuntimeError(f"{bp.get_name()} failed to recompile after defaults")
    _assets().save_loaded_asset(bp)
    fresh = unreal.get_default_object(BEL.generated_class(bp))
    for name, value in defaults.items():
        got = float(fresh.get_editor_property(name))
        if abs(got - float(value)) > 1e-6:
            raise RuntimeError(f"default for {name} did not stick: {got} != {value}")


# ─── Materials ───────────────────────────────────────────────────────────────

def build_materials():
    """Two unlit-ish constant materials: gunmetal and a wood-toned stock.

    Material *instances* of BasicShapeMaterial would be cheaper, but that engine
    material exposes no parameters, so there is nothing to instance.
    """
    eas = _assets()
    mel = unreal.MaterialEditingLibrary
    for path, (colour, metallic, roughness) in (
            (MAT_METAL, ((0.055, 0.058, 0.065), 1.0, 0.32)),
            (MAT_WOOD, ((0.115, 0.062, 0.030), 0.0, 0.62))):
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
        mel.recompile_material(mat)
        eas.save_loaded_asset(mat)
        _log(f"built {path}")


# ─── BP_HealthComponent ──────────────────────────────────────────────────────

def build_health_component():
    """Two floats and nothing else -- deliberately no event graph.

    Health is data. Everything that changes it (the shotgun) or reads it (the
    HUD) lives where that behaviour belongs, which keeps this asset something
    that can be dropped onto any actor without dragging logic along.
    """
    bp = _create_blueprint(HEALTH_BP_PATH, unreal.ActorComponent)
    ed = BGE.get_graph_editor_by_name(bp, "EventGraph")
    for name in ("Health", "MaxHealth"):
        # Re-declared every run so a type change in this file actually lands.
        ed.remove_member_variable(name)
        if not ed.add_member_variable(name, BEL.get_basic_type_by_name("float")):
            raise RuntimeError(f"could not declare {name}")
    if not BEL.compile_blueprint(bp):
        raise RuntimeError("BP_HealthComponent failed to compile")
    _apply_defaults(bp, {"Health": START_HEALTH, "MaxHealth": START_HEALTH})
    _log(f"built {HEALTH_BP_PATH} (Health = MaxHealth = {START_HEALTH})")
    return bp


# ─── The shotgun's geometry, added to the character ──────────────────────────

def install_weapon_mesh(character_bp):
    """Build the weapon out of engine primitives under a Shotgun scene root.

    The parts hang off the character's skeletal mesh component, and BeginPlay
    snaps the root to HandGrip_R (see _author_begin_play). The socket cannot be
    set here: a component's authored attach socket lives on the USCS_Node, and
    UE 5.8 exposes no way to reach that from Python.
    """
    eas = _assets()
    mesh_handle = _find_handle(character_bp, "Mesh")
    if not mesh_handle:
        raise RuntimeError("BP_ThirdPersonCharacter has no Mesh component")

    _drop_components(character_bp,
                     {SHOTGUN_ROOT} | {p[0] for p in _parts()})
    root = _add_component(character_bp, mesh_handle, unreal.SceneComponent, SHOTGUN_ROOT)
    root_obj = _component_object(root)
    root_obj.set_editor_property("relative_rotation", _grip_rotation())

    for name, mesh_path, location, rotation, scale, material in _parts():
        handle = _add_component(character_bp, root, unreal.StaticMeshComponent, name)
        obj = _component_object(handle)
        obj.set_editor_property("static_mesh", eas.load_asset(mesh_path))
        obj.set_editor_property("relative_location", unreal.Vector(*location))
        obj.set_editor_property("relative_rotation", rotation)
        obj.set_editor_property("relative_scale3d", unreal.Vector(*scale))
        obj.set_editor_property("override_materials", [eas.load_asset(material)])
        # The weapon must never block anything: it is glued to the player, and a
        # collider on the barrel would shove the capsule around.
        try:
            obj.set_collision_profile_name("NoCollision")
        except Exception as exc:                                  # noqa: BLE001
            _log(f"  note: could not set NoCollision on {name}: {exc}")
    _log(f"weapon mesh: {SHOTGUN_ROOT} + {len(_parts())} parts under Mesh")


# ─── BP_ShotgunComponent ─────────────────────────────────────────────────────

def _author_begin_play(ed, begin_play):
    """Snap the Shotgun component tree to the hand socket."""
    origin = BEL.get_node_pos(begin_play)
    x0, y0 = origin.x, origin.y

    owner = _at(_node(ed, FN_GET_OWNER), x0 + 240, y0 + 180)
    cast = _at(_palette(ed, NODE_CAST_CHAR), x0 + 460, y0)
    _connect(_pin(owner, "ReturnValue", is_input=False), _pin(cast, "Object"))
    _connect(BEL.find_then_pin(begin_play), _pin(cast, "execute"))
    as_char = _loose_pin(cast, "AsBPThirdPersonCharacter", is_input=False)

    gun = _at(ed.add_get_member_variable_node(SHOTGUN_ROOT, CHARACTER_CLASS_PATH),
              x0 + 760, y0 + 220)
    _connect(as_char, _pin(gun, "self"))

    mesh = _at(ed.add_get_member_variable_node("Mesh", "/Script/Engine.Character"),
               x0 + 760, y0 + 380)
    _connect(as_char, _pin(mesh, "self"))

    attach = _at(_node(ed, FN_ATTACH), x0 + 1020, y0)
    _connect(_pin(gun, SHOTGUN_ROOT, is_input=False), _pin(attach, "self"))
    _connect(_pin(mesh, "Mesh", is_input=False), _pin(attach, "Parent"))
    _set(attach, "SocketName", GRIP_SOCKET)
    # KeepRelative, not SnapToTarget: the weapon's offset from the socket is the
    # whole reason the grip rotation was measured, and SnapToTarget would throw
    # it away by forcing an identity relative transform.
    for rule in ("LocationRule", "RotationRule", "ScaleRule"):
        _set(attach, rule, "KeepRelative")
    _connect(BEL.find_then_pin(cast), _pin(attach, "execute"))

    ed.add_comment_to_nodes(
        f"The weapon is authored under the character's Mesh but with no socket: "
        f"UE 5.8 cannot set a component's authored attach socket from Python, so "
        f"it is snapped to {GRIP_SOCKET} here instead.",
        [owner, cast, gun, mesh, attach])


def _author_damage(ed, hit_actor_pin, exec_in, x0, y0):
    """hit actor -> its health component -> subtract one pellet's damage."""
    comp = _at(_node(ed, FN_GET_COMP), x0, y0 + 200)
    _connect(hit_actor_pin, _pin(comp, "self"))
    _pin(comp, "ComponentClass").set_pin_value(HEALTH_CLASS_PATH)

    cast = _at(_palette(ed, NODE_CAST_HEALTH), x0 + 260, y0)
    _connect(_pin(comp, "ReturnValue", is_input=False), _pin(cast, "Object"))
    _connect(exec_in, _pin(cast, "execute"))
    as_health = _loose_pin(cast, "AsBPHealthComponent", is_input=False)

    get_h = _at(ed.add_get_member_variable_node("Health", HEALTH_CLASS_PATH),
                x0 + 520, y0 + 240)
    _connect(as_health, _pin(get_h, "self"))

    sub = _at(_node(ed, FN_SUB), x0 + 740, y0 + 240)
    _connect(_pin(get_h, "Health", is_input=False), _pin(sub, "A"))
    get_dmg = _at(ed.add_get_member_variable_node("Damage"), x0 + 520, y0 + 380)
    _connect(_pin(get_dmg, "Damage", is_input=False), _pin(sub, "B"))

    clamp = _at(_node(ed, FN_CLAMP), x0 + 940, y0 + 240)
    _connect(_pin(sub, "ReturnValue", is_input=False), _pin(clamp, "Value"))
    _set(clamp, "Min", 0.0)
    _set(clamp, "Max", 1.0e9)

    set_h = _at(ed.add_set_member_variable_node("Health", HEALTH_CLASS_PATH),
                x0 + 1180, y0)
    _connect(as_health, _pin(set_h, "self"))
    _connect(_pin(clamp, "ReturnValue", is_input=False), _pin(set_h, "Health"))
    _connect(BEL.find_then_pin(cast), _pin(set_h, "execute"))

    made = [comp, cast, get_h, sub, get_dmg, clamp, set_h]
    ed.add_comment_to_nodes(
        "Anything carrying BP_HealthComponent can be shot -- the NPC today, "
        "anything else the component is dropped onto later. A miss, or a hit on "
        "something without health, fails the cast and costs nothing.",
        made)
    return made


def _author_tick(ed, tick):
    origin = BEL.get_node_pos(tick)
    x0, y0 = origin.x, origin.y

    pc = _at(_node(ed, FN_GET_PC), x0 + 200, y0 + 200)
    _set(pc, "PlayerIndex", 0)
    # One WasInputKeyJustPressed per trigger key, OR'd together.  The node is
    # pure despite being declared BlueprintCallable -- UHT promotes a const
    # BlueprintCallable to BlueprintPure -- so it has no exec pin to wire and is
    # evaluated when the branch reads its condition.
    trigger = None
    polls = []
    for i, key in enumerate(FIRE_KEYS):
        pressed = _at(_node(ed, FN_WAS_PRESSED), x0 + 460, y0 + 160 + i * 130)
        _connect(_pin(pc, "ReturnValue", is_input=False), _pin(pressed, "self"))
        # Bare key name, never struct text: FKey exports as just its name, so
        # '(KeyName="LeftMouseButton")' would import back as a key called "(".
        _set(pressed, "Key", key)
        polls.append(pressed)
        out = _pin(pressed, "ReturnValue", is_input=False)
        if trigger is None:
            trigger = out
        else:
            either = _at(_node(ed, FN_OR), x0 + 700, y0 + 200 + i * 130)
            _connect(trigger, _pin(either, "A"))
            _connect(out, _pin(either, "B"))
            polls.append(either)
            trigger = _pin(either, "ReturnValue", is_input=False)

    fire = _at(ed.add_branch_node(), x0 + 900, y0)
    _connect(trigger, _pin(fire, "Condition"))
    _connect(BEL.find_then_pin(tick), _pin(fire, "execute"))

    ed.add_comment_to_nodes(
        f"{' or '.join(FIRE_KEYS)} fires. Polled on Tick rather than bound to an "
        "input action, for the same reason the graphics menu polls M: an "
        "Enhanced Input binding needs an IA asset and an IMC entry, and neither "
        "is authorable from Python.",
        [pc] + polls + [fire])

    # --- where the shot comes from ------------------------------------------
    cam = _at(_node(ed, FN_GET_CAM), x0 + 1040, y0 + 240)
    _set(cam, "PlayerIndex", 0)
    cam_out = _pin(cam, "ReturnValue", is_input=False)
    loc = _at(_node(ed, FN_CAM_LOC), x0 + 1280, y0 + 200)
    _connect(cam_out, _pin(loc, "self"))
    rot = _at(_node(ed, FN_CAM_ROT), x0 + 1280, y0 + 340)
    _connect(cam_out, _pin(rot, "self"))
    fwd = _at(_node(ed, FN_FORWARD), x0 + 1520, y0 + 340)
    _connect(_pin(rot, "ReturnValue", is_input=False), _pin(fwd, "InRot"))

    ed.add_comment_to_nodes(
        "The shot is traced from the camera, not from the muzzle: in third "
        "person the barrel points wherever the idle animation leaves it, so "
        "muzzle-origin traces would not go where the player is looking.",
        [cam, loc, rot, fwd])

    # --- one trace per pellet ------------------------------------------------
    loop = ed.add_macro_node(MACRO_FOR_LOOP)
    if not loop:
        raise RuntimeError("could not create the ForLoop macro node")
    _at(loop, x0 + 1060, y0)
    _loose_pin(loop, "FirstIndex").set_pin_value("0")
    _loose_pin(loop, "LastIndex").set_pin_value(str(PELLET_COUNT - 1))
    _connect(BEL.find_then_pin(fire), _loose_pin(loop, "execute"))

    bx, by = x0 + 1800, y0
    cone = _at(_node(ed, FN_RAND_CONE), bx, by + 340)
    _connect(_pin(fwd, "ReturnValue", is_input=False), _pin(cone, "ConeDir"))
    _set(cone, "ConeHalfAngleInRadians", math.radians(SPREAD_DEGREES))

    reach = _at(_node(ed, FN_MUL_VF), bx + 260, by + 340)
    _connect(_pin(cone, "ReturnValue", is_input=False), _pin(reach, "A"))
    get_range = _at(ed.add_get_member_variable_node("Range"), bx, by + 480)
    _connect(_pin(get_range, "Range", is_input=False), _pin(reach, "B"))

    end = _at(_node(ed, FN_ADD_VV), bx + 500, by + 260)
    _connect(_pin(loc, "ReturnValue", is_input=False), _pin(end, "A"))
    _connect(_pin(reach, "ReturnValue", is_input=False), _pin(end, "B"))

    trace = _at(_node(ed, FN_TRACE), bx + 740, by)
    _connect(_pin(loc, "ReturnValue", is_input=False), _pin(trace, "Start"))
    _connect(_pin(end, "ReturnValue", is_input=False), _pin(trace, "End"))
    _set(trace, "TraceChannel", "TraceTypeQuery1")   # Visibility
    _set(trace, "bTraceComplex", "false")
    _set(trace, "bIgnoreSelf", "true")               # skips the player and its weapon
    # Visible pellet traces -- the only feedback the weapon has right now.
    if TRACE_DEBUG_SECONDS > 0:
        _set(trace, "DrawDebugType", "ForDuration")
        _set(trace, "DrawTime", TRACE_DEBUG_SECONDS)
    else:
        _set(trace, "DrawDebugType", "None")
    _connect(_loose_pin(loop, "LoopBody", is_input=False), _pin(trace, "execute"))

    hit = _at(ed.add_branch_node(), bx + 1040, by)
    _connect(_pin(trace, "ReturnValue", is_input=False), _pin(hit, "Condition"))
    _connect(BEL.find_then_pin(trace), _pin(hit, "execute"))

    brk = _at(_palette(ed, NODE_BREAK_HIT), bx + 1040, by + 300)
    _connect(_pin(trace, "OutHit", is_input=False), _loose_pin(brk, "Hit"))

    ed.add_comment_to_nodes(
        f"{PELLET_COUNT} pellets, each an independent trace inside a "
        f"{SPREAD_DEGREES:.0f}-degree cone, so range genuinely thins the shot "
        "the way a shotgun should. Ammo is unlimited by omission: nothing here "
        "counts or gates on shells.",
        [loop, cone, reach, get_range, end, trace, hit, brk])

    _author_damage(ed, _loose_pin(brk, "HitActor", is_input=False),
                   BEL.find_then_pin(hit), bx + 1340, by)


def build_shotgun_component(rebuild=False):
    """Create BP_ShotgunComponent and author BeginPlay + Tick.

    ``rebuild`` wipes the graph first. Without an escape hatch, an already
    authored blueprint would be left alone and no edit to this file could ever
    reach the asset -- the trap build_graphics_menu.py documents.
    """
    bp = _create_blueprint(SHOTGUN_BP_PATH, unreal.ActorComponent)
    ed = BGE.get_graph_editor_by_name(bp, "EventGraph")
    if not ed:
        raise RuntimeError(f"{SHOTGUN_BP_PATH} has no EventGraph")

    tick = ed.find_event_node("ReceiveTick")
    outgoing = BEL.find_then_pin(tick) if tick else None
    authored = bool(outgoing and outgoing.is_valid() and outgoing.list_connected_pins())
    if authored and not rebuild:
        _log(f"{SHOTGUN_BP_PATH} already authored — reusing")
        return bp
    if authored:
        _log("wiping the existing graph")
        ed.remove_nodes(ed.list_all_nodes())
        tick = None

    # Declared bare; the values are baked onto the CDO by _apply_defaults once
    # the graph compiles.
    for name in ("Damage", "Range"):
        ed.remove_member_variable(name)
        if not ed.add_member_variable(name, BEL.get_basic_type_by_name("float")):
            raise RuntimeError(f"could not declare {name}")

    if not tick:
        tick = ed.create_node_from_name(NODE_TICK, unreal.Vector2D(0.0, 0.0), [])
        if not tick:
            raise RuntimeError(f"could not create {NODE_TICK}")
    origin = BEL.get_node_pos(tick)

    begin_play = ed.find_event_node("ReceiveBeginPlay")
    if not begin_play:
        begin_play = ed.create_node_from_name(
            NODE_BEGIN_PLAY, unreal.Vector2D(float(origin.x), float(origin.y - 700)), [])
        if not begin_play:
            raise RuntimeError(f"could not create {NODE_BEGIN_PLAY}")

    _author_begin_play(ed, begin_play)
    _author_tick(ed, tick)

    # Tick late, so the player controller has already run ProcessInputStack this
    # frame.  WasInputKeyJustPressed reads EventCounts, which that call swaps
    # out once per frame; a component's default TG_PrePhysics puts it in the
    # same tick group as the controller with no defined order between them.
    cdo = unreal.get_default_object(BEL.generated_class(bp))
    tick_fn = cdo.get_editor_property("primary_component_tick")
    tick_fn.set_editor_property("tick_group", unreal.TickingGroup.TG_POST_PHYSICS)
    cdo.set_editor_property("primary_component_tick", tick_fn)

    # Nothing here enables ticking, and nothing needs to: bCanEverTick is not a
    # UPROPERTY, so Python cannot reach it -- but FKismetCompilerContext::
    # SetCanEverTick turns it on at compile time for any Blueprint whose first
    # native parent is UActorComponent (or AActor) and whose Tick event has its
    # exec pin connected. Both hold here. Leave the Tick event wired or the
    # component silently stops firing.
    if not BEL.compile_blueprint(bp):
        raise RuntimeError("BP_ShotgunComponent failed to compile")
    _apply_defaults(bp, {"Damage": PELLET_DAMAGE, "Range": WEAPON_RANGE})
    _log(f"built {SHOTGUN_BP_PATH}")
    return bp


# ─── Installing the components ───────────────────────────────────────────────

def install_on_character(health_bp, shotgun_bp):
    eas = _assets()
    bp = eas.load_asset(CHARACTER_BP_PATH)
    if not bp:
        raise RuntimeError(f"could not load {CHARACTER_BP_PATH}")
    _drop_components(bp, {"HealthComponent", "ShotgunComponent"})
    for name, source in (("HealthComponent", health_bp),
                         ("ShotgunComponent", shotgun_bp)):
        _add_component(bp, _root_handle(bp), BEL.generated_class(source), name)
    if not BEL.compile_blueprint(bp):
        raise RuntimeError("BP_ThirdPersonCharacter failed to compile")
    eas.save_loaded_asset(bp)
    _log("player: HealthComponent + ShotgunComponent installed")


def install_on_npc(health_bp):
    eas = _assets()
    bp = eas.load_asset(NPC_BP_PATH)
    if not bp:
        raise RuntimeError(f"could not load {NPC_BP_PATH}")
    _drop_components(bp, {"HealthComponent"})
    _add_component(bp, _root_handle(bp), BEL.generated_class(health_bp),
                   "HealthComponent")
    if not BEL.compile_blueprint(bp):
        raise RuntimeError("BP_ForestWanderer failed to compile")
    eas.save_loaded_asset(bp)
    _log("NPC: HealthComponent installed")


def build_all():
    eas = _assets()
    build_materials()
    health_bp = build_health_component()

    # The weapon mesh goes on first: BP_ShotgunComponent's BeginPlay reads the
    # character's `Shotgun` variable, which does not exist until the components
    # below have been added and the character recompiled.
    character = eas.load_asset(CHARACTER_BP_PATH)
    if not character:
        raise RuntimeError(f"could not load {CHARACTER_BP_PATH}")
    install_weapon_mesh(character)
    if not BEL.compile_blueprint(character):
        raise RuntimeError("BP_ThirdPersonCharacter failed to compile")
    eas.save_loaded_asset(character)

    shotgun_bp = build_shotgun_component(rebuild=True)
    install_on_character(health_bp, shotgun_bp)
    install_on_npc(health_bp)


if __name__ == "__main__":
    build_all()
    _log("done")
