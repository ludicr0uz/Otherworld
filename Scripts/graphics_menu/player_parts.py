"""The player's pieces a profile is made of, found and cast once.

The pawn, its health, weapon and survival components, and the player's
PlayerState (the kills; the HUD's owning controller's): the
save writes every one of them and the load writes them back. One chain of
exec casts, so everything past it can read the typed pins without a cast of
its own. A pawn without one of the components (a level where combat or
survival was never built) fails the chain and gets no profile.
"""

from uebp.graph import _connect, _loose_pin, _node, _palette, _pin, out, then
from combat.paths import HEALTH_CLASS_PATH, WEAPON_COMP_CLASS_PATH
from survival.paths import SURVIVAL_CLASS_PATH
from uebp.nodes.actor import FN_GET_COMP, FN_GET_OWNING_PC
from uebp.nodes.palette import NODE_CAST_SURVIVAL
from uebp.nodes.system import FN_GET_PLAYER_PAWN
from net.state_graph import CONTROLLER_CLASS_PATH, player_state_of


PAWN = "pawn"
STATE = "player state"

# (component class, its cast, the cast's output pin)
_COMPONENTS = (
    (HEALTH_CLASS_PATH, "Utilities|Casting|CastToBP_HealthComponent",
     "AsBPHealthComponent"),
    (WEAPON_COMP_CLASS_PATH, "Utilities|Casting|CastToBP_WeaponComponent",
     "AsBPWeaponComponent"),
    (SURVIVAL_CLASS_PATH, NODE_CAST_SURVIVAL, "AsBPSurvivalComponent"),
)


def author_player_parts(ed, in_execs, made):
    """Cast the pawn's components and the PlayerState, in one exec chain.

    Returns (the exec when every cast held, [every CastFailed pin], parts), where
    parts maps each component class path, PAWN and STATE to its typed pin.
    """
    pawn = _node(ed, FN_GET_PLAYER_PAWN)
    made.append(pawn)
    pawn_out = out(pawn)
    parts = {PAWN: pawn_out}
    fails = []
    flow = list(in_execs)
    for class_path, cast_name, as_name in _COMPONENTS:
        comp = _node(ed, FN_GET_COMP)
        _connect(pawn_out, _pin(comp, "self"))
        _pin(comp, "ComponentClass").set_pin_value(class_path)
        cast = _palette(ed, cast_name)
        _connect(out(comp), _pin(cast, "Object"))
        for e in flow:
            _connect(e, _pin(cast, "execute"))
        made += [comp, cast]
        parts[class_path] = _loose_pin(cast, as_name, is_input=False)
        fails.append(out(cast, "CastFailed"))
        flow = [then(cast)]
    owner = _node(ed, FN_GET_OWNING_PC)
    mine = player_state_of(ed, out(owner), CONTROLLER_CLASS_PATH, flow)
    made += [owner, *mine.nodes]
    parts[STATE] = mine.pin
    fails += mine.fails
    return mine.then, fails, parts

