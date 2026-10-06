"""A player killed by another player: the kill's credit (task M15).

Nothing else about a player hurting a player is its own code. A pellet, a
swing and a thrown blade each take health off whatever carries a
BP_HealthComponent through its TakeHit (damage.py), with the target's own
hit-box tables, and a player's character carries one as a wanderer's does. So
the one thing a fight between players adds is who is credited:

    a player's body dies (DespawnOnDeath false), on the server
      --> LastInstigator is a PlayerController     a wanderer's blow names its
                                                   AI controller, the
                                                   world-floor net no one
      --> and not this body's own                  a blade that came back
      --> its PlayerState.PlayerKillCount + 1

The count is a row of the PlayerState's table (net/state_consts.py), apart
from the wanderers' NpcKillCount, and replicates to everyone. It is taken at
the death itself, once the body is down and before the settle's Delay: by
the respawn the controller has let go of the body, and GetController answers
None.

LastInstigator is the last blow's, however long ago: a player who bleeds out
or starves after another player's blow is that player's kill, until a
wanderer's blow names someone else. Friendly fire is on: there are no teams
to ask yet (M33).
"""

from combat import health_vars as HV
from net.state_consts import PLAYER_KILL_COUNT_VAR, PLAYER_STATE_CLASS_PATH
from net.state_graph import CONTROLLER_CLASS_PATH, player_state_of
from uebp.g import _G
from uebp.graph import _connect, _loose_pin, _palette, _pin, _set, else_, out, then
from uebp.nodes.actor import FN_GET_CONTROLLER, FN_GET_OWNER
from uebp.nodes.math import FN_ADD_II, FN_NE_OO
from uebp.nodes.palette import (
    MACRO_SWITCH_AUTHORITY_COMP, NODE_CAST_PAWN, NODE_CAST_PLAYER_CONTROLLER)


def author_player_kill(ed, exec_in):
    """Credit this body's death to the player who struck the last blow.
    ``exec_in`` is the death path's player arm; returns the exec pins to carry
    on from, whoever was or was not credited."""
    g = _G(ed)
    server = g.keep(ed.add_macro_node(MACRO_SWITCH_AUTHORITY_COMP))
    _connect(exec_in, _pin(server, "execute"))

    by = g.keep(_palette(ed, NODE_CAST_PLAYER_CONTROLLER))
    _connect(g.get(HV.LastInstigator), _pin(by, "Object"))
    _connect(out(server, "Authority"), _pin(by, "execute"))
    killer = _loose_pin(by, "AsPlayerController", is_input=False)

    body = g.keep(_palette(ed, NODE_CAST_PAWN))
    _connect(out(g.call(FN_GET_OWNER)), _pin(body, "Object"))
    _connect(then(by), _pin(body, "execute"))
    own = g.call(FN_GET_CONTROLLER, self=_loose_pin(body, "AsPawn", is_input=False))
    other, itself = g.branch(out(g.call(FN_NE_OO, A=killer, B=out(own))), [then(body)])

    credited = player_state_of(ed, killer, CONTROLLER_CLASS_PATH, [other])
    g.made.extend(credited.nodes)
    tally = g.keep(ed.add_get_member_variable_node(PLAYER_KILL_COUNT_VAR, PLAYER_STATE_CLASS_PATH))
    _connect(credited.pin, _pin(tally, "self"))
    one_more = g.call(FN_ADD_II, A=out(tally, PLAYER_KILL_COUNT_VAR))
    _set(one_more, "B", 1)
    write = g.keep(ed.add_set_member_variable_node(PLAYER_KILL_COUNT_VAR, PLAYER_STATE_CLASS_PATH))
    _connect(credited.pin, _pin(write, "self"))
    _connect(out(one_more), _pin(write, PLAYER_KILL_COUNT_VAR))
    _connect(credited.then, _pin(write, "execute"))

    ed.add_comment_to_nodes(
        "A player's death, on the server: the last blow's instigator, where that is a "
        "player's controller and not this body's own, has one more player kill on its "
        "PlayerState. A wanderer's blow names an AI controller and the world-floor net "
        "no one, so neither is anybody's.", g.made)
    return (then(write), out(server, "Remote"), out(by, "CastFailed"),
            out(body, "CastFailed"), itself, *credited.fails)
