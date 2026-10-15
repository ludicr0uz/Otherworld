"""verify.pickup -- the pick-up (weapon_component/pickup.py), interact's item
kind: the target interact kept, cast to an item, is asked for once, after the
search, while there is room; the take is Server_Take's (task M20), which
asks again on the machine that owns the inventory; and a weapon, or a
blade that was Lodged, goes into empty hands.

How the target is chosen is verify/interact.py's. That a pick-up joins the
inventory without switching to it is verify/weapon_inputs.py's.

What the take puts in the inventory is TakeItem (task A2): the item asked
for, or, where it was placed in the level, a fresh one of its class, the
level's destroyed.

The reach down for it (weapon_component/pickup_clip.py): the skin's pick-up
clip, played once into the upper-body slot by Fx_PickUpClip, which the owner
calls off the ask and the server tells the others of after the take; and the
two pose plays that would cut it short ask for it first.
"""

from combat import item_vars as IV
from combat.anim_blueprint import AIM_SLOT
from combat.fx_vars import PICKUP_CLIP, fx_event
from combat.pickup_tuning import PICKUP_CLIP_START_S
from combat.skin import player_skin
from combat.slot_tuning import (
    HAND, HAND_FROM_VAR, HAS_ROOM_VAR, NOT_A_WEAPON, SLOT_VAR, WEAPON_KIND_VAR)
from combat.strike_vars import ITEM_PARAM, SERVER_TAKE, TAKE_REACH_CM
from combat.verify.common import (
    BEL, before_marks, by_pins, check, graph, in_pins, num_pin, past_marks, pin_value)
from combat.verify.anchor import event_nodes
from combat.verify.fixtures import w, wc, wg
from combat.verify.fx import calls, in_fx, predicts
from combat.verify.interact import _exec_from, _reads, _sources, _then, _title
from combat.verify.punch import _feeds
from combat.verify.shot import _calls_of
from combat.weapon_component import vars as WV
from combat.weapon_component.interact import INTERACT_TARGET_VAR
from combat.weapon_component.pickup_clip import PICKUP_ANIM_VAR


def _target_as_item(node, pin):
    """Is ``pin`` fed by a cast of InteractTarget, not of a loop's element?"""
    casts = [s for s in _sources(node, pin) if "Cast" in _title(s)]
    return len(casts) == 1 and _reads(casts[0], "Object", INTERACT_TARGET_VAR)


def _event_item(node, pin):
    """Is ``pin`` fed by Server_Take's own Item, the item the client asked for?"""
    event = graph(wc).find_event_node(SERVER_TAKE)
    return event is not None and _sources(node, pin) == [event]


def _taken_item(node, pin):
    """Is ``pin`` fed by TakeItem, what the take puts in the inventory?"""
    return _reads(node, pin, WV.TakeItem) and len(_sources(node, pin)) == 1


def check_pickup_takes_once():
    adds = by_pins(wg, "TargetArray", "NewItem")
    takes = [a for a in adds if _taken_item(a, "NewItem")]
    # (The loot take adds the item it has just spawned: verify/asks.py.)
    looped = [a for a in adds if a not in takes
              and any("Cast" in _title(s) and not any(
                  "SpawnTransform" in in_pins(o) for o in _sources(s, "Object"))
                  for s in _sources(a, "NewItem"))]
    check(f"the take, in {SERVER_TAKE}, adds the item the client asked for to the "
          "inventory, and nothing adds a loop's own element",
          len(takes) == 1 and not looped,
          f"{len(takes)} take(s), {len(looped)} add(s) inside a loop")
    if len(takes) != 1:
        return

    # Backwards from the add: Detach <- TakenFromWorld <- FlushNetDormancy <- Set InWorld <- Set Dropped
    # <- Set TakeItem (the item, or a fresh one) <- Branch(IsLevelActor) <- Branch(free).
    looses = [n for n, _pin in _exec_from(takes[0])]
    check("the taken item is detached from whatever it was left in (a body a "
          "thrown blade struck), staying where it is",
          len(looses) == 1 and "detachfromactor" in _title(looses[0]).replace(" ", "").lower()
          and _taken_item(looses[0], "self")
          and all(pin_value(looses[0], r) == "KeepWorld"
                  for r in ("LocationRule", "RotationRule", "ScaleRule")),
          ", ".join(_title(n) for n in looses))
    if len(looses) != 1:
        return
    struck = [n for n, _pin in _exec_from(looses[0])]
    check("the taken item is struck off the server's list of what is left in the "
          "world (TakenFromWorld, M31): no lifetime runs on a carried item",
          len(struck) == 1 and _title(struck[0]).replace(" ", "").lower() == "takenfromworld"
          and _taken_item(struck[0], "Actor"), ", ".join(_title(n) for n in struck))
    if len(struck) != 1:
        return
    wakes = [n for n, _pin in _exec_from(struck[0])]
    check("the taken item, dormant where it lay, is sent once more (FlushNetDormancy)",
          len(wakes) == 1 and _title(wakes[0]).replace(" ", "") == "FlushNetDormancy"
          and _taken_item(wakes[0], "self"), ", ".join(_title(n) for n in wakes))
    if len(wakes) != 1:
        return
    worlds = [n for n, _pin in _exec_from(wakes[0])]
    check(f"the taken item is out of the world ({IV.InWorld} lowered: each client's "
          "copy of it goes)",
          len(worlds) == 1 and _title(worlds[0]) == f"Set {IV.InWorld}"
          and pin_value(worlds[0], IV.InWorld) in ("false", "")
          and _taken_item(worlds[0], "self"), ", ".join(_title(n) for n in worlds))
    if len(worlds) != 1:
        return
    flags = [n for n, _pin in _exec_from(worlds[0])]
    check("the taken item stops being Dropped",
          len(flags) == 1 and _title(flags[0]) == "Set Dropped"
          and pin_value(flags[0], "Dropped") in ("false", "")
          and _taken_item(flags[0], "self"),
          ", ".join(_title(n) for n in flags))
    if len(flags) != 1:
        return
    writes = [n for n, _pin in _exec_from(flags[0])]
    kept = [n for n in writes if _title(n) == f"Set {WV.TakeItem}" and _event_item(n, WV.TakeItem)]
    fresh = [n for n in writes if _title(n) == f"Set {WV.TakeItem}" and n not in kept]
    check(f"{WV.TakeItem} is written twice before that: the item asked for, or a fresh one",
          len(writes) == 2 and len(kept) == 1 and len(fresh) == 1,
          ", ".join(_title(n) for n in writes))
    if len(kept) != 1 or len(fresh) != 1:
        return
    # The fresh one: Set TakeItem <- DestroyActor(the level's) <- Cast <- SpawnActor(its class,
    # where it lies) <- Branch(IsLevelActor).then; the kept one off its else.
    gone = [n for n, _pin in _exec_from(fresh[0])]
    spawned = [n for n, _pin in _exec_from(gone[0])] if len(gone) == 1 else []
    spawns = [n for n, _pin in _exec_from(spawned[0])] if len(spawned) == 1 else []
    check("the fresh one is spawned of the level item's class where it lies, and the "
          "level's destroyed: the engine tells every client, late joiners too (A2)",
          len(gone) == 1 and "destroyactor" in _title(gone[0]).replace(" ", "").lower()
          and _event_item(gone[0], "self")
          and len(spawned) == 1 and "Cast" in _title(spawned[0])
          and len(spawns) == 1 and "SpawnTransform" in in_pins(spawns[0])
          and any(_title(s).replace(" ", "") == "GetClass" and _event_item(s, "Object")
                  for s in _sources(spawns[0], "Class"))
          and any(_event_item(s, "self") for s in _sources(spawns[0], "SpawnTransform")),
          " <- ".join(_title(n) for n in gone + spawned + spawns))
    levels = _exec_from(spawns[0]) if len(spawns) == 1 else []
    kept_from = _exec_from(kept[0])
    check("...off a Branch on IsLevelActor(Item): then the fresh one, else the item itself",
          len(levels) == 1 and levels[0][1] == "then" and len(kept_from) == 1
          and kept_from[0][1] == "else" and levels[0][0] == kept_from[0][0]
          and any(_title(c).replace(" ", "") == "IsLevelActor" and _event_item(c, "Actor")
                  for c in _sources(levels[0][0], "Condition")),
          str([pin for _n, pin in levels + kept_from]))
    if len(levels) != 1:
        return
    rooms = _exec_from(levels[0][0])
    behind = (_feeds(BEL.find_input_pin(rooms[0][0], "Condition"))
              if len(rooms) == 1 else [])
    names = {_title(n) for n in behind}
    reach = [n for n in behind if num_pin(n, "B") == TAKE_REACH_CM
             and any("Distance" in _title(f) for f in _sources(n, "A"))]
    check(f"...only an item still Dropped, within {TAKE_REACH_CM:g} cm of this "
          f"machine's copy of the taker, while there is room ({HAS_ROOM_VAR}): two "
          "players reaching for one item, the first ask takes it",
          len(rooms) == 1 and rooms[0][1] == "then" and len(reach) == 1
          and {"Get Dropped", f"Get {HAS_ROOM_VAR}"} <= names, str(sorted(names)))

    # --- the ask, where the keys are ---------------------------------------------
    asks = [n for n in _calls_of(SERVER_TAKE) if _target_as_item(n, ITEM_PARAM)]
    check(f"the Tick asks for the take in one place: {INTERACT_TARGET_VAR}, cast to "
          "an item", len(asks) == 1, f"{len(asks)} ask(s)")
    if len(asks) != 1:
        return
    rooms = _exec_from(asks[0])
    fits = [c for n, _pin in rooms for c in _sources(n, "Condition")]
    check(f"...only while this copy has room ({HAS_ROOM_VAR}: a bag slot or the hand free)",
          len(rooms) == 1 and rooms[0][1] == "then" and len(fits) == 1
          and _title(fits[0]) == f"Get {HAS_ROOM_VAR}",
          f"{len(rooms)} gate(s)")
    if len(rooms) != 1:
        return
    casts = _exec_from(rooms[0][0])
    check(f"...only when the target is an item ({INTERACT_TARGET_VAR}'s cast "
          "took it)",
          len(casts) == 1 and casts[0][1] == "then" and "Cast" in _title(casts[0][0])
          and _reads(casts[0][0], "Object", INTERACT_TARGET_VAR),
          ", ".join(f"{_title(n)}.{pin}" for n, pin in casts))
    if len(casts) != 1:
        return
    founds = _exec_from(casts[0][0])
    valid = [c for n, _pin in founds for c in _sources(n, "Condition")]
    check(f"...and only when a target was kept ({INTERACT_TARGET_VAR} is valid)",
          len(founds) == 1 and founds[0][1] == "then" and len(valid) == 1
          and _reads(valid[0], "Object", INTERACT_TARGET_VAR),
          f"{len(founds)} gate(s)")
    if len(founds) != 1:
        return
    entries = _exec_from(founds[0][0])
    check("the ask runs once per press: off the loop's Completed, not its body",
          [pin for _n, pin in entries] == ["Completed"],
          str([pin for _n, pin in entries]))


def check_weapon_to_hand():
    """A weapon (melee or ranged), or a blade taken back out of a tree or a
    body, goes to empty hands."""
    hands = [n for n in wg if _title(n) == f"Set {SLOT_VAR}"
             and pin_value(n, SLOT_VAR) in (str(HAND), "")
             and not _sources(n, SLOT_VAR) and _taken_item(n, "self")]
    check("the take puts the item in the hand in one place",
          len(hands) == 1, f"{len(hands)} Set {SLOT_VAR} = HAND on the target")
    if len(hands) != 1:
        return
    gate = _exec_from(hands[0])
    conds = [c for n, _pin in gate for c in _sources(n, "Condition")]
    check("...behind one Branch, after the take set it UNPLACED",
          len(gate) == 1 and gate[0][1] == "then" and len(conds) == 1
          and [_title(n) for n in before_marks([n for n, _pin in _exec_from(gate[0][0])])]
          == [f"Set {SLOT_VAR}"],
          f"{len(gate)} gate(s)")
    if len(gate) != 1 or len(conds) != 1:
        return
    bare = [h for v in _sources(conds[0], "A") for h in _sources(v, "A")
            for o in _sources(h, "Object")]
    held = [_title(o) for v in _sources(conds[0], "A") for h in _sources(v, "A")
            for o in _sources(h, "Object")]
    check(f"...only with empty hands ({WV.Held} is not valid)",
          len(bare) == 1 and held == [f"Get {WV.Held}"], str(held))
    either = _sources(conds[0], "B")
    kinds = [k for e in either for ne in _sources(e, "A") for k in _sources(ne, "A")]
    nots = [pin_value(ne, "B") for e in either for ne in _sources(e, "A")]
    lodged = [_title(l) for e in either for l in _sources(e, "B")]
    check(f"...and only a weapon (its {WEAPON_KIND_VAR} not NOT_A_WEAPON, melee or "
          f"ranged) or an item that was {IV.Lodged} (a thrown blade left in a tree "
          "or a body)",
          [_title(k) for k in kinds] == [f"Get {WEAPON_KIND_VAR}"]
          and nots == [str(NOT_A_WEAPON)] and lodged == [f"Get {IV.Lodged}"]
          and all(_taken_item(k, "self") for k in kinds),
          f"{[_title(k) for k in kinds]} != {nots}, or {lodged}")
    froms = past_marks(_then(hands[0]))
    check(f"...{HAND_FROM_VAR} its {WEAPON_KIND_VAR}: its slot's key puts it away",
          len(froms) == 1 and _title(froms[0]) == f"Set {HAND_FROM_VAR}"
          and [_title(f) for f in _sources(froms[0], HAND_FROM_VAR)]
          == [f"Get {WEAPON_KIND_VAR}"],
          ", ".join(_title(n) for n in froms))
    if len(froms) != 1:
        return
    lowers = past_marks(_then(froms[0]))
    into = sorted(pin for _n, pin in _exec_from(lowers[0])) if len(lowers) == 1 else []
    check(f"...the item no longer {IV.Lodged}, in the hand or not",
          len(lowers) == 1 and _title(lowers[0]) == f"Set {IV.Lodged}"
          and pin_value(lowers[0], IV.Lodged) in ("false", "")
          and _taken_item(lowers[0], "self") and into == ["else", "then"],
          f"{[_title(n) for n in lowers]} from {into}")


def _reads_clip(node):
    return any(_title(f) == f"Get {PICKUP_ANIM_VAR}"
               for f in _feeds(BEL.find_input_pin(node, "Asset")))


def is_pickup_play(node):
    """The play of the pick-up's clip: a play (it has a rate) whose Asset is
    PickUpAnim. The keep-alive's and the equip's IsPlayingSlotAnimation read
    it through an Asset pin too, and are not plays."""
    return "InPlayRate" in in_pins(node) and _reads_clip(node)


def check_pickup_clip():
    """The reach down: the skin's pick-up clip, played by the owner off the
    ask and by the others at the server's word, and kept in the slot."""
    skin = player_skin()
    anim = w.get_editor_property(str(PICKUP_ANIM_VAR))
    check("the pick-up's clip is the worn skin's (none on a skin without one)",
          (anim.get_path_name().split(".")[0] if anim else None) == skin.pickup,
          f"{anim} for {skin.pickup}")
    plays = [n for n in by_pins(wg, "Asset", "SlotNodeName", "InPlayRate") if _reads_clip(n)]
    fx_plays = in_fx(PICKUP_CLIP, plays)
    check(f"...played once, in {fx_event(PICKUP_CLIP)}, into {AIM_SLOT}, upper body "
          f"only, at its own rate, from {PICKUP_CLIP_START_S:g} s in",
          len(plays) == 1 and fx_plays == plays
          and pin_value(plays[0], "SlotNodeName") == AIM_SLOT
          and num_pin(plays[0], "InPlayRate") in (None, 1.0)
          and num_pin(plays[0], "LoopCount") in (None, 1.0)
          and num_pin(plays[0], "InTimeToStartMontageAt") == PICKUP_CLIP_START_S,
          f"{len(plays)} play(s), {len(fx_plays)} in the cosmetic")
    if len(plays) == 1:
        gates = _exec_from(plays[0])
        check("...only where there is a clip (a Branch on IsValid of it)",
              len(gates) == 1 and gates[0][1] == "then" and _title(gates[0][0]) == "Branch"
              and any(_title(f) == f"Get {PICKUP_ANIM_VAR}"
                      for f in _feeds(BEL.find_input_pin(gates[0][0], "Condition"))),
              str([_title(n) for n, _pin in gates]))
    mine = predicts(PICKUP_CLIP)
    asks = [n for n in _calls_of(SERVER_TAKE) if _target_as_item(n, ITEM_PARAM)]
    check(f"the owner plays it off the ask: {fx_event(PICKUP_CLIP)} right after the "
          f"call of {SERVER_TAKE} (in single player, the frame the item goes)",
          len(mine) == 1 and len(asks) == 1
          and _exec_from(mine[0]) == [(asks[0], "then")],
          f"{len(mine)} own play(s), {len(asks)} ask(s)")
    told = calls(PICKUP_CLIP)
    refreshes = [n for n, _pin in _exec_from(told[0])] if len(told) == 1 else []
    check(f"the server tells the others after the take: once, under {SERVER_TAKE}, "
          f"after {WV.NeedsRefresh} is raised",
          len(told) == 1 and [_title(n) for n in refreshes] == [f"Set {WV.NeedsRefresh}"]
          and told[0] in event_nodes(SERVER_TAKE), str([_title(n) for n in refreshes]))
    readers = [n for n in by_pins(wg, "Asset", "SlotNodeName")
               if "InPlayRate" not in in_pins(n) and _reads_clip(n)]
    branches = [n for n in wg if _title(n) == "Branch"]
    guarded = [r for r in readers if any(
        r in _feeds(BEL.find_input_pin(b, "Condition")) for b in branches)]
    check("the keep-alive and the equip ask whether the clip is in the slot before "
          "they put a pose there (a montage just started reads as a quiet slot)",
          len(readers) == 2 and guarded == readers,
          f"{len(readers)} reader(s), {len(guarded)} behind a Branch")


def run():
    check_pickup_takes_once()
    check_weapon_to_hand()
    check_pickup_clip()
