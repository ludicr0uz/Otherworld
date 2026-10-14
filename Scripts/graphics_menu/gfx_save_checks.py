"""verify_graphics_menu.py's checks for what the player's graphics keep and
what the CSV decides: BP_GraphicsSave and its load and save in the HUD graph
(gfx_save.py, gfx_tune_tick's hand-over), the default preset the CSV names
(gfx_stats.default_preset) and the graphics tab's SAVE DEFAULT row
(tune_tab.TuneTab.save_widget; tune_tick, tune_draw, wbp_tune).
"""

import unreal

from graphics_menu import gfx_stats as GS
from graphics_menu import gfx_tune_consts as GC
from graphics_menu import umg_consts as UC
from graphics_menu.debug_tune_consts import DEBUG_TAB
from graphics_menu.pause_checks import _feeds, _gates, _pins, _sets, _sources, _value
from graphics_menu.presets import DEFAULT_PRESET
from graphics_menu.tune_tabs import TABS
from graphics_menu.umg_checks import _tree

BEL = unreal.BlueprintEditorLibrary
TAB = GC.GFX_TAB


def _int(n, pin):
    """A literal equal to its pin's default reads back empty once loaded."""
    return int(float(_value(n, pin) or 0))


def _on_slot(nodes, *pins):
    return [n for n in nodes if {"SlotName", *pins} <= _pins(n)
            and _value(n, "SlotName") == GC.GFX_SAVE_SLOT]


def _check_asset(check):
    bp = unreal.EditorAssetLibrary.load_asset(GC.GFX_SAVE_BP_PATH)
    check("BP_GraphicsSave exists and is a USaveGame", bp is not None
          and BEL.get_blueprint_parent_class(bp) == unreal.SaveGame.static_class(),
          GC.GFX_SAVE_BP_PATH)
    if not bp:
        return
    names = sorted(str(n) for n in BEL.list_member_variable_names(bp, False))
    cdo = unreal.get_default_object(BEL.generated_class(bp))
    check("...holding the picked preset and the table, and nothing else",
          names == sorted((GC.GFX_SAVE_QUALITY_FIELD, GC.GFX_SAVE_TABLE_FIELD))
          and isinstance(cdo.get_editor_property(GC.GFX_SAVE_QUALITY_FIELD), int)
          and len(cdo.get_editor_property(GC.GFX_SAVE_TABLE_FIELD)) == 0, str(names))


def _check_default(check):
    marked = []
    with open(GS.CSV_PATH, newline="") as f:
        header = f.readline().strip().split(",")
        col = header.index(GS.DEFAULT_COLUMN) if GS.DEFAULT_COLUMN in header else -1
        for line in f:
            cells = line.strip().split(",")
            if col >= 0 and len(cells) > col and float(cells[col] or 0) != 0.0:
                marked.append(cells[0])
    check("the presets are Low / Medium / High / Custom, Custom the last",
          GS.PRESET_LABELS == ("Low", "Medium", "High", "Custom")
          and GS.CUSTOM_PRESET == len(GS.PRESET_LABELS) - 1, str(GS.PRESET_LABELS))
    check(f"graphics_tuning.csv marks one preset as the default (its "
          f"{GS.DEFAULT_COLUMN!r} column), and that is the built default",
          len(marked) == 1 and marked[0] in GS.PRESET_LABELS
          and GS.PRESET_LABELS.index(marked[0]) == GS.default_preset() == DEFAULT_PRESET,
          f"marked {marked}, built {DEFAULT_PRESET}")


def _check_load(check, nodes):
    reads = [n for n in _on_slot(nodes, "UserIndex") if "SaveGameObject" not in _pins(n)]
    asks = [n for n in reads if "Exist" in str(BEL.get_node_title(n))]
    loads = [n for n in reads if "Load" in str(BEL.get_node_title(n))]
    check(f"BeginPlay loads slot {GC.GFX_SAVE_SLOT!r} only if it is on disk",
          len(asks) == 1 and len(loads) == 1, f"{len(asks)} asks, {len(loads)} loads")

    table = f"Get {GC.GFX_SAVE_TABLE_FIELD}"
    writes = [n for n in nodes if {"TargetArray", "Index", "Item", "bSizeToFit"} <= _pins(n)
              and f"Get {TAB.values_var}" in _feeds(n, "TargetArray")
              and any(table in _feeds(s, "TargetArray") for s in _sources(n, "Item"))]

    def sized(n, size):
        """``n``'s loop runs only on a saved table of ``size`` cells."""
        return [c for g in _sources(n, "execute") if "LastIndex" in _pins(g)
                and (_int(g, "FirstIndex"), _int(g, "LastIndex")) == (0, GS.STAT_COUNT - 1)
                for b in _gates(g) for c in _sources(b, "Condition")
                if _pins(c) == {"A", "B"} and _int(c, "B") == size
                and any(table in _feeds(s, "TargetArray") for s in _sources(c, "A"))]

    def cell(n):
        return [_int(a, "B") for a in _sources(n, "Index") if _pins(a) == {"A", "B"}]
    own = [n for n in writes if sized(n, GC.GFX_SAVE_TABLE_LEN)]
    check("...and lays only the save's Custom row over the table: one write, cell "
          f"{GS.CUSTOM_PRESET} x {GS.STAT_COUNT} + i for each of the {GS.STAT_COUNT} stats, "
          f"when the saved table is this build's size ({GC.GFX_SAVE_TABLE_LEN})",
          len(own) == 1 and cell(own[0]) == [GS.CUSTOM_PRESET * GS.STAT_COUNT],
          f"{len(own)} of {len(writes)} writes")
    _check_legacy(check, nodes, [n for n in writes if n not in own], sized, cell)
    picks = [n for n in _sets(nodes, "Quality")
             if any(f"Get {GC.GFX_SAVE_QUALITY_FIELD}" in _feeds(m, "A")
                    and _int(m, "B") == len(GS.PRESET_LABELS) - 1
                    for hi in _sources(n, "Quality") for m in _sources(hi, "A"))]
    check("...then Quality is the saved pick, held inside the presets (Max of Min, "
          "not a Clamp)", len(picks) == 1
          and not any("Clamp" in t for t in _feeds(picks[0], "Quality")),
          str([_feeds(n, "Quality") for n in picks]))


def _check_legacy(check, nodes, writes, sized, cell):
    """A save from before the engine quality row was split."""
    legacy = [n for n in writes if sized(n, GC.GFX_SAVE_LEGACY_LEN)]
    old_row = GS.CUSTOM_PRESET * GS.LEGACY_STAT_COUNT
    # Item <- SavedTable[GfxLegacySource[i] + the old Custom row].
    mapped = [n for n in legacy for kept in _sources(n, "Item")
              for add in _sources(kept, "Index") if _pins(add) == {"A", "B"}
              and _int(add, "B") == old_row
              and any(f"Get {GC.GFX_LEGACY_SOURCE_VAR}" in _feeds(src, "TargetArray")
                      for src in _sources(add, "A"))]
    check(f"a saved table of the size before the split ({GC.GFX_SAVE_LEGACY_LEN}) is "
          "not dropped: its Custom row is laid over today's, each stat from the old "
          f"cell {GC.GFX_LEGACY_SOURCE_VAR} names",
          len(legacy) == 1 == len(mapped) and len(writes) == 1
          and cell(legacy[0]) == [GS.CUSTOM_PRESET * GS.STAT_COUNT],
          f"{len(legacy)} legacy of {len(writes)} other writes, {len(mapped)} mapped")
    by_level = sorted(
        _int(n, "Index") for n in nodes
        if {"TargetArray", "Index", "Item", "bSizeToFit"} <= _pins(n)
        and f"Get {TAB.values_var}" in _feeds(n, "TargetArray")
        and any(f"Get {GC.GFX_LEGACY_BY_LEVEL_VAR}" in _feeds(s, "TargetArray")
                for s in _sources(n, "Item")))
    check("...then the shadow maps' sizes and the cascades are the old engine "
          "quality's, read from the by-level table into their own cells",
          by_level == sorted(GS.CUSTOM_PRESET * GS.STAT_COUNT + GS.index_of(c)
                             for c in GS.BY_LEVEL_COLUMNS), str(by_level))


def _check_keep(check, nodes):
    saves = _on_slot(nodes, "SaveGameObject")
    fields = {GC.GFX_SAVE_QUALITY_FIELD: "Get Quality",
              GC.GFX_SAVE_TABLE_FIELD: f"Get {TAB.values_var}"}
    wrong = [f for f, source in fields.items()
             if [_feeds(n, f) for n in _sets(nodes, f)] != [[source]]]
    check(f"a change is kept: Quality and the table into a BP_GraphicsSave, saved to "
          f"slot {GC.GFX_SAVE_SLOT!r}, from one place",
          len(saves) == 1 and not wrong, f"{len(saves)} saves, wrong {wrong}")
    makers = [n for n in nodes if "SaveGameClass" in _pins(n)
              and _value(n, "SaveGameClass").endswith(GC.GFX_SAVE_CLASS_PATH.split(".")[-1])]
    firsts = [c for n in makers for b in _gates(n) for c in _sources(b, "Condition")
              if _pins(c) == {"A", "B"} and f"Get {GC.GFX_APPLIED_VAR}" in _feeds(c, "A")
              and _int(c, "B") == GC.GFX_APPLIED_DEFAULT]
    check("...but not the session's first hand-over (GfxQualityApplied still "
          f"{GC.GFX_APPLIED_DEFAULT}): that is the save itself, or the defaults",
          len(makers) == 1 and len(firsts) == 1, f"{len(makers)} makers, {len(firsts)} gates")


def _check_save_row(check, nodes):
    tree = _tree(UC.WBP_PAUSE_MENU)
    row, is_var = tree.get(TAB.save_widget, (None, False))
    words = str(row.get_editor_property(UC.ROW_TEXT_VAR)) if row else None
    check(f"the graphics tab has a {GC.GFX_SAVE_DEFAULT_LABEL} row, a variable under "
          "its list, the caret's stop between the list and BACK",
          bool(row) and is_var and words == GC.GFX_SAVE_DEFAULT_LABEL
          and TAB.save_row == TAB.row_count and TAB.back_row == TAB.row_count + 1,
          f"{words!r}, save row {TAB.save_row}, BACK {TAB.back_row}")
    asks = [n for n in _sets(nodes, TAB.save_var) if _value(n, TAB.save_var) == "true"]

    def on_save_row(n):
        return any(_pins(c) == {"A", "B"} and f"Get {TAB.row_var}" in _feeds(c, "A")
                   and _int(c, "B") == TAB.save_row
                   for g in _gates(n) for outer in _gates(g)
                   for c in _sources(outer, "Condition"))
    keyed = [n for n in asks if on_save_row(n)]
    clicked = [n for n in asks if n not in keyed]
    check("Enter saves the defaults only with the caret on that row (an Enter on a "
          "number saves nothing), and a click on the row saves too",
          len(keyed) == 1 and len(clicked) == 1, f"{len(keyed)} keyed, {len(clicked)} clicked")
    carets = [n for n in _sets(nodes, TAB.row_var) if not _sources(n, TAB.row_var)
              and _int(n, TAB.row_var) == TAB.save_row]
    check("...and the cursor over it takes the caret", len(carets) == 1, str(len(carets)))
    # The debug tab's row is its FULL STATS cheat (debug_tune_checks.py).
    others = [t.action for t in TABS if t not in (TAB, DEBUG_TAB)
              and (t.save_widget or t.back_row != t.row_count)]
    check("the other tabs, but the debug tab's FULL STATS, keep Enter as their save: "
          "no save row, BACK right after the list", not others, str(others))


def check_gfx_save(check, nodes):
    _check_asset(check)
    _check_default(check)
    _check_load(check, nodes)
    _check_keep(check, nodes)
    _check_save_row(check, nodes)
