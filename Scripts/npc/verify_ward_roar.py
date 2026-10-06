"""Checks for the two roars of a wendigo held off by fire (npc/ward_roar.py),
read back off the saved controllers. Run through
Scripts/verify_npc_blueprints.py.

What it proves, of each fire-fearing creature's BT_Ward: a hold's beginning
throws the time of its first roar, once; a held pass short of the hold's end
stands while a roar is under way, starts that roar when its time is up, the
once, and otherwise goes on round; the hold's end starts the same roar, and
the flight stands until it is over; a roar stops it, faces the player and
plays the clip and a voice, with no order; and a blow that lands on the
player (BT_Swing) writes the hold back to none. That it does so in the game
is probes/probe_wendigo_ward_roar.py's.
"""

import unreal

from net.players_consts import NEAREST_TITLE
from forest_generator.npc_placement import NPC_VARIANTS
from forest_generator.npc_stalk import NPC_STALK_ROAR
from forest_generator.npc_ward import (
    NPC_WARD_FEARS, NPC_WARD_ROAR_AT_S, NPC_WARD_ROAR_S, NPC_WARD_ROAR_VARY_S,
)
from npc.paths import (
    MELEE_SLOT, STEP_SWING, STEP_WARD, WARD_FLEE_UNTIL_VAR, WARD_ROAR_AT_VAR,
    WARD_ROAR_UNTIL_VAR, WARD_SINCE_VAR,
)
from npc.verify import (
    BEL, PIN, _close, _drivers, _exec_reach, _fed, _feeders, _ins, _lit, _num,
    _sources, _take_hits, _title, _titled, check, step_nodes,
)
from npc.verify_ward import _after, _ends, _tests, _titles, _zero


def _timed(branch, var):
    """Is ``branch`` exactly "now < ``var``"?"""
    return (_title(branch) == "Branch" and _titles(_sources(branch, "Condition"))
            == {"float < float", "GetTimeSeconds", f"Get {var}"})


def _stands(pin):
    """Does a pass leaving by ``pin`` succeed at once, with nothing else done?"""
    return (len(_after(pin)) == 1
            and _title(_after(pin)[0]).startswith("Set ")
            and _ends(pin) == {True})


def check_throw(tag, own):
    writes = _titled(own, f"Set {WARD_ROAR_AT_VAR}")
    thrown = [s for s in writes if _feeders(s, WARD_ROAR_AT_VAR)]
    sums = [a for s in thrown for a in _feeders(s, WARD_ROAR_AT_VAR)]
    throws = [r for a in sums for r in _feeders(a, "B")]
    begins = [s for s in _titled(own, f"Set {WARD_SINCE_VAR}")
              if _titles(_feeders(s, WARD_SINCE_VAR)) == {"GetTimeSeconds"}]
    check(f"{tag}: a hold's beginning throws its first roar "
          f"{NPC_WARD_ROAR_AT_S - NPC_WARD_ROAR_VARY_S:g}-"
          f"{NPC_WARD_ROAR_AT_S + NPC_WARD_ROAR_VARY_S:g} s on, one throw, read once",
          len(thrown) == 1 and len(begins) == 1 and thrown[0] in _exec_reach(begins[0])
          and len(sums) == 1 and _title(sums[0]) == "float + float"
          and _titles(_feeders(sums[0], "A")) == {"GetTimeSeconds"}
          and len(throws) == 1 and _title(throws[0]) == "RandomFloatInRange"
          and _close(_num(throws[0], "Min"), NPC_WARD_ROAR_AT_S - NPC_WARD_ROAR_VARY_S)
          and _close(_num(throws[0], "Max"), NPC_WARD_ROAR_AT_S + NPC_WARD_ROAR_VARY_S)
          and len(PIN.list_connected_pins(
              BEL.find_output_pin(throws[0], "ReturnValue"))) == 1,
          f"{len(writes)} writes of {WARD_ROAR_AT_VAR}, {len(thrown)} thrown")
    return [s for s in writes if s not in thrown]


def check_first_roar(tag, own, spent, given):
    """Returns the one Set of WardRoarUntil, or None."""
    waits = _after(BEL.find_else_pin(spent))
    check(f"{tag}: a held pass short of the hold's end stands while a roar is "
          f"under way (now < {WARD_ROAR_UNTIL_VAR}): no order, and it succeeds",
          len(waits) == 1 and _timed(waits[0], WARD_ROAR_UNTIL_VAR)
          and _stands(BEL.find_then_pin(waits[0])))
    if len(waits) != 1:
        return None
    dues = _after(BEL.find_else_pin(waits[0]))
    armed = [t for b in dues for t in _tests(b, "float > float")]
    up = [t for b in dues for t in _tests(b, "float <= float")]
    check(f"{tag}: ...then roars when {WARD_ROAR_AT_VAR} is set and up, both",
          len(dues) == 1 and _title(dues[0]) == "Branch"
          and _titles(_feeders(dues[0], "Condition")) == {"AND Boolean"}
          and len(armed) == 1 and len(up) == 1
          and _titles(_feeders(armed[0], "A")) == {f"Get {WARD_ROAR_AT_VAR}"}
          and _zero(armed[0], "B")
          and _titles(_feeders(up[0], "A")) == {f"Get {WARD_ROAR_AT_VAR}"}
          and _titles(_feeders(up[0], "B")) == {"GetTimeSeconds"})
    untils = _titled(own, f"Set {WARD_ROAR_UNTIL_VAR}")
    lasts = [a for u in untils for a in _feeders(u, WARD_ROAR_UNTIL_VAR)]
    check(f"{tag}: ...the once a hold ({WARD_ROAR_AT_VAR} back to 0), standing "
          f"{NPC_WARD_ROAR_S:g} s ({WARD_ROAR_UNTIL_VAR})",
          len(dues) == 1 and len(given) == 1 and _zero(given[0], WARD_ROAR_AT_VAR)
          and given[0] in _after(BEL.find_then_pin(dues[0]))
          and len(untils) == 1 and untils[0] in _after(BEL.find_then_pin(given[0]))
          and len(lasts) == 1 and _title(lasts[0]) == "float + float"
          and _titles(_feeders(lasts[0], "A")) == {"GetTimeSeconds"}
          and _close(_num(lasts[0], "B"), NPC_WARD_ROAR_S),
          f"{len(untils)} writes of {WARD_ROAR_UNTIL_VAR}")
    return untils[0] if len(untils) == 1 else None


def check_last_roar(tag, own, event, spent, until):
    gave_up = _exec_reach(_after(BEL.find_then_pin(spent))[0])
    flees = _titled(gave_up, f"Set {WARD_FLEE_UNTIL_VAR}")
    check(f"{tag}: the hold's end starts the same roar, once the flight is set up, "
          f"and gives no move order on that pass",
          len(_drivers(until)) == 2 and until in gave_up
          and len(flees) == 1 and until in _exec_reach(flees[0])
          and not _titled(gave_up, "SimpleMoveToLocation")
          and _ends(BEL.find_then_pin(spent)) == {True})
    heads = [b for b in _titled(own, "Branch") if _timed(b, WARD_FLEE_UNTIL_VAR)]
    waits = _after(BEL.find_then_pin(heads[0])) if len(heads) == 1 else []
    check(f"{tag}: ...and the flight stands until that roar is over, then runs",
          len(heads) == 1 and heads[0] in _exec_reach(event) and len(waits) == 1
          and _timed(waits[0], WARD_ROAR_UNTIL_VAR)
          and _stands(BEL.find_then_pin(waits[0]))
          and len(_titled(_exec_reach(_after(BEL.find_else_pin(waits[0]))[0]),
                          "SimpleMoveToLocation")) == 1)


def check_bellow(tag, until, key):
    roar = _exec_reach(until)
    stops, looks = _titled(roar, "StopMovement"), _titled(roar, "SetFocus")
    check(f"{tag}: a roar stops it and faces the player, with no move order, "
          f"and the pass succeeds",
          len(stops) == 1 and len(looks) == 1 and looks[0] in _exec_reach(stops[0])
          and _titles(_feeders(looks[0], "NewFocus")) == {NEAREST_TITLE}
          and not _titled(roar, "SimpleMoveToLocation")
          and _ends(BEL.find_then_pin(until)) == {True})
    clip = NPC_STALK_ROAR.get(key)
    eas = unreal.get_editor_subsystem(unreal.EditorAssetSubsystem)
    plays = [n for n in roar if {"Asset", "SlotNodeName"} <= _ins(n)]
    voices = [n for n in roar if {"Sound", "Location"} <= _ins(n)]
    if clip and eas.does_asset_exist(clip):
        check(f"{tag}: ...playing its roar clip in the upper-body slot, and a voice",
              len(plays) == 1 and _lit(plays[0], "Asset").split(".")[0] == clip
              and _lit(plays[0], "SlotNodeName") == MELEE_SLOT
              and len(voices) == 1 and plays[0] in _exec_reach(looks[0] if looks else until),
              f"{[_lit(p, 'Asset') for p in plays]}")
    else:
        check(f"{tag}: ...with a voice alone: it has no roar clip",
              not plays and len(voices) == 1)


def check_blow(tag, everything, fears):
    swing = step_nodes(everything, STEP_SWING)
    clears = [s for s in everything if _title(s) == f"Set {WARD_SINCE_VAR}"
              and not _feeders(s, WARD_SINCE_VAR)]
    landed = _take_hits(swing)
    if not fears:
        check(f"{tag}: does not fear fire: its blow clears no hold",
              not _titled(swing, f"Set {WARD_SINCE_VAR}"))
        return
    mine = [s for s in clears if s in swing]
    check(f"{tag}: a blow that lands on the player starts the hold over: "
          f"{WARD_SINCE_VAR} back to 0, after the damage is written",
          len(mine) == 1 and _zero(mine[0], WARD_SINCE_VAR) and len(landed) >= 1
          and all(mine[0] in _exec_reach(w) for w in landed)
          and len(clears) == 2,
          f"{len(mine)} in BT_{STEP_SWING}, {len(clears)} in all, "
          f"{len(landed)} damage writes")


def check_ward_roar(path, key):
    tag = path.rsplit("/", 1)[-1]
    bp = unreal.get_editor_subsystem(unreal.EditorAssetSubsystem).load_asset(path)
    if not bp:
        check(f"{tag}: exists, for its roars at the fire", False)
        return
    ed = unreal.BlueprintGraphEditor.get_graph_editor_by_name(bp, "EventGraph")
    everything = list(ed.list_all_nodes())
    check_blow(tag, everything, key in NPC_WARD_FEARS)
    own = step_nodes(everything, STEP_WARD)
    events = [n for n in own if n.get_class().get_name() == "K2Node_CustomEvent"]
    if key not in NPC_WARD_FEARS or len(events) != 1:
        return          # npc/verify_ward.py says which, and fails the second
    cdo = unreal.get_default_object(BEL.generated_class(bp))
    roars = {v: cdo.get_editor_property(v)
             for v in (WARD_ROAR_AT_VAR, WARD_ROAR_UNTIL_VAR)}
    check(f"{tag}: it starts with no roar due and none under way: two reals at 0",
          all(isinstance(v, float) and v == 0.0 for v in roars.values()), f"{roars}")
    spent = [b for b in _titled(own, "Branch")
             if any(_fed(t, "B", "ward_hold_s") for t in _tests(b, "float >= float"))]
    check(f"{tag}: one Branch ends the hold, for the roars to hang off",
          len(spent) == 1)
    if len(spent) != 1:
        return
    given = check_throw(tag, own)
    until = check_first_roar(tag, own, spent[0], given)
    if until is None:
        return
    check_last_roar(tag, own, events[0], spent[0], until)
    check_bellow(tag, until, key)


def run():
    for variant in NPC_VARIANTS:
        check_ward_roar(variant.ai_blueprint, variant.key)
