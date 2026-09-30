"""verify.sights -- the two ways of aiming (shoulder and down the sights), each
weapon's eye point, and the camera that travels from the boom to it.
"""

import unreal

from combat.nodes import SPRING_ARM_SOCKET
from combat.paths import CYLINDER
from combat.tuning import BIND_VARS, COMBAT, SIGHTS_KEY
from combat.weapon_component.sights import SCOPE_HIDE_BLEND
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
        check("...the one off the sights key alone, and never with food in hand",
              len(on) == 1 and "Get KeySights" in on[0]
              and "Get KeyAim" not in on[0] and "Get Consumable" in on[0],
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
    got = w.get_editor_property("AimZoom")
    check("AimZoom starts at the shoulder's zoom, so (AimZoom - 1) is never zero",
          isinstance(got, float) and abs(got - COMBAT.shoulder_zoom) < 1e-9
          and COMBAT.shoulder_zoom > 1.0, repr(got))
    check("the shoulder aim zooms like the old aim did on every gun but the "
          "sniper", abs(COMBAT.shoulder_zoom - COMBAT.ads_zoom_irons) < 1e-9)


def check_eye_points():
    # Where the camera goes, per weapon. A point inside a part would put the
    # camera inside the gun; a point within the near clip of a part would cut
    # it open; a point well above the gun would show sky where the gun should
    # be. The sniper looks through its scope, so that one part is exempt and
    # the eye must be on its axis instead.
    for sp in _weapon_specs():
        got = cdo(load(sp["path"])).get_editor_property("SightOffset")
        want = unreal.Vector(*sp["sight"])
        check(f"{sp['display']}: SightOffset is {sp['sight']}",
              got is not None and (got - want).length() < 1e-4,
              str(got.to_tuple()) if got is not None else "None")
        ex, ey, ez = sp["sight"]
        check(f"{sp['display']}: the eye is behind the muzzle and above the bore",
              ex < sp["muzzle"][0] and ez > sp["muzzle"][2] and abs(ey) < 1e-6,
              f"eye {sp['sight']} muzzle {sp['muzzle']}")
        boxes = [(p[0], _part_box(p)) for p in sp["parts"] if p[0] != "Scope"]
        blocked = [name for name, (lo, hi) in boxes
                   if lo[1] <= ey <= hi[1] and lo[2] <= ez <= hi[2]
                   and hi[0] >= ex]
        check(f"{sp['display']}: nothing on the sight line from the eye forward",
              not blocked, str(blocked))
        # Parts ahead of the eye and near the line (top within 5 cm under it);
        # the grip, the magazine and a stock under the cheek are far enough
        # below it to be outside the view.
        under = [(name, lo[0]) for name, (lo, hi) in boxes
                 if lo[1] <= ey <= hi[1] and hi[2] >= ez - 5.0
                 and ex < lo[0] < ex + NEAR_CLIP_CM]
        check(f"{sp['display']}: no part starts within the near clip "
              f"({NEAR_CLIP_CM:g} cm) ahead of the eye",
              not under, str(under))
        tops = [hi[2] for _n, (lo, hi) in boxes
                if lo[1] <= ey <= hi[1] and hi[0] >= ex]
        rise = ez - max(tops) if tops else None
        check(f"{sp['display']}: the eye skims the top of the gun (0.5-3 cm "
              f"over it), so the gun is what the bottom of the view shows",
              rise is not None and 0.5 <= rise <= 3.0, f"{rise}")
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

    moves = [n for n in wg
             if "setworldlocation" in _title(n).replace(" ", "").lower()]
    check("the camera is placed twice: down the sights, and home with empty "
          "hands", len(moves) == 2, str(len(moves)))
    fed = [_feeds(BEL.find_input_pin(n, "NewLocation")) for n in moves]
    sight = [f for f in fed if any("SightOffset" in out_pins(n) for n in f)]
    check("...one between the boom's end and the held weapon's SightOffset, by "
          "SightBlend",
          len(sight) == 1
          and any({"A", "B", "Alpha"} <= in_pins(n) for n in sight[0])
          and any("SightBlend" in out_pins(n) or "Output_Get" in out_pins(n)
                  for n in sight[0]),
          str(len(sight)))
    sockets = [n for n in wg if "InSocketName" in in_pins(n)]
    check(f"...both measured from the boom's {SPRING_ARM_SOCKET} socket",
          len(sockets) == 1 and pin_value(sockets[0], "InSocketName") == SPRING_ARM_SOCKET
          and all(sockets[0] in f for f in fed),
          str([pin_value(n, "InSocketName") for n in sockets]))
    check("...and only the location: the view keeps the boom's rotation, "
          "which is the mouse's",
          not [n for n in wg
               if "setworldrotation" in _title(n).replace(" ", "").lower()
               or "setworldtransform" in _title(n).replace(" ", "").lower()])

    hides = [n for n in wg if "bNewHidden" in in_pins(n)]
    tucked = [n for n in hides if PIN.list_connected_pins(BEL.find_input_pin(n, "bNewHidden"))]
    up = {_title(n) for n in _feeds(BEL.find_input_pin(tucked[0], "bNewHidden"))} if tucked else set()
    check(f"a scoped weapon hides past SightBlend {SCOPE_HIDE_BLEND:g}, out of its "
          f"own scope's way -- and only a scoped one",
          len(tucked) == 1 and "Get Scoped" in up and "Set SightBlend" in up
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
    check("the camera sits on the boom's end with no offset, so SightBlend 0 "
          "is exactly where the boom holds it",
          len({id(c) for c in cams}) >= 1 and all(
              c.get_editor_property("relative_location").length() < 1e-3
              for c in cams),
          str([c.get_editor_property("relative_location").to_tuple() for c in cams]))


def run():
    check_two_aim_keys()
    check_eye_points()
    check_sight_camera()
