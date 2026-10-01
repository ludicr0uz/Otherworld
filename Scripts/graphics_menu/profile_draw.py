"""What save-and-exit puts on screen: WBP_HUD's banner, top centre.

While the countdown runs, BannerCount reads "SAVING AND EXITING IN  12"
(whole seconds rounded up, so it never reads 0 while waiting); for
EXIT_CALLED_OFF_SHOWN_S after a hit calls it off, BannerOff says why. The
logic is save_exit.py's on Tick; this only reads its variables. The panel's
"save and exit" row is a static label in WBP_PauseMenu.
"""

from combat.graph import BEL, _at, _connect, _node, _pin, _set
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


def author_exit_banner(ed, x0, y0, in_execs):
    """The countdown, or the called-off notice, or neither. Returns the exec tails."""
    made = []

    def keep(n):
        made.append(n)
        return n

    def get(var, px, py):
        return _pin(keep(_at(ed.add_get_member_variable_node(var), px, py)), var,
                    is_input=False)

    br = keep(_at(ed.add_branch_node(), x0, y0))
    _connect(get(EXIT_PENDING_VAR, x0 - 240, y0 + 200), _pin(br, "Condition"))
    for e in in_execs:
        _connect(e, _pin(br, "execute"))
    now = _pin(keep(_at(_node(ed, FN_TIME_SECONDS), x0, y0 + 600)), "ReturnValue",
               is_input=False)
    count = part(ed, WBP_HUD, BANNER_COUNT, x0 + 960, y0 + 600)
    called_off = part(ed, WBP_HUD, BANNER_OFF, x0 + 960, y0 + 800)

    # --- the countdown -----------------------------------------------------
    remaining = keep(_at(_node(ed, FN_SUB), x0 + 240, y0 + 400))
    _connect(get(EXIT_AT_VAR, x0, y0 + 400), _pin(remaining, "A"))
    _connect(now, _pin(remaining, "B"))
    whole = keep(_at(_node(ed, FN_CEIL), x0 + 480, y0 + 400))
    _connect(_pin(remaining, "ReturnValue", is_input=False), _pin(whole, "A"))
    digits = keep(_at(_node(ed, FN_INT_TO_STR), x0 + 720, y0 + 400))
    _connect(_pin(whole, "ReturnValue", is_input=False), _pin(digits, "InInt"))
    line = keep(_at(_node(ed, FN_CONCAT), x0 + 960, y0 + 400))
    _set(line, "A", EXIT_BANNER_PREFIX)
    _connect(_pin(digits, "ReturnValue", is_input=False), _pin(line, "B"))
    flow = set_text(ed, count, _pin(line, "ReturnValue", is_input=False),
                    [BEL.find_then_pin(br)], x0 + 1200, y0)
    flow = set_shown(ed, count, True, [flow], x0 + 1460, y0)
    counting = set_shown(ed, called_off, False, [flow], x0 + 1720, y0)

    # --- or, for a moment after a hit, why it stopped -------------------------
    idle = set_shown(ed, count, False, [BEL.find_else_pin(br)], x0 + 1200, y0 + 1000)
    ago = keep(_at(_node(ed, FN_SUB), x0 + 240, y0 + 1000))
    _connect(now, _pin(ago, "A"))
    _connect(get(EXIT_CALLED_OFF_VAR, x0, y0 + 1000), _pin(ago, "B"))
    recent = keep(_at(_node(ed, FN_LESS), x0 + 480, y0 + 1000))
    _connect(_pin(ago, "ReturnValue", is_input=False), _pin(recent, "A"))
    _set(recent, "B", EXIT_CALLED_OFF_SHOWN_S)
    tails = show_if(ed, called_off, _pin(recent, "ReturnValue", is_input=False),
                    [idle], x0 + 1460, y0 + 1000)
    ed.add_comment_to_nodes(
        "Save and exit: the countdown while it runs, and for "
        f"{EXIT_CALLED_OFF_SHOWN_S:.0f} s after a hit calls it off, why it stopped.",
        made)
    return [counting, *tails]
