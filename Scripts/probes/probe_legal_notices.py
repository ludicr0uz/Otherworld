"""The proprietary notices on the live screens, and how they look. Needs a window:

    python3 Scripts/dev/uepy.py --game --windowed --probe Scripts/probes/probe_legal_notices.py

The title screen's LegalNotice and the HUD's Watermark are static designer
text (graphics_menu/legal_consts.py), so the probe only reads that they are on
the live widgets and shown, then saves each screen with `shot showui` to
Saved/Screenshots/MacEditor/ for a look: the title page, the settings page
and the game (the watermark beside the inventory strip).
"""

import unreal

from graphics_menu import legal_consts as L
from graphics_menu import umg_consts as C
from graphics_menu.settings_rows import PAGE_SETTINGS, PAGE_TITLE

HUD_BP_PATH = "/Game/UI/BP_GraphicsMenuHUD"
WRITABLE = [(HUD_BP_PATH, v) for v in (C.GAME_STARTED_VAR, "MenuPage")]
SHOWN = unreal.SlateVisibility.HIT_TEST_INVISIBLE


def _find(screen, sibling, name):
    """A child of the screen's Root canvas, by name. The notices are not
    variables, and a live UserWidget exposes no tree to Python, so Root is
    reached as the parent of ``sibling``, a variable that sits on it."""
    root = screen.get_editor_property(sibling).get_parent()
    for w in root.get_all_children():
        if str(w.get_name()) == name:
            return w
    return None


def _lines(w):
    return [str(t.get_text()) for t in w.get_all_children()] if w else []


def _shot(p, what):
    unreal.SystemLibrary.execute_console_command(p.world(), "shot showui")
    p.note(f"shot showui: {what}")


def probe(p):
    yield lambda: p.hud() is not None and p.get(p.hud(), "UiHud") is not None
    if "-nullrhi" in str(unreal.SystemLibrary.get_command_line()).lower():
        p.check("this probe has a window to draw the screens in (run with --windowed)",
                False, "-nullrhi")
        return
    yield 0.5
    hud = p.hud()
    main, overlay = p.get(hud, C.UI_VAR[C.WBP_MAIN_MENU]), p.get(hud, "UiHud")
    notice, mark = (_find(main, C.TITLE_PANEL, L.LEGAL_NOTICE),
                    _find(overlay, C.HUD_BODY, L.WATERMARK))

    # --- the title page, then the settings page ----------------------------------
    p.set(hud, C.GAME_STARTED_VAR, False)
    p.set(hud, "MenuPage", PAGE_TITLE)
    yield 0.5
    p.check("the title screen shows the copyright and confidentiality lines",
            _lines(notice) == [L.LEGAL_COPYRIGHT_TEXT, L.LEGAL_CONFIDENTIAL_TEXT]
            and notice.is_visible() and main.is_visible(), str(_lines(notice)))
    want = [text for _name, text in L.watermark_lines()]
    p.check("...under the HUD's watermark, which takes no click",
            _lines(mark) == want and mark.is_visible()
            and mark.get_visibility() == SHOWN and notice.get_visibility() == SHOWN,
            str(_lines(mark)))
    _shot(p, "the title page")
    yield 0.5
    p.set(hud, "MenuPage", PAGE_SETTINGS)
    yield 0.5
    p.check("the notice stays up on the settings page",
            notice.is_visible() and main.is_visible())
    _shot(p, "the settings page")
    yield 0.5

    # --- the game: the watermark beside the strip, then with the loot window -----
    p.set(hud, "MenuPage", PAGE_TITLE)
    p.set(hud, C.GAME_STARTED_VAR, True)
    yield 0.5
    body = overlay.get_editor_property(C.HUD_BODY)
    # is_visible reads a widget's own flag, not its parents': the notice goes
    # with its screen.
    p.check("in play the watermark is still up, with Body, and the notice's screen "
            "is gone",
            mark.is_visible() and body.is_visible() and not main.is_visible(),
            f"mark {mark.is_visible()} body {body.is_visible()} "
            f"main menu {main.is_visible()}")
    _shot(p, "the game")
    yield 0.5
