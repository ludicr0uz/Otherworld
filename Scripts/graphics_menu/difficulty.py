"""The settings page's DIFFICULTY row and the copy of it gameplay reads.

The choice is BP_Settings.Difficulty, an index into DIFFICULTY_LABELS
(combat/difficulty.py), saved like every other setting. Left/Right cycle it,
wrapping, since three names are a list to walk rather than a number to push
against a floor. The HUD copies it onto the GameMode's Difficulty every
DrawHUD, so GA_ConsumeItem reads one world-scoped int and never loads the save
-- the same push-not-pull shape as the weapon component's settings.
"""

from combat.difficulty import DIFFICULTY_VAR
from uebp.graph import BEL, _connect, _loose_pin, _node, _pin, _set, else_, out, then
from combat.paths import GAME_MODE_CLASS_PATH
from graphics_menu.settings_rows import (
    DIFFICULTY_LABELS, DIFFICULTY_ROW, SETTINGS_CLASS_PATH)
from uebp.nodes.array import FN_ARR_GET
from uebp.nodes.math import FN_ADD_II, FN_AND, FN_EQ_II, FN_MOD_II, FN_SELECT_II
from uebp.nodes.system import FN_IS_VALID

LABELS_VAR = "DifficultyLabels"


def declare_difficulty_vars(ed):
    """The HUD's DifficultyLabels: the names the row shows, indexed like the
    save. Its default is written by the builder's _apply_defaults."""
    ed.remove_member_variable(LABELS_VAR)
    if not ed.add_member_variable(LABELS_VAR, BEL.get_array_type(
            BEL.get_basic_type_by_name("string"))):
        raise RuntimeError(f"could not declare member variable {LABELS_VAR}")


def difficulty_defaults():
    return {LABELS_VAR: list(DIFFICULTY_LABELS)}


def author_difficulty_name(ed, settings_out, made):
    """DifficultyLabels[Settings.Difficulty], as a string pin to draw."""
    level = ed.add_get_member_variable_node(DIFFICULTY_VAR, SETTINGS_CLASS_PATH)
    _connect(settings_out, _pin(level, "self"))
    labels = ed.add_get_member_variable_node(LABELS_VAR)
    name = _node(ed, FN_ARR_GET)
    _connect(out(labels, LABELS_VAR), _loose_pin(name, "TargetArray"))
    _connect(out(level, DIFFICULTY_VAR), _pin(name, "Index"))
    made += [level, labels, name]
    return _loose_pin(name, "Item", is_input=False)


def emit_difficulty_nudge(ed, settings_out, either_out, right_out, in_execs, made):
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
    here = keep(_node(ed, FN_EQ_II))
    _connect(out(keep(ed.add_get_member_variable_node("MenuRow")), "MenuRow"), _pin(here, "A"))
    _set(here, "B", DIFFICULTY_ROW)
    adjusting = keep(_node(ed, FN_AND))
    _connect(either_out, _pin(adjusting, "A"))
    _connect(out(here), _pin(adjusting, "B"))
    cycling = keep(ed.add_branch_node())
    _connect(out(adjusting), _pin(cycling, "Condition"))
    for e in in_execs:
        _connect(e, _pin(cycling, "execute"))

    delta = keep(_node(ed, FN_SELECT_II))
    _set(delta, "A", 1)
    _set(delta, "B", count - 1)
    _connect(right_out, _pin(delta, "bPickA"))
    now = keep(ed.add_get_member_variable_node(DIFFICULTY_VAR, SETTINGS_CLASS_PATH))
    _connect(settings_out, _pin(now, "self"))
    total = keep(_node(ed, FN_ADD_II))
    _connect(out(now, DIFFICULTY_VAR), _pin(total, "A"))
    _connect(out(delta), _pin(total, "B"))
    wrapped = keep(_node(ed, FN_MOD_II))
    _connect(out(total), _pin(wrapped, "A"))
    _set(wrapped, "B", count)
    store = keep(ed.add_set_member_variable_node(DIFFICULTY_VAR, SETTINGS_CLASS_PATH))
    _connect(settings_out, _pin(store, "self"))
    _connect(out(wrapped), _pin(store, DIFFICULTY_VAR))
    _connect(then(cycling), _pin(store, "execute"))
    return then(store), else_(cycling)


def author_push_difficulty(ed, in_exec, mode_out):
    """GameMode.Difficulty = Settings.Difficulty, every DrawHUD.

    Every frame rather than on change: it is one Set, and it means a level
    opened by the death menu's restart (a fresh GameMode at its default) is
    corrected on its first frame without a second code path. Guarded on
    IsValid(Settings), which BeginPlay fills. Returns the exec tails.
    """
    got = ed.add_get_member_variable_node("Settings")
    settings_out = out(got, "Settings")
    ok = _node(ed, FN_IS_VALID)
    _connect(settings_out, _pin(ok, "Object"))
    have = ed.add_branch_node()
    _connect(out(ok), _pin(have, "Condition"))
    _connect(in_exec, _pin(have, "execute"))
    level = ed.add_get_member_variable_node(DIFFICULTY_VAR, SETTINGS_CLASS_PATH)
    _connect(settings_out, _pin(level, "self"))
    push = ed.add_set_member_variable_node(DIFFICULTY_VAR, GAME_MODE_CLASS_PATH)
    _connect(mode_out, _pin(push, "self"))
    _connect(out(level, DIFFICULTY_VAR), _pin(push, DIFFICULTY_VAR))
    _connect(then(have), _pin(push, "execute"))
    ed.add_comment_to_nodes(
        f"The settings' {DIFFICULTY_VAR} onto the GameMode, every frame, so "
        "gameplay (GA_ConsumeItem's easy heal) reads it without the save.",
        [got, ok, have, level, push])
    return then(push), else_(have)
