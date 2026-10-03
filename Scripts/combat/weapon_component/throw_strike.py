"""What a thrown blade does to what its flight strikes: it wounds a body and
stays in it, and it lodges in a tree.

The flight (throw_flight.py) calls in here on the frame its segment trace
hits something, before it sets the item down:

    Thrown.ThrowDamage > 0                       (else it falls, as any item)
      --> the struck actor has a BP_HealthComponent: a body
            ThrowBone = None; the body is a Character, and a trace of its
            mesh finds one of its physics bodies: on along the blade's own
            line or, that missing, from the hit towards its nearest bone
              --> ThrowBone = that body's bone, ThrowSkin = where on it
            Health -= ThrowDamage, times the body's HeadMultiplier where
            ThrowBone is one of its HeadBones; stamped as a pellet hit is;
            blood at the wound
            ThrowBone is a bone
              --> the item set into the body there, and attached to that
                  bone --> lodged
              (else it falls at the body's foot)
      --> else the struck component is an instanced mesh: a tree (chop.py
          says why that is the test)
            the hit no higher than LODGE_MAX_HEIGHT_CM over the tree's foot
              --> chips off the bark; the item set into the trunk --> lodged

ThrowDamage is the item's own (throw_tuning.py): 0 on the base, so a thrown
gun, mushroom or canteen does neither and comes to rest as it always did.

A BLADE IN THE HEAD does more: the damage is times the struck body's own
HeadMultiplier (hit_zones.py: the pellet's) where the bone the blade is set
into is one of its HeadBones. That bone is the one the item is then attached
to, so what the player sees is what was counted: a blade left in the head was
a head shot. So the body's skin is found before the wound, and ThrowBone
carries the bone from there to the wound and to the attach (None: it could
not be set into the body). Only the head: a limb takes the blade whole, and
there is no hot blade's double, which is the blow's.

LODGED, the item is where the flight left it, turned and set by its own
LodgeTurn and LodgePoint (combat/lodge.py): its X along the segment it
just flew, after a turn of its own that takes its point or its bit onto X, and
placed so that LodgePoint is on the bark. The flight then flags it Dropped
without the fall to the ground, so it hangs in the tree and E takes it back
like any item lying about. The height is measured from the tree instance's own
origin, which is the foot of its trunk on the ground, not by a trace, which a
branch under the hit would stop. Higher than the pick-up could reach, it
glances off and falls to the foot of the tree.

IN A BODY it is set the same way, and then attached to the bone it struck
(_author_stick), keeping where it is: it goes where the body goes, walking or
fallen, a pick-up all the while, and E takes it back from within reach of it
(pickup.py detaches what it takes). The flight's hit is on the capsule, which
is far wider than the model (hit_zones.make_shootable), so where on the body
is a trace of the mesh's physics bodies alone (_author_skin). First on along
the blade's own line: from that hit the way the segment flew, and
STICK_LINE_REACH_CM far, not the segment itself, which is one frame long and
may end short of the model. What that strikes is what the blade struck: aimed
at the head, it is in the head. A blade can also cross the capsule beside the
model, which has wounded the body all the same: then the trace is from the hit
towards the bone nearest it and STICK_TRACE_PAST times as far, the model's
skin nearest where the blade came in, and the bone that skin moves with. (The
nearest bone alone would not do for the first: it is nearest the point of the
capsule the blade came in at, not what the blade was going to.) A corpse's
lifespan ends with the item still
in it: the engine detaches an actor's attached actors as it destroys it, so
the item is left where the corpse lay.

THE FALL PASSES THE BODY BY. A body the blade could not be set into (it is no
Character, or the trace found no physics body) drops it at its foot, as every
body used to. The flight's way down is a trace from beside what was struck,
and a body's arm or knee under that point would catch the item and leave it
in the air once the body walked on. ThrowPast is what that trace ignores:
emptied here every time, and given such a body. (It is an array variable
because the trace's ignore list is one, and a wall or the ground struck must
not be in it.)

Thrown is valid throughout: the flight's gate asked.

Owns ThrowPast, which build.py declares and the flight's ground trace reads,
and ThrowBone and ThrowSkin, which build.py declares too.
"""

from combat.game_state import DAMAGED_BY_PLAYER_VAR, LAST_DAMAGE_VAR
from combat.graph import BEL, _connect, _loose_pin, _node, _palette, _pin, _set, _vec
from uebp.graph import out
from combat.hit_reaction import LAST_HIT_FROM_VAR
from combat.hit_zones import HEAD_BONES_VAR, HEAD_MULT_VAR
from combat.nodes import (
    FN_ADD_VV, FN_ARR_ADD, FN_ARR_CONTAINS, FN_ATTACH, FN_BREAK_VECTOR, FN_CLAMP,
    FN_GET_COMP, FN_GREATER_FF, FN_LE_FF, FN_MAKE_TRANSFORM, FN_MUL_FF, FN_MUL_VF,
    FN_NORMAL, FN_ROT_FROM_X, FN_SELECT_FF, FN_SUB_FF, FN_SUB_VV, FN_TIME_SECONDS,
    FN_TRACE_COMPONENT, INF, NODE_CAST_CHARACTER, NODE_CAST_HEALTH, NODE_SPAWN,
)
from combat.paths import HEALTH_CLASS_PATH
from combat.throw_tuning import (
    LODGE_MAX_HEIGHT_CM, LODGE_POINT_VAR, LODGE_TURN_VAR, STICK_LINE_REACH_CM,
    STICK_TRACE_PAST, THROW_DAMAGE_VAR,
)
from combat.weapon_component.common import _prop
from combat.weapon_component.surface_impact import _author_surface_impact

THROW_PAST_VAR = "ThrowPast"          # the actors the fall to the ground ignores
# The bone of the body the blade is set into, a Name on the component: None
# for a body it cannot be set into. Written before the wound, which reads it
# for the head, and read again after it by the attach. ThrowSkin is the point
# of that bone's body the blade struck: where it is set.
THROW_BONE_VAR = "ThrowBone"
THROW_SKIN_VAR = "ThrowSkin"

NODE_CAST_INSTANCED = "Utilities|Casting|CastToInstancedStaticMeshComponent"
FN_INSTANCE_TRANSFORM = "/Script/Engine.InstancedStaticMeshComponent.GetInstanceTransform"
FN_BREAK_TRANSFORM = "/Script/Engine.KismetMathLibrary.BreakTransform"
FN_COMPOSE_ROT = "/Script/Engine.KismetMathLibrary.ComposeRotators"
FN_ROTATE_VECTOR = "/Script/Engine.KismetMathLibrary.GreaterGreater_VectorRotator"
FN_ARR_CLEAR = "/Script/Engine.KismetArrayLibrary.Array_Clear"
FN_SET_LOC_ROT = "/Script/Engine.Actor.K2_SetActorLocationAndRotation"
FN_CLOSEST_BONE = "/Script/Engine.SkinnedMeshComponent.FindClosestBone_K2"
FN_NE_NAME = "/Script/Engine.KismetMathLibrary.NotEqual_NameName"


def _hit(brk, name):
    return _loose_pin(brk, name, is_input=False)


def _z(ed, vector):
    parts = _node(ed, FN_BREAK_VECTOR)
    _connect(vector, _pin(parts, "InVec"))
    return out(parts, "Z")


def _head_worth(ed, as_health, damage):
    """``damage`` on this body where ThrowBone says the blade went in: times
    its HeadMultiplier in one of its HeadBones, as it is anywhere else. A pure
    float pin, and the nodes."""
    bone = ed.add_get_member_variable_node(THROW_BONE_VAR)
    heads, heads_n = _prop(ed, HEAD_BONES_VAR, as_health, HEALTH_CLASS_PATH)
    in_head = _node(ed, FN_ARR_CONTAINS)
    _connect(heads, _loose_pin(in_head, "TargetArray"))
    _connect(out(bone, THROW_BONE_VAR), _loose_pin(in_head, "ItemToFind"))
    worth, worth_n = _prop(ed, HEAD_MULT_VAR, as_health, HEALTH_CLASS_PATH)
    scale = _node(ed, FN_SELECT_FF)
    _connect(worth, _pin(scale, "A"))
    _set(scale, "B", 1.0)
    _connect(out(in_head), _pin(scale, "bPickA"))
    dealt = _node(ed, FN_MUL_FF)
    _connect(damage, _pin(dealt, "A"))
    _connect(out(scale), _pin(dealt, "B"))
    return out(dealt), [bone, heads_n, in_head, worth_n, scale, dealt]


def _author_wound(ed, as_health, damage, brk, execs):
    """Take ``damage`` off the body and leave the three stamps a pellet does
    (impact.py): the health bar, the kill's credit, which way the flinch
    goes. Returns the exec pin after them, and the nodes."""
    get_h = ed.add_get_member_variable_node("Health", HEALTH_CLASS_PATH)
    _connect(as_health, _pin(get_h, "self"))
    sub = _node(ed, FN_SUB_FF)
    _connect(out(get_h, "Health"), _pin(sub, "A"))
    _connect(damage, _pin(sub, "B"))
    clamp = _node(ed, FN_CLAMP)
    _connect(out(sub), _pin(clamp, "Value"))
    _set(clamp, "Min", 0.0)
    _set(clamp, "Max", INF)
    set_h = ed.add_set_member_variable_node("Health", HEALTH_CLASS_PATH)
    _connect(as_health, _pin(set_h, "self"))
    _connect(out(clamp), _pin(set_h, "Health"))
    for pin in execs:
        _connect(pin, _pin(set_h, "execute"))
    now = _node(ed, FN_TIME_SECONDS)
    stamp = ed.add_set_member_variable_node(LAST_DAMAGE_VAR, HEALTH_CLASS_PATH)
    _connect(as_health, _pin(stamp, "self"))
    _connect(out(now), _pin(stamp, LAST_DAMAGE_VAR))
    _connect(BEL.find_then_pin(set_h), _pin(stamp, "execute"))
    blame = ed.add_set_member_variable_node(DAMAGED_BY_PLAYER_VAR, HEALTH_CLASS_PATH)
    _connect(as_health, _pin(blame, "self"))
    _set(blame, DAMAGED_BY_PLAYER_VAR, "true")
    _connect(BEL.find_then_pin(stamp), _pin(blame, "execute"))
    from_where = ed.add_set_member_variable_node(LAST_HIT_FROM_VAR, HEALTH_CLASS_PATH)
    _connect(as_health, _pin(from_where, "self"))
    _connect(_hit(brk, "ImpactNormal"), _pin(from_where, LAST_HIT_FROM_VAR))
    _connect(BEL.find_then_pin(blame), _pin(from_where, "execute"))
    return BEL.find_then_pin(from_where), [set_h, stamp, blame, from_where]


def _author_lodge(ed, thrown, brk, on, exec_in):
    """Set the item into what it struck: its X along the segment it just
    flew, after its own LodgeTurn, and its LodgePoint on ``on`` (a point of
    the world: the bark, the skin). Returns the exec pin after it, and the
    node."""
    flew = _node(ed, FN_SUB_VV)
    _connect(_hit(brk, "TraceEnd"), _pin(flew, "A"))
    _connect(_hit(brk, "TraceStart"), _pin(flew, "B"))
    along = _node(ed, FN_NORMAL)
    _connect(out(flew), _pin(along, "A"))
    into = _node(ed, FN_ROT_FROM_X)
    _connect(out(along), _pin(into, "X"))
    own, _own_n = _prop(ed, LODGE_TURN_VAR, thrown)
    # ComposeRotators applies A first: the item's own turn, then the throw's.
    pose = _node(ed, FN_COMPOSE_ROT)
    _connect(own, _pin(pose, "A"))
    _connect(out(into), _pin(pose, "B"))
    point, _point_n = _prop(ed, LODGE_POINT_VAR, thrown)
    reach = _node(ed, FN_ROTATE_VECTOR)
    _connect(point, _pin(reach, "A"))
    _connect(out(pose), _pin(reach, "B"))
    at = _node(ed, FN_SUB_VV)
    _connect(on, _pin(at, "A"))
    _connect(out(reach), _pin(at, "B"))
    put = _node(ed, FN_SET_LOC_ROT)
    _connect(thrown, _pin(put, "self"))
    _connect(out(at), _pin(put, "NewLocation"))
    _connect(out(pose), _pin(put, "NewRotation"))
    _connect(exec_in, _pin(put, "execute"))
    return BEL.find_then_pin(put), put


def _body_trace(ed, mesh_out, start, end, exec_in):
    """One trace of the mesh's physics bodies alone, and the Branch on
    whether it struck one. Returns (the trace, the Branch)."""
    skin = _node(ed, FN_TRACE_COMPONENT)
    _connect(mesh_out, _pin(skin, "self"))
    _connect(start, _pin(skin, "TraceStart"))
    _connect(end, _pin(skin, "TraceEnd"))
    # Simple collision: the physics asset's bodies, each of which names its bone.
    _set(skin, "bTraceComplex", "false")
    _set(skin, "bShowTrace", "false")
    _set(skin, "bPersistentShowTrace", "false")
    _connect(exec_in, _pin(skin, "execute"))
    found = ed.add_branch_node()
    _connect(out(skin), _pin(found, "Condition"))
    _connect(BEL.find_then_pin(skin), _pin(found, "execute"))
    return skin, found


def _note(ed, skin, exec_in):
    """ThrowBone, ThrowSkin := what the trace ``skin`` struck. Returns the
    exec pin after them, and the two nodes."""
    bone = ed.add_set_member_variable_node(THROW_BONE_VAR)
    _connect(out(skin, "BoneName"), _pin(bone, THROW_BONE_VAR))
    _connect(exec_in, _pin(bone, "execute"))
    at = ed.add_set_member_variable_node(THROW_SKIN_VAR)
    _connect(out(skin, "HitLocation"), _pin(at, THROW_SKIN_VAR))
    _connect(BEL.find_then_pin(bone), _pin(at, "execute"))
    return BEL.find_then_pin(at), [bone, at]


def _author_skin(ed, brk, exec_in):
    """Where on the body the blade went in, before the wound: ThrowBone and
    ThrowSkin := the bone and the point of the physics body the blade's own
    line strikes, or failing that the one a trace towards the nearest bone
    does; ThrowBone left None for a body that is no Character, or where both
    find nothing. Returns (the exec pins it leaves by, the mesh, the nodes)."""
    none = ed.add_set_member_variable_node(THROW_BONE_VAR)
    _connect(exec_in, _pin(none, "execute"))    # its pin left at None
    as_char = _palette(ed, NODE_CAST_CHARACTER)
    _connect(_hit(brk, "HitActor"), _pin(as_char, "Object"))
    _connect(BEL.find_then_pin(none), _pin(as_char, "execute"))
    mesh = ed.add_get_member_variable_node("Mesh", "/Script/Engine.Character")
    _connect(_loose_pin(as_char, "AsCharacter", is_input=False), _pin(mesh, "self"))
    mesh_out = out(mesh, "Mesh")

    # The blade's own line: on from the capsule's hit the way the segment
    # flew, far enough to cross the capsule. What that strikes is what the
    # blade struck, the head or a hand.
    flew = _node(ed, FN_SUB_VV)
    _connect(_hit(brk, "TraceEnd"), _pin(flew, "A"))
    _connect(_hit(brk, "TraceStart"), _pin(flew, "B"))
    along = _node(ed, FN_NORMAL)
    _connect(out(flew), _pin(along, "A"))
    on = _node(ed, FN_MUL_VF)
    _connect(out(along), _pin(on, "A"))
    r = STICK_LINE_REACH_CM
    _connect(_vec(ed, r, r, r), _pin(on, "B"))
    through = _node(ed, FN_ADD_VV)
    _connect(_hit(brk, "ImpactPoint"), _pin(through, "A"))
    _connect(out(on), _pin(through, "B"))
    line, struck = _body_trace(ed, mesh_out, _hit(brk, "ImpactPoint"), out(through),
                               BEL.find_then_pin(as_char))
    on_line, line_nodes = _note(ed, line, BEL.find_then_pin(struck))

    # It crossed the capsule beside the model, and has wounded it all the
    # same: the way in is then towards the nearest bone that has a body, and
    # on past it.
    step = BEL.find_else_pin(struck)
    near = _node(ed, FN_CLOSEST_BONE)
    _connect(mesh_out, _pin(near, "self"))
    _connect(_hit(brk, "ImpactPoint"), _pin(near, "TestLocation"))
    _set(near, "bRequirePhysicsAsset", "true")
    # Const, so pure here; were it ever given an exec pin, it goes in the chain.
    runs = BEL.find_input_pin(near, "execute")
    if runs and runs.is_valid():
        _connect(step, runs)
        step = BEL.find_then_pin(near)
    inward = _node(ed, FN_SUB_VV)
    _connect(out(near, "BoneLocation"), _pin(inward, "A"))
    _connect(_hit(brk, "ImpactPoint"), _pin(inward, "B"))
    far = _node(ed, FN_MUL_VF)
    _connect(out(inward), _pin(far, "A"))
    s = STICK_TRACE_PAST
    _connect(_vec(ed, s, s, s), _pin(far, "B"))
    end = _node(ed, FN_ADD_VV)
    _connect(_hit(brk, "ImpactPoint"), _pin(end, "A"))
    _connect(out(far), _pin(end, "B"))
    skin, found = _body_trace(ed, mesh_out, _hit(brk, "ImpactPoint"), out(end), step)
    nearest, near_nodes = _note(ed, skin, BEL.find_then_pin(found))
    return ((on_line, nearest, _loose_pin(as_char, "CastFailed", is_input=False),
             BEL.find_else_pin(found)),
            mesh_out,
            [none, as_char, line, struck, skin, found] + line_nodes + near_nodes)


def _author_stick(ed, thrown, brk, mesh_out, exec_in):
    """Leave the item in the body it wounded, if _author_skin found where
    (ThrowBone is a bone): set into the model at ThrowSkin, and attached to
    that bone. Returns (the exec pin a stuck item leaves by, the one an item
    that could not be set leaves by, the nodes)."""
    bone = ed.add_get_member_variable_node(THROW_BONE_VAR)
    is_set = _node(ed, FN_NE_NAME)
    _connect(out(bone, THROW_BONE_VAR), _pin(is_set, "A"))   # B is left at None
    found = ed.add_branch_node()
    _connect(out(is_set), _pin(found, "Condition"))
    _connect(exec_in, _pin(found, "execute"))
    at = ed.add_get_member_variable_node(THROW_SKIN_VAR)
    set_in, put = _author_lodge(ed, thrown, brk, out(at, THROW_SKIN_VAR), BEL.find_then_pin(found))
    hold = _node(ed, FN_ATTACH)
    _connect(thrown, _pin(hold, "self"))
    _connect(mesh_out, _pin(hold, "Parent"))
    _connect(out(bone, THROW_BONE_VAR), _pin(hold, "SocketName"))
    # Where the lodge just put it, and its own size on a scaled model.
    for rule in ("LocationRule", "RotationRule", "ScaleRule"):
        _set(hold, rule, "KeepWorld")
    _connect(set_in, _pin(hold, "execute"))
    return BEL.find_then_pin(hold), BEL.find_else_pin(found), [found, put, hold]


def _author_throw_strike(ed, thrown, brk, exec_in):
    """The flight's segment struck something (``brk`` is that hit, broken):
    a blade wounds a body and stays in it, and lodges in a tree. Returns
    (falls, lodged): the exec pins an item that still has to come down to the
    ground leaves by, and the ones an item left in what it struck leaves by."""
    damage, damage_n = _prop(ed, THROW_DAMAGE_VAR, thrown)
    sharp = _node(ed, FN_GREATER_FF)
    _connect(damage, _pin(sharp, "A"))        # B is left at its default, 0
    bites = ed.add_branch_node()
    _connect(out(sharp), _pin(bites, "Condition"))
    past = ed.add_get_member_variable_node(THROW_PAST_VAR)
    fresh = _node(ed, FN_ARR_CLEAR)
    _connect(out(past, THROW_PAST_VAR), _pin(fresh, "TargetArray"))
    _connect(exec_in, _pin(fresh, "execute"))
    _connect(BEL.find_then_pin(fresh), _pin(bites, "execute"))

    # --- a body: the wound, and blood out of it --------------------------------
    comp = _node(ed, FN_GET_COMP)
    _connect(_hit(brk, "HitActor"), _pin(comp, "self"))
    _pin(comp, "ComponentClass").set_pin_value(HEALTH_CLASS_PATH)
    body = _palette(ed, NODE_CAST_HEALTH)
    _connect(out(comp), _pin(body, "Object"))
    _connect(BEL.find_then_pin(bites), _pin(body, "execute"))
    as_health = _loose_pin(body, "AsBPHealthComponent", is_input=False)
    # Where it went in comes first: the wound asks whether that is the head.
    known, mesh_out, skin_nodes = _author_skin(ed, brk, BEL.find_then_pin(body))
    dealt, worth_nodes = _head_worth(ed, as_health, damage)
    wounded, wound_nodes = _author_wound(ed, as_health, dealt, brk, known)
    # The one transform serves the blood and the chips, as a pellet's does:
    # the hit, +X turned out along the surface normal.
    facing = _node(ed, FN_ROT_FROM_X)
    _connect(_hit(brk, "ImpactNormal"), _pin(facing, "X"))
    where = _node(ed, FN_MAKE_TRANSFORM)
    _connect(_hit(brk, "ImpactPoint"), _pin(where, "Location"))
    _connect(out(facing), _pin(where, "Rotation"))
    blood_cls = ed.add_get_member_variable_node("BloodClass")
    blood = _palette(ed, NODE_SPAWN)
    _connect(out(blood_cls, "BloodClass"), _pin(blood, "Class"))
    _connect(out(where), _pin(blood, "SpawnTransform"))
    _set(blood, "CollisionHandlingOverride", "AlwaysSpawn")
    _connect(wounded, _pin(blood, "execute"))
    # ...and the blade stays in the body. One it cannot be set into drops
    # it, and that fall to the ground passes the body by.
    stuck, dropped, stick_nodes = _author_stick(ed, thrown, brk, mesh_out, BEL.find_then_pin(blood))
    aside = _node(ed, FN_ARR_ADD)
    _connect(out(past, THROW_PAST_VAR), _pin(aside, "TargetArray"))
    _connect(_hit(brk, "HitActor"), _pin(aside, "NewItem"))
    _connect(dropped, _pin(aside, "execute"))

    # --- a tree, struck low enough to be taken back -----------------------------
    tree = _palette(ed, NODE_CAST_INSTANCED)
    _connect(_hit(brk, "HitComponent"), _pin(tree, "Object"))
    _connect(_loose_pin(body, "CastFailed", is_input=False), _pin(tree, "execute"))
    step = BEL.find_then_pin(tree)
    stands = _node(ed, FN_INSTANCE_TRANSFORM)
    _connect(_loose_pin(tree, "AsInstancedStaticMeshComponent", is_input=False),
             _pin(stands, "self"))
    _connect(_hit(brk, "HitItem"), _pin(stands, "InstanceIndex"))
    _set(stands, "bWorldSpace", "true")
    # Const, so pure here; were it ever given an exec pin, it goes in the chain.
    runs = BEL.find_input_pin(stands, "execute")
    if runs and runs.is_valid():
        _connect(step, runs)
        step = BEL.find_then_pin(stands)
    foot = _node(ed, FN_BREAK_TRANSFORM)
    _connect(out(stands, "OutInstanceTransform"), _pin(foot, "InTransform"))
    up = _node(ed, FN_SUB_FF)
    _connect(_z(ed, _hit(brk, "ImpactPoint")), _pin(up, "A"))
    _connect(_z(ed, out(foot, "Location")), _pin(up, "B"))
    low = _node(ed, FN_LE_FF)
    _connect(out(up), _pin(low, "A"))
    _set(low, "B", LODGE_MAX_HEIGHT_CM)
    reachable = ed.add_branch_node()
    _connect(out(low), _pin(reachable, "Condition"))
    _connect(step, _pin(reachable, "execute"))
    _cls, chipped = _author_surface_impact(ed, where, BEL.find_then_pin(reachable))
    lodged, put = _author_lodge(ed, thrown, brk, _hit(brk, "ImpactPoint"),
                                BEL.find_then_pin(chipped))

    ed.add_comment_to_nodes(
        f"What the flight struck, for an item with a {THROW_DAMAGE_VAR} (a "
        "blade). Where it went into a body with health is found first (a "
        "trace of its mesh on along the way it flew, or failing that from the "
        f"hit towards the nearest bone: {THROW_BONE_VAR}, {THROW_SKIN_VAR}). "
        "The body loses that much, times its "
        f"{HEAD_MULT_VAR} for a bone of its head, stamped like a pellet hit, "
        "and bleeds; the item is set into the model and attached to the bone "
        "there, a pick-up that goes where the body goes. A body it cannot be "
        f"set into drops it at its foot, past it ({THROW_PAST_VAR}: what the "
        "fall's trace ignores, emptied first). A tree (an instanced "
        f"mesh) struck within {LODGE_MAX_HEIGHT_CM:.0f} cm of its foot chips, "
        f"and the item lodges in it: {LODGE_POINT_VAR} on the bark, turned by "
        f"{LODGE_TURN_VAR} along the way it flew, left there to be picked up.",
        [fresh, damage_n, bites, body, blood, aside, tree, reachable, chipped, put]
        + wound_nodes + skin_nodes + worth_nodes + stick_nodes)
    falls = (BEL.find_else_pin(bites), BEL.find_then_pin(aside),
             _loose_pin(tree, "CastFailed", is_input=False),
             BEL.find_else_pin(reachable))
    return falls, (lodged, stuck)
