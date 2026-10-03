"""DrawHUD: the survival bars -- hunger, thirst and temperature, vertical in
WBP_HUD's bottom-left corner, each blinking when low -- and the name of any
debuff the player is carrying above them. The layout and the bars' colours
are wbp_hud.py's.

The debuff names are shown off the player's AbilitySystemComponent -- the tag
the debuff GameplayEffect granted -- not off "Hunger <= 0". The HUD therefore
says STARVING exactly while the debuff is actually on, which is also exactly
while health is draining, and would say it for a debuff applied by anything
else too.
"""

from uebp.graph import (
    _connect, _loose_pin, _must_load, _node, _palette, _pin, _set, else_, out, then)
from graphics_menu.hud_flash import author_flash
from graphics_menu.ui_graph import part, set_percent, set_shown, show_if
from graphics_menu.umg_consts import (
    DEBUFF_LABELS, SURVIVAL_BARS, WBP_HUD, debuff_text, stat_bar, stat_group,
)
from survival.paths import SURVIVAL_BP_PATH, SURVIVAL_CLASS_PATH
from uebp.nodes.actor import FN_GET_COMP
from uebp.nodes.gas import FN_GET_ASC, FN_TAG_COUNT
from uebp.nodes.math import FN_DIV_FF, FN_GREATER_II
from uebp.nodes.palette import NODE_CAST_SURVIVAL
from uebp.nodes.system import FN_GET_PLAYER_PAWN, FN_IS_VALID


def _author_bar(ed, survival, stat, exec_in):
    """<stat>Bar = stat / Max<stat>; <stat>Stat blinks while it is low."""
    now = ed.add_get_member_variable_node(stat, SURVIVAL_CLASS_PATH)
    _connect(survival, _pin(now, "self"))
    top = ed.add_get_member_variable_node(f"Max{stat}", SURVIVAL_CLASS_PATH)
    _connect(survival, _pin(top, "self"))
    frac = _node(ed, FN_DIV_FF)
    _connect(out(now, stat), _pin(frac, "A"))
    _connect(out(top, f"Max{stat}"), _pin(frac, "B"))
    filled = set_percent(ed, part(ed, WBP_HUD, stat_bar(stat)), out(frac), [exec_in])
    return author_flash(ed, part(ed, WBP_HUD, stat_group(stat)), out(frac), [filled])


def _author_debuff_labels(ed, pawn, exec_in):
    """Each debuff name shown while its tag is on the player. Returns the exec
    pins every path ends on."""
    lookup = _node(ed, FN_GET_ASC)
    _connect(pawn, _pin(lookup, "Actor"))
    asc = out(lookup)
    valid = _node(ed, FN_IS_VALID)
    _connect(asc, _pin(valid, "Object"))
    gate = ed.add_branch_node()
    _connect(out(valid), _pin(gate, "Condition"))
    _connect(exec_in, _pin(gate, "execute"))

    exits = (then(gate),)
    hidden = (else_(gate),)
    for tag, _label, stat in DEBUFF_LABELS:
        count = _node(ed, FN_TAG_COUNT)
        _connect(asc, _pin(count, "self"))
        _set(count, "GameplayTag", f'(TagName="{tag}")')
        on = _node(ed, FN_GREATER_II)
        _connect(out(count), _pin(on, "A"))
        _set(on, "B", 0)
        exits = show_if(ed, part(ed, WBP_HUD, debuff_text(stat)), out(on), exits)
        # No ability system: nothing can be on, so nothing is named.
        hidden = (set_shown(ed, part(ed, WBP_HUD, debuff_text(stat)), False, hidden),)
    ed.add_comment_to_nodes(
        "Any debuff the player's ability system carries, named beside its bar.",
        [lookup, valid, gate])
    return exits + hidden


def author_survival_bars(ed, in_execs):
    """Fill the three bars and name the debuffs. Returns the exec pins to go
    on from -- including the cast-failed pin, so a pawn with no survival
    component still reaches the rest of the HUD."""
    # The cast node is only in the palette once its class is loaded, and the
    # class only exists once build_survival.py has run -- which has to be
    # before this builder.
    _must_load(SURVIVAL_BP_PATH)
    pawn = _node(ed, FN_GET_PLAYER_PAWN)
    _set(pawn, "PlayerIndex", 0)
    pawn_out = out(pawn)
    comp = _node(ed, FN_GET_COMP)
    _connect(pawn_out, _pin(comp, "self"))
    _pin(comp, "ComponentClass").set_pin_value(SURVIVAL_CLASS_PATH)
    cast = _palette(ed, NODE_CAST_SURVIVAL)
    _connect(out(comp), _pin(cast, "Object"))
    for e in in_execs:
        _connect(e, _pin(cast, "execute"))
    survival = _loose_pin(cast, "AsBPSurvivalComponent", is_input=False)

    flow = then(cast)
    for stat, _label, _colour in SURVIVAL_BARS:
        flow = _author_bar(ed, survival, stat, flow)
    exits = _author_debuff_labels(ed, pawn_out, flow)
    return exits + (out(cast, "CastFailed"),)
