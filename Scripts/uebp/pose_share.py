"""An anim graph's pose that feeds more than one input.

The graph editor lets one pose output be linked to two inputs when Python
makes the links, and the compile accepts it. The engine then updates the node
behind that output once per link that reaches it, each with the frame's whole
delta (FPoseLinkBase::Update has no guard), and evaluates it as often. So
everything under a pose linked twice plays at twice its speed, and two such
places one after the other play it at four times: the weapon layers' two
upper-body blends each took the pose as their base and as their slot's
source, and the player's motion matching under them ran its clips 4 x 0.85
(the play rate it picked) = 3.4 times too fast, measured
(probes/probe_gas_anim_speed.py). The wanderers' graphs had the same two.

The engine's own answer is a cached pose: Save cached pose updates and
evaluates what feeds it once a frame, however many Use cached pose nodes read
it. So:

    share(ed)     every pose output with more than one link gets a Save
                  cached pose, and each input it fed a Use cached pose of its
                  own. Last thing before the compile that a body will run.
    unshare(ed)   the inverse: the plain links back. First thing a builder
                  that walks the graph does, so the builders (and the
                  fragments they find by following links) still meet the
                  chain they were written against.
    fed(pin)      the pins linked to ``pin``, read through a cached pose: what
                  a verifier, or a builder's helper a verifier calls, follows
                  instead of PIN.list_connected_pins.
    fanouts(ed)   the pose outputs with more than one link: none in a graph
                  that is worn (combat/verify/pose_share.py).

A cached pose is local space. No graph here fans a component-space pose out;
share() refuses one.
"""

from uebp.graph import BEL, BGE, PIN, _connect, _palette, _pin, out
from uebp.nodes.palette import NODE_SAVE_POSE

SAVE_CLASS = "AnimGraphNode_SaveCachedPose"
USE_CLASS = "AnimGraphNode_UseCachedPose"
# The caches this makes: OwPose1, OwPose2, ... (no spaces: a palette path
# drops them). A cache of another name is someone else's and is left alone.
PREFIX = "OwPose"
LOCAL_POSE_PIN = "Pose"


def use_path(name):
    """The palette path of the node that reads the cache ``name``."""
    return f"Animation|CachedPoses|Usecachedpose'{name}'"


def _class(node):
    return node.get_class().get_name()


def _links(pin):
    return list(PIN.list_connected_pins(pin))


def _ordinal(node):
    """Creation order: the trailing integer of the node's object name."""
    head, _, tail = node.get_name().rpartition("_")
    return (head, int(tail)) if tail.isdigit() else (node.get_name(), -1)


def _cache_of(node):
    """The cache a Save or a Use cached pose node names, or None for a cache
    that is not one of these."""
    if _class(node) == SAVE_CLASS:
        name = str(node.get_editor_property("cache_name"))
    elif _class(node) == USE_CLASS:
        # A Use node holds its Save node, not a name Python can read: its
        # title is "Use cached pose '<name>'".
        name = str(BEL.get_node_title(node)).partition("'")[2].rpartition("'")[0]
    else:
        return None
    return name if name.startswith(PREFIX) else None


def _caches(ed):
    """{name: (the Save node, [its Use nodes])} of the caches share() made."""
    found = {}
    for node in ed.list_all_nodes():
        name = _cache_of(node)
        if name is None:
            continue
        save, uses = found.get(name, (None, []))
        if _class(node) == SAVE_CLASS:
            if save is not None:
                raise RuntimeError(f"two Save cached pose nodes are named {name}")
            save = node
        else:
            uses = uses + [node]
        found[name] = (save, uses)
    for name, (save, uses) in found.items():
        if save is None:
            raise RuntimeError(f"{len(uses)} Use cached pose '{name}' and no Save node")
    return found


def fanouts(ed):
    """[(pose output pin, [the input pins it feeds])] for every anim node's
    output with more than one link, in the nodes' creation order."""
    found = []
    nodes = [n for n in ed.list_all_nodes() if _class(n).startswith("AnimGraphNode_")]
    for node in sorted(nodes, key=_ordinal):
        for pin in BEL.list_output_pins(node):
            links = _links(pin)
            if len(links) > 1:
                found.append((pin, links))
    return found


def unshare(ed):
    """Put the plain links back where share() put cached poses. Returns how
    many caches there were. Nothing is compiled or saved here."""
    caches = _caches(ed)
    for name in sorted(caches):
        save, uses = caches[name]
        source = _links(_pin(save, LOCAL_POSE_PIN))
        onward = [pin for use in uses for pin in _links(out(use, LOCAL_POSE_PIN))]
        ed.remove_nodes([save] + uses)
        if not source:
            raise RuntimeError(f"Save cached pose '{name}' was fed by nothing; refusing "
                               "to guess how the chain went")
        for pin in onward:
            _connect(source[0], pin)
    return len(caches)


def share(ed):
    """A cached pose at every pose output with more than one link. Returns
    how many it made. Run it last, before the compile; a graph it has already
    been run on has no such output left and is not touched."""
    taken = set(_caches(ed))
    made = 0
    for pin, links in fanouts(ed):
        if str(PIN.get_pin_name(pin)) != LOCAL_POSE_PIN:
            raise RuntimeError(
                f"{BEL.get_node_title(PIN.get_owning_node(pin))} feeds its "
                f"{PIN.get_pin_name(pin)} to {len(links)} inputs: a cached pose is "
                "local space, so a component-space pose cannot be shared")
        name = next(f"{PREFIX}{i}" for i in range(1, len(taken) + 2)
                    if f"{PREFIX}{i}" not in taken)
        taken.add(name)
        PIN.break_pin_links(pin)
        save = _palette(ed, NODE_SAVE_POSE)
        save.set_editor_property("cache_name", name)
        if _cache_of(save) != name:
            raise RuntimeError(f"the Save cached pose is named {_cache_of(save)!r}, "
                               f"not {name!r}")
        _connect(pin, _pin(save, LOCAL_POSE_PIN))
        uses = []
        for link in links:
            use = _palette(ed, use_path(name))
            if _cache_of(use) != name:
                raise RuntimeError(f"asked for a Use cached pose '{name}', got "
                                   f"{BEL.get_node_title(use)}")
            _connect(out(use, LOCAL_POSE_PIN), link)
            uses.append(use)
        ed.add_comment_to_nodes(
            f"{name}: this pose feeds {len(links)} inputs, so it is a cached pose. Linked "
            "straight to each, the engine updates everything under it once per link "
            "and plays it that many times too fast. Scripts/uebp/pose_share.py.",
            [save] + uses)
        made += 1
    return made


def _editor_of(node):
    """The graph editor of the graph ``node`` is in (a node's outer is its
    graph, and an anim graph's outer its Blueprint)."""
    graph = node.get_outer()
    ed = BGE.get_graph_editor_by_name(graph.get_outer(), graph.get_name())
    if not ed:
        raise RuntimeError(f"no graph editor for {graph.get_path_name()}")
    return ed


def fed(pin):
    """The pins linked to ``pin``, read through a cached pose: an input fed by
    a Use node is fed by what feeds its Save node, and an output that feeds a
    Save node feeds what its Use nodes feed. Any other link is itself, so
    this stands in for PIN.list_connected_pins wherever a graph is read."""
    caches = None
    found = []
    for link in _links(pin):
        node = PIN.get_owning_node(link)
        name = _cache_of(node)
        if name is None:
            found.append(link)
            continue
        caches = caches if caches is not None else _caches(_editor_of(node))
        save, uses = caches[name]
        if _class(node) == USE_CLASS:
            found += _links(_pin(save, LOCAL_POSE_PIN))
        else:
            found += [q for use in uses for q in _links(out(use, LOCAL_POSE_PIN))]
    return found
