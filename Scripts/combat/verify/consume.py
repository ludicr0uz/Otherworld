"""verify.consume -- the fire press that eats an item does not also fire.

Mirrors weapon_component/consume.py. Eating empties the slot, the next item is
equipped the same frame, and the key is still down: TriggerSpent is what keeps
that press from firing it. Checked on the wiring, since a headless run has no
mouse to hold down.
"""

from uebp import net
from combat.tuning import SERVER_CONSUME
from combat.weapon_component.consume import TRIGGER_SPENT
from uebp.nodes.weapon import FIRE_HELD
from combat.verify.fixtures import wc, wc_cdo, wg
from combat.verify.common import BEL, PIN, by_pins, check, graph, in_pins, out_pins, pin_value


def _title(n):
    return str(BEL.get_node_title(n)).replace("\n", " ")


def _feeders(node, pin):
    p = BEL.find_input_pin(node, pin)
    return [PIN.get_owning_node(q) for q in PIN.list_connected_pins(p)] if p else []


def _exec_after(node, limit=40):
    """Nodes reached by following `then` pins forward from node."""
    seen, cur = [], node
    while cur is not None and len(seen) < limit:
        then = BEL.find_then_pin(cur)
        nxt = [PIN.get_owning_node(q) for q in PIN.list_connected_pins(then)] if then else []
        cur = nxt[0] if nxt else None
        if cur is not None:
            seen.append(cur)
    return seen


def _reached(node, limit=400):
    """Every node an exec link leads to from node, down every arm."""
    seen, todo = [], [node]
    while todo and len(seen) < limit:
        for p in BEL.list_output_pins(todo.pop()):
            for q in PIN.list_connected_pins(p):
                nxt = PIN.get_owning_node(q)
                if str(PIN.get_pin_name(q)) == "execute" and nxt not in seen:
                    seen.append(nxt)
                    todo.append(nxt)
    return seen


def _upstream(pin, limit=200):
    """Every node feeding pin, over data links only (see verify.firing)."""
    seen, stack = set(), [pin]
    while stack and len(seen) < limit:
        for q in PIN.list_connected_pins(stack.pop()):
            node = PIN.get_owning_node(q)
            if node in seen:
                continue
            seen.add(node)
            stack.extend(x for x in BEL.list_input_pins(node)
                         if str(PIN.get_pin_name(x)) != "execute")
    return seen


def check_eating_spends_the_press():
    got = wc_cdo.get_editor_property(TRIGGER_SPENT)
    check(f"{TRIGGER_SPENT} exists and starts False", got is False, repr(got))

    sets = [n for n in wg if n.get_class().get_name() == "K2Node_VariableSet"
            and TRIGGER_SPENT in in_pins(n)]
    spends = [n for n in sets if pin_value(n, TRIGGER_SPENT) == "true"
              and not _feeders(n, TRIGGER_SPENT)]
    rearms = [n for n in sets if _feeders(n, TRIGGER_SPENT)]
    # The throw's click is spent the same way (verify/throw.check_click), and
    # so is the press that puts a garment on (verify/wear.py).
    check(f"{TRIGGER_SPENT} is written four times: spent by eating, by wearing and "
          f"by the throw, re-armed each frame",
          len(sets) == 4 and len(spends) == 3 and len(rearms) == 1,
          f"{len(sets)} sets, {len(spends)} spend, {len(rearms)} re-arm")

    # The use is the server's (M26): the key's arm asks and spends the press,
    # and Server_Consume sends the event, then destroys the item.
    asks = [n for n in wg if _title(n).replace(" ", "").replace("_", "") == SERVER_CONSUME.replace("_", "")
            and "execute" in in_pins(n)]
    after_ask = _exec_after(asks[0], 2) if len(asks) == 1 else []
    check(f"...the key's arm asks the server ({SERVER_CONSUME}) and spends the press "
          "next, and eats nothing itself",
          bool(after_ask) and after_ask[0] in spends, str([_title(n) for n in after_ask]))
    event = graph(wc).find_event_node(SERVER_CONSUME)
    check(f"{SERVER_CONSUME} is a reliable Server event",
          bool(event) and net.compiled_rpc(wc, SERVER_CONSUME) == (net.SERVER, True),
          str(net.compiled_rpc(wc, SERVER_CONSUME)) if event else "no event")
    sends = by_pins(wg, "Actor", "EventTag", "Payload")
    served = _reached(event) if event else []
    chain = [_title(n) for n in _exec_after(event)] if event else []
    after_send = [_title(n) for n in _exec_after(sends[0])] if len(sends) == 1 else []
    check("...which asks the guard, refuses a Held that is not there, not Consumable or "
          "a garment (three Branches), then sends the use event once, and only then destroys the item",
          chain[:5] == ["Allow"] + ["Branch"] * 4 and len(sends) == 1 and "Destroy Actor" in after_send
          and sends[0] in served,
          f"{chain[:6]} / {after_send}")

    if rearms:
        ands = _feeders(rearms[0], TRIGGER_SPENT)
        feeds = {_title(n) for a in ands for n in _feeders(a, "A") + _feeders(a, "B")}
        check("...re-armed as TriggerSpent AND the fire action down (FireHeld), so only "
              "a release clears it",
              len(ands) == 1 and "AND" in _title(ands[0]).upper()
              and f"Get {TRIGGER_SPENT}" in feeds
              and f"Get {FIRE_HELD}" in feeds, str(feeds))

    # The outer fire gate is the Branch whose True pin leads to the Consumable
    # test. Its condition must refuse a spent press -- which also shuts the
    # ready gate, the shot and the dry click behind it.
    branches = [n for n in wg if n.get_class().get_name() == "K2Node_IfThenElse"]
    # Server_Consume tests Consumable too, behind its own IsValid: not a fire gate.
    outer = [b for b in branches if b not in served
             if any("Consumable" in out_pins(f)
                    for nxt in _exec_after(b, 1)
                    if nxt.get_class().get_name() == "K2Node_IfThenElse"
                    for f in _feeders(nxt, "Condition"))]
    check("one fire gate opens onto the Consumable test", len(outer) == 1, str(len(outer)))
    if outer:
        up = _upstream(BEL.find_input_pin(outer[0], "Condition"))
        nots = [n for n in up if "NOT" in _title(n).upper()
                and any(f"Get {TRIGGER_SPENT}" == _title(f) for f in _feeders(n, "A"))]
        check("...and its condition refuses a spent press (NOT TriggerSpent)",
              len(nots) == 1, str(sorted(_title(n) for n in up)))
        pre = [PIN.get_owning_node(q) for q in
               PIN.list_connected_pins(BEL.find_input_pin(outer[0], "execute"))]
        check("...with the re-arm run just before it, so a release frame is armed",
              bool(rearms) and pre == [rearms[0]], str([_title(n) for n in pre]))


def run():
    check_eating_spends_the_press()
