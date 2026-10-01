"""verify_graphics_menu.py's checks for the proprietary notices: the title
screen's LegalNotice and the HUD's Watermark (legal_consts, wbp_legal)."""

import unreal

from graphics_menu import legal_consts as L
from graphics_menu import umg_consts as C
from graphics_menu.umg_checks import _tree

SHOWN = unreal.SlateVisibility.HIT_TEST_INVISIBLE


def _lines(w):
    return [str(t.get_editor_property("text")) for t in w.get_all_children()] if w else []


def _place(w):
    """(anchors, alignment, position) of a canvas child."""
    if not w:
        return None
    s = w.get_editor_property("slot")
    a = s.get_anchors()
    return ((a.minimum.x, a.minimum.y, a.maximum.x, a.maximum.y),
            (s.get_alignment().x, s.get_alignment().y),
            (s.get_position().x, s.get_position().y))


def _parent(w):
    return str(w.get_parent().get_name()) if w and w.get_parent() else None


def check_legal(check):
    main, hud = _tree(C.WBP_MAIN_MENU), _tree(C.WBP_HUD)
    notice = main.get(L.LEGAL_NOTICE, (None, False))[0]
    mark = hud.get(L.WATERMARK, (None, False))[0]

    words = _lines(notice)
    check("the title screen carries the copyright line over the confidentiality line",
          words == [L.LEGAL_COPYRIGHT_TEXT, L.LEGAL_CONFIDENTIAL_TEXT], str(words))
    check("...which name Ellivian Inc. and forbid sharing the build",
          "Ellivian Inc." in L.LEGAL_COPYRIGHT_TEXT
          and "All rights reserved" in L.LEGAL_COPYRIGHT_TEXT
          and "Do not distribute" in L.LEGAL_CONFIDENTIAL_TEXT)
    place = _place(notice)
    check("...anchored bottom centre",
          place == ((0.5, 1.0, 0.5, 1.0), (0.5, 1.0), (0.0, -L.LEGAL_BOTTOM)), str(place))
    check("...outside both panels, so it shows on the title and the settings page",
          _parent(notice) == "Root", str(_parent(notice)))

    words = _lines(mark)
    want = [text for _name, text in L.watermark_lines()]
    check("the HUD's watermark says ELLIVIAN INC. · CONFIDENTIAL, then who the build "
          "was given to when WATERMARK_RECIPIENT is set",
          words == want and want[0] == L.WATERMARK_TEXT
          and len(want) == (2 if L.WATERMARK_RECIPIENT.strip() else 1)
          and all(L.WATERMARK_RECIPIENT.strip() in t for t in want[1:]), str(words))
    place = _place(mark)
    check("...anchored bottom right",
          place == ((1.0, 1.0, 1.0, 1.0), (1.0, 1.0),
                    (-L.WATERMARK_RIGHT, -L.WATERMARK_BOTTOM)), str(place))
    check("...outside Body, so it shows over every screen",
          _parent(mark) == "Root", str(_parent(mark)))
    opacity = mark.get_editor_property("render_opacity") if mark else None
    check("...at a low opacity", opacity is not None
          and abs(opacity - L.WATERMARK_OPACITY) < 1e-4 and opacity <= 0.5, str(opacity))
    sizes = [t.get_editor_property("font").get_editor_property("size")
             for w in (notice, mark) if w for t in w.get_all_children()]
    check("both notices are set small", bool(sizes) and max(sizes) <= 14, str(sizes))
    seen = {n: str(w.get_editor_property("visibility")) for n, w in
            ((L.LEGAL_NOTICE, notice), (L.WATERMARK, mark)) if w}
    check("both notices are HitTestInvisible: neither takes a click or a hover",
          notice is not None and mark is not None
          and all(w.get_editor_property("visibility") == SHOWN for w in (notice, mark)),
          str(seen))
    # The strip stands on the bottom centre and the loot window hangs off the
    # middle of the right edge; the watermark keeps to the corner below it.
    loot = _place(hud.get("LootPanel", (None, False))[0])
    strip = _place(hud.get("Strip", (None, False))[0])
    check("the watermark keeps clear of the loot window (right edge, centred) and "
          "the inventory strip (bottom centre)",
          loot is not None and strip is not None
          and loot[0] == (1.0, 0.5, 1.0, 0.5) and loot[1] == (1.0, 0.5)
          and strip[0] == (0.5, 1.0, 0.5, 1.0) and strip[1] == (0.5, 1.0),
          f"loot {loot}, strip {strip}")
