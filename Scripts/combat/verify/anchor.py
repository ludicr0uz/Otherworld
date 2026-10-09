"""verify.anchor -- how a check finds its node without counting the graph.

A check that counts a kind of node over the whole graph ("Loaded is written
four times") fails the day another feature legitimately adds one, and says
nothing about where the four are. A check here starts from something with a
name (an event, a variable's read or write, a fragment's gate) and steps along
the links from it, asserting what it finds wired there:

  event_nodes(name)  the nodes of one named event: what it runs, and the pure
                     nodes feeding those
  feeders(node, pin) the nodes linked into one input pin
  runs(node, pin)    the nodes one exec output runs
  pure_feeds(node)   everything feeding a node through data links
  the(nodes)         the node a step arrives at, or None when it arrives at
                     none or at several

``the`` is for a step from an anchor (what is linked at a pin, what a
fragment's own nodes hold), never for a filter of the whole graph: that is the
count again under another name (Scripts/combat/CLAUDE.md, "Verifiers mirror
builders").
"""

import functools

from combat.verify.common import BEL, PIN, graph, has_in_pin
from combat.verify.fixtures import _is_exec, exec_reach, wc


def title(node):
    return str(BEL.get_node_title(node)).replace("\n", " ")


def the(nodes):
    """The one node a step from an anchor arrives at, else None."""
    nodes = list(nodes)
    return nodes[0] if len(nodes) == 1 else None


def feeders(node, pin):
    p = BEL.find_input_pin(node, pin)
    return [PIN.get_owning_node(q) for q in PIN.list_connected_pins(p)] if p else []


def runs(node, pin=None):
    """The nodes ``node``'s exec outputs run next: one output's by name, or
    all of them."""
    return [PIN.get_owning_node(q) for p in BEL.list_output_pins(node)
            if _is_exec(p) and (pin is None or str(PIN.get_pin_name(p)) == pin)
            for q in PIN.list_connected_pins(p)]


def pure_feeds(node):
    """Every node feeding ``node`` through data links, not looking past a node
    with an exec pin: what such a node gives out was stored when it ran."""
    seen, stack = [], [node]
    while stack:
        for pin in BEL.list_input_pins(stack.pop()):
            if str(PIN.get_pin_name(pin)) == "execute":
                continue
            for q in PIN.list_connected_pins(pin):
                src = PIN.get_owning_node(q)
                if src in seen:
                    continue
                seen.append(src)
                if not has_in_pin(src, "execute"):
                    stack.append(src)
    return seen


def reads(node):
    """The titles of everything feeding ``node``: ``"Get Loaded" in reads(n)``."""
    return {title(n) for n in pure_feeds(node)}


def event(name):
    return graph(wc).find_event_node(name)


@functools.lru_cache(maxsize=None)
def event_nodes(name):
    """Every node of one of the weapon component's named events: the event,
    what its exec runs, and the pure nodes feeding those. A call of another
    event is a node of this one; that event's body is not."""
    ev = event(name)
    if ev is None:
        return ()
    found = [ev] + exec_reach([p for p in BEL.list_output_pins(ev) if _is_exec(p)])
    for n in list(found):
        found += [f for f in pure_feeds(n) if f not in found]
    return tuple(found)


def in_event(name, node_title):
    """The nodes of the named event with this title."""
    return [n for n in event_nodes(name) if title(n) == node_title]
