"""verify.loot -- the corpse loot roll on BP_HealthComponent (loot/roll.py).

The table's contents are verify_survival's (survival/verify/loot.py): they
are written by build_survival.py, once the items exist.
"""

import unreal

from combat.game_state import DAMAGED_BY_PLAYER_VAR
from combat.paths import HEALTH_BP_PATH
from combat.verify.common import BEL, PIN, by_pins, check, graph, in_pins, load
from loot.consts import BODY_ARRAYS, LOOT_ARRAYS, LOOT_CHANCES_VAR


def _title(n):
    return str(BEL.get_node_title(n)).replace("\n", " ")


def _feeders(n, pin):
    p = BEL.find_input_pin(n, pin)
    return [PIN.get_owning_node(q) for q in (p.list_connected_pins() if p else [])]


def _upstream(n, limit=400):
    """Every node whose exec reaches ``n``, walking execute pins backwards."""
    seen, todo = set(), [n]
    while todo and len(seen) < limit:
        cur = todo.pop()
        for pin in ("execute", "Exec"):
            for f in _feeders(cur, pin):
                if f not in seen:
                    seen.add(f)
                    todo.append(f)
    return seen


def check_loot_roll():
    bp = load(HEALTH_BP_PATH)
    names = {str(n) for n in BEL.list_member_variable_names(bp, False)}
    want = (LOOT_CHANCES_VAR, *(v for pair in LOOT_ARRAYS for v in pair))
    check("BP_HealthComponent declares the loot table and the body's Loot",
          all(v in names for v in want), str([v for v in want if v not in names]))
    body = unreal.get_default_object(BEL.generated_class(bp))
    check("...and a body starts carrying nothing",
          all(len(body.get_editor_property(v)) == 0 for v in BODY_ARRAYS))

    nodes = graph(bp).list_all_nodes()
    adds = [n for n in by_pins(nodes, "TargetArray", "NewItem")
            if any(_title(f) in [f"Get {v}" for v in BODY_ARRAYS]
                   for f in _feeders(n, "TargetArray"))]
    check("a kill fills Loot and its names, icons and tints, one Add each",
          sorted(_title(f) for n in adds for f in _feeders(n, "TargetArray"))
          == sorted(f"Get {v}" for v in BODY_ARRAYS), str(len(adds)))
    pairs = sorted((_title(g), _title(t)) for n in adds for t in _feeders(n, "TargetArray")
                   for f in _feeders(n, "NewItem") for g in _feeders(f, "TargetArray"))
    check("...each from the table's own array",
          pairs == sorted((f"Get {table}", f"Get {body}") for table, body in LOOT_ARRAYS),
          str(pairs))
    rolls = [n for n in by_pins(nodes, "A", "B")
             if any(_title(g) == f"Get {LOOT_CHANCES_VAR}"
                    for f in _feeders(n, "B") for g in _feeders(f, "TargetArray"))
             and any(not in_pins(f) and "Random" in _title(f) for f in _feeders(n, "A"))]
    check("...each entry rolled once: RandomFloat < LootChances[i]", len(rolls) == 1,
          str(len(rolls)))
    first = adds[0] if adds else None
    guards = [n for n in (_upstream(first) if first else ())
              if any(_title(f) == f"Get {DAMAGED_BY_PLAYER_VAR}"
                     for f in _feeders(n, "Condition"))]
    check("...only on a counted kill (behind DamagedByPlayer), like the shells",
          len(guards) == 1, str(len(guards)))


def run():
    check_loot_roll()
