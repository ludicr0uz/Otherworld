"""The FPS readout: WBP_HUD's Fps text, always on screen.

Authored into BP_GraphicsMenuHUD's ReceiveDrawHUD by build_graphics_menu.py,
on every frame of every screen. It is not one of the debug-mode overlays (it
used to be): it shows whether debug mode is on or off.

It used to be the engine's own ``stat fps``, sent once from BeginPlay. That
command is a TOGGLE, not a switch: the stat state lives on the viewport, which
in PIE outlives the session, so every other Play turned the readout *off* --
and there is no console form that asks for "on". Drawing it here leaves
nothing to fall out of step. It sits outside WBP_HUD's Body, so it shows on
the title and death screens too.

The number is frames counted over a half-second window of *real* time
(GetRealTimeSeconds keeps running while the game is paused, which the main
menu and the death menu both are), so it reads steadily instead of flickering
with every frame's delta.
"""

from combat.graph import BEL, _connect, _declare, _float_type, _node, _pin, _set
from graphics_menu.ui_graph import part, set_text
from graphics_menu.umg_consts import HUD_FPS, WBP_HUD

FPS_FRAMES_VAR = "FpsFrames"   # frames drawn since FpsSince
FPS_SINCE_VAR = "FpsSince"     # real time the current window opened
FPS_SHOWN_VAR = "FpsShown"     # what the readout says, rounded
FPS_WINDOW_S = 0.5

FPS_PREFIX = "FPS  "

_FN_REAL_TIME = "/Script/Engine.GameplayStatics.GetRealTimeSeconds"
_FN_ADD_II = "/Script/Engine.KismetMathLibrary.Add_IntInt"
_FN_SUB = "/Script/Engine.KismetMathLibrary.Subtract_DoubleDouble"
_FN_GREATER = "/Script/Engine.KismetMathLibrary.Greater_DoubleDouble"
_FN_CONV_INT = "/Script/Engine.KismetMathLibrary.Conv_IntToDouble"
_FN_DIV = "/Script/Engine.KismetMathLibrary.Divide_DoubleDouble"
_FN_ROUND = "/Script/Engine.KismetMathLibrary.Round"
_FN_INT_TO_STR = "/Script/Engine.KismetStringLibrary.Conv_IntToString"
_FN_CONCAT = "/Script/Engine.KismetStringLibrary.Concat_StrStr"


def declare_fps_vars(ed):
    """All three default to zero, which is what add_member_variable leaves."""
    _declare(ed, FPS_FRAMES_VAR, BEL.get_basic_type_by_name("int"))
    _declare(ed, FPS_SINCE_VAR, _float_type())
    _declare(ed, FPS_SHOWN_VAR, BEL.get_basic_type_by_name("int"))


def author_fps(ed, in_execs):
    """Count the frame, maybe refresh, show. Returns the exec pins out."""
    made = []

    def keep(n):
        made.append(n)
        return n

    def get(var):
        return _pin(keep(ed.add_get_member_variable_node(var)), var, is_input=False)

    # FpsFrames += 1
    plus = keep(_node(ed, _FN_ADD_II))
    _connect(get(FPS_FRAMES_VAR), _pin(plus, "A"))
    _set(plus, "B", 1)
    count = keep(ed.add_set_member_variable_node(FPS_FRAMES_VAR))
    _connect(_pin(plus, "ReturnValue", is_input=False), _pin(count, FPS_FRAMES_VAR))
    for e in in_execs:
        _connect(e, _pin(count, "execute"))

    # Window closed? elapsed = now - FpsSince > FPS_WINDOW_S
    now = _pin(keep(_node(ed, _FN_REAL_TIME)), "ReturnValue", is_input=False)
    elapsed = keep(_node(ed, _FN_SUB))
    _connect(now, _pin(elapsed, "A"))
    _connect(get(FPS_SINCE_VAR), _pin(elapsed, "B"))
    elapsed_out = _pin(elapsed, "ReturnValue", is_input=False)
    due = keep(_node(ed, _FN_GREATER))
    _connect(elapsed_out, _pin(due, "A"))
    _set(due, "B", FPS_WINDOW_S)
    refresh = keep(ed.add_branch_node())
    _connect(_pin(due, "ReturnValue", is_input=False), _pin(refresh, "Condition"))
    _connect(BEL.find_then_pin(count), _pin(refresh, "execute"))

    # FpsShown = round(FpsFrames / elapsed); FpsFrames = 0; FpsSince = now
    frames = keep(_node(ed, _FN_CONV_INT))
    _connect(get(FPS_FRAMES_VAR), _pin(frames, "InInt"))
    rate = keep(_node(ed, _FN_DIV))
    _connect(_pin(frames, "ReturnValue", is_input=False), _pin(rate, "A"))
    _connect(elapsed_out, _pin(rate, "B"))
    rounded = keep(_node(ed, _FN_ROUND))
    _connect(_pin(rate, "ReturnValue", is_input=False), _pin(rounded, "A"))
    shown = keep(ed.add_set_member_variable_node(FPS_SHOWN_VAR))
    _connect(_pin(rounded, "ReturnValue", is_input=False), _pin(shown, FPS_SHOWN_VAR))
    _connect(BEL.find_then_pin(refresh), _pin(shown, "execute"))
    reset = keep(ed.add_set_member_variable_node(FPS_FRAMES_VAR))
    _set(reset, FPS_FRAMES_VAR, 0)
    _connect(BEL.find_then_pin(shown), _pin(reset, "execute"))
    since = keep(ed.add_set_member_variable_node(FPS_SINCE_VAR))
    _connect(now, _pin(since, FPS_SINCE_VAR))
    _connect(BEL.find_then_pin(reset), _pin(since, "execute"))

    # "FPS  60", in WBP_HUD's top-right corner above the kill counter.
    as_text = keep(_node(ed, _FN_INT_TO_STR))
    _connect(get(FPS_SHOWN_VAR), _pin(as_text, "InInt"))
    line = keep(_node(ed, _FN_CONCAT))
    _set(line, "A", FPS_PREFIX)
    _connect(_pin(as_text, "ReturnValue", is_input=False), _pin(line, "B"))
    readout = part(ed, WBP_HUD, HUD_FPS)
    wrote = set_text(ed, readout, _pin(line, "ReturnValue", is_input=False),
                     [BEL.find_then_pin(since), BEL.find_else_pin(refresh)])

    ed.add_comment_to_nodes(
        f"FPS readout (always, debug mode or not): frames counted over "
        f"{FPS_WINDOW_S}s of real time, so it keeps counting under the paused "
        "menus. Drawn here rather than with `stat fps`, which is a toggle.",
        made)
    # Never shown or hidden from here: the widget is visible in the designer
    # (wbp_hud.py) and stays so.
    return (wrote,)
