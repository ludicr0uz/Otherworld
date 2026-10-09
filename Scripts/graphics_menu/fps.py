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

from uebp.vars import declare
from graphics_menu import hud_vars as MV
from uebp.graph import _connect, _node, _pin, _set, else_, out, then
from graphics_menu.ui_graph import part, set_text
from graphics_menu.umg_consts import HUD_FPS, WBP_HUD

FPS_FRAMES_VAR, FPS_SINCE_VAR, FPS_SHOWN_VAR = MV.FPS
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
    declare(ed, MV.FPS)


def author_fps(ed, in_execs):
    """Count the frame, maybe refresh, show. Returns the exec pins out."""
    made = []

    def keep(n):
        made.append(n)
        return n

    def get(var):
        return out(keep(ed.add_get_member_variable_node(var)), var)

    # FpsFrames += 1
    plus = keep(_node(ed, _FN_ADD_II))
    _connect(get(FPS_FRAMES_VAR), _pin(plus, "A"))
    _set(plus, "B", 1)
    count = keep(ed.add_set_member_variable_node(FPS_FRAMES_VAR))
    _connect(out(plus), _pin(count, FPS_FRAMES_VAR))
    for e in in_execs:
        _connect(e, _pin(count, "execute"))

    # Window closed? elapsed = now - FpsSince > FPS_WINDOW_S
    now = out(keep(_node(ed, _FN_REAL_TIME)))
    elapsed = keep(_node(ed, _FN_SUB))
    _connect(now, _pin(elapsed, "A"))
    _connect(get(FPS_SINCE_VAR), _pin(elapsed, "B"))
    elapsed_out = out(elapsed)
    due = keep(_node(ed, _FN_GREATER))
    _connect(elapsed_out, _pin(due, "A"))
    _set(due, "B", FPS_WINDOW_S)
    refresh = keep(ed.add_branch_node())
    _connect(out(due), _pin(refresh, "Condition"))
    _connect(then(count), _pin(refresh, "execute"))

    # FpsShown = round(FpsFrames / elapsed); FpsFrames = 0; FpsSince = now
    frames = keep(_node(ed, _FN_CONV_INT))
    _connect(get(FPS_FRAMES_VAR), _pin(frames, "InInt"))
    rate = keep(_node(ed, _FN_DIV))
    _connect(out(frames), _pin(rate, "A"))
    _connect(elapsed_out, _pin(rate, "B"))
    rounded = keep(_node(ed, _FN_ROUND))
    _connect(out(rate), _pin(rounded, "A"))
    shown = keep(ed.add_set_member_variable_node(FPS_SHOWN_VAR))
    _connect(out(rounded), _pin(shown, FPS_SHOWN_VAR))
    _connect(then(refresh), _pin(shown, "execute"))
    reset = keep(ed.add_set_member_variable_node(FPS_FRAMES_VAR))
    _set(reset, FPS_FRAMES_VAR, 0)
    _connect(then(shown), _pin(reset, "execute"))
    since = keep(ed.add_set_member_variable_node(FPS_SINCE_VAR))
    _connect(now, _pin(since, FPS_SINCE_VAR))
    _connect(then(reset), _pin(since, "execute"))

    # "FPS  60", in WBP_HUD's top-right corner above the kill counter.
    as_text = keep(_node(ed, _FN_INT_TO_STR))
    _connect(get(FPS_SHOWN_VAR), _pin(as_text, "InInt"))
    line = keep(_node(ed, _FN_CONCAT))
    _set(line, "A", FPS_PREFIX)
    _connect(out(as_text), _pin(line, "B"))
    readout = part(ed, WBP_HUD, HUD_FPS)
    wrote = set_text(ed, readout, out(line), [then(since), else_(refresh)])

    ed.add_comment_to_nodes(
        f"FPS readout (always, debug mode or not): frames counted over "
        f"{FPS_WINDOW_S}s of real time, so it keeps counting under the paused "
        "menus. Drawn here rather than with `stat fps`, which is a toggle.",
        made)
    # Never shown or hidden from here: the widget is visible in the designer
    # (wbp_hud.py) and stays so.
    return (wrote,)
