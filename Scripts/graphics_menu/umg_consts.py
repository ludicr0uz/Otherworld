"""The UMG screens' constants: asset paths, the widget names the HUD graph
writes to, what the static widgets say, and the layout.

Constants only. The trees are built by wbp_parts.py, wbp_hud.py and
wbp_screens.py; the HUD writes the live values from its DrawHUD fragments.

Sizes are slate units. UMG multiplies them by the project's DPI curve (the
engine default: 1.0 at a 1080 px shortest side), so the screens scale with the
window instead of staying at canvas pixels. Font sizes are the old canvas
DrawText scale x 10: Roboto's LegacyFontSize is 10, so a DrawText at 2.2 was
22 pt and a 22 pt TextBlock is the same size at 1080p.
"""

from graphics_menu.presets import PRESETS
from graphics_menu.profile_consts import EXIT_ROW_LABEL
from graphics_menu.settings_rows import (
    BACK_LABEL, BIND_LABELS, DIFFICULTY_LABEL, SETTINGS_TITLE, SLIDERS)
from survival.tuning import DEHYDRATED_TAG, STARVING_TAG

UI_DIR = "/Game/UI"
UI_ART_DIR = f"{UI_DIR}/Art"
UI_FONT = "/Engine/EngineFonts/Roboto"

WBP_HUD = f"{UI_DIR}/WBP_HUD"
WBP_MAIN_MENU = f"{UI_DIR}/WBP_MainMenu"
WBP_PAUSE_MENU = f"{UI_DIR}/WBP_PauseMenu"
WBP_DEATH_MENU = f"{UI_DIR}/WBP_DeathMenu"
WBP_MENU_ROW = f"{UI_DIR}/WBP_MenuRow"
WBP_INVENTORY_SLOT = f"{UI_DIR}/WBP_InventorySlot"


def class_path(asset_path):
    """``/Game/UI/WBP_X`` -> ``/Game/UI/WBP_X.WBP_X_C``."""
    name = asset_path.rsplit("/", 1)[1]
    return f"{asset_path}.{name}_C"


# The HUD's references to the four screens: (HUD variable, asset, z-order).
# BeginPlay creates each, adds it to the viewport collapsed, and DrawHUD shows
# whichever the frame calls for. Later z-orders draw on top.
SCREENS = (("UiHud", WBP_HUD, 0),
           ("UiPause", WBP_PAUSE_MENU, 10),
           ("UiMain", WBP_MAIN_MENU, 20),
           ("UiDeath", WBP_DEATH_MENU, 30))
UI_VAR = {asset: var for var, asset, _z in SCREENS}

# The HUD variable that picks the title screens over the game: false until
# NEW GAME (or -nomenu), and BeginPlay pauses the world alongside it.
GAME_STARTED_VAR = "GameStarted"

# What "shown" means. Never Visible: every key is polled off the controller,
# so no widget may take a click or hover away from the game viewport.
SHOWN = "HitTestInvisible"
HIDDEN = "Collapsed"

# ─── The palette ──────────────────────────────────────────────────────────────
COL_TITLE = "(R=0.850000,G=0.900000,B=1.000000,A=1.000000)"
COL_ROW = "(R=0.720000,G=0.750000,B=0.800000,A=1.000000)"
COL_CARET = "(R=1.000000,G=0.820000,B=0.320000,A=1.000000)"
COL_HINT = "(R=0.480000,G=0.510000,B=0.560000,A=1.000000)"
COL_MAIN_HINT = "(R=0.560000,G=0.590000,B=0.650000,A=1.000000)"
COL_LABEL = "(R=0.620000,G=0.650000,B=0.700000,A=1.000000)"
COL_NUMBER = "(R=0.960000,G=0.960000,B=0.970000,A=1.000000)"
COL_GOLD = "(R=1.000000,G=0.870000,B=0.450000,A=1.000000)"
COL_KILL = "(R=0.960000,G=0.860000,B=0.450000,A=0.950000)"
COL_FPS = "(R=0.550000,G=0.950000,B=0.550000,A=0.950000)"
COL_HP_FILL = "(R=0.750000,G=0.130000,B=0.120000,A=0.950000)"
COL_ST_FILL = "(R=0.320000,G=0.720000,B=0.880000,A=0.950000)"
COL_ST_SPENT = "(R=0.820000,G=0.560000,B=0.180000,A=0.950000)"
COL_DEBUFF = "(R=0.950000,G=0.300000,B=0.220000,A=1.000000)"
COL_MAIN_TITLE = "(R=0.920000,G=0.945000,B=1.000000,A=1.000000)"
COL_MAIN_SUB = "(R=0.520000,G=0.560000,B=0.630000,A=1.000000)"
COL_DEATH_TITLE = "(R=0.880000,G=0.220000,B=0.180000,A=1.000000)"
COL_DEATH_TEXT = "(R=0.900000,G=0.900000,B=0.920000,A=1.000000)"
COL_DEATH_HINT = "(R=0.700000,G=0.720000,B=0.760000,A=1.000000)"
COL_EXIT_CALLED_OFF = "(R=0.900000,G=0.300000,B=0.250000,A=1.000000)"

# ─── WBP_MenuRow: caret, label, value ─────────────────────────────────────────
# One row of any menu. The screens set each instance's LabelText, LabelWidth
# and LabelColor in the designer (PreConstruct applies them), and the HUD
# writes Caret's opacity and Value's text per frame.
ROW_CARET, ROW_LABEL_BOX, ROW_LABEL, ROW_VALUE = "Caret", "LabelBox", "Label", "Value"
ROW_TEXT_VAR, ROW_WIDTH_VAR, ROW_COLOR_VAR = "LabelText", "LabelWidth", "LabelColor"
ROW_FONT = 15.0          # the settings page's old 1.5x
ROW_CARET_W = 36.0
ROW_LABEL_W = 284.0      # the settings page's value column, off its labels
ROW_GAP = 14.0           # px under each row

# ─── WBP_InventorySlot ────────────────────────────────────────────────────────
SLOT_BACK, SLOT_ACTIVE, SLOT_ICON, SLOT_AMMO, SLOT_FRAME = (
    "Back", "Active", "Icon", "Ammo", "Frame")
SLOT_W, SLOT_H = 84.0, 59.0
SLOT_GAP = 7.0
SLOT_ICON_W, SLOT_ICON_H, SLOT_ICON_TOP = 78.0, 35.0, 2.0
SLOT_AMMO_FONT = 12.0
SLOT_AMMO_RIGHT, SLOT_AMMO_BOTTOM = 6.0, 3.0

# ─── WBP_HUD ──────────────────────────────────────────────────────────────────
# Body holds everything the death and title screens hide; Fps sits beside it
# because the debug readout shows on every screen.
HUD_BODY, HUD_FPS = "Body", "Fps"
HP_BAR, HP_NUM = "HpBar", "HpNum"
KILLS = "Kills"
BANNER_COUNT, BANNER_OFF = "BannerCount", "BannerOff"
SLOTS, EQUIPPED_NAME = "Slots", "EquippedName"
STAMINA_BAR = "StaminaBar"


def stat_bar(stat):
    """The survival bar for ``stat`` (Hunger -> HungerBar)."""
    return f"{stat}Bar"


def debuff_text(stat):
    """The debuff name beside ``stat``'s bar (Hunger -> HungerDebuff)."""
    return f"{stat}Debuff"


# (stat, label, fill colour): hunger, thirst and temperature, standing as
# vertical bars in the bottom-left corner -- they change over minutes and are
# read at a glance.
SURVIVAL_BARS = (
    ("Hunger", "FOOD", "(R=0.860000,G=0.580000,B=0.220000,A=0.950000)"),
    ("Thirst", "H2O", "(R=0.200000,G=0.480000,B=1.000000,A=0.950000)"),
    ("Temperature", "TEMP", "(R=0.920000,G=0.360000,B=0.260000,A=0.950000)"),
)
# (tag, label, the bar it sits beside)
DEBUFF_LABELS = ((STARVING_TAG, "STARVING", "Hunger"),
                 (DEHYDRATED_TAG, "DEHYDRATED", "Thirst"))

# Each bar, its icon and (HP) its number sit in one group widget, and the
# group is what flashes while the bar is low (hud_flash.py).
HP_GROUP, ST_GROUP = "HpStat", "StaStat"
HP_ICON, ST_ICON = "HpIcon", "StaIcon"
STAT_ICON = 24.0                 # px square, beside every bar


def stat_group(stat):
    """The column holding ``stat``'s bar and icon (Hunger -> HungerStat)."""
    return f"{stat}Stat"


def stat_icon(stat):
    """``stat``'s icon widget (Hunger -> HungerIcon)."""
    return f"{stat}Icon"


def flash_groups():
    """{group widget: the bar it blinks for}, every bar on the HUD."""
    groups = {HP_GROUP: HP_BAR, ST_GROUP: STAMINA_BAR}
    groups.update({stat_group(s): stat_bar(s) for s, _l, _c in SURVIVAL_BARS})
    return groups


# Bottom centre, under the inventory grid: HP then stamina, side by side.
VITALS = "Vitals"
HP_BAR_SIZE = (200.0, 18.0)
HP_NUM_FONT = 17.0
ST_BAR_SIZE = (200.0, 14.0)
VITALS_OVER = 10.0               # between the grid and the row
VITALS_GAP = 24.0                # between the HP group and the stamina group
ICON_GAP = 6.0                   # between an icon and its bar
# Bottom-left: the survival columns, the debuff names stacked above them.
SURVIVAL = "Survival"
SV_BAR_SIZE = (16.0, 140.0)
SV_COLUMN_GAP = 14.0
SV_LABEL_FONT, DEBUFF_FONT = 10.0, 11.0
CORNER_MARGIN = 40.0             # the kill counter and FPS, in from the right
SURVIVAL_LEFT = 24.0             # the survival columns, in from the left
FPS_TOP, FPS_FONT = 40.0, 16.0
KILLS_TOP, KILLS_FONT = 92.0, 22.0
BANNER_TOP, BANNER_FONT = 150.0, 20.0
STRIP_BOTTOM = 22.0              # the vitals' and the survival bars' bottom edge
INVENTORY_COLUMNS = 5
EQUIPPED_FONT, EQUIPPED_GAP = 17.0, 8.0

# A bar under LOW_FRACTION of its maximum blinks its group: FLASH_HZ times a
# second, down to FLASH_DIM opacity for half of each blink. Real time, so it
# still blinks with the M panel open over a paused game.
LOW_FRACTION = 0.25
FLASH_HZ = 2.0
FLASH_DIM = 0.25

# ─── WBP_MainMenu: the title page and the settings page ───────────────────────
TITLE_PANEL, TITLE_ROWS = "TitlePanel", "TitleRows"
SETTINGS_PANEL, SETTINGS_ROWS_BOX = "SettingsPanel", "SettingsRows"
HINT_IDLE, HINT_CAPTURE = "HintIdle", "HintCapture"
GAME_TITLE = "OTHERWORLD"
GAME_SUBTITLE = "a night in the forest"
MENU_ROWS = ("NEW GAME", "SETTINGS")
MAIN_HINT = "UP / DOWN  ·  ENTER selects"
MAIN_PANEL_SIZE = (600.0, 346.0)
MAIN_TITLE_FONT, MAIN_SUB_FONT, MAIN_HINT_FONT = 34.0, 14.0, 12.0
MAIN_ROW_SCALE = 1.4             # the title rows, bigger than the settings rows
MAIN_ROW_LABEL_W = 170.0
SETTINGS_ROW_LABELS = (tuple(sl.label for sl in SLIDERS) + (DIFFICULTY_LABEL,)
                       + BIND_LABELS + (BACK_LABEL,))
SETTINGS_TITLE_TEXT = SETTINGS_TITLE
SETTINGS_PANEL_W = 620.0
SET_TITLE_FONT, SET_HINT_FONT = 22.0, 12.0
HINT_IDLE_TEXT = "arrows adjust  ·  ENTER rebinds"
HINT_CAPTURE_TEXT = "press any key to bind it"

# ─── WBP_PauseMenu: the M panel ───────────────────────────────────────────────
PAUSE_ROWS = "PauseRows"
MENU_KEY, DEBUG_KEY = "M", "D"
PAUSE_TITLE = "GRAPHICS QUALITY"
PAUSE_ROW_LABELS = (tuple(f"[{i + 1}]   {p.label}" for i, p in enumerate(PRESETS))
                    + (f"[{DEBUG_KEY}]   debug", EXIT_ROW_LABEL))
PAUSE_DEBUG_ROW = len(PRESETS)
PAUSE_HINT = f"[{MENU_KEY}]   close"
PAUSE_POS, PAUSE_W = (60.0, 130.0), 600.0
PAUSE_TITLE_FONT, PAUSE_HINT_FONT = 22.0, 15.0
PAUSE_ROW_LABEL_W = 300.0
PAUSE_ROW_SCALE = 1.25
DEBUG_ON, DEBUG_OFF = "ON", "OFF"

# ─── WBP_DeathMenu ────────────────────────────────────────────────────────────
DEATH_SCORE = "Score"
RESTART_KEY = "R"
DEATH_TITLE = "YOU DIED"
DEATH_SCORE_PREFIX = "NPCs killed:  "
DEATH_HINT = f"[{RESTART_KEY}]   try again"
DEATH_PANEL_SIZE = (560.0, 300.0)
DEATH_TITLE_FONT, DEATH_SCORE_FONT, DEATH_HINT_FONT = 34.0, 22.0, 16.0

# Inside every panel, between its artwork's edge and its content.
PANEL_PADDING = (40.0, 28.0, 40.0, 24.0)
