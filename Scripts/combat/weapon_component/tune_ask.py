"""AskTune: a tuning tab's table, sent by a client of a server (task M32).

    AskTune(Table, Values)    a reliable Server event, the RPC guard first
      the GameState is there, and its DevTuning is true (a server started
      with -AllowDevTuning; single player's is always true):
        Table == i            GameState.<TUNED[i]> := Values

The table goes no further here: the GameState's four arrays are an inbox,
which the server's tuner (graphics_menu/game_tuner.py, a component of the
GameState) checks for length, takes and applies. That builder comes after
this one and knows the tables; this graph names no creature, gun or cycle.
A server that does not allow tuning drops the table, whatever the client's
own tab let it send: the tab's read-only rows are display.
"""

from combat.ask_consts import ASK_TUNE, TABLE_PARAM, TUNE_TABLES, VALUES_PARAM
from net import state_consts as S
from net.guard import author_guard
from net.state_graph import game_state
from uebp.g import _G
from uebp.graph import out, then
from uebp.net import server_event
from uebp.nodes.math import FN_EQ_II
from uebp.vars import FLOAT, INT, array


def author_tune_ask(ed):
    """The event (see the module docstring)."""
    if len(S.TUNED) != len(TUNE_TABLES):
        raise RuntimeError("one inbox per gameplay table")
    event = server_event(ed, ASK_TUNE, [(TABLE_PARAM, INT), (VALUES_PARAM, array(FLOAT))])
    g = _G(ed)
    flow, _refused = author_guard(g, ASK_TUNE, [then(event)])
    got = game_state(ed, [flow])
    g.made += got.nodes
    allowed = g.iget(got.pin, S.DevTuning, S.GAME_STATE_CLASS_PATH)
    flow, _shut = g.branch(allowed, [got.then])
    for i, inbox in enumerate(S.TUNED):
        this = g.call(FN_EQ_II, A=out(event, TABLE_PARAM), B=i)
        take, flow = g.branch(out(this), [flow])
        g.iput(got.pin, inbox, out(event, VALUES_PARAM), [take], S.GAME_STATE_CLASS_PATH)
    ed.add_comment_to_nodes(
        f"{ASK_TUNE}: a client's tuning tab sends its table; the server takes it into "
        "the GameState's inbox only where DevTuning is true (-AllowDevTuning), and "
        "its tuner applies it (tune_ask.py).", [event] + g.made)
