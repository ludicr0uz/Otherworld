"""verify.chop -- chopping a tree (weapon_component/chop.py) and what it
leaves (wood.py): the wood item, which items Chop, and the stage off the knife
blow's failed health cast: the tree test, the count on one tree, the landing
point stored before it is read, the ground trace and the spawn.

is_chop_node picks out the stage's nodes, so the older counts over the whole
graph (traces, SelectFloats, impact spawns, Make Rotators, random draws) can
set them aside, as they do the punch's and the knife's.
"""

import functools

import unreal

from combat.chop_tuning import (
    CHOP_COUNT_VAR, CHOP_ITEM_VAR, CHOP_TREE_VAR, CHOPS_PER_WOOD, CHOPS_VAR,
    WOOD_CLASS_VAR, WOOD_GROUND_CM, WOOD_LIE_PITCH_DEG, WOOD_OUT_CM, WOOD_SIDE_DEG,
    WOOD_SPOT_VAR,
)
from combat.paths import (
    AXE_BP_PATH, HOLD_ITEM_ANIM_PATH, ITEM_BP_PATH, KNIFE_BP_PATH, WOOD_BP_PATH,
)
from combat.verify.common import (
    BEL, PIN, by_pins, cdo, check, component_template, has_in_pin, load, num_pin,
    pin_value,
)
from combat.verify.fixtures import w, wg
from combat.verify.grip_fit import FIST_MISS_CM, JOINT_REACH_CM, grip_fit
from combat.verify.knife import is_knife_sweep
from combat.verify.punch import _feeders, _title, is_punch_sweep
from combat.weapon_component.surface_impact import IMPACT_CLASS_VAR
from combat.weapon_specs import _weapon_specs
from combat.wood import (
    LOG_LENGTH_CM, LOG_THICK_CM, WOOD_DISPLAY, WOOD_MESH, WOOD_SCALE, wood_outline,
)

# A piece of firewood, end to end (cm).
WOOD_LENGTH_CM = (20.0, 45.0)
# How far the closed fist's joints may sit inside the log (cm): see the check.
WOOD_SINK_CM = 1.8


def _squash(node):
    return _title(node).replace(" ", "").lower()


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


def _ran_by(node):
    """The nodes whose exec output runs into ``node``."""
    return _feeders(node, "execute")


def _casts():
    return [n for n in wg if "instancedstaticmesh" in _squash(n)
            and has_in_pin(n, "Object")]


def _spawns(var):
    return [n for n in by_pins(wg, "Class", "SpawnTransform")
            if any(_title(f) == f"Get {var}" for f in _feeders(n, "Class"))]


def _sets(var):
    return [n for n in wg if _title(n) == f"Set {var}"]


def _floor_traces():
    return [n for n in by_pins(wg, "Start", "End", "TraceChannel")
            if any(_title(f) == f"Get {WOOD_SPOT_VAR}" for f in _feeders(n, "Start"))]


def _branches_on(title):
    return [n for n in wg if _title(n) == "Branch"
            and any(_title(f) == title for f in _feeders(n, "Condition"))]


@functools.lru_cache(maxsize=1)
def _chop_nodes():
    casts = _casts()
    roots = list(casts)
    roots += [n for n in _spawns(IMPACT_CLASS_VAR) if set(_ran_by(n)) & set(casts)]
    for var in (CHOP_COUNT_VAR, CHOP_TREE_VAR, CHOP_ITEM_VAR, WOOD_SPOT_VAR):
        roots += _sets(var)
    roots += _spawns(WOOD_CLASS_VAR) + _floor_traces()
    bites = _branches_on(f"Get {CHOPS_VAR}")
    roots += bites + [g for b in bites for g in _ran_by(b) if _title(g) == "Branch"]
    roots += [n for n in wg if _title(n) == "Branch"
              and any(_title(s) == f"Set {CHOP_ITEM_VAR}" for s in _ran_by(n))]
    names = {n.get_path_name() for n in roots}
    for root in roots:
        names |= {f.get_path_name() for f in _pure_feeds(root)}
    return frozenset(names)


def is_chop_node(node):
    """Is this node part of the chop stage (its exec nodes, or a pure node
    feeding one)? The sweep and its broken hit are the blow's, not the chop's."""
    return (node.get_path_name() in _chop_nodes()
            and not is_knife_sweep(node) and not is_punch_sweep(node)
            and "Hit" not in {str(PIN.get_pin_name(p)) for p in BEL.list_input_pins(node)})


def check_wood_item():
    bp = load(WOOD_BP_PATH)
    check("BP_Wood exists", bp is not None)
    if bp is None:
        return
    check("...a child of BP_WeaponItem, so the bag, Q, G, E and the HUD take it",
          bp.get_blueprint_parent_class() == BEL.generated_class(load(ITEM_BP_PATH)))
    d = cdo(bp)
    flags = {k: d.get_editor_property(k) for k in
             ("Dropped", "Melee", "Consumable", CHOPS_VAR, "UsesAmmo", "Automatic")}
    check("...lying about from the start (Dropped), and not a melee item, food, "
          "a tool that chops or a gun",
          flags == {"Dropped": True, "Melee": False, "Consumable": False,
                    CHOPS_VAR: False, "UsesAmmo": False, "Automatic": False}, str(flags))
    inert = {k: d.get_editor_property(k) for k in
             ("PelletCount", "Damage", "RecoilPitch", "ShotVolume", "FireSound")}
    check("...with nothing for the fire key to fire: no pellets, damage, kick, "
          "noise or sound",
          inert == {"PelletCount": 0, "Damage": 0.0, "RecoilPitch": 0.0,
                    "ShotVolume": 0.0, "FireSound": None}, str(inert))
    model = component_template(bp, "Model")
    mesh = model.get_editor_property("static_mesh") if model else None
    check("...drawn by Quaternius's Survival Pack log (SM_WoodLog)",
          mesh is not None and mesh == load(WOOD_MESH), str(mesh))
    if model is None or mesh is None:
        return
    box = mesh.get_bounding_box()
    scale = model.get_editor_property("relative_scale3d")
    at = model.get_editor_property("relative_location")
    length = (box.max.x - box.min.x) * scale.x
    thick = ((box.max.y - box.min.y) * scale.y, (box.max.z - box.min.z) * scale.z)
    check(f"...at {WOOD_SCALE}, a split of firewood "
          f"({WOOD_LENGTH_CM[0]:.0f}-{WOOD_LENGTH_CM[1]:.0f} cm long, a fistful "
          f"thick), as measured",
          all(abs(getattr(scale, a) - k) < 1e-4 for a, k in zip("xyz", WOOD_SCALE))
          and WOOD_LENGTH_CM[0] < length < WOOD_LENGTH_CM[1]
          and abs(length - LOG_LENGTH_CM) < 0.5
          and all(abs(t - k) < 0.3 for t, k in zip(thick, LOG_THICK_CM)),
          f"{length:.1f} cm long, {thick[0]:.1f} x {thick[1]:.1f} cm thick")
    turn = unreal.MathLibrary.greater_greater_vector_rotator
    rot = model.get_editor_property("relative_rotation")
    up = turn(unreal.Vector(1.0, 0.0, 0.0), rot)
    mid = turn(unreal.Vector(*[(getattr(box.min, a) + getattr(box.max, a)) / 2.0
                               * getattr(scale, a) for a in "xyz"]), rot)
    middle = [getattr(mid, a) + getattr(at, a) for a in "xyz"]
    check("...on end in the item's frame, up through the fist, its middle at "
          "the origin",
          up.z > 0.99 and all(abs(m) < 0.5 for m in middle),
          f"length along {up}, middle {[round(m, 2) for m in middle]}")
    check("...and blocking nothing in the hand or on the ground",
          str(model.get_collision_profile_name()) == "NoCollision",
          str(model.get_collision_profile_name()))
    pose = d.get_editor_property("AimPose")
    check("...carried in A_HoldItem, with an icon and its name",
          pose is not None and pose == load(HOLD_ITEM_ANIM_PATH)
          and d.get_editor_property("Icon") is not None
          and str(d.get_editor_property("DisplayName")) == WOOD_DISPLAY,
          f"{pose} {d.get_editor_property('Icon')}")
    fit = grip_fit(bp, HOLD_ITEM_ANIM_PATH, wood_outline(), "Grip")
    check("...its middle in the middle of the fist, the fingers closed on it",
          fit["miss"] < FIST_MISS_CM and fit["reach"] < JOINT_REACH_CM,
          f"{fit['miss']:.2f} cm off, furthest joint {fit['reach']:.2f} cm off")
    # A log has no handle. The fist has one pose, closed on a pistol's grip,
    # and its joints sit inside anything over 4 cm thick; this is the least of
    # it, the log running up through the fist (across it, 2 cm and more).
    check(f"...which sink no more than {WOOD_SINK_CM} cm into it",
          fit["sink"] < WOOD_SINK_CM, f"deepest joint {fit['sink']:.2f} cm in")


def check_who_chops():
    check("the axe Chops", cdo(load(AXE_BP_PATH)).get_editor_property(CHOPS_VAR) is True)
    others = {p.rsplit("/", 1)[1]: cdo(load(p)).get_editor_property(CHOPS_VAR)
              for p in [KNIFE_BP_PATH] + [s["path"] for s in _weapon_specs()]}
    check("...and nothing else does: not the knife, not a gun",
          all(v is False for v in others.values()), str(others))


def check_chop_gate():
    got = w.get_editor_property(WOOD_CLASS_VAR)
    check(f"{WOOD_CLASS_VAR} points at BP_Wood_C",
          got is not None and got.get_name() == "BP_Wood_C", str(got))
    check("no blow is counted at the start",
          w.get_editor_property(CHOP_COUNT_VAR) == 0
          and w.get_editor_property(CHOP_TREE_VAR) is None)
    casts = _casts()
    check("one test for a tree: a cast to InstancedStaticMeshComponent",
          len(casts) == 1, str([_title(c) for c in casts]))
    if len(casts) != 1:
        return
    cast = casts[0]
    hits = _feeders(cast, "Object")
    check("...of the component the knife's sweep struck (not the punch's: fists "
          "cut no tree)",
          len(hits) == 1 and any(is_knife_sweep(s) for s in _feeders(hits[0], "Hit")),
          str([_title(h) for h in hits]))
    bites = _branches_on(f"Get {CHOPS_VAR}")
    check(f"...asked only behind a Branch on Held.{CHOPS_VAR}",
          len(bites) == 1 and bites[0] in _ran_by(cast), str(len(bites)))
    if len(bites) != 1:
        return
    armed = [g for g in _ran_by(bites[0]) if _title(g) == "Branch"]
    check(f"...and {CHOPS_VAR} is read only behind its own Branch on IsValid(Held), "
          "nested, not folded: the hands may be empty when the blow lands",
          len(armed) == 1 and len(_ran_by(bites[0])) == 1
          and any("isvalid" in _squash(f) for f in _feeders(armed[0], "Condition")),
          str([_title(g) for g in _ran_by(bites[0])]))
    check("...which runs off the blow's failed health cast: a body bleeds, it is "
          "not chopped",
          len(armed) == 1 and any("health" in _squash(c) for c in _ran_by(armed[0])),
          str([_title(c) for g in armed for c in _ran_by(g)]))
    chips = [n for n in _spawns(IMPACT_CLASS_VAR) if cast in _ran_by(n)]
    check("a blow on a tree throws chips: BP_BulletImpact, at the cut",
          len(chips) == 1 and any(
              is_knife_sweep(s) for m in _feeders(chips[0], "SpawnTransform")
              for b in _feeders(m, "Location") for s in _feeders(b, "Hit")),
          str(len(chips)))


def check_chop_count():
    counts = _sets(CHOP_COUNT_VAR)
    check(f"{CHOP_COUNT_VAR} is written twice: the blow counted, and the count "
          "started over", len(counts) == 2, str(len(counts)))
    picked = [n for n in counts if _feeders(n, CHOP_COUNT_VAR)]
    reset = [n for n in counts if not _feeders(n, CHOP_COUNT_VAR)]
    if len(picked) != 1 or len(reset) != 1:
        check("...one from a pick, one a literal", False)
        return
    feeds = {_title(f) for f in _pure_feeds(picked[0])}
    check("the count goes on only on the same tree: the component AND the "
          "instance struck last time, else it starts at 1",
          {f"Get {CHOP_TREE_VAR}", f"Get {CHOP_ITEM_VAR}", f"Get {CHOP_COUNT_VAR}"}
          <= feeds and any("select" in t.lower() for t in feeds), str(sorted(feeds)))
    # The pure "same tree" test reads ChopTree and ChopItem, so the count must
    # be stored before either is overwritten with this tree.
    tree, item = _sets(CHOP_TREE_VAR), _sets(CHOP_ITEM_VAR)
    check("...and is stored before the tree is: count, then ChopTree, then ChopItem",
          len(tree) == 1 and len(item) == 1 and picked[0] in _ran_by(tree[0])
          and tree[0] in _ran_by(item[0]),
          str([_title(n) for t in tree for n in _ran_by(t)]))
    gates = [n for n in wg if _title(n) == "Branch" and item
             and item[0] in _ran_by(n)]
    tests = [f for g in gates for f in _feeders(g, "Condition")]
    check(f"wood comes on blow {CHOPS_PER_WOOD}: ChopCount >= {CHOPS_PER_WOOD}",
          len(gates) == 1 and len(tests) == 1
          and num_pin(tests[0], "B") == CHOPS_PER_WOOD and CHOPS_PER_WOOD >= 1
          and any(_title(f) == f"Get {CHOP_COUNT_VAR}" for f in _feeders(tests[0], "A")),
          str([_title(t) for t in tests]))
    # A literal equal to the pin's default is not saved: "" off disk.
    check("...and the count starts over there, at 0",
          len(gates) == 1 and gates[0] in _ran_by(reset[0])
          and str(pin_value(reset[0], CHOP_COUNT_VAR)) in ("0", ""),
          repr(pin_value(reset[0], CHOP_COUNT_VAR)))


def check_wood_spawn():
    spots, traces, woods = _sets(WOOD_SPOT_VAR), _floor_traces(), _spawns(WOOD_CLASS_VAR)
    check("the wood is spawned in one place, after one ground trace from one "
          "stored landing point",
          len(spots) == 1 and len(traces) == 1 and len(woods) == 1,
          f"{len(spots)} / {len(traces)} / {len(woods)}")
    if not (len(spots) == 1 and len(traces) == 1 and len(woods) == 1):
        return
    spot, trace, wood = spots[0], traces[0], woods[0]
    src = _pure_feeds(spot)
    draws = [n for n in src if _squash(n).startswith("random")]
    check("the landing point is drawn at random to one side or the other...",
          len(draws) == 2
          and sorted(num_pin(n, k) for n in draws for k in ("Min", "Max")
                     if has_in_pin(n, k)) == sorted(WOOD_SIDE_DEG)
          and 0.0 < WOOD_SIDE_DEG[0] < WOOD_SIDE_DEG[1] <= 90.0,
          str([_title(n) for n in draws]))
    check(f"...{WOOD_OUT_CM:.0f} cm from the cut, towards where the blow came from",
          any(is_knife_sweep(s) for n in src for s in _feeders(n, "Hit"))
          and any(has_in_pin(n, "X") and num_pin(n, "X") == WOOD_OUT_CM for n in src),
          str(sorted({_title(n) for n in src})))
    after = _pure_feeds(trace) + _pure_feeds(wood)
    check("...and stored before it is read: no random draw feeds the trace's two "
          "ends or the wood's place (a pure node read twice answers twice)",
          not any(_squash(n).startswith("random") and n in draws for n in after)
          and spot in _ran_by(trace) and trace in _ran_by(wood),
          str([_title(n) for n in after if _squash(n).startswith("random")]))
    ends = [f for f in _feeders(trace, "End")]
    drop = [g for e in ends for g in _feeders(e, "B")]
    check(f"the trace looks {WOOD_GROUND_CM:.0f} cm straight down, on Visibility, "
          "from the stored point",
          len(drop) == 1 and num_pin(drop[0], "Z") == -WOOD_GROUND_CM
          and str(pin_value(trace, "TraceChannel")) == "TraceTypeQuery1",
          str(pin_value(trace, "TraceChannel")))
    places = [n for m in _feeders(wood, "SpawnTransform") for n in _feeders(m, "Location")]
    check("the wood rests on the ground the trace found, or at the stored point "
          "where there is none",
          len(places) == 1 and trace in _feeders(places[0], "bPickA")
          and any(_title(f) == f"Get {WOOD_SPOT_VAR}" for f in _feeders(places[0], "B")),
          str([_title(n) for n in places]))
    turns = [n for m in _feeders(wood, "SpawnTransform") for n in _feeders(m, "Rotation")]
    check("...laid flat (the log stands on end in its own frame), at a random heading",
          len(turns) == 1 and num_pin(turns[0], "Pitch") == WOOD_LIE_PITCH_DEG == 90.0
          and any(_squash(f).startswith("random") for f in _feeders(turns[0], "Yaw")),
          str([_title(n) for n in turns]))
    check("...and always spawns (AlwaysSpawn), whatever is beside the trunk",
          str(pin_value(wood, "CollisionHandlingOverride")) == "AlwaysSpawn",
          str(pin_value(wood, "CollisionHandlingOverride")))


def run():
    check_wood_item()
    check_who_chops()
    check_chop_gate()
    check_chop_count()
    check_wood_spawn()
