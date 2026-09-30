"""The settings page's DIFFICULTY row and the copy of it gameplay reads.

The choice is BP_Settings.Difficulty, an index into DIFFICULTY_LABELS
(combat/difficulty.py), saved like every other setting. Left/Right cycle it,
wrapping, since three names are a list to walk rather than a number to push
against a floor. The HUD copies it onto the GameMode's Difficulty every
DrawHUD, so GA_ConsumeItem reads one world-scoped int and never loads the save
-- the same push-not-pull shape as the weapon component's settings.
"""

from combat.difficulty import DIFFICULTY_VAR
from combat.graph import BEL, _at, _connect, _loose_pin, _node, _pin, _set
from combat.paths import GAME_MODE_CLASS_PATH
from graphics_menu.settings_rows import (
    DIFFICULTY_LABELS, DIFFICULTY_ROW, SETTINGS_CLASS_PATH)

LABELS_VAR = "DifficultyLabels"

FN_ADD_II = "/Script/Engine.KismetMathLibrary.Add_IntInt"
FN_AND = "/Script/Engine.KismetMathLibrary.BooleanAND"
FN_ARR_GET = "/Script/Engine.KismetArrayLibrary.Array_Get"
FN_EQ_II = "/Script/Engine.KismetMathLibrary.EqualEqual_IntInt"
FN_IS_VALID = "/Script/Engine.KismetSystemLibrary.IsValid"
FN_MOD_II = "/Script/Engine.KismetMathLibrary.Percent_IntInt"
FN_SELECT_INT = "/Script/Engine.KismetMathLibrary.SelectInt"


def declare_difficulty_vars(ed):
    """The HUD's DifficultyLabels: the names the row shows, indexed like the
    save. Its default is written by the builder's _apply_defaults."""
    ed.remove_member_variable(LABELS_VAR)
    if not ed.add_member_variable(LABELS_VAR, BEL.get_array_type(
            BEL.get_basic_type_by_name("string"))):
        raise RuntimeError(f"could not declare member variable {LABELS_VAR}")


def difficulty_defaults():
    return {LABELS_VAR: list(DIFFICULTY_LABELS)}


def author_difficulty_name(ed, settings_out, x0, y0, made):
    """DifficultyLabels[Settings.Difficulty], as a string pin to draw."""
    level = _at(ed.add_get_member_variable_node(DIFFICULTY_VAR, SETTINGS_CLASS_PATH),
                x0, y0)
    _connect(settings_out, _pin(level, "self"))
    labels = _at(ed.add_get_member_variable_node(LABELS_VAR), x0, y0 + 120)
    name = _at(_node(ed, FN_ARR_GET), x0 + 260, y0)
    _connect(_pin(labels, LABELS_VAR, is_input=False), _loose_pin(name, "TargetArray"))
    _connect(_pin(level, DIFFICULTY_VAR, is_input=False), _pin(name, "Index"))
    made += [level, labels, name]
    return _loose_pin(name, "Item", is_input=False)


def emit_difficulty_nudge(ed, settings_out, either_out, right_out, in_execs,
                          x0, y0, made):
    """Left/Right on DIFFICULTY_ROW: step Difficulty one name either way,
    wrapping. Returns (the stored tail, which the caller saves; the "not this
    row" arm).

    Left adds n-1 rather than subtracting 1, so the modulo never sees a
    negative number (Percent_IntInt keeps the sign of its A).
    """
    def keep(n):
        made.append(n)
        return n

    count = len(DIFFICULTY_LABELS)
    here = keep(_at(_node(ed, FN_EQ_II), x0 + 260, y0 + 480))
    _connect(_pin(keep(_at(ed.add_get_member_variable_node("MenuRow"),
                           x0, y0 + 480)), "MenuRow", is_input=False),
             _pin(here, "A"))
    _set(here, "B", DIFFICULTY_ROW)
    adjusting = keep(_at(_node(ed, FN_AND), x0 + 520, y0 + 200))
    _connect(either_out, _pin(adjusting, "A"))
    _connect(_pin(here, "ReturnValue", is_input=False), _pin(adjusting, "B"))
    cycling = keep(_at(ed.add_branch_node(), x0 + 780, y0))
    _connect(_pin(adjusting, "ReturnValue", is_input=False), _pin(cycling, "Condition"))
    for e in in_execs:
        _connect(e, _pin(cycling, "execute"))

    delta = keep(_at(_node(ed, FN_SELECT_INT), x0 + 780, y0 + 340))
    _set(delta, "A", 1)
    _set(delta, "B", count - 1)
    _connect(right_out, _pin(delta, "bPickA"))
    now = keep(_at(ed.add_get_member_variable_node(DIFFICULTY_VAR,
                                                   SETTINGS_CLASS_PATH),
                   x0 + 780, y0 + 480))
    _connect(settings_out, _pin(now, "self"))
    total = keep(_at(_node(ed, FN_ADD_II), x0 + 1040, y0 + 400))
    _connect(_pin(now, DIFFICULTY_VAR, is_input=False), _pin(total, "A"))
    _connect(_pin(delta, "ReturnValue", is_input=False), _pin(total, "B"))
    wrapped = keep(_at(_node(ed, FN_MOD_II), x0 + 1300, y0 + 400))
    _connect(_pin(total, "ReturnValue", is_input=False), _pin(wrapped, "A"))
    _set(wrapped, "B", count)
    store = keep(_at(ed.add_set_member_variable_node(DIFFICULTY_VAR,
                                                     SETTINGS_CLASS_PATH),
                     x0 + 1560, y0))
    _connect(settings_out, _pin(store, "self"))
    _connect(_pin(wrapped, "ReturnValue", is_input=False), _pin(store, DIFFICULTY_VAR))
    _connect(BEL.find_then_pin(cycling), _pin(store, "execute"))
    return BEL.find_then_pin(store), BEL.find_else_pin(cycling)


def author_push_difficulty(ed, x0, y0, in_exec, mode_out):
    """GameMode.Difficulty = Settings.Difficulty, every DrawHUD.

    Every frame rather than on change: it is one Set, and it means a level
    opened by the death menu's restart (a fresh GameMode at its default) is
    corrected on its first frame without a second code path. Guarded on
    IsValid(Settings), which BeginPlay fills. Returns the exec tails.
    """
    got = _at(ed.add_get_member_variable_node("Settings"), x0, y0 + 240)
    settings_out = _pin(got, "Settings", is_input=False)
    ok = _at(_node(ed, FN_IS_VALID), x0 + 240, y0 + 240)
    _connect(settings_out, _pin(ok, "Object"))
    have = _at(ed.add_branch_node(), x0 + 480, y0)
    _connect(_pin(ok, "ReturnValue", is_input=False), _pin(have, "Condition"))
    _connect(in_exec, _pin(have, "execute"))
    level = _at(ed.add_get_member_variable_node(DIFFICULTY_VAR, SETTINGS_CLASS_PATH),
                x0 + 480, y0 + 400)
    _connect(settings_out, _pin(level, "self"))
    push = _at(ed.add_set_member_variable_node(DIFFICULTY_VAR, GAME_MODE_CLASS_PATH),
               x0 + 740, y0)
    _connect(mode_out, _pin(push, "self"))
    _connect(_pin(level, DIFFICULTY_VAR, is_input=False), _pin(push, DIFFICULTY_VAR))
    _connect(BEL.find_then_pin(have), _pin(push, "execute"))
    ed.add_comment_to_nodes(
        f"The settings' {DIFFICULTY_VAR} onto the GameMode, every frame, so "
        "gameplay (GA_ConsumeItem's easy heal) reads it without the save.",
        [got, ok, have, level, push])
    return BEL.find_then_pin(push), BEL.find_else_pin(have)
