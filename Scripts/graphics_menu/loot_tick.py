"""The loot window's HUD Tick fragment: find the body, poll its keys, serve a
take, kneel.

    find the nearest body (loot_find)                -> LootTarget
    none in reach   -> LootOpen = false, LootTakeRequested = false
    the player dead -> the same: the dead search nobody (the weapon
                       component's OwnerDead, combat/weapon_component/dead.py)
    else, with the player's weapon component:
        LootBagFull = NOT the weapon component's HasRoom (no bag slot, no
                      empty hand)
        LootSel clamped to the body's contents (a take shortens them)
        panel shut (NOT MenuOpen):
            [Tab]          LootOpen = NOT LootOpen, LootSel = 0
            open: Up/Down  LootSel -/+ 1, clamped
                  Enter    LootTakeRequested = true
        LootTakeRequested AND LootOpen -> lower it, and ask the weapon
            component for it, if the body has that row:
            AskLootTake(LootTarget, LootSel, the class shown there). Whether
            it is taken (room in the bag, the row still that item's) is the
            component's to say, on the server
            (combat/weapon_component/loot_take.py). The window shows the
            body's arrays, which replicate: a row another player took first
            is gone from it, with nothing taken here
    then, on every path: the kneel follows LootOpen (loot_kneel)

Tick, not DrawHUD: a -nullrhi probe never draws. The keys only raise flags,
which is what lets probes/probe_corpse_loot.py open the window and take
without a keyboard. Walking out of reach, or the body's lifespan ending, loses
the target and so shuts the window. Taking the last item does not: the body
is still there, and the window says NOTHING.
"""

import unreal

from uebp.graph import (
    BEL, _connect, _declare, _float_type, _loose_pin, _must_load, _palette, _pin, out, then)
from combat.ask_consts import ASK_LOOT_TAKE
from combat.paths import (
    HEALTH_BP_PATH, HEALTH_CLASS_PATH, WEAPON_COMP_BP_PATH, WEAPON_COMP_CLASS_PATH,
)
from combat.slot_tuning import HAS_ROOM_VAR
from combat.weapon_component.dead import OWNER_DEAD_VAR
from graphics_menu.ask import ask
from graphics_menu.dev_guns import _branch, _call, _get, _setter
from graphics_menu.loot_consts import (
    LOOT_BAG_FULL_VAR, LOOT_BEST_VAR, LOOT_DOWN, LOOT_KEY, LOOT_KNEELING_VAR,
    LOOT_OPEN_VAR, LOOT_SEL_VAR, LOOT_TAKE_KEY, LOOT_TAKE_VAR, LOOT_TARGET_VAR, LOOT_UP,
)
from graphics_menu.loot_find import author_find_body, put
from graphics_menu.loot_kneel import author_kneel
from loot.consts import LOOT_NAMES_VAR, LOOT_RADIUS, LOOT_VAR
from uebp.nodes.actor import FN_GET_COMP, FN_GET_OWNING_PAWN, FN_WAS_PRESSED
from uebp.nodes.array import FN_ARR_GET, FN_ARR_LEN, FN_ARR_VALID
from uebp.nodes.math import (
    FN_ADD_II, FN_AND, FN_MAX_II, FN_MIN_II, FN_NOT, FN_SUB_II)
from uebp.nodes.palette import NODE_CAST_WEAPON
from uebp.nodes.system import FN_IS_VALID
from graphics_menu import hud_vars as MV


_BOOLS = (LOOT_OPEN_VAR, LOOT_TAKE_VAR, LOOT_BAG_FULL_VAR, LOOT_KNEELING_VAR)


def declare_loot_vars(ed):
    """The HUD's loot variables. Defaults: loot_defaults()."""
    target = BEL.get_object_reference_type(BEL.generated_class(_must_load(HEALTH_BP_PATH)))
    for name, kind in ((LOOT_TARGET_VAR, target), (LOOT_BEST_VAR, _float_type()),
                       (LOOT_SEL_VAR, BEL.get_basic_type_by_name("int")),
                       *((b, BEL.get_basic_type_by_name("bool")) for b in _BOOLS)):
        _declare(ed, name, kind)


def loot_defaults():
    return {LOOT_BEST_VAR: LOOT_RADIUS, LOOT_SEL_VAR: 0, **{b: False for b in _BOOLS}}


def _pressed(ed, pc_out, key, made):
    return out(_call(ed, FN_WAS_PRESSED, made, self=pc_out, Key=key))


def _count(ed, made):
    """How many things the target body carries."""
    names = _get(ed, LOOT_NAMES_VAR, made, HEALTH_CLASS_PATH, _get(ed, LOOT_TARGET_VAR, made))
    return out(_call(ed, FN_ARR_LEN, made, TargetArray=names))


def _move(ed, step, limit, bound, in_execs, made):
    """LootSel := limit(LootSel step 1, bound); bound is an int or a pin."""
    moved = _call(ed, step, made, A=_get(ed, LOOT_SEL_VAR, made), B=1)
    held = _call(ed, limit, made, A=out(moved), B=bound)
    return put(ed, LOOT_SEL_VAR, out(held), in_execs, made)


def _author_keys(ed, pc_out, in_execs, made):
    """Tab, and with the window open Up/Down/Enter. Returns the exec tails."""
    free, busy = _branch(ed, out(_call(ed, FN_NOT, made,
                                        A=_get(ed, MV.MenuOpen, made))),
                         in_execs, made)
    tab, no_tab = _branch(ed, _pressed(ed, pc_out, LOOT_KEY, made), [free], made)
    flip = _call(ed, FN_NOT, made, A=_get(ed, LOOT_OPEN_VAR, made))
    flow = put(ed, LOOT_OPEN_VAR, out(flip), [tab], made)
    flow = _setter(ed, LOOT_SEL_VAR, 0, [flow], made)

    shown, shut = _branch(ed, _get(ed, LOOT_OPEN_VAR, made), [flow, no_tab], made)
    last = _call(ed, FN_SUB_II, made, A=_count(ed, made), B=1)
    flow = [shown]
    for key, step, limit, bound in ((LOOT_UP, FN_SUB_II, FN_MAX_II, 0),
                                    (LOOT_DOWN, FN_ADD_II, FN_MIN_II, out(last))):
        hit, miss = _branch(ed, _pressed(ed, pc_out, key, made), flow, made)
        flow = [_move(ed, step, limit, bound, [hit], made), miss]
    ask, no_ask = _branch(ed, _pressed(ed, pc_out, LOOT_TAKE_KEY, made), flow, made)
    asked = _setter(ed, LOOT_TAKE_VAR, "true", [ask], made)
    return [asked, no_ask, shut, busy]


def author_loot_tick(ed, pc_out, in_execs):
    """The whole fragment (see the module docstring). Returns the tails."""
    made = []
    flow = author_find_body(ed, in_execs, made)
    found, lost = _branch(ed, out(_call(ed, FN_IS_VALID, made,
                                         Object=_get(ed, LOOT_TARGET_VAR, made))),
                          flow, made)

    pawn = out(_call(ed, FN_GET_OWNING_PAWN, made))
    comp = _call(ed, FN_GET_COMP, made, self=pawn)
    _pin(comp, "ComponentClass").set_pin_value(WEAPON_COMP_CLASS_PATH)
    unreal.load_asset(WEAPON_COMP_BP_PATH)   # for its cast node
    cast = _palette(ed, NODE_CAST_WEAPON)
    made.append(cast)
    _connect(out(comp), _pin(cast, "Object"))
    _connect(found, _pin(cast, "execute"))
    wc = _loose_pin(cast, "AsBPWeaponComponent", is_input=False)
    # Dying is not searching: no Tab, no take, and an open window shuts.
    dead, alive = _branch(ed, _get(ed, OWNER_DEAD_VAR, made,
                                   WEAPON_COMP_CLASS_PATH, wc),
                          [then(cast)], made)
    shut = _setter(ed, LOOT_OPEN_VAR, "false", [lost, dead], made)
    shut = _setter(ed, LOOT_TAKE_VAR, "false", [shut], made)

    # Full: no bag slot and no empty hand (the slot sync's HasRoom).
    full = _call(ed, FN_NOT, made, A=_get(ed, HAS_ROOM_VAR, made, WEAPON_COMP_CLASS_PATH, wc))
    flow = put(ed, LOOT_BAG_FULL_VAR, out(full), [alive], made)
    last = _call(ed, FN_SUB_II, made, A=_count(ed, made), B=1)
    # Min then Max rather than an int Clamp: the verifier reads every Clamp
    # node in this graph as a settings slider.
    under = _call(ed, FN_MIN_II, made, A=_get(ed, LOOT_SEL_VAR, made), B=out(last))
    kept = _call(ed, FN_MAX_II, made, A=out(under), B=0)
    flow = put(ed, LOOT_SEL_VAR, out(kept), [flow], made)

    keyed = _author_keys(ed, pc_out, [flow], made)
    wanted = _call(ed, FN_AND, made,
                   A=_get(ed, LOOT_TAKE_VAR, made),
                   B=_get(ed, LOOT_OPEN_VAR, made))
    serve, idle = _branch(ed, out(wanted), keyed, made)
    flow = _setter(ed, LOOT_TAKE_VAR, "false", [serve], made)
    # What the caret is on, so the server takes that or nothing. A body that
    # carries nothing has no row to read.
    loot = _get(ed, LOOT_VAR, made, HEALTH_CLASS_PATH, _get(ed, LOOT_TARGET_VAR, made))
    row, no_row = _branch(ed, out(_call(ed, FN_ARR_VALID, made, TargetArray=loot,
                                        IndexToTest=_get(ed, LOOT_SEL_VAR, made))),
                          [flow], made)
    shown = _call(ed, FN_ARR_GET, made, TargetArray=loot, Index=_get(ed, LOOT_SEL_VAR, made))
    taken = ask(ed, wc, ASK_LOOT_TAKE, [row], made,
                Body=_get(ed, LOOT_TARGET_VAR, made), Index=_get(ed, LOOT_SEL_VAR, made),
                Want=out(shown, "Item"))
    ed.add_comment_to_nodes(
        f"Loot: the nearest dead body within the reach is LootTarget; "
        f"[{LOOT_KEY}] kneels and opens its window, Up/Down pick, Enter asks the "
        f"weapon component for the item (AskLootTake). Out of reach, the window "
        f"shuts.", made[:1])
    tails = [taken, no_row, idle, shut, out(cast, "CastFailed")]
    return author_kneel(ed, pc_out, tails)
