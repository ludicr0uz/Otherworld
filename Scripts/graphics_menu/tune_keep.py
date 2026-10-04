"""What the tuning tabs keep between sessions: BP_TuneSave, and the two HUD
fragments that read and write it for any kept tab (tune_tab.TuneTab.kept).

    BeginPlay (author_load_kept), per tab, over the built table:
        its slot on disk, a BP_TuneSave whose KeptBuilt is this build's
        table (the tab's <Values>Built), KeptTable the same size
            -> <Values> := KeptTable, but for the tab's unkept cells
               (the built ones back); <Touched> := true
        anything else -> nothing: the built table, which is the CSV's

    a nudge (author_keep_tab, from tune_tick._author_nudge):
        a fresh BP_TuneSave; KeptBuilt := <Values>Built, KeptTable :=
        <Values>; SaveGameToSlot

This is the one place a tab's table persists, so a tab only names itself
(TuneTab.keep_slot, built_var) and applies its table when touched. The CSV
stays the default, tracked in git and baked into the HUD by the build; the
save is what a player (or a developer in PIE) moved since. It needs no Python,
so it works in a packaged build, where Enter's CSV save cannot run.

KeptBuilt is why a save never hides a newer CSV: Enter writes the CSV, the
next build bakes it, and the built table no longer matches the save's, which
is then left alone. The numbers are the same either way: the save held what
the CSV now does. A hand-edited CSV wins the same way.

The load raises Touched because a tab's apply runs on it (the guns', the
creatures', the player's, the world's): the assets hold the CSV's numbers,
not the save's.

GRAPHICS SETTINGS keeps its pick and its Custom row by itself (gfx_save.py),
which author_load_kept and build_keep_savegames also run, so the HUD build
has one call for each.
"""

import unreal

from combat.log import _log
from uebp.graph import (
    BEL, BGE, _connect, _create_blueprint, _declare, _float_type, _loose_pin, _must_load,
    _palette, _pin, out, then)
from uebp.layout import arrange
from graphics_menu.dev_guns import _branch, _call, _get, _setter
from graphics_menu.gfx_save import author_load_graphics, build_graphics_savegame
from graphics_menu.loot_find import put
from graphics_menu.save_exit import _chain
from graphics_menu.tune_keep_consts import (
    KEPT_TABS, TUNE_SAVE_BP_PATH, TUNE_SAVE_BUILT_FIELD, TUNE_SAVE_CLASS_PATH,
    TUNE_SAVE_TABLE_FIELD, TUNE_SAVE_USER_INDEX)
from uebp.nodes.array import FN_ARR_GET, FN_ARR_IDENTICAL, FN_ARR_LEN, FN_ARR_SET
from uebp.nodes.math import FN_AND, FN_EQ_II
from uebp.nodes.palette import NODE_CAST_TUNE_SAVE
from uebp.nodes.system import FN_CREATE_SAVE, FN_LOAD_SAVE, FN_SAVE_EXISTS, FN_WRITE_SAVE


def build_tune_savegame():
    """Create (or re-declare) BP_TuneSave and compile it. A record, no graph."""
    bp = _create_blueprint(TUNE_SAVE_BP_PATH, unreal.SaveGame)
    ed = BGE.get_graph_editor_by_name(bp, "EventGraph")
    for field in (TUNE_SAVE_TABLE_FIELD, TUNE_SAVE_BUILT_FIELD):
        _declare(ed, field, BEL.get_array_type(_float_type()))
    arrange(ed)
    if not BEL.compile_blueprint(bp):
        raise RuntimeError("BP_TuneSave failed to compile")
    unreal.get_editor_subsystem(unreal.EditorAssetSubsystem).save_loaded_asset(bp)
    _log(f"built {TUNE_SAVE_BP_PATH} (one slot a tab: "
         f"{', '.join(t.keep_slot for t in KEPT_TABS)})")
    return bp


def build_keep_savegames():
    """Every SaveGame class the tabs keep something in."""
    build_graphics_savegame()
    build_tune_savegame()


def _cast(ed, obj_out, in_execs, made):
    """Cast to BP_TuneSave. Returns (the save, then, CastFailed)."""
    _must_load(TUNE_SAVE_BP_PATH)   # a cast node exists only for a loaded class
    cast = _palette(ed, NODE_CAST_TUNE_SAVE)
    if not BEL.list_input_pins(cast):
        raise RuntimeError("no cast node for BP_TuneSave")
    made.append(cast)
    _connect(obj_out, _pin(cast, "Object"))
    for e in in_execs:
        _connect(e, _pin(cast, "execute"))
    return (_loose_pin(cast, "AsBPTuneSave", is_input=False),
            then(cast), out(cast, "CastFailed"))


def _field(ed, save, name, made):
    return _get(ed, name, made, TUNE_SAVE_CLASS_PATH, save)


def author_load_tab(ed, tab, in_execs, made):
    """BeginPlay: ``tab``'s saved table over the built one (see the module
    docstring). Returns the exec tails."""
    slot = dict(SlotName=tab.keep_slot, UserIndex=TUNE_SAVE_USER_INDEX)
    exists = _call(ed, FN_SAVE_EXISTS, made, **slot)
    have, none = _branch(ed, out(exists), _chain(exists, in_execs), made)
    loaded = _call(ed, FN_LOAD_SAVE, made, **slot)
    save, flow, other = _cast(ed, out(loaded), _chain(loaded, [have]), made)

    # Made over this build's table, and whole.
    same = _call(ed, FN_ARR_IDENTICAL, made,
                 ArrayA=_field(ed, save, TUNE_SAVE_BUILT_FIELD, made),
                 ArrayB=_get(ed, tab.built_var, made))
    size = _call(ed, FN_ARR_LEN, made, TargetArray=_field(ed, save, TUNE_SAVE_TABLE_FIELD, made))
    built = _call(ed, FN_ARR_LEN, made, TargetArray=_get(ed, tab.built_var, made))
    whole = _call(ed, FN_EQ_II, made, A=out(size), B=out(built))
    ours = _call(ed, FN_AND, made, A=out(same), B=out(whole))
    fits, stale = _branch(ed, out(ours), [flow], made)

    flow = put(ed, tab.values_var, _field(ed, save, TUNE_SAVE_TABLE_FIELD, made), [fits], made)
    for cell in tab.unkept_cells:
        back = _call(ed, FN_ARR_GET, made, TargetArray=_get(ed, tab.built_var, made), Index=cell)
        write = _call(ed, FN_ARR_SET, made,
                      TargetArray=_get(ed, tab.values_var, made), Index=cell)
        _connect(out(back, "Item"), _pin(write, "Item"))
        _connect(flow, _pin(write, "execute"))
        flow = then(write)
    applied = _setter(ed, tab.touched_var, "true", [flow], made)
    return [applied, none, other, stale]


def author_load_kept(ed, in_execs):
    """BeginPlay: everything a player's tabs kept, over the built defaults.
    Returns the exec tails."""
    flow = author_load_graphics(ed, in_execs)
    made = []
    for tab in KEPT_TABS:
        flow = author_load_tab(ed, tab, flow, made)
    ed.add_comment_to_nodes(
        "The tuning tabs' tables, each from its own save slot, over the built "
        "ones (the CSVs'). A save made over another built table is left alone: "
        "the CSV changed since, and wins. A loaded tab is touched, so its "
        "apply runs.", made[:1])
    return flow


def author_keep_tab(ed, tab, in_execs, made):
    """A nudge: ``tab``'s table, and the built one it was made over, into a
    fresh BP_TuneSave, saved to the tab's slot. Returns the exec tails."""
    fresh = _call(ed, FN_CREATE_SAVE, made)
    _pin(fresh, "SaveGameClass").set_pin_value(TUNE_SAVE_CLASS_PATH)
    save, flow, failed = _cast(ed, out(fresh), _chain(fresh, in_execs), made)
    for field, source in ((TUNE_SAVE_BUILT_FIELD, tab.built_var),
                          (TUNE_SAVE_TABLE_FIELD, tab.values_var)):
        n = ed.add_set_member_variable_node(field, TUNE_SAVE_CLASS_PATH)
        made.append(n)
        _connect(save, _pin(n, "self"))
        _connect(_get(ed, source, made), _pin(n, field))
        _connect(flow, _pin(n, "execute"))
        flow = then(n)
    saved = _call(ed, FN_WRITE_SAVE, made, SaveGameObject=save,
                  SlotName=tab.keep_slot, UserIndex=TUNE_SAVE_USER_INDEX)
    _connect(flow, _pin(saved, "execute"))
    return [then(saved), failed]
