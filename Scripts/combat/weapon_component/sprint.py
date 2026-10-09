"""Sprint and stamina in the weapon component's Tick: the key goes to the
character's movement component, and what it made of the key comes back.

The sprint itself (the stamina latch, the forward cone, the speed, the drain
and the refill) is C++, in the movement component (Source/Otherworld,
OtherworldCharacterMovement), because only there can the owning client
predict it and the server agree: a speed a Blueprint writes exists on one
machine. This graph is the two ends of it: the local player's key in, and
the state out, into the variables every other graph already reads.
"""

from uebp.g import _G
from uebp.graph import _connect, _node, _pin, out, then
from combat.sprint_tuning import (
    BASE_SPEED_VAR, SPRINT_AHEAD_VAR, SPRINT_CONE_HALF_ANGLE_DEG, SPRINT_FORCED_VAR,
    SPRINT_SPEED_VAR, STAMINA_DRAIN_VAR, STAMINA_REGEN_VAR,
)
from combat.tuning import COMBAT, SPRINT_KEY
from uebp.nodes.actor import FN_IS_KEY_DOWN
from uebp.nodes.math import FN_OR
from uebp.nodes.move import (
    FN_GET_STAMINA, FN_IS_SPRINT_AHEAD, FN_IS_SPRINT_SPENT, FN_IS_SPRINTING,
    FN_SET_PACE, FN_SET_SPRINT_HELD)
from combat.weapon_component import vars as WV

# Set when a held sprint runs Stamina out, cleared by letting the key go.
SPRINT_SPENT_VAR = WV.SprintSpent


def _author_sprint(ed, pc_out, owner_out, key_pin, exec_ins):
    """Hold Shift to run, while there is stamina left to spend.

        SetSprintHeld(owner, ShiftDown OR SprintForced)
        SetPace(owner, BaseSpeed, SprintSpeed, drain, regen)
        SprintAhead, SprintSpent, Sprinting, Stamina = the movement's

    What the movement component does with the key, each move, on the owning
    client and on the server alike:

        SprintAhead = steering . facing >= cos(cone)
        SprintSpent = key AND (SprintSpent OR Stamina <= 0)
        Sprinting = key AND NOT SprintSpent AND SprintAhead
        speed = Sprinting ? SprintSpeed : jog (x the aim's slowdown)
        Stamina += (Sprinting ? -drain : +regen) * the move's time,  clamped

    SprintSpent is a latch, and it is what keeps a held key from strobing:
    with only "key AND Stamina > 0", a sprint that ran Stamina out stopped for
    one frame, that frame's regen put it back above zero, and the next frame
    sprinted again, and everything gated on NOT Sprinting (the aim, the ready
    pose) flipped with it. SprintAhead gates Sprinting only, not the latch, so
    turning away and back with the key held resumes the sprint.

    The four variables are this component's copies, written once a frame:
    the fire gate, the aim, the carry, the stance, the block, the HUD's bar
    and the breath all read them, as they did when this graph computed them.
    They are a frame behind the key (the movement ticks before this
    component does), which is the frame the old write of MaxWalkSpeed took
    to reach the movement too.

    SetPace hands over the numbers the menu's PLAYER SETTINGS tab changes in
    a running game (sprint_tuning.SPRINT_RATE_VARS and BaseSpeed). It does
    nothing on a client of a server: there the pace is the server's, which
    is the character's own (combat/player_move.py).

    SprintForced holds the key for a probe: no key can be pressed in a
    headless game.

    Returns the exec pins to carry on from.
    """
    g = _G(ed)
    down = g.keep(_node(ed, FN_IS_KEY_DOWN))
    _connect(pc_out, _pin(down, "self"))
    _connect(key_pin, _pin(down, "Key"))
    held = g.keep(_node(ed, FN_OR))
    _connect(out(down), _pin(held, "A"))
    _connect(g.get(SPRINT_FORCED_VAR), _pin(held, "B"))

    ask = g.call(FN_SET_SPRINT_HELD, exec_ins, Character=owner_out, bHeld=out(held))
    pace = g.call(FN_SET_PACE, (then(ask),), Character=owner_out,
                  JogSpeed=g.get(BASE_SPEED_VAR), SprintSpeed=g.get(SPRINT_SPEED_VAR),
                  StaminaDrainPerSecond=g.get(STAMINA_DRAIN_VAR),
                  StaminaRegenPerSecond=g.get(STAMINA_REGEN_VAR))
    flow = then(pace)
    for var, fn in ((SPRINT_AHEAD_VAR, FN_IS_SPRINT_AHEAD),
                    (SPRINT_SPENT_VAR, FN_IS_SPRINT_SPENT),
                    (WV.Sprinting, FN_IS_SPRINTING),
                    (WV.Stamina, FN_GET_STAMINA)):
        flow = g.put(var, out(g.call(fn, Character=owner_out)), (flow,))

    ed.add_comment_to_nodes(
        f"{SPRINT_KEY}: the key goes to the movement component, which sprints at "
        f"{SPRINT_SPEED_VAR} ({COMBAT.sprint_speed_cms:.0f} cm/s as built) while Stamina "
        f"lasts ({COMBAT.max_stamina / COMBAT.stamina_drain_per_s:.0f} s from full), "
        f"refilling at {COMBAT.stamina_regen_per_s:.0f}/s the moment it stops. Forwards "
        f"only: {SPRINT_AHEAD_VAR} is the steering within "
        f"{SPRINT_CONE_HALF_ANGLE_DEG:.0f} deg of the way the character faces. A sprint "
        f"that runs Stamina out latches {SPRINT_SPENT_VAR} until the key is let go, so "
        f"a held key cannot flip Sprinting (and the aim with it) every frame. All of "
        f"that is the movement component's (C++), predicted by the owning client and "
        f"decided by the server; {SPRINT_AHEAD_VAR}, {SPRINT_SPENT_VAR}, Sprinting and "
        f"Stamina here are copies of its answers. The fire gate below reads Sprinting: "
        f"you cannot shoot while running.",
        g.made)
    return (flow,)
