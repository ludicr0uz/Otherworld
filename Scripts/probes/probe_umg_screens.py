"""The UMG screens: BeginPlay creates all four and adds them to the viewport,
and each DrawHUD shows the one the game is on and writes the live values in.

A -nullrhi run never renders, so the engine never calls DrawHUD; the probe
calls the HUD's ReceiveDrawHUD event itself, then reads the widgets back. (The
canvas layers -- reticle, scope, wanderers' bars -- log that there is no
canvas when called this way; they are not what this probe is about.) State is
set by writing the HUD's and the game's variables: a probe has no keyboard.
"""

import os

import unreal

from combat.slot_tuning import HAND, SLOT_ITEMS_VAR, WEAPON_SLOTS
from graphics_menu.inv_consts import BAG_PANEL, SLOT_BOXES
from combat.game_state import DEBUG_MODE_VAR, KILL_COUNT_VAR
from net.state_consts import GAME_STATE_BP_PATH, PLAYER_STATE_BP_PATH
from combat.paths import (
    HEALTH_BP_PATH, HEALTH_CLASS_PATH, WEAPON_COMP_CLASS_PATH,
)
from graphics_menu import mode_consts as MC
from graphics_menu import umg_consts as C
from net.session_consts import SERVER_ADDRESS_VAR
from graphics_menu.profile_consts import (
    PROFILE_CLASS_PATH, PROFILE_SLOT, PROFILE_USER_INDEX)
from graphics_menu.settings_rows import (
    BACK_ROW, DIFFICULTY_LABELS, DIFFICULTY_ROW, FIRST_BIND_ROW)
from survival.paths import SURVIVAL_BP_PATH, SURVIVAL_CLASS_PATH
from combat import health_vars as HV
from graphics_menu import hud_vars as MV
from survival import component_vars as UV

HUD_BP_PATH = "/Game/UI/BP_GraphicsMenuHUD"
WRITABLE = [(HUD_BP_PATH, v) for v in (MV.MenuOpen, C.GAME_STARTED_VAR, MV.MenuPage,
                                       MV.MenuRow, C.PAUSE_ROW_VAR)]
WRITABLE += [(PLAYER_STATE_BP_PATH, KILL_COUNT_VAR), (PLAYER_STATE_BP_PATH, "PlayerDead"),
             (GAME_STATE_BP_PATH, DEBUG_MODE_VAR),
             (HEALTH_BP_PATH, HV.Health), (SURVIVAL_BP_PATH, UV.Hunger)]

SHOWN = unreal.SlateVisibility.HIT_TEST_INVISIBLE
HIDDEN = unreal.SlateVisibility.COLLAPSED
HEALTH, HUNGER, KILLS = 37.0, 40.0, 4


def _profile_file():
    return os.path.join(unreal.Paths.project_saved_dir(), "SaveGames",
                        f"{PROFILE_SLOT}.sav")


def _draw(hud):
    hud.call_method("ReceiveDrawHUD", (1920, 1080))


def _text(w):
    return str(w.get_text())


def _row(box, i):
    return box.get_child_at(i)


def _carets(box, count):
    return [round(_row(box, i).get_editor_property(C.ROW_CARET).get_render_opacity(), 3)
            for i in range(count)]


def _screens(p, hud):
    return {var: p.get(hud, var) for var, _a, _z in C.SCREENS}


def _visible(ui):
    return {var: w.get_visibility() for var, w in ui.items()}


def probe(p):
    yield lambda: p.hud() is not None and p.get(p.hud(), "UiHud") is not None
    yield 0.3
    hud, pawn, mode = p.hud(), p.pawn(), p.player_state()
    world_state = p.game_state()
    ui = _screens(p, hud)
    p.check("BeginPlay created all four screens and put them on the viewport",
            all(w is not None and w.is_in_viewport() for w in ui.values()),
            str({k: (w.get_class().get_name() if w else None) for k, w in ui.items()}))

    # --- playing: the HUD's Body, and its numbers --------------------------------
    health = p.component(pawn, HEALTH_CLASS_PATH)
    survival = p.component(pawn, SURVIVAL_CLASS_PATH)
    wc = p.component(pawn, WEAPON_COMP_CLASS_PATH)
    p.set(health, "Health", HEALTH)
    p.set(survival, "Hunger", HUNGER)
    p.set(mode, KILL_COUNT_VAR, KILLS)
    _draw(hud)
    body = ui["UiHud"].get_editor_property(C.HUD_BODY)
    seen = _visible(ui)
    p.check("in play the HUD's Body is up and every menu is down",
            body.get_visibility() == SHOWN and seen["UiHud"] == SHOWN
            and all(seen[v] == HIDDEN for v in ("UiMain", "UiPause", "UiDeath")),
            f"body {body.get_visibility()}, {seen}")
    hp_num = _text(ui["UiHud"].get_editor_property(C.HP_NUM))
    hp_bar = ui["UiHud"].get_editor_property(C.HP_BAR).get_editor_property("percent")
    top = p.get(health, "MaxHealth")
    p.check("the HP number and bar show the player's health",
            hp_num == str(int(HEALTH)) and abs(hp_bar - HEALTH / top) < 1e-3,
            f"'{hp_num}', {hp_bar:.3f} (want {HEALTH / top:.3f})")
    hunger = ui["UiHud"].get_editor_property(C.stat_bar("Hunger")).get_editor_property("percent")
    want = p.get(survival, "Hunger") / p.get(survival, "MaxHunger")
    p.check("the FOOD bar shows the player's hunger", abs(hunger - want) < 1e-2,
            f"{hunger:.3f} (want {want:.3f})")
    stamina = ui["UiHud"].get_editor_property(C.STAMINA_BAR).get_editor_property("percent")
    want = p.get(wc, "Stamina") / p.get(wc, "MaxStamina")
    p.check("the stamina bar shows the player's stamina", abs(stamina - want) < 1e-2,
            f"{stamina:.3f} (want {want:.3f})")
    kills = _text(ui["UiHud"].get_editor_property(C.KILLS))
    p.check("the kill counter reads the GameMode's count", kills == f"KILLS  {KILLS}",
            f"'{kills}'")

    # The slots (combat/slot_tuning.py): code c is the hand's cell, a weapon
    # cell or a bag cell, and shows SlotItems[c].
    slots = list(p.get(wc, SLOT_ITEMS_VAR))
    cells = []
    for box, first, count in SLOT_BOXES:
        grid = ui["UiHud"].get_editor_property(box)
        cells += [grid.get_child_at(i) for i in range(count)]
    icons = [c.get_editor_property(C.SLOT_ICON).get_visibility() for c in cells]
    p.check("a slot shows an icon exactly when something is in it (the hand, the "
            "weapon slots, the bag)",
            len(slots) == len(cells) and any(slots)
            and icons == [SHOWN if s else HIDDEN for s in slots],
            f"{[_name(p, s) for s in slots]}: {[str(v.name) for v in icons]}")
    lit = [c.get_editor_property(C.SLOT_FRAME).get_visibility() == SHOWN for c in cells]
    name = _text(ui["UiHud"].get_editor_property(C.EQUIPPED_NAME))
    held = p.get(wc, "Held")
    p.check("only the hand's slot is lit (the I panel shut), and the held item's name "
            "is over it",
            lit == [i == HAND for i in range(len(cells))] and held is not None
            and name == str(p.get(held, "DisplayName")),
            f"lit {lit}, name '{name}'")
    counted = [(i, _text(c.get_editor_property(C.SLOT_AMMO)))
               for i, (c, it) in enumerate(zip(cells, slots)) if it and p.get(it, "UsesAmmo")]
    want = [(i, f"{p.get(it, 'Loaded')} / "
                f"{chr(0x221e) if p.get(it, 'InfiniteReserve') else p.get(it, 'Reserve')}")
            for i, it in enumerate(slots) if it and p.get(it, "UsesAmmo")]
    p.check("each gun that uses ammunition shows loaded / reserve", counted == want,
            f"{counted} vs {want}")
    bag = ui["UiHud"].get_editor_property(BAG_PANEL)
    p.check("the backpack shows with the I panel shut", bag.get_visibility() == SHOWN,
            str(bag.get_visibility()))
    # An empty slot's silhouette: only a slot that has one (the weapon slots).
    ghosts = [c.get_editor_property(C.SLOT_GHOST).get_visibility() == SHOWN for c in cells]
    p.check("an empty weapon slot shows its kind's silhouette; a filled one, the hand's "
            "and the bag's show none",
            ghosts == [code in WEAPON_SLOTS and not s for code, s in enumerate(slots)]
            and any(ghosts), f"{ghosts}")

    # --- the M panel ----------------------------------------------------------------
    p.set(hud, "MenuOpen", True)
    p.set(hud, C.PAUSE_ROW_VAR, 2)
    _draw(hud)
    rows = ui["UiPause"].get_editor_property(C.PAUSE_ROWS)
    carets = _carets(rows, len(C.PAUSE_ROW_LABELS))
    debug = _text(_row(rows, C.PAUSE_DEBUG_ROW).get_editor_property(C.ROW_VALUE))
    p.check("M opens the panel with the caret on its own row (PauseRow)",
            ui["UiPause"].get_visibility() == SHOWN
            and carets == [float(i == 2) for i in range(len(C.PAUSE_ROW_LABELS))],
            str(carets))
    p.check("...and the debug row says whether debug mode is on",
            debug == (C.DEBUG_ON if p.get(hud, "DebugOn") else C.DEBUG_OFF), f"'{debug}'")
    first = _text(_row(rows, C.PAUSE_START_ROW).get_editor_property(C.ROW_LABEL))
    needs = [_text(_row(rows, C.PAUSE_ROW_ACTIONS.index(a)).get_editor_property(C.ROW_VALUE))
             for a in C.IN_GAME_ACTIONS]
    p.check("...and in play its first row reads resume, and no row says it needs a game",
            first == C.RESUME_ROW_LABEL and needs == [""] * len(needs),
            f"'{first}', {needs}")
    p.set(hud, "MenuOpen", False)
    _draw(hud)
    p.check("...and closing it takes it down", ui["UiPause"].get_visibility() == HIDDEN)

    # --- the FPS readout: on screen whatever debug mode says --------------------------
    fps = ui["UiHud"].get_editor_property(C.HUD_FPS)
    was, seen = p.get(world_state, DEBUG_MODE_VAR), {}
    for debug in (False, True):
        p.set(world_state, DEBUG_MODE_VAR, debug)
        _draw(hud)
        seen[debug] = (p.get(hud, "DebugOn"), fps.get_visibility(), _text(fps))
    p.set(world_state, DEBUG_MODE_VAR, was)
    _draw(hud)
    p.check("the FPS readout is on screen with debug mode off, and with it on",
            all(on == debug and vis not in (HIDDEN, unreal.SlateVisibility.HIDDEN)
                and words.startswith("FPS  ") and words[5:].isdigit()
                for debug, (on, vis, words) in seen.items()),
            str({d: (on, str(vis.name), words) for d, (on, vis, words) in seen.items()}))

    # --- the title: the same menu, alone; and its settings page ---------------------
    p.set(hud, C.GAME_STARTED_VAR, False)
    p.set(hud, "MenuPage", 0)
    p.set(hud, C.PAUSE_ROW_VAR, 1)
    _draw(hud)
    main, pause = ui["UiMain"], ui["UiPause"]
    panel, settings = (pause.get_editor_property(C.PAUSE_PANEL),
                       main.get_editor_property(C.SETTINGS_PANEL))
    p.check("before a game starts the menu is up, held open, over a hidden HUD",
            p.get(hud, "MenuOpen") is True and pause.get_visibility() == SHOWN
            and panel.get_visibility() == SHOWN and main.get_visibility() == SHOWN
            and settings.get_visibility() == HIDDEN and body.get_visibility() == HIDDEN,
            f"pause {pause.get_visibility()}, panel {panel.get_visibility()}, "
            f"body {body.get_visibility()}")
    rows = pause.get_editor_property(C.PAUSE_ROWS)
    carets = _carets(rows, len(C.PAUSE_ROW_LABELS))
    p.check("...with the caret on PauseRow's row",
            carets == [float(i == 1) for i in range(len(C.PAUSE_ROW_LABELS))], str(carets))
    first, second = (_text(_row(rows, i).get_editor_property(C.ROW_LABEL)) for i in (0, 1))
    p.check("...its first two rows the modes: single player, multiplayer",
            [first, second] == [C.SINGLE_ROW_LABEL, C.MULTI_ROW_LABEL], f"'{first}', '{second}'")

    # --- the Single Player page, in the rows' place ----------------------------
    p.set(hud, "MenuPage", MC.PAGE_SINGLE)
    p.set(hud, "MenuRow", MC.SINGLE_START_ROW)
    _draw(hud)
    single = pause.get_editor_property(MC.SINGLE.panel)
    multi = pause.get_editor_property(MC.MULTI.panel)
    p.check("the Single Player page stands in the menu's place, the caret on its row",
            single.get_visibility() == SHOWN and panel.get_visibility() == HIDDEN
            and multi.get_visibility() == HIDDEN and settings.get_visibility() == HIDDEN
            and _carets(pause.get_editor_property(MC.SINGLE.rows_box), 1) == [1.0]
            and pause.get_editor_property(MC.SINGLE.back).get_editor_property(
                C.ROW_CARET).get_render_opacity() == 0.0)
    page_rows = pause.get_editor_property(MC.SINGLE.rows_box)

    # Its row asks the disk whether there is a profile to continue. One
    # that is the player's own is set aside for the look without it and put
    # back; with none, a blank one is saved for the look with it and deleted.
    def first_row():
        _draw(hud)
        return _text(_row(page_rows, MC.SINGLE_START_ROW).get_editor_property(C.ROW_LABEL))

    GS = unreal.GameplayStatics
    mine = os.path.exists(_profile_file())
    if mine:
        os.rename(_profile_file(), _profile_file() + ".probe")
    try:
        first = first_row()
        if mine:
            os.rename(_profile_file() + ".probe", _profile_file())
        else:
            GS.save_game_to_slot(
                GS.create_save_game_object(p.load_class(PROFILE_CLASS_PATH)),
                PROFILE_SLOT, PROFILE_USER_INDEX)
        saved = first_row()
    finally:
        if mine and os.path.exists(_profile_file() + ".probe"):
            os.rename(_profile_file() + ".probe", _profile_file())
        if not mine:
            GS.delete_game_in_slot(PROFILE_SLOT, PROFILE_USER_INDEX)
    needs = [_text(_row(rows, C.PAUSE_ROW_ACTIONS.index(a)).get_editor_property(C.ROW_VALUE))
             for a in C.IN_GAME_ACTIONS]
    last = str(_row(rows, len(C.PAUSE_ROW_LABELS) - 1).get_editor_property(C.ROW_TEXT_VAR))
    p.check("...its row reads new game",
            first == C.START_ROW_LABEL, f"'{first}'")
    p.check("...and with a saved profile on disk continue game",
            saved == C.CONTINUE_ROW_LABEL, f"'{saved}'")

    # --- the Multiplayer page ------------------------------------------------------
    p.set(hud, "MenuPage", MC.PAGE_MULTI)
    p.set(hud, "MenuRow", MC.MULTI.back_row)
    _draw(hud)
    typed = str(p.get(p.get(hud, MV.Settings), SERVER_ADDRESS_VAR))
    shown = _text(_row(pause.get_editor_property(MC.MULTI.rows_box),
                       MC.MULTI_ADDRESS_ROW).get_editor_property(C.ROW_VALUE))
    p.check("the Multiplayer page stands in the menu's place, its address row "
            "showing the saved address, its BACK row lit with the caret on it",
            multi.get_visibility() == SHOWN and single.get_visibility() == HIDDEN
            and panel.get_visibility() == HIDDEN and shown == typed != ""
            and pause.get_editor_property(MC.MULTI.back).get_editor_property(
                C.ROW_CARET).get_render_opacity() == 1.0
            and _carets(pause.get_editor_property(MC.MULTI.rows_box), 2) == [0.0, 0.0],
            f"'{shown}' of '{typed}'")
    p.set(hud, "MenuRow", MC.MULTI_ADDRESS_ROW)
    _draw(hud)
    shown = _text(_row(pause.get_editor_property(MC.MULTI.rows_box),
                       MC.MULTI_ADDRESS_ROW).get_editor_property(C.ROW_VALUE))
    status = _text(pause.get_editor_property(MC.MULTI_STATUS))
    p.check("...with the caret on the address row a typing mark follows it, and "
            "the status line is empty: no join, no reason",
            shown == typed + MC.ADDRESS_CARET and status == "", f"'{shown}', '{status}'")
    p.set(hud, "MenuPage", 0)
    _draw(hud)
    p.check("back on the menu's rows both pages are down",
            panel.get_visibility() == SHOWN and single.get_visibility() == HIDDEN
            and multi.get_visibility() == HIDDEN)
    p.check("...its last row exit game, its third the settings page's (controls), "
            "and the rows that need a game say so",
            last == C.QUIT_ROW_LABEL and needs == [C.IN_GAME_ONLY] * len(needs)
            and str(_row(rows, 2).get_editor_property(C.ROW_TEXT_VAR))
            == "Controls" == C.SETTINGS_ROW_LABEL, f"'{last}', {needs}")

    p.set(hud, "MenuPage", 1)
    p.set(hud, "MenuRow", FIRST_BIND_ROW)
    _draw(hud)
    rows = main.get_editor_property(C.SETTINGS_ROWS_BOX)
    values = [_text(_row(rows, i).get_editor_property(C.ROW_VALUE))
              for i in range(len(C.SETTINGS_ROW_LABELS))]
    p.check("the settings page stands in the menu's place",
            settings.get_visibility() == SHOWN and panel.get_visibility() == HIDDEN)
    back = main.get_editor_property(C.SETTINGS_BACK)
    p.check("...every setting row shows its value and BACK, the row over them, "
            "shows none",
            all(values) and _text(back.get_editor_property(C.ROW_VALUE)) == ""
            and values[DIFFICULTY_ROW] in DIFFICULTY_LABELS, str(values))
    carets = _carets(rows, len(C.SETTINGS_ROW_LABELS))
    p.check("...and the caret is on MenuRow's row",
            carets.index(1.0) == FIRST_BIND_ROW and carets.count(1.0) == 1
            and back.get_editor_property(C.ROW_CARET).get_render_opacity() == 0.0,
            str(carets))
    p.set(hud, "MenuRow", BACK_ROW)
    _draw(hud)
    carets = _carets(rows, len(C.SETTINGS_ROW_LABELS))
    p.check("...and on BACK's row with MenuRow on its number, the last",
            back.get_editor_property(C.ROW_CARET).get_render_opacity() == 1.0
            and carets.count(1.0) == 0, str(carets))
    p.set(hud, "MenuPage", 0)
    _draw(hud)
    p.check("...and back on the menu's rows the page is gone",
            settings.get_visibility() == HIDDEN and panel.get_visibility() == SHOWN)
    # The title held the menu open; the game below starts with it shut.
    p.set(hud, "MenuOpen", False)

    # --- dead ----------------------------------------------------------------------------
    p.set(hud, C.GAME_STARTED_VAR, True)
    p.set(mode, "PlayerDead", True)
    _draw(hud)
    seen = _visible(ui)
    score = _text(ui["UiDeath"].get_editor_property(C.DEATH_SCORE))
    p.check("dead: the death menu replaces the HUD",
            seen["UiDeath"] == SHOWN and body.get_visibility() == HIDDEN
            and seen["UiMain"] == HIDDEN and seen["UiPause"] == HIDDEN, str(seen))
    p.check("...and shows the kill count", score == f"{C.DEATH_SCORE_PREFIX}{KILLS}",
            f"'{score}'")
    p.set(mode, "PlayerDead", False)
    _draw(hud)
    p.check("alive again: the HUD is back and the death menu gone",
            body.get_visibility() == SHOWN and ui["UiDeath"].get_visibility() == HIDDEN)


def _name(p, item):
    return str(p.get(item, "DisplayName")) if item else "-"
