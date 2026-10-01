"""The proprietary notices' widgets (legal_consts has the words and places):
WBP_MainMenu's LegalNotice (called from wbp_screens) and WBP_HUD's Watermark
(called from wbp_hud). Each is a stack of text lines on its screen's Root
canvas, HitTestInvisible so it never takes the cursor from a menu row.
"""

import unreal

from graphics_menu import umg_author as U
from graphics_menu.legal_consts import (
    COL_LEGAL, COL_WATERMARK, LEGAL_BOTTOM, LEGAL_CONFIDENTIAL,
    LEGAL_CONFIDENTIAL_TEXT, LEGAL_COPYRIGHT, LEGAL_COPYRIGHT_TEXT, LEGAL_FONT,
    LEGAL_NOTICE, NOTICE_SHADOW, NOTICE_SHADOW_OFFSET, WATERMARK, WATERMARK_BOTTOM, WATERMARK_FONT, WATERMARK_OPACITY,
    WATERMARK_RIGHT, watermark_lines,
)


def _stack(bp, root, name, lines, size, col, h):
    stack = U.add(bp, unreal.VerticalBox, name, root)
    stack.set_editor_property("visibility", U.visibility("HitTestInvisible"))
    for i, (line, label) in enumerate(lines):
        t = U.text(bp, stack, line, label, size, col)
        t.set_editor_property("shadow_offset", unreal.Vector2D(*NOTICE_SHADOW_OFFSET))
        t.set_editor_property("shadow_color_and_opacity", U.colour(NOTICE_SHADOW))
        U.pad(t, top=0.0 if i == 0 else 2.0, h=h)
    return stack


def author_legal_notice(bp, root):
    """Bottom centre of the main menu, under whichever panel is up."""
    stack = _stack(bp, root, LEGAL_NOTICE,
                   ((LEGAL_COPYRIGHT, LEGAL_COPYRIGHT_TEXT),
                    (LEGAL_CONFIDENTIAL, LEGAL_CONFIDENTIAL_TEXT)),
                   LEGAL_FONT, COL_LEGAL, "Center")
    U.at(stack, (0.5, 1.0), (0.5, 1.0), (0.0, -LEGAL_BOTTOM))
    return stack


def author_watermark(bp, root):
    """Bottom right of the HUD's Root, over every screen."""
    stack = _stack(bp, root, WATERMARK, watermark_lines(), WATERMARK_FONT,
                   COL_WATERMARK, "Right")
    stack.set_editor_property("render_opacity", WATERMARK_OPACITY)
    U.at(stack, (1.0, 1.0), (1.0, 1.0), (-WATERMARK_RIGHT, -WATERMARK_BOTTOM))
    return stack
