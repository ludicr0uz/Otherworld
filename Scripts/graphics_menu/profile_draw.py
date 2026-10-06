"""What save-and-exit puts on screen: WBP_HUD's banner, top centre.

While the countdown runs, BannerCount reads "SAVING AND EXITING IN  12"
(whole seconds rounded up, so it never reads 0 while waiting); for
EXIT_CALLED_OFF_SHOWN_S after a hit calls it off, BannerOff says why. The
countdown is the weapon component's (combat/weapon_component/save_exit.py);
this only reads its variables, off the owning pawn. The panel's "save and
exit" row is a static label in WBP_PauseMenu.
"""

from uebp.graph import _connect, _loose_pin, _node, _palette, _pin, _set, else_, out, then
from combat.ask_consts import EXIT_AT_VAR, EXIT_CALLED_OFF_VAR, EXIT_PENDING_VAR
from combat.paths import WEAPON_COMP_CLASS_PATH
from graphics_menu.profile_consts import EXIT_BANNER_PREFIX, EXIT_CALLED_OFF_SHOWN_S
from uebp.nodes.actor import FN_GET_COMP, FN_GET_OWNING_PAWN
from uebp.nodes.palette import NODE_CAST_WEAPON
from graphics_menu.ui_graph import part, set_shown, set_text, show_if
from graphics_menu.umg_consts import BANNER_COUNT, BANNER_OFF, WBP_HUD
from uebp.nodes.math import FN_CEIL, FN_LESS_FF, FN_SUB_FF
from uebp.nodes.system import FN_CONCAT, FN_INT_TO_STR, FN_TIME_SECONDS


def author_exit_banner(ed, in_execs):
    """The countdown, or the called-off notice, or neither. Returns the exec tails."""
    made = []

    def keep(n):
        made.append(n)
        return n

    comp = keep(_node(ed, FN_GET_COMP))
    _connect(out(keep(_node(ed, FN_GET_OWNING_PAWN))), _pin(comp, "self"))
    _pin(comp, "ComponentClass").set_pin_value(WEAPON_COMP_CLASS_PATH)
    cast = keep(_palette(ed, NODE_CAST_WEAPON))
    _connect(out(comp), _pin(cast, "Object"))
    for e in in_execs:
        _connect(e, _pin(cast, "execute"))
    wc = _loose_pin(cast, "AsBPWeaponComponent", is_input=False)

    def get(var):
        n = keep(ed.add_get_member_variable_node(var, WEAPON_COMP_CLASS_PATH))
        _connect(wc, _pin(n, "self"))
        return out(n, var)

    br = keep(ed.add_branch_node())
    _connect(get(EXIT_PENDING_VAR), _pin(br, "Condition"))
    _connect(then(cast), _pin(br, "execute"))
    now = out(keep(_node(ed, FN_TIME_SECONDS)))
    count = part(ed, WBP_HUD, BANNER_COUNT)
    called_off = part(ed, WBP_HUD, BANNER_OFF)

    # --- the countdown -----------------------------------------------------
    remaining = keep(_node(ed, FN_SUB_FF))
    _connect(get(EXIT_AT_VAR), _pin(remaining, "A"))
    _connect(now, _pin(remaining, "B"))
    whole = keep(_node(ed, FN_CEIL))
    _connect(out(remaining), _pin(whole, "A"))
    digits = keep(_node(ed, FN_INT_TO_STR))
    _connect(out(whole), _pin(digits, "InInt"))
    line = keep(_node(ed, FN_CONCAT))
    _set(line, "A", EXIT_BANNER_PREFIX)
    _connect(out(digits), _pin(line, "B"))
    flow = set_text(ed, count, out(line), [then(br)])
    flow = set_shown(ed, count, True, [flow])
    counting = set_shown(ed, called_off, False, [flow])

    # --- or, for a moment after a hit, why it stopped -------------------------
    idle = set_shown(ed, count, False, [else_(br)])
    ago = keep(_node(ed, FN_SUB_FF))
    _connect(now, _pin(ago, "A"))
    _connect(get(EXIT_CALLED_OFF_VAR), _pin(ago, "B"))
    recent = keep(_node(ed, FN_LESS_FF))
    _connect(out(ago), _pin(recent, "A"))
    _set(recent, "B", EXIT_CALLED_OFF_SHOWN_S)
    tails = show_if(ed, called_off, out(recent), [idle])
    ed.add_comment_to_nodes(
        "Save and exit: the countdown while it runs, and for "
        f"{EXIT_CALLED_OFF_SHOWN_S:.0f} s after a hit calls it off, why it stopped.",
        made)
    return [counting, *tails, out(cast, "CastFailed")]
