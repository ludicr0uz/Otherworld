"""The dead gate: the first thing the weapon component's Tick asks, before any
key is polled. A dead owner's Tick does nothing.

    Tick --> owner's BP_HealthComponent --> [Dead OR Health <= 0?]
               no, or no component --> OwnerDead = false --> the rest of Tick
               yes --> OwnerDead = true, and what the Tick was holding is let
                       go: the aim, the sprint and the guard; the zoom and
                       the camera go home; a scoped gun, the body and the
                       head the sights hid show

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

from uebp.graph import _connect, _loose_pin, _node, _palette, _pin, _set, else_, then
from combat.ask_consts import EXIT_PENDING_VAR
from combat.nodes import CAMERA_CLASS_PATH, SPRING_ARM_CLASS_PATH, SPRING_ARM_SOCKET
from combat.paths import FIRE_WARD_VAR, HEALTH_CLASS_PATH
from combat.seat_tuning import LOOK_VAR, SEAT_VAR, SEATED_VAR
from combat.weapon_component.head_hide import _author_head_shown
from uebp.nodes.actor import (
    FN_COMP_SET_WORLD_LOC, FN_COMP_SET_WORLD_ROT, FN_GET_COMP, FN_SET_FOV, FN_SET_HIDDEN,
    FN_SET_OWNER_NO_SEE, FN_SOCKET_LOC, FN_SOCKET_ROT)
from uebp.nodes.math import FN_LE_FF, FN_OR
from uebp.nodes.palette import NODE_CAST_HEALTH
from combat import health_vars as HV
from combat.weapon_component import vars as WV

OWNER_DEAD_VAR = "OwnerDead"   # this Tick found its owner dead and did nothing

# What a dead owner is no longer doing. Others read these: the wanderers'
# swing reads Blocking, the HUD's reticle the aim, a wendigo FireWard, the
# HUD's banner the save-and-exit countdown (save_exit.py): a death calls it off.
LET_GO_VARS = ("Aiming", "SightAiming", SEATED_VAR, "Sprinting", "Blocking",
               FIRE_WARD_VAR, EXIT_PENDING_VAR)


def _author_dead_gate(ed, owner_out, held, armed_out, exec_in):
    """See the module docstring. Returns the exec pin a living owner's Tick
    carries on from."""
    made = []

    def keep(n):
        made.append(n)
        return n

    def out(n, name="ReturnValue"):
        return _pin(n, name, is_input=False)

    comp = keep(_node(ed, FN_GET_COMP))
    _connect(owner_out, _pin(comp, "self"))
    _pin(comp, "ComponentClass").set_pin_value(HEALTH_CLASS_PATH)
    cast = keep(_palette(ed, NODE_CAST_HEALTH))
    _connect(out(comp), _pin(cast, "Object"))
    _connect(exec_in, _pin(cast, "execute"))
    as_health = _loose_pin(cast, "AsBPHealthComponent", is_input=False)

    # Behind the cast, so neither read is ever pulled off a null component.
    marked = keep(ed.add_get_member_variable_node(HV.Dead, HEALTH_CLASS_PATH))
    _connect(as_health, _pin(marked, "self"))
    hp = keep(ed.add_get_member_variable_node(HV.Health, HEALTH_CLASS_PATH))
    _connect(as_health, _pin(hp, "self"))
    spent = keep(_node(ed, FN_LE_FF))
    _connect(out(hp, HV.Health), _pin(spent, "A"))
    _set(spent, "B", 0.0)
    dead = keep(_node(ed, FN_OR))
    _connect(out(marked, HV.Dead), _pin(dead, "A"))
    _connect(out(spent), _pin(dead, "B"))
    gate = keep(ed.add_branch_node())
    _connect(out(dead), _pin(gate, "Condition"))
    _connect(then(cast), _pin(gate, "execute"))

    # Alive, or nothing to die with: one setter both arms run into, so the
    # rest of the Tick still hangs off a single exec pin.
    alive = keep(ed.add_set_member_variable_node(OWNER_DEAD_VAR))
    _set(alive, OWNER_DEAD_VAR, False)
    _connect(else_(gate), _pin(alive, "execute"))
    _connect(_pin(cast, "CastFailed", is_input=False), _pin(alive, "execute"))

    # Dead. Nothing below reaches the rest of the Tick.
    gone = keep(ed.add_set_member_variable_node(OWNER_DEAD_VAR))
    _set(gone, OWNER_DEAD_VAR, True)
    _connect(then(gate), _pin(gone, "execute"))
    flow = then(gone)
    for name in LET_GO_VARS:
        drop = keep(ed.add_set_member_variable_node(name))
        _set(drop, name, False)
        _connect(flow, _pin(drop, "execute"))
        flow = then(drop)

    # The zoom and the camera, home at once (ads.py and sights.py ease them,
    # and neither runs again).
    cam = keep(_node(ed, FN_GET_COMP))
    _connect(owner_out, _pin(cam, "self"))
    _pin(cam, "ComponentClass").set_pin_value(CAMERA_CLASS_PATH)
    base = keep(ed.add_get_member_variable_node(WV.BaseFOV))
    fov = keep(ed.add_set_member_variable_node(WV.CurrentFOV))
    _connect(out(base, WV.BaseFOV), _pin(fov, WV.CurrentFOV))
    _connect(flow, _pin(fov, "execute"))
    unzoom = keep(_node(ed, FN_SET_FOV))
    _connect(out(cam), _pin(unzoom, "self"))
    _connect(out(base, WV.BaseFOV), _pin(unzoom, "InFieldOfView"))
    _connect(then(fov), _pin(unzoom, "execute"))
    seat = keep(ed.add_set_member_variable_node(SEAT_VAR))
    _set(seat, SEAT_VAR, 0.0)
    _connect(then(unzoom), _pin(seat, "execute"))
    look = keep(ed.add_set_member_variable_node(LOOK_VAR))
    _set(look, LOOK_VAR, 0.0)
    _connect(then(seat), _pin(look, "execute"))
    blend = keep(ed.add_set_member_variable_node(WV.SightBlend))
    _set(blend, WV.SightBlend, 0.0)
    _connect(then(look), _pin(blend, "execute"))
    arm = keep(_node(ed, FN_GET_COMP))
    _connect(owner_out, _pin(arm, "self"))
    _pin(arm, "ComponentClass").set_pin_value(SPRING_ARM_CLASS_PATH)
    shoulder = keep(_node(ed, FN_SOCKET_LOC))
    _connect(out(arm), _pin(shoulder, "self"))
    _set(shoulder, "InSocketName", SPRING_ARM_SOCKET)
    home = keep(_node(ed, FN_COMP_SET_WORLD_LOC))
    _connect(out(cam), _pin(home, "self"))
    _connect(out(shoulder), _pin(home, "NewLocation"))
    _connect(then(blend), _pin(home, "execute"))
    boom_rot = keep(_node(ed, FN_SOCKET_ROT))
    _connect(out(arm), _pin(boom_rot, "self"))
    _set(boom_rot, "InSocketName", SPRING_ARM_SOCKET)
    level = keep(_node(ed, FN_COMP_SET_WORLD_ROT))
    _connect(out(cam), _pin(level, "self"))
    _connect(out(boom_rot), _pin(level, "NewRotation"))
    _connect(then(home), _pin(level, "execute"))

    # ...and what the scope hid shows again: the body, and the gun if there
    # is one (a nested Branch, so Held is never read null).
    body = keep(ed.add_get_member_variable_node(WV.OwnerMesh))
    shown = keep(_node(ed, FN_SET_OWNER_NO_SEE))
    _connect(out(body, WV.OwnerMesh), _pin(shown, "self"))
    _set(shown, "bNewOwnerNoSee", False)
    _connect(then(level), _pin(shown, "execute"))
    # ...and the head the sights hid (head_hide.py).
    headed = _author_head_shown(ed, keep, then(shown))
    armed = keep(ed.add_branch_node())
    _connect(armed_out, _pin(armed, "Condition"))
    _connect(headed, _pin(armed, "execute"))
    untuck = keep(_node(ed, FN_SET_HIDDEN))
    _connect(held, _pin(untuck, "self"))
    _set(untuck, "bNewHidden", False)
    _connect(then(armed), _pin(untuck, "execute"))

    ed.add_comment_to_nodes(
        "The dead gate, before any key is polled: an owner whose health "
        "component is Dead, or at 0 HP on the frame of the blow, gets none of "
        "this Tick -- no shot, reload, switch, drop, pick-up, throw, bite, "
        "punch or slash. The dead arm lets go of what the Tick was holding "
        f"({', '.join(LET_GO_VARS)}), snaps the zoom and the camera home and "
        "shows the body and the gun a scope had hidden and the head the "
        "sights had. OwnerDead is what the "
        "HUD's loot window reads.",
        made)
    return then(alive)
