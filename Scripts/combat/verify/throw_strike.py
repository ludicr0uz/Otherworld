"""verify.throw_strike -- what a thrown blade does to what it strikes
(weapon_component/throw_strike.py): who has a ThrowDamage, how the knife and
the axe sit lodged (combat/lodge.py), and the stage off the flight's hit: the
wound and its blood, the tree test, the height it may lodge at, the chips, the
item set into the trunk, and the fall it then skips.

is_strike_node picks out the stage's nodes, so the older counts over the whole
graph (blood and impact spawns, LastHitFrom writes, the chop's tree test) can
set them aside, as they do the chop's.
"""

import functools
import math

import unreal

from combat.axe import axe_lodge
from combat.game_state import DAMAGED_BY_PLAYER_VAR, LAST_DAMAGE_VAR
from combat.grip import _rotate_vector
from combat.hit_reaction import LAST_HIT_FROM_VAR
from combat.knife import knife_lodge
from combat.paths import (
    AXE_BP_PATH, ITEM_BP_PATH, KNIFE_BP_PATH, MATCHES_BP_PATH, STICK_BP_PATH,
    WOOD_BP_PATH,
)
from combat.throw_tuning import (
    LODGE_AXE_DEPTH_CM, LODGE_KNIFE_DEPTH_CM, LODGE_MAX_HEIGHT_CM, LODGE_POINT_VAR,
    LODGE_TURN_VAR, THROW_AXE_DAMAGE, THROW_DAMAGE_VAR, THROW_KNIFE_DAMAGE,
)
from combat.tuning import COMBAT, INTERACT_RADIUS
from combat.verify.common import BEL, PIN, by_pins, check, has_in_pin, num_pin, pin_value
from combat.verify.fixtures import _is_exec, wg
from combat.verify.throw import _item_cdo, _title, is_throw_trace
from combat.weapon_component.surface_impact import IMPACT_CLASS_VAR
from combat.weapon_component.throw_flight import THROWN_VAR
from combat.weapon_component.throw_strike import THROW_PAST_VAR
from combat.weapon_specs import _weapon_specs

# The player's middle over the ground (the capsule's half height), and how far
# from a trunk's bark it can stand: what the lodge's height is reached from.
REACH_FROM_CM = 90.0
REACH_OUT_CM = 60.0


def _feeders(node, pin):
    p = BEL.find_input_pin(node, pin)
    return [PIN.get_owning_node(q) for q in PIN.list_connected_pins(p)] if p else []


def _pure_feeds(node):
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


def _gates():
    """The Branches that ask the thrown item's ThrowDamage."""
    return [n for n in wg if _title(n) == "Branch"
            and any(_title(f) == f"Get {THROW_DAMAGE_VAR}"
                    for c in _feeders(n, "Condition") for f in _feeders(c, "A"))]


def _leaves(node):
    """Where the stage hands back to the flight: its way down to the ground,
    or the landing."""
    return ((has_in_pin(node, "TraceChannel") and is_throw_trace(node))
            or _title(node) == "Set Dropped")


@functools.lru_cache(maxsize=1)
def _stage():
    """(the stage's exec nodes, {the title of each of the flight's nodes they
    hand back to: the stage's nodes that run it})."""
    ran, exits, todo = {}, {}, list(_gates())
    while todo:
        n = todo.pop()
        if n.get_path_name() in ran:
            continue
        ran[n.get_path_name()] = n
        for p in BEL.list_output_pins(n):
            if not _is_exec(p):
                continue
            for q in PIN.list_connected_pins(p):
                nxt = PIN.get_owning_node(q)
                if _leaves(nxt):
                    exits.setdefault(_title(nxt), []).append(n)
                else:
                    todo.append(nxt)
    return list(ran.values()), exits


@functools.lru_cache(maxsize=1)
def _strike_names():
    ran, _exits = _stage()
    names = {n.get_path_name() for n in ran}
    for n in ran:
        names |= {f.get_path_name() for f in _pure_feeds(n)}
    return frozenset(names)


def is_strike_node(node):
    """Is this node part of the thrown blade's stage (its exec nodes, or a
    pure node feeding one)? The flight's own hit and item are not."""
    return (node.get_path_name() in _strike_names()
            and not has_in_pin(node, "Hit") and _title(node) != f"Get {THROWN_VAR}")


def _floor():
    """The flight's nodes the stage hands the falling item to."""
    _ran, exits = _stage()
    return [PIN.get_owning_node(q) for k, v in exits.items() if k != "Set Dropped"
            for n in v for p in BEL.list_output_pins(n) if _is_exec(p)
            for q in PIN.list_connected_pins(p) if _title(PIN.get_owning_node(q)) == k]


def _mine(nodes):
    return [n for n in nodes if is_strike_node(n)]


def _spawns(var):
    return [n for n in by_pins(wg, "Class", "SpawnTransform")
            if any(_title(f) == f"Get {var}" for f in _feeders(n, "Class"))]


def _of_thrown(node):
    return [_title(f) for f in _feeders(node, "self")] == [f"Get {THROWN_VAR}"]


def check_blades():
    base = _item_cdo(ITEM_BP_PATH)
    got = base.get_editor_property(THROW_DAMAGE_VAR)
    check("a thrown item does no damage unless it says otherwise",
          isinstance(got, float) and got == 0.0, str(got))
    others = ([(sp["display"], sp["path"]) for sp in _weapon_specs()]
              + [("wood", WOOD_BP_PATH), ("matches", MATCHES_BP_PATH),
                 ("stick", STICK_BP_PATH)])
    bad = [f"{name}={v}" for name, path in others
           for v in [_item_cdo(path).get_editor_property(THROW_DAMAGE_VAR)] if v != 0.0]
    check("...which no gun does, nor the wood, the matches or the stick",
          not bad, "; ".join(bad))
    for name, path, damage, lodge, depth in (
            ("knife", KNIFE_BP_PATH, THROW_KNIFE_DAMAGE, knife_lodge, LODGE_KNIFE_DEPTH_CM),
            ("axe", AXE_BP_PATH, THROW_AXE_DAMAGE, axe_lodge, LODGE_AXE_DEPTH_CM)):
        cdo = _item_cdo(path)
        got = cdo.get_editor_property(THROW_DAMAGE_VAR)
        check(f"a thrown {name} takes {damage:g} HP: more than a slash, since "
              "the throw costs the weapon, and less than a wanderer's all",
              got == damage and COMBAT.knife_damage < damage < 100.0, str(got))
        turn, point = cdo.get_editor_property(LODGE_TURN_VAR), \
            cdo.get_editor_property(LODGE_POINT_VAR)
        want_turn, want_point = lodge()
        check(f"...and lodges as its model says: {LODGE_TURN_VAR} and "
              f"{LODGE_POINT_VAR} are the builder's",
              abs(turn.pitch - want_turn.pitch) < 1e-3 and abs(turn.yaw) < 1e-3
              and abs(turn.roll) < 1e-3 and (point - want_point).length() < 1e-3,
              f"{turn} {point}")
        # Turned, the point of the item on the bark is `depth` behind what
        # leads into the wood, straight along +X: the way the item then flies.
        on_bark = _rotate_vector(turn, point)
        check(f"...{depth:g} cm into the wood, what leads within 30 cm of the "
              "hand's grip and ahead of it",
              0.0 < on_bark.x < 30.0 and 0.0 < depth < 10.0,
              f"the bark {on_bark.x:.1f} cm ahead of the grip, {on_bark.z:.1f} up")
    far = math.hypot(LODGE_MAX_HEIGHT_CM - REACH_FROM_CM, REACH_OUT_CM)
    check(f"a blade lodges no higher than {LODGE_MAX_HEIGHT_CM:g} cm over the "
          "tree's foot: within the pick-up's reach of a player stood at the trunk",
          far < INTERACT_RADIUS and LODGE_MAX_HEIGHT_CM >= 180.0,
          f"{far:.0f} cm from the player's middle, reach {INTERACT_RADIUS:g}")


def check_strike_gate():
    gates = _gates()
    check(f"the flight asks {THROW_DAMAGE_VAR} once: is what struck a blade",
          len(gates) == 1, str(len(gates)))
    if len(gates) != 1:
        return False
    reads = [f for c in _feeders(gates[0], "Condition") for f in _feeders(c, "A")]
    check("...of the item in the air, against zero",
          len(reads) == 1 and _of_thrown(reads[0])
          and all(pin_value(c, "B") in ("", "0", "0.0", "0.000000")
                  for c in _feeders(gates[0], "Condition")),
          str([pin_value(c, "B") for c in _feeders(gates[0], "Condition")]))
    clears = _feeders(gates[0], "execute")
    before = [b for c in clears for b in _feeders(c, "execute")]
    check("...on the frame the flight's segment hits something, before the "
          f"item is set down, {THROW_PAST_VAR} emptied first",
          len(clears) == 1 and has_in_pin(clears[0], "TargetArray")
          and not has_in_pin(clears[0], "NewItem")
          and [_title(f) for f in _feeders(clears[0], "TargetArray")]
          == [f"Get {THROW_PAST_VAR}"]
          and len(before) == 1 and _title(before[0]) == "Branch"
          and any(is_throw_trace(t) for t in _feeders(before[0], "Condition")),
          str([_title(b) for b in clears + before]))
    return True


def check_wound():
    writes = _mine([n for n in wg if _title(n) == "Set Health"])
    check("a blade that strikes a body takes its health once",
          len(writes) == 1, str(len(writes)))
    if len(writes) != 1:
        return
    fed = {_title(n) for n in _pure_feeds(writes[0])}
    check(f"...by the thrown item's {THROW_DAMAGE_VAR}, clamped at zero",
          {f"Get {THROW_DAMAGE_VAR}", "Get Health"} <= fed
          and any("Clamp" in t for t in fed), str(sorted(fed)))
    cast = _feeders(writes[0], "execute")
    check("...behind the health cast of the actor the flight struck",
          len(cast) == 1 and "HealthComponent" in _title(cast[0]).replace(" ", ""),
          str([_title(c) for c in cast]))
    stamps = {v: _mine([n for n in wg if _title(n) == f"Set {v}"])
              for v in (LAST_DAMAGE_VAR, DAMAGED_BY_PLAYER_VAR, LAST_HIT_FROM_VAR)}
    check("...stamped as a pellet's hit is: the health bar, the kill's credit "
          "(and the wendigo's rage), the flinch's direction",
          all(len(s) == 1 for s in stamps.values())
          and all(pin_value(s, DAMAGED_BY_PLAYER_VAR) == "true"
                  for s in stamps[DAMAGED_BY_PLAYER_VAR]),
          str({k: len(v) for k, v in stamps.items()}))
    blood = _mine(_spawns("BloodClass"))
    check("...and it bleeds: one blood spawn, after the wound",
          len(blood) == 1 and len(stamps[LAST_HIT_FROM_VAR]) == 1
          and _feeders(blood[0], "execute") == stamps[LAST_HIT_FROM_VAR],
          str(len(blood)))
    adds = [n for n in by_pins(wg, "TargetArray", "NewItem")
            if [_title(f) for f in _feeders(n, "TargetArray")] == [f"Get {THROW_PAST_VAR}"]]
    floors = [n for n in by_pins(wg, "Start", "End", "TraceChannel", "ActorsToIgnore")
              if [_title(f) for f in _feeders(n, "ActorsToIgnore")]
              == [f"Get {THROW_PAST_VAR}"]]
    check(f"...and its fall passes the body by: the struck actor goes into "
          f"{THROW_PAST_VAR} once, after the blood, and only the flight's trace "
          "down to the ground ignores it",
          len(adds) == 1 and _feeders(adds[0], "execute") == blood
          and any(has_in_pin(f, "Hit") for f in _feeders(adds[0], "NewItem"))
          and len(floors) == 1 and is_throw_trace(floors[0])
          and floors[0].get_path_name() in {n.get_path_name() for n in _floor()},
          f"{len(adds)} add(s), {len(floors)} trace(s)")


def check_lodge():
    _ran, exits = _stage()
    casts = _mine([n for n in wg if "instancedstaticmesh" in
                   _title(n).replace(" ", "").lower() and has_in_pin(n, "Object")])
    check("a blade that strikes no body asks whether it struck a tree: one "
          "cast to InstancedStaticMeshComponent, off the health cast's failed arm",
          len(casts) == 1 and any("HealthComponent" in _title(f).replace(" ", "")
                                  for c in casts for f in _feeders(c, "execute")),
          str(len(casts)))
    highs = _mine([n for n in wg if _title(n) == "Branch"
                   and any(num_pin(c, "B") == LODGE_MAX_HEIGHT_CM
                           for c in _feeders(n, "Condition"))])
    check(f"...and how high: within {LODGE_MAX_HEIGHT_CM:g} cm of the tree "
          "instance's own origin, in world space",
          len(highs) == 1
          and any(has_in_pin(f, "InstanceIndex") and pin_value(f, "bWorldSpace") == "true"
                  for f in _pure_feeds(highs[0])),
          str(len(highs)))
    chips = _mine(_spawns(IMPACT_CLASS_VAR))
    check("it chips the bark once, on the reachable arm",
          len(chips) == 1 and _feeders(chips[0], "execute") == highs, str(len(chips)))
    puts = _mine(by_pins(wg, "NewLocation", "NewRotation"))
    check("...and is set into the trunk once: the item in the air, placed and "
          "turned in one move", len(puts) == 1 and _of_thrown(puts[0]), str(len(puts)))
    if len(puts) != 1:
        return
    turn = {_title(n) for f in _feeders(puts[0], "NewRotation")
            for n in [f] + _pure_feeds(f)}
    at = {_title(n) for f in _feeders(puts[0], "NewLocation")
          for n in [f] + _pure_feeds(f)}
    check(f"...its own {LODGE_TURN_VAR}, then its X along the segment it flew",
          f"Get {LODGE_TURN_VAR}" in turn
          and any("CombineRotators" in t.replace(" ", "") for t in turn)
          and any("MakeRotFromX" in t.replace(" ", "") for t in turn),
          str(sorted(turn)))
    check(f"...its {LODGE_POINT_VAR}, turned the same way, on the hit",
          {f"Get {LODGE_POINT_VAR}", f"Get {LODGE_TURN_VAR}"} <= at, str(sorted(at)))
    check("lodged, it skips the fall: straight on to the landing's Dropped, "
          "so it hangs in the tree as a pick-up",
          exits.get("Set Dropped") == puts and len(exits) == 2, str(sorted(exits)))
    falls = [v for k, v in exits.items() if k != "Set Dropped"]
    check("everything else still comes down to the ground: an item that is no "
          "blade, one that wounded a body, one that struck no tree, one too high",
          len(falls) == 1 and len(falls[0]) == 4, str([len(v) for v in falls]))


def run():
    check_blades()
    if check_strike_gate():
        check_wound()
        check_lodge()
