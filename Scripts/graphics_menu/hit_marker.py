"""The headshot mark: an X round the reticle for a moment after a round or a
thrown blade of the player's struck a head. The weapon component stamps the
time (combat weapon_component/headshot.py); reticle.py calls in here last, on
every arm on which the component is valid -- the crosshair, the scope, the
iron sights that hide the crosshair, and empty hands (a thrown knife leaves
them empty) -- so the X is drawn whatever stands on the centre.
"""

from combat.headshot_tuning import HEADSHOT_MARK_SECONDS
from combat.weapon_component import vars as WV
from uebp.graph import _connect, _node, _pin, _set, else_, out, then
from uebp.nodes.actor import FN_DRAW_HUD_LINE
from uebp.nodes.math import FN_ADD_FF, FN_LESS_FF, FN_SUB_FF
from uebp.nodes.system import FN_TIME_SECONDS

WEAPON_COMP_CLASS_PATH = "/Game/Weapons/BP_WeaponComponent.BP_WeaponComponent_C"

# Four strokes on the diagonals, where the crosshair's ticks (on the axes)
# never are: from MARK_INNER to MARK_OUTER pixels off the centre each way.
MARK_INNER = 9.0
MARK_OUTER = 20.0
MARK_THICK = 2.0
# The reticle's own white: the mark is told by its shape, not by a colour.
COL_MARK = "(R=0.960000,G=0.960000,B=0.970000,A=0.900000)"


def _author_headshot_mark(ed, in_execs, as_weapon, cx, cy):
    """Draw the X while now - HeadshotTime < HEADSHOT_MARK_SECONDS.

    ``in_execs`` all lie past the weapon component's cast, so the Get off
    ``as_weapon`` is never an Accessed None. Game time on both sides: the
    stamp is GetTimeSeconds. Returns the exec pins the frame goes on by."""
    made = []

    def keep(n):
        made.append(n)
        return n

    when = keep(ed.add_get_member_variable_node(WV.HeadshotTime, WEAPON_COMP_CLASS_PATH))
    _connect(as_weapon, _pin(when, "self"))
    now = keep(_node(ed, FN_TIME_SECONDS))
    since = keep(_node(ed, FN_SUB_FF))
    _connect(out(now), _pin(since, "A"))
    _connect(out(when, WV.HeadshotTime), _pin(since, "B"))
    fresh = keep(_node(ed, FN_LESS_FF))
    _connect(out(since), _pin(fresh, "A"))
    _set(fresh, "B", HEADSHOT_MARK_SECONDS)
    shown = keep(ed.add_branch_node())
    _connect(out(fresh), _pin(shown, "Condition"))
    for e in in_execs:
        _connect(e, _pin(shown, "execute"))

    def off(centre, by):
        n = keep(_node(ed, FN_ADD_FF))
        _connect(centre, _pin(n, "A"))
        _set(n, "B", by)
        return out(n)

    flow = then(shown)
    for sx in (-1.0, 1.0):
        for sy in (-1.0, 1.0):
            line = keep(_node(ed, FN_DRAW_HUD_LINE))
            _connect(off(cx, sx * MARK_INNER), _pin(line, "StartScreenX"))
            _connect(off(cy, sy * MARK_INNER), _pin(line, "StartScreenY"))
            _connect(off(cx, sx * MARK_OUTER), _pin(line, "EndScreenX"))
            _connect(off(cy, sy * MARK_OUTER), _pin(line, "EndScreenY"))
            _set(line, "LineColor", COL_MARK)
            _set(line, "LineThickness", MARK_THICK)
            _connect(flow, _pin(line, "execute"))
            flow = then(line)

    ed.add_comment_to_nodes(
        "The headshot mark: an X round the centre of the viewport for "
        f"{HEADSHOT_MARK_SECONDS:g} s after the weapon component's "
        "HeadshotTime (a round or a thrown blade that struck a head). Four "
        "strokes on the diagonals, in the reticle's white, drawn over the "
        "crosshair, the scope or the iron sights alike.",
        made)
    return [flow, else_(shown)]
