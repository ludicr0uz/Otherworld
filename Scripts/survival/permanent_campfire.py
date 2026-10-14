"""BP_PermanentCampfire: the fire that burns at the Horde Survival level's
centre for as long as the level is open (forest_import/fort.py places it).

    BP_Campfire (the parent: the model, the glow, the crackle, the warmth)
      [BeginPlay] --> SetLifeSpan(0)        burns for ever; the parent's
                                            BeginPlay is not called

It is a child of BP_Campfire, so everything that knows a campfire knows this
one with no change: the zombies' Drawn step (GetAllActorsOfClass(BP_Campfire),
npc/drawn.py) walks them to it, the wendigos' ward holds them off it, a stick
takes its fire (CampfireClass), and its inherited Tick warms a player near
it, on the server.

Its own BeginPlay replaces the parent's, and calls nothing of it: the
parent's sets the burn time and notes the fire as a leftover
(net/leftover.py), and a server keeping at most CAMPFIRE fires would put out
the oldest, which this one always is. The life span is set to 0 (none)
rather than left alone, so the override has a node and compiles as one.
"""

from combat.log import _log
from uebp.graph import BEL, BGE, _assets, _connect, _create_blueprint, _must_load, _node, _palette, _pin, _set, then
from uebp.layout import arrange
from uebp.nodes.actor import FN_LIFESPAN
from uebp.nodes.palette import NODE_BEGIN_PLAY
from survival.paths import CAMPFIRE_BP_PATH, PERMANENT_CAMPFIRE_BP_PATH


def build_permanent_campfire():
    """BP_PermanentCampfire: BP_Campfire that never burns out."""
    parent = BEL.generated_class(_must_load(CAMPFIRE_BP_PATH))
    bp = _create_blueprint(PERMANENT_CAMPFIRE_BP_PATH, parent)
    if bp.get_blueprint_parent_class() != parent:
        raise RuntimeError(f"{PERMANENT_CAMPFIRE_BP_PATH} is not a child of BP_Campfire")
    ed = BGE.get_graph_editor_by_name(bp, "EventGraph")
    nodes = ed.list_all_nodes()
    if nodes:
        ed.remove_nodes(nodes)
    begin = _palette(ed, NODE_BEGIN_PLAY)
    life = _node(ed, FN_LIFESPAN)
    _set(life, "InLifespan", 0.0)
    _connect(then(begin), _pin(life, "execute"))
    ed.add_comment_to_nodes(
        "Burns for ever: no life span, no burn time, no cap on fires.", [begin, life])
    arrange(ed)
    if not BEL.compile_blueprint(bp):
        raise RuntimeError(f"{PERMANENT_CAMPFIRE_BP_PATH} failed to compile")
    _assets().save_loaded_asset(bp)
    _log(f"built {PERMANENT_CAMPFIRE_BP_PATH} (BP_Campfire that never burns out)")
    return bp
