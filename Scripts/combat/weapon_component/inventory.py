"""The inventory: equip, drop, and BeginPlay's starting loadout. Interact is
interact.py's, and picking an item up pickup.py's.
"""

from combat.anim_blueprint import AIM_SLOT
from combat.weapon_component.look import _author_hand_pose
from combat.weapon_component.look_vars import HandPose
from uebp.graph import (
    _connect, _loose_pin, _node, _palette, _pin, _set, _vec, else_, out, then)
from combat.nodes import CAMERA_CLASS_PATH, MOVEMENT_CLASS_PATH
from combat.paths import ITEM_CLASS_PATH
from combat.skin import player_skin
from combat.slot_tuning import SLOT_VAR, STARTER_SLOTS
from combat.tuning import DROP_FORWARD, DROP_KEY
from combat.carry_tuning import LOWERED_VAR
from combat.light_tuning import MATCHES_CLASS_VAR
from combat.torch_tuning import STICK_CLASS_VAR
from combat.weapon_component.common import AIM_BLEND, AIM_LOOPS, _prop
from combat.weapon_component.sights import _author_camera_after_boom
from uebp.nodes.actor import (
    FN_ACTOR_LOC, FN_ANIM_INSTANCE, FN_ATTACH, FN_DETACH, FN_GET_COMP, FN_GET_OWNER,
    FN_GET_TRANSFORM, FN_PLAY_SLOT, FN_SET_ACTOR_LOC,
    FN_SET_HIDDEN, FN_SET_REL_LOC, FN_SET_REL_ROT, FN_STOP_SLOT)
from uebp.nodes.array import FN_ARR_ADD, FN_ARR_REMOVE
from uebp.nodes.math import FN_ADD_VV, FN_AND, FN_EQ_II, FN_FORWARD, FN_MUL_VF, FN_NOT
from uebp.nodes.palette import (
    MACRO_FOR_EACH, MACRO_SWITCH_AUTHORITY_COMP, NODE_BREAK_HIT, NODE_CAST_CHAR, NODE_SPAWN)
from uebp.nodes.system import FN_IS_VALID, FN_TRACE
from combat.sprint_tuning import BASE_SPEED_VAR
from uebp import props as EP
from combat import item_vars as IV
from combat.weapon_component import vars as WV

# What the player is issued, in bag order: the component's class variables
# BeginPlay spawns from (build.py declares and fills them).
STARTER_CLASS_VARS = (WV.ShotgunClass, WV.PistolClass, WV.KnifeClass, WV.AxeClass,
                      MATCHES_CLASS_VAR, STICK_CLASS_VAR)


def _detach_rules(node):
    # KeepWorld everywhere: a dropped weapon should stay exactly where it was in
    # world space and then be moved deliberately, not snap back to the origin.
    for rule in ("LocationRule", "RotationRule", "ScaleRule"):
        _set(node, rule, "KeepWorld")


def _author_set_down(ed, item, owner, exec_in, keep):
    """``item`` becomes a pick-up on the ground in front of ``owner``: Dropped,
    detached, shown, and set on the terrain under a point DROP_FORWARD ahead.
    The G drop's and a drag out of the inventory's (drop_request.py). Returns
    the two exec tails (landed, and left in the air over no ground)."""
    flag = keep(ed.add_set_member_variable_node(IV.Dropped, ITEM_CLASS_PATH))
    _connect(item, _pin(flag, "self"))
    _set(flag, IV.Dropped, True)
    _connect(exec_in, _pin(flag, "execute"))

    off = keep(_node(ed, FN_DETACH))
    _connect(item, _pin(off, "self"))
    _detach_rules(off)
    _connect(then(flag), _pin(off, "execute"))
    # Shown on the way out: a sniper dropped while down its scope was hidden
    # by the sight camera (sights.py), and nothing else would ever show it.
    shown = keep(_node(ed, FN_SET_HIDDEN))
    _connect(item, _pin(shown, "self"))
    _set(shown, "bNewHidden", False)
    _connect(then(off), _pin(shown, "execute"))

    loc = keep(_node(ed, FN_ACTOR_LOC))
    _connect(owner, _pin(loc, "self"))
    rot = keep(_node(ed, "/Script/Engine.Actor.K2_GetActorRotation"))
    _connect(owner, _pin(rot, "self"))
    fwd = keep(_node(ed, FN_FORWARD))
    _connect(out(rot), _pin(fwd, "InRot"))
    ahead = keep(_node(ed, FN_MUL_VF))
    _connect(out(fwd), _pin(ahead, "A"))
    # A vector literal, for the same reason as the aim ray: with nothing
    # connected, this operator's B pin is a struct pin and will not take a
    # number. Until _set started reading pins back, this silently stayed empty
    # and dropped weapons landed on the player's own feet.
    _connect(_vec(ed, DROP_FORWARD, DROP_FORWARD, DROP_FORWARD), _pin(ahead, "B"))
    start = keep(_node(ed, FN_ADD_VV))
    _connect(out(loc), _pin(start, "A"))
    _connect(out(ahead), _pin(start, "B"))

    down = keep(_node(ed, FN_ADD_VV))
    _connect(out(start), _pin(down, "A"))
    _connect(_vec(ed, 0.0, 0.0, -400.0), _pin(down, "B"))

    # Trace down so the weapon lands on the terrain instead of hanging at hip
    # height. The forest floor is a mesh, not a plane, so a fixed Z would float
    # or bury it depending on where the player is standing.
    ground = keep(_node(ed, FN_TRACE))
    _connect(out(start), _pin(ground, "Start"))
    _connect(out(down), _pin(ground, "End"))
    _set(ground, "TraceChannel", "TraceTypeQuery1")
    _set(ground, "bTraceComplex", False)
    _set(ground, "bIgnoreSelf", True)
    _set(ground, "DrawDebugType", "None")
    _connect(then(shown), _pin(ground, "execute"))

    landed = keep(ed.add_branch_node())
    _connect(out(ground), _pin(landed, "Condition"))
    _connect(then(ground), _pin(landed, "execute"))
    brk = keep(_palette(ed, NODE_BREAK_HIT))
    _connect(out(ground, "OutHit"), _loose_pin(brk, "Hit"))

    lift = keep(_node(ed, FN_ADD_VV))
    _connect(_loose_pin(brk, "Location", is_input=False), _pin(lift, "A"))
    _connect(_vec(ed, 0.0, 0.0, 12.0), _pin(lift, "B"))

    on_ground = keep(_node(ed, FN_SET_ACTOR_LOC))
    _connect(item, _pin(on_ground, "self"))
    _connect(out(lift), _pin(on_ground, "NewLocation"))
    _connect(then(landed), _pin(on_ground, "execute"))

    in_air = keep(_node(ed, FN_SET_ACTOR_LOC))
    _connect(item, _pin(in_air, "self"))
    _connect(out(start), _pin(in_air, "NewLocation"))
    _connect(else_(landed), _pin(in_air, "execute"))
    return then(on_ground), then(in_air)


def _author_drop(ed, held, owner, exec_in):
    """Detach the held weapon, drop it on the ground in front of the player."""
    made = []

    def keep(n):
        made.append(n)
        return n

    on_ground, in_air = _author_set_down(ed, held, owner, exec_in, keep)

    # Both placements rejoin here; an exec input takes more than one link.
    inv = keep(ed.add_get_member_variable_node(WV.Inventory))
    idx = keep(ed.add_get_member_variable_node(WV.EquippedIndex))
    remove = keep(_node(ed, FN_ARR_REMOVE))
    _connect(out(inv, WV.Inventory), _pin(remove, "TargetArray"))
    _connect(out(idx, WV.EquippedIndex), _pin(remove, "IndexToRemove"))
    _connect(on_ground, _pin(remove, "execute"))
    _connect(in_air, _pin(remove, "execute"))

    # Held is set with its input pin left unconnected, which is how a Blueprint
    # object variable is cleared to None.
    clear = keep(ed.add_set_member_variable_node(WV.Held))
    _connect(then(remove), _pin(clear, "execute"))
    reset = keep(ed.add_set_member_variable_node(WV.EquippedIndex))
    _set(reset, WV.EquippedIndex, 0)
    _connect(then(clear), _pin(reset, "execute"))

    ed.add_comment_to_nodes(
        f"{DROP_KEY} drops the equipped weapon {DROP_FORWARD:.0f} cm ahead, "
        "traced down onto the terrain, and takes it out of Inventory. It stays "
        "in the world as an ordinary actor with Dropped set, which is the only "
        "thing pick-up looks for.",
        made)
    return then(reset)


def _author_equip(ed, exec_in):
    """Show exactly one weapon in the hand, hide the rest, play its ready pose.

    Weapons are spawned once and kept: equipping hides and shows actors rather
    than destroying and respawning them, so a weapon keeps its identity (and
    could keep its ammo, condition, anything) across switches, and so dropping
    can hand the very same actor to the world.

    It is also where sprinting stops looking absurd. The ready pose is a
    montage in an upper-body slot; a sprinting player with it still playing
    runs with the barrel levelled at the horizon and the arms locked, which is
    the one animation complaint this project has had. The fix is not a new
    animation -- it is *not playing* this one: stop the slot, and the layered
    blend has nothing left to override the locomotion state machine with, so
    the character runs with its own run cycle and the weapon goes along in the
    hand socket where it is attached. The same now goes for a gun at rest
    (carry.py): Lowered is sprinting, or a gun nothing is holding up, and the
    pose edge in Tick (ready_pose.py) raises NeedsRefresh on the frame it
    flips, which is what routes back here.
    """
    made = []

    def keep(n):
        made.append(n)
        return n

    inv = keep(ed.add_get_member_variable_node(WV.Inventory))
    loop = ed.add_macro_node(MACRO_FOR_EACH)
    if not loop:
        raise RuntimeError("could not create the ForEachLoop macro node")
    keep(loop)
    _connect(out(inv, WV.Inventory), _loose_pin(loop, "Array"))
    # Empty first: with EquippedIndex -1 (nothing in the hand slot) no turn of
    # the loop sets Held, and the hands are empty rather than still holding
    # what was put away.
    empty = keep(ed.add_set_member_variable_node(WV.Held))
    _connect(exec_in, _pin(empty, "execute"))
    _connect(then(empty), _loose_pin(loop, "Exec"))
    item = _loose_pin(loop, "ArrayElement", is_input=False)

    idx = keep(ed.add_get_member_variable_node(WV.EquippedIndex))
    same = keep(_node(ed, FN_EQ_II))
    _connect(_loose_pin(loop, "ArrayIndex", is_input=False), _pin(same, "A"))
    _connect(out(idx, WV.EquippedIndex), _pin(same, "B"))

    chosen = keep(ed.add_branch_node())
    _connect(out(same), _pin(chosen, "Condition"))
    _connect(_loose_pin(loop, "LoopBody", is_input=False), _pin(chosen, "execute"))

    show = keep(_node(ed, FN_SET_HIDDEN))
    _connect(item, _pin(show, "self"))
    _set(show, "bNewHidden", False)
    _connect(then(chosen), _pin(show, "execute"))

    hide = keep(_node(ed, FN_SET_HIDDEN))
    _connect(item, _pin(hide, "self"))
    _set(hide, "bNewHidden", True)
    _connect(else_(chosen), _pin(hide, "execute"))

    mesh = keep(ed.add_get_member_variable_node(WV.OwnerMesh))
    attach = keep(_node(ed, FN_ATTACH))
    _connect(item, _pin(attach, "self"))
    _connect(out(mesh, WV.OwnerMesh), _pin(attach, "Parent"))
    _set(attach, "SocketName", player_skin().grip)
    # Snap first, then apply the weapon's own grip offset explicitly. Snapping
    # gives a known starting transform; KeepRelative would carry over whatever
    # the actor happened to be at, which after a drop is a world position.
    for rule in ("LocationRule", "RotationRule", "ScaleRule"):
        _set(attach, rule, "SnapToTarget")
    _connect(then(show), _pin(attach, "execute"))

    gl_pin, gl_n = _prop(ed, IV.GripLocation, item)
    keep(gl_n)
    put = keep(_node(ed, FN_SET_REL_LOC))
    _connect(item, _pin(put, "self"))
    _connect(gl_pin, _pin(put, "NewRelativeLocation"))
    _connect(then(attach), _pin(put, "execute"))

    # The resting orientation only. From the next frame on, Tick points the
    # held weapon at the aim point; this just stops it being visibly wrong for
    # the one frame in between.
    gr_pin, gr_n = _prop(ed, IV.GripRotation, item)
    keep(gr_n)
    turn = keep(_node(ed, FN_SET_REL_ROT))
    _connect(item, _pin(turn, "self"))
    _connect(gr_pin, _pin(turn, "NewRelativeRotation"))
    _connect(then(put), _pin(turn, "execute"))

    hold = keep(ed.add_set_member_variable_node(WV.Held))
    _connect(item, _pin(hold, WV.Held))
    _connect(then(turn), _pin(hold, "execute"))

    # --- once the loop is done, drive the ready pose -------------------------
    # The pose is HandPose (look.py): Held's AimPose where this machine's
    # player holds it, taken here; on a copy of another machine's player it is
    # the pose that player's machine reported, and Held is not read for it.
    taken = _author_hand_pose(ed, _loose_pin(loop, "Completed", is_input=False))
    pose_get = keep(ed.add_get_member_variable_node(HandPose))
    pose_pin = out(pose_get, HandPose)
    armed = keep(_node(ed, FN_IS_VALID))
    _connect(pose_pin, _pin(armed, "Object"))
    # Safe to fold into one condition, unlike the fire gate's ammunition tests:
    # IsValid takes a null object as an answer rather than as an error, and
    # Lowered is this component's own bool (carry.py: sprinting, or a gun
    # nothing is holding up). Neither read can touch Held.
    running = keep(ed.add_get_member_variable_node(LOWERED_VAR))
    still = keep(_node(ed, FN_NOT))
    _connect(out(running, LOWERED_VAR), _pin(still, "A"))
    shown = keep(_node(ed, FN_AND))
    _connect(out(armed), _pin(shown, "A"))
    _connect(out(still), _pin(shown, "B"))
    posing = keep(ed.add_branch_node())
    _connect(out(shown), _pin(posing, "Condition"))
    for e in taken:
        _connect(e, _pin(posing, "execute"))

    mesh2 = keep(ed.add_get_member_variable_node(WV.OwnerMesh))
    anim = keep(_node(ed, FN_ANIM_INSTANCE))
    _connect(out(mesh2, WV.OwnerMesh), _pin(anim, "self"))
    anim_out = out(anim)

    play = keep(_node(ed, FN_PLAY_SLOT))
    _connect(anim_out, _pin(play, "self"))
    _connect(pose_pin, _pin(play, "Asset"))
    _set(play, "SlotNodeName", AIM_SLOT)
    _set(play, "BlendInTime", AIM_BLEND)
    _set(play, "BlendOutTime", AIM_BLEND)
    _set(play, "InPlayRate", 1.0)
    _set(play, "LoopCount", AIM_LOOPS)
    _connect(then(posing), _pin(play, "execute"))

    stop = keep(_node(ed, FN_STOP_SLOT))
    _connect(anim_out, _pin(stop, "self"))
    _set(stop, "InBlendOutTime", AIM_BLEND)
    _set(stop, "SlotNodeName", AIM_SLOT)
    _connect(else_(posing), _pin(stop, "execute"))

    ed.add_comment_to_nodes(
        f"The ready pose is the weapon's own AimPose (HandPose) played into {AIM_SLOT}, "
        f"looping {AIM_LOOPS} times because PlaySlotAnimationAsDynamicMontage "
        "has no infinite option. It reads as a pose rather than a full-body "
        "animation only because patch_anim_blueprint() put a spine_01 layered "
        "blend around that slot in ABP_Unarmed -- without it the legs would "
        "freeze mid-stride. Empty hands stop the slot and locomotion returns, "
        "and so does Lowered: sprinting, or a gun that no aim key, guard or "
        "shot is holding up (carry.py).",
        made)


def _author_wc_begin_play(ed, begin):
    """Cache the character's mesh, spawn the starting loadout into its slots."""
    made = []

    def keep(n):
        made.append(n)
        return n

    owner = keep(_node(ed, FN_GET_OWNER))
    cast = keep(_palette(ed, NODE_CAST_CHAR))
    _connect(out(owner), _pin(cast, "Object"))
    _connect(then(begin), _pin(cast, "execute"))
    as_char = _loose_pin(cast, "AsBPThirdPersonCharacter", is_input=False)

    mesh = keep(ed.add_get_member_variable_node(EP.MESH, "/Script/Engine.Character"))
    _connect(as_char, _pin(mesh, "self"))
    remember = keep(ed.add_set_member_variable_node(WV.OwnerMesh))
    _connect(out(mesh, "Mesh"), _pin(remember, WV.OwnerMesh))
    _connect(then(cast), _pin(remember, "execute"))

    # Whatever the character's own walking speed is, before sprint ever touches
    # it. Cached rather than written down here: a literal would silently fight
    # any later change to BP_ThirdPersonCharacter's movement defaults, and the
    # symptom -- "the player walks at the wrong speed, but only after
    # sprinting once" -- would point at the sprint code instead of at the copy.
    movement = keep(ed.add_get_member_variable_node(
        EP.CHARACTER_MOVEMENT, "/Script/Engine.Character"))
    _connect(as_char, _pin(movement, "self"))
    walk = keep(ed.add_get_member_variable_node(EP.MAX_WALK_SPEED, MOVEMENT_CLASS_PATH))
    _connect(out(movement, "CharacterMovement"), _pin(walk, "self"))
    cache = keep(ed.add_set_member_variable_node(BASE_SPEED_VAR))
    _connect(out(walk, "MaxWalkSpeed"), _pin(cache, "BaseSpeed"))
    _connect(then(remember), _pin(cache, "execute"))

    # And whatever the camera's own field of view is, for the same reason and
    # with the same failure mode: a literal 90 here would silently fight the
    # camera asset, and the symptom -- "the view is subtly wrong, but only
    # after aiming once" -- would point at the ADS code rather than at the copy.
    cam = keep(_node(ed, FN_GET_COMP))
    _connect(as_char, _pin(cam, "self"))
    _pin(cam, "ComponentClass").set_pin_value(CAMERA_CLASS_PATH)
    fov = keep(ed.add_get_member_variable_node(EP.FIELD_OF_VIEW, CAMERA_CLASS_PATH))
    _connect(out(cam), _pin(fov, "self"))
    fov_out = out(fov, "FieldOfView")
    base_fov = keep(ed.add_set_member_variable_node(WV.BaseFOV))
    _connect(fov_out, _pin(base_fov, WV.BaseFOV))
    _connect(then(cache), _pin(base_fov, "execute"))
    # Start the interpolation where the camera already is, or the first frame
    # lerps from zero and the view snaps open.
    now_fov = keep(ed.add_set_member_variable_node(WV.CurrentFOV))
    _connect(fov_out, _pin(now_fov, WV.CurrentFOV))
    _connect(then(base_fov), _pin(now_fov, "execute"))

    # The controller's own look scales, and the listener it hears from, are
    # taken on the first frame the character is locally controlled (local.py):
    # a pawn may have no controller yet here.
    where = keep(_node(ed, FN_GET_TRANSFORM))
    _connect(as_char, _pin(where, "self"))
    spawn_at = out(where)

    # The loadout is the server's to issue (and single player's): a client's
    # items are made from the record it is sent (view.py).
    prev = _author_camera_after_boom(ed, as_char, then(now_fov))
    owns = keep(ed.add_macro_node(MACRO_SWITCH_AUTHORITY_COMP))
    _connect(prev, _pin(owns, "execute"))
    prev = out(owns, "Authority")
    for i, var in enumerate(STARTER_CLASS_VARS):
        cls = keep(ed.add_get_member_variable_node(var))
        spawn = keep(_palette(ed, NODE_SPAWN))
        _connect(out(cls, var), _pin(spawn, "Class"))
        _connect(spawn_at, _pin(spawn, "SpawnTransform"))
        _set(spawn, "CollisionHandlingOverride", "AlwaysSpawn")
        _connect(prev, _pin(spawn, "execute"))

        inv = keep(ed.add_get_member_variable_node(WV.Inventory))
        add = keep(_node(ed, FN_ARR_ADD))
        _connect(out(inv, WV.Inventory), _pin(add, "TargetArray"))
        _connect(out(spawn), _pin(add, "NewItem"))
        _connect(then(spawn), _pin(add, "execute"))
        # Its slot (slot_tuning.STARTER_SLOTS): the slot sync places it there.
        slot = keep(ed.add_set_member_variable_node(SLOT_VAR, ITEM_CLASS_PATH))
        _connect(out(spawn), _pin(slot, "self"))
        _set(slot, SLOT_VAR, STARTER_SLOTS[i])
        _connect(then(add), _pin(slot, "execute"))
        prev = then(slot)

    dirty = keep(ed.add_set_member_variable_node(WV.NeedsRefresh))
    _set(dirty, WV.NeedsRefresh, True)
    _connect(prev, _pin(dirty, "execute"))
    _connect(out(owns, "Remote"), _pin(dirty, "execute"))

    ed.add_comment_to_nodes(
        "With authority (the server, and single player; a client's are a picture of "
        "the server's record, view.py): the player starts carrying the shotgun, the pistol, the knife, the "
        "axe, the matches and a stick, each given its slot: the shotgun in "
        "hand, the pistol and the knife in theirs, the rest in the bag. "
        "They are spawned here rather "
        "than placed in the level so that a generated map needs no weapon "
        "actors in it -- nothing in Scripts/generated_levels knows weapons "
        "exist. NeedsRefresh makes Tick do the actual equipping, so the attach "
        "logic is authored exactly once.",
        made)
