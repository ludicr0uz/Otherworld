"""Medium, step by step, and how far it really draws: the frame at the engine
level and the draw distances Medium had before G2 and at G2's, and a picture
of the grass past 250 m and the trees past 350 m, shown and hidden.

    OW_REACH_LABEL=after python3 Scripts/dev/uepy.py --game --windowed \
        --seconds 600 --probe-timeout 580 --probe Scripts/probes/probe_medium_reach.py
    ... --map /Game/Maps/Lvl_Forest_1000m      (the 1 km map: its trees)

It needs a rendered window (--windowed). The rows are moved by the GRAPHICS
SETTINGS tab's own nudge (probe_gfx_groups.py's way), so the numbers do not
depend on what graphics_tuning.csv holds today: a run before a change to the
CSV and a run after it measure the same three states.

  the frame   at the perf audit's forest spot, noon (probe_perf_audit.py's
              method): OLD, then the ten engine groups and the three shadow
              rows at level 2, then the grass at 300 m and the trees at
              400 m, and back down again, so each state is measured twice.
              Saved/uepy/bench/medium_reach_<label>.json.
  the reach   with the rows at NEW. The numbers first: a cell's instance fade
              and its own max draw distance, times r.ViewDistanceScale. Then
              the frame itself, because the mesh's LODs and the cell's bounds
              can cut shorter than the numbers say: the view is put 255 m
              (350 m for trees) short of two cells, everything else that grows
              is hidden and the fog is off (at noon it turns anything 300 m
              away the sky's colour), and the frame is pictured with those cells shown,
              hidden, and shown again (what two frames of one state differ
              by). Then from past the cells' own max draw distance, where
              nothing of them may be left. The grass cells are drawn white
              for it (their own material, turned up): a clump 300 m off is a
              pixel and a half of olive on olive ground. The frames are
              compared where those cells are on the screen.
              assets/generated/undergrowth/<OW_REACH_PREFIX, default g2_>reach_*.png.

The player's graphics save is set aside first and put back.
"""

LEVEL = "/Game/Maps/Lvl_Forest_200m"  # the perf audit's spot; --map for the 1 km map
SYSTEMS = ('load', 'menu')
import json
import math
import os
import shutil

from forest_generator.grass_cells import GRASS_CELL_CM, GRASS_TIERS, tier_tag
from graphics_menu import gfx_stats as GS
from probes import png_pixels
from probes import probe_gfx_groups as G
from probes import probe_grass_look as K
from probes import probe_perf_audit as B

WRITABLE = G.WRITABLE
unreal = B.unreal
SL = unreal.SystemLibrary

LABEL = os.environ.get("OW_REACH_LABEL", "run")
PREFIX = os.environ.get("OW_REACH_PREFIX", "g2_")
MEDIUM = GS.PRESET_LABELS.index("Medium")

SHADOWS = ("shadow_resolution", "light_shadow_resolution", "shadow_cascades")
GROUPS = tuple(s.column for s in GS.GROUP_STATS)
# Medium before G2, and G2's.
OLD = {**{c: 1 for c in GROUPS}, **{c: GS.SHADOW_BY_LEVEL[c][1] for c in SHADOWS},
       "grass_distance": 180, "tree_distance": 180}
NEW = {**{c: 2 for c in GROUPS}, **{c: GS.SHADOW_BY_LEVEL[c][2] for c in SHADOWS},
       "grass_distance": 300, "tree_distance": 400}
LEVEL_ROWS, DISTANCE_ROWS = GROUPS + SHADOWS, ("grass_distance", "tree_distance")

# The view's height over the ground it looks at, and how far short of the
# cells it stands: what must be drawn, and what must not.
EYE_UP_CM = 6000.0
REACH = {"grass": {"near_m": 255.0}, "tree": {"near_m": 350.0}}
# OW_REACH_NEAR="tree:150" looks from another distance (to find where a thing
# stops being drawn); the checks' labels follow it.
for _part in filter(None, os.environ.get("OW_REACH_NEAR", "").split(",")):
    REACH[_part.split(":")[0]]["near_m"] = float(_part.split(":")[1])
# A clump 300 m off is a pixel and a half of olive on olive ground: nothing a
# picture can show. For the pictures the cells looked at are drawn by a copy
# of their own material turned up to white (MA_Grass's parameters,
# forest_generator/grass_look.py), which changes neither their culling, their
# LODs nor the blades' cut-out.
PAINT = {"Brightness": 40.0, "Subsurface Strengh": 40.0, "Saturation": 0.0}
PAINT_TINT = "Tint"
# The frame is compared where the cells are on the screen, this far round.
BOX_PAD_PX = 8
ONLY_REACH = bool(os.environ.get("OW_REACH_ONLY"))
SHOT_SETTLE = 2.0
# A pixel has changed when a channel moved by more than this (of 255).
PIXEL_THRESHOLD = 8


def _value(tuner, column):
    values = tuner.get_editor_property(str(G.GC.TUNER_VALUES_VAR))
    return values[MEDIUM * GS.STAT_COUNT + GS.index_of(column)]


def _move(p, hud, tuner, wanted):
    """Nudge Medium's rows to ``wanted`` (column -> value)."""
    for column, target in wanted.items():
        for _ in range(400):
            now = _value(tuner, column)
            if abs(now - target) < 1e-6:
                break
            yield from G._nudge(p, hud, tuner, column, 1 if target > now else -1)
        else:
            raise RuntimeError(f"{column} did not reach {target}: {_value(tuner, column)}")


def _only(wanted, columns):
    return {c: wanted[c] for c in columns}


def _prop(obj, *names):
    for name in names:
        try:
            return obj.get_editor_property(name)
        except Exception:
            continue
    raise RuntimeError(f"{type(obj).__name__} has none of {names}: "
                       f"{[n for n in dir(obj) if 'cull' in n or 'draw' in n]}")


def _cell(actor):
    origin, _extent = SL.get_component_bounds(B._root(actor))[:2]
    return (math.floor(origin.x / GRASS_CELL_CM), math.floor(origin.y / GRASS_CELL_CM)), origin


def _distances(actors):
    """(instance fade end, the cell's max draw distance) in metres on the
    ground: the smallest of each over ``actors``."""
    scale = SL.get_console_variable_float_value("r.ViewDistanceScale")
    ends, draws = [], []
    for a in actors:
        c = B._root(a)
        ends.append(_prop(c, "instance_end_cull_distance") * scale / 100.0)
        draws.append(_prop(c, "cached_max_draw_distance") * scale / 100.0)
    return min(ends), min(draws), scale


def _in_band(actors, eye, lo_m, hi_m):
    """(the places of the instances of ``actors`` lo..hi metres from ``eye``,
    every instance's place, the nearest one's distance in metres)."""
    inside, every, nearest = [], [], float("inf")
    for a in actors:
        c = B._root(a)
        for i in range(c.get_instance_count()):
            t = c.get_instance_transform(i, True).translation
            d = math.dist((t.x, t.y, t.z), (eye.x, eye.y, eye.z)) / 100.0
            nearest = min(nearest, d)
            every.append(t)
            if lo_m < d < hi_m:
                inside.append(t)
    return inside, every, nearest


def _screen_box(p, places, width):
    """The box of the picture (``width`` pixels wide) ``places`` fall in."""
    pc = p.controller()
    size = unreal.WidgetLayoutLibrary.get_viewport_size(p.world())
    per = width / size.x
    xs, ys = [], []
    for place in places[::max(1, len(places) // 400)]:
        got = unreal.GameplayStatics.project_world_to_screen(pc, place, False)
        at = got[-1] if isinstance(got, tuple) else got
        if at is not None and (at.x or at.y):
            xs.append(at.x * per)
            ys.append(at.y * per)
    if not xs:
        return None
    return (int(min(xs)) - BOX_PAD_PX, int(min(ys)) - BOX_PAD_PX,
            int(max(xs)) + BOX_PAD_PX, int(max(ys)) + BOX_PAD_PX)


def _look(p, targets, short_m):
    """Stand the view ``short_m`` short of the target cells' near edge (x = 0),
    up in the air, looking down at the ground just past that edge."""
    pawn, pc = p.pawn(), p.controller()
    ground = sum(_cell(a)[1].z for a in targets) / len(targets)
    eye = unreal.Vector(-short_m * 100.0, 0.0, ground + EYE_UP_CM)
    aim = unreal.Vector(2000.0, 0.0, ground)
    pawn.set_actor_hidden_in_game(True)
    for actor in unreal.GameplayStatics.get_all_actors_of_class(p.world(), unreal.Actor):
        if pawn in (actor.get_attach_parent_actor(), actor.get_owner()):    # what it holds
            actor.set_actor_hidden_in_game(True)
    pawn.get_editor_property("character_movement").set_movement_mode(
        unreal.MovementMode.MOVE_NONE)
    pawn.set_actor_location(eye, False, True)
    pc.set_control_rotation(unreal.MathLibrary.find_look_at_rotation(eye, aim))


def _pictured(p, name):
    yield SHOT_SETTLE
    yield from K._shot(p, name)
    return png_pixels.read(os.path.join(K.OUT_DIR, name))


def _paint(targets):
    """Draw ``targets`` white; returns what they drew with."""
    was = []
    for a in targets:
        c = B._root(a)
        for slot in range(c.get_num_materials()):
            was.append((c, slot, c.get_material(slot)))
            white = c.create_dynamic_material_instance(slot, was[-1][2])
            for name, value in PAINT.items():
                white.set_scalar_parameter_value(name, value)
            white.set_vector_parameter_value(PAINT_TINT, unreal.LinearColor(1.0, 1.0, 1.0, 1.0))
    return was


def _reach(p, cycle, level, kind, targets, row_m, cell_m, paint):
    """Picture ``targets`` from short of the row's distance (where they must
    be drawn) and from past their cells' own max draw distance (where nothing
    of them may be: an instanced mesh culls by cluster, so between the two
    some still are)."""
    near_m = REACH[kind]["near_m"]
    stem = f"{PREFIX}reach_{level}_{kind}"
    pc = p.controller()
    seen = {}
    was = _paint(targets) if paint else []
    far_m = cell_m + GRASS_CELL_CM * math.sqrt(0.5) / 100.0 + 15.0
    for where, short_m in (("near", near_m), ("far", far_m)):
        _look(p, targets, short_m)
        p.set(cycle, "Clock", B.hour_to_clock(12.0))
        yield 2.0
        eye = pc.get_editor_property("player_camera_manager").get_camera_location()
        inside, every, nearest = _in_band(targets, eye, near_m, row_m)
        B._hide(p, targets, True)
        bare = yield from _pictured(p, f"{stem}_{where}_bare.png")
        os.remove(os.path.join(K.OUT_DIR, f"{stem}_{where}_bare.png"))
        B._hide(p, targets, False)
        shown = yield from _pictured(p, f"{stem}_{where}_shown.png")
        B._hide(p, targets, True)
        hidden = yield from _pictured(p, f"{stem}_{where}_hidden.png")
        box = _screen_box(p, inside if where == "near" else every, shown[0])
        drawn, _ = png_pixels.changed(shown, hidden, PIXEL_THRESHOLD, box)
        noise, _ = png_pixels.changed(bare, hidden, PIXEL_THRESHOLD, box)
        seen[where] = {"drawn": drawn, "noise": noise, "box": box, "inside": len(inside),
                       "nearest_m": round(nearest, 1)}
        B._log(f"reach {kind} {where}: view {short_m:.0f} m short, nearest instance "
               f"{nearest:.1f} m, {len(inside)} of {len(every)} inside {near_m:.0f}-"
               f"{row_m:.0f} m, on the screen in {box}; there {drawn} pixels differ "
               f"shown/hidden, {noise} hidden/hidden")
    B._hide(p, targets, True)
    for c, slot, material in was:
        c.set_material(slot, material)
    near, far = seen["near"], seen["far"]
    p.check(f"{kind}: what stands past {near_m:.0f} m is drawn at Medium",
            near["nearest_m"] > near_m and near["inside"] > 0 and near["box"] is not None
            and near["drawn"] > max(40, 4 * near["noise"]), str(near))
    p.check(f"{kind}: nothing is drawn from past its cell's {cell_m:.0f} m",
            far["nearest_m"] > cell_m and far["box"] is not None
            and far["drawn"] <= max(40, 2 * far["noise"]), str(far))
    return seen


def probe(p):
    save = os.path.join(unreal.Paths.project_saved_dir(), "SaveGames",
                        f"{G.GC.GFX_SAVE_SLOT}.sav")
    kept = save + ".probe-backup"
    if os.path.exists(save):
        shutil.move(save, kept)
    try:
        yield from _run(p)
    finally:
        if os.path.exists(save):
            os.remove(save)
        if os.path.exists(kept):
            shutil.move(kept, save)


def _run(p):
    def live():
        try:
            hud = p.hud()
        except Exception:
            return None
        return hud if hud is not None and p.get(hud, B.PROFILE_CHECKED_VAR) else None

    level = p.world().get_name()
    B.OUT_NAME = f"medium_reach_{LABEL}_{level}.json"
    del B.RESULTS[:]
    yield lambda: live() is not None
    hud, cycle = live(), p.actor_of(B.DAY_NIGHT_CLASS_PATH)
    tuner = p.get(hud, B.GC.TUNER_COMPONENT)
    yield lambda: not p.get(tuner, B.GC.TUNER_DIRTY_VAR)
    B._cmd(p, "t.MaxFPS 0")
    B._cmd(p, "r.VSync 0")
    yield 4.0       # shaders, streaming
    trees, grass = B._trees(p), K._grass_cells(p)
    bushes = [a for a in B._grass(p) if a not in grass]
    spot, yaw, n_near, n_all = B._forest_spot(p, trees)
    B._log(f"{level}: forest spot {spot.x:.0f},{spot.y:.0f} yaw {yaw:.0f}: {n_near} of "
           f"{n_all} trees in 35 m; {len(grass)} grass cells, {len(trees)} tree cells")
    pawn, pc = p.pawn(), p.controller()
    pawn.set_actor_location(spot, False, True)
    yield from B._preset(p, hud, tuner, MEDIUM)
    pc.set_control_rotation(unreal.Rotator(pitch=12.0, yaw=yaw, roll=0.0))
    yield 2.5

    # ── The frame, state by state ────────────────────────────────────────
    states = (("old", OLD),
              ("level 2", _only(NEW, LEVEL_ROWS)),
              ("level 2 + distances", _only(NEW, DISTANCE_ROWS)),
              ("level 2 + distances", {}),
              ("level 2", _only(OLD, DISTANCE_ROWS)),
              ("old", _only(OLD, LEVEL_ROWS)))
    seen = {}
    for name, rows in (() if ONLY_REACH else states):
        yield from _move(p, hud, tuner, rows)
        turn = len(seen.setdefault(name, [])) + 1
        yield from B._measure(p, cycle, f"Medium {name} {turn}", 12.0)
        seen[name].append(B.RESULTS[-1]["ms"])
    mean = {name: round(sum(ms) / len(ms), 2) for name, ms in seen.items()}
    B._log(f"{level} Medium: {mean}")
    if not ONLY_REACH:
        p.check("Medium's frame measured at its old rows, at level 2 and at the new "
                "distances", all(len(ms) == 2 for ms in seen.values()), str(seen))

    # ── The reach ────────────────────────────────────────────────────────
    yield from _move(p, hud, tuner, NEW)
    base = [a for a in grass
            if not any(a.actor_has_tag(tier_tag(t)) for t in range(1, len(GRASS_TIERS)))]
    g_end, g_draw, scale = _distances(base)
    t_end, t_draw, _ = _distances(trees)
    half_diagonal_m = GRASS_CELL_CM * math.sqrt(0.5) / 100.0
    B._log(f"reach numbers at view distance {scale:.2f}: grass base tier fades out at "
           f"{g_end:.1f} m, its cells at {g_draw:.1f} m; trees at {t_end:.1f} m, their "
           f"cells at {t_draw:.1f} m")
    p.check("the grass's base layer fades out at the row's 300 m, its cells no sooner",
            abs(g_end - NEW["grass_distance"]) < 1.0
            and g_draw >= NEW["grass_distance"] + half_diagonal_m,
            f"fade end {g_end:.1f} m, cell max draw {g_draw:.1f} m")
    p.check("the trees fade out at the row's 400 m, their cells no sooner",
            abs(t_end - NEW["tree_distance"]) < 1.0
            and t_draw >= NEW["tree_distance"] + half_diagonal_m,
            f"fade end {t_end:.1f} m, cell max draw {t_draw:.1f} m")

    everything = grass + bushes + trees
    # The noon haze turns anything 300 m off the sky's colour. It culls
    # nothing; the next preset applied puts the row's fog back.
    B._cmd(p, "r.Fog 0")
    was_hidden = {a: a.get_editor_property("hidden") for a in everything}
    B._hide(p, everything, True)
    out = {}
    for kind, cells, row, cell_m in (("grass", base, "grass_distance", g_draw),
                                     ("tree", trees, "tree_distance", t_draw)):
        targets = [a for a in cells if _cell(a)[0] in ((0, -1), (0, 0))]
        if not targets:
            p.check(f"{kind}: cells at the map's middle to look at", False, "none")
            continue
        out[kind] = yield from _reach(p, cycle, level, kind, targets, float(NEW[row]),
                                      cell_m, paint=kind == "grass")
    for a, hidden in was_hidden.items():
        a.set_actor_hidden_in_game(hidden)
    B.RESULTS.append({"label": "reach", "grass_fade_m": round(g_end, 1),
                      "grass_cell_m": round(g_draw, 1), "tree_fade_m": round(t_end, 1),
                      "tree_cell_m": round(t_draw, 1), "pictures": out})
    with open(os.path.join(B.OUT_DIR, B.OUT_NAME), "w") as f:
        json.dump(B.RESULTS, f, indent=1)
