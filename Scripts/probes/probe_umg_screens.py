"""The UMG screens: BeginPlay creates all four and adds them to the viewport,
and each DrawHUD shows the one the game is on and writes the live values in.

A -nullrhi run never renders, so the engine never calls DrawHUD; the probe
calls the HUD's ReceiveDrawHUD event itself, then reads the widgets back. (The
canvas layers -- reticle, scope, wanderers' bars -- log that there is no
canvas when called this way; they are not what this probe is about.) State is
set by writing the HUD's and the game's variables: a probe has no keyboard.
"""

import unreal

from combat.game_state import KILL_COUNT_VAR
from combat.paths import (
    GAME_MODE_BP_PATH, HEALTH_BP_PATH, HEALTH_CLASS_PATH, WEAPON_COMP_CLASS_PATH,
)
from graphics_menu import umg_consts as C
from graphics_menu.settings_rows import DIFFICULTY_LABELS, DIFFICULTY_ROW, FIRST_BIND_ROW
from survival.paths import SURVIVAL_BP_PATH, SURVIVAL_CLASS_PATH

HUD_BP_PATH = "/Game/UI/BP_GraphicsMenuHUD"
WRITABLE = [(HUD_BP_PATH, v) for v in ("MenuOpen", C.GAME_STARTED_VAR, "MenuPage",
                                       "MenuRow", "Quality")]
WRITABLE += [(GAME_MODE_BP_PATH, KILL_COUNT_VAR), (GAME_MODE_BP_PATH, "PlayerDead"),
             (HEALTH_BP_PATH, "Health"), (SURVIVAL_BP_PATH, "Hunger")]

SHOWN = unreal.SlateVisibility.HIT_TEST_INVISIBLE
HIDDEN = unreal.SlateVisibility.COLLAPSED
HEALTH, HUNGER, KILLS = 37.0, 40.0, 4


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
    hud, pawn, mode = p.hud(), p.pawn(), p.game_mode()
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

    items = list(p.get(wc, "Inventory"))
    equipped = p.get(wc, "EquippedIndex")
    grid = ui["UiHud"].get_editor_property(C.SLOTS)
    icons = [grid.get_child_at(i).get_editor_property(C.SLOT_ICON).get_visibility()
             for i in range(grid.get_children_count())]
    p.check("a slot shows an icon exactly when something is carried in it",
            bool(items) and icons == [SHOWN] * len(items) + [HIDDEN] * (len(icons) - len(items)),
            f"{len(items)} carried: {[str(v.name) for v in icons]}")
    lit = [grid.get_child_at(i).get_editor_property(C.SLOT_FRAME).get_visibility() == SHOWN
           for i in range(grid.get_children_count())]
    name = _text(ui["UiHud"].get_editor_property(C.EQUIPPED_NAME))
    p.check("only the equipped slot is lit, and its name is over the grid",
            lit.count(True) == 1 and lit.index(True) == equipped
            and name == str(p.get(items[equipped], "DisplayName")),
            f"lit {lit}, name '{name}', equipped {equipped}")
    counted = [(i, _text(grid.get_child_at(i).get_editor_property(C.SLOT_AMMO)))
               for i, item in enumerate(items) if p.get(item, "UsesAmmo")]
    want = [(i, f"{p.get(it, 'Loaded')} / {p.get(it, 'Reserve')}")
            for i, it in enumerate(items) if p.get(it, "UsesAmmo")]
    p.check("each gun that uses ammunition shows loaded / reserve", counted == want,
            f"{counted} vs {want}")

    # --- the M panel ----------------------------------------------------------------
    p.set(hud, "MenuOpen", True)
    p.set(hud, "Quality", 2)
    _draw(hud)
    rows = ui["UiPause"].get_editor_property(C.PAUSE_ROWS)
    carets = _carets(rows, len(C.PAUSE_ROW_LABELS))
    debug = _text(_row(rows, C.PAUSE_DEBUG_ROW).get_editor_property(C.ROW_VALUE))
    p.check("M opens the panel with the caret on the current preset",
            ui["UiPause"].get_visibility() == SHOWN
            and carets == [0.0, 0.0, 1.0, 0.0, 0.0, 0.0], str(carets))
    p.check("...and the debug row says whether debug mode is on",
            debug == (C.DEBUG_ON if p.get(hud, "DebugOn") else C.DEBUG_OFF), f"'{debug}'")
    p.set(hud, "MenuOpen", False)
    _draw(hud)
    p.check("...and closing it takes it down", ui["UiPause"].get_visibility() == HIDDEN)

    # --- the title page and the settings page ------------------------------------------
    p.set(hud, C.GAME_STARTED_VAR, False)
    p.set(hud, "MenuPage", 0)
    p.set(hud, "MenuRow", 1)
    _draw(hud)
    main = ui["UiMain"]
    title, settings = (main.get_editor_property(C.TITLE_PANEL),
                       main.get_editor_property(C.SETTINGS_PANEL))
    p.check("before a game starts the title page is up, over a hidden HUD",
            main.get_visibility() == SHOWN and title.get_visibility() == SHOWN
            and settings.get_visibility() == HIDDEN and body.get_visibility() == HIDDEN,
            f"main {main.get_visibility()}, body {body.get_visibility()}")
    carets = _carets(main.get_editor_property(C.TITLE_ROWS), len(C.MENU_ROWS))
    p.check("...with the caret on MenuRow's row", carets == [0.0, 1.0], str(carets))

    p.set(hud, "MenuPage", 1)
    p.set(hud, "MenuRow", FIRST_BIND_ROW)
    _draw(hud)
    rows = main.get_editor_property(C.SETTINGS_ROWS_BOX)
    values = [_text(_row(rows, i).get_editor_property(C.ROW_VALUE))
              for i in range(len(C.SETTINGS_ROW_LABELS))]
    p.check("the settings page replaces the title page",
            settings.get_visibility() == SHOWN and title.get_visibility() == HIDDEN)
    p.check("...every setting row shows its value and BACK shows none",
            all(values[:-1]) and values[-1] == ""
            and values[DIFFICULTY_ROW] in DIFFICULTY_LABELS, str(values))
    carets = _carets(rows, len(C.SETTINGS_ROW_LABELS))
    p.check("...and the caret is on MenuRow's row",
            carets.index(1.0) == FIRST_BIND_ROW and carets.count(1.0) == 1, str(carets))

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
