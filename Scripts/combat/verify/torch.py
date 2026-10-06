"""verify.torch -- the stick and the use key (combat/stick.py,
weapon_component/use.py, weapon_component/torch.py): BP_Stick and its two
models, the burn on its own Tick, the two torch poses, the loadout, the use
key (the sights key on an item with no sights, which then does not aim), the
light at a campfire, FireWard, and the raised pose's swap.
"""

import unreal

from combat.grip import fist_in_socket
from combat.light_tuning import CAMPFIRE_CLASS_VAR
from combat.paths import (
    FIRE_WARD_VAR, HOLD_KNIFE_ANIM_PATH, HOLD_TORCH_ANIM_PATH, ITEM_BP_PATH,
    STICK_BP_PATH, WARD_TORCH_ANIM_PATH, WEAPON_DIR,
)
from combat.seat_tuning import HAS_SIGHTS_VAR, SIGHTS_FORCED_VAR
from combat.strike_vars import AskUse
from combat.skin import player_skin
from combat.stick import (
    FLAME, GLOW, MODEL, STICK_DISPLAY, STICK_LIT_MESH, STICK_MESH, STICK_SCALE,
    stick_outline,
)
from combat.torch_tuning import (
    BURN_OUT_VAR, BURNS_VAR, LIT_VAR, NEAR_FIRE_VAR, STICK_BURN_S, STICK_CLASS_VAR,
    STICK_LIGHT_RADIUS_CM, USE_POSE_VAR, WARD_CARRY_VAR, WARD_ITEM_VAR,
)
from combat.use_tuning import USE_PRESSED_VAR, USE_WAS_VAR, USING_VAR
from combat.verify.chop import _branches_on, _pure_feeds, _ran_by
from combat.verify.common import (
    BEL, PIN, by_pins, cdo, check, component_template, graph, load, num_pin, pin_value,
)
from combat.verify.fixtures import _is_exec, w, wg
from combat.verify.glimmer import is_glimmer_node
from combat.verify.grip_fit import check_handles_in_fist
from combat.verify.hold_pose import _pose, _sub
from combat.verify.punch import _feeders, _feeds, _title
from combat.weapon_component.inventory import STARTER_CLASS_VARS
from combat.weapon_specs import _weapon_specs
from survival.paths import SURVIVAL_DIR

# A stick to carry in one hand, and the same with flames standing on it (cm).
STICK_LENGTH_CM = (35.0, 60.0)
FLAMES_OVER_CM = 8.0
# Where the fist must be, cm, in the body frame (+Y forward, +Z up), from the
# hips: carried, at the shoulder's height or above the knife's guard; held
# out, at arm's length in front and no lower.
WARD_REACH_CM = 40.0
WARD_OVER_CARRY_REACH_CM = 15.0
TORCH_HEIGHT_CM = 25.0
FIST_SAME_CM = 0.5
# Every other item: none of them Burns.
OTHERS = ([s["path"] for s in _weapon_specs()]
          + [f"{WEAPON_DIR}/{n}" for n in ("BP_Knife", "BP_Axe", "BP_Wood", "BP_Matches")]
          + [f"{SURVIVAL_DIR}/{n}" for n in ("BP_Mushroom", "BP_WaterCanteen")])


def _false(node, pin):
    # A literal equal to its pin's default reads "" once loaded from disk.
    return pin_value(node, pin) in ("false", "") and not _feeders(node, pin)


def _sets(nodes, var):
    return [n for n in nodes if _title(n) == f"Set {var}"]


def _names(nodes):
    return {_title(n) for n in nodes}


def check_stick_item():
    bp = load(STICK_BP_PATH)
    check("BP_Stick exists", bp is not None)
    if bp is None:
        return
    check("...a child of BP_WeaponItem, so the bag, Q, G, E, the throw and the HUD take it",
          bp.get_blueprint_parent_class() == BEL.generated_class(load(ITEM_BP_PATH)))
    d = cdo(bp)
    flags = {k: d.get_editor_property(k) for k in
             (BURNS_VAR, LIT_VAR, HAS_SIGHTS_VAR, "Melee", "Consumable", "UsesAmmo", "Dropped")}
    check(f"...it {BURNS_VAR}, starts unlit, and is not a gun, a blade, food or lying about",
          flags == {BURNS_VAR: True, LIT_VAR: False, HAS_SIGHTS_VAR: False, "Melee": False,
                    "Consumable": False, "UsesAmmo": False, "Dropped": False}, str(flags))
    burners = [p.rsplit("/", 1)[-1] for p in OTHERS
               if load(p) is None or cdo(load(p)).get_editor_property(BURNS_VAR) is not False]
    check(f"...and nothing else {BURNS_VAR}", not burners, str(burners))

    bare, lit, glow = (component_template(bp, n) for n in (MODEL, FLAME, GLOW))
    meshes = [c.get_editor_property("static_mesh") if c else None for c in (bare, lit)]
    check("...drawn by Quaternius's Survival Pack torch, bare and burning, in one place",
          meshes == [load(STICK_MESH), load(STICK_LIT_MESH)] and None not in meshes
          and bare.get_editor_property("relative_location")
          == lit.get_editor_property("relative_location")
          and bare.get_editor_property("relative_scale3d")
          == lit.get_editor_property("relative_scale3d"), str(meshes))
    if None in meshes or glow is None:
        check("...with a glow", False)
        return
    scale = bare.get_editor_property("relative_scale3d").z
    tall = [(m.get_bounding_box().max.z - m.get_bounding_box().min.z) * scale for m in meshes]
    check(f"...at {STICK_SCALE}, a stick for one hand "
          f"({STICK_LENGTH_CM[0]:.0f}-{STICK_LENGTH_CM[1]:.0f} cm), taller by its flames",
          abs(scale - STICK_SCALE) < 1e-4 and STICK_LENGTH_CM[0] < tall[0] < STICK_LENGTH_CM[1]
          and tall[1] > tall[0] + FLAMES_OVER_CM, f"{tall[0]:.1f} cm, {tall[1]:.1f} burning")
    check("...the bare stick shown and the burning one hidden until it is lit",
          bare.get_editor_property("visible") is True
          and lit.get_editor_property("visible") is False)
    top = bare.get_editor_property("relative_location").z + meshes[0].get_bounding_box().max.z * scale
    check("...its fire a point light at the flames, hidden with them, casting no shadow",
          isinstance(glow, unreal.PointLightComponent)
          and glow.get_editor_property("visible") is False
          and glow.get_editor_property("cast_shadows") is False
          and glow.get_editor_property("relative_location").z > top - 5.0,
          f"glow z {glow.get_editor_property('relative_location').z:.1f}, stick top {top:.1f}")
    check("...and neither model blocking anything",
          all(str(c.get_collision_profile_name()) == "NoCollision" for c in (bare, lit)))
    pose, use = d.get_editor_property("AimPose"), d.get_editor_property(USE_POSE_VAR)
    check(f"...carried in A_HoldTorch and raised in A_WardTorch (its {USE_POSE_VAR}), "
          "with an icon and its name",
          pose is not None and pose == load(HOLD_TORCH_ANIM_PATH)
          and use is not None and use == load(WARD_TORCH_ANIM_PATH)
          and d.get_editor_property("Icon") is not None
          and str(d.get_editor_property("DisplayName")) == STICK_DISPLAY,
          f"{pose} {use} {d.get_editor_property('Icon')}")
    check_handles_in_fist([("Stick", STICK_BP_PATH, HOLD_TORCH_ANIM_PATH,
                            stick_outline(), "Grip", None)])


def check_stick_burn():
    bp = load(STICK_BP_PATH)
    if bp is None:
        return
    sg = graph(bp).list_all_nodes()
    outs = _sets(sg, LIT_VAR)
    check("the stick puts its own fire out, in one place", len(outs) == 1
          and _false(outs[0], LIT_VAR), str(len(outs)))
    if len(outs) == 1:
        gates = _ran_by(outs[0])
        src = _pure_feeds(gates[0]) if len(gates) == 1 else []
        check(f"...on its Tick, once it is {LIT_VAR} and the clock has reached {BURN_OUT_VAR}",
              {f"Get {LIT_VAR}", f"Get {BURN_OUT_VAR}"} <= _names(src)
              and any("GetTimeSeconds" in _title(n).replace(" ", "") for n in src)
              and any("ReceiveTick" in str(n.get_name()) or "Tick" in _title(n)
                      for g in gates for n in _ran_by(g)),
              str(sorted(_names(src))))
    shows = [n for n in by_pins(sg, "bNewVisibility") if not is_glimmer_node(n)]
    how = {}
    for n in shows:
        src = _pure_feeds(n)
        who = [_title(f).replace("Get ", "") for f in _feeders(n, "self")]
        fed = _feeders(n, "bNewVisibility")
        how[who[0] if who else "?"] = (
            "lit" if [_title(f) for f in fed] == [f"Get {LIT_VAR}"]
            else "unlit" if f"Get {LIT_VAR}" in _names(src) else "?")
    check("...and shows the bare stick while not Lit, the burning one and the glow while Lit",
          how == {MODEL: "unlit", FLAME: "lit", GLOW: "lit"}, str(how))


def check_torch_poses():
    skin = player_skin()
    b = skin.pose_bones
    carry, ward, knife = (load(p) for p in (HOLD_TORCH_ANIM_PATH, WARD_TORCH_ANIM_PATH,
                                            HOLD_KNIFE_ANIM_PATH))
    if None in (carry, ward, knife):
        check("both torch poses load", False)
        return
    c, r, k = _pose(carry), _pose(ward), _pose(knife)
    hand_c = _sub(c(b["hand_r"]), c(b["hips"]))
    hand_r = _sub(r(b["hand_r"]), r(b["hips"]))
    hand_k = _sub(k(b["hand_r"]), k(b["hips"]))
    check("A_HoldTorch carries the stick up beside the head: the fist above the knife's "
          "guard, the left arm hanging",
          hand_c[2] > TORCH_HEIGHT_CM and hand_c[2] > hand_k[2]
          and c(b["hand_l"])[2] < c(b["forearm_l"])[2] < c(b["upperarm_l"])[2],
          f"right hand {tuple(round(v, 1) for v in hand_c)} from the hips")
    check("A_WardTorch holds it out: the fist at arm's length in front, no lower",
          hand_r[1] > WARD_REACH_CM and hand_r[1] > hand_c[1] + WARD_OVER_CARRY_REACH_CM
          and hand_r[2] > TORCH_HEIGHT_CM,
          f"right hand {tuple(round(v, 1) for v in hand_r)} from the hips")
    fist = fist_in_socket(skin.aim_pistol)[0]
    off = {p.rsplit("/", 1)[-1]: round((fist_in_socket(p)[0] - fist).length(), 2)
           for p in (HOLD_TORCH_ANIM_PATH, WARD_TORCH_ANIM_PATH)}
    check("...and both close the right hand as the pistol pose does, so the one grip "
          "holds in either (fist within 0.5 cm)",
          all(v < FIST_SAME_CM for v in off.values()), str(off))


def check_stick_loadout():
    got = w.get_editor_property(STICK_CLASS_VAR)
    check(f"{STICK_CLASS_VAR} points at BP_Stick_C",
          got is not None and got.get_name() == "BP_Stick_C", str(got))
    spawned = [_title(f) for n in by_pins(wg, "Class", "SpawnTransform")
               for f in _feeders(n, "Class")]
    check("the stick is issued last, after the matches, spawned once by BeginPlay",
          STARTER_CLASS_VARS[-1] == STICK_CLASS_VAR
          and spawned.count(f"Get {STICK_CLASS_VAR}") == 1, str(STARTER_CLASS_VARS))


def check_use_key():
    for name in (USING_VAR, USE_PRESSED_VAR, USE_WAS_VAR, NEAR_FIRE_VAR):
        check(f"{name} exists and starts False", w.get_editor_property(name) is False,
              repr(w.get_editor_property(name)))
    sets = _sets(wg, USING_VAR)
    fed = [n for n in sets if _feeders(n, USING_VAR)]
    idle = [n for n in sets if _false(n, USING_VAR)]
    check(f"{USING_VAR} is written in two places: with an item in hand, and false with "
          "empty hands", len(sets) == 2 and len(fed) == 1 and len(idle) == 1,
          f"{len(sets)} writes, {len(fed)} fed")
    if len(fed) != 1 or len(idle) != 1:
        return
    src = _names(_feeds(BEL.find_input_pin(fed[0], USING_VAR)))
    check("...the sights key held (or the probes' SightsForced), not sprinting, on an "
          f"item with no sights (NOT Held.{HAS_SIGHTS_VAR})",
          {"Get KeySights", f"Get {SIGHTS_FORCED_VAR}", "Get Sprinting"} <= src
          and any(HAS_SIGHTS_VAR in t for t in src)
          and any("IsInputKeyDown" in t.replace(" ", "") for t in src), str(sorted(src)))
    gates = _ran_by(fed[0])
    check(f"...Held.{HAS_SIGHTS_VAR} read on the true arm of an IsValid(Held) Branch, "
          "whose false arm is the empty hands' write",
          len(gates) == 1 and gates[0] in _ran_by(idle[0])
          and BEL.find_then_pin(gates[0]) is not None
          and fed[0] in [PIN.get_owning_node(q) for q in
                         PIN.list_connected_pins(BEL.find_then_pin(gates[0]))]
          and any("IsValid" in _title(f).replace(" ", "")
                  for f in _feeders(gates[0], "Condition")),
          str([_title(g) for g in gates]))
    press, was = _sets(wg, USE_PRESSED_VAR), _sets(wg, USE_WAS_VAR)
    check(f"{USE_PRESSED_VAR} is {USING_VAR} AND NOT {USE_WAS_VAR}, written before "
          f"{USE_WAS_VAR} takes this frame's {USING_VAR}",
          len(press) == 1 and len(was) == 1
          and {f"Get {USING_VAR}", f"Get {USE_WAS_VAR}"}
          <= _names(_feeds(BEL.find_input_pin(press[0], USE_PRESSED_VAR)))
          and _ran_by(was[0]) == press
          and [_title(f) for f in _feeders(was[0], USE_WAS_VAR)] == [f"Get {USING_VAR}"],
          f"{len(press)} press, {len(was)} was")
    aims = [n for n in _sets(wg, "SightAiming") if _feeders(n, "SightAiming")]
    marks = [n for n in _sets(wg, "Aiming") if _feeders(n, "Aiming")]
    check(f"the key that uses does not aim: Aiming and SightAiming both read {USING_VAR}",
          len(aims) == 1 and len(marks) == 1
          and all(f"Get {USING_VAR}" in _names(_feeds(BEL.find_input_pin(n, v)))
                  for n, v in ((aims[0], "SightAiming"), (marks[0], "Aiming"))),
          f"{len(aims)} SightAiming, {len(marks)} Aiming")
    polls = [n for n in wg if "IsInputKeyDown" in _title(n).replace(" ", "")
             and [_title(f) for f in _feeders(n, "Key")] == ["Get KeySights"]]
    check("...and the key is polled once, for both", len(polls) == 1, str(len(polls)))


def _served_ward(node):
    """A write of FireWard behind the Branch on AskUse: the server's."""
    cur = [node]
    for _ in range(2):
        cur = [PIN.get_owning_node(q) for c in cur
               for q in PIN.list_connected_pins(BEL.find_input_pin(c, "execute"))]
        if any(_title(f) == f"Get {AskUse}" for c in cur if _title(c) == "Branch"
               for f in _feeders(c, "Condition")):
            return True
    return False


def check_fire_ward():
    # The keys' writes: the server's for a client's character (holds.py) are
    # verify/strike.py's.
    sets = [n for n in _sets(wg, FIRE_WARD_VAR) if not _served_ward(n)]
    up = [n for n in sets if pin_value(n, FIRE_WARD_VAR) == "true"]
    down = [n for n in sets if _false(n, FIRE_WARD_VAR)]
    check(f"{FIRE_WARD_VAR} is raised in one place and lowered on every other arm",
          len(up) == 1 and len(down) == 2 and len(sets) == 3,
          f"{len(up)} true, {len(down)} false of {len(sets)}")
    if len(up) != 1:
        return None
    lit = _ran_by(up[0])
    using = _ran_by(lit[0]) if len(lit) == 1 else []
    check(f"...raised while {USING_VAR}, behind a second Branch on Held.{LIT_VAR} "
          "(nested: Held is read only where the key says it is valid)",
          len(lit) == 1 and len(using) == 1
          and [_title(f) for f in _feeders(lit[0], "Condition")] == [f"Get {LIT_VAR}"]
          and [_title(f) for f in _feeders(using[0], "Condition")] == [f"Get {USING_VAR}"],
          str([_title(f) for g in lit for f in _feeders(g, "Condition")]))
    return lit[0] if len(lit) == 1 else None


def check_light_at_fire():
    lights = _sets(wg, LIT_VAR)
    check("the stick is lit in one place", len(lights) == 1
          and pin_value(lights[0], LIT_VAR) == "true", str(len(lights)))
    if len(lights) != 1:
        return
    burns = _ran_by(lights[0])
    check(f"...after {BURN_OUT_VAR} is set {STICK_BURN_S:g} s on from now",
          len(burns) == 1 and _title(burns[0]) == f"Set {BURN_OUT_VAR}"
          and any(num_pin(f, "B") == STICK_BURN_S
                  and any("GetTimeSeconds" in _title(g).replace(" ", "")
                          for g in _feeders(f, "A"))
                  for f in _feeders(burns[0], BURN_OUT_VAR)),
          str([_title(n) for n in burns]))
    found = [g for b in burns for g in _ran_by(b)]
    check(f"...only if the press found a campfire ({NEAR_FIRE_VAR})",
          len(found) == 1
          and [_title(f) for f in _feeders(found[0], "Condition")] == [f"Get {NEAR_FIRE_VAR}"],
          str([_title(n) for n in found]))
    marks = _sets(wg, NEAR_FIRE_VAR)
    forget = [n for n in marks if _false(n, NEAR_FIRE_VAR)]
    keep = [n for n in marks if pin_value(n, NEAR_FIRE_VAR) == "true"]
    check(f"{NEAR_FIRE_VAR} is forgotten, then set by a walk that only remembers",
          len(marks) == 2 and len(forget) == 1 and len(keep) == 1, str(len(marks)))
    if len(forget) != 1 or len(keep) != 1:
        return
    tests = _ran_by(keep[0])
    src = _pure_feeds(tests[0]) if len(tests) == 1 else []
    # The stick's own walk of the fires: the interact key has another, for
    # heating a blade (verify/heat.py).
    walks = [n for n in by_pins(wg, "ActorClass")
             if [_title(f) for f in _feeders(n, "ActorClass")] == [f"Get {CAMPFIRE_CLASS_VAR}"]
             and _ran_by(n) == forget]
    check(f"...over every {CAMPFIRE_CLASS_VAR} actor, kept if within "
          f"{STICK_LIGHT_RADIUS_CM:g} cm of the player",
          len(walks) == 1 and _ran_by(walks[0]) == forget
          and any(num_pin(n, "B") == STICK_LIGHT_RADIUS_CM for n in src)
          and any("GetOwner" in _title(n).replace(" ", "") for n in src),
          f"{len(walks)} walk(s), {sorted(_names(src))}")
    press = _ran_by(forget[0])
    names = (_names(_feeds(BEL.find_input_pin(press[0], "Condition")))
             if len(press) == 1 else set())
    check(f"...started by a press ({USE_PRESSED_VAR}) with an item that {BURNS_VAR} in "
          "hand, not burning yet",
          names == {f"Get {USE_PRESSED_VAR}", f"Get {BURNS_VAR}", "Get Held", "AND"}
          or {f"Get {USE_PRESSED_VAR}", f"Get {BURNS_VAR}"} <= names, str(sorted(names)))


def check_raised_pose():
    swaps = _sets(wg, "AimPose")
    by_src = {tuple(sorted(_title(f) for f in _feeders(n, "AimPose"))): n for n in swaps}
    up, back = by_src.get((f"Get {USE_POSE_VAR}",)), by_src.get((f"Get {WARD_CARRY_VAR}",))
    check(f"an item's AimPose is written twice: its {USE_POSE_VAR} when the fire goes "
          f"out in front, {WARD_CARRY_VAR} when it comes back",
          len(swaps) == 2 and up is not None and back is not None, str(sorted(by_src)))
    if up is None or back is None:
        return
    check(f"...raised on Held, lowered on {WARD_ITEM_VAR} (the stick that was raised, "
          "which may no longer be in hand)",
          [_title(f) for f in _feeders(up, "self")] == ["Get Held"]
          and [_title(f) for f in _feeders(back, "self")] == [f"Get {WARD_ITEM_VAR}"],
          f"{[_title(f) for f in _feeders(up, 'self')]} "
          f"{[_title(f) for f in _feeders(back, 'self')]}")
    kept = [n for n in _sets(wg, WARD_CARRY_VAR)
            if any("AimPose" in _title(f) for f in _feeders(n, WARD_CARRY_VAR))]
    check(f"...the carry pose kept in {WARD_CARRY_VAR} before the swap overwrites it",
          len(kept) == 1 and _ran_by(up) == kept, str(len(kept)))
    raise_, lower = _gate_of(up), _gate_of(back)
    r_src = _names(_pure_feeds(raise_)) if raise_ else set()
    l_src = _names(_pure_feeds(lower)) if lower else set()
    check(f"...raised when {FIRE_WARD_VAR} is up and no stick is raised; lowered when "
          f"one is and {FIRE_WARD_VAR} is down or the hand holds another",
          {f"Get {FIRE_WARD_VAR}", f"Get {WARD_ITEM_VAR}"} <= r_src
          and {f"Get {FIRE_WARD_VAR}", f"Get {WARD_ITEM_VAR}", "Get Held"} <= l_src,
          f"raise {sorted(r_src)} lower {sorted(l_src)}")
    after = {name: _reach(n) for name, n in (("raise", up), ("lower", back))}
    check("...and each change re-equips (NeedsRefresh), which blends the arm",
          all(any(_title(n) == "Set NeedsRefresh" and pin_value(n, "NeedsRefresh") == "true"
                  for n in nodes) for nodes in after.values()),
          str({k: len(v) for k, v in after.items()}))
    check("...the lowering tested first, so a swap to another lit stick does both on "
          "one frame", lower is not None and raise_ is not None
          and raise_ in _reach(lower, 8), "")


def _gate_of(node):
    """The first Branch up the exec chain from ``node``."""
    seen = 0
    while node is not None and seen < 8:
        ran = _ran_by(node)
        node = ran[0] if ran else None
        if node is not None and _title(node) == "Branch":
            return node
        seen += 1
    return None


def _reach(node, limit=4):
    """The nodes down ``node``'s exec outputs, a few steps."""
    out, frontier = [], [node]
    for _ in range(limit):
        nxt = []
        for n in frontier:
            for pin in BEL.list_output_pins(n):
                if _is_exec(pin):
                    nxt += [PIN.get_owning_node(q) for q in PIN.list_connected_pins(pin)]
        out += nxt
        frontier = nxt
    return out


def run():
    check_stick_item()
    check_stick_burn()
    check_torch_poses()
    check_stick_loadout()
    check_use_key()
    check_fire_ward()
    check_light_at_fire()
    check_raised_pose()
