"""verify_graphics_menu.py's checks for what the tabs keep between sessions:
BP_TuneSave and each kept tab's load and save in the HUD graph (tune_keep.py),
then the graphics tab's own (gfx_save_checks.py).
"""

import unreal

from graphics_menu import tune_keep_consts as KC
from graphics_menu.gfx_save_checks import check_gfx_save
from graphics_menu.gfx_tune_consts import GFX_TAB
from graphics_menu.pause_checks import _feeds, _gates, _pins, _sets, _sources, _title, _value
from graphics_menu.tune_tabs import TABS

BEL = unreal.BlueprintEditorLibrary


def _check_asset(check):
    bp = unreal.EditorAssetLibrary.load_asset(KC.TUNE_SAVE_BP_PATH)
    check("BP_TuneSave exists and is a USaveGame", bp is not None
          and BEL.get_blueprint_parent_class(bp) == unreal.SaveGame.static_class(),
          KC.TUNE_SAVE_BP_PATH)
    if not bp:
        return
    names = sorted(str(n) for n in BEL.list_member_variable_names(bp, False))
    cdo = unreal.get_default_object(BEL.generated_class(bp))
    fields = sorted((KC.TUNE_SAVE_TABLE_FIELD, KC.TUNE_SAVE_BUILT_FIELD))
    check("...holding a tab's table and the built table it was made over, both "
          "empty, and nothing else",
          names == fields and all(len(cdo.get_editor_property(f)) == 0 for f in fields),
          str(names))


def _check_tabs(check):
    unkept = [t.action for t in TABS if not t.kept]
    slots = [t.keep_slot for t in KC.KEPT_TABS]
    check("every tab but the graphics one is kept, each in a slot of its own",
          unkept == [GFX_TAB.action] and len(set(KC.KEPT_SLOTS)) == len(KC.KEPT_SLOTS)
          and len(slots) == len(TABS) - 1, f"unkept {unkept}, slots {slots}")


def _check_tab(check, nodes, cdo, tab):
    on_slot = [n for n in nodes if {"SlotName", "UserIndex"} <= _pins(n)
               and _value(n, "SlotName") == tab.keep_slot]
    reads = [n for n in on_slot if "SaveGameObject" not in _pins(n)]
    asks = [n for n in reads if "Exist" in _title(n)]
    loads = [n for n in reads if "Load" in _title(n)]
    saves = [n for n in on_slot if "SaveGameObject" in _pins(n)]
    check(f"{tab.title_text}: BeginPlay loads slot {tab.keep_slot!r} only if it is "
          "on disk, and one place saves it",
          (len(asks), len(loads), len(saves)) == (1, 1, 1),
          f"{len(asks)} asks, {len(loads)} loads, {len(saves)} saves")

    built = f"Get {tab.built_var}"
    takes = [n for n in _sets(nodes, tab.values_var)
             if f"Get {KC.TUNE_SAVE_TABLE_FIELD}" in _feeds(n, tab.values_var)]
    same = [c for n in takes for g in _gates(n) for both in _sources(g, "Condition")
            if _pins(both) == {"A", "B"}
            for c in _sources(both, "A") + _sources(both, "B")
            if {"ArrayA", "ArrayB"} <= _pins(c)
            and f"Get {KC.TUNE_SAVE_BUILT_FIELD}" in _feeds(c, "ArrayA")
            and built in _feeds(c, "ArrayB")]
    check("...the saved table replaces the HUD's only when the save was made over "
          "this build's table (a changed CSV wins), and is the same size",
          len(takes) == 1 and len(same) == 1, f"{len(takes)} takes, {len(same)} gates")
    backs = [int(float(_value(n, "Index") or 0)) for n in nodes
             if {"TargetArray", "Index", "Item", "bSizeToFit"} <= _pins(n)
             and f"Get {tab.values_var}" in _feeds(n, "TargetArray")
             and any(built in _feeds(s, "TargetArray") for s in _sources(n, "Item"))]
    check(f"...but for its session-only cells {list(tab.unkept_cells)}, which take "
          "the built ones back", sorted(backs) == sorted(tab.unkept_cells), str(backs))
    raised = [n for n in _sets(nodes, tab.touched_var)
              if not _sources(n, tab.touched_var) and _value(n, tab.touched_var) == "true"]
    check("...and a loaded table is touched, so the tab's apply runs: a second "
          "place raises the flag, beside the nudge", len(raised) == 2, str(len(raised)))

    wrong = [f for f, source in ((KC.TUNE_SAVE_BUILT_FIELD, built),
                                 (KC.TUNE_SAVE_TABLE_FIELD, f"Get {tab.values_var}"))
             if not any(_feeds(n, f) == [source] and saves
                        and n in _upstream(saves[0]) for n in _sets(nodes, f))]
    check("...a nudge saves the table and the built one it was made over",
          bool(saves) and not wrong, f"wrong {wrong}")
    kept = [float(v) for v in cdo.get_editor_property(tab.built_var)]
    table = [float(v) for v in cdo.get_editor_property(tab.values_var)]
    check(f"...the built copy ({tab.built_var}) is the built table, cell for cell",
          bool(kept) and kept == table, f"{len(kept)} against {len(table)}")


def _upstream(node, limit=6):
    """The nodes whose exec leads into ``node``, ``limit`` steps back."""
    seen, todo = [], [node]
    for _ in range(limit):
        todo = [s for n in todo for s in _sources(n, "execute") if s not in seen]
        seen += todo
    return seen


def check_kept(check, bp, nodes):
    _check_asset(check)
    _check_tabs(check)
    cdo = unreal.get_default_object(BEL.generated_class(bp))
    for tab in KC.KEPT_TABS:
        _check_tab(check, nodes, cdo, tab)
    check_gfx_save(check, nodes)
