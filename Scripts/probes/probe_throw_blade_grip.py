"""The knife cocked to throw is held by its blade: while the throw key is
held (ThrowKeyForced) the knife moves from its hammer grip (GripLocation/
GripRotation) to its ThrowGripLocation/Rotation (knife.knife_throw_grip,
weapon_component/throw_ready.py), and letting the key go puts the hammer grip
back. The axe, which has no throw grip, stays in its own.
"""

import unreal

from combat.paths import WEAPON_COMP_BP_PATH, WEAPON_COMP_CLASS_PATH
from combat.throw_tuning import THROW_GRIP_LOC_VAR, THROW_GRIP_VAR
from combat.weapon_component.throw import THROW_AIMING_VAR, THROW_FORCED_VAR
from combat.weapon_component import vars as WV

WRITABLE = [(WEAPON_COMP_BP_PATH, THROW_FORCED_VAR),
            (WEAPON_COMP_BP_PATH, WV.EquippedIndex),
            (WEAPON_COMP_BP_PATH, WV.NeedsRefresh)]

NEAR_CM = 0.1


def _rel(item):
    """A copy: the struct read back is a view that later reads overwrite."""
    v = item.root_component.get_editor_property("relative_location")
    return unreal.Vector(v.x, v.y, v.z)


def _cocked(p, wc, item):
    """(relative location before, while cocked, after the key is let go)."""
    p.set(wc, "EquippedIndex", list(p.get(wc, "Inventory")).index(item))
    p.set(wc, "NeedsRefresh", True)
    yield lambda: p.get(wc, "Held") == item
    yield 0.1
    before = _rel(item)
    p.set(wc, THROW_FORCED_VAR, True)
    yield lambda: p.get(wc, THROW_AIMING_VAR)
    yield 0.1
    during = _rel(item)
    p.set(wc, THROW_FORCED_VAR, False)
    yield lambda: not p.get(wc, THROW_AIMING_VAR)
    yield 0.2
    return before, during, _rel(item)


def probe(p):
    yield lambda: p.pawn() is not None
    yield 0.3
    wc = p.component(p.pawn(), WEAPON_COMP_CLASS_PATH)
    p.check("the player has a weapon component", wc is not None)
    if wc is None:
        return
    yield lambda: p.get(wc, "Held") is not None
    melee = {str(i.get_editor_property("DisplayName")): i
             for i in p.get(wc, "Inventory") if i.get_editor_property("Melee")}
    knife, axe = melee.get("Knife"), melee.get("Axe")
    p.check("the player carries the knife and the axe", knife and axe,
            str(list(melee)))
    if not (knife and axe):
        return

    grip = knife.get_editor_property("GripLocation")
    blade = knife.get_editor_property(THROW_GRIP_LOC_VAR)
    p.check("the knife has a blade grip apart from its hammer grip",
            knife.get_editor_property(THROW_GRIP_VAR)
            and (blade - grip).length() > 5.0,
            f"{grip} / {blade}")
    before, during, after = yield from _cocked(p, wc, knife)
    p.check("...held by the handle until the throw key goes down",
            (before - grip).length() < NEAR_CM, str(before))
    p.check("...by the blade while the arm is cocked",
            (during - blade).length() < NEAR_CM, f"{during} for {blade}")
    p.check("...and by the handle again once the key is let go",
            (after - grip).length() < NEAR_CM, str(after))

    a_grip = axe.get_editor_property("GripLocation")
    _b, a_during, _a = yield from _cocked(p, wc, axe)
    p.check("the axe, with no blade grip, stays in its own while cocked",
            not axe.get_editor_property(THROW_GRIP_VAR)
            and (a_during - a_grip).length() < NEAR_CM, str(a_during))
