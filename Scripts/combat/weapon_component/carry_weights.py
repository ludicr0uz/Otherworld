"""The long gun's carry, on the component: what the anim BP's CarryPose and
CarrySprint ease towards (carry_pose.py owns the nodes they weight;
pose_weights.py eases them, on every machine's copy).

    CarryPose   -> Lowered AND HandPose == CarryFor AND NOT Stance == PRONE
                   AND NOT Searching AND NOT sliding AND NOT in a traversal
    CarrySprint -> the movement's IsSprinting

Lowered (carry.py) is already "no ready pose": a gun nothing holds up, or a
sprint. HandPose (look.py) is the pose the hand's item is held in, and CarryFor
is the rifle's ready pose, which the rifle, the sniper and the shotgun share:
so the carry is theirs alone, and the pistol, the knife and empty hands keep
the locomotion's arms. Both travel to the other machines already (LookLowered,
LookPose), so another player's copy carries with nothing new replicated.

Standing and crouched (which clips, carry_pose.py chooses by PoseCrouch);
prone the gun is up (Lowered is false there, and the crawl's arms are its
own if it ever were not). Not while searching a body, sliding or in a
traversal, which pose the whole body themselves.
"""

from combat.carry_pose_consts import CARRY_FOR_VAR, CARRY_POSE, CARRY_SPRINT
from combat.carry_tuning import LOWERED_VAR
from combat.gas_moves import traversal_on
from combat.gas_moves_tuning import DOING_VAR
from combat.weapon_component import vars as WV
from combat.weapon_component.carry import TRAVERSAL_CLASS
from combat.weapon_component.look_vars import HandPose
from combat.weapon_component.stance import PRONE, STANCE_VAR
from uebp.g import _G
from uebp.graph import _pin, out
from uebp.nodes.actor import FN_GET_COMP, FN_GET_OWNER
from uebp.nodes.math import FN_AND, FN_EQ_II, FN_EQ_OO, FN_NOT
from uebp.nodes.move import FN_IS_SPRINTING


def carry_targets(ed, sliding=None):
    """{weight: bool pin} for the two carry weights. ``sliding``: the pin the
    slide's own weight eases to (pose_weights.py), None with no slide."""
    g = _G(ed)

    def both(a, b):
        return out(g.call(FN_AND, A=a, B=b))

    def never(a):
        return out(g.call(FN_NOT, A=a))

    owner = out(g.call(FN_GET_OWNER))
    long_gun = out(g.call(FN_EQ_OO, A=g.get(HandPose), B=g.get(CARRY_FOR_VAR)))
    upright = never(out(g.call(FN_EQ_II, A=g.get(STANCE_VAR), B=PRONE)))
    on = both(both(g.get(LOWERED_VAR), long_gun), upright)
    on = both(on, never(g.get(WV.Searching)))
    if sliding is not None:
        on = both(on, never(sliding))
    if traversal_on():
        comp = g.call(FN_GET_COMP, self=owner)
        _pin(comp, "ComponentClass").set_pin_value(TRAVERSAL_CLASS)
        on = both(on, never(g.iget(out(comp), DOING_VAR, TRAVERSAL_CLASS)))
    return {CARRY_POSE: on,
            CARRY_SPRINT: out(g.call(FN_IS_SPRINTING, Character=owner))}
