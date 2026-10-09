"""A shot the server let through: the shot's one draw inside the accuracy
cloud, and the call that flies its pellets around it (FirePellets, C++:
Source/Otherworld, OtherworldWeaponComponentBase). The round and the cooldown
are that class's Server_Fire's; what each pellet shows is impact.py.
"""

from combat.game_state import DEBUG_MODE_VAR
from uebp.g import _G
from uebp.graph import _connect, _node, _pin, _set, out, then
from net.state_consts import GAME_STATE_CLASS_PATH
from net.state_graph import game_state
from combat.weapon_component.accuracy import AIM_SPREAD_VAR
from combat.lag_tuning import EXTRA_REWIND_S, MAX_REWIND_S
from combat.weapon_component.common import _prop
from combat.weapon_component import shot_hits
from uebp.nodes.math import FN_DEG2RAD, FN_NORMAL, FN_RAND_CONE, FN_SUB_VV
from uebp.nodes.weapon import FN_FIRE_PELLETS
from combat import item_vars as IV
from combat.weapon_component import vars as WV

# The shot's direction, drawn once per trigger pull inside AimSpread.
SHOT_DIRECTION_VAR = WV.ShotDirection


def _author_fire(ed, held, muzzle, aim, exec_in):
    """One shot the server let through (the body of ShotFired, shot.py): the
    draw inside the accuracy cloud, then the pellets. ``aim`` is where the
    shooter's reticle rested, the event's parameter; the sound is the
    shooter's own machine's (shot.py).

    The round and the cooldown are not here: the native Server_Fire spent
    and stamped them before it raised the event, so nothing downstream can
    leave the weapon having fired for free.

    All the aiming was done in _author_resolve_aim; what is left is the
    spread, in two layers. The shot draws ONE direction inside the accuracy
    cloud (AimSpread, around the muzzle-to-AimPoint line) into ShotDirection;
    then FirePellets (C++) jitters each pellet inside the weapon's own
    PelletSpreadDegrees, traces the weapon's own range and hands a body it
    strikes its damage. A single-round gun has no pattern, so its round flies
    down the draw: the same code path as the eight-pellet shotgun.
    """
    made = []

    def keep(n):
        made.append(n)
        return n

    # --- is anyone watching the tracers? -------------------------------------
    # Read once per shot and cached on this component, rather than read per
    # pellet: PelletFlew needs a plain bool it can branch on, and a
    # GetGameState plus a cast eight times over for one flag is eight times the
    # work for the same answer. Off the GameState, which every machine has.
    state = game_state(ed, [exec_in])
    for n in state.nodes:
        keep(n)
    flag = keep(ed.add_get_member_variable_node(DEBUG_MODE_VAR, GAME_STATE_CLASS_PATH))
    _connect(state.pin, _pin(flag, "self"))
    note = keep(ed.add_set_member_variable_node(DEBUG_MODE_VAR))
    _connect(out(flag, DEBUG_MODE_VAR), _pin(note, DEBUG_MODE_VAR))
    _connect(state.then, _pin(note, "execute"))
    # A GameState of the wrong class cannot say; not drawing is the safe answer,
    # and the component's own default is already false.
    ready = [then(note), *state.fails]

    delta = keep(_node(ed, FN_SUB_VV))
    _connect(aim, _pin(delta, "A"))
    _connect(muzzle, _pin(delta, "B"))
    direction_n = keep(_node(ed, FN_NORMAL))
    _connect(out(delta), _pin(direction_n, "A"))
    direction = out(direction_n)
    drawn = _author_shot_direction(ed, direction, ready, keep)

    # The pellets (C++, uebp/nodes/weapon.py): each inside the weapon's own
    # pattern around the stored draw, one ShotTrace each from the muzzle.
    # On a server a remote shooter's are judged against where every character
    # stood when it fired, by its round trip, within the cap
    # (combat/lag_tuning.py); a local shooter's against the present.
    pellets = keep(_node(ed, FN_FIRE_PELLETS))
    _connect(held, _pin(pellets, "Gun"))
    _connect(muzzle, _pin(pellets, "Muzzle"))
    shot_get = keep(ed.add_get_member_variable_node(SHOT_DIRECTION_VAR))
    _connect(out(shot_get, SHOT_DIRECTION_VAR), _pin(pellets, "Direction"))
    for pin, var in (("Pellets", IV.PelletCount), ("SpreadDegrees", IV.PelletSpreadDegrees),
                     ("Range", IV.WeaponRange), ("Damage", IV.Damage)):
        value, value_n = _prop(ed, var, held)
        keep(value_n)
        _connect(value, _pin(pellets, pin))
    _set(pellets, "MaxRewindSeconds", MAX_REWIND_S)
    _set(pellets, "ExtraRewindSeconds", EXTRA_REWIND_S)
    _connect(drawn, _pin(pellets, "execute"))

    ed.add_comment_to_nodes(
        "A shot the server let through (its round and cooldown are the native "
        "Server_Fire's): origin at the muzzle, direction muzzle -> the shooter's "
        "AimPoint drawn once inside AimSpread, then FirePellets (C++): each pellet "
        "inside the weapon's own pattern, judged where the shooter saw the others "
        "(ShotTrace, lag compensation), a body struck handed the round's damage "
        "times its zone. Each pellet comes back as PelletFlew (impact.py).",
        made)

    # What the pellets struck, told to every screen at once (shot_hits.py).
    told = shot_hits.flush(_G(ed), [then(pellets)])
    # The direction goes back too, so the shot's noise cone is the pellets' line.
    return told, direction


def _author_shot_direction(ed, direction, exec_ins, keep):
    """ShotDirection = a random direction within AimSpread of `direction`.

    Stored, because RandomUnitVectorInCone is pure: read per pellet it would
    be a new draw per pellet and the shotgun's pattern would lose its centre.
    Down the sights AimSpread is zero, and VRandCone returns the direction
    itself for a zero cone, so the shot goes exactly where the reticle is.
    Returns the exec pin to carry on from.
    """
    cloud = keep(ed.add_get_member_variable_node(AIM_SPREAD_VAR))
    rad = keep(_node(ed, FN_DEG2RAD))
    _connect(out(cloud, AIM_SPREAD_VAR), _pin(rad, "A"))
    draw = keep(_node(ed, FN_RAND_CONE))
    _connect(direction, _pin(draw, "ConeDir"))
    _connect(out(rad), _pin(draw, "ConeHalfAngleInRadians"))
    hold = keep(ed.add_set_member_variable_node(SHOT_DIRECTION_VAR))
    _connect(out(draw), _pin(hold, SHOT_DIRECTION_VAR))
    for e in exec_ins:
        _connect(e, _pin(hold, "execute"))
    return then(hold)
