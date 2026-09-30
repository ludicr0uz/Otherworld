"""DrawHUD: the survival bars -- hunger, thirst and temperature under the HP
bar in WBP_HUD -- and the name of any debuff the player is carrying beside
them. The layout and the bars' colours are wbp_hud.py's.

The debuff names are shown off the player's AbilitySystemComponent -- the tag
the debuff GameplayEffect granted -- not off "Hunger <= 0". The HUD therefore
says STARVING exactly while the debuff is actually on, which is also exactly
while health is draining, and would say it for a debuff applied by anything
else too.
"""

from combat.graph import (
    BEL, _at, _connect, _loose_pin, _must_load, _node, _palette, _pin, _set,
)
from combat.nodes import FN_GET_ASC, FN_TAG_COUNT
from graphics_menu.ui_graph import part, set_percent, set_shown, show_if
from graphics_menu.umg_consts import (
    DEBUFF_LABELS, SURVIVAL_BARS, WBP_HUD, debuff_text, stat_bar,
)
from survival.paths import (
    NODE_CAST_SURVIVAL, SURVIVAL_BP_PATH, SURVIVAL_CLASS_PATH,
)

FN_DIV = "/Script/Engine.KismetMathLibrary.Divide_DoubleDouble"
FN_GET_COMP = "/Script/Engine.Actor.GetComponentByClass"
FN_GET_PLAYER_PAWN = "/Script/Engine.GameplayStatics.GetPlayerPawn"
FN_GREATER_II = "/Script/Engine.KismetMathLibrary.Greater_IntInt"
FN_IS_VALID = "/Script/Engine.KismetSystemLibrary.IsValid"


def _author_bar(ed, survival, stat, exec_in, x0, y0):
    """<stat>Bar = stat / Max<stat>."""
    now = _at(ed.add_get_member_variable_node(stat, SURVIVAL_CLASS_PATH), x0, y0 + 260)
    _connect(survival, _pin(now, "self"))
    top = _at(ed.add_get_member_variable_node(f"Max{stat}", SURVIVAL_CLASS_PATH),
              x0, y0 + 380)
    _connect(survival, _pin(top, "self"))
    frac = _at(_node(ed, FN_DIV), x0 + 240, y0 + 300)
    _connect(_pin(now, stat, is_input=False), _pin(frac, "A"))
    _connect(_pin(top, f"Max{stat}", is_input=False), _pin(frac, "B"))
    return set_percent(ed, part(ed, WBP_HUD, stat_bar(stat), x0 + 240, y0 + 500),
                       _pin(frac, "ReturnValue", is_input=False), [exec_in],
                       x0 + 700, y0)


def _author_debuff_labels(ed, pawn, exec_in, x0, y0):
    """Each debuff name shown while its tag is on the player. Returns the exec
    pins every path ends on."""
    lookup = _at(_node(ed, FN_GET_ASC), x0, y0 + 300)
    _connect(pawn, _pin(lookup, "Actor"))
    asc = _pin(lookup, "ReturnValue", is_input=False)
    valid = _at(_node(ed, FN_IS_VALID), x0 + 240, y0 + 300)
    _connect(asc, _pin(valid, "Object"))
    gate = _at(ed.add_branch_node(), x0 + 480, y0)
    _connect(_pin(valid, "ReturnValue", is_input=False), _pin(gate, "Condition"))
    _connect(exec_in, _pin(gate, "execute"))

    exits = (BEL.find_then_pin(gate),)
    hidden = (BEL.find_else_pin(gate),)
    for i, (tag, _label, stat) in enumerate(DEBUFF_LABELS):
        x = x0 + 760 + i * 1000
        count = _at(_node(ed, FN_TAG_COUNT), x, y0 + 300)
        _connect(asc, _pin(count, "self"))
        _set(count, "GameplayTag", f'(TagName="{tag}")')
        on = _at(_node(ed, FN_GREATER_II), x + 240, y0 + 300)
        _connect(_pin(count, "ReturnValue", is_input=False), _pin(on, "A"))
        _set(on, "B", 0)
        exits = show_if(ed, part(ed, WBP_HUD, debuff_text(stat), x + 240, y0 + 500),
                        _pin(on, "ReturnValue", is_input=False), exits, x + 480, y0)
        # No ability system: nothing can be on, so nothing is named.
        hidden = (set_shown(ed, part(ed, WBP_HUD, debuff_text(stat), x, y0 + 900),
                            False, hidden, x + 480, y0 + 800),)
    ed.add_comment_to_nodes(
        "Any debuff the player's ability system carries, named beside its bar.",
        [lookup, valid, gate])
    return exits + hidden


def author_survival_bars(ed, x0, y0, in_execs):
    """Fill the three bars and name the debuffs. Returns the exec pins to go
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
    for i, (stat, _label, _colour) in enumerate(SURVIVAL_BARS):
        flow = _author_bar(ed, survival, stat, flow, x0 + 800 + i * 1000, y0)
    exits = _author_debuff_labels(ed, pawn_out, flow, x0 + 3800, y0)
    return exits + (_pin(cast, "CastFailed", is_input=False),)
