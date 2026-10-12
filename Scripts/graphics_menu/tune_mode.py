"""Whose the gameplay tables are, by mode (task M32): what a tab's nudge, its
kept table and its hint line do in single player and as a client of a server.

A gameplay tab (tune_tab.TuneTab.gameplay: guns, monsters, world, player)
tunes the game, which on a server is everyone's. The GameState says whether
it may be tuned: DevTuning (net/state_consts.py), true in single player, and
on a server only one started with -AllowDevTuning. The graphics and sound
tabs tune this machine and pass through here untouched.

    a nudge of a stat (tune_tick._author_nudge):
        author_allowed    no GameState, or DevTuning false: nothing moves,
                          nothing is touched; the rows are read-only
        author_send       after the cell is written. This machine owns the
                          GameState (single player): the table into the
                          tab's save slot, as before. A client: AskTune(the
                          tab's table index, the whole table) to the server,
                          whose tuner applies it (game_tuner.py); nothing is
                          kept, the table being the server's
    BeginPlay (tune_keep.author_load_tab, its own Branch on IsStandalone):
                          a gameplay tab's kept table is loaded in single
                          player only: a client must not start with the
                          developer's saved numbers on its own copies of the
                          server's guns
    DrawHUD (tune_draw.author_tune_panel):
        author_hint       the hint line: the tab's own words, or
                          READ_ONLY_HINT where DevTuning is false

The subject row (which gun, which creature) browses in every mode. The tab's
own apply still runs on a client that was allowed: it moves that client's
copies at once, and the server's values are the ones that count.
"""

from combat.ask_consts import ASK_TUNE
from combat.paths import WEAPON_COMP_BP_PATH, WEAPON_COMP_CLASS_PATH
from graphics_menu.ask import ask
from graphics_menu.dev_guns import _branch, _call, _get
from graphics_menu.tune_keep import author_keep_tab
from graphics_menu.tune_tab import READ_ONLY_HINT
from graphics_menu.ui_graph import set_text
from net import state_consts as S
from net.state_graph import game_state
from uebp.graph import BEL, _connect, _loose_pin, _must_load, _palette, _pin, out, then
from uebp.nodes.actor import FN_GET_COMP, FN_GET_OWNING_PAWN, FN_HAS_AUTHORITY
from uebp.nodes.palette import NODE_CAST_WEAPON


def _dev_tuning(ed, got, made):
    made += got.nodes
    return _get(ed, S.DevTuning, made, S.GAME_STATE_CLASS_PATH, got.pin)


def author_allowed(ed, tab, in_execs, made):
    """May this tab's numbers move here? Returns (the GameState pin or None,
    the exec to go on from, the exec pins of a refusal)."""
    if not tab.gameplay:
        (only,) = in_execs
        return None, only, []
    got = game_state(ed, in_execs)
    allowed, denied = _branch(ed, _dev_tuning(ed, got, made), [got.then], made)
    return got.pin, allowed, [denied, *got.fails]


def author_send(ed, tab, state, in_execs, made):
    """A cell moved: keep the table (single player) or send it (a client).
    ``state``: author_allowed's pin. Returns the exec tails."""
    if not tab.gameplay:
        return author_keep_tab(ed, tab, in_execs, made) if tab.kept else in_execs
    owns = _call(ed, FN_HAS_AUTHORITY, made, self=state)
    mine, theirs = _branch(ed, out(owns), in_execs, made)
    kept = author_keep_tab(ed, tab, [mine], made) if tab.kept else [mine]

    pawn = out(_call(ed, FN_GET_OWNING_PAWN, made))
    comp = _call(ed, FN_GET_COMP, made, self=pawn)
    _pin(comp, "ComponentClass").set_pin_value(WEAPON_COMP_CLASS_PATH)
    _must_load(WEAPON_COMP_BP_PATH)   # the cast exists only for a loaded class
    cast = _palette(ed, NODE_CAST_WEAPON)
    if not BEL.list_input_pins(cast):
        raise RuntimeError("no cast node for BP_WeaponComponent")
    made.append(cast)
    _connect(out(comp), _pin(cast, "Object"))
    _connect(theirs, _pin(cast, "execute"))
    wc = _loose_pin(cast, "AsBPWeaponComponent", is_input=False)
    sent = ask(ed, wc, ASK_TUNE, [then(cast)], made,
               Table=tab.table_index, Values=_get(ed, tab.values_var, made))
    return [*kept, sent, out(cast, "CastFailed")]


def author_hint(ed, tab, hint, in_execs, made):
    """A gameplay tab's hint line says why its rows do not move. ``hint``:
    the TextBlock. Returns the exec tails."""
    if not tab.gameplay:
        return in_execs
    got = game_state(ed, in_execs)
    allowed, denied = _branch(ed, _dev_tuning(ed, got, made), [got.then], made)
    return [set_text(ed, hint, tab.hint_text, [allowed]),
            set_text(ed, hint, READ_ONLY_HINT, [denied]), *got.fails]
