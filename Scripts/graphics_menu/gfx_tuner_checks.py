"""verify_graphics_menu.py's checks for BP_GraphicsTuner (gfx_tuner,
gfx_tuner_foliage, gfx_tuner_sky, gfx_tuner_wind): that each number of the graphics table
reaches the thing it names. The tab that edits the table is gfx_checks.py.

A wire's stat is read off the graph: Values[Base + <literal>], through a
Round for the int stats and a multiply by the stat's scale for the
percentages (gfx_tuner_read.py). A draw distance arrives as a ratio:
metres / (view distance x the level's metres per percent).
"""

import unreal

from forest_generator.grass_cells import GRASS_TAG, tier_tag
from graphics_menu import gfx_stats as GS
from graphics_menu import gfx_tune_consts as GC
from graphics_menu.gfx_tuner import command_prefix, tuner_defaults
from graphics_menu.gfx_tuner_foliage import GRASS_SETTERS, SWITCHED_TIERS
from graphics_menu.gfx_tuner_wind import CM_PER_M
from world.paths import DAY_NIGHT_CLASS_PATH

BEL = unreal.BlueprintEditorLibrary
BGE = unreal.BlueprintGraphEditor
PIN = unreal.BlueprintGraphPinLibrary


def _title(n):
    return str(BEL.get_node_title(n)).replace("\n", " ")


def _pins(n):
    return {str(PIN.get_pin_name(p)) for p in BEL.list_input_pins(n)}


def _sources(n, pin):
    return [PIN.get_owning_node(q) for q in BEL.find_input_pin(n, pin).list_connected_pins()]


def _feeds(n, pin):
    return [_title(s) for s in _sources(n, pin)]


def _literal(n, pin):
    """An int literal; one equal to the pin's default reads "" from disk."""
    return int(float(BEL.find_input_pin(n, pin).get_pin_value() or 0))


def _is_scale(n):
    """A float product with a literal B: a stat x its scale, or the view
    distance x the level's metres per percent."""
    return _pins(n) == {"A", "B"} and "*" in _title(n) and not _sources(n, "B")


def _number(n, pin):
    return float(BEL.find_input_pin(n, pin).get_pin_value() or 0)


def _stats(n, pin):
    """The stat indices wired into ``pin``, straight, through a Round or
    through a scale."""
    out = set()
    for src in _sources(n, pin):
        pins = _pins(src)
        if {"TargetArray", "Index"} <= pins:
            if f"Get {GC.TUNER_VALUES_VAR}" in _feeds(src, "TargetArray"):
                out |= {_literal(add, "B") for add in _sources(src, "Index")
                        if f"Get {GC.TUNER_BASE_VAR}" in _feeds(add, "A")}
        elif pins == {"A"} or _is_scale(src):
            out |= _stats(src, "A")
    return out


def _scale(n, pin):
    """What the stat wired into ``pin`` is multiplied by on the way: 1 when
    it arrives as the table has it."""
    scales = [_number(src, "B") for src in _sources(n, pin) if _is_scale(src)]
    return scales[0] if scales else 1.0


def _metres(n, pin):
    """The draw-distance stats wired into ``pin`` as a ratio to the level's
    own distances: metres / (view distance % x the level's metres per %)."""
    view, out = GS.index_of("view_distance"), set()
    for div in _sources(n, pin):
        if _pins(div) != {"A", "B"} or "/" not in _title(div):
            continue
        for s in _stats(div, "A"):
            per_pct = GS.FULL_VIEW_M.get(GS.GFX_STATS[s].column, 0.0) * GS.PERCENT
            if any(_is_scale(m) and _stats(m, "A") == {view}
                   and abs(_number(m, "B") - per_pct) < 1e-6 for m in _sources(div, "B")):
                out.add(s)
    return out


def _ran(n):
    return bool(BEL.find_input_pin(n, "execute").list_connected_pins())


def _same(a, b):
    if isinstance(b, list):
        a = list(a)
        return len(a) == len(b) and all(abs(float(x) - y) < 1e-6 for x, y in zip(a, b))
    return a == b


def _check_engine(check, nodes):
    gate = [n for n in nodes if _title(n) == "Branch"
            and _feeds(n, "Condition") == [f"Get {GC.TUNER_DIRTY_VAR}"]]
    lowered = [n for n in nodes if _title(n) == f"Set {GC.TUNER_DIRTY_VAR}"
               and str(BEL.find_input_pin(n, GC.TUNER_DIRTY_VAR).get_pin_value()) == "false"]
    check("the tuner's Tick applies only when Dirty, and lowers it",
          len(gate) == 1 and len(lowered) == 1 and _ran(gate[0]),
          f"{len(gate)} gates, {len(lowered)} lowered")

    (level, _st), = GS.stats_by(GS.LEVEL)
    calls = [n for n in nodes if {"Value", "self", "execute"} <= _pins(n)]
    check("one SetOverallScalabilityLevel, from the preset's engine quality",
          len(calls) == 1 and _stats(calls[0], "Value") == {level},
          str([sorted(_stats(n, "Value")) for n in calls]))
    # ApplyNonResolutionSettings takes no arguments: the only node here whose
    # inputs are exactly exec + self.
    applies = [n for n in nodes if _pins(n) == {"execute", "self"}]
    check("...then ApplyNonResolutionSettings, once", len(applies) == 1 and _ran(applies[0]),
          str(len(applies)))
    # Regression guard: ApplySettings also applies *resolution*, which on
    # macOS drives SWindow::SetWindowMode and hangs the editor in PIE.
    check("no ApplySettings anywhere (it hangs macOS PIE on a window-mode change)",
          not [n for n in nodes if "bCheckForCommandLineOverrides" in _pins(n)])

    want = {command_prefix(s.target):
            (i, "InInt" if s.kind is int and s.scale == 1 else "InDouble", s.scale)
            for i, s in GS.stats_by(GS.CVAR)}
    got, loose = {}, []
    commands = [n for n in nodes if "Command" in _pins(n)]
    for n in commands:
        words = _sources(n, "Command")
        if len(words) != 1 or not _ran(n) or "Prefix" not in _pins(words[0]):
            loose.append(_title(n))
            continue
        number = "InInt" if "InInt" in _pins(words[0]) else "InDouble"
        prefix = str(BEL.find_input_pin(words[0], "Prefix").get_pin_value())
        got[prefix] = (next(iter(_stats(words[0], number)), -1), number,
                       round(_scale(words[0], number), 6))
    check(f"one console command per cvar stat ({len(want)}), each built from its own "
          "stat's number (ints rounded, a percentage x 0.01), and nothing else",
          got == want and not loose and len(commands) == len(want),
          str(sorted(set(got.items()) ^ set(want.items()))[:6]) + str(loose))
    # `stat fps` is a toggle, so sending it could as well switch a readout off.
    check("no `stat` console commands (they toggle)",
          not any(p.startswith("stat ") for p in got), str(sorted(got)))


def _check_grass(check, nodes):
    shadows, layers = GS.index_of("grass_shadows"), GS.index_of("grass_layers")
    tagged = sorted(str(BEL.find_input_pin(n, "Tag").get_pin_value())
                    for n in nodes if "Tag" in _pins(n))
    want = sorted([GRASS_TAG, GRASS_TAG] + [tier_tag(t) for t in SWITCHED_TIERS])
    check(f"grass cells are found by their tags ({GRASS_TAG} for the walk and to "
          "tell grass from trees, and one per density tier above the first)",
          tagged == want, str(tagged))
    for _fn, arg in GRASS_SETTERS:
        setters = [n for n in nodes if {arg, "self", "execute"} <= _pins(n)]
        # Driven by the stat, never a literal: a literal would light (or
        # unlight) the grass for every preset alike.
        ok = (len(setters) == 1 and _ran(setters[0]) and all(
            _stats(c, "A") == {shadows} and _literal(c, "B") == 1
            for c in _sources(setters[0], arg)) and _sources(setters[0], arg))
        check(f"{arg} is set once, from grass shadows >= 1", bool(ok), str(len(setters)))
    hides = [n for n in nodes if {"bNewHidden", "self", "execute"} <= _pins(n)]
    rules = sorted((_literal(c, "B"), tuple(_stats(c, "A")))
                   for n in hides for c in _sources(n, "bNewHidden"))
    check("each density tier above the first is hidden while grass layers < its "
          f"number + 1 ({', '.join(str(t + 1) for t in SWITCHED_TIERS)})",
          rules == [(t + 1, (layers,)) for t in SWITCHED_TIERS]
          and all(_ran(n) for n in hides), str(rules))


def _check_distances(check, nodes):
    ratios = {}
    for n in nodes:
        if _pins(n) == {"A", "B"} and "/" in _title(n):
            applied = [t for t in _feeds(n, "B") if t.startswith("Get ")]
            for s in _metres(n, "A"):
                ratios[s] = applied
    want = {GS.index_of("grass_distance"): [f"Get {GC.TUNER_GRASS_DISTANCE_APPLIED_VAR}"],
            GS.index_of("tree_distance"): [f"Get {GC.TUNER_TREE_DISTANCE_APPLIED_VAR}"]}
    check("the grass and the tree cells are scaled by wanted / applied, where wanted "
          "is the stat's metres over what the level draws at the applied view "
          "distance (so a metre is a metre at any view distance)",
          ratios == want, str(ratios))
    fades = [n for n in nodes if {"StartCullDistance", "EndCullDistance", "execute"}
             <= _pins(n)]
    fars = [n for n in nodes if {"NewCullDistance", "self", "execute"} <= _pins(n)]
    check("two walks set a cell's instance fade (SetCullDistances), each after its "
          "max draw distance (the old fade is still what GetCullDistances reads)",
          len(fades) == 2 == len(fars) and all(_ran(n) for n in fars) and all(
              any({"NewCullDistance", "self"} <= _pins(PIN.get_owning_node(q))
                  for q in BEL.find_input_pin(n, "execute").list_connected_pins())
              for n in fades), f"{len(fades)} fades, {len(fars)} max draws")
    # Start and End <- Round <- a float multiply whose B is the ratio itself.
    # Multiply_IntFloat compiled too, and truncated the ratio to an int on
    # the way in: x1.1 did nothing and x0.9 put every distance at zero.
    loose = [pin for n in fades for pin in ("StartCullDistance", "EndCullDistance")
             for r in _sources(n, pin) for m in _sources(r, "A")
             if not any("/" in t for t in _feeds(m, "B"))
             or not any("Float" in t or "Double" in t for t in _feeds(m, "A"))]
    check("...each distance a float product of the old one and the ratio, then "
          "rounded (no int multiply in between)",
          len(fades) == 2 and not loose, str(loose))
    every = [n for n in nodes if "ActorClass" in _pins(n) and "OutActors" in {
        str(PIN.get_pin_name(p)) for p in BEL.list_output_pins(n)}]
    check("the tree walk and the wind walk are every actor (trees carry no tag)",
          len(every) == 2 and all(str(BEL.find_input_pin(n, "ActorClass")
                                      .get_pin_value()).endswith("Actor") for n in every),
          str([str(BEL.find_input_pin(n, "ActorClass").get_pin_value()) for n in every]))
    stale = []
    for var, column, read, rounded in (
            (GC.TUNER_GRASS_DISTANCE_APPLIED_VAR, "grass_distance", _metres, False),
            (GC.TUNER_TREE_DISTANCE_APPLIED_VAR, "tree_distance", _metres, False),
            (GC.TUNER_GRASS_SHADOWS_APPLIED_VAR, "grass_shadows", _stats, True),
            (GC.TUNER_GRASS_LAYERS_APPLIED_VAR, "grass_layers", _stats, True),
            (GC.TUNER_LEVEL_APPLIED_VAR, "engine_quality", _stats, True),
            (GC.TUNER_WIND_APPLIED_VAR, "wind", _stats, True),
            (GC.TUNER_WIND_DISTANCE_APPLIED_VAR, "wind_distance", _stats, True)):
        sets = [n for n in nodes if _title(n) == f"Set {var}"]
        if len(sets) != 1 or read(sets[0], var) != {GS.index_of(column)} or (
                rounded and "Get" in _feeds(sets[0], var)[0]):
            stale.append(var)
    check("each walk records what it applied, so the next apply only redoes what "
          "moved", not stale, str(stale))


def _check_sky(check, nodes):
    cycle = DAY_NIGHT_CLASS_PATH.rsplit(".", 1)[-1][:-2]
    wrong = []
    for index, st in GS.stats_by(GS.CYCLE):
        sets = [n for n in nodes if _title(n) == f"Set {st.target}"
                and any(t.replace(" ", "").endswith(f"CastTo{cycle}")
                        for t in _feeds(n, "self"))]
        if len(sets) != 1 or _stats(sets[0], st.target) != {index} or not _ran(sets[0]) \
                or abs(_scale(sets[0], st.target) - st.scale) > 1e-6:
            wrong.append(st.target)
    check(f"each of the cycle's look multipliers ({len(GS.stats_by(GS.CYCLE))}) is set "
          "from its own stat (a percentage x 0.01), on the level's BP_DayNightCycle",
          not wrong, str(wrong))
    finds = [n for n in nodes if "ActorClass" in _pins(n) and "DayNightCycle" in
             str(BEL.find_input_pin(n, "ActorClass").get_pin_value())]
    check("...found with one GetActorOfClass", len(finds) == 1, str(len(finds)))


def _check_wind(check, nodes):
    wind, reach = GS.index_of("wind"), GS.index_of("wind_distance")
    flags = [n for n in nodes if {"NewValue", "self", "execute"} <= _pins(n)
             and any("Greater" in t or ">=" in t for t in _feeds(n, "NewValue"))]
    ok = (len(flags) == 1 and _ran(flags[0]) and all(
        _stats(c, "A") == {wind} and _literal(c, "B") == 1
        for c in _sources(flags[0], "NewValue")))
    check("every cell's SetEvaluateWorldPositionOffset is set once, from wind >= 1",
          bool(ok), str(len(flags)))
    dists = [n for n in nodes if {"NewValue", "self", "execute"} <= _pins(n)
             and n not in flags]
    ok = (len(dists) == 1 and _ran(dists[0]) and _stats(dists[0], "NewValue") == {reach}
          and abs(_scale(dists[0], "NewValue") - CM_PER_M) < 1e-6)
    check("...and its WPO disable distance once, from wind distance (m x 100)",
          bool(ok), str(len(dists)))
    params = {}
    for n in nodes:
        if {"Collection", "ParameterName", "ParameterValue", "execute"} <= _pins(n):
            name = str(BEL.find_input_pin(n, "ParameterName").get_pin_value())
            mpc = str(BEL.find_input_pin(n, "Collection").get_pin_value())
            params.setdefault(name, []).append((n, "MPC_Wind" in mpc and _ran(n)))
    wrong = []
    for index, st in GS.stats_by(GS.WIND_PARAM):
        got = params.get(st.target, [])
        if len(got) != 1 or not got[0][1]:
            wrong.append(st.target)
            continue
        n = got[0][0]
        if st.target == "Strength":
            # The strength x the wind switch, so off is still even if a cell
            # was missed.
            muls = _sources(n, "ParameterValue")
            ok = len(muls) == 1 and _stats(muls[0], "A") == {index} and abs(
                _scale(muls[0], "A") - st.scale) < 1e-6 and any(
                _stats(c, "InInt") == {wind} for c in _sources(muls[0], "B"))
        else:
            ok = _stats(n, "ParameterValue") == {index} and abs(
                _scale(n, "ParameterValue") - st.scale) < 1e-6
        if not ok:
            wrong.append(st.target)
    check(f"MPC_Wind's {len(GS.stats_by(GS.WIND_PARAM))} scalars are set from their own "
          "stats (a percentage x 0.01; the strength x the wind switch)",
          not wrong and len(params) == len(GS.stats_by(GS.WIND_PARAM)),
          str(wrong) + str(sorted(params)))


def check_gfx_tuner(check):
    bp = unreal.load_asset(GC.TUNER_BP_PATH)
    check("BP_GraphicsTuner exists", bp is not None, GC.TUNER_BP_PATH)
    if bp is None:
        return
    check("...parented to ActorComponent",
          BEL.get_blueprint_parent_class(bp) == unreal.ActorComponent.static_class())
    ed = BGE.get_graph_editor_by_name(bp, "EventGraph")
    check("...and compiles without node errors or warnings",
          BEL.compile_blueprint(bp) and not ed.list_nodes_with_errors()
          and not ed.list_nodes_with_warnings(),
          f"{len(ed.list_nodes_with_errors())} errors, "
          f"{len(ed.list_nodes_with_warnings())} warnings")
    cdo = unreal.get_default_object(BEL.generated_class(bp))
    wrong = [k for k, v in tuner_defaults().items()
             if not _same(cdo.get_editor_property(k), v)]
    check("the tuner starts clean, with the built table, distances applied at 1 and "
          "the level, grass shadows and grass layers never applied",
          not wrong, str(wrong))
    nodes = ed.list_all_nodes()
    _check_engine(check, nodes)
    _check_grass(check, nodes)
    _check_distances(check, nodes)
    _check_sky(check, nodes)
    _check_wind(check, nodes)
