"""verify_graphics_menu.py's checks for the UMG screens: their saved widget
trees (the designer half) and the HUD graph that creates and writes them.
Here rather than in the verifier, which is over its size budget.

The trees are read back through UMGToolSet's GetWidgets, the same door the
builders write through (umg_author.py).
"""

import re

import unreal

from combat.tuning import INVENTORY_SIZE
from graphics_menu import settings_rows as S
from graphics_menu import umg_consts as C
from graphics_menu.profile_consts import EXIT_CALLED_OFF_TEXT
from graphics_menu.umg_author import toolset

BEL = unreal.BlueprintEditorLibrary
PIN = unreal.BlueprintGraphPinLibrary

# Every widget the HUD graph writes to, per screen. Each has to be a variable
# of its screen, or the HUD's member reads have nothing to read.
WRITTEN = {
    C.WBP_HUD: (C.HUD_BODY, C.HUD_FPS, C.HP_BAR, C.HP_NUM, C.KILLS, C.BANNER_COUNT,
                C.BANNER_OFF, C.SLOTS, C.EQUIPPED_NAME, C.STAMINA_BAR)
               + tuple(C.stat_bar(s) for s, _l, _c in C.SURVIVAL_BARS)
               + tuple(C.debuff_text(s) for _t, _l, s in C.DEBUFF_LABELS),
    C.WBP_MAIN_MENU: (C.TITLE_PANEL, C.TITLE_ROWS, C.SETTINGS_PANEL, C.SETTINGS_ROWS_BOX,
                      C.HINT_IDLE, C.HINT_CAPTURE),
    C.WBP_PAUSE_MENU: (C.PAUSE_ROWS,),
    C.WBP_DEATH_MENU: (C.DEATH_SCORE,),
    C.WBP_MENU_ROW: (C.ROW_CARET, C.ROW_LABEL_BOX, C.ROW_LABEL, C.ROW_VALUE),
    C.WBP_INVENTORY_SLOT: (C.SLOT_ACTIVE, C.SLOT_ICON, C.SLOT_AMMO, C.SLOT_FRAME),
}


def _tree(asset):
    """{widget name: (widget template, is_variable)} of a saved Widget Blueprint."""
    wbp = unreal.load_asset(asset)
    if not wbp:
        return {}
    infos = toolset().call_method("GetWidgets", (wbp,)).get_editor_property("widgets")
    return {str(i.get_editor_property("widget_name")):
            (i.get_editor_property("widget"), i.get_editor_property("is_variable"))
            for i in infos}


def _labels(tree, stack):
    w = tree.get(stack, (None, False))[0]
    return [str(r.get_editor_property(C.ROW_TEXT_VAR)) for r in w.get_all_children()] if w else []


def row_labels(asset, stack):
    """The LabelText of each WBP_MenuRow in ``stack``, in order."""
    return _labels(_tree(asset), stack)


def text_literal(node):
    """A Text pin's literal as the words it holds: the pin reads back as
    NSLOCTEXT("", "<key>", "<words>"), or empty when unset."""
    raw = _value(node, "InText")
    m = re.search(r'"([^"]*)"\)\s*$', raw)
    return m.group(1) if m else raw


def _title(n):
    return str(BEL.get_node_title(n)).replace("\n", " ")


def _pins(n):
    return {str(PIN.get_pin_name(p)) for p in BEL.list_input_pins(n)}


def _value(n, pin):
    return str(BEL.find_input_pin(n, pin).get_pin_value())


def _sources(n, pin):
    p = BEL.find_input_pin(n, pin)
    return [PIN.get_owning_node(q) for q in (p.list_connected_pins() if p and p.is_valid() else [])]


def _source_titles(n, pin):
    return [_title(s) for s in _sources(n, pin)]


def check_trees(check):
    """The designer half: what each screen holds, says and is anchored to."""
    trees = {asset: _tree(asset) for asset in WRITTEN}
    check("the four UMG screens and their two parts are built",
          all(trees.values()), str([a for a, t in trees.items() if not t]))
    missing = [f"{a.rsplit('/', 1)[1]}.{n}" for a, names in WRITTEN.items()
               for n in names if not trees[a].get(n, (None, False))[1]]
    check("every widget the HUD writes to is a variable of its screen",
          not missing, str(missing))

    main, pause = trees[C.WBP_MAIN_MENU], trees[C.WBP_PAUSE_MENU]
    title_rows = _labels(main, C.TITLE_ROWS)
    check("the title page's rows are NEW GAME then SETTINGS, the order MenuRow picks",
          title_rows == list(C.MENU_ROWS), str(title_rows))
    rows = _labels(main, C.SETTINGS_ROWS_BOX)
    check(f"the settings page has its {S.SETTINGS_ROWS} rows in the order MenuRow "
          "indexes them",
          len(rows) == S.SETTINGS_ROWS
          and rows[:len(S.SLIDERS)] == [sl.label for sl in S.SLIDERS]
          and rows[S.DIFFICULTY_ROW] == S.DIFFICULTY_LABEL
          and rows[S.FIRST_BIND_ROW:S.BACK_ROW] == list(S.BIND_LABELS)
          and rows[S.BACK_ROW] == S.BACK_LABEL, str(rows))
    check("...with one bind row per BIND_VARS entry",
          len(S.BIND_LABELS) == len(S.BIND_VARS), f"{len(S.BIND_LABELS)} labels")
    pause_rows = _labels(pause, C.PAUSE_ROWS)
    check("the M panel lists the presets, then debug, then save and exit",
          pause_rows == list(C.PAUSE_ROW_LABELS)
          and pause_rows[C.PAUSE_DEBUG_ROW].endswith("debug"), str(pause_rows))

    texts = set()
    for tree in trees.values():
        for w, _var in tree.values():
            if isinstance(w, unreal.TextBlock):
                texts.add(str(w.get_editor_property("text")))
    want = {C.GAME_TITLE, C.GAME_SUBTITLE, C.MAIN_HINT, C.SETTINGS_TITLE_TEXT,
            C.HINT_IDLE_TEXT, C.HINT_CAPTURE_TEXT, C.PAUSE_TITLE, C.PAUSE_HINT,
            C.DEATH_TITLE, C.DEATH_HINT, "HP", "STA", EXIT_CALLED_OFF_TEXT}
    want |= {label for _s, label, _c in C.SURVIVAL_BARS}
    want |= {label for _t, label, _s in C.DEBUFF_LABELS}
    check("the screens' static text is in the designer, where it can be edited",
          want <= texts, str(sorted(want - texts)))

    hud = trees[C.WBP_HUD]
    grid = hud.get(C.SLOTS, (None, False))[0]
    cells = list(grid.get_all_children()) if grid else []
    places = sorted((c.get_editor_property("slot").get_editor_property("row"),
                     c.get_editor_property("slot").get_editor_property("column"))
                    for c in cells)
    check(f"the grid holds {INVENTORY_SIZE} slots, {C.INVENTORY_COLUMNS} to a row",
          len(cells) == INVENTORY_SIZE
          and all(c.get_class().get_name() == "WBP_InventorySlot_C" for c in cells)
          and places == [(i // C.INVENTORY_COLUMNS, i % C.INVENTORY_COLUMNS)
                         for i in range(INVENTORY_SIZE)], str(places))
    slot = trees[C.WBP_INVENTORY_SLOT]
    cell = slot.get("Cell", (None, False))[0]
    icon = slot.get(C.SLOT_ICON, (None, False))[0]
    size = (cell.get_editor_property("width_override"),
            cell.get_editor_property("height_override")) if cell else None
    # A DeprecateSlateVector2D exposes no fields; its text form is the way in.
    icon_size = (icon.get_editor_property("brush").get_editor_property("image_size")
                 .export_text() if icon else "")
    want_icon = f"(X={C.SLOT_ICON_W:.6f},Y={C.SLOT_ICON_H:.6f})"
    check("a slot is 84 x 59 with a 78 x 35 icon (30% under the old 120 x 84)",
          size == (C.SLOT_W, C.SLOT_H) and icon_size == want_icon,
          f"{size}, icon {icon_size}")
    strip = hud.get("Strip", (None, False))[0]
    order = [str(w.get_name()) for w in strip.get_all_children()] if strip else []
    pad = grid.get_editor_property("slot_padding").left if grid else None
    check("the stamina bar is under the grid, as wide as its slots and gaps",
          order == [C.EQUIPPED_NAME, C.SLOTS, "StaminaRow"]
          and C.ST_BAR_SIZE[0] == C.INVENTORY_COLUMNS * C.SLOT_W
          + (C.INVENTORY_COLUMNS - 1) * C.SLOT_GAP and pad == C.SLOT_GAP / 2.0,
          f"{order}, bar {C.ST_BAR_SIZE[0]}, gap {pad}")

    def anchor(tree, name):
        w = tree.get(name, (None, False))[0]
        if not w:
            return None
        s = w.get_editor_property("slot")
        a = s.get_anchors()
        return (a.minimum.x, a.minimum.y, a.maximum.x, a.maximum.y), \
            (s.get_alignment().x, s.get_alignment().y)
    edges = {"Stats": ((0.0, 0.0, 0.0, 0.0), (0.0, 0.0)),
             C.KILLS: ((1.0, 0.0, 1.0, 0.0), (1.0, 0.0)),
             C.HUD_FPS: ((1.0, 0.0, 1.0, 0.0), (1.0, 0.0)),
             C.BANNER_COUNT: ((0.5, 0.0, 0.5, 0.0), (0.5, 0.0)),
             "Strip": ((0.5, 1.0, 0.5, 1.0), (0.5, 1.0)),
             C.HUD_BODY: ((0.0, 0.0, 1.0, 1.0), (0.0, 0.0))}
    wrong = [n for n, want_at in edges.items() if anchor(hud, n) != want_at]
    centred = ((0.5, 0.5, 0.5, 0.5), (0.5, 0.5))
    wrong += [n for n in (C.TITLE_PANEL, C.SETTINGS_PANEL) if anchor(main, n) != centred]
    if anchor(trees[C.WBP_DEATH_MENU], "Panel") != centred:
        wrong.append("the death panel")
    check("each HUD element is anchored to its corner or edge, each menu centred",
          not wrong, str(wrong))
    fps = hud.get(C.HUD_FPS, (None, False))[0]
    parent = fps.get_parent().get_name() if fps and fps.get_parent() else None
    check("the FPS readout sits outside Body, so it shows over every screen",
          parent == "Root", str(parent))


def check_hud_graph(check, nodes):
    """The HUD graph's half: the screens are created, shown one at a time, and
    written from the game's values."""
    made = {_value(n, "Class") for n in nodes if {"Class", "OwningPlayer"} <= _pins(n)}
    want = {C.class_path(asset) for _v, asset, _z in C.SCREENS}
    check("BeginPlay creates each of the four screens once, for the owning player",
          made == want, str(sorted(made)))
    added = sorted(int(_value(n, "ZOrder")) for n in nodes if _pins(n) == {"execute", "self", "ZOrder"})
    check("...and adds each to the viewport, menus above the HUD",
          added == sorted(z for _v, _a, z in C.SCREENS), str(added))

    shows = [n for n in nodes if "InVisibility" in _pins(n)]
    literals = {_value(n, "InVisibility") for n in shows}
    check("no screen ever takes a click: shown means HitTestInvisible",
          literals == {C.SHOWN, C.HIDDEN}, str(sorted(literals)))

    def toggles(target):
        on = off = 0
        for n in shows:
            if f"Get {target}" in _source_titles(n, "self") or target in _source_titles(n, "self"):
                if _value(n, "InVisibility") == C.SHOWN:
                    on += 1
                else:
                    off += 1
        return on, off
    body = toggles(C.HUD_BODY)
    check("the title and death screens hide the HUD's Body, and play shows it",
          body == (1, 2), f"shown {body[0]}, hidden {body[1]}")
    hud_on = toggles(C.UI_VAR[C.WBP_HUD])
    check("WBP_HUD itself is shown at BeginPlay and never hidden (DrawHUD "
          "toggles its Body)", hud_on == (1, 0), f"shown {hud_on[0]}, hidden {hud_on[1]}")
    for var, asset, _z in C.SCREENS[1:]:
        on, off = toggles(var)
        check(f"{asset.rsplit('/', 1)[1]} is shown from exactly one place",
              on == 1 and off >= 2, f"shown {on}, hidden {off}")
    for name in (C.HUD_FPS, C.BANNER_COUNT, C.BANNER_OFF, C.HINT_IDLE, C.HINT_CAPTURE,
                 *(C.debuff_text(s) for _t, _l, s in C.DEBUFF_LABELS)):
        on, off = toggles(name)
        check(f"{name} is shown and hidden by its own condition", on == 1 and off >= 1,
              f"shown {on}, hidden {off}")

    percents = [n for n in nodes if "InPercent" in _pins(n)]
    targets = sorted(t for n in percents for t in _source_titles(n, "self"))
    want_bars = sorted(f"Get {b}" for b in (C.HP_BAR, C.STAMINA_BAR)
                       + tuple(C.stat_bar(s) for s, _l, _c in C.SURVIVAL_BARS))
    check("HP, stamina and the three survival bars are filled from a fraction",
          targets == want_bars and all(_sources(n, "InPercent") for n in percents),
          str(targets))
    fills = [n for n in nodes if _pins(n) == {"execute", "self", "InColor"}]
    check("the stamina fill is recoloured while sprinting",
          len(fills) == 1 and _source_titles(fills[0], "InColor") == ["SelectColor"],
          str([_source_titles(n, "InColor") for n in fills]))

    carets = [n for n in nodes if "InOpacity" in _pins(n)]
    selected = []
    for n in carets:
        for pick in _sources(n, "InOpacity"):
            for eq in _sources(pick, "bPickA"):
                selected += _source_titles(eq, "B")
    check("the title page, settings page and M panel light the selected row's caret",
          sorted(selected) == ["Get MenuRow", "Get MenuRow", "Get Quality"],
          str(sorted(selected)))

    texts = [n for n in nodes if {"self", "InText"} <= _pins(n)]
    blank = [n for n in texts if not text_literal(n) and not _sources(n, "InText")]
    check("every SetText has a literal or a wire", not blank, f"{len(blank)} empty")
    written = sorted(t for n in texts for t in _source_titles(n, "self")
                     if t.startswith("Get ") and _sources(n, "InText"))
    for name in (C.HP_NUM, C.KILLS, C.DEATH_SCORE, C.HUD_FPS, C.EQUIPPED_NAME,
                 C.SLOT_AMMO, C.BANNER_COUNT):
        check(f"{name} is written from the game, not a literal",
              f"Get {name}" in written)
    literal = {text_literal(n) for n in texts if not _sources(n, "InText")}
    check("the debug row reads ON or OFF", literal == {C.DEBUG_ON, C.DEBUG_OFF},
          str(sorted(literal)))

    brushes = [n for n in nodes if {"Texture", "bMatchSize"} <= _pins(n)]
    check("each slot's icon is the carried item's own",
          len(brushes) == 1 and _source_titles(brushes[0], "Texture") == ["Get Icon"],
          str([_source_titles(n, "Texture") for n in brushes]))
    guards = [n for n in nodes if {"TargetArray", "IndexToTest"} <= _pins(n)]
    check("an inventory slot reads its item only behind IsValidIndex, and so "
          "does the equipped name", len(guards) == 2, str(len(guards)))
