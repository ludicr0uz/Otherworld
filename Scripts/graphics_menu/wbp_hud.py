"""WBP_HUD: the in-game overlay's layout.

  Body   (hidden on the title and death screens)
    top left      HP, then the FOOD / H2O / TEMP bars, debuff names beside them
    top right     the kill counter
    top centre    the save-and-exit countdown, or why it was called off
    bottom centre the equipped weapon's name, the 2 x 5 inventory grid of
                  WBP_InventorySlot, and the stamina bar under it
  Fps    (debug mode, on every screen)

Everything is anchored to its corner or edge of the viewport, so none of it is
positioned by arithmetic any more. The values are written by the HUD's DrawHUD
fragments (hud_stats.py, hud_inventory.py, fps.py, profile_draw.py). The
reticle, the scope and the wanderers' bars are still drawn on the HUD canvas:
they are placed per frame from the viewport centre and from world positions.
"""

import unreal

from combat.graph import BEL, _must_load
from combat.tuning import INVENTORY_SIZE
from graphics_menu import umg_author as U
from graphics_menu.profile_consts import EXIT_CALLED_OFF_TEXT
from graphics_menu.umg_consts import (
    BANNER_COUNT, BANNER_FONT, BANNER_OFF, BANNER_TOP, COL_EXIT_CALLED_OFF, COL_FPS,
    COL_GOLD, COL_HP_FILL, COL_KILL, COL_LABEL, COL_NUMBER, COL_DEBUFF, COL_ST_FILL,
    CORNER_MARGIN, DEBUFF_FONT, DEBUFF_LABELS, EQUIPPED_FONT, EQUIPPED_GAP, EQUIPPED_NAME,
    FPS_FONT, FPS_TOP, HP_BAR, HP_BAR_SIZE, HP_LABEL_FONT, HP_NUM, HP_NUM_FONT, HUD_BODY,
    HUD_FPS, INVENTORY_COLUMNS, KILLS, KILLS_FONT, KILLS_TOP, SLOT_GAP, SLOTS,
    STAMINA_BAR, STAT_LABEL_W, STATS_POS, STRIP_BOTTOM, ST_BAR_SIZE, ST_LABEL_FONT,
    ST_LABEL_W, ST_OVER, SURVIVAL_BARS, SV_BAR_SIZE, SV_LABEL_FONT, SV_ROW_GAP,
    WBP_HUD, WBP_INVENTORY_SLOT, debuff_text, stat_bar,
)

DEBUFF_OF = {stat: label for _tag, label, stat in DEBUFF_LABELS}


def _stat_row(bp, parent, name, label, font, top):
    row = U.add(bp, unreal.HorizontalBox, f"{name}Row", parent)
    U.pad(row, top=top)
    box = U.sized(bp, row, f"{name}LabelBox", w=STAT_LABEL_W)
    U.pad(box, v="Center")
    U.text(bp, box, f"{name}Label", label, font, COL_LABEL)
    return row


def _author_stats(bp, body):
    stats = U.add(bp, unreal.VerticalBox, "Stats", body)
    U.at(stats, (0.0, 0.0), (0.0, 0.0), STATS_POS)

    row = _stat_row(bp, stats, "Hp", "HP", HP_LABEL_FONT, 0.0)
    hp = U.bar(bp, row, HP_BAR, HP_BAR_SIZE, COL_HP_FILL)
    U.pad(hp.get_parent(), v="Center")
    num = U.text(bp, row, HP_NUM, "100", HP_NUM_FONT, COL_NUMBER, variable=True)
    U.pad(num, left=20.0, v="Center")

    for stat, label, fill in SURVIVAL_BARS:
        row = _stat_row(bp, stats, stat, label, SV_LABEL_FONT, SV_ROW_GAP)
        sv = U.bar(bp, row, stat_bar(stat), SV_BAR_SIZE, fill)
        U.pad(sv.get_parent(), v="Center")
        if stat in DEBUFF_OF:
            name = U.text(bp, row, debuff_text(stat), DEBUFF_OF[stat], DEBUFF_FONT,
                          COL_DEBUFF, variable=True)
            U.pad(name, left=10.0, v="Center")
            U.hide(name)


def _author_strip(bp, body):
    """The equipped name, the grid and the stamina bar, stood on the bottom edge."""
    strip = U.add(bp, unreal.VerticalBox, "Strip", body)
    U.at(strip, (0.5, 1.0), (0.5, 1.0), (0.0, -STRIP_BOTTOM))

    name = U.text(bp, strip, EQUIPPED_NAME, "", EQUIPPED_FONT, COL_GOLD, variable=True)
    U.pad(name, bottom=EQUIPPED_GAP, h="Center")

    grid = U.add(bp, unreal.UniformGridPanel, SLOTS, strip, variable=True)
    half = SLOT_GAP / 2.0
    grid.set_editor_property("slot_padding", unreal.Margin(half, half, half, half))
    U.pad(grid, h="Center")
    slot_class = BEL.generated_class(_must_load(WBP_INVENTORY_SLOT))
    for i in range(INVENTORY_SIZE):
        cell = U.add(bp, slot_class, f"Slot{i}", grid)
        U.cell(cell, i // INVENTORY_COLUMNS, i % INVENTORY_COLUMNS)

    # The bar centred under the grid: its label on the left is balanced by a
    # spacer as wide on the right.
    row = U.add(bp, unreal.HorizontalBox, "StaminaRow", strip)
    U.pad(row, top=ST_OVER, h="Center")
    box = U.sized(bp, row, "StaLabelBox", w=ST_LABEL_W)
    U.pad(box, v="Center")
    U.text(bp, box, "StaLabel", "STA", ST_LABEL_FONT, COL_LABEL)
    st = U.bar(bp, row, STAMINA_BAR, ST_BAR_SIZE, COL_ST_FILL)
    U.pad(st.get_parent(), v="Center")
    U.sized(bp, row, "StaSpacer", w=ST_LABEL_W)


def build_hud_widget():
    bp = U.widget_blueprint(WBP_HUD)
    root = U.add(bp, unreal.CanvasPanel, "Root")
    body = U.add(bp, unreal.CanvasPanel, HUD_BODY, root, variable=True)
    U.fill_parent(body)
    _author_stats(bp, body)

    kills = U.text(bp, body, KILLS, "KILLS  0", KILLS_FONT, COL_KILL, variable=True)
    U.at(kills, (1.0, 0.0), (1.0, 0.0), (-CORNER_MARGIN, KILLS_TOP))
    for name, label, col in ((BANNER_COUNT, "", COL_GOLD),
                             (BANNER_OFF, EXIT_CALLED_OFF_TEXT, COL_EXIT_CALLED_OFF)):
        banner = U.text(bp, body, name, label, BANNER_FONT, col, variable=True)
        U.at(banner, (0.5, 0.0), (0.5, 0.0), (0.0, BANNER_TOP))
        U.hide(banner)
    _author_strip(bp, body)

    fps = U.text(bp, root, HUD_FPS, "FPS  60", FPS_FONT, COL_FPS, variable=True)
    U.at(fps, (1.0, 0.0), (1.0, 0.0), (-CORNER_MARGIN, FPS_TOP))
    U.hide(fps)
    return U.compile_and_save(bp)
