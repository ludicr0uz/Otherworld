"""verify.leftovers -- what is left in the world is noted for the server's
cleanup rule (task M31, net/leftover_consts.py): an item as it enters the
world (its own Tick, and the throw's release) with the ITEM row, struck off
by the take; a corpse (a wanderer's, a dead player's body) with the CORPSE
row, beside its lifespan. The campfire's is verify_survival's.
"""

from combat import item_vars as IV
from combat.paths import ITEM_BP_PATH, WEAPON_COMP_BP_PATH
from combat.verify.common import check, graph, load, pin_value
from combat.verify.fixtures import hg
from combat.verify.interact import _sources
from combat.verify.record import _title, _upstream
from net.leftover_checks import carries, left_nodes, taken_nodes
from net.leftover_consts import CORPSE, ITEM


def _in_world_sets(nodes, value):
    return [n for n in nodes if _title(n) == f"Set {IV.InWorld}"
            and (pin_value(n, IV.InWorld) == "true") == value]


def _rows(nodes, row):
    return all(carries(n, row)[0] for n in nodes), str([carries(n, row)[1] for n in nodes])


def check_items():
    item = list(graph(load(ITEM_BP_PATH)).list_all_nodes())
    noted = left_nodes(item)
    entered = [n for n in noted if any(_title(u) == f"Set {IV.InWorld}" for u in _upstream(n))]
    check("an item entering the world in its own Tick is noted as left there, once, "
          f"behind the Set of {IV.InWorld}", len(noted) == 1 and len(entered) == 1,
          f"{len(noted)} node(s), {len(entered)} behind the Set")
    ok, read = _rows(noted, ITEM)
    check(f"...with the ITEM row: {ITEM.lifetime_s:g} s, at most {ITEM.cap} "
          "(net/leftover_consts.py)", bool(noted) and ok, read)
    check("...its own actor: the Actor pin is left to default to self",
          all(not _sources(n, "Actor") for n in noted), str(len(noted)))

    comp = list(graph(load(WEAPON_COMP_BP_PATH)).list_all_nodes())
    into, out_of = _in_world_sets(comp, True), _in_world_sets(comp, False)
    noted = left_nodes(comp)
    after = [n for n in noted if any(u in into for u in _upstream(n, 4))]
    check(f"the component's graph notes an item it sends into the world (the throw's "
          f"release), one node a Set of {IV.InWorld} true",
          len(into) >= 1 and len(noted) == len(into) == len(after),
          f"{len(into)} set(s), {len(noted)} node(s), {len(after)} behind one")
    ok, read = _rows(noted, ITEM)
    check("...with the ITEM row, and the item on the Actor pin",
          bool(noted) and ok and all(_sources(n, "Actor") for n in noted), read)
    struck = taken_nodes(comp)
    behind = [n for n in struck if any(u in out_of for f in _sources(n, "execute")
                                       for u in _sources(f, "execute"))]
    check(f"...and the take strikes it off: one node a Set of {IV.InWorld} false, "
          "behind the flush that sends it, the item on its Actor pin",
          len(out_of) >= 1 and len(struck) == len(out_of) == len(behind)
          and all(_sources(n, "Actor") for n in struck),
          f"{len(out_of)} set(s), {len(struck)} node(s), {len(behind)} behind one")


def check_corpses():
    noted = left_nodes(hg)
    beside = [n for n in noted
              if any(_title(u).replace(" ", "") == "SetLifeSpan" for u in _sources(n, "execute"))]
    check("a corpse is noted as left in the world straight off its lifespan: a "
          "wanderer's, and a dead player's body on a server",
          len(noted) == 2 and len(beside) == 2, f"{len(noted)} node(s), {len(beside)} "
          "behind a SetLifeSpan")
    ok, read = _rows(noted, CORPSE)
    check(f"...with the CORPSE row: its own lifespan, at most {CORPSE.cap}",
          bool(noted) and ok and all(_sources(n, "Actor") for n in noted), read)


def run():
    check_items()
    check_corpses()
