"""The controller's Tune* variables: one real per npc/monster_tuning.MONSTER_STATS
entry, holding this creature's numbers.

Every sense, patrol, melee, speed and health fragment reads its number off
one of these rather than a pin literal, so the M panel's MONSTER TUNING tab
can change a live wanderer by writing its controller (the HUD does, every
Tick once something is tuned: graphics_menu/monster_tune_tick.py). Their
defaults are the creature's monster_specs(), written onto the CDO after the
compile (write_tuned_defaults), because add_member_variable's own default
does not apply.
"""

from npc.graph import BEL, _at, _pin
from npc.monster_tuning import MONSTER_STATS, TUNED_VAR


def declare_tuned_vars(ed):
    for _col, var, *_rest in MONSTER_STATS:
        ed.remove_member_variable(var)
        if not ed.add_member_variable(var, BEL.get_basic_type_by_name("real")):
            raise RuntimeError(f"could not declare {var}")


def tuned(ed, column, x, y):
    """A Get of the Tune variable for ``column``: ``(node, output pin)``."""
    var = TUNED_VAR[column]
    node = _at(ed.add_get_member_variable_node(var), x, y)
    return node, _pin(node, var, is_input=False)


def tuned_pin(g, column, x, y):
    """The same Get, kept by a npc.graph._Graph: its output pin."""
    node, pin = tuned(g.ed, column, x, y)
    g.made.append(node)
    return pin


def write_tuned_defaults(cdo, specs):
    """specs: {column: value}. Written and read back."""
    for col, var, *_rest in MONSTER_STATS:
        cdo.set_editor_property(var, float(specs[col]))
    wrong = [var for col, var, *_rest in MONSTER_STATS
             if abs(float(cdo.get_editor_property(var)) - float(specs[col])) > 1e-4]
    if wrong:
        raise RuntimeError(f"Tune defaults did not stick: {wrong}")


def tuned_values(cdo):
    """{column: value} as the CDO holds them (for the verifier)."""
    return {col: float(cdo.get_editor_property(var)) for col, var, *_r in MONSTER_STATS}

