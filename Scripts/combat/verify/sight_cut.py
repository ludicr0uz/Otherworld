"""verify.sight_cut -- the cut to the sights keeps the point aimed at
(weapon_component/sight_cut.py): ads.py writes SightCut on the cut's frame
alone, aim.py keeps the camera trace's point as ViewPoint, and on SightCut
the control rotation turns onto it from the anchor, the camera taking that
rotation on the same frame. probes/probe_sight_cut_aim.py measures it.
"""

from combat.weapon_component import vars as WV
from combat.verify.fixtures import wg
from combat.verify.common import BEL, PIN, check, in_pins
from combat.verify.sights import _feeds, _title


def _sets(var):
    return [n for n in wg if _title(n).startswith("Set") and _title(n).endswith(f" {var}")]


def check_cut_written():
    """SightCut: the cut AND NOT last frame's SightSnapped, written just
    before SightSnapped; cleared off the sights."""
    cuts = _sets(WV.SightCut)
    fed = [{_title(n) for n in _feeds(BEL.find_input_pin(c, str(WV.SightCut)))}
           for c in cuts]
    first = [c for c, f in zip(cuts, fed) if "Get SightSnapped" in f
             and any("not" in t.lower() for t in f)]
    before = [c for c in first if any(
        _title(PIN.get_owning_node(q)) == f"Set {WV.SightSnapped}"
        for q in PIN.list_connected_pins(BEL.find_then_pin(c)))]
    check("SightCut is written twice: on the cut's frame alone (the cut AND NOT "
          "last frame's SightSnapped, just before SightSnapped is written), and "
          "false off the sights",
          len(cuts) == 2 and len(first) == 1 and len(before) == 1,
          f"{len(cuts)} writes, {len(first)} off SightSnapped, {len(before)} before it")
    views = _sets(WV.ViewPoint)
    check("ViewPoint is the camera trace's point, kept before the muzzle's "
          "trace can move AimPoint",
          len(views) == 1 and "Get AimPoint" in {
              _title(n) for n in _feeds(BEL.find_input_pin(views[0], str(WV.ViewPoint)))},
          str(len(views)))


def _turns():
    return [n for n in wg if "setcontrolrotation" in _title(n).replace(" ", "").lower()]


def cut_turns():
    """The SetControlRotation nodes that turn the view onto ViewPoint (the
    cut's: a write with no read back, which verify.firing leaves out of its
    count of the kick's, the recovery's and the sway's)."""
    return [n for n in _turns()
            if {"Get ViewPoint", "Get SightAnchor"}
            <= {_title(m) for m in _feeds(BEL.find_input_pin(n, "NewRotation"))}]


def check_cut_turn():
    """On SightCut the control rotation turns from the anchor onto ViewPoint,
    and the camera's rotation takes it on that frame."""
    turns = _turns()
    onto = cut_turns()
    gated = [n for n in onto if any(
        "Get SightCut" in {_title(m) for m in _feeds(
            BEL.find_input_pin(PIN.get_owning_node(q), "Condition"))}
        for q in PIN.list_connected_pins(BEL.find_input_pin(n, "execute"))
        if "Condition" in in_pins(PIN.get_owning_node(q)))]
    check("on the cut's frame (a Branch on SightCut) the control rotation turns "
          "from the anchor (SightAnchor) onto ViewPoint, so what was under the "
          "crosshair stays there",
          len(onto) == 1 and len(gated) == 1, f"{len(turns)} turns, {len(onto)} onto it")
    picks = [n for n in wg if {"A", "B", "bPickA"} <= in_pins(n)
             and "Get ViewPoint" in {_title(m) for m in _feeds(BEL.find_input_pin(n, "A"))}]
    cams = [n for n in wg if "setworldrotation" in _title(n).replace(" ", "").lower()
            and any(p in _feeds(BEL.find_input_pin(n, "NewRotation")) for p in picks)]
    check("...and the camera takes that rotation on the same frame (the boom "
          "has ticked with the old one), the boom's on every other",
          len(picks) == 1 and len(cams) == 1, f"{len(picks)} picks, {len(cams)} cameras")


def run():
    check_cut_written()
    check_cut_turn()
