"""The player's motion-matching anim Blueprint (task G3): the Game Animation
Sample's SandboxCharacter_CMC_ABP, patched where it lies
(gas_locomotion_consts.py says why it is not a copy).

The sample's graph is kept whole: its motion matching node, its
CHT_PoseSearchDatabases chooser, its blend stack, steering, root offset and
foot placement. What this file changes in it, each time it runs:

  WHAT IT READS   Update_PropertiesFromCharacter is re-authored. The sample's
                  asks its pawn for a struct through an interface its own
                  character implements; patched, it fills the same struct from
                  the pawn's CharacterMovementComponent, as that character
                  did (Get_PropertiesForAnimation, read off the sample), so it
                  runs on any Character and on every machine. The speeds, the
                  sprint and the aim's walk stay the game's (the C++ movement
                  component): the gait is read off them, never set.
                      Gait          Sprint while the movement sprints, Walk
                                    under WALK_BELOW_CMS of pace, else Run
                      RotationMode  Strafe unless the movement orients the
                                    body to its velocity (the player faces
                                    the view, so it strafes)
                      MovementMode  InAir while falling, else OnGround
                      Stance        Crouch while the movement crouches and
                                    is not prone (gas_moves.crouch_on(): the
                                    sample's crouch set, G5), else Stand
                      JustLanded,   kept here: the frame the fall ends, and
                      LandVelocity  the velocity of its last frame
  THE SLOT        its one montage slot (full body, before the root's offset)
                  leaves the pose line: the slots that play are the weapon
                  layers'. With traversal on (gas_moves.traversal_on(), G5) it
                  is back on one arm of a blend, in the line only while a
                  traversal plays (gas_traversal_slot.py)
  THE LAYERS      one Linked Anim Graph node, after Remap Curves: the weapon
                  layers' anim Blueprint (weapon_layers.py), which plays
                  everything a weapon, a stance or a hit does to the body
                  over this graph's pose (G4)
  THE FOLEY       silent_foley_bank(): the empty sound bank the sample's foley
                  component is given on the player (install.install_foley)
  THE SERVER      the one IsDedicatedServer branch (A4): a server skips the
                  feet's ground traces (gas_locomotion_consts, "The server
                  branch")

Nothing is hand-animated here and no clip is named: which clip plays is the
sample's chooser's and its databases' business.
"""

import unreal

from combat.gas_locomotion_consts import (
    ABP_LOCOMOTION, ADDED_VARS, EYE_CLASSES, FALL_VELOCITY, FIELDS_SET,
    FOLEY_BANK_SOURCE, FOLEY_BANK_TABLE, FOLEY_SILENT_BANK,
    HISTORY_CLASS, JUST_LANDED_SECONDS, LAND_VELOCITY, LANDED_AT, PROPERTIES_GRAPH,
    PROPERTIES_VAR, SLOT_CLASS, SLOT_NAME, WALK_BELOW_CMS, WAS_FALLING,
)
from combat.gas_moves import crouch_on, traversal_on
from combat.gas_traversal_slot import (
    author_traversal_slot, author_traversing_flag, remove_traversal_slot,
)
from combat.log import _log
from combat.weapon_layers import layers_class_path
from combat.weapon_layers_consts import (
    BEFORE_LINK_CLASS, LAYERS_ABP, LAYERS_TAG, LINK_CLASS, LINK_IN_PIN,
)
from combat.server_anim_consts import (
    BRANCH_CLASS, CLIENT_PIN, FLAG_PIN, SERVER_PIN, SERVER_POSE_VAR,
)
from uebp import props as EP
from uebp.g import _G
from uebp.graph import (
    BEL, BGE, PIN, _apply_defaults, _assets, _connect, _declare, _loose_pin, _node,
    _palette, _pin, _set, out, then,
)
from uebp.layout import arrange
from uebp.nodes.actor import FN_GET_BASE_AIM_ROT, FN_GET_TRANSFORM, FN_VELOCITY
from uebp.nodes.locomotion import (
    FN_ACTOR_ROT, FN_CURRENT_ACCELERATION, FN_INT_TO_BYTE, FN_IS_FALLING,
    FN_MAX_ACCELERATION, FN_MAX_SPEED, FN_SELECT_INT, FN_TRY_GET_PAWN_OWNER,
    NODE_BREAK_FLOOR, NODE_BYTE_TO_GAIT, NODE_BYTE_TO_MOVEMENT_MODE,
    NODE_BYTE_TO_ROTATION_MODE, NODE_BYTE_TO_STANCE, NODE_EVENT_INIT_ANIM, NODE_MAKE_CHARACTER_PROPERTIES,
    NODE_MAKE_INPUT_STATE,
)
from uebp.nodes.math import FN_AND, FN_EQ_II, FN_GREATER_FF, FN_LESS_FF, FN_NOT, FN_SUB_FF
from uebp.nodes.move import FN_GET_STANCE, FN_IS_SPRINTING
from uebp.nodes.palette import NODE_BLEND_BY_BOOL, NODE_BREAK_HIT, NODE_CAST_CHARACTER
from uebp.nodes.system import FN_IS_DEDICATED_SERVER, FN_TIME_SECONDS
from uebp.pose_share import fed, share, unshare
from uebp.vars import BOOL, declare, defaults

CMC = "/Script/Engine.CharacterMovementComponent"
CHARACTER = "/Script/Engine.Character"
INIT_EVENT = "BlueprintInitializeAnimation"


def _class(node):
    return node.get_class().get_name()


def _fed(pin):
    # Read through a cached pose: a verifier calls these walks on the graph
    # as it is worn (uebp/pose_share.py).
    return fed(pin)


def _field(make, name):
    """The Make node's pin for one field: its name, then an id."""
    for pin in BEL.list_input_pins(make):
        if str(PIN.get_pin_name(pin)).split("_")[0] == name:
            return pin
    raise RuntimeError(f"the properties struct has no field {name}")


def enum_values(bp):
    """{variable: {member: number}} for the sample's Gait, MovementMode and
    RotationMode, read off the compiled class: the byte each member is."""
    cdo = unreal.get_default_object(BEL.generated_class(bp))
    found = {}
    for var in ("Gait", "MovementMode", "RotationMode", "Stance"):
        kind = type(cdo.get_editor_property(var))
        found[var] = {m: int(getattr(kind, m).value) for m in dir(kind) if m.isupper()}
    return found


def _as_enum(g, node_name, picked):
    """An int pin as one of the sample's enums."""
    as_byte = g.call(FN_INT_TO_BYTE, InInt=picked)
    cast = g.keep(_palette(g.ed, node_name))
    _connect(out(as_byte), _pin(cast, "Byte"))
    return out(cast)


def _pick(g, when, a, b):
    """``a`` while ``when``, else ``b``: two numbers, one pin."""
    return out(g.call(FN_SELECT_INT, A=a, B=b, bPickA=when))


def _author_properties(bp, ed):
    """Update_PropertiesFromCharacter, from the function's entry on."""
    values = enum_values(bp)
    entry = next(n for n in ed.list_all_nodes() if _class(n) == "K2Node_FunctionEntry")
    ed.remove_nodes([n for n in ed.list_all_nodes() if n.get_name() != entry.get_name()])
    g = _G(ed)

    cast = g.keep(_palette(ed, NODE_CAST_CHARACTER))
    _connect(out(g.call(FN_TRY_GET_PAWN_OWNER)), _pin(cast, "Object"))
    _connect(then(entry), _pin(cast, "execute"))
    char = _loose_pin(cast, "AsCharacter", is_input=False)
    move = g.iget(char, EP.CHARACTER_MOVEMENT, CHARACTER)

    def velocity():
        return out(g.call(FN_VELOCITY, self=char))

    falling = g.call(FN_IS_FALLING, self=move)
    now = g.call(FN_TIME_SECONDS)

    # The landing. While it falls, the fall's velocity is kept; the frame it
    # no longer falls, that is the land velocity and the time is written down.
    in_air, on_ground = g.branch(out(falling), [then(cast)])
    kept = g.put(FALL_VELOCITY, velocity(), [in_air])
    kept = g.put(WAS_FALLING, "true", [kept])
    landed, _ = g.branch(g.get(WAS_FALLING), [on_ground])
    done = g.put(LAND_VELOCITY, g.get(FALL_VELOCITY), [landed])
    done = g.put(LANDED_AT, out(now), [done])
    done = g.put(WAS_FALLING, "false", [done])
    since = g.call(FN_SUB_FF, A=out(g.call(FN_TIME_SECONDS)), B=g.get(LANDED_AT))
    just_landed = g.call(
        FN_AND,
        A=out(g.call(FN_AND, A=out(g.call(FN_GREATER_FF, A=g.get(LANDED_AT), B="0.0")),
                     B=out(g.call(FN_LESS_FF, A=out(since), B=str(JUST_LANDED_SECONDS))))),
        B=out(g.call(FN_NOT, A=out(g.call(FN_IS_FALLING, self=move)))))

    # The gait, the rotation mode and the movement mode: numbers, then enums.
    sprinting = g.call(FN_IS_SPRINTING, Character=char)
    walking = g.call(FN_LESS_FF, A=out(g.call(FN_MAX_SPEED, self=move)),
                     B=str(WALK_BELOW_CMS))
    gait = _pick(g, out(sprinting), values["Gait"]["SPRINT"],
                 _pick(g, out(walking), values["Gait"]["WALK"], values["Gait"]["RUN"]))
    orients = g.iget(move, EP.ORIENT_ROTATION_TO_MOVEMENT, CMC)
    rotation = _pick(g, orients, values["RotationMode"]["ORIENT_TO_MOVEMENT"],
                     values["RotationMode"]["STRAFE"])
    mode = _pick(g, out(g.call(FN_IS_FALLING, self=move)),
                 values["MovementMode"]["IN_AIR"], values["MovementMode"]["ON_GROUND"])

    wants = g.keep(_palette(ed, NODE_MAKE_INPUT_STATE))
    _connect(out(g.call(FN_IS_SPRINTING, Character=char)), _field(wants, "WantsToSprint"))
    _connect(out(g.call(FN_LESS_FF, A=out(g.call(FN_MAX_SPEED, self=move)),
                        B=str(WALK_BELOW_CMS))), _field(wants, "WantsToWalk"))
    _connect(out(g.call(FN_NOT, A=g.iget(move, EP.ORIENT_ROTATION_TO_MOVEMENT, CMC))),
             _field(wants, "WantsToStrafe"))

    floor = g.keep(_palette(ed, NODE_BREAK_FLOOR))
    _connect(g.iget(move, EP.CURRENT_FLOOR, CMC), _pin(floor, "FindFloorResult"))
    hit = g.keep(_palette(ed, NODE_BREAK_HIT))
    _connect(out(floor, "HitResult"), _pin(hit, "Hit"))

    make = g.keep(_palette(ed, NODE_MAKE_CHARACTER_PROPERTIES))
    fields = {
        "ActorTransform": out(g.call(FN_GET_TRANSFORM, self=char)),
        "AimingRotation": out(g.call(FN_GET_BASE_AIM_ROT, self=char)),
        "OrientationIntent": out(g.call(FN_ACTOR_ROT, self=char)),
        "Velocity": velocity(),
        "InputAcceleration": out(g.call(FN_CURRENT_ACCELERATION, self=move)),
        "CurrentMaxAcceleration": out(g.call(FN_MAX_ACCELERATION, self=move)),
        "CurrentMaxDeceleration": g.iget(move, EP.BRAKING_DECELERATION_WALKING, CMC),
        "GroundNormal": out(hit, "ImpactNormal"),
        "Gait": _as_enum(g, NODE_BYTE_TO_GAIT, gait),
        "MovementMode": _as_enum(g, NODE_BYTE_TO_MOVEMENT_MODE, mode),
        "RotationMode": _as_enum(g, NODE_BYTE_TO_ROTATION_MODE, rotation),
        "InputState": next(iter(BEL.list_output_pins(wants))),
        "JustLanded": out(just_landed),
        "LandVelocity": g.get(LAND_VELOCITY),
    }
    if crouch_on():
        # The movement's own answer (1: crouched and not prone), so another
        # player's copy and the server's crouch with it. Prone and a slide
        # are the weapon layers' clips, over whatever this picks.
        crouched = g.call(FN_EQ_II, A=out(g.call(FN_GET_STANCE, Character=char)), B="1")
        fields["Stance"] = _as_enum(g, NODE_BYTE_TO_STANCE, _pick(
            g, out(crouched), values["Stance"]["CROUCH"], values["Stance"]["STAND"]))
    if set(fields) != set(fields_set()):
        raise RuntimeError("FIELDS_SET and the fields authored here disagree")
    for name, pin in fields.items():
        _connect(pin, _field(make, name))
    # One write, reached from every way through the landing's branches.
    wrote = g.put(PROPERTIES_VAR, next(iter(BEL.list_output_pins(make))),
                  [kept, done, else_pin(ed, landed)])
    if traversal_on():
        author_traversing_flag(g, char, [wrote])
    ed.add_comment_to_nodes(
        "What the motion matching reads of its character, straight off the "
        "CharacterMovementComponent (the sample asked its own character through an "
        "interface): the game's speeds and sprint decide the gait, the body strafes "
        "while it faces the view, and the landing is kept here. "
        "Scripts/combat/gas_locomotion.py.", g.made)


def fields_set():
    """The struct's fields the patch sets: Stance with them while the crouch
    is the sample's."""
    return FIELDS_SET + (("Stance",) if crouch_on() else ())


def else_pin(ed, then_pin):
    """The else of the Branch whose then pin this is."""
    return BEL.find_output_pin(PIN.get_owning_node(then_pin), "else")


# ─── The montage slot ────────────────────────────────────────────────────────

def _slot(ed):
    slots = [n for n in ed.list_all_nodes() if _class(n) == SLOT_CLASS
             and SLOT_NAME in str(BEL.get_node_title(n))]
    if len(slots) != 1:
        raise RuntimeError(f"expected one Slot({SLOT_NAME}), found {len(slots)}")
    return slots[0]


def slot_in_line(ed):
    """Whether the sample's montage slot is part of the pose line."""
    slot = _slot(ed)
    return bool(_fed(_pin(slot, "Source"))) and bool(_fed(out(slot, "Pose")))


def _remove_slot(ed):
    """Take the sample's slot out of the pose line and join what it split:
    the slots that play are the weapon layers'."""
    if not slot_in_line(ed):
        return
    slot = _slot(ed)
    source, onward = _fed(_pin(slot, "Source")), _fed(out(slot, "Pose"))
    PIN.break_pin_links(_pin(slot, "Source"))
    PIN.break_pin_links(out(slot, "Pose"))
    for pin in onward:
        _connect(source[0], pin)


# ─── The weapon layers ───────────────────────────────────────────────────────

def layer_links(ed):
    """The Linked Anim Graph nodes of the graph."""
    return [n for n in ed.list_all_nodes() if _class(n) == LINK_CLASS]


def link_tag(node):
    return str(node.get_editor_property("tag"))


def link_class(node):
    """The path of the anim class a Linked Anim Graph node runs."""
    cls = node.get_editor_property("node").get_editor_property("instance_class")
    return cls.get_path_name() if cls else None


def _remove_link(ed):
    for link in layer_links(ed):
        source, onward = _fed(_pin(link, LINK_IN_PIN)), _fed(out(link, "Pose"))
        ed.remove_nodes([link])
        for pin in onward if source else ():
            _connect(source[0], pin)


def _author_link(ed):
    """Link ABP_WeaponLayers in after Remap Curves: after the root's offset,
    so an aimed upper body (a mesh-space blend) faces where the capsule does
    and not where the lagging root does, and before the feet and the pose
    history. Before the server branch is authored: it is on both its arms
    (weapon_layers_consts.py)."""
    if not unreal.load_class(None, layers_class_path()):
        raise RuntimeError(f"{LAYERS_ABP} has no class: build_weapon_layers() runs first")
    before = [n for n in ed.list_all_nodes() if _class(n) == BEFORE_LINK_CLASS]
    if len(before) != 1:
        raise RuntimeError(f"expected one {BEFORE_LINK_CLASS}, found {len(before)}")
    pose = out(before[0], "Pose")
    onward = _fed(pose)
    PIN.break_pin_links(pose)
    link = _palette(ed, f"Animation|LinkedAnimGraphs|{LAYERS_ABP.rsplit('/', 1)[1]}-LinkedAnimGraph")
    # The graph node's own tag (the inner struct's is a deprecated one).
    link.set_editor_property("tag", LAYERS_TAG)
    if link_tag(link) != LAYERS_TAG or link_class(link) != layers_class_path():
        raise RuntimeError(f"the link is {link_class(link)} tagged {link_tag(link)!r}")
    _connect(pose, _pin(link, LINK_IN_PIN))
    for pin in onward:
        _connect(out(link, "Pose"), pin)
    ed.add_comment_to_nodes(
        f"The weapon layers ({LAYERS_ABP.rsplit('/', 1)[1]}, tagged {LAYERS_TAG}): the "
        "stances, the ready pose, the swings and the throw, the flinch, the aim's pitch "
        "and the support hand, over the motion matching's pose. On a server too: they "
        "move the hit bodies and the muzzle. Scripts/combat/weapon_layers.py.", [link])


# ─── The server branch ───────────────────────────────────────────────────────

def server_branches(ed):
    """The blends by bool that ServerPose drives (the sample has one of its
    own, on another flag)."""
    found = []
    for node in ed.list_all_nodes():
        if _class(node) != BRANCH_CLASS:
            continue
        flags = [PIN.get_owning_node(q) for q in _fed(_pin(node, FLAG_PIN))]
        if any(str(BEL.get_node_title(f)) == f"Get {SERVER_POSE_VAR}" for f in flags):
            found.append(node)
    return found


def _remove_server_branch(ed, events):
    for branch in server_branches(ed):
        client, onward = _fed(_pin(branch, CLIENT_PIN)), _fed(out(branch, "Pose"))
        flags = [PIN.get_owning_node(q) for q in _fed(_pin(branch, FLAG_PIN))]
        ed.remove_nodes([branch] + flags)
        for pin in onward:
            _connect(client[0], pin)
    for node in events.list_all_nodes():
        if str(BEL.get_node_title(node)) == f"Set {SERVER_POSE_VAR}":
            before, after = _fed(_pin(node, "execute")), _fed(then(node))
            asked = [PIN.get_owning_node(q) for q in _fed(_pin(node, SERVER_POSE_VAR))]
            events.remove_nodes([node] + asked)
            for a in before:
                for b in after:
                    _connect(a, b)


def eye_segment(ed):
    """(the pose pin a server takes, the pose pin a client takes, the pin both
    feed): the feet's nodes lie between the first two."""
    history = [n for n in ed.list_all_nodes() if _class(n) == HISTORY_CLASS]
    if len(history) != 1:
        raise RuntimeError(f"expected one pose history node, found {len(history)}")
    into = _pin(history[0], "Source")
    client = _fed(into)
    if not client:
        raise RuntimeError("the pose history is fed by nothing")
    tap, walked = client[0], 0
    while _class(PIN.get_owning_node(tap)) in EYE_CLASSES:
        node = PIN.get_owning_node(tap)
        source = next(p for p in BEL.list_input_pins(node)
                      if str(PIN.get_pin_name(p)) in ("ComponentPose", "LocalPose"))
        tap, walked = _fed(source)[0], walked + 1
    if walked != len(EYE_CLASSES):
        raise RuntimeError(f"the feet's segment is {walked} nodes, not {len(EYE_CLASSES)}: "
                           "the sample's graph is not the one this was written for")
    return tap, client[0], into


def _author_server_branch(ed, events):
    _declare(ed, SERVER_POSE_VAR, BOOL())
    tap, client, into = eye_segment(ed)
    PIN.break_pin_links(into)
    branch = _palette(ed, NODE_BLEND_BY_BOOL)
    flag = ed.add_get_member_variable_node(SERVER_POSE_VAR)
    _connect(out(flag, SERVER_POSE_VAR), _pin(branch, FLAG_PIN))
    _connect(tap, _pin(branch, SERVER_PIN))
    _connect(client, _pin(branch, CLIENT_PIN))
    # No blend between the arms (server_anim.py): the flag never changes.
    inner = branch.get_editor_property("node")
    inner.set_editor_property("blend_time", [0.0, 0.0])
    branch.set_editor_property("node", inner)
    _set(branch, "BlendTime_0", 0.0)
    _set(branch, "BlendTime_1", 0.0)
    _connect(out(branch, "Pose"), into)
    ed.add_comment_to_nodes(
        f"The one IsDedicatedServer branch ({SERVER_POSE_VAR}): a dedicated server takes "
        "the pose from before the feet (Foot Placement and Leg IK, which trace the ground "
        "and are for the eye), which it then neither updates nor evaluates. A new node for "
        "the eye goes on the other arm. Scripts/combat/gas_locomotion.py.", [branch, flag])
    # ServerPose = IsDedicatedServer, once: the sample's event graph has no
    # initialize event, so it gets one.
    inits = [n for n in events.list_all_nodes()
             if INIT_EVENT in str(BEL.get_node_title(n)).replace(" ", "")]
    init = inits[0] if inits else _palette(events, NODE_EVENT_INIT_ANIM)
    after = _fed(then(init))
    put = events.add_set_member_variable_node(SERVER_POSE_VAR)
    _connect(out(_node(events, FN_IS_DEDICATED_SERVER)), _pin(put, SERVER_POSE_VAR))
    PIN.break_pin_links(then(init))
    _connect(then(init), _pin(put, "execute"))
    for pin in after:
        _connect(then(put), pin)


# ─── The foley bank ──────────────────────────────────────────────────────────

def silent_foley_bank():
    """A sound bank of the sample's kind with nothing in it: what the foley
    component on the player is given (combat/install.install_foley)."""
    eas = _assets()
    bank = (eas.load_asset(FOLEY_SILENT_BANK) if eas.does_asset_exist(FOLEY_SILENT_BANK)
            else eas.duplicate_asset(FOLEY_BANK_SOURCE, FOLEY_SILENT_BANK))
    if not bank:
        raise RuntimeError(f"could not copy {FOLEY_BANK_SOURCE} to {FOLEY_SILENT_BANK}")
    bank.set_editor_property(FOLEY_BANK_TABLE, {})
    if len(bank.get_editor_property(FOLEY_BANK_TABLE)):
        raise RuntimeError(f"{FOLEY_SILENT_BANK} kept its sounds")
    eas.save_loaded_asset(bank)
    return bank


# ─── The build ───────────────────────────────────────────────────────────────

def graphs(bp):
    """(AnimGraph, EventGraph, the properties function) of the anim Blueprint."""
    eds = [BGE.get_graph_editor_by_name(bp, n)
           for n in ("AnimGraph", "EventGraph", PROPERTIES_GRAPH)]
    if not all(eds):
        raise RuntimeError(f"{bp.get_name()} lacks one of AnimGraph, EventGraph, "
                           f"{PROPERTIES_GRAPH}")
    return eds


def build_gas_locomotion():
    """Patch the sample's anim Blueprint. Idempotent: each part is taken out
    or rebuilt before it is authored."""
    eas = _assets()
    if not eas.does_asset_exist(ABP_LOCOMOTION):
        raise RuntimeError(f"{ABP_LOCOMOTION} is not here: run asset_pipeline/import_gas.py")
    bp = eas.load_asset(ABP_LOCOMOTION)
    anim, events, properties = graphs(bp)
    # The plain links back first: the fragments below find their places by
    # following them.
    unshare(anim)
    _remove_server_branch(anim, events)
    _remove_link(anim)
    remove_traversal_slot(anim, _slot(anim))
    declare(properties, ADDED_VARS)
    if not BEL.compile_blueprint(bp):
        raise RuntimeError(f"{ABP_LOCOMOTION} failed to compile before the patch")
    _author_properties(bp, properties)
    _remove_slot(anim)
    if traversal_on():
        author_traversal_slot(anim, _slot(anim))
    _author_link(anim)
    _author_server_branch(anim, events)
    # The traversal's slot and the server branch each take one pose on both
    # arms: a cached pose each, or the motion matching under them is updated
    # twice a frame while a blend has both arms in (uebp/pose_share.py).
    share(anim)
    for ed in (anim, events, properties):
        arrange(ed)
    if not BEL.compile_blueprint(bp):
        raise RuntimeError(f"{ABP_LOCOMOTION} failed to compile")
    _apply_defaults(bp, defaults(ADDED_VARS))
    eas.save_loaded_asset(bp)
    _log(f"{ABP_LOCOMOTION.rsplit('/', 1)[1]}: the sample's motion matching, reading the "
         f"CharacterMovementComponent; {LAYERS_ABP.rsplit('/', 1)[1]} linked in after the "
         "root's offset; server branch before the feet")
    return bp


def resave_gas_locomotion():
    """Compile and save the base again, once the weapon layers' graph is
    whole: the link holds that graph's class, which every builder after
    build_gas_locomotion() has recompiled."""
    bp = _assets().load_asset(ABP_LOCOMOTION)
    if not BEL.compile_blueprint(bp):
        raise RuntimeError(f"{ABP_LOCOMOTION} failed to compile over the finished layers")
    _assets().save_loaded_asset(bp)
