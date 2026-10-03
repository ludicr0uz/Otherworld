"""What save-and-exit puts on screen: WBP_HUD's banner, top centre.

While the countdown runs, BannerCount reads "SAVING AND EXITING IN  12"
(whole seconds rounded up, so it never reads 0 while waiting); for
EXIT_CALLED_OFF_SHOWN_S after a hit calls it off, BannerOff says why. The
logic is save_exit.py's on Tick; this only reads its variables. The panel's
"save and exit" row is a static label in WBP_PauseMenu.
"""

from combat.graph import BEL, _connect, _node, _pin, _set
from graphics_menu.profile_consts import (
    EXIT_AT_VAR, EXIT_BANNER_PREFIX, EXIT_CALLED_OFF_SHOWN_S, EXIT_CALLED_OFF_VAR,
    EXIT_PENDING_VAR,
)
from graphics_menu.ui_graph import part, set_shown, set_text, show_if
from graphics_menu.umg_consts import BANNER_COUNT, BANNER_OFF, WBP_HUD

FN_TIME_SECONDS = "/Script/Engine.GameplayStatics.GetTimeSeconds"
FN_SUB = "/Script/Engine.KismetMathLibrary.Subtract_DoubleDouble"
FN_LESS = "/Script/Engine.KismetMathLibrary.Less_DoubleDouble"
FN_CEIL = "/Script/Engine.KismetMathLibrary.FCeil"
FN_INT_TO_STR = "/Script/Engine.KismetStringLibrary.Conv_IntToString"
FN_CONCAT = "/Script/Engine.KismetStringLibrary.Concat_StrStr"


def author_exit_banner(ed, in_execs):
    """The countdown, or the called-off notice, or neither. Returns the exec tails."""
    made = []

    def keep(n):
        made.append(n)
        return n

    def get(var):
        return _pin(keep(ed.add_get_member_variable_node(var)), var, is_input=False)

    br = keep(ed.add_branch_node())
    _connect(get(EXIT_PENDING_VAR), _pin(br, "Condition"))
    for e in in_execs:
        _connect(e, _pin(br, "execute"))
    now = _pin(keep(_node(ed, FN_TIME_SECONDS)), "ReturnValue", is_input=False)
    count = part(ed, WBP_HUD, BANNER_COUNT)
    called_off = part(ed, WBP_HUD, BANNER_OFF)

    # --- the countdown -----------------------------------------------------
    remaining = keep(_node(ed, FN_SUB))
    _connect(get(EXIT_AT_VAR), _pin(remaining, "A"))
    _connect(now, _pin(remaining, "B"))
    whole = keep(_node(ed, FN_CEIL))
    _connect(_pin(remaining, "ReturnValue", is_input=False), _pin(whole, "A"))
    digits = keep(_node(ed, FN_INT_TO_STR))
    _connect(_pin(whole, "ReturnValue", is_input=False), _pin(digits, "InInt"))
    line = keep(_node(ed, FN_CONCAT))
    _set(line, "A", EXIT_BANNER_PREFIX)
    _connect(_pin(digits, "ReturnValue", is_input=False), _pin(line, "B"))
    flow = set_text(ed, count, _pin(line, "ReturnValue", is_input=False), [BEL.find_then_pin(br)])
    flow = set_shown(ed, count, True, [flow])
    counting = set_shown(ed, called_off, False, [flow])

    # --- or, for a moment after a hit, why it stopped -------------------------
    idle = set_shown(ed, count, False, [BEL.find_else_pin(br)])
    ago = keep(_node(ed, FN_SUB))
    _connect(now, _pin(ago, "A"))
    _connect(get(EXIT_CALLED_OFF_VAR), _pin(ago, "B"))
    recent = keep(_node(ed, FN_LESS))
    _connect(_pin(ago, "ReturnValue", is_input=False), _pin(recent, "A"))
    _set(recent, "B", EXIT_CALLED_OFF_SHOWN_S)
    tails = show_if(ed, called_off, _pin(recent, "ReturnValue", is_input=False), [idle])
    ed.add_comment_to_nodes(
        "Save and exit: the countdown while it runs, and for "
        f"{EXIT_CALLED_OFF_SHOWN_S:.0f} s after a hit calls it off, why it stopped.",
        made)
    return [counting, *tails]
