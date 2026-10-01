"""verify.light -- the matches (matches.py) and lighting a campfire with them
(weapon_component/light.py): the item, which items Light, its place in the
starting loadout, the branch off the fire gate, and the strike: a piece of
wood found in the bag and spent, the held item's slot found again, the ground
trace and the spawn.

The campfire itself, and CampfireClass pointing at it, are survival's
(survival/verify/campfire.py): build_survival.py writes that default.

is_light_trace picks out the strike's ground trace, so the older count of
the component's traces can set it aside, as it does the chop's.
"""

from combat.chop_tuning import WOOD_CLASS_VAR
from combat.light_tuning import (
    CAMPFIRE_AHEAD_CM, CAMPFIRE_CLASS_VAR, CAMPFIRE_FEET_CM, CAMPFIRE_TRACE_DOWN_CM,
    CAMPFIRE_TRACE_UP_CM, LIGHT_WOOD_VAR, LIGHTS_VAR, MATCHES_CLASS_VAR,
)
from combat.matches import (
    BOX_CM, MATCHES_DISPLAY, MATCHES_MESH, MATCHES_SCALE, matches_outline,
)
from combat.paths import (
    AXE_BP_PATH, HOLD_ITEM_ANIM_PATH, ITEM_BP_PATH, KNIFE_BP_PATH, MATCHES_BP_PATH,
    WOOD_BP_PATH,
)
from combat.verify.chop import _branches_on, _pure_feeds, _ran_by, _spawns, _squash
from combat.verify.common import (
    BEL, PIN, by_pins, cdo, check, component_template, has_in_pin, load, num_pin,
    out_pins, pin_value,
)
from combat.verify.fixtures import w, wg
from combat.verify.grip_fit import (
    FIST_MISS_CM, JOINT_REACH_CM, JOINT_SINK_CM, grip_fit,
)
from combat.verify.punch import _feeders, _feeds, _title
from combat.weapon_component.inventory import STARTER_CLASS_VARS
from combat.weapon_component.knife import MELEE_VAR
from combat.weapon_specs import _weapon_specs

# A box of matches, the matches standing out of it (cm).
MATCHES_HEIGHT_CM = (5.0, 12.0)
# How far the closed fist's joints may stand off the box (cm): see the check.
MATCHES_REACH_CM = 4.5


def _fires():
    return _spawns(CAMPFIRE_CLASS_VAR)


def is_light_trace(node):
    """Is this the strike's ground trace (the one that runs the campfire's
    spawn)?"""
    return any(node in _ran_by(f) for f in _fires())


def _else_next(node):
    return [PIN.get_owning_node(q) for q in PIN.list_connected_pins(BEL.find_else_pin(node))]


def check_matches_item():
    bp = load(MATCHES_BP_PATH)
    check("BP_Matches exists", bp is not None)
    if bp is None:
        return
    check("...a child of BP_WeaponItem, so the bag, Q, G, E and the HUD take it",
          bp.get_blueprint_parent_class() == BEL.generated_class(load(ITEM_BP_PATH)))
    d = cdo(bp)
    flags = {k: d.get_editor_property(k) for k in
             (LIGHTS_VAR, MELEE_VAR, "Consumable", "UsesAmmo", "Automatic", "Dropped")}
    check("...Lights, so the fire key strikes it, and not a blade, food, a gun "
          "or lying about",
          flags == {LIGHTS_VAR: True, MELEE_VAR: False, "Consumable": False,
                    "UsesAmmo": False, "Automatic": False, "Dropped": False}, str(flags))
    model = component_template(bp, "Model")
    mesh = model.get_editor_property("static_mesh") if model else None
    check("...drawn by Quaternius's Survival Pack matchbox (SM_Matchbox)",
          mesh is not None and mesh == load(MATCHES_MESH), str(mesh))
    if model is None or mesh is None:
        return
    box = mesh.get_bounding_box()
    scale = model.get_editor_property("relative_scale3d")
    at = model.get_editor_property("relative_location")
    size = [(getattr(box.max, a) - getattr(box.min, a)) * getattr(scale, a) for a in "xyz"]
    check(f"...at {MATCHES_SCALE}, a box of matches "
          f"({MATCHES_HEIGHT_CM[0]:.0f}-{MATCHES_HEIGHT_CM[1]:.0f} cm tall), as measured",
          abs(scale.x - MATCHES_SCALE) < 1e-4 and scale.x == scale.y == scale.z
          and MATCHES_HEIGHT_CM[0] < size[2] < MATCHES_HEIGHT_CM[1]
          and all(abs(s - k) < 0.1 for s, k in zip(size, BOX_CM)),
          " x ".join(f"{s:.1f}" for s in size) + " cm")
    middle = [(getattr(box.min, a) + getattr(box.max, a)) / 2.0 * getattr(scale, a)
              + getattr(at, a) for a in "xyz"]
    check("...upright, its middle at the item's origin",
          all(abs(m) < 0.1 for m in middle), str([round(m, 2) for m in middle]))
    check("...and blocking nothing in the hand or on the ground",
          str(model.get_collision_profile_name()) == "NoCollision",
          str(model.get_collision_profile_name()))
    pose = d.get_editor_property("AimPose")
    check("...carried in A_HoldItem, with an icon and its name",
          pose is not None and pose == load(HOLD_ITEM_ANIM_PATH)
          and d.get_editor_property("Icon") is not None
          and str(d.get_editor_property("DisplayName")) == MATCHES_DISPLAY,
          f"{pose} {d.get_editor_property('Icon')}")
    fit = grip_fit(bp, HOLD_ITEM_ANIM_PATH, matches_outline(), "Grip")
    check("...its middle in the middle of the fist, no finger through it",
          fit["miss"] < FIST_MISS_CM and fit["sink"] < JOINT_SINK_CM,
          f"{fit['miss']:.2f} cm off, deepest joint {fit['sink']:.2f} cm in")
    # The fist has one pose, closed on a pistol's grip some 4 cm thick, and
    # the box is 1.3: the fingers stand off its faces instead of closing on
    # it (JOINT_REACH_CM is for a handle that fills the fist).
    check(f"...the fingers no more than {MATCHES_REACH_CM} cm off the slim box",
          JOINT_REACH_CM < MATCHES_REACH_CM and fit["reach"] < MATCHES_REACH_CM,
          f"furthest joint {fit['reach']:.2f} cm off")


def check_who_lights():
    others = {p.rsplit("/", 1)[1]: cdo(load(p)).get_editor_property(LIGHTS_VAR)
              for p in [KNIFE_BP_PATH, AXE_BP_PATH, WOOD_BP_PATH]
              + [s["path"] for s in _weapon_specs()]}
    check("only the matches Light: not the knife, the axe, the wood or a gun",
          all(v is False for v in others.values()), str(others))


def check_matches_loadout():
    got = w.get_editor_property(MATCHES_CLASS_VAR)
    check(f"{MATCHES_CLASS_VAR} points at BP_Matches_C",
          got is not None and got.get_name() == "BP_Matches_C", str(got))
    check("the matches are issued last, after the axe",
          STARTER_CLASS_VARS[-2:] == ("AxeClass", MATCHES_CLASS_VAR), str(STARTER_CLASS_VARS))
    spawned = [_title(f) for n in by_pins(wg, "Class", "SpawnTransform")
               for f in _feeders(n, "Class")]
    check("...spawned once by BeginPlay", spawned.count(f"Get {MATCHES_CLASS_VAR}") == 1,
          str(sorted(spawned)))


def check_light_gate():
    gates = _branches_on(f"Get {LIGHTS_VAR}")
    check(f"one Branch asks Held.{LIGHTS_VAR}", len(gates) == 1, str(len(gates)))
    if len(gates) != 1:
        return None
    gate = gates[0]
    before = _ran_by(gate)
    check("...on the Melee test's False arm, inside the fire gate (it reads Held)",
          len(before) == 1 and gate in _else_next(before[0])
          and any(MELEE_VAR in out_pins(f) for f in _feeders(before[0], "Condition")),
          str([_title(b) for b in before]))
    other = _else_next(gate)
    check("...and anything that does not Light goes on to the guns' ready gate",
          len(other) == 1 and "Get Automatic" in
          {_title(x) for x in _feeds(BEL.find_input_pin(other[0], "Condition"))},
          str([_title(o) for o in other]))
    press = [PIN.get_owning_node(q) for q in
             PIN.list_connected_pins(BEL.find_then_pin(gate))]
    names = ({_title(x) for x in _feeds(BEL.find_input_pin(press[0], "Condition"))}
             if len(press) == 1 else set())
    check("...then a tap strikes: a held button lights nothing more",
          "Get KeyFire" in names
          and not any("IsInputKeyDown" in t.replace(" ", "") for t in names),
          str(sorted(names)))
    return press[0] if len(press) == 1 else None


def check_light_strike(press):
    fires = _fires()
    check("a campfire is spawned in one place", len(fires) == 1, str(len(fires)))
    if len(fires) != 1 or press is None:
        return
    fire = fires[0]
    known = [PIN.get_owning_node(q) for q in
             PIN.list_connected_pins(BEL.find_then_pin(press))]
    check(f"the strike is refused before anything is spent while {CAMPFIRE_CLASS_VAR} "
          "is unset (build_survival.py fills it)",
          len(known) == 1 and any(
              "isvalidclass" in _squash(f)
              and any(_title(g) == f"Get {CAMPFIRE_CLASS_VAR}" for g in _feeders(f, "Class"))
              for f in _feeders(known[0], "Condition")),
          str([_title(n) for n in known]))

    picks = [n for n in wg if _title(n) == f"Set {LIGHT_WOOD_VAR}"]
    kept = [n for n in picks if _feeders(n, LIGHT_WOOD_VAR)]
    check("the wood to burn is forgotten, then looked for in the bag",
          len(picks) == 2 and len(kept) == 1, f"{len(picks)} sets, {len(kept)} fed")
    if len(kept) != 1:
        return
    tests = [g for g in _ran_by(kept[0]) if _title(g) == "Branch"]
    src = _pure_feeds(tests[0]) if len(tests) == 1 else []
    check(f"...an item of the bag whose class is {WOOD_CLASS_VAR}",
          any(_title(n) == f"Get {WOOD_CLASS_VAR}" for n in src)
          and any(_title(n) == "Get Inventory" for f in _feeders(kept[0], LIGHT_WOOD_VAR)
                  for n in _feeders(f, "Array")),
          str(sorted({_title(n) for n in src})))

    removes = [n for n in by_pins(wg, "TargetArray", "Item")
               if any(_title(f) == f"Get {LIGHT_WOOD_VAR}" for f in _feeders(n, "Item"))]
    check("the strike takes that piece of wood out of Inventory",
          len(removes) == 1
          and any(_title(f) == "Get Inventory" for f in _feeders(removes[0], "TargetArray")),
          str(len(removes)))
    if len(removes) != 1:
        return
    has = _ran_by(removes[0])
    check("...only behind a Branch on IsValid(LightWood): with no wood, nothing happens",
          len(has) == 1 and _title(has[0]) == "Branch" and removes[0] not in _else_next(has[0])
          and any("isvalid" in _squash(f)
                  and any(_title(g) == f"Get {LIGHT_WOOD_VAR}" for g in _feeders(f, "Object"))
                  for f in _feeders(has[0], "Condition")),
          str([_title(h) for h in has]))
    check("...asked once the loop is done (ForEachLoop has no break pin)",
          len(has) == 1 and any("Array" in {str(PIN.get_pin_name(p))
                                           for p in BEL.list_input_pins(l)}
                                for l in _ran_by(has[0])),
          str([_title(l) for h in has for l in _ran_by(h)]))
    burnt = [n for n in wg if removes[0] in _ran_by(n)]
    check("...and destroys it, not the matches",
          len(burnt) == 1 and "destroy" in _squash(burnt[0])
          and [_title(f) for f in _feeders(burnt[0], "self")] == [f"Get {LIGHT_WOOD_VAR}"],
          str([_title(b) for b in burnt]))
    slots = [n for n in wg if _title(n) == "Set EquippedIndex"
             and any(b in _ran_by(n) for b in burnt)]
    finds = [f for s in slots for f in _feeders(s, "EquippedIndex")]
    check("EquippedIndex follows Held to its slot in the shorter bag",
          len(slots) == 1 and len(finds) == 1 and has_in_pin(finds[0], "ItemToFind")
          and any(_title(f) == "Get Held" for f in _feeders(finds[0], "ItemToFind"))
          and any(_title(f) == "Get Inventory" for f in _feeders(finds[0], "TargetArray")),
          str([_title(f) for f in finds]))

    traces = [t for t in _ran_by(fire) if has_in_pin(t, "TraceChannel")]
    check("the fire is spawned after one ground trace, after the wood is spent",
          len(traces) == 1 and len(_ran_by(fire)) == 1
          and any(s in _ran_by(traces[0]) for s in slots),
          str([_title(t) for t in _ran_by(fire)]))
    if len(traces) != 1:
        return
    trace = traces[0]
    src = _pure_feeds(trace)
    check(f"...{CAMPFIRE_AHEAD_CM:.0f} cm along the owner's forward",
          any("forwardvector" in _squash(n) for n in src)
          and any(has_in_pin(n, "X") and num_pin(n, "X") == CAMPFIRE_AHEAD_CM for n in src),
          str(sorted({_title(n) for n in src})))
    ends = {k: [num_pin(g, "Z") for e in _feeders(trace, k) for g in _feeders(e, "B")]
            for k in ("Start", "End")}
    check(f"...from {CAMPFIRE_TRACE_UP_CM:.0f} cm above the spot to "
          f"{CAMPFIRE_TRACE_DOWN_CM:.0f} cm below it, on Visibility",
          ends == {"Start": [CAMPFIRE_TRACE_UP_CM], "End": [-CAMPFIRE_TRACE_DOWN_CM]}
          and str(pin_value(trace, "TraceChannel")) == "TraceTypeQuery1", str(ends))
    places = [n for m in _feeders(fire, "SpawnTransform") for n in _feeders(m, "Location")]
    feet = [num_pin(g, "Z") for p in places for e in _feeders(p, "B") for g in _feeders(e, "B")]
    check("the fire stands on the ground the trace found, or at the player's feet "
          "where there is none",
          len(places) == 1 and trace in _feeders(places[0], "bPickA")
          and feet == [-CAMPFIRE_FEET_CM], f"{[_title(n) for n in places]} {feet}")
    check("...and always spawns (AlwaysSpawn), whatever stands there",
          str(pin_value(fire, "CollisionHandlingOverride")) == "AlwaysSpawn",
          str(pin_value(fire, "CollisionHandlingOverride")))


def run():
    check_matches_item()
    check_who_lights()
    check_matches_loadout()
    check_light_strike(check_light_gate())
