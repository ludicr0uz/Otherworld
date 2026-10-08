"""verify.relevancy -- what the server sends and how often (task A2): the
player's character and the items carry the rows of net/relevancy_consts.py
on their class defaults (a child item inherits the base's); an item's own
Tick puts the actor to sleep while it lies still or is carried and wakes it
in flight, and the graphs that change a lying item's replicated state send
it once more (FlushNetDormancy: into and out of the world, the stick burning
out, a blade cooling). The campfire's row is verify_survival's, the
wanderers' verify_npc's.
"""

from combat import item_vars as IV
from combat.item_world import AWAKE, DORMANT
from combat.paths import (
    AXE_BP_PATH, CHARACTER_BP_PATH, ITEM_BP_PATH, KNIFE_BP_PATH, STICK_BP_PATH, WOOD_BP_PATH)
from combat.verify.common import before_marks, check, graph, load, pin_value
from combat.verify.fixtures import wg
from combat.verify.record import _title, _upstream
from combat.verify.world_items import _data_upstream
from combat.verify.interact import _sources
from net import relevancy
from net.relevancy_consts import CHARACTER, ITEM


def _flushes(nodes):
    return [n for n in nodes if _title(n).replace(" ", "") == "FlushNetDormancy"]


def check_rows():
    bp = load(CHARACTER_BP_PATH)
    check(f"the player's character is sent within {CHARACTER.cull_m:g} m, at "
          f"{CHARACTER.update_hz:g}/{CHARACTER.min_hz:g} Hz (net/relevancy_consts.py)",
          relevancy.matches(bp, CHARACTER), str(relevancy.read(bp)))
    for path in (ITEM_BP_PATH, STICK_BP_PATH, WOOD_BP_PATH, KNIFE_BP_PATH):
        bp = load(path)
        check(f"{bp.get_name()} is sent within {ITEM.cull_m:g} m, at "
              f"{ITEM.update_hz:g}/{ITEM.min_hz:g} Hz", relevancy.matches(bp, ITEM),
              str(relevancy.read(bp)))


def check_item_rests():
    nodes = list(graph(load(ITEM_BP_PATH)).list_all_nodes())
    sets = {pin_value(n, "NewDormancy"): n for n in nodes
            if _title(n).replace(" ", "") == "SetNetDormancy"}
    check(f"the item's own Tick sets NetDormancy {DORMANT} and {AWAKE}, once each",
          sorted(sets) == sorted((AWAKE, DORMANT)), str(sorted(sets)))
    if sorted(sets) != sorted((AWAKE, DORMANT)):
        return
    gates = {k: [b for b in _sources(n, "execute") if "Branch" in _title(b)]
             for k, n in sets.items()}
    reads = {k: {_title(f).replace(" ", "") for b in gs for c in _sources(b, "Condition")
                 for f in [c, *_data_upstream(c)]}
             for k, gs in gates.items()}
    check(f"...{DORMANT} while {IV.Dropped} or not {IV.InWorld}, {AWAKE} otherwise, off "
          f"one Branch on that",
          all(len(gs) == 1 for gs in gates.values())
          and gates[DORMANT] == gates[AWAKE]
          and {f"Get{IV.Dropped}", f"Get{IV.InWorld}"} <= reads[DORMANT],
          str({k: sorted(v) for k, v in reads.items()}))
    outer = [b for g in gates[DORMANT] for b in _sources(g, "execute") if "Branch" in _title(b)]
    change = {_title(f).replace(" ", "") for b in outer for c in _sources(b, "Condition")
              for f in [c, *_data_upstream(c)]}
    check(f"...and only on a change: the outer Branch compares that with {IV.Dormant}",
          len(outer) == 1 and f"Get{IV.Dormant}" in change and "NotEqual(Boolean)" in change,
          str(sorted(change)))
    remembered = {pin_value(n, IV.Dormant) for n in nodes if _title(n) == f"Set {IV.Dormant}"}
    check(f"...and {IV.Dormant} remembers which",
          remembered >= {"true"} and len(remembered) == 2, str(sorted(remembered)))
    authority = [n for n in sets.values()
                 if any("HasAuthority" in _title(c).replace(" ", "")
                        for b in _upstream(n) for c in _sources(b, "Condition"))]
    check("...with authority: a client's copy sets no dormancy", len(authority) == 2,
          str(len(authority)))


def check_wakes():
    item = list(graph(load(ITEM_BP_PATH)).list_all_nodes())
    enter = [n for n in _flushes(item)
             if any(_title(u) == f"Set {IV.InWorld}" for u in _upstream(n))]
    check("an item entering the world is sent once more (it may have lain dormant "
          "elsewhere, carried)", len(enter) == 1, f"{len(_flushes(item))} flush(es)")
    out = [n for n in _flushes(wg)
           if any(_title(u) == f"Set {IV.InWorld}" and pin_value(u, IV.InWorld) in ("false", "")
                  for u in _sources(n, "execute"))]
    check("the take sends the item out of the world once more, so every client hides "
          "its copy", len(out) == 1, f"{len(out)} of {len(_flushes(wg))} flush(es)")
    for path, var in ((STICK_BP_PATH, "Lit"), (KNIFE_BP_PATH, "Hot"), (AXE_BP_PATH, "Hot")):
        nodes = list(graph(load(path)).list_all_nodes())
        woke = [n for n in _flushes(nodes)
                if any(_title(u) == f"Set {var}"
                       for u in before_marks(_sources(n, "execute")))]
        check(f"{path.rsplit('/', 1)[-1]}: {var} lowered on the server's clock sends the "
              "lying item once more", len(woke) == 1, f"{len(woke)} flush(es)")


def run():
    check_rows()
    check_item_rests()
    check_wakes()
