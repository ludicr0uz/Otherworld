"""verify.throw_strike -- what a thrown blade does to what it strikes
(weapon_component/throw_strike.py): who has a ThrowDamage, how the knife and
the axe sit lodged (combat/lodge.py), and the stage off the flight's hit: where
on the body it went in, the wound (the head's worth more) and its blood, the
item set into the body and attached to the bone it struck, the tree test, the
height it may lodge at, the chips, the item set into the trunk, and the fall
both then skip.

The checks walk the stage from its gate (_walk: each node is the one the step
before it runs) and say what each must be; none counts a kind of node over the
graph (verify/anchor.py).

is_strike_node picks out the stage's nodes, so the older counts over the whole
graph (blood and impact spawns, LastHitFrom writes, the chop's tree test, the
pellet's body trace) can set them aside, as they do the chop's.
"""

import functools
import math
import types

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
from combat.verify import fx as fxv
from combat import fx_vars as FX
from combat.verify.anchor import feeders as _feeders, pure_feeds as _pure_feeds, runs, the
from combat.verify.common import (
    take_hits,
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
# Anywhere but the head, a wound is the item's whole ThrowDamage.
WHOLE = 1.0


def _entries():
    """Where the flight enters the stage: it empties ThrowPast."""
    return [n for n in wg if _title(n) == "Clear"
            and [_title(f) for f in _feeders(n, "TargetArray")] == [f"Get {THROW_PAST_VAR}"]]


def _gates():
    """The Branches the entry runs, which ask the thrown item's ThrowDamage."""
    return [n for e in _entries() for n in runs(e, "then") if _title(n) == "Branch"
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
    # The blood and the sounds into a body, the chips and the sound into a
    # trunk, are Fx_Stab's and Fx_Lodge's, told by their Multicasts (verify/fx.py).
    ran = list(ran) + list(fxv.nodes_of(FX.STAB)) + list(fxv.nodes_of(FX.LODGE))
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


def _t(node):
    return _title(node) if node is not None else "nothing"


def _step(node, pin):
    """The one node this exec output runs; a walk that lost its way stays lost."""
    return the(runs(node, pin)) if node is not None else None


@functools.lru_cache(maxsize=1)
def _walk():
    """The stage, node by node from its gate (weapon_component/throw_strike.py):
    each name is the one node the step before it runs, or None. The checks
    say what each must be; nothing here is found by counting the graph."""
    w = types.SimpleNamespace()
    w.gate = the(_gates())
    w.health = _step(w.gate, "then")              # the struck actor's health cast
    w.emptied = _step(w.health, "then")           # ThrowBone set to no bone
    w.character = _step(w.emptied, "then")        # the cast for its mesh
    w.line = _step(w.character, "then")           # the body trace along the blade
    w.line_hit = _step(w.line, "then")
    w.nearest = _step(w.line_hit, "else")         # the one towards the nearest bone
    w.nearest_hit = _step(w.nearest, "then")
    w.wound = _step(w.character, "CastFailed")    # the TakeHit all four ways reach
    w.stamp = _step(w.wound, "then")
    w.stab = _step(w.stamp, "then")               # Multicast_Stab
    w.stuck = _step(w.stab, "then")               # is ThrowBone a bone
    w.in_body = _step(w.stuck, "then")
    w.hold = _step(w.in_body, "then")
    w.past = _step(w.stuck, "else")               # the body goes into ThrowPast
    w.floor = _step(w.past, "then")
    w.tree = _step(w.health, "CastFailed")        # the tree's cast
    w.high = _step(w.tree, "then")
    w.lodge = _step(w.high, "then")               # Multicast_Lodge
    w.in_tree = _step(w.lodge, "then")
    w.lodged = _step(w.in_tree, "then")
    return w


def _noted(trace, struck):
    """(the ThrowBone write, the ThrowSkin write) a body trace's Branch runs
    where it struck."""
    bone = _step(struck, "then")
    return trace, bone, _step(bone, "then")


def check_strike_gate():
    w = _walk()
    check(f"the flight asks {THROW_DAMAGE_VAR} once: is what struck a blade",
          w.gate is not None,
          f"{len(_entries())} emptying of {THROW_PAST_VAR}, {len(_gates())} gate(s) behind")
    if w.gate is None:
        return False
    conds = _feeders(w.gate, "Condition")
    read = the([f for c in conds for f in _feeders(c, "A")])
    check("...of the item in the air, against zero",
          read is not None and _of_thrown(read)
          and all(pin_value(c, "B") in ("", "0", "0.0", "0.000000") for c in conds),
          str([pin_value(c, "B") for c in conds]))
    entry = the(_feeders(w.gate, "execute"))
    before = the(_feeders(entry, "execute")) if entry is not None else None
    check("...on the frame the flight's segment hits something, before the "
          f"item is set down, {THROW_PAST_VAR} emptied first",
          entry is not None and entry in _entries()
          and before is not None and _title(before) == "Branch"
          and any(is_throw_trace(t) for t in _feeders(before, "Condition")),
          str([_t(entry), _t(before)]))
    return True


def check_wound():
    w = _walk()
    wound = w.wound
    check("a blade that strikes a body takes its health once (the body's TakeHit: "
          "combat/damage.py)",
          wound is not None and wound in take_hits(wg), _t(wound))
    if wound is None:
        return
    fed = {_title(n) for n in _pure_feeds(wound)}
    check(f"...by the thrown item's {THROW_DAMAGE_VAR} (the body floors it at zero)",
          f"Get {THROW_DAMAGE_VAR}" in fed, str(sorted(fed)))
    pick = the([n for n in _pure_feeds(wound) if {"A", "B", "bPickA"} <= in_pins(n)])
    test = the(_feeders(pick, "bPickA")) if pick is not None else None
    check(f"...times the struck body's own {HEAD_MULT_VAR} where the bone the "
          f"blade went in at ({THROW_BONE_VAR}) is one of its {HEAD_BONES_VAR}, "
          "and whole anywhere else",
          pick is not None and num_pin(pick, "B") == WHOLE
          and [_title(f) for f in _feeders(pick, "A")] == [f"Get {HEAD_MULT_VAR}"]
          and test is not None
          and [_title(f) for f in _feeders(test, "TargetArray")]
          == [f"Get {HEAD_BONES_VAR}"]
          and [_title(f) for f in _feeders(test, "ItemToFind")]
          == [f"Get {THROW_BONE_VAR}"],
          f"picked by {_t(pick)}, tested by {_t(test)}")
    check(f"the stage is behind the health cast of the actor the flight struck: "
          f"it empties {THROW_BONE_VAR} first",
          w.emptied is not None and _title(w.emptied) == f"Set {THROW_BONE_VAR}"
          and not _feeders(w.emptied, THROW_BONE_VAR)
          and pin_value(w.emptied, THROW_BONE_VAR) in ("", "None")
          and "HealthComponent" in _title(w.health).replace(" ", ""),
          f"{_t(w.emptied)}, behind {_t(w.health)}")
    noted = [_noted(w.line, w.line_hit), _noted(w.nearest, w.nearest_hit)]
    check(f"each of the two body traces that strikes notes its bone and its "
          f"point: {THROW_BONE_VAR}, then {THROW_SKIN_VAR}, off its own hit",
          all(t is not None and bone is not None and skin is not None
              and _title(bone) == f"Set {THROW_BONE_VAR}"
              and _title(skin) == f"Set {THROW_SKIN_VAR}"
              and _feeders(bone, THROW_BONE_VAR) == [t]
              and _feeders(skin, THROW_SKIN_VAR) == [t]
              for t, bone, skin in noted),
          str([(_t(t), _t(bone), _t(skin)) for t, bone, skin in noted]))
    ways = _feeders(wound, "execute")
    before = sorted(_title(f).replace(" ", "") for f in ways)
    check("...and the wound comes after the body's skin is looked for, on all "
          "four of its ways out: struck on the blade's line, struck towards "
          "the nearest bone, both missed, and a body that is no Character",
          before == sorted([f"Set{THROW_SKIN_VAR}"] * 2 + ["CastToCharacter", "Branch"])
          and all(skin in ways for _trace, _bone, skin in noted)
          and w.nearest_hit in ways and w.character in ways,
          str(before))
    told = {pin: [_title(f).replace(" ", "") for f in _feeders(wound, pin)]
            for pin in ("InstigatedBy", "Cause")}
    normal = [str(PIN.get_pin_name(q)).replace(" ", "") for q in
              PIN.list_connected_pins(BEL.find_input_pin(wound, "From"))]
    check("...stamped as a pellet's hit is: who struck it (the thrower's controller: "
          "the kill's credit, and the wendigo's rage), which way it came (the flinch) "
          "and with what (the thrown item)",
          told["InstigatedBy"] == ["GetInstigatorController"] and normal == ["ImpactNormal"]
          and told["Cause"] == [f"Get{THROWN_VAR}"]
          and not [n for v in (LAST_DAMAGE_VAR, DAMAGED_BY_PLAYER_VAR, LAST_HIT_FROM_VAR)
                   for n in wg if _title(n) == f"Set {v}"],
          f"{told}, From off {normal}")
    # Between the two, the headshot stamp (verify/headshot.py); the blood is
    # Fx_Stab's, told after it.
    blood = fxv.in_fx(FX.STAB, _spawns("BloodClass"))
    check("...and it bleeds: one blood spawn (Fx_Stab), told after the wound and its "
          f"{HEADSHOT_TIME_VAR} stamp",
          bool(blood) and w.stab is not None and w.stab in fxv.calls(FX.STAB)
          and _title(w.stamp).startswith("Set")
          and _title(w.stamp).endswith(f" {HEADSHOT_TIME_VAR}"),
          f"{len(blood)} spawn(s) under Fx_Stab, {_t(w.stamp)} then {_t(w.stab)}")
    check_stick()
    ignoring = [n for n in by_pins(wg, "Start", "End", "TraceChannel", "ActorsToIgnore")
                if [_title(f) for f in _feeders(n, "ActorsToIgnore")]
                == [f"Get {THROW_PAST_VAR}"]]
    check(f"a body it cannot be set into drops it, and that fall passes the "
          f"body by: the struck actor goes into {THROW_PAST_VAR} once, off the "
          f"arm on which {THROW_BONE_VAR} is no bone (the Character cast "
          "failed, or the body trace missed), and only the "
          "flight's trace down to the ground ignores it",
          w.past is not None and has_in_pin(w.past, "NewItem")
          and [_title(f) for f in _feeders(w.past, "TargetArray")]
          == [f"Get {THROW_PAST_VAR}"]
          and any(has_in_pin(f, "Hit") for f in _feeders(w.past, "NewItem"))
          and _asks_bone(w.stuck)
          and w.floor is not None and is_throw_trace(w.floor) and w.floor in ignoring
          and all(n in _floor() for n in ignoring),
          f"{_t(w.past)} then {_t(w.floor)}; {len(ignoring)} trace(s) ignore "
          f"{THROW_PAST_VAR}")


def _body_traces():
    return [n for n in wg if {"TraceStart", "TraceEnd", "bTraceComplex"} <= in_pins(n)]


def _asks_bone(node):
    """Is this the Branch that asks whether ThrowBone is a bone."""
    return (node is not None and _title(node) == "Branch"
            and any(_title(f) == f"Get {THROW_BONE_VAR}"
                    and pin_value(c, "B") in ("", "None")
                    for c in _feeders(node, "Condition") for f in _feeders(c, "A")))


def _is_put(node):
    """Is this the one move that places and turns the item in the air."""
    return (node is not None and {"NewLocation", "NewRotation"} <= in_pins(node)
            and _of_thrown(node))


def _from_hit(node, pin):
    return any(has_in_pin(f, "Hit") for f in _feeders(node, pin))


def check_stick():
    w = _walk()
    cast = w.character
    check("where the blade went into the body: one cast of the struck actor "
          "to Character, for its mesh",
          cast is not None and _title(cast).replace(" ", "") == "CastToCharacter"
          and _from_hit(cast, "Object"), _t(cast))
    line, nearest = w.line, w.nearest
    bodies = _body_traces()
    check("...two traces of that mesh's physics bodies alone",
          line is not None and nearest is not None
          and all(n in bodies and pin_value(n, "bTraceComplex").lower() == "false"
                  and [_title(f) for f in _feeders(n, "self")] == ["Get Mesh"]
                  for n in (line, nearest)), f"{_t(line)} + {_t(nearest)}")
    if line is None or nearest is None:
        return
    way = _pure_feeds(line)
    check("...the first on along the blade's own line: from the flight's hit "
          f"the way its segment flew, {STICK_LINE_REACH_CM:g} cm far",
          _from_hit(line, "TraceStart") and not _from_hit(line, "TraceEnd")
          and not any(has_in_pin(n, "TestLocation") for n in way)
          and any("Normal" in _title(n) for n in way)
          and any(num_pin(n, "X") == num_pin(n, "Y") == num_pin(n, "Z")
                  == STICK_LINE_REACH_CM for n in way if {"X", "Y", "Z"} <= in_pins(n)),
          str(sorted(_title(n) for n in way)))
    way = _pure_feeds(nearest)
    bone = the([n for n in way if has_in_pin(n, "TestLocation")])
    check("...the second only where that struck nothing: from the flight's hit "
          f"towards the bone nearest it that has a body, {STICK_TRACE_PAST:g} "
          "times as far",
          w.line_hit is not None and _title(w.line_hit) == "Branch"
          and _feeders(w.line_hit, "Condition") == [line]
          and _feeders(w.nearest_hit, "Condition") == [nearest]
          and _from_hit(nearest, "TraceStart") and bone is not None
          and pin_value(bone, "bRequirePhysicsAsset") == "true"
          and [_title(f) for f in _feeders(bone, "self")] == ["Get Mesh"]
          and _from_hit(bone, "TestLocation")
          and any(num_pin(n, "X") == num_pin(n, "Y") == num_pin(n, "Z") == STICK_TRACE_PAST
                  for n in way if {"X", "Y", "Z"} <= in_pins(n)),
          f"behind {_t(w.line_hit)}, the bone by {_t(bone)}")
    in_body = w.in_body
    check("a blade that wounded a body stays in it: after the blood and the "
          "sound of it going in, where "
          f"{THROW_BONE_VAR} is a bone, the item in the air is set on the skin "
          f"({THROW_SKIN_VAR}) once, as it is into a trunk",
          _asks_bone(w.stuck) and w.stab in fxv.calls(FX.STAB) and _is_put(in_body)
          and any(_title(n) == f"Get {THROW_SKIN_VAR}"
                  for f in _feeders(in_body, "NewLocation") for n in _pure_feeds(f))
          and _feeders(in_body, "NewLocation") != _feeders(in_body, "NewRotation"),
          f"{_t(w.stab)}, {_t(w.stuck)}, {_t(in_body)}")
    hold = w.hold
    check("...and attached to the mesh at the bone it struck, keeping "
          "where it was set and its own size",
          hold is not None and {"Parent", "SocketName", "LocationRule"} <= in_pins(hold)
          and _of_thrown(hold)
          and [_title(f) for f in _feeders(hold, "Parent")] == ["Get Mesh"]
          and [_title(f) for f in _feeders(hold, "SocketName")]
          == [f"Get {THROW_BONE_VAR}"]
          and all(pin_value(hold, r) == "KeepWorld"
                  for r in ("LocationRule", "RotationRule", "ScaleRule")),
          _t(hold))


def check_lodge():
    w = _walk()
    _ran, exits = _stage()
    tree = w.tree
    check("a blade that strikes no body asks whether it struck a tree: one "
          "cast to InstancedStaticMeshComponent, off the health cast's failed arm",
          tree is not None and has_in_pin(tree, "Object")
          and "instancedstaticmesh" in _title(tree).replace(" ", "").lower()
          and "HealthComponent" in _title(w.health).replace(" ", ""),
          _t(tree))
    high = w.high
    check(f"...and how high: within {LODGE_MAX_HEIGHT_CM:g} cm of the tree "
          "instance's own origin, in world space",
          high is not None and _title(high) == "Branch"
          and any(num_pin(c, "B") == LODGE_MAX_HEIGHT_CM
                  for c in _feeders(high, "Condition"))
          and any(has_in_pin(f, "InstanceIndex") and pin_value(f, "bWorldSpace") == "true"
                  for f in _pure_feeds(high)),
          _t(high))
    chips = fxv.in_fx(FX.LODGE, _spawns(IMPACT_CLASS_VAR))
    check("it chips the bark once (Fx_Lodge), told on the reachable arm",
          bool(chips) and w.lodge is not None and w.lodge in fxv.calls(FX.LODGE),
          f"{len(chips)} spawn(s) under Fx_Lodge, told by {_t(w.lodge)}")
    put = w.in_tree
    check("...and, after the tell of the chips and the chop's sound, is set into the "
          "trunk once: the item in the air, placed and turned in one move",
          _is_put(put)
          and any(has_in_pin(f, "Hit") for f in _feeders(put, "NewLocation")
                  for f in [f] + _feeders(f, "A")),
          _t(put))
    if not _is_put(put):
        return
    turn = {_title(n) for f in _feeders(put, "NewRotation")
            for n in [f] + _pure_feeds(f)}
    at = {_title(n) for f in _feeders(put, "NewLocation")
          for n in [f] + _pure_feeds(f)}
    check(f"...its own {LODGE_TURN_VAR}, then its X along the segment it flew",
          f"Get {LODGE_TURN_VAR}" in turn
          and any("CombineRotators" in t.replace(" ", "") for t in turn)
          and any("MakeRotFromX" in t.replace(" ", "") for t in turn),
          str(sorted(turn)))
    check(f"...its {LODGE_POINT_VAR}, turned the same way, on the hit",
          {f"Get {LODGE_POINT_VAR}", f"Get {LODGE_TURN_VAR}"} <= at, str(sorted(at)))
    landed = the(exits.get("Set Dropped", []))
    marks = _feeders(landed, "execute") if landed is not None else []
    check("lodged, in a tree or in a body, it is flagged Lodged (the pick-up "
          "puts such a blade back in empty hands) and skips the fall: straight "
          "on to the landing's Dropped, so it stays there as a pick-up",
          landed is not None and landed == w.lodged and _title(landed) == "Set Lodged"
          and pin_value(landed, "Lodged") == "true" and _of_thrown(landed)
          and w.hold is not None
          and sorted(n.get_path_name() for n in marks)
          == sorted(n.get_path_name() for n in (put, w.hold)),
          f"{_t(landed)} after {[_title(n) for n in marks]}")
    falls = [n for k, v in exits.items() if k != "Set Dropped" for n in v]
    arms = [w.gate, w.past, tree, high]
    check("everything else still comes down to the ground: an item that is no "
          "blade, one a body dropped, one that struck no tree, one too high",
          all(n is not None for n in arms)
          and sorted(n.get_path_name() for n in falls)
          == sorted(n.get_path_name() for n in arms),
          str([_title(n) for n in falls]))


def run():
    check_blades()
    if check_strike_gate():
        check_wound()
        check_lodge()
