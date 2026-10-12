"""The verifiers' check that a graph notes what it leaves in the world by its
row of net/leftover_consts.py (task M31): the LeftInWorld nodes of a graph,
each with the row's kind, lifetime and cap on its pins.
"""

import unreal

from net.leftover_consts import Leftover

BEL = unreal.BlueprintEditorLibrary
PIN = unreal.BlueprintGraphPinLibrary


def _title(node):
    return str(BEL.get_node_title(node)).replace("\n", " ").replace(" ", "").lower()


def _value(node, name):
    return str(PIN.get_pin_value(BEL.find_input_pin(node, name)))


def left_nodes(nodes):
    """The nodes of ``nodes`` that note an actor as left in the world."""
    return [n for n in nodes if _title(n) == "leftinworld"]


def taken_nodes(nodes):
    """...and that strike one off."""
    return [n for n in nodes if _title(n) == "takenfromworld"]


def carries(node, row: Leftover):
    """Whether the node's pins are the row's: (ok, what they read)."""
    kind, life, cap = (_value(node, "Kind"), _value(node, "LifetimeSeconds"),
                       _value(node, "Cap"))
    try:
        ok = (kind == row.kind and abs(float(life or 0.0) - row.lifetime_s) < 1e-3
              and int(cap or 0) == row.cap)
    except ValueError:
        ok = False
    return ok, f"kind {kind}, lifetime {life}, cap {cap}"
