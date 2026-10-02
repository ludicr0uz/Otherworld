"""What a thrown blade does to what its flight strikes: it wounds a body and
stays in it, and it lodges in a tree.

The flight (throw_flight.py) calls in here on the frame its segment trace
hits something, before it sets the item down:

    Thrown.ThrowDamage > 0                       (else it falls, as any item)
      --> the struck actor has a BP_HealthComponent: a body
            Health -= ThrowDamage, stamped as a pellet hit is; blood at the
            wound
            the body is a Character, and a trace of its mesh from the hit
            towards its nearest bone finds one of its physics bodies
              --> the item set into the body there, and attached to that
                  bone --> lodged
              (else it falls at the body's foot)
      --> else the struck component is an instanced mesh: a tree (chop.py
          says why that is the test)
            the hit no higher than LODGE_MAX_HEIGHT_CM over the tree's foot
              --> chips off the bark; the item set into the trunk --> lodged

ThrowDamage is the item's own (throw_tuning.py): 0 on the base, so a thrown
gun, mushroom or canteen does neither and comes to rest as it always did. The
damage is flat: no hit zones and no hot blade's double, which are the pellet's
and the blow's.

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
is a second trace, of the mesh's physics bodies alone, from that hit towards
the bone nearest it and STICK_TRACE_PAST times as far: the model's skin
nearest where the blade came in, and the bone that skin moves with. The
flight's own line would not do: a segment is one frame long and may end short
of the model, and a blade can cross the capsule beside the model, which has
wounded the body all the same. A corpse's lifespan ends with the item still
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

Owns ThrowPast, which build.py declares and the flight's ground trace reads.
"""

from combat.game_state import DAMAGED_BY_PLAYER_VAR, LAST_DAMAGE_VAR
from combat.graph import (
    BEL, _at, _connect, _loose_pin, _node, _palette, _pin, _set, _vec,
)
from combat.hit_reaction import LAST_HIT_FROM_VAR
from combat.nodes import (
    FN_ADD_VV, FN_ARR_ADD, FN_ATTACH, FN_BREAK_VECTOR, FN_CLAMP, FN_GET_COMP,
    FN_GREATER_FF, FN_LE_FF, FN_MAKE_TRANSFORM, FN_MUL_VF, FN_NORMAL,
    FN_ROT_FROM_X, FN_SUB_FF, FN_SUB_VV, FN_TIME_SECONDS, FN_TRACE_COMPONENT, INF,
    NODE_CAST_CHARACTER, NODE_CAST_HEALTH, NODE_SPAWN,
)
from combat.paths import HEALTH_CLASS_PATH
from combat.throw_tuning import (
    LODGE_MAX_HEIGHT_CM, LODGE_POINT_VAR, LODGE_TURN_VAR, STICK_TRACE_PAST,
    THROW_DAMAGE_VAR,
)
from combat.weapon_component.common import _prop
from combat.weapon_component.surface_impact import _author_surface_impact

THROW_PAST_VAR = "ThrowPast"          # the actors the fall to the ground ignores

NODE_CAST_INSTANCED = "Utilities|Casting|CastToInstancedStaticMeshComponent"
FN_INSTANCE_TRANSFORM = "/Script/Engine.InstancedStaticMeshComponent.GetInstanceTransform"
FN_BREAK_TRANSFORM = "/Script/Engine.KismetMathLibrary.BreakTransform"
FN_COMPOSE_ROT = "/Script/Engine.KismetMathLibrary.ComposeRotators"
FN_ROTATE_VECTOR = "/Script/Engine.KismetMathLibrary.GreaterGreater_VectorRotator"
FN_ARR_CLEAR = "/Script/Engine.KismetArrayLibrary.Array_Clear"
FN_SET_LOC_ROT = "/Script/Engine.Actor.K2_SetActorLocationAndRotation"
FN_CLOSEST_BONE = "/Script/Engine.SkinnedMeshComponent.FindClosestBone_K2"


def _out(n, name="ReturnValue"):
    return _pin(n, name, is_input=False)


def _hit(brk, name):
    return _loose_pin(brk, name, is_input=False)


def _z(ed, vector, x, y):
    parts = _at(_node(ed, FN_BREAK_VECTOR), x, y)
    _connect(vector, _pin(parts, "InVec"))
    return _out(parts, "Z")


def _author_wound(ed, as_health, damage, brk, exec_in, x0, y0):
    """Take ``damage`` off the body and leave the three stamps a pellet does
    (impact.py): the health bar, the kill's credit, which way the flinch
    goes. Returns the exec pin after them, and the nodes."""
    get_h = _at(ed.add_get_member_variable_node("Health", HEALTH_CLASS_PATH),
                x0, y0 + 300)
    _connect(as_health, _pin(get_h, "self"))
    sub = _at(_node(ed, FN_SUB_FF), x0 + 240, y0 + 300)
    _connect(_out(get_h, "Health"), _pin(sub, "A"))
    _connect(damage, _pin(sub, "B"))
    clamp = _at(_node(ed, FN_CLAMP), x0 + 480, y0 + 300)
    _connect(_out(sub), _pin(clamp, "Value"))
    _set(clamp, "Min", 0.0)
    _set(clamp, "Max", INF)
    set_h = _at(ed.add_set_member_variable_node("Health", HEALTH_CLASS_PATH),
                x0 + 740, y0)
    _connect(as_health, _pin(set_h, "self"))
    _connect(_out(clamp), _pin(set_h, "Health"))
    _connect(exec_in, _pin(set_h, "execute"))
    now = _at(_node(ed, FN_TIME_SECONDS), x0 + 740, y0 + 300)
    stamp = _at(ed.add_set_member_variable_node(LAST_DAMAGE_VAR, HEALTH_CLASS_PATH),
                x0 + 1000, y0)
    _connect(as_health, _pin(stamp, "self"))
    _connect(_out(now), _pin(stamp, LAST_DAMAGE_VAR))
    _connect(BEL.find_then_pin(set_h), _pin(stamp, "execute"))
    blame = _at(ed.add_set_member_variable_node(DAMAGED_BY_PLAYER_VAR,
                                                HEALTH_CLASS_PATH), x0 + 1260, y0)
    _connect(as_health, _pin(blame, "self"))
    _set(blame, DAMAGED_BY_PLAYER_VAR, "true")
    _connect(BEL.find_then_pin(stamp), _pin(blame, "execute"))
    from_where = _at(ed.add_set_member_variable_node(LAST_HIT_FROM_VAR,
                                                     HEALTH_CLASS_PATH),
                     x0 + 1520, y0)
    _connect(as_health, _pin(from_where, "self"))
    _connect(_hit(brk, "ImpactNormal"), _pin(from_where, LAST_HIT_FROM_VAR))
    _connect(BEL.find_then_pin(blame), _pin(from_where, "execute"))
    return BEL.find_then_pin(from_where), [set_h, stamp, blame, from_where]


def _author_lodge(ed, thrown, brk, on, exec_in, x0, y0):
    """Set the item into what it struck: its X along the segment it just
    flew, after its own LodgeTurn, and its LodgePoint on ``on`` (a point of
    the world: the bark, the skin). Returns the exec pin after it, and the
    node."""
    flew = _at(_node(ed, FN_SUB_VV), x0, y0 + 300)
    _connect(_hit(brk, "TraceEnd"), _pin(flew, "A"))
    _connect(_hit(brk, "TraceStart"), _pin(flew, "B"))
    along = _at(_node(ed, FN_NORMAL), x0 + 240, y0 + 300)
    _connect(_out(flew), _pin(along, "A"))
    into = _at(_node(ed, FN_ROT_FROM_X), x0 + 480, y0 + 300)
    _connect(_out(along), _pin(into, "X"))
    own, _own_n = _prop(ed, LODGE_TURN_VAR, thrown, x0 + 480, y0 + 480)
    # ComposeRotators applies A first: the item's own turn, then the throw's.
    pose = _at(_node(ed, FN_COMPOSE_ROT), x0 + 740, y0 + 380)
    _connect(own, _pin(pose, "A"))
    _connect(_out(into), _pin(pose, "B"))
    point, _point_n = _prop(ed, LODGE_POINT_VAR, thrown, x0 + 480, y0 + 660)
    reach = _at(_node(ed, FN_ROTATE_VECTOR), x0 + 1000, y0 + 560)
    _connect(point, _pin(reach, "A"))
    _connect(_out(pose), _pin(reach, "B"))
    at = _at(_node(ed, FN_SUB_VV), x0 + 1260, y0 + 460)
    _connect(on, _pin(at, "A"))
    _connect(_out(reach), _pin(at, "B"))
    put = _at(_node(ed, FN_SET_LOC_ROT), x0 + 1520, y0)
    _connect(thrown, _pin(put, "self"))
    _connect(_out(at), _pin(put, "NewLocation"))
    _connect(_out(pose), _pin(put, "NewRotation"))
    _connect(exec_in, _pin(put, "execute"))
    return BEL.find_then_pin(put), put


def _author_stick(ed, thrown, brk, exec_in, x0, y0):
    """Leave the item in the body it wounded: set into the model where the
    blade came in, and attached to the bone there. Returns (the exec pin a
    stuck item leaves by, the ones an item that could not be set leaves by,
    the nodes)."""
    as_char = _at(_palette(ed, NODE_CAST_CHARACTER), x0, y0)
    _connect(_hit(brk, "HitActor"), _pin(as_char, "Object"))
    _connect(exec_in, _pin(as_char, "execute"))
    step = BEL.find_then_pin(as_char)
    mesh = _at(ed.add_get_member_variable_node("Mesh", "/Script/Engine.Character"),
               x0, y0 + 300)
    _connect(_loose_pin(as_char, "AsCharacter", is_input=False), _pin(mesh, "self"))
    mesh_out = _out(mesh, "Mesh")
    # The capsule's hit is in the air round the model: the way in from it is
    # towards the nearest bone that has a body, and on past it.
    near = _at(_node(ed, FN_CLOSEST_BONE), x0 + 280, y0 + 300)
    _connect(mesh_out, _pin(near, "self"))
    _connect(_hit(brk, "ImpactPoint"), _pin(near, "TestLocation"))
    _set(near, "bRequirePhysicsAsset", "true")
    # Const, so pure here; were it ever given an exec pin, it goes in the chain.
    runs = BEL.find_input_pin(near, "execute")
    if runs and runs.is_valid():
        _connect(step, runs)
        step = BEL.find_then_pin(near)
    inward = _at(_node(ed, FN_SUB_VV), x0 + 560, y0 + 300)
    _connect(_out(near, "BoneLocation"), _pin(inward, "A"))
    _connect(_hit(brk, "ImpactPoint"), _pin(inward, "B"))
    far = _at(_node(ed, FN_MUL_VF), x0 + 800, y0 + 300)
    _connect(_out(inward), _pin(far, "A"))
    s = STICK_TRACE_PAST
    _connect(_vec(ed, s, s, s, x0 + 560, y0 + 460), _pin(far, "B"))
    end = _at(_node(ed, FN_ADD_VV), x0 + 1040, y0 + 300)
    _connect(_hit(brk, "ImpactPoint"), _pin(end, "A"))
    _connect(_out(far), _pin(end, "B"))
    skin = _at(_node(ed, FN_TRACE_COMPONENT), x0 + 1300, y0)
    _connect(mesh_out, _pin(skin, "self"))
    _connect(_hit(brk, "ImpactPoint"), _pin(skin, "TraceStart"))
    _connect(_out(end), _pin(skin, "TraceEnd"))
    # Simple collision: the physics asset's bodies, each of which names its bone.
    _set(skin, "bTraceComplex", "false")
    _set(skin, "bShowTrace", "false")
    _set(skin, "bPersistentShowTrace", "false")
    _connect(step, _pin(skin, "execute"))
    found = _at(ed.add_branch_node(), x0 + 1620, y0)
    _connect(_out(skin), _pin(found, "Condition"))
    _connect(BEL.find_then_pin(skin), _pin(found, "execute"))
    set_in, put = _author_lodge(ed, thrown, brk, _out(skin, "HitLocation"),
                                BEL.find_then_pin(found), x0 + 1880, y0)
    hold = _at(_node(ed, FN_ATTACH), x0 + 3700, y0)
    _connect(thrown, _pin(hold, "self"))
    _connect(mesh_out, _pin(hold, "Parent"))
    _connect(_out(skin, "BoneName"), _pin(hold, "SocketName"))
    # Where the lodge just put it, and its own size on a scaled model.
    for rule in ("LocationRule", "RotationRule", "ScaleRule"):
        _set(hold, rule, "KeepWorld")
    _connect(set_in, _pin(hold, "execute"))
    return (BEL.find_then_pin(hold),
            (_loose_pin(as_char, "CastFailed", is_input=False),
             BEL.find_else_pin(found)),
            [as_char, skin, found, put, hold])


def _author_throw_strike(ed, thrown, brk, exec_in, x0, y0):
    """The flight's segment struck something (``brk`` is that hit, broken):
    a blade wounds a body and stays in it, and lodges in a tree. Returns
    (falls, lodged): the exec pins an item that still has to come down to the
    ground leaves by, and the ones an item left in what it struck leaves by."""
    damage, damage_n = _prop(ed, THROW_DAMAGE_VAR, thrown, x0, y0 + 200)
    sharp = _at(_node(ed, FN_GREATER_FF), x0 + 240, y0 + 200)
    _connect(damage, _pin(sharp, "A"))        # B is left at its default, 0
    bites = _at(ed.add_branch_node(), x0 + 480, y0)
    _connect(_out(sharp), _pin(bites, "Condition"))
    past = _at(ed.add_get_member_variable_node(THROW_PAST_VAR), x0 - 260, y0 + 200)
    fresh = _at(_node(ed, FN_ARR_CLEAR), x0, y0)
    _connect(_out(past, THROW_PAST_VAR), _pin(fresh, "TargetArray"))
    _connect(exec_in, _pin(fresh, "execute"))
    _connect(BEL.find_then_pin(fresh), _pin(bites, "execute"))

    # --- a body: the wound, and blood out of it --------------------------------
    comp = _at(_node(ed, FN_GET_COMP), x0 + 480, y0 + 300)
    _connect(_hit(brk, "HitActor"), _pin(comp, "self"))
    _pin(comp, "ComponentClass").set_pin_value(HEALTH_CLASS_PATH)
    body = _at(_palette(ed, NODE_CAST_HEALTH), x0 + 760, y0)
    _connect(_out(comp), _pin(body, "Object"))
    _connect(BEL.find_then_pin(bites), _pin(body, "execute"))
    wounded, wound_nodes = _author_wound(
        ed, _loose_pin(body, "AsBPHealthComponent", is_input=False), damage, brk,
        BEL.find_then_pin(body), x0 + 1040, y0)
    # The one transform serves the blood and the chips, as a pellet's does:
    # the hit, +X turned out along the surface normal.
    facing = _at(_node(ed, FN_ROT_FROM_X), x0 + 2600, y0 + 440)
    _connect(_hit(brk, "ImpactNormal"), _pin(facing, "X"))
    where = _at(_node(ed, FN_MAKE_TRANSFORM), x0 + 2860, y0 + 300)
    _connect(_hit(brk, "ImpactPoint"), _pin(where, "Location"))
    _connect(_out(facing), _pin(where, "Rotation"))
    blood_cls = _at(ed.add_get_member_variable_node("BloodClass"), x0 + 2860, y0 + 180)
    blood = _at(_palette(ed, NODE_SPAWN), x0 + 3140, y0)
    _connect(_out(blood_cls, "BloodClass"), _pin(blood, "Class"))
    _connect(_out(where), _pin(blood, "SpawnTransform"))
    _set(blood, "CollisionHandlingOverride", "AlwaysSpawn")
    _connect(wounded, _pin(blood, "execute"))
    # ...and the blade stays in the body. One it cannot be set into drops
    # it, and that fall to the ground passes the body by.
    stuck, dropped, stick_nodes = _author_stick(
        ed, thrown, brk, BEL.find_then_pin(blood), x0 + 3440, y0 - 900)
    aside = _at(_node(ed, FN_ARR_ADD), x0 + 5400, y0)
    _connect(_out(past, THROW_PAST_VAR), _pin(aside, "TargetArray"))
    _connect(_hit(brk, "HitActor"), _pin(aside, "NewItem"))
    for pin in dropped:
        _connect(pin, _pin(aside, "execute"))

    # --- a tree, struck low enough to be taken back -----------------------------
    y1 = y0 + 900
    tree = _at(_palette(ed, NODE_CAST_INSTANCED), x0 + 1040, y1)
    _connect(_hit(brk, "HitComponent"), _pin(tree, "Object"))
    _connect(_loose_pin(body, "CastFailed", is_input=False), _pin(tree, "execute"))
    step = BEL.find_then_pin(tree)
    stands = _at(_node(ed, FN_INSTANCE_TRANSFORM), x0 + 1320, y1 + 300)
    _connect(_loose_pin(tree, "AsInstancedStaticMeshComponent", is_input=False),
             _pin(stands, "self"))
    _connect(_hit(brk, "HitItem"), _pin(stands, "InstanceIndex"))
    _set(stands, "bWorldSpace", "true")
    # Const, so pure here; were it ever given an exec pin, it goes in the chain.
    runs = BEL.find_input_pin(stands, "execute")
    if runs and runs.is_valid():
        _connect(step, runs)
        step = BEL.find_then_pin(stands)
    foot = _at(_node(ed, FN_BREAK_TRANSFORM), x0 + 1600, y1 + 300)
    _connect(_out(stands, "OutInstanceTransform"), _pin(foot, "InTransform"))
    up = _at(_node(ed, FN_SUB_FF), x0 + 2140, y1 + 300)
    _connect(_z(ed, _hit(brk, "ImpactPoint"), x0 + 1880, y1 + 200), _pin(up, "A"))
    _connect(_z(ed, _out(foot, "Location"), x0 + 1880, y1 + 380), _pin(up, "B"))
    low = _at(_node(ed, FN_LE_FF), x0 + 2380, y1 + 300)
    _connect(_out(up), _pin(low, "A"))
    _set(low, "B", LODGE_MAX_HEIGHT_CM)
    reachable = _at(ed.add_branch_node(), x0 + 2620, y1)
    _connect(_out(low), _pin(reachable, "Condition"))
    _connect(step, _pin(reachable, "execute"))
    _cls, chipped = _author_surface_impact(ed, where, BEL.find_then_pin(reachable),
                                           x0 + 2880, y1)
    lodged, put = _author_lodge(ed, thrown, brk, _hit(brk, "ImpactPoint"),
                                BEL.find_then_pin(chipped), x0 + 3440, y1)

    ed.add_comment_to_nodes(
        f"What the flight struck, for an item with a {THROW_DAMAGE_VAR} (a "
        "blade). A body with health loses that much, stamped like a pellet "
        "hit, and bleeds; the item is set into the model (a trace of its mesh "
        "from the hit towards the nearest bone) and attached to the bone "
        "there, a pick-up that goes where the body goes. A body it cannot be "
        f"set into drops it at its foot, past it ({THROW_PAST_VAR}: what the "
        "fall's trace ignores, emptied first). A tree (an instanced "
        f"mesh) struck within {LODGE_MAX_HEIGHT_CM:.0f} cm of its foot chips, "
        f"and the item lodges in it: {LODGE_POINT_VAR} on the bark, turned by "
        f"{LODGE_TURN_VAR} along the way it flew, left there to be picked up.",
        [fresh, damage_n, bites, body, blood, aside, tree, reachable, chipped, put]
        + wound_nodes + stick_nodes)
    falls = (BEL.find_else_pin(bites), BEL.find_then_pin(aside),
             _loose_pin(tree, "CastFailed", is_input=False),
             BEL.find_else_pin(reachable))
    return falls, (lodged, stuck)
