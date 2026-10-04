"""verify.throw_strike -- what a thrown blade does to what it strikes
(weapon_component/throw_strike.py): who has a ThrowDamage, how the knife and
the axe sit lodged (combat/lodge.py), and the stage off the flight's hit: where
on the body it went in, the wound (the head's worth more) and its blood, the
item set into the body and attached to the bone it struck, the tree test, the
height it may lodge at, the chips, the item set into the trunk, and the fall
both then skip.

is_strike_node picks out the stage's nodes, so the older counts over the whole
graph (blood and impact spawns, LastHitFrom writes, the chop's tree test, the
pellet's body trace) can set them aside, as they do the chop's.
"""

import functools
import math

import unreal

from combat.axe import AXE_DISPLAY, axe_lodge
from combat.game_state import DAMAGED_BY_PLAYER_VAR, LAST_DAMAGE_VAR
from combat.grip import _rotate_vector
from combat.hit_reaction import LAST_HIT_FROM_VAR
from combat.hit_zones import HEAD_BONES_VAR, HEAD_MULT_VAR
from combat.knife import KNIFE_DISPLAY, knife_lodge
from combat.melee_tuning import throw_damage
from combat.paths import (
    AXE_BP_PATH, ITEM_BP_PATH, KNIFE_BP_PATH, MATCHES_BP_PATH, STICK_BP_PATH,
    WOOD_BP_PATH,
)
from combat.throw_tuning import (
    LODGE_AXE_DEPTH_CM, LODGE_KNIFE_DEPTH_CM, LODGE_MAX_HEIGHT_CM, LODGE_POINT_VAR,
    LODGE_TURN_VAR, STICK_LINE_REACH_CM, STICK_TRACE_PAST, THROW_DAMAGE_VAR,
)
from combat.tuning import COMBAT, INTERACT_RADIUS
from combat.verify.common import (
    BEL, PIN, by_pins, check, has_in_pin, in_pins, num_pin, pin_value,
)
from combat.verify.fixtures import _is_exec, wg
from combat.verify.throw import _item_cdo, _title, is_throw_trace
from combat.headshot_tuning import HEADSHOT_TIME_VAR
from combat.weapon_component.surface_impact import IMPACT_CLASS_VAR
from combat.weapon_component.throw_flight import THROWN_VAR
from combat.weapon_component.throw_strike import (
    THROW_BONE_VAR, THROW_PAST_VAR, THROW_SKIN_VAR,
)
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


def _past_sound(nodes):
    """Exec feeders, looked back past one played sound. A sound is three
    nodes (weapon_component/sounds.py): a Branch on "are there takes", the
    play, and a Branch both of those run into. Where ``nodes`` is that last
    Branch, what feeds the first one is what the sound came after."""
    if len(nodes) == 1 and _title(nodes[0]) == "Branch":
        back = _feeders(nodes[0], "execute")
        plays = [n for n in back if has_in_pin(n, "Sound")]
        gates = [n for n in back if n not in plays]
        if len(plays) == 1 and len(gates) == 1 and _feeders(plays[0], "execute") == gates:
            return _feeders(gates[0], "execute")
    return nodes


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
            ("knife", KNIFE_BP_PATH, throw_damage(KNIFE_DISPLAY), knife_lodge,
             LODGE_KNIFE_DEPTH_CM),
            ("axe", AXE_BP_PATH, throw_damage(AXE_DISPLAY), axe_lodge,
             LODGE_AXE_DEPTH_CM)):
        cdo = _item_cdo(path)
        got = cdo.get_editor_property(THROW_DAMAGE_VAR)
        check(f"a thrown {name} takes {damage:g} HP (its gun_tuning.csv row's, "
              "the GUN SETTINGS tab's `throw_damage`): more than a slash, since "
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
    picks = [n for n in _pure_feeds(writes[0]) if {"A", "B", "bPickA"} <= in_pins(n)]
    tests = [f for n in picks for f in _feeders(n, "bPickA")]
    check(f"...times the struck body's own {HEAD_MULT_VAR} where the bone the "
          f"blade went in at ({THROW_BONE_VAR}) is one of its {HEAD_BONES_VAR}, "
          "and whole anywhere else",
          len(picks) == 1 and num_pin(picks[0], "B") == 1.0
          and [_title(f) for f in _feeders(picks[0], "A")] == [f"Get {HEAD_MULT_VAR}"]
          and len(tests) == 1
          and [_title(f) for f in _feeders(tests[0], "TargetArray")]
          == [f"Get {HEAD_BONES_VAR}"]
          and [_title(f) for f in _feeders(tests[0], "ItemToFind")]
          == [f"Get {THROW_BONE_VAR}"],
          f"{len(picks)} Select(s), {len(tests)} test(s)")
    marks = _mine([n for n in wg if _title(n) == f"Set {THROW_BONE_VAR}"])
    none = [n for n in marks if not _feeders(n, THROW_BONE_VAR)]
    cast = [c for n in none for c in _feeders(n, "execute")]
    check(f"the stage is behind the health cast of the actor the flight struck: "
          f"it empties {THROW_BONE_VAR} first",
          len(marks) == 3 and len(none) == 1
          and pin_value(none[0], THROW_BONE_VAR) in ("", "None")
          and len(cast) == 1 and "HealthComponent" in _title(cast[0]).replace(" ", ""),
          f"{len(marks)} write(s), behind {[_title(c) for c in cast]}")
    line, nearest = _skins()
    told = [n for n in marks if _feeders(n, THROW_BONE_VAR)]
    spots = _mine([n for n in wg if _title(n) == f"Set {THROW_SKIN_VAR}"])
    check(f"each of the two body traces that strikes notes its bone and its "
          f"point: {THROW_BONE_VAR}, then {THROW_SKIN_VAR}, off its own hit",
          len(line) == 1 and len(nearest) == 1 and len(told) == 2 and len(spots) == 2
          and sorted(t.get_path_name() for sp in spots for t in _feeders(sp, "execute"))
          == sorted(t.get_path_name() for t in told)
          and all(_feeders(sp, THROW_SKIN_VAR) == _feeders(t, THROW_BONE_VAR)
                  and _feeders(t, THROW_BONE_VAR)[0] in line + nearest
                  for sp in spots for t in _feeders(sp, "execute"))
          and {f.get_path_name() for t in told for f in _feeders(t, THROW_BONE_VAR)}
          == {n.get_path_name() for n in line + nearest},
          f"{len(told)} bone(s), {len(spots)} point(s)")
    ways = _feeders(writes[0], "execute")
    before = sorted(_title(f).replace(" ", "") for f in ways)
    check("...and the wound comes after the body's skin is looked for, on all "
          "four of its ways out: struck on the blade's line, struck towards "
          "the nearest bone, both missed, and a body that is no Character",
          before == sorted([f"Set{THROW_SKIN_VAR}"] * 2 + ["CastToCharacter", "Branch"])
          and all(sp in ways for sp in spots)
          and any(_feeders(f, "Condition") == nearest for f in ways
                  if _title(f) == "Branch"),
          str(before))
    stamps = {v: _mine([n for n in wg if _title(n) == f"Set {v}"])
              for v in (LAST_DAMAGE_VAR, DAMAGED_BY_PLAYER_VAR, LAST_HIT_FROM_VAR)}
    check("...stamped as a pellet's hit is: the health bar, the kill's credit "
          "(and the wendigo's rage), the flinch's direction",
          all(len(s) == 1 for s in stamps.values())
          and all(pin_value(s, DAMAGED_BY_PLAYER_VAR) == "true"
                  for s in stamps[DAMAGED_BY_PLAYER_VAR]),
          str({k: len(v) for k, v in stamps.items()}))
    blood = _mine(_spawns("BloodClass"))
    # Between the two, the headshot stamp (verify/headshot.py).
    told = _feeders(blood[0], "execute") if len(blood) == 1 else []
    check("...and it bleeds: one blood spawn, after the wound and its "
          f"{HEADSHOT_TIME_VAR} stamp",
          len(blood) == 1 and len(stamps[LAST_HIT_FROM_VAR]) == 1
          and [_title(n) for n in told] == [f"Set {HEADSHOT_TIME_VAR}"]
          and _feeders(told[0], "execute") == stamps[LAST_HIT_FROM_VAR],
          f"{len(blood)} spawns, after {[_title(n) for n in told]}")
    adds = [n for n in by_pins(wg, "TargetArray", "NewItem")
            if [_title(f) for f in _feeders(n, "TargetArray")] == [f"Get {THROW_PAST_VAR}"]]
    floors = [n for n in by_pins(wg, "Start", "End", "TraceChannel", "ActorsToIgnore")
              if [_title(f) for f in _feeders(n, "ActorsToIgnore")]
              == [f"Get {THROW_PAST_VAR}"]]
    check_stick(blood)
    drops = [f for a in adds for f in _feeders(a, "execute")]
    check(f"a body it cannot be set into drops it, and that fall passes the "
          f"body by: the struck actor goes into {THROW_PAST_VAR} once, off the "
          f"arm on which {THROW_BONE_VAR} is no bone (the Character cast "
          "failed, or the body trace missed), and only the "
          "flight's trace down to the ground ignores it",
          len(adds) == 1 and drops == _stuck_gates()
          and any(has_in_pin(f, "Hit") for f in _feeders(adds[0], "NewItem"))
          and len(floors) == 1 and is_throw_trace(floors[0])
          and floors[0].get_path_name() in {n.get_path_name() for n in _floor()},
          f"{len(adds)} add(s), {len(floors)} trace(s)")


def _body_traces():
    return [n for n in wg if {"TraceStart", "TraceEnd", "bTraceComplex"} <= in_pins(n)]


def _skins():
    """(the body trace on along the blade's own line, the one towards the
    nearest bone): told apart by the nearest-bone node feeding the second."""
    traces = _mine(_body_traces())
    nearest = [n for n in traces
               if any(has_in_pin(f, "TestLocation") for f in _pure_feeds(n))]
    return [n for n in traces if n not in nearest], nearest


def _puts():
    """(the move that sets the item into a body, the one into a tree): told
    apart by what the item's point is set on, the body's skin or the flight's
    own hit."""
    puts = _mine(by_pins(wg, "NewLocation", "NewRotation"))
    in_body = [n for n in puts
               if any(_title(n2) == f"Get {THROW_SKIN_VAR}"
                      for f in _feeders(n, "NewLocation") for n2 in _pure_feeds(f))]
    return in_body, [n for n in puts if n not in in_body]


def _stuck_gates():
    """The Branches that ask whether ThrowBone is a bone: is the blade to be
    left in the body."""
    return _mine([n for n in wg if _title(n) == "Branch"
                  and any(_title(f) == f"Get {THROW_BONE_VAR}"
                          and pin_value(c, "B") in ("", "None")
                          for c in _feeders(n, "Condition") for f in _feeders(c, "A"))])


def _from_hit(node, pin):
    return any(has_in_pin(f, "Hit") for f in _feeders(node, pin))


def check_stick(blood):
    casts = _mine([n for n in wg if _title(n).replace(" ", "") == "CastToCharacter"])
    check("where the blade went into the body: one cast of the struck actor "
          "to Character, for its mesh",
          len(casts) == 1
          and [_title(f) for f in _feeders(casts[0], "execute")] == [f"Set {THROW_BONE_VAR}"]
          and _from_hit(casts[0], "Object"), str(len(casts)))
    line, nearest = _skins()
    check("...two traces of that mesh's physics bodies alone",
          len(line) == 1 and len(nearest) == 1
          and all(pin_value(n, "bTraceComplex").lower() == "false"
                  and [_title(f) for f in _feeders(n, "self")] == ["Get Mesh"]
                  for n in line + nearest), f"{len(line)} + {len(nearest)}")
    if len(line) != 1 or len(nearest) != 1:
        return
    way = _pure_feeds(line[0])
    check("...the first on along the blade's own line: from the flight's hit "
          f"the way its segment flew, {STICK_LINE_REACH_CM:g} cm far",
          _feeders(line[0], "execute") == casts and _from_hit(line[0], "TraceStart")
          and not _from_hit(line[0], "TraceEnd")
          and any("Normal" in _title(n) for n in way)
          and any(num_pin(n, "X") == num_pin(n, "Y") == num_pin(n, "Z")
                  == STICK_LINE_REACH_CM for n in way if {"X", "Y", "Z"} <= in_pins(n)),
          str(sorted(_title(n) for n in way)))
    missed = [n for n in wg if _title(n) == "Branch" and _feeders(n, "Condition") == line]
    way = _pure_feeds(nearest[0])
    bones = [n for n in way if has_in_pin(n, "TestLocation")]
    check("...the second only where that struck nothing: from the flight's hit "
          f"towards the bone nearest it that has a body, {STICK_TRACE_PAST:g} "
          "times as far",
          len(missed) == 1 and _feeders(nearest[0], "execute") == missed
          and _from_hit(nearest[0], "TraceStart") and len(bones) == 1
          and pin_value(bones[0], "bRequirePhysicsAsset") == "true"
          and [_title(f) for f in _feeders(bones[0], "self")] == ["Get Mesh"]
          and _from_hit(bones[0], "TestLocation")
          and any(num_pin(n, "X") == num_pin(n, "Y") == num_pin(n, "Z") == STICK_TRACE_PAST
                  for n in way if {"X", "Y", "Z"} <= in_pins(n)),
          f"{len(bones)} nearest-bone node(s)")
    in_body, _in_tree = _puts()
    found = _stuck_gates()
    check("a blade that wounded a body stays in it: after the blood and the "
          "sound of it going in, where "
          f"{THROW_BONE_VAR} is a bone, the item in the air is set on the skin "
          f"({THROW_SKIN_VAR}) once, as it is into a trunk",
          len(in_body) == 1 and len(found) == 1 and _of_thrown(in_body[0])
          and _feeders(in_body[0], "execute") == found
          and _past_sound(_feeders(found[0], "execute")) == blood
          and _feeders(in_body[0], "NewLocation") != _feeders(in_body[0], "NewRotation"),
          f"{len(in_body)} move(s), {len(found)} Branch(es)")
    holds = _mine(by_pins(wg, "Parent", "SocketName", "LocationRule"))
    check("...and attached to the mesh at the bone it struck, keeping "
          "where it was set and its own size",
          len(holds) == 1 and _of_thrown(holds[0])
          and _feeders(holds[0], "execute") == in_body
          and [_title(f) for f in _feeders(holds[0], "Parent")] == ["Get Mesh"]
          and [_title(f) for f in _feeders(holds[0], "SocketName")]
          == [f"Get {THROW_BONE_VAR}"]
          and all(pin_value(holds[0], r) == "KeepWorld"
                  for r in ("LocationRule", "RotationRule", "ScaleRule")),
          str(len(holds)))


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
    in_body, puts = _puts()
    check("...and, after the chop's sound, is set into the trunk once: the item "
          "in the air, placed and turned in one move",
          len(puts) == 1 and _of_thrown(puts[0])
          and _past_sound(_feeders(puts[0], "execute")) == chips
          and any(has_in_pin(f, "Hit") for f in _feeders(puts[0], "NewLocation")
                  for f in [f] + _feeders(f, "A")),
          str(len(puts)))
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
    held = [n for n in _mine(by_pins(wg, "Parent", "SocketName", "LocationRule"))]
    landed = exits.get("Set Dropped", [])
    marks = [f for n in landed for f in _feeders(n, "execute")]
    check("lodged, in a tree or in a body, it is flagged Lodged (the pick-up "
          "puts such a blade back in empty hands) and skips the fall: straight "
          "on to the landing's Dropped, so it stays there as a pick-up",
          len(landed) == 1 and _title(landed[0]) == "Set Lodged"
          and pin_value(landed[0], "Lodged") == "true" and _of_thrown(landed[0])
          and len(marks) == 2 and all(n in marks for n in puts + held)
          and len(exits) == 2, f"{sorted(exits)}, {[_title(n) for n in landed]}")
    falls = [v for k, v in exits.items() if k != "Set Dropped"]
    check("everything else still comes down to the ground: an item that is no "
          "blade, one a body dropped, one that struck no tree, one too high",
          len(falls) == 1 and len(falls[0]) == 4, str([len(v) for v in falls]))


def run():
    check_blades()
    if check_strike_gate():
        check_wound()
        check_lodge()
