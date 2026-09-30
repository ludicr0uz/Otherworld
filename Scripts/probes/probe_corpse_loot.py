"""Corpse loot: a killed wanderer carries its roll, and the loot window takes it.

The table's 50% is forced per wanderer by writing its LootChances (1.0, then
0.0), so each case is decided rather than a coin toss; the default table is
read first. Kills are Health = 0 with DamagedByPlayer set, as a shot leaves
them. The window is opened and the take asked for by writing the HUD's
LootOpen / LootTakeRequested (a probe has no keyboard; the verifier checks the
Tab / Enter polls).

Cases: a lucky kill carries a canteen and the HUD finds its body in reach;
taking puts a carried canteen in the bag and empties the body, which shuts the
window; an unlucky kill carries nothing; a death nobody caused (no
DamagedByPlayer, as the world-floor net) carries nothing even at 100%.

Any profile on disk is set aside first, so the game starts on the issued
loadout, and put back at the end.
"""

import os
import shutil

import unreal

from combat.paths import (
    HEALTH_BP_PATH, HEALTH_CLASS_PATH, WEAPON_COMP_CLASS_PATH,
)
from graphics_menu import umg_consts as C
from graphics_menu.loot_consts import (
    LOOT_OPEN_VAR, LOOT_PANEL, LOOT_PROMPT, LOOT_ROWS_BOX, LOOT_TAKE_VAR, LOOT_TARGET_VAR,
)
from graphics_menu.profile_consts import PROFILE_CHECKED_VAR, PROFILE_SLOT
from loot.consts import LOOT_CHANCES_VAR, LOOT_NAMES_VAR, LOOT_TABLE_VAR, LOOT_VAR

HUD_BP_PATH = "/Game/UI/BP_GraphicsMenuHUD"
WRITABLE = [(HEALTH_BP_PATH, "Health"), (HEALTH_BP_PATH, "DamagedByPlayer"),
            (HEALTH_BP_PATH, LOOT_CHANCES_VAR),
            (HUD_BP_PATH, LOOT_OPEN_VAR), (HUD_BP_PATH, LOOT_TAKE_VAR)]
CANTEEN = "BP_WaterCanteen_C"
IN_FRONT_CM = 150.0
SETTLE = 0.3
SHOWN = unreal.SlateVisibility.HIT_TEST_INVISIBLE
HIDDEN = unreal.SlateVisibility.COLLAPSED


def _file():
    return os.path.join(unreal.Paths.project_saved_dir(), "SaveGames",
                        f"{PROFILE_SLOT}.sav")


def _live_hud(p):
    try:
        hud = p.hud()
    except Exception:
        return None
    return hud if hud is not None and p.get(hud, PROFILE_CHECKED_VAR) else None


def _wanderers(p):
    ctrls = unreal.GameplayStatics.get_all_actors_of_class(p.world(), unreal.AIController)
    pawns = [c.get_controlled_pawn() for c in ctrls
             if "ForestWandererAI" in c.get_class().get_name()]
    return [x for x in pawns if x is not None
            and not p.get(p.component(x, HEALTH_CLASS_PATH), "Dead")]


def _kill(p, npc, chance, by_player=True):
    """Place ``npc`` in front of the player, force its roll, kill it; returns
    its health component once it is Dead."""
    player = p.pawn()
    spot = player.get_actor_location() + player.get_actor_forward_vector() * IN_FRONT_CM
    npc.set_actor_location(spot, False, True)
    health = p.component(npc, HEALTH_CLASS_PATH)
    p.set(health, LOOT_CHANCES_VAR, [chance])
    p.set(health, "DamagedByPlayer", by_player)
    p.set(health, "Health", 0.0)
    yield lambda: p.get(health, "Dead")
    yield SETTLE
    return health


def _names(p, health):
    return [str(n) for n in p.get(health, LOOT_NAMES_VAR)]


def _check_window(p, hud):
    """DrawHUD by hand (a -nullrhi run never draws, see probe_umg_screens):
    shut, the prompt; open, the panel listing the canteen on the caret's row."""
    ui = p.get(hud, "UiHud")
    prompt, panel = (ui.get_editor_property(n) for n in (LOOT_PROMPT, LOOT_PANEL))
    rows = ui.get_editor_property(LOOT_ROWS_BOX)
    hud.call_method("ReceiveDrawHUD", (1920, 1080))
    p.check("shut, the window shows only its prompt",
            prompt.get_visibility() == SHOWN and panel.get_visibility() == HIDDEN,
            f"{prompt.get_visibility()} {panel.get_visibility()}")
    p.set(hud, LOOT_OPEN_VAR, True)
    hud.call_method("ReceiveDrawHUD", (1920, 1080))
    first, second = rows.get_child_at(0), rows.get_child_at(1)
    value = str(first.get_editor_property(C.ROW_VALUE).get_text())
    p.check("open, the panel lists the canteen, caret on it, and no other row",
            panel.get_visibility() == SHOWN and prompt.get_visibility() == HIDDEN
            and value == "Canteen" and first.get_visibility() == SHOWN
            and first.get_editor_property(C.ROW_CARET).get_render_opacity() == 1.0
            and second.get_visibility() == HIDDEN,
            f"{panel.get_visibility()} {value!r} {second.get_visibility()}")


def _bag(p, wc):
    return [i.get_class().get_name() for i in p.get(wc, "Inventory")]


def probe(p):
    backup = _file() + ".probe-backup"
    if os.path.exists(_file()):
        shutil.move(_file(), backup)
    try:
        yield from _run(p)
    finally:
        if os.path.exists(backup):
            shutil.move(backup, _file())


def _run(p):
    yield lambda: _live_hud(p) is not None and len(_wanderers(p)) >= 3
    hud = _live_hud(p)
    wc = p.component(p.pawn(), WEAPON_COMP_CLASS_PATH)
    first, second, third = _wanderers(p)[:3]

    table = p.component(first, HEALTH_CLASS_PATH)
    items = [c.get_name() for c in p.get(table, LOOT_TABLE_VAR)]
    chances = [round(float(c), 3) for c in p.get(table, LOOT_CHANCES_VAR)]
    p.check("a live wanderer's loot table is water at 50%",
            items == [CANTEEN] and chances == [0.5], f"{items} {chances}")

    # --- a lucky kill ---------------------------------------------------------
    body = yield from _kill(p, first, 1.0)
    p.check("a lucky counted kill carries a canteen",
            [c.get_name() for c in p.get(body, LOOT_VAR)] == [CANTEEN]
            and _names(p, body) == ["Canteen"], str(_names(p, body)))
    yield lambda: p.get(hud, LOOT_TARGET_VAR) == body
    p.check("the HUD finds the body in reach", p.get(hud, LOOT_TARGET_VAR) == body)

    _check_window(p, hud)

    before = _bag(p, wc)
    held = p.get(wc, "Held")
    p.set(hud, LOOT_TAKE_VAR, True)
    yield lambda: not p.get(hud, LOOT_TAKE_VAR)
    yield SETTLE
    after = _bag(p, wc)
    p.check("taking puts the canteen in the bag",
            after.count(CANTEEN) == before.count(CANTEEN) + 1
            and len(after) == len(before) + 1, f"{before} -> {after}")
    taken = [i for i in p.get(wc, "Inventory") if i.get_class().get_name() == CANTEEN]
    p.check("...carried, not lying in the world",
            bool(taken) and all(not p.get(i, "Dropped") for i in taken))
    p.check("...the held item stays held", p.get(wc, "Held") == held)
    p.check("...and the body is emptied",
            len(p.get(body, LOOT_VAR)) == 0 and not _names(p, body), str(_names(p, body)))
    p.check("an empty body is no longer a target, and the window shuts",
            p.get(hud, LOOT_TARGET_VAR) is None and not p.get(hud, LOOT_OPEN_VAR),
            f"{p.get(hud, LOOT_TARGET_VAR)} open={p.get(hud, LOOT_OPEN_VAR)}")

    # --- an unlucky kill, and a death nobody caused ----------------------------
    body = yield from _kill(p, second, 0.0)
    p.check("an unlucky kill carries nothing", len(p.get(body, LOOT_VAR)) == 0,
            str(_names(p, body)))
    body = yield from _kill(p, third, 1.0, by_player=False)
    p.check("a death nobody caused carries nothing, even at 100%",
            len(p.get(body, LOOT_VAR)) == 0, str(_names(p, body)))
    yield SETTLE
    p.check("...and neither is a target", p.get(hud, LOOT_TARGET_VAR) is None,
            str(p.get(hud, LOOT_TARGET_VAR)))
