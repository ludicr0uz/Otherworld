"""A row of the grip nudge table moves the held item by exactly that row
(combat/grip_nudges.py, Source/Otherworld/Public/OtherworldGripLibrary.h).

The game's table is pointed at a scratch file for the run, so the tracked
Content/Tuning/grip_nudges.csv is never written. Reading the file again
(ReloadGripNudges) is what a launch does: nothing is rebuilt anywhere here.

    no row, then a row of zeros   the knife sits where its Grip alone says
    a row of centimetres          ...moved by exactly the row
    a row with degrees too        ...at inverse(Grip) * row
    the same on the pistol        and it is still there half a second on
    the GUN SETTINGS tab open     its grip cells show the held item's row;
    one step on "grip x"          the knife moves 0.1 cm that Tick, with no
                                  equip, and the file holds the new number,
                                  which a reload then seats it by
"""

SYSTEMS = ('weapons', 'menu')

import os

import unreal

from combat.grip_nudges import GRIP_COLUMNS, GRIP_STATS, read_table, write_table
from combat.paths import WEAPON_COMP_BP_PATH, WEAPON_COMP_CLASS_PATH
from combat.weapon_component import vars as WV
from graphics_menu import tune_consts as TC
from graphics_menu.profile_consts import PROFILE_CHECKED_VAR

HUD_BP_PATH = "/Game/UI/BP_GraphicsMenuHUD"
WRITABLE = ([(WEAPON_COMP_BP_PATH, WV.EquippedIndex), (WEAPON_COMP_BP_PATH, WV.NeedsRefresh)]
            + [(HUD_BP_PATH, v) for v in (TC.TUNE_OPEN_VAR, TC.TUNE_ROW_VAR,
                                          TC.TUNE_WEAPON_VAR, TC.TUNE_NUDGE_VAR)])

LIB = unreal.OtherworldGripLibrary
NEAR_CM = 0.001
NEAR_DEG = 0.01
# "Changes nothing": the seat read back through the root's rotator is the
# Grip's inverse to float noise (8e-15 cm measured), not to the bit.
SAME = 1e-6
KNIFE, PISTOL = "BP_Knife", "BP_Pistol"
MOVE = dict(x=1.5, y=-2.0, z=0.5)
TURN = dict(MOVE, pitch=10.0, yaw=20.0, roll=30.0)


def _row(values):
    return unreal.Transform(
        location=unreal.Vector(*(values.get(c, 0.0) for c in GRIP_COLUMNS[:3])),
        rotation=unreal.Rotator(pitch=values.get("pitch", 0.0), yaw=values.get("yaw", 0.0),
                                roll=values.get("roll", 0.0)))


def _rel(item):
    """The item under the socket, as a copy (a struct read back is a view)."""
    root = item.root_component
    at, rot = (root.get_editor_property(n) for n in ("relative_location", "relative_rotation"))
    return unreal.Transform(location=unreal.Vector(at.x, at.y, at.z),
                            rotation=unreal.Rotator(pitch=rot.pitch, yaw=rot.yaw, roll=rot.roll))


def _by_grip(item):
    """Where the item's Grip alone seats it (combat/grip_handle.py)."""
    grip = item.find_component_by_tag(unreal.SceneComponent, "Grip")
    return grip.get_relative_transform().inverse()


def _off(a, b):
    """(cm, degrees) between two transforms."""
    turn = a.rotation.angular_distance(b.rotation)
    return ((a.translation - b.translation).length(),
            abs(unreal.MathLibrary.radians_to_degrees(turn)))


def _near(a, b):
    cm, deg = _off(a, b)
    return cm < NEAR_CM and deg < NEAR_DEG


def _equip(p, wc, item, other):
    """Seat ``item`` anew: through another item, so the equip runs."""
    for it in (other, item):
        p.set(wc, "EquippedIndex", list(p.get(wc, "Inventory")).index(it))
        p.set(wc, "NeedsRefresh", True)
        yield lambda: p.get(wc, "Held") == it and not p.get(wc, "NeedsRefresh")
        yield 0.1


def _relaunch(path, rows):
    """The file as a person left it, read as a launch reads it."""
    write_table(rows, path)
    return LIB.reload_grip_nudges()


def _carried(p, wc, row):
    return next((i for i in p.get(wc, "Inventory") if i and str(LIB.grip_row_of(i)) == row),
                None)


def _live_hud(p):
    try:
        hud = p.hud()
    except Exception:
        return None
    return hud if hud is not None and p.get(hud, PROFILE_CHECKED_VAR) else None


def probe(p):
    path = os.path.join(
        unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()),
        "uepy", "probe_grip_nudges.csv")
    write_table([], path)
    LIB.set_grip_nudge_file(path)
    try:
        yield from _run(p, path)
    finally:
        LIB.set_grip_nudge_file("")
        if os.path.exists(path):
            os.remove(path)


def _run(p, path):
    yield lambda: p.pawn() is not None and _live_hud(p) is not None
    hud = _live_hud(p)
    wc = p.component(p.pawn(), WEAPON_COMP_CLASS_PATH)
    yield lambda: p.get(wc, "Held") is not None
    knife, pistol = _carried(p, wc, KNIFE), _carried(p, wc, PISTOL)
    p.check("the player carries the knife and the pistol", bool(knife and pistol))
    if not (knife and pistol):
        return
    p.check("the game reads the scratch table, which has no rows",
            os.path.samefile(str(LIB.grip_nudge_file()), path)
            and LIB.reload_grip_nudges() == 0, str(LIB.grip_nudge_file()))

    yield from _equip(p, wc, knife, pistol)
    base = _by_grip(knife)
    p.check("with no row the knife sits where its Grip alone says",
            max(_off(_rel(knife), base)) < SAME, str(_off(_rel(knife), base)))
    rows = _relaunch(path, [(KNIFE, {}), (PISTOL, {})])
    yield from _equip(p, wc, knife, pistol)
    p.check("a row of zeros changes nothing",
            rows == 2 and max(_off(_rel(knife), base)) < SAME, str(_off(_rel(knife), base)))

    _relaunch(path, [(KNIFE, MOVE), (PISTOL, {})])
    yield from _equip(p, wc, knife, pistol)
    got = _rel(knife)
    moved = got.translation - base.translation
    p.check(f"a row of {MOVE} read at a launch moves the knife by exactly that",
            (moved - unreal.Vector(MOVE["x"], MOVE["y"], MOVE["z"])).length() < NEAR_CM
            and _off(got, base)[1] < NEAR_DEG, f"moved {moved}, turned {_off(got, base)[1]}")
    p.check("...which is what the library says its seat is",
            _near(got, LIB.grip_seat(knife)), str(_off(got, LIB.grip_seat(knife))))

    _relaunch(path, [(KNIFE, TURN), (PISTOL, TURN)])
    yield from _equip(p, wc, knife, pistol)
    want = unreal.MathLibrary.compose_transforms(base, _row(TURN))
    p.check("a row with degrees seats the knife at inverse(Grip) * row: turned "
            "about the socket, then moved",
            _near(_rel(knife), want) and _off(want, base)[1] > 30.0,
            f"{_off(_rel(knife), want)} off, the row turns {_off(want, base)[1]:.1f} deg")
    yield from _equip(p, wc, pistol, knife)
    want = unreal.MathLibrary.compose_transforms(_by_grip(pistol), _row(TURN))
    seated = _off(_rel(pistol), want)
    yield 0.5
    p.check("the pistol takes its row too, and nothing takes it back in half a second",
            max(seated) < NEAR_DEG and _near(_rel(pistol), want),
            f"{seated} at the equip, {_off(_rel(pistol), want)} later")

    # The tab: its grip rows are the held item's, whichever weapon it shows.
    yield from _equip(p, wc, knife, pistol)
    before = _rel(knife)
    p.set(hud, TC.TUNE_WEAPON_VAR, 0)
    p.set(hud, TC.TUNE_OPEN_VAR, True)
    yield 0.2
    first = 0 * TC.STAT_COUNT + TC.GRIP_FIRST
    cells = [float(v) for v in p.get(hud, TC.TUNE_VALUES_VAR)][first:first + len(GRIP_STATS)]
    p.check("open, the tab's grip cells show the held knife's row",
            cells == [TURN[c] for c in GRIP_COLUMNS], str(cells))
    p.check("...and showing it moved nothing", max(_off(_rel(knife), before)) < SAME)
    step = GRIP_STATS[0][2]
    p.set(hud, TC.TUNE_ROW_VAR, 1 + TC.GRIP_FIRST)
    p.set(hud, TC.TUNE_NUDGE_VAR, 1)
    yield lambda: p.get(hud, TC.TUNE_NUDGE_VAR) == 0
    yield 0.1
    slid = _rel(knife).translation - before.translation
    p.check(f"one step on the grip x row moves the held knife {step} cm, with no equip",
            (slid - unreal.Vector(step, 0.0, 0.0)).length() < NEAR_CM
            and _off(_rel(knife), before)[1] < NEAR_DEG, str(slid))
    saved = read_table(path)
    p.check("...and wrote the table: the knife's row with the step, the pistol's as it was",
            saved.get(KNIFE) == dict(TURN, x=TURN["x"] + step) and saved.get(PISTOL) == TURN,
            str(saved))
    p.set(hud, TC.TUNE_OPEN_VAR, False)
    yield 0.1
    slid_to = _rel(knife)
    LIB.reload_grip_nudges()
    yield from _equip(p, wc, knife, pistol)
    p.check("...which the next launch seats the knife by",
            _near(_rel(knife), slid_to), str(_off(_rel(knife), slid_to)))
