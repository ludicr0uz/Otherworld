"""The dead gate: the first thing the weapon component's Tick asks, before any
key is polled. A dead owner's Tick does nothing.

    Tick --> owner's BP_HealthComponent --> [Dead OR Health <= 0?]
               no, or no component --> OwnerDead = false --> the rest of Tick
               yes --> OwnerDead = true, and what the Tick was holding is let
                       go: the aim, the sprint and the guard; the zoom and
                       the camera go home; a scoped gun and the body show

A dead player used to fire. The player's death is a ragdoll collapse and a
2.2 s settle before the game pauses (death.py), and through it the Tick below
polled every key as if nothing had happened: a shot, a reload, a switch, a
drop, a pick-up, a throw, a bite, a punch. Refusing each one where it is
polled would be a dozen gates and the next action would forget its own, so
death is a state the Tick itself is in: nothing after this gate runs, which
covers every action there is and every one added later.

Health <= 0 as well as Dead, because Dead is written by the health
component's own Tick: on the frame the killing blow lands, whichever of the
two components ticks first, Health is already zero.

The dead arm writes every frame rather than once. Each write is idempotent,
and the aim fragments it stands in for (ads.py, sights.py) are written the
same way: no latch to forget. It snaps rather than eases, because the eases
live in the Tick that no longer runs. Without it a player who died down a
scope stays hidden behind its glass (sights.py hides the gun and the body)
for the whole collapse and the death menu after it.

OwnerDead is for whoever else acts for the player: the HUD's loot window
(graphics_menu/loot_tick.py) reads it rather than finding the health
component again.
"""

from combat.graph import BEL, _at, _connect, _loose_pin, _node, _palette, _pin, _set
from combat.nodes import (
    CAMERA_CLASS_PATH, FN_COMP_SET_WORLD_LOC, FN_COMP_SET_WORLD_ROT,
    FN_GET_COMP, FN_LE_FF, FN_OR, FN_SET_FOV, FN_SET_HIDDEN,
    FN_SET_OWNER_NO_SEE, FN_SOCKET_LOC, FN_SOCKET_ROT,
    NODE_CAST_HEALTH, SPRING_ARM_CLASS_PATH, SPRING_ARM_SOCKET,
)
from combat.paths import HEALTH_CLASS_PATH

OWNER_DEAD_VAR = "OwnerDead"   # this Tick found its owner dead and did nothing

# What a dead owner is no longer doing. Others read these: the wanderers'
# swing reads Blocking, the HUD's reticle the aim.
LET_GO_VARS = ("Aiming", "SightAiming", "Sprinting", "Blocking")


def _author_dead_gate(ed, owner_out, held, armed_out, exec_in, x0, y0):
    """See the module docstring. Returns the exec pin a living owner's Tick
    carries on from."""
    made = []

    def keep(n):
        made.append(n)
        return n

    def out(n, name="ReturnValue"):
        return _pin(n, name, is_input=False)

    comp = keep(_at(_node(ed, FN_GET_COMP), x0, y0 + 260))
    _connect(owner_out, _pin(comp, "self"))
    _pin(comp, "ComponentClass").set_pin_value(HEALTH_CLASS_PATH)
    cast = keep(_at(_palette(ed, NODE_CAST_HEALTH), x0 + 260, y0))
    _connect(out(comp), _pin(cast, "Object"))
    _connect(exec_in, _pin(cast, "execute"))
    as_health = _loose_pin(cast, "AsBPHealthComponent", is_input=False)

    # Behind the cast, so neither read is ever pulled off a null component.
    marked = keep(_at(ed.add_get_member_variable_node("Dead", HEALTH_CLASS_PATH),
                      x0 + 520, y0 + 260))
    _connect(as_health, _pin(marked, "self"))
    hp = keep(_at(ed.add_get_member_variable_node("Health", HEALTH_CLASS_PATH),
                  x0 + 520, y0 + 400))
    _connect(as_health, _pin(hp, "self"))
    spent = keep(_at(_node(ed, FN_LE_FF), x0 + 760, y0 + 400))
    _connect(out(hp, "Health"), _pin(spent, "A"))
    _set(spent, "B", 0.0)
    dead = keep(_at(_node(ed, FN_OR), x0 + 1000, y0 + 300))
    _connect(out(marked, "Dead"), _pin(dead, "A"))
    _connect(out(spent), _pin(dead, "B"))
    gate = keep(_at(ed.add_branch_node(), x0 + 1240, y0))
    _connect(out(dead), _pin(gate, "Condition"))
    _connect(BEL.find_then_pin(cast), _pin(gate, "execute"))

    # Alive, or nothing to die with: one setter both arms run into, so the
    # rest of the Tick still hangs off a single exec pin.
    alive = keep(_at(ed.add_set_member_variable_node(OWNER_DEAD_VAR),
                     x0 + 1500, y0 - 200))
    _set(alive, OWNER_DEAD_VAR, "false")
    _connect(BEL.find_else_pin(gate), _pin(alive, "execute"))
    _connect(_pin(cast, "CastFailed", is_input=False), _pin(alive, "execute"))

    # Dead. Nothing below reaches the rest of the Tick.
    x, y = x0 + 1500, y0 + 200
    gone = keep(_at(ed.add_set_member_variable_node(OWNER_DEAD_VAR), x, y))
    _set(gone, OWNER_DEAD_VAR, "true")
    _connect(BEL.find_then_pin(gate), _pin(gone, "execute"))
    flow = BEL.find_then_pin(gone)
    for name in LET_GO_VARS:
        x += 260
        drop = keep(_at(ed.add_set_member_variable_node(name), x, y))
        _set(drop, name, "false")
        _connect(flow, _pin(drop, "execute"))
        flow = BEL.find_then_pin(drop)

    # The zoom and the camera, home at once (ads.py and sights.py ease them,
    # and neither runs again).
    x += 300
    cam = keep(_at(_node(ed, FN_GET_COMP), x, y + 400))
    _connect(owner_out, _pin(cam, "self"))
    _pin(cam, "ComponentClass").set_pin_value(CAMERA_CLASS_PATH)
    base = keep(_at(ed.add_get_member_variable_node("BaseFOV"), x, y + 260))
    fov = keep(_at(ed.add_set_member_variable_node("CurrentFOV"), x + 260, y))
    _connect(out(base, "BaseFOV"), _pin(fov, "CurrentFOV"))
    _connect(flow, _pin(fov, "execute"))
    unzoom = keep(_at(_node(ed, FN_SET_FOV), x + 520, y))
    _connect(out(cam), _pin(unzoom, "self"))
    _connect(out(base, "BaseFOV"), _pin(unzoom, "InFieldOfView"))
    _connect(BEL.find_then_pin(fov), _pin(unzoom, "execute"))
    blend = keep(_at(ed.add_set_member_variable_node("SightBlend"), x + 780, y))
    _set(blend, "SightBlend", 0.0)
    _connect(BEL.find_then_pin(unzoom), _pin(blend, "execute"))
    arm = keep(_at(_node(ed, FN_GET_COMP), x + 780, y + 400))
    _connect(owner_out, _pin(arm, "self"))
    _pin(arm, "ComponentClass").set_pin_value(SPRING_ARM_CLASS_PATH)
    shoulder = keep(_at(_node(ed, FN_SOCKET_LOC), x + 1040, y + 400))
    _connect(out(arm), _pin(shoulder, "self"))
    _set(shoulder, "InSocketName", SPRING_ARM_SOCKET)
    home = keep(_at(_node(ed, FN_COMP_SET_WORLD_LOC), x + 1300, y))
    _connect(out(cam), _pin(home, "self"))
    _connect(out(shoulder), _pin(home, "NewLocation"))
    _connect(BEL.find_then_pin(blend), _pin(home, "execute"))
    boom_rot = keep(_at(_node(ed, FN_SOCKET_ROT), x + 1040, y + 540))
    _connect(out(arm), _pin(boom_rot, "self"))
    _set(boom_rot, "InSocketName", SPRING_ARM_SOCKET)
    level = keep(_at(_node(ed, FN_COMP_SET_WORLD_ROT), x + 1300, y + 200))
    _connect(out(cam), _pin(level, "self"))
    _connect(out(boom_rot), _pin(level, "NewRotation"))
    _connect(BEL.find_then_pin(home), _pin(level, "execute"))

    # ...and what the scope hid shows again: the body, and the gun if there
    # is one (a nested Branch, so Held is never read null).
    body = keep(_at(ed.add_get_member_variable_node("OwnerMesh"), x + 1300, y + 400))
    shown = keep(_at(_node(ed, FN_SET_OWNER_NO_SEE), x + 1560, y))
    _connect(out(body, "OwnerMesh"), _pin(shown, "self"))
    _set(shown, "bNewOwnerNoSee", "false")
    _connect(BEL.find_then_pin(level), _pin(shown, "execute"))
    armed = keep(_at(ed.add_branch_node(), x + 1820, y))
    _connect(armed_out, _pin(armed, "Condition"))
    _connect(BEL.find_then_pin(shown), _pin(armed, "execute"))
    untuck = keep(_at(_node(ed, FN_SET_HIDDEN), x + 2080, y))
    _connect(held, _pin(untuck, "self"))
    _set(untuck, "bNewHidden", "false")
    _connect(BEL.find_then_pin(armed), _pin(untuck, "execute"))

    ed.add_comment_to_nodes(
        "The dead gate, before any key is polled: an owner whose health "
        "component is Dead, or at 0 HP on the frame of the blow, gets none of "
        "this Tick -- no shot, reload, switch, drop, pick-up, throw, bite, "
        "punch or slash. The dead arm lets go of what the Tick was holding "
        f"({', '.join(LET_GO_VARS)}), snaps the zoom and the camera home and "
        "shows the body and the gun a scope had hidden. OwnerDead is what the "
        "HUD's loot window reads.",
        made)
    return BEL.find_then_pin(alive)
