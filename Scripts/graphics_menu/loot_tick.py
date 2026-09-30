"""The loot window's HUD Tick fragment: find the body, poll its keys, serve a take.

    find the nearest body with loot (loot_find)      -> LootTarget
    none in reach   -> LootOpen = false, LootTakeRequested = false
    else, with the player's weapon component:
        LootBagFull = Length(Inventory) >= INVENTORY_SIZE
        LootSel clamped to the body's contents (a take shortens them)
        panel shut (NOT MenuOpen):
            [Tab]          LootOpen = NOT LootOpen, LootSel = 0
            open: Up/Down  LootSel -/+ 1, clamped
                  Enter    LootTakeRequested = true
        LootTakeRequested AND LootOpen -> lower it; room in the bag -> take (loot_take)

Tick, not DrawHUD: a -nullrhi probe never draws. The keys only raise flags,
which is what lets probes/probe_corpse_loot.py open the window and take
without a keyboard. Walking out of reach, or the body's lifespan ending, loses
the target and so shuts the window; so does taking its last item.
"""

import unreal

from combat.graph import (
    BEL, _at, _connect, _declare, _float_type, _loose_pin, _must_load, _palette, _pin,
)
from combat.nodes import (
    FN_ADD_II, FN_AND, FN_ARR_LEN, FN_GET_COMP, FN_GET_PLAYER_PAWN,
    FN_IS_VALID, FN_MIN_II, FN_NOT, FN_SUB_II, FN_WAS_PRESSED,
)
from combat.paths import (
    HEALTH_BP_PATH, HEALTH_CLASS_PATH, WEAPON_COMP_BP_PATH, WEAPON_COMP_CLASS_PATH,
)
from combat.tuning import INVENTORY_SIZE
from graphics_menu.dev_guns import _branch, _call, _get, _out, _setter
from graphics_menu.loot_consts import (
    LOOT_BAG_FULL_VAR, LOOT_BEST_VAR, LOOT_DOWN, LOOT_KEY, LOOT_OPEN_VAR, LOOT_SEL_VAR,
    LOOT_TAKE_KEY, LOOT_TAKE_VAR, LOOT_TARGET_VAR, LOOT_UP,
)
from graphics_menu.loot_find import author_find_body, put
from graphics_menu.loot_take import author_take
from loot.consts import LOOT_NAMES_VAR, LOOT_RADIUS

FN_MAX_II = "/Script/Engine.KismetMathLibrary.Max"
FN_GE_II = "/Script/Engine.KismetMathLibrary.GreaterEqual_IntInt"
NODE_CAST_WEAPON = "Utilities|Casting|CastToBP_WeaponComponent"

_BOOLS = (LOOT_OPEN_VAR, LOOT_TAKE_VAR, LOOT_BAG_FULL_VAR)


def declare_loot_vars(ed):
    """The HUD's loot variables. Defaults: loot_defaults()."""
    target = BEL.get_object_reference_type(BEL.generated_class(_must_load(HEALTH_BP_PATH)))
    for name, kind in ((LOOT_TARGET_VAR, target), (LOOT_BEST_VAR, _float_type()),
                       (LOOT_SEL_VAR, BEL.get_basic_type_by_name("int")),
                       *((b, BEL.get_basic_type_by_name("bool")) for b in _BOOLS)):
        _declare(ed, name, kind)


def loot_defaults():
    return {LOOT_BEST_VAR: LOOT_RADIUS, LOOT_SEL_VAR: 0, **{b: False for b in _BOOLS}}


def _pressed(ed, pc_out, key, x, y, made):
    return _out(_call(ed, FN_WAS_PRESSED, x, y, made, self=pc_out, Key=key))


def _count(ed, x, y, made):
    """How many things the target body carries."""
    names = _get(ed, LOOT_NAMES_VAR, x, y, made, HEALTH_CLASS_PATH,
                 _get(ed, LOOT_TARGET_VAR, x - 240, y, made))
    return _out(_call(ed, FN_ARR_LEN, x + 240, y, made, TargetArray=names))


def _move(ed, step, limit, bound, in_execs, x, y, made):
    """LootSel := limit(LootSel step 1, bound); bound is an int or a pin."""
    moved = _call(ed, step, x, y + 300, made,
                  A=_get(ed, LOOT_SEL_VAR, x - 240, y + 300, made), B=1)
    held = _call(ed, limit, x + 240, y + 300, made, A=_out(moved), B=bound)
    return put(ed, LOOT_SEL_VAR, _out(held), in_execs, x + 480, y, made)


def _author_keys(ed, pc_out, in_execs, x0, y0, made):
    """Tab, and with the window open Up/Down/Enter. Returns the exec tails."""
    free, busy = _branch(ed, _out(_call(ed, FN_NOT, x0, y0 + 300, made,
                                        A=_get(ed, "MenuOpen", x0 - 240, y0 + 300, made))),
                         in_execs, x0 + 240, y0, made)
    tab, no_tab = _branch(ed, _pressed(ed, pc_out, LOOT_KEY, x0 + 240, y0 + 440, made),
                          [free], x0 + 500, y0, made)
    flip = _call(ed, FN_NOT, x0 + 500, y0 + 440, made,
                 A=_get(ed, LOOT_OPEN_VAR, x0 + 260, y0 + 580, made))
    flow = put(ed, LOOT_OPEN_VAR, _out(flip), [tab], x0 + 760, y0 - 200, made)
    flow = _setter(ed, LOOT_SEL_VAR, 0, [flow], x0 + 1020, y0 - 200, made)

    x = x0 + 1300
    shown, shut = _branch(ed, _get(ed, LOOT_OPEN_VAR, x - 240, y0 + 300, made),
                          [flow, no_tab], x, y0, made)
    last = _call(ed, FN_SUB_II, x, y0 + 600, made, A=_count(ed, x - 480, y0 + 600, made),
                 B=1)
    flow = [shown]
    for key, step, limit, bound in ((LOOT_UP, FN_SUB_II, FN_MAX_II, 0),
                                    (LOOT_DOWN, FN_ADD_II, FN_MIN_II, _out(last))):
        x += 300
        hit, miss = _branch(ed, _pressed(ed, pc_out, key, x, y0 + 440, made), flow,
                            x, y0, made)
        flow = [_move(ed, step, limit, bound, [hit], x + 300, y0, made), miss]
        x += 800
    ask, no_ask = _branch(ed, _pressed(ed, pc_out, LOOT_TAKE_KEY, x, y0 + 440, made),
                          flow, x + 300, y0, made)
    asked = _setter(ed, LOOT_TAKE_VAR, "true", [ask], x + 560, y0, made)
    return [asked, no_ask, shut, busy]


def author_loot_tick(ed, pc_out, in_execs, x0, y0):
    """The whole fragment (see the module docstring). Returns the tails."""
    made = []
    flow = author_find_body(ed, in_execs, x0, y0, made)
    x0 += 4800
    found, lost = _branch(ed, _out(_call(ed, FN_IS_VALID, x0, y0 + 300, made,
                                         Object=_get(ed, LOOT_TARGET_VAR, x0 - 240,
                                                     y0 + 300, made))),
                          flow, x0 + 240, y0, made)
    shut = _setter(ed, LOOT_OPEN_VAR, "false", [lost], x0 + 500, y0 + 800, made)
    shut = _setter(ed, LOOT_TAKE_VAR, "false", [shut], x0 + 760, y0 + 800, made)

    pawn = _out(_call(ed, FN_GET_PLAYER_PAWN, x0 + 240, y0 + 440, made, PlayerIndex=0))
    comp = _call(ed, FN_GET_COMP, x0 + 500, y0 + 440, made, self=pawn)
    _pin(comp, "ComponentClass").set_pin_value(WEAPON_COMP_CLASS_PATH)
    unreal.load_asset(WEAPON_COMP_BP_PATH)   # for its cast node
    cast = _at(_palette(ed, NODE_CAST_WEAPON), x0 + 760, y0)
    made.append(cast)
    _connect(_out(comp), _pin(cast, "Object"))
    _connect(found, _pin(cast, "execute"))
    wc = _loose_pin(cast, "AsBPWeaponComponent", is_input=False)

    carried = _call(ed, FN_ARR_LEN, x0 + 1040, y0 + 300, made,
                    TargetArray=_get(ed, "Inventory", x0 + 800, y0 + 300, made,
                                     WEAPON_COMP_CLASS_PATH, wc))
    full = _call(ed, FN_GE_II, x0 + 1280, y0 + 300, made, A=_out(carried),
                 B=INVENTORY_SIZE)
    flow = put(ed, LOOT_BAG_FULL_VAR, _out(full), [BEL.find_then_pin(cast)],
               x0 + 1540, y0, made)
    last = _call(ed, FN_SUB_II, x0 + 1540, y0 + 440, made,
                 A=_count(ed, x0 + 1060, y0 + 440, made), B=1)
    # Min then Max rather than an int Clamp: the verifier reads every Clamp
    # node in this graph as a settings slider.
    under = _call(ed, FN_MIN_II, x0 + 1800, y0 + 300, made,
                  A=_get(ed, LOOT_SEL_VAR, x0 + 1540, y0 + 300, made), B=_out(last))
    kept = _call(ed, FN_MAX_II, x0 + 2040, y0 + 300, made, A=_out(under), B=0)
    flow = put(ed, LOOT_SEL_VAR, _out(kept), [flow], x0 + 2300, y0, made)

    keyed = _author_keys(ed, pc_out, [flow], x0 + 2400, y0, made)
    x0 += 6600
    wanted = _call(ed, FN_AND, x0, y0 + 300, made,
                   A=_get(ed, LOOT_TAKE_VAR, x0 - 240, y0 + 300, made),
                   B=_get(ed, LOOT_OPEN_VAR, x0 - 240, y0 + 440, made))
    serve, idle = _branch(ed, _out(wanted), keyed, x0 + 240, y0, made)
    flow = _setter(ed, LOOT_TAKE_VAR, "false", [serve], x0 + 500, y0, made)
    room, no_room = _branch(ed, _out(_call(ed, FN_NOT, x0 + 500, y0 + 300, made,
                                           A=_get(ed, LOOT_BAG_FULL_VAR, x0 + 260,
                                                  y0 + 300, made))),
                            [flow], x0 + 760, y0, made)
    taken = author_take(ed, wc, pawn, [room], x0 + 1020, y0, made)
    ed.add_comment_to_nodes(
        f"Loot: the nearest dead body with Loot within the reach is LootTarget; "
        f"[{LOOT_KEY}] opens its window, Up/Down pick, Enter takes into the bag "
        f"(while it has room). Out of reach, the window shuts.", made[:1])
    return taken + [idle, no_room, shut, _pin(cast, "CastFailed", is_input=False)]
