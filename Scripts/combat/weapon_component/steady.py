"""Down the sights the body is steady: a hit plays no flinch.

    steady = SightBlend > STEADY_BLEND
    owner's BP_HealthComponent -->
        steady AND NOT its Steady (last frame's) AND HitSlot is playing?
            -> NeedsRefresh = true      (the equip plays the ready pose again)
        its Steady = steady

Why: down the sights the camera rides the gun (sights.py puts it at the gun's
eye point, looking along its sight line). A flinch takes the arms, and since
every slot is in one montage group it also stops the ready pose
(hit_reaction.py), so for the stagger and the blend back the gun was at the
carry, at the knee, and the view dropped there and came back: a hit threw the
aim off the target. The health component's flinch asks Steady first
(hit_reaction._author_steady_gate); the damage itself is untouched.

SightBlend, not SightAiming: the camera is on the gun for as long as the
blend is above zero, the ease out included, and SightBlend is what the probes
hold the sights up with (no key reaches a headless game).

The re-equip is for a flinch that was already playing when the sights came
up: hit at the hip with the gun raised, then the sights. The equip at the end
of this Tick plays the ready pose, which stops the flinch (the same group, for
once on purpose) and blends straight from it, with no pass through the carry.
Only on the frame Steady turns true: IsSlotActive stays true through the
flinch's blend out, and a re-equip a frame would restart the pose each time.
A gun that was lowered is re-equipped by the carry's edge (ready_pose.py) on
the same frame; this covers the raised one. NeedsRefresh rather than a play
of its own: the equip is the one place the pose is started, behind Lowered.

After sights.py, which writes SightBlend, and before the equip.
"""

from combat.anim_blueprint import AIM_SLOT, HIT_SLOT
from combat.graph import BEL, _connect, _loose_pin, _node, _palette, _pin, _set
from combat.hit_reaction import STEADY_VAR
from combat.nodes import (
    FN_AND, FN_ANIM_INSTANCE, FN_GET_COMP, FN_GREATER_FF, FN_IS_SLOT_ACTIVE,
    FN_NOT, NODE_CAST_HEALTH,
)
from combat.paths import HEALTH_CLASS_PATH

# The sights are up, for the flinch, from this much of the camera's travel to
# the eye point. Below it the view is the boom's to within a hundredth.
STEADY_BLEND = 0.01


def _author_steady(ed, owner_out, exec_ins):
    """See the module docstring. Returns the exec pins to carry on from."""
    made = []

    def keep(n):
        made.append(n)
        return n

    def out(n, name="ReturnValue"):
        return _pin(n, name, is_input=False)

    blend = keep(ed.add_get_member_variable_node("SightBlend"))
    steady = keep(_node(ed, FN_GREATER_FF))
    _connect(out(blend, "SightBlend"), _pin(steady, "A"))
    _set(steady, "B", STEADY_BLEND)

    comp = keep(_node(ed, FN_GET_COMP))
    _connect(owner_out, _pin(comp, "self"))
    _pin(comp, "ComponentClass").set_pin_value(HEALTH_CLASS_PATH)
    cast = keep(_palette(ed, NODE_CAST_HEALTH))
    _connect(out(comp), _pin(cast, "Object"))
    for e in exec_ins:
        _connect(e, _pin(cast, "execute"))
    as_health = _loose_pin(cast, "AsBPHealthComponent", is_input=False)

    # Behind the cast, and before the write below: last frame's answer.
    was = keep(ed.add_get_member_variable_node(STEADY_VAR, HEALTH_CLASS_PATH))
    _connect(as_health, _pin(was, "self"))
    fresh = keep(_node(ed, FN_NOT))
    _connect(out(was, STEADY_VAR), _pin(fresh, "A"))
    raised = keep(_node(ed, FN_AND))
    _connect(out(steady), _pin(raised, "A"))
    _connect(out(fresh), _pin(raised, "B"))

    mesh = keep(ed.add_get_member_variable_node("OwnerMesh"))
    anim = keep(_node(ed, FN_ANIM_INSTANCE))
    _connect(out(mesh, "OwnerMesh"), _pin(anim, "self"))
    flinching = keep(_node(ed, FN_IS_SLOT_ACTIVE))
    _connect(out(anim), _pin(flinching, "self"))
    _set(flinching, "SlotNodeName", HIT_SLOT)
    caught = keep(_node(ed, FN_AND))
    _connect(out(raised), _pin(caught, "A"))
    _connect(out(flinching), _pin(caught, "B"))

    mid = keep(ed.add_branch_node())
    _connect(out(caught), _pin(mid, "Condition"))
    _connect(BEL.find_then_pin(cast), _pin(mid, "execute"))
    dirty = keep(ed.add_set_member_variable_node("NeedsRefresh"))
    _set(dirty, "NeedsRefresh", "true")
    _connect(BEL.find_then_pin(mid), _pin(dirty, "execute"))

    mark = keep(ed.add_set_member_variable_node(STEADY_VAR, HEALTH_CLASS_PATH))
    _connect(as_health, _pin(mark, "self"))
    _connect(out(steady), _pin(mark, STEADY_VAR))
    for tail in (BEL.find_then_pin(dirty), BEL.find_else_pin(mid)):
        _connect(tail, _pin(mark, "execute"))

    ed.add_comment_to_nodes(
        f"Down the sights (SightBlend > {STEADY_BLEND:g}) the body is "
        f"{STEADY_VAR}: the health component plays no flinch, so a hit leaves "
        f"the view, which rides the gun, on the target. A flinch already "
        f"playing on the frame the sights come up is ended by re-equipping, "
        f"which plays the ready pose straight back into {AIM_SLOT}.", made)
    return (BEL.find_then_pin(mark), _pin(cast, "CastFailed", is_input=False))
