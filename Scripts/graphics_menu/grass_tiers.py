"""Grass density follows Quality: the graph fragment that shows or hides each
density tier. Chained into presets.author_grass_sync, so it runs exactly when
the grass lighting does -- on the first Tick and whenever Quality changes.

A tier above Low (forest_generator/grass_cells.GRASS_TIERS) is saved hidden in
game and tagged OW_GrassTier<n>. For each such tier:

    for each actor tagged OW_GrassTier<n>:
        SetActorHiddenInGame(Quality < tier.min_preset)

A hidden cell is skipped by the renderer before any of its instances is
culled, so an undrawn tier costs nothing but the one-off walk on a change.
"""

from combat.graph import BEL, _at, _connect, _loose_pin, _node, _pin, _set
from forest_generator.grass_cells import GRASS_TIERS, tier_tag

FN_WITH_TAG = "/Script/Engine.GameplayStatics.GetAllActorsWithTag"
FN_HIDE = "/Script/Engine.Actor.SetActorHiddenInGame"
FN_LT_II = "/Script/Engine.KismetMathLibrary.Less_IntInt"
MACRO_FOR_EACH = ("/Engine/EditorBlueprintResources/StandardMacros"
                  ".StandardMacros:ForEachLoop")

# The tiers the menu switches: every one not drawn at every preset.
SWITCHED_TIERS = tuple((i, t) for i, t in enumerate(GRASS_TIERS) if t.min_preset > 0)


def author_tier_visibility(ed, x0, y0, in_exec, quality):
    """Emit one tag walk per switched tier, chained from ``in_exec``.

    ``quality(x, y)`` makes a Quality getter and returns its output pin.
    Returns (exec pin the chain ends on, nodes made).
    """
    made = []

    def keep(n):
        made.append(n)
        return n

    flow = in_exec
    for row, (index, tier) in enumerate(SWITCHED_TIERS):
        x = x0 + row * 1400
        cells = keep(_at(_node(ed, FN_WITH_TAG), x, y0))
        _set(cells, "Tag", tier_tag(index))
        _connect(flow, _pin(cells, "execute"))

        loop = ed.add_macro_node(MACRO_FOR_EACH)
        if not loop:
            raise RuntimeError("could not create the ForEachLoop macro node")
        keep(_at(loop, x + 280, y0))
        _connect(_pin(cells, "OutActors", is_input=False), _loose_pin(loop, "Array"))
        _connect(BEL.find_then_pin(cells), _loose_pin(loop, "Exec"))

        below = keep(_at(_node(ed, FN_LT_II), x + 580, y0 + 300))
        _connect(quality(x + 340, y0 + 360), _pin(below, "A"))
        _set(below, "B", tier.min_preset)

        hide = keep(_at(_node(ed, FN_HIDE), x + 860, y0))
        _connect(_loose_pin(loop, "ArrayElement", is_input=False), _pin(hide, "self"))
        _connect(_pin(below, "ReturnValue", is_input=False), _pin(hide, "bNewHidden"))
        _connect(_loose_pin(loop, "LoopBody", is_input=False), _pin(hide, "execute"))

        flow = _loose_pin(loop, "Completed", is_input=False)
    return flow, made
