"""WBP_HUD: the in-game overlay's layout.

  Body   (hidden on the title and death screens)
    bottom left   the FOOD / H2O / TEMP bars, standing vertical, each over its
                  icon; the debuff names stacked above them
    top right     the kill counter
    top centre    the save-and-exit countdown, or why it was called off
    bottom centre the equipped weapon's name, the 2 x 5 inventory grid of
                  WBP_InventorySlot, and under it HP and stamina side by side
    right edge    the loot window, and under the reticle its prompt (wbp_loot.py)
  Fps    (debug mode, on every screen)

Every bar has a stat icon beside it (ui_art/stat_icons.py), tinted its fill
colour, and sits with it in one group widget (HpStat, StaStat, <Stat>Stat)
that the HUD blinks while the bar is low (hud_flash.py).

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
from graphics_menu.wbp_loot import author_loot_widgets
from graphics_menu.umg_consts import (
    BANNER_COUNT, BANNER_FONT, BANNER_OFF, BANNER_TOP, COL_EXIT_CALLED_OFF, COL_FPS,
    COL_GOLD, COL_HP_FILL, COL_KILL, COL_LABEL, COL_NUMBER, COL_DEBUFF, COL_ST_FILL,
    CORNER_MARGIN, DEBUFF_FONT, DEBUFF_LABELS, EQUIPPED_FONT, EQUIPPED_GAP, EQUIPPED_NAME,
    FPS_FONT, FPS_TOP, HP_BAR, HP_BAR_SIZE, HP_GROUP, HP_ICON, HP_NUM, HP_NUM_FONT,
    HUD_BODY, HUD_FPS, ICON_GAP, INVENTORY_COLUMNS, KILLS, KILLS_FONT, KILLS_TOP,
    SLOT_GAP, SLOTS, STAMINA_BAR, STAT_ICON, STRIP_BOTTOM, ST_BAR_SIZE, ST_GROUP,
    ST_ICON, SURVIVAL, SURVIVAL_BARS, SURVIVAL_LEFT, SV_BAR_SIZE, SV_COLUMN_GAP,
    SV_LABEL_FONT, VITALS, VITALS_GAP, VITALS_OVER, WBP_HUD, WBP_INVENTORY_SLOT,
    debuff_text, stat_bar, stat_group, stat_icon,
)
from ui_art.stat_icons import stat_icon_name

DEBUFF_OF = {stat: label for _tag, label, stat in DEBUFF_LABELS}


def _icon(bp, parent, name, stat, tint):
    return U.image(bp, parent, name, stat_icon_name(stat), (STAT_ICON, STAT_ICON),
                   tint=tint)


def _author_survival(bp, body):
    """Bottom left: one column per survival stat -- its bar filling upwards,
    its icon and its label under it -- with the debuff names above them."""
    stack = U.add(bp, unreal.VerticalBox, SURVIVAL, body)
    U.at(stack, (0.0, 1.0), (0.0, 1.0), (SURVIVAL_LEFT, -STRIP_BOTTOM))
    for _tag, label, stat in DEBUFF_LABELS:
        name = U.text(bp, stack, debuff_text(stat), label, DEBUFF_FONT, COL_DEBUFF,
                      variable=True)
        U.pad(name, bottom=4.0)
        U.hide(name)

    row = U.add(bp, unreal.HorizontalBox, "SurvivalBars", stack)
    for i, (stat, label, fill) in enumerate(SURVIVAL_BARS):
        col = U.add(bp, unreal.VerticalBox, stat_group(stat), row, variable=True)
        U.pad(col, left=0.0 if i == 0 else SV_COLUMN_GAP, v="Bottom")
        sv = U.bar(bp, col, stat_bar(stat), SV_BAR_SIZE, fill, vertical=True)
        U.pad(sv.get_parent(), h="Center")
        icon = _icon(bp, col, stat_icon(stat), stat, fill)
        U.pad(icon, top=ICON_GAP, h="Center")
        caption = U.text(bp, col, f"{stat}Label", label, SV_LABEL_FONT, COL_LABEL)
        U.pad(caption, top=2.0, h="Center")


def _author_vitals(bp, strip):
    """Under the grid: HP (icon, bar, number) and stamina (icon, bar)."""
    row = U.add(bp, unreal.HorizontalBox, VITALS, strip)
    U.pad(row, top=VITALS_OVER, h="Center")

    hp = U.add(bp, unreal.HorizontalBox, HP_GROUP, row, variable=True)
    U.pad(hp, v="Center")
    icon = _icon(bp, hp, HP_ICON, "Health", COL_HP_FILL)
    U.pad(icon, right=ICON_GAP, v="Center")
    bar = U.bar(bp, hp, HP_BAR, HP_BAR_SIZE, COL_HP_FILL)
    U.pad(bar.get_parent(), v="Center")
    num = U.text(bp, hp, HP_NUM, "100", HP_NUM_FONT, COL_NUMBER, variable=True)
    U.pad(num, left=8.0, v="Center")

    st = U.add(bp, unreal.HorizontalBox, ST_GROUP, row, variable=True)
    U.pad(st, left=VITALS_GAP, v="Center")
    icon = _icon(bp, st, ST_ICON, "Stamina", COL_ST_FILL)
    U.pad(icon, right=ICON_GAP, v="Center")
    bar = U.bar(bp, st, STAMINA_BAR, ST_BAR_SIZE, COL_ST_FILL)
    U.pad(bar.get_parent(), v="Center")


def _author_strip(bp, body):
    """The equipped name, the grid and the vitals, stood on the bottom edge."""
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
    _author_vitals(bp, strip)


def build_hud_widget():
    bp = U.widget_blueprint(WBP_HUD)
    root = U.add(bp, unreal.CanvasPanel, "Root")
    body = U.add(bp, unreal.CanvasPanel, HUD_BODY, root, variable=True)
    U.fill_parent(body)
    _author_survival(bp, body)

    kills = U.text(bp, body, KILLS, "KILLS  0", KILLS_FONT, COL_KILL, variable=True)
    U.at(kills, (1.0, 0.0), (1.0, 0.0), (-CORNER_MARGIN, KILLS_TOP))
    for name, label, col in ((BANNER_COUNT, "", COL_GOLD),
                             (BANNER_OFF, EXIT_CALLED_OFF_TEXT, COL_EXIT_CALLED_OFF)):
        banner = U.text(bp, body, name, label, BANNER_FONT, col, variable=True)
        U.at(banner, (0.5, 0.0), (0.5, 0.0), (0.0, BANNER_TOP))
        U.hide(banner)
    _author_strip(bp, body)
    author_loot_widgets(bp, body)

    fps = U.text(bp, root, HUD_FPS, "FPS  60", FPS_FONT, COL_FPS, variable=True)
    U.at(fps, (1.0, 0.0), (1.0, 0.0), (-CORNER_MARGIN, FPS_TOP))
    U.hide(fps)
    return U.compile_and_save(bp)
