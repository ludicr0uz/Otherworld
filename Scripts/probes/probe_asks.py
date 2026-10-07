"""What a screen asks of the weapon component, in a game: each Ask event
(combat/ask_consts.py) called as the HUD calls it, and the one a headless
probe can raise through the HUD itself, the menu's save-and-exit row.

    AskSlot       a weapon slot's item comes to hand
    AskMove       a bag slot's item moves to an empty bag slot
    AskDrop       a slot's item is set down on the ground
    AskLootTake   with no body, nothing is taken
    AskSaveExit   the row taken in play: the countdown runs on the component
                  for EXIT_SECONDS, the menu shuts, the character stands
                  still; asked again it does not start over; a hit calls it
                  off, and nothing is due

The wear, the take-off and the loot take go through the HUD in
probe_clothing.py and probe_corpse_loot.py, the countdown's end in
probe_save_exit.py. Any profile on disk is set aside first, so the game
starts on the issued loadout, and put back at the end.
"""

import os
import shutil

import unreal

from combat import ask_consts as AC
from combat.game_state import LAST_DAMAGE_VAR
from combat.paths import HEALTH_BP_PATH, HEALTH_CLASS_PATH, WEAPON_COMP_CLASS_PATH
from combat.slot_tuning import BAG_FIRST, HAND, PISTOL_SLOT, SLOT_ITEMS_VAR
from graphics_menu import cursor_consts as CC
from graphics_menu import hud_vars as MV
from graphics_menu import umg_consts as C
from graphics_menu.profile_consts import EXIT_ACTION, PROFILE_SLOT

HUD_BP_PATH = "/Game/UI/BP_GraphicsMenuHUD"
WRITABLE = [(HUD_BP_PATH, MV.MenuOpen), (HUD_BP_PATH, CC.PAUSE_CLICK_VAR),
            (HEALTH_BP_PATH, LAST_DAMAGE_VAR)]
SETTLE = 0.2


def _file():
    return os.path.join(unreal.Paths.project_saved_dir(), "SaveGames",
                        f"{PROFILE_SLOT}.sav")


def probe(p):
    backup = _file() + ".probe-backup"
    if os.path.exists(_file()):
        shutil.move(_file(), backup)
    try:
        yield from _run(p)
    finally:
        if os.path.exists(backup):
            shutil.move(backup, _file())


def _slots(p, wc):
    return list(p.get(wc, SLOT_ITEMS_VAR))


def _run(p):
    yield lambda: p.pawn() is not None and p.hud() is not None
    player, hud = p.pawn(), p.hud()
    wc = p.component(player, WEAPON_COMP_CLASS_PATH)
    health = p.component(player, HEALTH_CLASS_PATH)
    yield lambda: p.get(wc, "Held") is not None
    yield 0.3

    # --- a slot to hand ------------------------------------------------------
    pistol = _slots(p, wc)[PISTOL_SLOT]
    wc.call_method(AC.ASK_SLOT, (PISTOL_SLOT,))
    yield lambda: p.get(wc, "Held") == pistol
    p.check(f"{AC.ASK_SLOT}: the pistol's slot asked for, the pistol is in hand",
            pistol is not None and p.get(wc, "Held") == pistol
            and _slots(p, wc)[HAND] == pistol, str(p.get(wc, "Held")))

    # --- a move --------------------------------------------------------------
    slots = _slots(p, wc)
    src = next(c for c in range(BAG_FIRST, len(slots)) if slots[c] is not None)
    dst = next(c for c in range(len(slots) - 1, BAG_FIRST, -1) if slots[c] is None)
    moved = slots[src]
    wc.call_method(AC.ASK_MOVE, (src, dst))
    yield lambda: _slots(p, wc)[dst] == moved
    p.check(f"{AC.ASK_MOVE}: bag slot {src}'s item is in bag slot {dst}, and its "
            "own is empty", _slots(p, wc)[dst] == moved and _slots(p, wc)[src] is None,
            str(_slots(p, wc)[dst]))

    # --- a drop --------------------------------------------------------------
    wc.call_method(AC.ASK_DROP, (dst,))
    yield lambda: moved not in list(p.get(wc, "Inventory"))
    yield SETTLE
    p.check(f"{AC.ASK_DROP}: that item is out of the inventory, lying on the ground",
            moved not in list(p.get(wc, "Inventory"))
            and moved.get_editor_property("Dropped") is True
            and _slots(p, wc)[dst] is None)

    # --- a take from nobody --------------------------------------------------
    count = len(p.get(wc, "Inventory"))
    wc.call_method(AC.ASK_LOOT_TAKE, (None, 0, None))
    yield SETTLE
    p.check(f"{AC.ASK_LOOT_TAKE} with no body takes nothing",
            len(p.get(wc, "Inventory")) == count)

    # --- save and exit, by the menu's row ------------------------------------
    moves = player.get_editor_property("character_movement")
    p.set(hud, MV.MenuOpen, True)
    p.set(hud, CC.PAUSE_CLICK_VAR, C.PAUSE_ROW_ACTIONS.index(EXIT_ACTION))
    yield lambda: p.get(wc, AC.EXIT_PENDING_VAR)
    p.set(hud, CC.PAUSE_CLICK_VAR, CC.NO_ROW)
    yield SETTLE
    started, due = p.get(wc, AC.EXIT_STARTED_VAR), p.get(wc, AC.EXIT_AT_VAR)
    p.check(f"the menu's save-and-exit row starts the component's countdown, "
            f"{AC.EXIT_SECONDS:.0f} s long, and the menu shuts",
            p.get(wc, AC.EXIT_PENDING_VAR) is True
            and abs(due - started - AC.EXIT_SECONDS) < 1e-3
            and p.get(hud, MV.MenuOpen) is False, f"{due - started:.2f} s")
    p.check("...the character standing still meanwhile",
            moves.movement_mode == unreal.MovementMode.MOVE_NONE, str(moves.movement_mode))
    wc.call_method(AC.ASK_SAVE_EXIT)
    yield SETTLE
    p.check("...asked again while it runs, it does not start over",
            p.get(wc, AC.EXIT_STARTED_VAR) == started and p.get(wc, AC.EXIT_AT_VAR) == due,
            f"{p.get(wc, AC.EXIT_STARTED_VAR):.2f} / {started:.2f}")
    p.set(health, LAST_DAMAGE_VAR, p.time())
    yield lambda: not p.get(wc, AC.EXIT_PENDING_VAR)
    yield SETTLE
    p.check("a hit calls it off: the character walks again, and nothing is due",
            moves.movement_mode == unreal.MovementMode.MOVE_WALKING
            and p.get(wc, AC.EXIT_CALLED_OFF_VAR) > 0.0
            and p.get(wc, AC.EXIT_DUE_VAR) is False, str(moves.movement_mode))
