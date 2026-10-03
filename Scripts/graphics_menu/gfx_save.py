"""BP_GraphicsSave: what the player's graphics keep between sessions -- the
preset they picked and the Custom preset's numbers -- and the two HUD
fragments that read and write it.

    BeginPlay (author_load_graphics), after Quality := the CSV's default:
        slot OtherworldGraphics on disk, a BP_GraphicsSave, its SavedTable
        the size of this build's table
            -> GfxTuneValues' Custom row := the save's Custom row
               Quality := SavedQuality, held inside the presets
        anything else -> nothing: the CSV's default preset and Custom row

    Tick (author_keep_graphics, from gfx_tune_tick's hand-over), on a change:
        a fresh BP_GraphicsSave; SavedQuality := Quality, SavedTable :=
        GfxTuneValues; SaveGameToSlot

Low, Medium and High are never read back: they are the CSV's, the same for
every player, and a session's nudges to them last the session (SAVE DEFAULT
writes them to the CSV, gfx_tune_save.py). The whole table is stored all the
same, so the write is one Set and its length says which build wrote it: a
build with another STAT_COUNT would read Custom's numbers off the wrong rows.

A look number is one for all four presets, so a nudge to it on any preset is
in Custom's row and kept with it; picking Custom next session brings it back.

A SaveGame of its own rather than two fields on BP_Settings: the HUD is its
only reader, so the HUD's builder builds it (as BP_Profile, profile_asset.py),
and a probe can set its slot aside without touching the player's keybinds.
"""

import unreal

from combat.graph import (
    BEL, BGE, _at, _connect, _create_blueprint, _declare, _float_type, _log,
    _loose_pin, _must_load, _palette, _pin,
)
from uebp.graph import out
from combat.nodes import FN_ADD_II, FN_ARR_GET, FN_EQ_II, FN_MIN_II, MACRO_FOR_LOOP
from graphics_menu.dev_guns import _branch, _call, _get
from graphics_menu.gfx_stats import CUSTOM_PRESET, PRESET_LABELS, STAT_COUNT
from graphics_menu.gfx_tune_consts import (
    GFX_SAVE_BP_PATH, GFX_SAVE_CLASS_PATH, GFX_SAVE_QUALITY_FIELD, GFX_SAVE_SLOT,
    GFX_SAVE_TABLE_FIELD, GFX_SAVE_TABLE_LEN, GFX_SAVE_USER_INDEX, GFX_TUNE_VALUES_VAR,
    NODE_CAST_GFX_SAVE,
)
from graphics_menu.loot_find import put
from graphics_menu.save_exit import _chain

FN_SAVE_EXISTS = "/Script/Engine.GameplayStatics.DoesSaveGameExist"
FN_LOAD_SAVE = "/Script/Engine.GameplayStatics.LoadGameFromSlot"
FN_CREATE_SAVE = "/Script/Engine.GameplayStatics.CreateSaveGameObject"
FN_WRITE_SAVE = "/Script/Engine.GameplayStatics.SaveGameToSlot"
FN_ARR_LEN = "/Script/Engine.KismetArrayLibrary.Array_Length"
FN_ARR_SET = "/Script/Engine.KismetArrayLibrary.Array_Set"
FN_MAX_II = "/Script/Engine.KismetMathLibrary.Max"


def build_graphics_savegame():
    """Create (or re-declare) BP_GraphicsSave and compile it. A record, no graph."""
    bp = _create_blueprint(GFX_SAVE_BP_PATH, unreal.SaveGame)
    ed = BGE.get_graph_editor_by_name(bp, "EventGraph")
    _declare(ed, GFX_SAVE_QUALITY_FIELD, BEL.get_basic_type_by_name("int"))
    _declare(ed, GFX_SAVE_TABLE_FIELD, BEL.get_array_type(_float_type()))
    if not BEL.compile_blueprint(bp):
        raise RuntimeError("BP_GraphicsSave failed to compile")
    unreal.get_editor_subsystem(unreal.EditorAssetSubsystem).save_loaded_asset(bp)
    _log(f"built {GFX_SAVE_BP_PATH} (slot {GFX_SAVE_SLOT!r})")
    return bp


def _cast(ed, obj_out, in_execs, x, y, made):
    """Cast to BP_GraphicsSave. Returns (the save, then, CastFailed)."""
    _must_load(GFX_SAVE_BP_PATH)   # a cast node exists only for a loaded class
    cast = _at(_palette(ed, NODE_CAST_GFX_SAVE), x, y)
    made.append(cast)
    _connect(obj_out, _pin(cast, "Object"))
    for e in in_execs:
        _connect(e, _pin(cast, "execute"))
    return (_loose_pin(cast, "AsBPGraphicsSave", is_input=False),
            BEL.find_then_pin(cast), _pin(cast, "CastFailed", is_input=False))


def _field(ed, save, name, x, y, made):
    return _get(ed, name, x, y, made, GFX_SAVE_CLASS_PATH, save)


def author_load_graphics(ed, in_execs, x0, y0):
    """BeginPlay: the saved pick and Custom row over the built defaults (see
    the module docstring). Returns the exec tails."""
    made = []
    exists = _call(ed, FN_SAVE_EXISTS, x0, y0 + 300, made, SlotName=GFX_SAVE_SLOT,
                   UserIndex=GFX_SAVE_USER_INDEX)
    have, none = _branch(ed, out(exists), _chain(exists, in_execs), x0 + 260, y0, made)
    loaded = _call(ed, FN_LOAD_SAVE, x0 + 520, y0, made, SlotName=GFX_SAVE_SLOT,
                   UserIndex=GFX_SAVE_USER_INDEX)
    save, flow, other = _cast(ed, out(loaded), _chain(loaded, [have]), x0 + 800, y0, made)

    # This build's table, or the Custom row would be read off the wrong cells.
    size = _call(ed, FN_ARR_LEN, x0 + 1100, y0 + 440, made,
                 TargetArray=_field(ed, save, GFX_SAVE_TABLE_FIELD, x0 + 840, y0 + 440, made))
    whole = _call(ed, FN_EQ_II, x0 + 1340, y0 + 440, made, A=out(size),
                  B=GFX_SAVE_TABLE_LEN)
    fits, stale = _branch(ed, out(whole), [flow], x0 + 1340, y0, made)

    loop = ed.add_macro_node(MACRO_FOR_LOOP)
    if not loop:
        raise RuntimeError("could not create the ForLoop macro node")
    made.append(_at(loop, x0 + 1600, y0))
    _loose_pin(loop, "FirstIndex").set_pin_value("0")
    _loose_pin(loop, "LastIndex").set_pin_value(str(STAT_COUNT - 1))
    _connect(fits, _pin(loop, "execute"))
    cell = out(_call(ed, FN_ADD_II, x0 + 1900, y0 + 300, made,
                      A=_pin(loop, "Index", is_input=False),
                      B=CUSTOM_PRESET * STAT_COUNT))
    kept = _call(ed, FN_ARR_GET, x0 + 2160, y0 + 500, made,
                 TargetArray=_field(ed, save, GFX_SAVE_TABLE_FIELD, x0 + 1900, y0 + 640,
                                    made))
    _connect(cell, _pin(kept, "Index"))
    write = _call(ed, FN_ARR_SET, x0 + 2440, y0, made,
                  TargetArray=_get(ed, GFX_TUNE_VALUES_VAR, x0 + 2180, y0 + 300, made))
    _connect(cell, _pin(write, "Index"))
    _connect(_pin(kept, "Item", is_input=False), _pin(write, "Item"))
    _connect(_pin(loop, "LoopBody", is_input=False), _pin(write, "execute"))

    # Min then Max, not a Clamp: the verifier reads every Clamp in this graph
    # as a settings slider.
    top = _call(ed, FN_MIN_II, x0 + 2180, y0 + 900, made,
                A=_field(ed, save, GFX_SAVE_QUALITY_FIELD, x0 + 1900, y0 + 900, made),
                B=len(PRESET_LABELS) - 1)
    held = _call(ed, FN_MAX_II, x0 + 2440, y0 + 900, made, A=out(top), B=0)
    picked = put(ed, "Quality", out(held), [_pin(loop, "Completed", is_input=False)],
                 x0 + 2740, y0 + 700, made)
    ed.add_comment_to_nodes(
        f"The player's graphics, from slot {GFX_SAVE_SLOT!r}: the preset they picked "
        f"and their Custom row, over the built defaults. Low, Medium and High stay "
        f"the CSV's. No save, or one from a build with another table: the defaults.",
        made)
    return [picked, none, other, stale]


def author_keep_graphics(ed, in_execs, x0, y0, made):
    """Tick: the pick and the table into a fresh BP_GraphicsSave, saved.
    Returns the exec tails."""
    fresh = _call(ed, FN_CREATE_SAVE, x0, y0, made)
    _pin(fresh, "SaveGameClass").set_pin_value(GFX_SAVE_CLASS_PATH)
    save, flow, failed = _cast(ed, out(fresh), _chain(fresh, in_execs), x0 + 280, y0,
                               made)
    for i, (field, source) in enumerate(((GFX_SAVE_QUALITY_FIELD, "Quality"),
                                         (GFX_SAVE_TABLE_FIELD, GFX_TUNE_VALUES_VAR))):
        n = _at(ed.add_set_member_variable_node(field, GFX_SAVE_CLASS_PATH),
                x0 + 600 + i * 320, y0)
        made.append(n)
        _connect(save, _pin(n, "self"))
        _connect(_get(ed, source, x0 + 340 + i * 320, y0 + 400, made), _pin(n, field))
        _connect(flow, _pin(n, "execute"))
        flow = BEL.find_then_pin(n)
    saved = _call(ed, FN_WRITE_SAVE, x0 + 1260, y0, made, SaveGameObject=save,
                  SlotName=GFX_SAVE_SLOT, UserIndex=GFX_SAVE_USER_INDEX)
    _connect(flow, _pin(saved, "execute"))
    return [BEL.find_then_pin(saved), failed]
