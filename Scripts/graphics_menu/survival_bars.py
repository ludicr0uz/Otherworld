"""The survival bars: hunger, thirst and temperature under the stamina bar,
and the name of any debuff the player is carrying beside them.

Same shape as the HP and stamina bars in build_graphics_menu.py -- a track and a
width-driven fill of the shared white T_UI_Bar, tinted per bar -- and the same
left edge and width, so the five read as one readout. Thinner than stamina
(12 px against 14): they change over minutes, not seconds, and are read at a
glance rather than watched.

The debuff labels are read off the player's AbilitySystemComponent -- the tag
the debuff GameplayEffect granted -- not off "Hunger <= 0". The HUD therefore
says STARVING exactly while the debuff is actually on, which is also exactly
while health is draining, and would say it for a debuff applied by anything
else too.
"""

from combat.graph import (
    BEL, _at, _connect, _loose_pin, _must_load, _node, _palette, _pin, _set,
)
from combat.nodes import FN_GET_ASC, FN_TAG_COUNT
from graphics_menu.canvas import UI_FONT, _draw_texture
from survival.paths import (
    NODE_CAST_SURVIVAL, SURVIVAL_BP_PATH, SURVIVAL_CLASS_PATH,
)
from survival.tuning import DEHYDRATED_TAG, STARVING_TAG

FN_DIV = "/Script/Engine.KismetMathLibrary.Divide_DoubleDouble"
FN_DRAW_TEXT = "/Script/Engine.HUD.DrawText"
FN_GET_COMP = "/Script/Engine.Actor.GetComponentByClass"
FN_GET_PLAYER_PAWN = "/Script/Engine.GameplayStatics.GetPlayerPawn"
FN_GREATER_II = "/Script/Engine.KismetMathLibrary.Greater_IntInt"
FN_IS_VALID = "/Script/Engine.KismetSystemLibrary.IsValid"
FN_MUL = "/Script/Engine.KismetMathLibrary.Multiply_DoubleDouble"

# x, w, h of every bar; y per row. The stamina bar ends at y 114.
SV_X, SV_W, SV_H = 60.0, 420.0, 12.0
SV_LABEL_X = 16.0
SV_LABEL_RISE = 4.0
SV_LABEL_SCALE = 1.0
DEBUFF_X = 490.0
DEBUFF_SCALE = 1.1
COL_SV_LABEL = "(R=0.620000,G=0.650000,B=0.700000,A=1.000000)"
COL_DEBUFF = "(R=0.950000,G=0.300000,B=0.220000,A=1.000000)"

# (stat, label, fill colour, y)
SURVIVAL_BARS = (
    ("Hunger", "FOOD", "(R=0.860000,G=0.580000,B=0.220000,A=0.950000)", 122.0),
    ("Thirst", "H2O", "(R=0.200000,G=0.480000,B=1.000000,A=0.950000)", 140.0),
    ("Temperature", "TEMP", "(R=0.920000,G=0.360000,B=0.260000,A=0.950000)", 158.0),
)
# (tag, label, the bar it sits beside)
DEBUFF_LABELS = ((STARVING_TAG, "STARVING", "Hunger"),
                 (DEHYDRATED_TAG, "DEHYDRATED", "Thirst"))
BAR_Y = {stat: y for stat, _label, _col, y in SURVIVAL_BARS}


def _author_bar(ed, survival, stat, label, colour, y, exec_in, x0, y0):
    made = []

    def keep(n):
        made.append(n)
        return n

    now = keep(_at(ed.add_get_member_variable_node(stat, SURVIVAL_CLASS_PATH), x0, y0 + 260))
    _connect(survival, _pin(now, "self"))
    top = keep(_at(ed.add_get_member_variable_node(f"Max{stat}", SURVIVAL_CLASS_PATH),
                   x0, y0 + 380))
    _connect(survival, _pin(top, "self"))
    frac = keep(_at(_node(ed, FN_DIV), x0 + 240, y0 + 300))
    _connect(_pin(now, stat, is_input=False), _pin(frac, "A"))
    _connect(_pin(top, f"Max{stat}", is_input=False), _pin(frac, "B"))
    width = keep(_at(_node(ed, FN_MUL), x0 + 480, y0 + 300))
    _connect(_pin(frac, "ReturnValue", is_input=False), _pin(width, "A"))
    _set(width, "B", SV_W)

    back = keep(_draw_texture(ed, x0 + 240, y0, "T_UI_BarTrack"))
    for name, value in zip(("ScreenX", "ScreenY", "ScreenW", "ScreenH"),
                           (SV_X, y, SV_W, SV_H)):
        _set(back, name, value)
    _connect(exec_in, _pin(back, "execute"))

    fill = keep(_draw_texture(ed, x0 + 480, y0, "T_UI_Bar", tint=colour))
    for name, value in zip(("ScreenX", "ScreenY", "ScreenW", "ScreenH"),
                           (SV_X, y, SV_W, SV_H)):
        _set(fill, name, value)
    _connect(_pin(width, "ReturnValue", is_input=False), _pin(fill, "ScreenW"))
    _connect(BEL.find_then_pin(back), _pin(fill, "execute"))

    text = keep(_at(_node(ed, FN_DRAW_TEXT), x0 + 720, y0))
    _set(text, "Text", label)
    _set(text, "TextColor", COL_SV_LABEL)
    _set(text, "ScreenX", SV_LABEL_X)
    _set(text, "ScreenY", y - SV_LABEL_RISE)
    _set(text, "Scale", SV_LABEL_SCALE)
    _set(text, "bScalePosition", "false")
    _set(text, "Font", UI_FONT)
    _connect(BEL.find_then_pin(fill), _pin(text, "execute"))
    ed.add_comment_to_nodes(f"{label}: {stat} / Max{stat}", made)
    return BEL.find_then_pin(text)


def _author_debuff_labels(ed, pawn, exec_in, x0, y0):
    """Returns the exec pins every path ends on."""
    lookup = _at(_node(ed, FN_GET_ASC), x0, y0 + 300)
    _connect(pawn, _pin(lookup, "Actor"))
    asc = _pin(lookup, "ReturnValue", is_input=False)
    valid = _at(_node(ed, FN_IS_VALID), x0 + 240, y0 + 300)
    _connect(asc, _pin(valid, "Object"))
    gate = _at(ed.add_branch_node(), x0 + 480, y0)
    _connect(_pin(valid, "ReturnValue", is_input=False), _pin(gate, "Condition"))
    _connect(exec_in, _pin(gate, "execute"))
    made = [lookup, valid, gate]

    exits = (BEL.find_then_pin(gate),)
    for i, (tag, label, stat) in enumerate(DEBUFF_LABELS):
        x = x0 + 760 + i * 760
        count = _at(_node(ed, FN_TAG_COUNT), x, y0 + 300)
        _connect(asc, _pin(count, "self"))
        _set(count, "GameplayTag", f'(TagName="{tag}")')
        on = _at(_node(ed, FN_GREATER_II), x + 240, y0 + 300)
        _connect(_pin(count, "ReturnValue", is_input=False), _pin(on, "A"))
        _set(on, "B", 0)
        shown = _at(ed.add_branch_node(), x + 240, y0)
        _connect(_pin(on, "ReturnValue", is_input=False), _pin(shown, "Condition"))
        for e in exits:
            _connect(e, _pin(shown, "execute"))
        text = _at(_node(ed, FN_DRAW_TEXT), x + 480, y0)
        _set(text, "Text", label)
        _set(text, "TextColor", COL_DEBUFF)
        _set(text, "ScreenX", DEBUFF_X)
        _set(text, "ScreenY", BAR_Y[stat] - SV_LABEL_RISE - 2.0)
        _set(text, "Scale", DEBUFF_SCALE)
        _set(text, "bScalePosition", "false")
        _set(text, "Font", UI_FONT)
        _connect(BEL.find_then_pin(shown), _pin(text, "execute"))
        exits = (BEL.find_then_pin(text), BEL.find_else_pin(shown))
        made += [count, on, shown, text]
    ed.add_comment_to_nodes(
        "Any debuff the player's ability system carries, named beside its bar.",
        made)
    return exits + (BEL.find_else_pin(gate),)


def author_survival_bars(ed, x0, y0, in_execs):
    """Draw the three bars and the debuff labels. Returns the exec pins to go
    on from -- including the cast-failed pin, so a pawn with no survival
    component still reaches the rest of the HUD."""
    # The cast node is only in the palette once its class is loaded, and the
    # class only exists once build_survival.py has run -- which has to be
    # before this builder.
    _must_load(SURVIVAL_BP_PATH)
    pawn = _at(_node(ed, FN_GET_PLAYER_PAWN), x0, y0 + 260)
    _set(pawn, "PlayerIndex", 0)
    pawn_out = _pin(pawn, "ReturnValue", is_input=False)
    comp = _at(_node(ed, FN_GET_COMP), x0 + 240, y0 + 260)
    _connect(pawn_out, _pin(comp, "self"))
    _pin(comp, "ComponentClass").set_pin_value(SURVIVAL_CLASS_PATH)
    cast = _at(_palette(ed, NODE_CAST_SURVIVAL), x0 + 500, y0)
    _connect(_pin(comp, "ReturnValue", is_input=False), _pin(cast, "Object"))
    for e in in_execs:
        _connect(e, _pin(cast, "execute"))
    survival = _loose_pin(cast, "AsBPSurvivalComponent", is_input=False)

    flow = BEL.find_then_pin(cast)
    for i, (stat, label, colour, y) in enumerate(SURVIVAL_BARS):
        flow = _author_bar(ed, survival, stat, label, colour, y, flow,
                           x0 + 800 + i * 1000, y0)
    exits = _author_debuff_labels(ed, pawn_out, flow, x0 + 3800, y0)
    return exits + (_pin(cast, "CastFailed", is_input=False),)
