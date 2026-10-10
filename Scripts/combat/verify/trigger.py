"""verify.trigger -- the fire key as an Enhanced Input action (I1;
combat/input_assets.py, weapon_component/trigger.py): IA_Fire and the
mapping context that maps it to the default key, their names on the player
character's class defaults, the event the weapon component stamps the press
in, and that its Tick reads the stamp and the native held flag and polls no
fire key.

That the press of the action fires the gun in a game, and that rebinding
moves the context's key: probes/probe_fire_action.py; on a client of a
server, probe_net_fire_action.py.
"""

import unreal

from combat.input_consts import (
    CONTEXT_PROP, FIRE_ACTION_PROP, IA_FIRE, IMC_DEFAULT, MAPPINGS)
from combat.paths import CHARACTER_BP_PATH
from combat.tuning import FIRE_BIND, FIRE_KEY
from combat.verify.common import BEL, PIN, cdo, check, graph, load
from combat.verify.fixtures import wc, wg, wg_dead
from combat.weapon_component.vars import FireForced, FirePressedAt
from uebp.nodes.weapon import FIRE_HELD

EVENT = "Event OnFirePressed"


def _title(n):
    return str(BEL.get_node_title(n)).replace("\n", " ")


def _squash(n):
    return _title(n).replace(" ", "")


def _feeds(node, pin):
    p = BEL.find_input_pin(node, pin)
    return [PIN.get_owning_node(q) for q in PIN.list_connected_pins(p)] if p else []


def check_assets():
    action, context = load(IA_FIRE), load(IMC_DEFAULT)
    check("IA_Fire is a bool with no trigger of its own: Started is the press",
          action.get_editor_property("value_type") == unreal.InputActionValueType.BOOLEAN
          and not list(action.get_editor_property("triggers")))
    check("...that triggers while paused (a button held through a pause is no "
          "new press when it ends) and takes its key from nothing else",
          bool(action.get_editor_property("trigger_when_paused"))
          and not action.get_editor_property("consume_input"))
    rows = [(m.get_editor_property("action").get_path_name().split(".")[0],
             m.get_editor_property("key").export_text())
            for m in context.get_editor_property("default_key_mappings").mappings]
    check(f"IMC_Default maps one row per action, to its default key: {list(MAPPINGS)}",
          rows == list(MAPPINGS), str(rows))
    check(f"...the trigger to {FIRE_KEY}, the first row of the settings' binds ({FIRE_BIND})",
          (IA_FIRE, FIRE_KEY) in rows, str(rows))
    player = cdo(load(CHARACTER_BP_PATH))
    check("the player character names the context and the fire action for its native parent",
          player.get_editor_property(CONTEXT_PROP) == context
          and player.get_editor_property(FIRE_ACTION_PROP) == action,
          f"{player.get_editor_property(CONTEXT_PROP)}, "
          f"{player.get_editor_property(FIRE_ACTION_PROP)}")


def check_graph():
    every = list(graph(wc).list_all_nodes())
    events = [n for n in every if _title(n) == EVENT]
    check("the weapon component has the base's OnFirePressed event, once",
          len(events) == 1, str(len(events)))
    stamps = [PIN.get_owning_node(q) for e in events
              for q in PIN.list_connected_pins(BEL.find_then_pin(e))]
    check("...which stamps FirePressedAt with the world's time and does nothing else",
          len(stamps) == 1 and _title(stamps[0]) == f"Set {FirePressedAt}"
          and [_squash(x) for x in _feeds(stamps[0], str(FirePressedAt))] == ["GetTimeSeconds"]
          and not PIN.list_connected_pins(BEL.find_then_pin(stamps[0])),
          str([_title(s) for s in stamps]))
    reads = [n for n in wg if _title(n) == f"Get {FirePressedAt}"]
    users = [u for r in reads for p in BEL.list_output_pins(r)
             for u in (PIN.get_owning_node(q) for q in PIN.list_connected_pins(p))]
    check("the Tick's tap is the stamp equal to the world's time now, or the probe's stand-in",
          len(users) == 1 and "GetTimeSeconds" in {_squash(x) for x in _feeds(users[0], "B")}
          and any(f"Get {FireForced}" in {_title(x) for x in _feeds(o, "B")}
                  for p in BEL.list_output_pins(users[0])
                  for o in (PIN.get_owning_node(q) for q in PIN.list_connected_pins(p))),
          f"{len(reads)} read(s), {[_squash(u) for u in users]}")
    held = [n for n in wg if _squash(n) == f"Get{FIRE_HELD}"]
    check("...and its hold the native base's FireHeld, read once",
          len(held) == 1, str(len(held)))
    check("no node of the component reads a KeyFire, in the dead arm either",
          not [n for n in every + list(wg_dead) if _squash(n).endswith(FIRE_BIND)])
    check("...and the component has no such variable",
          not hasattr(cdo(wc), FIRE_BIND) and _no_property(cdo(wc), FIRE_BIND))


def _no_property(obj, name):
    try:
        obj.get_editor_property(name)
    except Exception:
        return True
    return False


def run():
    check_assets()
    check_graph()
