"""verify.sights -- the two ways of aiming (shoulder and down the sights), each
weapon's eye point and sight line, and the camera that travels from the boom
to the one and turns onto the other.
"""

import unreal

from combat.nodes import SPRING_ARM_SOCKET
from combat.paths import (
    AXE_BP_PATH, CYLINDER, ITEM_BP_PATH, KNIFE_BP_PATH, MATCHES_BP_PATH,
    WOOD_BP_PATH,
)
from combat.seat_tuning import (
    HAS_SIGHTS_VAR, SEAT_HOLD, SEAT_VAR, SEATED_VAR, SIGHT_SEAT_COS,
    SIGHT_SEAT_DEG, SIGHTS_FORCED_VAR,
)
from combat.tuning import BIND_VARS, COMBAT, SIGHTS_KEY
from combat.weapon_component.sights import SCOPE_HIDE_BLEND, SIGHT_LINE_MIN_CM
from combat.weapon_specs import _weapon_specs
from combat.verify.fixtures import char, w, wg
from combat.verify.common import (
    BEL, PIN, cdo, check, component_template, components, in_pins, load,
    num_pin, out_pins, pin_value,
)

NEAR_CLIP_CM = 10.0      # the engine's default near plane


def _title(n):
    return str(BEL.get_node_title(n)).replace("\n", " ")


def _feeds(pin, limit=250):
    """Every node feeding this pin through DATA links only."""
    seen, stack = set(), [pin]
    while stack and len(seen) < limit:
        for q in PIN.list_connected_pins(stack.pop()):
            node = PIN.get_owning_node(q)
            if node in seen:
                continue
            seen.add(node)
            stack.extend(x for x in BEL.list_input_pins(node)
                         if str(PIN.get_pin_name(x)) != "execute")
    return seen


def _part_box(part):
    """(min, max) corners of a part in weapon space, ignoring small tilts.

    A cylinder is 100 cm along its own Z with a 50 cm radius; the barrel
    rotation lays that axis along +X, and nothing else here is a cylinder that
    the sight line could pass through.
    """
    _name, mesh, loc, rot, scale, _mat = part
    if mesh == CYLINDER and abs(abs(rot.pitch) - 90.0) < 1.0:
        half = (scale[2] * 50.0, scale[0] * 50.0, scale[1] * 50.0)
    else:
        half = (scale[0] * 50.0, scale[1] * 50.0, scale[2] * 50.0)
    return (tuple(c - h for c, h in zip(loc, half)),
            tuple(c + h for c, h in zip(loc, half)))


def check_two_aim_keys():
    # Two actions, two binds, and both held rather than tapped.
    check(f"aiming down the sights is its own bind, {SIGHTS_KEY} by default, "
          f"next to the shoulder aim",
          [v for v, _k in BIND_VARS][1:3] == ["KeyAim", "KeySights"]
          and w.get_editor_property("KeySights").export_text() == SIGHTS_KEY,
          str([v for v, _k in BIND_VARS]))

    writes = {v: [n for n in wg if v in in_pins(n) and _title(n) == f"Set {v}"]
              for v in ("Aiming", "SightAiming", "AimZoom")}
    if len(writes["Aiming"]) == 1:
        src = {_title(n) for n in _feeds(BEL.find_input_pin(writes["Aiming"][0],
                                                            "Aiming"))}
        check("Aiming is either key: the cone and the recoil are earned by both",
              {"Get KeyAim", "Get KeySights"} <= src, str(sorted(src)))
    check("SightAiming is written twice: on the aiming arm, and false on the other",
          len(writes["SightAiming"]) == 2, str(len(writes["SightAiming"])))
    if len(writes["SightAiming"]) == 2:
        fed = [{_title(n) for n in _feeds(BEL.find_input_pin(x, "SightAiming"))}
               for x in writes["SightAiming"]]
        on = [f for f in fed if f]
        off = [x for x in writes["SightAiming"]
               if pin_value(x, "SightAiming") == "false"
               and not PIN.list_connected_pins(BEL.find_input_pin(x, "SightAiming"))]
        check(f"...the one off the sights key alone, and only with a gun in hand "
              f"(Held.{HAS_SIGHTS_VAR})",
              len(on) == 1 and "Get KeySights" in on[0]
              and "Get KeyAim" not in on[0] and f"Get {HAS_SIGHTS_VAR}" in on[0],
              str(sorted(on[0]) if on else fed))
        check(f"...or off {SIGHTS_FORCED_VAR}, the probes' stand-in for that key, "
              "which is False in a real game",
              len(on) == 1 and f"Get {SIGHTS_FORCED_VAR}" in on[0]
              and w.get_editor_property(SIGHTS_FORCED_VAR) is False,
              str(sorted(on[0]) if on else fed))
        check("...the other a literal false", len(off) == 1, str(len(off)))

    check("AimZoom is written once, where Held is valid",
          len(writes["AimZoom"]) == 1, str(len(writes["AimZoom"])))
    if writes["AimZoom"]:
        up = _feeds(BEL.find_input_pin(writes["AimZoom"][0], "AimZoom"))
        picks = [n for n in up if {"A", "B", "bPickA"} <= in_pins(n)]
        check(f"...picking the weapon's AdsZoom down the sights and "
              f"{COMBAT.shoulder_zoom:g}x off the shoulder",
              len(picks) == 1
              and abs((num_pin(picks[0], "B") or 0.0) - COMBAT.shoulder_zoom) < 1e-9
              and any("AdsZoom" in out_pins(n) for n in up)
              and any("SightAiming" in out_pins(n) or "Output_Get" in out_pins(n)
                      for n in up),
              str(sorted(_title(n) for n in up)))
        check(f"...the weapon's only once the camera may go onto the gun "
              f"({SEATED_VAR}), so the scope's zoom and glass arrive with it",
              len(picks) == 1 and f"Get {SEATED_VAR}" in {
                  _title(n) for n in _feeds(BEL.find_input_pin(picks[0], "bPickA"))},
              str(sorted(_title(n) for n in up)))
    got = w.get_editor_property("AimZoom")
    check("AimZoom starts at the shoulder's zoom, so (AimZoom - 1) is never zero",
          isinstance(got, float) and abs(got - COMBAT.shoulder_zoom) < 1e-9
          and COMBAT.shoulder_zoom > 1.0, repr(got))
    check("the shoulder aim zooms like the old aim did on every gun but the "
          "sniper", abs(COMBAT.shoulder_zoom - COMBAT.ads_zoom_irons) < 1e-9)


def _blocks(box, eye, front, slack=0.1):
    """Does the sight line, eye to front sight, pass through this box? `slack`
    (cm) off its top: an outline box is the part's extent to the millimetre,
    and the sights themselves top out ON the line."""
    lo, hi = box
    if not lo[1] < eye[1] < hi[1]:
        return False
    x0, x1 = max(lo[0], eye[0]), min(hi[0], front[0])
    if x0 >= x1:
        return False
    rise = (front[2] - eye[2]) / (front[0] - eye[0])
    z0, z1 = sorted(eye[2] + (x - eye[0]) * rise for x in (x0, x1))
    return z0 < hi[2] - slack and z1 > lo[2]


def check_only_guns_have_sights():
    # The sights key takes the camera onto the item only where the item says
    # it has sights. The guns' rows say so; the base class does not, so the
    # knife, the axe, the matches, wood, food and anything added later don't.
    for sp in _weapon_specs():
        got = cdo(load(sp["path"])).get_editor_property(HAS_SIGHTS_VAR)
        check(f"{sp['display']}: a gun, so it has sights to aim down "
              f"({HAS_SIGHTS_VAR})", got is True, str(got))
    for what, path in (("the base item (so food, and any new item)", ITEM_BP_PATH),
                       ("the knife", KNIFE_BP_PATH), ("the axe", AXE_BP_PATH),
                       ("the matches", MATCHES_BP_PATH), ("wood", WOOD_BP_PATH)):
        got = cdo(load(path)).get_editor_property(HAS_SIGHTS_VAR)
        check(f"{what} has no sights: the sights key aims it over the shoulder",
              got is False, str(got))


def check_eye_points():
    # Where the camera goes, per weapon, and what it looks at. The eye, the
    # rear sight and the front sight's tip are one line, so the view from the
    # eye towards the tip runs down the sights. A box on that line would put
    # the gun in front of its own sights; a part within the near clip of the
    # eye would be cut open. The sniper looks through its scope, so that one
    # part is exempt and the line is its axis.
    for sp in _weapon_specs():
        d = cdo(load(sp["path"]))
        for var, key, what in (("SightOffset", "sight", "the eye"),
                               ("SightAim", "sight_front", "the front sight's tip")):
            got = d.get_editor_property(var)
            want = unreal.Vector(*sp[key])
            check(f"{sp['display']}: {var} is {what}, "
                  f"({', '.join(f'{v:.2f}' for v in sp[key])})",
                  got is not None and (got - want).length() < 1e-4,
                  str(got.to_tuple()) if got is not None else "None")
        eye, rear, front = sp["sight"], sp["sight_rear"], sp["sight_front"]
        ex, ey, ez = eye
        check(f"{sp['display']}: the eye is behind the muzzle and above the bore",
              ex < sp["muzzle"][0] and ez > sp["muzzle"][2] and abs(ey) < 1e-6,
              f"eye {eye} muzzle {sp['muzzle']}")
        to_rear = unreal.Vector(*rear) - unreal.Vector(*eye)
        to_front = unreal.Vector(*front) - unreal.Vector(*eye)
        check(f"{sp['display']}: the eye, the rear sight and the front sight's tip "
              f"are one line, the eye {rear[0] - ex:.1f} cm behind the rear sight",
              to_rear.cross(to_front).length() < 1e-6 * to_front.length()
              and ex < rear[0] < front[0],
              f"eye {eye} rear {rear} front {front}")
        boxes = [(p[0], _part_box(p)) for p in sp["parts"] if p[0] != "Scope"]
        blocked = [name for name, box in boxes if _blocks(box, eye, front)]
        check(f"{sp['display']}: nothing stands on the sight line; the sights top "
              f"out on it", not blocked, str(blocked))
        # Parts ahead of the eye and near the line (top within 5 cm under it);
        # the grip, the magazine and a stock under the cheek are far enough
        # below it to be outside the view.
        under = [(name, lo[0]) for name, (lo, hi) in boxes
                 if lo[1] <= ey <= hi[1] and hi[2] >= ez - 5.0
                 and ex < lo[0] < ex + NEAR_CLIP_CM]
        check(f"{sp['display']}: no part starts within the near clip "
              f"({NEAR_CLIP_CM:g} cm) ahead of the eye",
              not under, str(under))
        tips = [hi[2] for name, (lo, hi) in boxes
                if lo[0] <= front[0] <= hi[0] and lo[1] < front[1] < hi[1]]
        if not sp.get("scoped"):
            check(f"{sp['display']}: the front sight's tip is the top of the gun "
                  f"there, not a point in the air",
                  bool(tips) and abs(max(tips) - front[2]) < 0.05,
                  f"tip {front[2]} gun {max(tips) if tips else None}")
        scope = [p for p in sp["parts"] if p[0] == "Scope"]
        if sp.get("scoped"):
            lo, hi = _part_box(scope[0]) if scope else ((0, 0, 0), (0, 0, 0))
            check(f"{sp['display']}: the eye is on the scope's axis, behind "
                  f"its eyepiece",
                  bool(scope) and abs(ez - scope[0][2][2]) < 1e-6
                  and abs(ey - scope[0][2][1]) < 1e-6
                  and NEAR_CLIP_CM <= lo[0] - ex,
                  f"eye {sp['sight']} scope {lo}..{hi}")


def check_sight_camera():
    blend_writes = [n for n in wg if _title(n) == "Set SightBlend"]
    check("SightBlend is written once, eased toward SightAiming",
          len(blend_writes) == 1, str(len(blend_writes)))
    if blend_writes:
        up = {_title(n) for n in _feeds(BEL.find_input_pin(blend_writes[0],
                                                           "SightBlend"))}
        check("...by an FInterpTo off the SightAiming flag, at the zoom's speed",
              "Get SightAiming" in up and "Get SightBlend" in up
              and any("FInterp" in t.replace(" ", "") for t in up),
              str(sorted(up)))
        held = [n for n in _feeds(BEL.find_input_pin(blend_writes[0], "SightBlend"))
                if num_pin(n, "B") == SEAT_HOLD and "A" in in_pins(n)
                and f"Get {SEAT_VAR}" in {
                    _title(m) for m in _feeds(BEL.find_input_pin(n, "A"), 2)}]
        check(f"...or held up by the camera still on the gun ({SEAT_VAR} > "
              f"{SEAT_HOLD:g}): the body keeps the aim until the view is home",
              len(held) == 1, str(len(held)))

    moves = [n for n in wg
             if "setworldlocation" in _title(n).replace(" ", "").lower()]
    check("the camera is placed twice: down the sights, and home with empty "
          "hands", len(moves) == 2, str(len(moves)))
    fed = [_feeds(BEL.find_input_pin(n, "NewLocation")) for n in moves]
    sight = [f for f in fed if any("SightOffset" in out_pins(n) for n in f)]
    mixes = [n for f in sight for n in f if {"A", "B", "Alpha"} <= in_pins(n)]
    check(f"...one between the boom's end and the held weapon's SightOffset, by "
          f"{SEAT_VAR}",
          len(sight) == 1 and len(mixes) == 1
          and f"Set {SEAT_VAR}" in {
              _title(n) for n in _feeds(BEL.find_input_pin(mixes[0], "Alpha"))},
          str(len(sight)))
    sockets = [n for n in wg if "InSocketName" in in_pins(n)]
    at = [n for n in sockets if "location" in _title(n).lower()]
    check(f"...both measured from the boom's {SPRING_ARM_SOCKET} socket",
          len(at) == 1 and pin_value(at[0], "InSocketName") == SPRING_ARM_SOCKET
          and all(at[0] in f for f in fed),
          str([pin_value(n, "InSocketName") for n in sockets]))
    check_sight_look(sockets, moves)
    check_sight_seat()

    hides = [n for n in wg if "bNewHidden" in in_pins(n)]
    tucked = [n for n in hides if PIN.list_connected_pins(BEL.find_input_pin(n, "bNewHidden"))]
    up = {_title(n) for n in _feeds(BEL.find_input_pin(tucked[0], "bNewHidden"))} if tucked else set()
    check(f"a scoped weapon hides past {SEAT_VAR} {SCOPE_HIDE_BLEND:g}, out of its "
          f"own scope's way -- and only a scoped one",
          len(tucked) == 1 and "Get Scoped" in up and f"Set {SEAT_VAR}" in up
          and any(abs((num_pin(n, "B") or 0.0) - SCOPE_HIDE_BLEND) < 1e-9
                  for n in _feeds(BEL.find_input_pin(tucked[0], "bNewHidden"))),
          str(sorted(up)))
    no_see = [n for n in wg if "bNewOwnerNoSee" in in_pins(n)]
    fed = [n for n in no_see
           if PIN.list_connected_pins(BEL.find_input_pin(n, "bNewOwnerNoSee"))]
    def _src(n, pin):
        return [PIN.get_owning_node(q)
                for q in PIN.list_connected_pins(BEL.find_input_pin(n, pin))]
    same = fed and tucked and _src(fed[0], "bNewOwnerNoSee") == _src(tucked[0], "bNewHidden")
    body = fed and {_title(PIN.get_owning_node(q))
                    for q in PIN.list_connected_pins(BEL.find_input_pin(fed[0], "self"))}
    check("...and the player's own body with it, hidden from its own camera "
          "(OwnerNoSee) on the same condition, so the arms' animation stays "
          "out of the glass",
          len(fed) == 1 and bool(same) and body == {"Get OwnerMesh"}, str(body))
    check("...and the body is shown again with empty hands, when the camera "
          "goes home",
          len(no_see) == 2 and any(pin_value(n, "bNewOwnerNoSee") == "false"
                                   for n in no_see if n not in fed),
          str(len(no_see)))
    detaches = [n for n in wg if "detachfromactor" in _title(n).replace(" ", "").lower()]
    unhide = [PIN.get_owning_node(q) for d in detaches
              for q in PIN.list_connected_pins(BEL.find_then_pin(d))]
    check("...and a dropped weapon is shown on its way out of the hand, so one "
          "dropped while scoped is not left invisible on the ground",
          any("bNewHidden" in in_pins(n) and pin_value(n, "bNewHidden") == "false"
              for n in unhide),
          str([_title(n) for n in unhide]))

    prereq = [n for n in wg if "PrerequisiteComponent" in in_pins(n)]
    check("the weapon component ticks after the camera boom, so the sight "
          "camera is not a frame behind it",
          len(prereq) == 1 and any(
              "SpringArm" in pin_value(PIN.get_owning_node(q), "ComponentClass")
              for q in PIN.list_connected_pins(
                  BEL.find_input_pin(prereq[0], "PrerequisiteComponent"))),
          str(len(prereq)))

    cams = [c for c in (component_template(char, n) for n in components(char))
            if isinstance(c, unreal.CameraComponent)]
    check(f"the camera sits on the boom's end with no offset, so {SEAT_VAR} 0 "
          "is exactly where the boom holds it",
          len({id(c) for c in cams}) >= 1 and all(
              c.get_editor_property("relative_location").length() < 1e-3
              for c in cams),
          str([c.get_editor_property("relative_location").to_tuple() for c in cams]))
    turns = [c.get_editor_property("relative_rotation") for c in cams]
    check("...and turned only by the boom (no turn of its own, and not taking "
          "the control rotation itself), so the sights can turn it onto the gun",
          bool(cams) and all(max(abs(r.pitch), abs(r.yaw), abs(r.roll)) < 1e-3
                             for r in turns)
          and not any(c.get_editor_property("use_pawn_control_rotation") for c in cams),
          str([(r.pitch, r.yaw, r.roll) for r in turns]))


def check_sight_look(sockets, moves):
    """The camera's rotation: onto the held weapon's sight line by SightSeat,
    and the boom's again with empty hands."""
    turns = [n for n in wg
             if "setworldrotation" in _title(n).replace(" ", "").lower()]
    check("the camera is turned twice: down the sights, and level with the "
          "boom with empty hands", len(turns) == 2, str(len(turns)))
    check("...and never by a whole transform",
          not [n for n in wg
               if "setworldtransform" in _title(n).replace(" ", "").lower()])
    fed = [_feeds(BEL.find_input_pin(n, "NewRotation")) for n in turns]
    look = [f for f in fed if any("SightAim" in out_pins(n) for n in f)]
    check("...one onto the line from the weapon's SightOffset to its SightAim, "
          "the front sight's tip, so the tip is the middle of the view",
          len(look) == 1
          and any("SightOffset" in out_pins(n) for n in look[0])
          and any("makerotfromx" in _title(n).replace(" ", "").lower()
                  for n in look[0]),
          str(len(look)))
    lerps = [n for f in look for n in f
             if {"A", "B", "Alpha", "bShortestPath"} <= in_pins(n)]
    check(f"...eased from the boom's rotation by {SEAT_VAR}, the short way round",
          len(lerps) == 1 and pin_value(lerps[0], "bShortestPath") == "true"
          and f"Set {SEAT_VAR}" in {
              _title(n) for n in _feeds(BEL.find_input_pin(lerps[0], "Alpha"))},
          str(len(lerps)))
    gates = [n for f in look for n in f
             if abs((num_pin(n, "B") or 0.0) - SIGHT_LINE_MIN_CM) < 1e-9
             and "A" in in_pins(n) and len(in_pins(n)) == 2]
    check(f"...and only for an item with a sight line (longer than "
          f"{SIGHT_LINE_MIN_CM:g} cm): the knife keeps the boom's view",
          bool(gates) and bool(lerps)
          and any(g in _feeds(BEL.find_input_pin(lerps[0], "Alpha")) for g in gates),
          str(len(gates)))
    rot = [n for n in sockets if "rotation" in _title(n).lower()]
    check(f"...both from the boom's {SPRING_ARM_SOCKET} socket's rotation, "
          f"which is the control rotation",
          len(rot) == 1 and pin_value(rot[0], "InSocketName") == SPRING_ARM_SOCKET
          and all(rot[0] in f for f in fed),
          str([_title(n) for n in sockets]))
    placed = [n for n in moves
              if any(PIN.get_owning_node(q) in turns
                     for q in PIN.list_connected_pins(BEL.find_then_pin(n)))]
    check("...each straight after the camera is placed, in the same frame",
          len(placed) == 2, str(len(placed)))


def check_sight_seat():
    """The camera waits on the boom until the gun is up (weapon_component/
    seat.py): SightSeated latches on the gun's sight line coming near the
    view, and SightSeat, which places the camera, eases toward it."""
    def writes(var):
        sets = [n for n in wg if _title(n) == f"Set {var}"]
        wired = [n for n in sets
                 if PIN.list_connected_pins(BEL.find_input_pin(n, var))]
        return sets, wired

    latches, wired = writes(SEATED_VAR)
    check(f"{SEATED_VAR} is written twice by the living Tick: armed, and false "
          f"with empty hands",
          len(latches) == 2 and len(wired) == 1
          and all(pin_value(n, SEATED_VAR) == "false"
                  for n in latches if n not in wired),
          f"{len(latches)} writes, {len(wired)} wired")
    fed = _feeds(BEL.find_input_pin(wired[0], SEATED_VAR)) if wired else set()
    names = {_title(n) for n in fed}
    check("...armed, it is the sights held AND (already seated OR the gun up): "
          "a latch, so a reload with the sights up keeps the camera on the gun",
          {"Get SightAiming", f"Get {SEATED_VAR}"} <= names, str(sorted(names)))
    near = [n for n in fed
            if abs((num_pin(n, "B") or 0.0) - SIGHT_SEAT_COS) < 1e-5
            and "A" in in_pins(n) and len(in_pins(n)) == 2]
    behind = ({_title(n) for n in _feeds(BEL.find_input_pin(near[0], "A"))}
              if near else set())
    check(f"...the gun is up when its sight line is within {SIGHT_SEAT_DEG:g} deg "
          f"of the view: the line's direction dotted with the boom's (the "
          f"control rotation's) forward, against cos",
          len(near) == 1 and "Get SightAim" in behind and "Get SightOffset" in behind
          and any("dot" in t.lower() for t in behind)
          and any("InSocketName" in in_pins(n)
                  for n in _feeds(BEL.find_input_pin(near[0], "A"))),
          str(sorted(behind)))
    gates = [n for n in fed
             if abs((num_pin(n, "B") or 0.0) - SIGHT_LINE_MIN_CM) < 1e-9
             and "A" in in_pins(n) and len(in_pins(n)) == 2]
    check("...and an item with no sight line is seated at once: there is no "
          "line to wait for", len(gates) == 1, str(len(gates)))

    seats, wired = writes(SEAT_VAR)
    check(f"{SEAT_VAR} is written twice by the living Tick: armed, and zero "
          f"with empty hands",
          len(seats) == 2 and len(wired) == 1
          and all((num_pin(n, SEAT_VAR) or 0.0) == 0.0
                  for n in seats if n not in wired),
          f"{len(seats)} writes, {len(wired)} wired")
    fed = _feeds(BEL.find_input_pin(wired[0], SEAT_VAR)) if wired else set()
    names = {_title(n) for n in fed}
    eases = [n for n in fed if {"Current", "Target", "InterpSpeed"} <= in_pins(n)]
    check(f"...eased toward {SEATED_VAR} by an FInterpTo at the zoom's speed "
          f"({COMBAT.ads_interp_speed:g}), so the camera travels rather than cuts",
          len(eases) == 1 and {f"Get {SEAT_VAR}", f"Set {SEATED_VAR}"} <= names
          and abs((num_pin(eases[0], "InterpSpeed") or 0.0)
                  - COMBAT.ads_interp_speed) < 1e-9,
          str(sorted(names)))
    got = (w.get_editor_property(SEATED_VAR), w.get_editor_property(SEAT_VAR))
    check("...and both start clear: the camera begins on the boom",
          got[0] is False and isinstance(got[1], float) and got[1] == 0.0, repr(got))


def run():
    check_two_aim_keys()
    check_only_guns_have_sights()
    check_eye_points()
    check_sight_camera()
