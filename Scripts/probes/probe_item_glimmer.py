"""The item highlight: an item lying on the ground glimmers, one that is
carried does not, and the WORLD SETTINGS tab's row switches every glimmer.

  - every Dropped item in the level shows its Glimmer sprite, and no carried
    one does (the issued knife, axe and stick among them: each has a Tick of
    its own, which overrides the base item's);
  - an item that becomes Dropped starts to glimmer, and stops when it is taken
    (the flag is written on a carried knife, a gun and a stick, and cleared on
    a forage item: the drop, the throw and the pick-up write nothing else);
  - the cycle writes MPC_ItemGlimmer.Highlight from its ItemHighlight, on as
    built;
  - the tab's row steps it to 0 and back to 1 and no further either way, and
    the collection follows;
  - the save writes it into world_tuning.csv.

world_tuning.csv is set aside first and put back.

Run with --windowed and OW_GLIMMER_SHOTS=1 to save pictures of the items
nearest the start, four across one flash's period at noon and four at
midnight, to Saved/Screenshots/MacEditor: the only way to see the glimmer
without playing.
"""

SYSTEMS = ('inventory',)

import os
import shutil

import unreal

from combat.glimmer_tuning import GLIMMER_PERIOD_S, MPC_ITEM_GLIMMER, PARAM_HIGHLIGHT
from combat.paths import ITEM_BP_PATH, ITEM_CLASS_PATH
from graphics_menu import world_tune_consts as WC
from graphics_menu.profile_consts import PROFILE_CHECKED_VAR
from graphics_menu import hud_vars as MV
from world.day_night_blueprint import ITEM_HIGHLIGHT_VAR
from world.paths import DAY_NIGHT_CLASS_PATH
from world.world_tuning import CSV_PATH, ITEM_HIGHLIGHT_ROW, WORLD_STATS, read_table

HUD_BP_PATH = "/Game/UI/BP_GraphicsMenuHUD"
TAB = WC.WORLD_TAB
DROPPED = "Dropped"
WRITABLE = ([(HUD_BP_PATH, v) for v in (TAB.open_var, TAB.row_var, TAB.nudge_var,
                                        TAB.save_var, MV.MenuOpen)]
            + [(ITEM_BP_PATH, DROPPED)])
HIGHLIGHT_TAB_ROW = 1 + WORLD_STATS.index(ITEM_HIGHLIGHT_ROW)
SETTLE = 0.15          # game seconds: a Tick of the item, or of the cycle
SHOTS = bool(os.environ.get("OW_GLIMMER_SHOTS"))
SHOT_BURST = 4


def _live_hud(p):
    try:
        hud = p.hud()
    except Exception:
        return None
    return hud if hud is not None and p.get(hud, PROFILE_CHECKED_VAR) else None


def _glimmers(item):
    sprite = item.get_component_by_class(unreal.MaterialBillboardComponent)
    return sprite is not None and sprite.is_visible()


def _items(p):
    return list(unreal.GameplayStatics.get_all_actors_of_class(
        p.world(), p.load_class(ITEM_CLASS_PATH)))


def _switch(p):
    return unreal.MaterialLibrary.get_scalar_parameter_value(
        p.world(), unreal.load_asset(MPC_ITEM_GLIMMER), PARAM_HIGHLIGHT)


def _nudge(p, hud, step):
    p.set(hud, TAB.row_var, HIGHLIGHT_TAB_ROW)
    p.set(hud, TAB.nudge_var, step)
    yield lambda: p.get(hud, TAB.nudge_var) == 0
    yield SETTLE        # the HUD's apply, then the cycle's Tick


def _shots(p, cycle, ground):
    """Look at the nearest item on the ground, at noon and at midnight."""
    if not SHOTS:
        return
    pc, eye = p.controller(), p.pawn().get_actor_location() + unreal.Vector(0.0, 0.0, 60.0)
    near = min(ground, key=lambda i: (i.get_actor_location() - eye).length())
    pc.set_control_rotation(unreal.MathLibrary.find_look_at_rotation(
        eye, near.get_actor_location()))
    day, night = p.get(cycle, "DayLengthSeconds"), p.get(cycle, "NightLengthSeconds")
    for what, clock in (("noon", day / 2.0), ("midnight", day + night / 2.0)):
        p.set(cycle, "Clock", clock)
        yield 2.0       # the exposure settles
        # A glint is gone most of the time: a burst across one period.
        for _ in range(SHOT_BURST):
            unreal.SystemLibrary.execute_console_command(p.world(), "shot")
            yield GLIMMER_PERIOD_S / SHOT_BURST
        p.note(f"{SHOT_BURST} shots: the glimmer at {what}, {near.get_name()}")


def probe(p):
    backup = CSV_PATH + ".probe-backup"
    shutil.copy2(CSV_PATH, backup)
    try:
        yield from _run(p)
    finally:
        shutil.move(backup, CSV_PATH)


def _run(p):
    yield lambda: _live_hud(p) is not None
    yield SETTLE
    hud, cycle = _live_hud(p), p.actor_of(DAY_NIGHT_CLASS_PATH)
    items = _items(p)
    ground = [i for i in items if i.get_editor_property(DROPPED)]
    carried = [i for i in items if not i.get_editor_property(DROPPED)]
    dark = [i.get_name() for i in ground if not _glimmers(i)]
    p.check("every item lying on the ground glimmers",
            len(ground) > 0 and not dark, f"{len(ground)} on the ground, without: {dark[:5]}")
    lit = [i.get_name() for i in carried if _glimmers(i)]
    p.check("no carried item does",
            len(carried) >= 6 and not lit, f"{len(carried)} carried, glimmering: {lit[:5]}")

    yield from _shots(p, cycle, ground)

    def of(word):
        return next((i for i in carried if word in i.get_class().get_name()), None)

    # A blade and the stick have Ticks of their own; the shotgun runs the base's.
    for word in ("Knife", "Stick", "Shotgun"):
        item = of(word)
        if item is None:
            p.check(f"a carried {word.lower()} to drop", False, "none carried")
            continue
        p.set(item, DROPPED, True)
        yield SETTLE
        on = _glimmers(item)
        p.set(item, DROPPED, False)
        yield SETTLE
        p.check(f"the {word.lower()} glimmers once it is Dropped, and not once it is taken",
                on and not _glimmers(item), f"dropped {on}, taken {_glimmers(item)}")

    taken = ground[0]
    p.set(taken, DROPPED, False)
    yield SETTLE
    off = not _glimmers(taken)
    p.set(taken, DROPPED, True)
    yield SETTLE
    p.check("an item taken off the ground stops glimmering, and glimmers again put back",
            off and _glimmers(taken), f"taken off {off}, back {_glimmers(taken)}")

    p.check("the cycle's ItemHighlight is on as built, and the collection's switch with it",
            p.get(cycle, ITEM_HIGHLIGHT_VAR) == 1.0 and _switch(p) == 1.0,
            f"{p.get(cycle, ITEM_HIGHLIGHT_VAR)}, {PARAM_HIGHLIGHT} {_switch(p)}")

    p.set(hud, "MenuOpen", True)
    p.set(hud, TAB.open_var, True)
    yield SETTLE
    yield from _nudge(p, hud, -1)
    p.check("the WORLD SETTINGS row switches it off: no glimmer shines",
            p.get(cycle, ITEM_HIGHLIGHT_VAR) == 0.0 and _switch(p) == 0.0,
            f"{p.get(cycle, ITEM_HIGHLIGHT_VAR)}, {PARAM_HIGHLIGHT} {_switch(p)}")
    yield from _nudge(p, hud, -1)
    p.check("off is the row's least: another step down changes nothing",
            p.get(cycle, ITEM_HIGHLIGHT_VAR) == 0.0 and _switch(p) == 0.0,
            f"{p.get(cycle, ITEM_HIGHLIGHT_VAR)}, {PARAM_HIGHLIGHT} {_switch(p)}")

    p.set(hud, TAB.save_var, True)
    yield lambda: not p.get(hud, TAB.save_var)
    saved = read_table()
    p.check("the save writes the switch into world_tuning.csv",
            p.get(hud, TAB.saved_var) and saved.get(ITEM_HIGHLIGHT_ROW[0]) == 0.0, str(saved))

    yield from _nudge(p, hud, 1)
    on = p.get(cycle, ITEM_HIGHLIGHT_VAR), _switch(p)
    yield from _nudge(p, hud, 1)
    p.check("the row switches it back on, and on is its most",
            on == (1.0, 1.0) and p.get(cycle, ITEM_HIGHLIGHT_VAR) == 1.0
            and _switch(p) == 1.0,
            f"{on}, then {p.get(cycle, ITEM_HIGHLIGHT_VAR)}, {PARAM_HIGHLIGHT} {_switch(p)}")
    p.set(hud, TAB.open_var, False)
    p.set(hud, "MenuOpen", False)
