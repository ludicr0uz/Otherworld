"""BP_DayNightCycle's Tick step for the item highlight: whether the items
lying on the ground glimmer.

    [Tick ...] --> SetScalarParameterValue(MPC_ItemGlimmer, "Highlight",
                                           ItemHighlight)

The glimmer itself is combat's (combat/glimmer.py: a sprite on every item,
shown while the item is Dropped, drawn with a material that multiplies by the
collection's Highlight). The switch is the world's: the cycle's ItemHighlight
(Instance Editable; world_config.ITEM_HIGHLIGHT, a WORLD SETTINGS row saved to
world_tuning.csv), 1 on and 0 off. Writing it every Tick is what makes the
tab's row live, and a collection scalar is one float: no item is told.

build_weapons_and_combat.py runs before build_day_night.py and makes the
collection. A level without a cycle keeps the collection's own default: on.

It goes into the chain before the night's cold, which stops at a level with
no player.
"""

from combat.glimmer_tuning import MPC_ITEM_GLIMMER, MPC_NAME, MPC_OBJECT_PATH, PARAM_HIGHLIGHT
from uebp.graph import _must_load, _pin
from uebp.nodes.system import FN_SET_MPC_SCALAR
from world.day_night_blueprint import ITEM_HIGHLIGHT_VAR
from world.day_night_graph import _call, _get


def author_item_highlight(ed, chain):
    """Extend the Tick chain with the write (see the module docstring)."""
    # A mistyped path would leave the pin empty and the node writing nothing.
    _must_load(MPC_ITEM_GLIMMER)
    write = chain.step(_call(ed, FN_SET_MPC_SCALAR, ParameterName=PARAM_HIGHLIGHT,
                             ParameterValue=_get(ed, ITEM_HIGHLIGHT_VAR)))
    pin = _pin(write, "Collection")
    pin.set_pin_value(MPC_OBJECT_PATH)
    got = str(pin.get_pin_value())
    if MPC_NAME not in got:
        raise RuntimeError(f"the Collection pin would not take {MPC_OBJECT_PATH!r}: {got!r}")
    ed.add_comment_to_nodes(
        f"The item highlight: {MPC_NAME}.{PARAM_HIGHLIGHT} := {ITEM_HIGHLIGHT_VAR} "
        "(1 on, 0 off), which every item's glimmer is multiplied by.", [write])
