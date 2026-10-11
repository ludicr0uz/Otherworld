"""The figure on the title: the player's character, spawned on the title
level's stage in front of its camera (Scripts/title), dressed as the saved
profile has it.

Tick, on the title (GameStarted false), once (TitleDressed): when the pawn's
parts cast and the weapon component is up (its Inventory holds the issued
loadout), the profile, if there is one, is loaded and each saved worn class
worn again through ViewWorn (profile_read._author_rewear), which draws it on
the body. With no profile the figure stands as it spawned: a fresh
character, in the pants its weapon component's BeginPlay wears
(combat/weapon_component/starter_worn.py). Nothing else of the profile is read here: the stats and
the items are the play level's (save_exit._author_load_once), once New Game
has opened it.

After it, once (TitleStowed), when the component holds something (Held: the
issued gun reaches the hand a frame or more after the loadout is issued, and
a move asked before that finds the hand empty), the gun is stowed: AskMove
from the hand to the primary slot, the slot it was issued from. The figure
on the title holds nothing.
"""

from uebp.graph import _connect, _loose_pin, _palette, _pin, out, then
from uebp.vars import BOOL, Var, declare, defaults
from combat.ask_consts import ASK_MOVE, FROM_PARAM, TO_PARAM
from combat.paths import WEAPON_COMP_CLASS_PATH
from combat.slot_tuning import HAND, PRIMARY
from graphics_menu.ask import ask
from graphics_menu.player_parts import author_player_parts
from graphics_menu.profile_consts import PROFILE_SLOT, PROFILE_USER_INDEX
from graphics_menu.profile_read import _author_rewear
from graphics_menu.save_exit import _branch, _call, _chain, _get, _setter
from uebp.nodes.array import FN_ARR_LEN
from uebp.nodes.math import FN_GREATER_II, FN_NOT
from uebp.nodes.palette import NODE_CAST_PROFILE
from uebp.nodes.system import FN_IS_VALID, FN_LOAD_SAVE, FN_SAVE_EXISTS
from combat.weapon_component import vars as WV

# Raised once the figure has been dressed (or found nothing to wear).
TITLE_DRESSED_VAR = Var("TitleDressed", BOOL, False)
# Raised once the issued gun has been asked back into its slot.
TITLE_STOWED_VAR = Var("TitleStowed", BOOL, False)
TABLE = (TITLE_DRESSED_VAR, TITLE_STOWED_VAR)


def declare_title_vars(ed):
    declare(ed, TABLE)


def title_defaults():
    return defaults(TABLE)


def _author_dress(ed, wc, in_execs, made):
    """Once, with the loadout issued: the profile's garments worn. Returns
    the tails."""
    fresh = _call(ed, FN_NOT, made, A=_get(ed, TITLE_DRESSED_VAR, made))
    look, skip = _branch(ed, out(fresh), in_execs, made)
    # The component is up once it has issued the loadout.
    inv = _get(ed, WV.Inventory, made, WEAPON_COMP_CLASS_PATH, wc)
    count = _call(ed, FN_ARR_LEN, made, TargetArray=inv)
    armed = _call(ed, FN_GREATER_II, made, A=out(count), B=0)
    ready, not_yet = _branch(ed, out(armed), [look], made)
    flow = _setter(ed, TITLE_DRESSED_VAR, "true", [ready], made)
    exists = _call(ed, FN_SAVE_EXISTS, made, SlotName=PROFILE_SLOT, UserIndex=PROFILE_USER_INDEX)
    flow = _chain(exists, flow)
    have, none = _branch(ed, out(exists), flow, made)
    load = _call(ed, FN_LOAD_SAVE, made, SlotName=PROFILE_SLOT, UserIndex=PROFILE_USER_INDEX)
    _connect(have, _pin(load, "execute"))
    cast = _palette(ed, NODE_CAST_PROFILE)
    _connect(out(load), _pin(cast, "Object"))
    _connect(then(load), _pin(cast, "execute"))
    made.append(cast)
    prof = _loose_pin(cast, "AsBPProfile", is_input=False)
    done = _author_rewear(ed, prof, wc, then(cast), made)
    return [done, out(cast, "CastFailed"), none, not_yet, skip]


def _author_stow(ed, wc, in_execs, made):
    """Once, with something in the hand: it goes back into its slot.
    Returns the tails."""
    fresh = _call(ed, FN_NOT, made, A=_get(ed, TITLE_STOWED_VAR, made))
    look, skip = _branch(ed, out(fresh), in_execs, made)
    held = _get(ed, WV.Held, made, WEAPON_COMP_CLASS_PATH, wc)
    holding = _call(ed, FN_IS_VALID, made, Object=held)
    full, empty = _branch(ed, out(holding), [look], made)
    flow = _setter(ed, TITLE_STOWED_VAR, "true", [full], made)
    stowed = ask(ed, wc, ASK_MOVE, flow, made, **{FROM_PARAM: HAND, TO_PARAM: PRIMARY})
    return [stowed, empty, skip]


def author_title_figure(ed, in_execs):
    """Tick's title arm (see the module docstring). Returns the tails."""
    made = []
    ok, fails, parts = author_player_parts(ed, in_execs, made)
    wc = parts[WEAPON_COMP_CLASS_PATH]
    dressed = _author_dress(ed, wc, [ok], made)
    tails = _author_stow(ed, wc, dressed, made)
    ed.add_comment_to_nodes(
        f"The figure on the title: once ({TITLE_DRESSED_VAR}), with the weapon "
        f"component up, the saved profile ({PROFILE_SLOT!r}), if there is one, "
        f"dresses the character through ViewWorn, slot by slot. No profile: a "
        f"fresh character, in its starting pants. Then, once ({TITLE_STOWED_VAR}), when the issued "
        f"gun has reached the hand, it is stowed ({ASK_MOVE} hand -> primary): the "
        f"figure holds nothing. Its stats and items are loaded in play, not here.",
        made)
    return tails + fails
