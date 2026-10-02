"""verify_graphics_menu.py's checks for the GRAPHICS TUNING tab on the HUD
(gfx_tune_tick, tune_draw and wbp_tune over GFX_TAB), the table it holds and
the M panel's title. What the numbers do to the engine is BP_GraphicsTuner's:
gfx_tuner_checks.py.
"""

import unreal

from combat.verify.common import component_template
from graphics_menu import gfx_stats as GS
from graphics_menu import gfx_tune_consts as GC
from graphics_menu import tune_consts as TC
from graphics_menu import umg_consts as UC
from graphics_menu.gfx_tune_tick import gfx_tune_defaults
from graphics_menu.presets import DEFAULT_PRESET, PRESETS
from graphics_menu.umg_checks import _tree

BEL = unreal.BlueprintEditorLibrary
PIN = unreal.BlueprintGraphPinLibrary
TAB = GC.GFX_TAB


def _title(n):
    return str(BEL.get_node_title(n)).replace("\n", " ")


def _pins(n):
    return {str(PIN.get_pin_name(p)) for p in BEL.list_input_pins(n)}


def _same(a, b):
    a, b = list(a), list(b)
    return len(a) == len(b) and all(
        abs(float(x) - float(y)) < 1e-6 if isinstance(y, float) else x == y
        for x, y in zip(a, b))


def _sources(n, pin):
    return [PIN.get_owning_node(q) for q in BEL.find_input_pin(n, pin).list_connected_pins()]


def _feeds(n, pin):
    return [_title(s) for s in _sources(n, pin)]


def _sets(nodes, var):
    return [n for n in nodes if _title(n) == f"Set {var}"]


def _check_table(check):
    rows = GS.preset_rows()
    out = [f"{label}.{s.column}={v}" for label, row in zip(GS.PRESET_LABELS, rows)
           for s, v in zip(GS.GFX_STATS, row) if not s.lo - 1e-6 <= v <= s.hi + 1e-6]
    check(f"every preset's {GS.STAT_COUNT} numbers are inside their stat's limits",
          len(rows) == len(GS.PRESET_LABELS) and not out, str(out[:6]))
    split = [s.column for i, s in enumerate(GS.GFX_STATS) if i >= GS.LOOK_FROM
             and len({row[i] for row in rows}) != 1]
    check("the look stats (brightness, sun, moon, stars, ambient, fog density) "
          "are one number for all four presets", not split, str(split))
    table = GS.read_table()
    check("graphics_tuning.csv has a row for every preset and a cell for every stat",
          set(table) == set(GS.PRESET_LABELS)
          and all(set(table[p]) == set(GS.GFX_COLUMNS) for p in table),
          f"{GS.CSV_PATH}: rows {sorted(table)}")
    # A person's units: draw distances in metres, every scale a percentage.
    units = {s.column: s.label for s in GS.GFX_STATS}
    loose = [s.label for s in GS.GFX_STATS if "(x)" in s.label
             or (s.scale != 1 and not s.label.endswith("(%)"))]
    check("the draw distances are in metres and every scale is a percentage "
          "(no bare multipliers)",
          units["grass_distance"].endswith("(m)") and units["tree_distance"].endswith("(m)")
          and not loose and GS.index_of("view_distance") >= 0, str(loose))
    view = GS.GFX_STATS[GS.index_of("view_distance")].defaults
    at_full = {c: [round(m / (pct * GS.PERCENT))
                   for m, pct in zip(GS.GFX_STATS[GS.index_of(c)].defaults, view)]
               for c in GS.FULL_VIEW_M}
    check("...the default metres are the levels' own distances at each preset's view "
          "distance (grass 70 m, trees 300 m at 100%)",
          all(set(v) == {round(GS.FULL_VIEW_M[c])} for c, v in at_full.items()),
          str(at_full))
    wanted = {"grass_distance", "tree_distance", "grass_layers", "fog", "fog_density",
              "leaf_cutouts", "brightness", "sun_light", "moon_light", "stars",
              "ambient_light"}
    check("the table covers grass and tree draw distance, grass density, fog on/off "
          "and density, leaves, brightness, the sun, the moon and the stars",
          wanted <= set(GS.GFX_COLUMNS), str(sorted(wanted - set(GS.GFX_COLUMNS))))


def _check_widgets(check):
    widgets = {name: w for name, (w, _var) in _tree(UC.WBP_PAUSE_MENU).items()}
    title = widgets.get("PauseTitle")
    words = str(title.get_editor_property("text")) if title else ""
    check('the M panel is titled "GAME SETTINGS"',
          UC.PAUSE_TITLE == "GAME SETTINGS" and words == UC.PAUSE_TITLE, repr(words))
    box = widgets.get(TAB.rows_box)
    labels = [str(k.get_editor_property(UC.ROW_TEXT_VAR))
              for k in (box.get_all_children() if box else [])]
    check(f"WBP_PauseMenu has the graphics tuning panel, its {TAB.row_count} rows "
          f"labelled preset then each stat, and the saved line",
          TAB.panel in widgets and TAB.saved_text in widgets
          and labels == list(TAB.row_labels), str(labels))
    hidden = [n for n in (TAB.panel, TAB.saved_text) if n in widgets
              and "COLLAPSED" in str(widgets[n].get_editor_property("visibility")).upper()]
    check("...collapsed until the HUD shows it", len(hidden) == 2, str(hidden))
    check("the M panel lists the graphics tab",
          GC.GFX_TUNE_ROW_LABEL in UC.PAUSE_ROW_LABELS, str(UC.PAUSE_ROW_LABELS))
    # Out of the picture's way: the bottom-right corner, a small title.
    panel = widgets.get(TAB.panel)
    slot = panel.get_editor_property("slot") if panel else None
    place = (slot.get_anchors().get_editor_property("minimum"),
             slot.get_anchors().get_editor_property("maximum"),
             slot.get_alignment(), slot.get_position()) if slot else None
    check("the graphics panel is anchored to the bottom-right corner of the screen, "
          "its own bottom-right a margin in from it",
          bool(place) and all((v.x, v.y) == (1.0, 1.0) for v in place[:3])
          and place[3].x < 0 and place[3].y < 0,
          str([(v.x, v.y) for v in place]) if place else "no panel")
    font = widgets[TAB.title_widget].get_editor_property("font").get_editor_property(
        "size") if TAB.title_widget in widgets else None
    check(f"...and its title is small ({GC.GFX_TITLE_FONT:g} pt, the other tabs' "
          f"{TC.TUNE_TITLE_FONT:g})",
          font is not None and abs(font - GC.GFX_TITLE_FONT) < 1e-3
          and GC.GFX_TITLE_FONT < TC.TUNE_TITLE_FONT, str(font))


def _check_presets(check, nodes):
    """BeginPlay and the tab's preset row only set Quality; nothing in the
    HUD graph reaches the engine. The M panel has no preset rows or keys."""
    sets = _sets(nodes, "Quality")
    literal = sorted(int(BEL.find_input_pin(n, "Quality").get_pin_value() or 0)
                     for n in sets if not _sources(n, "Quality"))
    driven = [n for n in sets if _sources(n, "Quality")]
    check("BeginPlay sets Quality to the default preset: the one literal Set (the "
          "M panel has no preset rows; the graphics tab's preset row picks one)",
          literal == [DEFAULT_PRESET]
          and not set(UC.PAUSE_ROW_LABELS) & {p.label for p in PRESETS}, str(literal))
    picked = [n for n in driven if _feeds(n, "Quality") == [f"Get {TAB.pick_var}"]]
    check("...and the tab's preset row sets it from GfxTunePick; the one other driven "
          "Set is the save's pick at BeginPlay (gfx_save_checks.py)",
          len(picked) == 1 and len(driven) == 2,
          str([_feeds(n, "Quality") for n in driven]))
    follows = [n for n in _sets(nodes, TAB.pick_var)
               if _feeds(n, TAB.pick_var) == ["Get Quality"]]
    check("...otherwise the pick follows Quality, so the tab shows the running preset",
          len(follows) == 1, str(len(follows)))
    engine = [n for n in nodes
              if {"Command", "bCheckForCommandLineOverrides"} & _pins(n)
              or ("Tag" in _pins(n) and "ComponentClass" not in _pins(n))
              or "ScalabilityLevel" in _title(n).replace(" ", "")]
    check("the HUD graph issues no console command, scalability call or tag walk "
          "of its own: BP_GraphicsTuner applies a preset",
          not engine, str([_title(n) for n in engine]))


def _check_graph(check, nodes):
    runs = [n for n in nodes if "PythonCommand" in _pins(n)
            and str(BEL.find_input_pin(n, "PythonCommand").get_pin_value())
            == TAB.save_command]
    check("the graphics tab's SAVE DEFAULT runs gfx_tune_save through "
          "ExecutePythonCommand, once, into GfxTuneSaved",
          len(runs) == 1 and f"Set {TAB.saved_var}" in [
              _title(PIN.get_owning_node(q))
              for q in BEL.find_output_pin(runs[0], "ReturnValue").list_connected_pins()],
          str(len(runs)))

    writes = [n for n in nodes if {"TargetArray", "Index", "Item", "bSizeToFit"} <= _pins(n)
              and f"Get {TAB.values_var}" in _feeds(n, "TargetArray")]
    nudged = [n for n in writes if any("Min" in t for t in _feeds(n, "Item"))]
    held = [f for n in nudged for m in _sources(n, "Item") for f in _feeds(m, "A")]
    # The third write is BeginPlay's: the saved Custom row (gfx_save_checks.py).
    loaded = [n for n in writes if any("TargetArray" in _pins(s) for s in _sources(n, "Item"))
              and not _sources(n, "Item")[0] in nudged
              and any(f"Get {GC.GFX_SAVE_TABLE_FIELD}" in _feeds(s, "TargetArray")
                      for s in _sources(n, "Item"))]
    spread = [n for n in writes if n not in nudged and n not in loaded]
    check("a graphics nudge writes GfxTuneValues, held between the stat's minimum "
          "and maximum (FMin of FMax)",
          len(nudged) == 1 and any("Max" in t for t in held), f"{len(nudged)}: {held}")
    check("...and a second write spreads the picked preset's look stats over every "
          f"preset (stat index >= {GS.LOOK_FROM})",
          len(writes) == 3 and len(spread) == 1 and len(loaded) == 1
          and any(str(BEL.find_input_pin(n, "B").get_pin_value()) == str(GS.LOOK_FROM)
                  for n in nodes if "GreaterEqual" in _title(n).replace(" ", "")
                  or ">=" in _title(n)),
          f"{len(writes)} writes, {len(spread)} spread")

    tuner = f"Get {GC.TUNER_COMPONENT}"
    wrong = []
    for var, source in ((GC.TUNER_VALUES_VAR, f"Get {TAB.values_var}"),
                        (GC.TUNER_PRESET_VAR, "Get Quality")):
        sets = [n for n in _sets(nodes, var) if tuner in _feeds(n, "self")]
        if len(sets) != 1 or _feeds(sets[0], var) != [source]:
            wrong.append(var)
    dirty = [n for n in _sets(nodes, GC.TUNER_DIRTY_VAR) if tuner in _feeds(n, "self")]
    if len(dirty) != 1 or str(BEL.find_input_pin(
            dirty[0], GC.TUNER_DIRTY_VAR).get_pin_value()) != "true":
        wrong.append(GC.TUNER_DIRTY_VAR)
    check("the HUD hands the tuner the table, Quality as its preset, and Dirty, "
          "once each", not wrong, str(wrong))
    gates = [n for n in nodes if _title(n) == "Branch" and any(
        "OR" in _title(o).upper()
        and f"Get {TAB.touched_var}" in _feeds(o, "A")
        and any(f"Get {GC.GFX_APPLIED_VAR}" in _feeds(q, "B") for q in _sources(o, "B"))
        for o in _sources(n, "Condition"))]
    check("...when a number was touched or Quality differs from GfxQualityApplied",
          len(gates) == 1, str(len(gates)))
    kept = _sets(nodes, GC.GFX_APPLIED_VAR)
    check("...which is then set to Quality, and GfxTuneTouched lowered",
          len(kept) == 1 and _feeds(kept[0], GC.GFX_APPLIED_VAR) == ["Get Quality"]
          and any(str(BEL.find_input_pin(n, TAB.touched_var).get_pin_value()) == "false"
                  for n in _sets(nodes, TAB.touched_var)),
          str([_feeds(n, GC.GFX_APPLIED_VAR) for n in kept]))


def check_gfx_tune(check, bp, nodes):
    cdo = unreal.get_default_object(BEL.generated_class(bp))
    defaults = gfx_tune_defaults()
    wrong = [k for k, v in defaults.items()
             if not (_same(cdo.get_editor_property(k), v) if isinstance(v, list)
                     else cdo.get_editor_property(k) == v)]
    check("the graphics tab starts shut, untouched, on the default preset, with the "
          f"built table ({len(GS.PRESET_LABELS)} presets x {GS.STAT_COUNT} stats) and "
          f"nothing applied ({GC.GFX_APPLIED_VAR} {GC.GFX_APPLIED_DEFAULT}, so the "
          "first Tick applies)", not wrong, str(wrong))
    comp = component_template(bp, GC.TUNER_COMPONENT)
    check(f"the HUD carries a {GC.TUNER_COMPONENT} component of BP_GraphicsTuner",
          comp is not None and comp.get_class().get_path_name() == GC.TUNER_CLASS_PATH,
          str(comp.get_class().get_path_name() if comp else None))
    _check_table(check)
    _check_widgets(check)
    _check_presets(check, nodes)
    _check_graph(check, nodes)
