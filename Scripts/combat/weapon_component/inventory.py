"""The inventory: equip, drop, and BeginPlay's starting loadout. The pick-up is
pickup.py's.
"""

from combat.anim_blueprint import AIM_SLOT
from combat.graph import (
    BEL, _at, _connect, _loose_pin, _node, _palette, _pin, _set, _vec,
)
from combat.nodes import (
    CAMERA_CLASS_PATH, FN_ACTOR_LOC, FN_ADD_VV, FN_AND, FN_ANIM_INSTANCE,
    FN_ARR_ADD, FN_ARR_REMOVE, FN_ATTACH, FN_DETACH, FN_EQ_II, FN_FORWARD,
    FN_GET_COMP, FN_GET_OWNER, FN_GET_PC, FN_GET_PITCH_SCALE, FN_GET_TRANSFORM,
    FN_GET_YAW_SCALE, FN_IS_VALID, FN_MUL_VF, FN_NOT, FN_PLAY_SLOT,
    FN_SET_ACTOR_LOC, FN_SET_HIDDEN, FN_SET_REL_LOC, FN_SET_REL_ROT,
    FN_STOP_SLOT, FN_TRACE, MACRO_FOR_EACH, MOVEMENT_CLASS_PATH,
    NODE_BREAK_HIT, NODE_CAST_CHAR, NODE_SPAWN,
)
from combat.paths import ITEM_CLASS_PATH
from combat.skin import player_skin
from combat.tuning import DROP_FORWARD, DROP_KEY
from combat.weapon_component.common import AIM_BLEND, AIM_LOOPS, _prop
from combat.weapon_component.listener import _author_listener_at_character
from combat.weapon_component.sights import _author_camera_after_boom


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
    # Shown on the way out: a sniper dropped while down its scope was hidden
    # by the sight camera (sights.py), and nothing else would ever show it.
    shown = keep(_at(_node(ed, FN_SET_HIDDEN), x0 + 540, y0 - 160))
    _connect(held, _pin(shown, "self"))
    _set(shown, "bNewHidden", "false")
    _connect(BEL.find_then_pin(off), _pin(shown, "execute"))

    loc = keep(_at(_node(ed, FN_ACTOR_LOC), x0, y0 + 300))
    _connect(owner, _pin(loc, "self"))
    rot = keep(_at(_node(ed, "/Script/Engine.Actor.K2_GetActorRotation"), x0, y0 + 420))
    _connect(owner, _pin(rot, "self"))
    fwd = keep(_at(_node(ed, FN_FORWARD), x0 + 240, y0 + 420))
    _connect(_pin(rot, "ReturnValue", is_input=False), _pin(fwd, "InRot"))
    ahead = keep(_at(_node(ed, FN_MUL_VF), x0 + 480, y0 + 420))
    _connect(_pin(fwd, "ReturnValue", is_input=False), _pin(ahead, "A"))
    # A vector literal, for the same reason as the aim ray: with nothing
    # connected, this operator's B pin is a struct pin and will not take a
    # number. Until _set started reading pins back, this silently stayed empty
    # and dropped weapons landed on the player's own feet.
    _connect(_vec(ed, DROP_FORWARD, DROP_FORWARD, DROP_FORWARD, x0 + 240, y0 + 560),
             _pin(ahead, "B"))
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
    _connect(BEL.find_then_pin(shown), _pin(ground, "execute"))

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


def _author_equip(ed, exec_in, x0, y0):
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
    hand socket where it is attached. Sprint's own block in Tick raises
    NeedsRefresh on the frame the state flips, which is what routes back here.
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
    _set(attach, "SocketName", player_skin().grip)
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

    # The resting orientation only. From the next frame on, Tick points the
    # held weapon at the aim point; this just stops it being visibly wrong for
    # the one frame in between.
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
    # Safe to fold into one condition, unlike the fire gate's ammunition tests:
    # IsValid takes a null object as an answer rather than as an error, and
    # Sprinting is this component's own bool. Neither read can touch Held.
    running = keep(_at(ed.add_get_member_variable_node("Sprinting"),
                       x0 + 2700, y0 + 480))
    still = keep(_at(_node(ed, FN_NOT), x0 + 2940, y0 + 480))
    _connect(_pin(running, "Sprinting", is_input=False), _pin(still, "A"))
    shown = keep(_at(_node(ed, FN_AND), x0 + 3180, y0 + 400))
    _connect(_pin(armed, "ReturnValue", is_input=False), _pin(shown, "A"))
    _connect(_pin(still, "ReturnValue", is_input=False), _pin(shown, "B"))
    posing = keep(_at(ed.add_branch_node(), x0 + 3420, y0))
    _connect(_pin(shown, "ReturnValue", is_input=False), _pin(posing, "Condition"))
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
        "freeze mid-stride. Empty hands stop the slot and locomotion returns, "
        "and so does sprinting: you cannot fire while running, so there is "
        "nothing for a ready pose to be ready for.",
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

    # Whatever the character's own walking speed is, before sprint ever touches
    # it. Cached rather than written down here: a literal would silently fight
    # any later change to BP_ThirdPersonCharacter's movement defaults, and the
    # symptom -- "the player walks at the wrong speed, but only after
    # sprinting once" -- would point at the sprint code instead of at the copy.
    movement = keep(_at(ed.add_get_member_variable_node(
        "CharacterMovement", "/Script/Engine.Character"), 1040, -1560))
    _connect(as_char, _pin(movement, "self"))
    walk = keep(_at(ed.add_get_member_variable_node(
        "MaxWalkSpeed", MOVEMENT_CLASS_PATH), 1300, -1560))
    _connect(_pin(movement, "CharacterMovement", is_input=False), _pin(walk, "self"))
    cache = keep(_at(ed.add_set_member_variable_node("BaseSpeed"), 1300, -1420))
    _connect(_pin(walk, "MaxWalkSpeed", is_input=False), _pin(cache, "BaseSpeed"))
    _connect(BEL.find_then_pin(remember), _pin(cache, "execute"))

    # And whatever the camera's own field of view is, for the same reason and
    # with the same failure mode: a literal 90 here would silently fight the
    # camera asset, and the symptom -- "the view is subtly wrong, but only
    # after aiming once" -- would point at the ADS code rather than at the copy.
    cam = keep(_at(_node(ed, FN_GET_COMP), 1040, -1700))
    _connect(as_char, _pin(cam, "self"))
    _pin(cam, "ComponentClass").set_pin_value(CAMERA_CLASS_PATH)
    fov = keep(_at(ed.add_get_member_variable_node("FieldOfView", CAMERA_CLASS_PATH),
                   1300, -1700))
    _connect(_pin(cam, "ReturnValue", is_input=False), _pin(fov, "self"))
    fov_out = _pin(fov, "FieldOfView", is_input=False)
    base_fov = keep(_at(ed.add_set_member_variable_node("BaseFOV"), 1560, -1700))
    _connect(fov_out, _pin(base_fov, "BaseFOV"))
    _connect(BEL.find_then_pin(cache), _pin(base_fov, "execute"))
    # Start the interpolation where the camera already is, or the first frame
    # lerps from zero and the view snaps open.
    now_fov = keep(_at(ed.add_set_member_variable_node("CurrentFOV"), 1820, -1700))
    _connect(fov_out, _pin(now_fov, "CurrentFOV"))
    _connect(BEL.find_then_pin(base_fov), _pin(now_fov, "execute"))

    # And whatever the controller's own look scales already are, for the third
    # time in this function and for the third identical reason. The pitch one
    # is the reason this is a cache and not a constant: the engine ships it
    # NEGATIVE (-2.5), so any literal written here would have a one-in-two
    # chance of inverting the player's vertical look, and the symptom -- "the
    # mouse is upside down, but only after aiming once" -- would send whoever
    # chased it into the ADS code rather than into this line.
    pc = keep(_at(_node(ed, FN_GET_PC), 1040, -1840))
    _set(pc, "PlayerIndex", 0)
    pc_out = _pin(pc, "ReturnValue", is_input=False)
    yaw_now = keep(_at(_node(ed, FN_GET_YAW_SCALE), 1300, -1840))
    _connect(pc_out, _pin(yaw_now, "self"))
    keep_yaw = keep(_at(ed.add_set_member_variable_node("BaseYawScale"), 2080, -1700))
    _connect(_pin(yaw_now, "ReturnValue", is_input=False), _pin(keep_yaw, "BaseYawScale"))
    _connect(BEL.find_then_pin(now_fov), _pin(keep_yaw, "execute"))
    pitch_now = keep(_at(_node(ed, FN_GET_PITCH_SCALE), 1300, -1960))
    _connect(pc_out, _pin(pitch_now, "self"))
    keep_pitch = keep(_at(ed.add_set_member_variable_node("BasePitchScale"),
                          2340, -1700))
    _connect(_pin(pitch_now, "ReturnValue", is_input=False),
             _pin(keep_pitch, "BasePitchScale"))
    _connect(BEL.find_then_pin(keep_yaw), _pin(keep_pitch, "execute"))

    where = keep(_at(_node(ed, FN_GET_TRANSFORM), 1040, -1000))
    _connect(as_char, _pin(where, "self"))
    spawn_at = _pin(where, "ReturnValue", is_input=False)

    prev = _author_camera_after_boom(ed, as_char, BEL.find_then_pin(keep_pitch),
                                     2600, -1840)
    prev = _author_listener_at_character(ed, as_char, pc_out, prev, 3120, -1840)
    for i, var in enumerate(("ShotgunClass", "PistolClass", "KnifeClass")):
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
        "The player starts carrying the shotgun, the pistol and the knife. "
        "They are spawned here rather "
        "than placed in the level so that a generated map needs no weapon "
        "actors in it -- nothing in Scripts/generated_levels knows weapons "
        "exist. NeedsRefresh makes Tick do the actual equipping, so the attach "
        "logic is authored exactly once.",
        made)
