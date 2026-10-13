"""The engine quality groups as rows: a group row moves its own section of
BaseScalability.ini and nothing else, a cvar row keeps what it set, and the
presets are what one engine quality level made them.

    python3 Scripts/dev/uepy.py --game --windowed --probe-timeout 300 \
        --probe Scripts/probes/probe_gfx_groups.py

Every console variable any section of the engine's BaseScalability.ini
names, the sg.* levels and every cvar row's are read before and after each
step (the keys are raised by writing the HUD's GfxTuneRow / GfxTuneNudge):

  - High, then Lumen GI quality 3 -> 2: sg.GlobalIlluminationQuality and the
    cvars [GlobalIlluminationQuality@2] has unlike @3, and no other;
  - shadow resolution down a step: r.Shadow.MaxCSMResolution alone;
  - shadow detail 3 -> 2, after the cvar rows have set six of that group's
    cvars by console: the group still moves its others, and the six stay
    their rows' (a console set outranks scalability, which is the rule that
    lets a row win over its group);
  - shadow cascades down a step, after the group moved: the row still moves
    its cvar;
  - Low: every group at 0, each cvar of the @0 sections as the ini has it,
    and the rows' cvars as Low's row has them.

Standing in the perf audit's forest spot at noon (probe_perf_audit.py) the
frame time is logged as [BENCH] before and after the Lumen GI nudge, and
with the reflection group down too (the strategy's "Lumen at engine level
2" was both). That needs a rendered window: under -nullrhi the numbers are
of an undrawn frame, and only the checks above mean anything.

The player's graphics save is set aside first and put back.
"""

LEVEL = "/Game/Maps/Lvl_Forest_200m"  # the strategy's forest spot is on it
SYSTEMS = ('menu',)

import os
import re
import shutil
import time

import unreal

from graphics_menu import gfx_stats as GS
from graphics_menu import gfx_tune_consts as GC
from graphics_menu import hud_vars as MV
from graphics_menu.profile_consts import PROFILE_CHECKED_VAR
from probes.probe_perf_audit import _forest_spot, _trees
from world import day_night_vars as DV
from world.paths import DAY_NIGHT_BP_PATH, DAY_NIGHT_CLASS_PATH
from world.world_config import hour_to_clock

HUD_BP_PATH = "/Game/UI/BP_GraphicsMenuHUD"
TAB = GC.GFX_TAB
WRITABLE = ([(HUD_BP_PATH, v) for v in (TAB.open_var, TAB.row_var, TAB.nudge_var,
                                        MV.MenuOpen, MV.Quality)]
            + [(DAY_NIGHT_BP_PATH, DV.Clock)])
ROW = {s.column: i + 1 for i, s in enumerate(GS.GFX_STATS)}
STAT = {s.column: s for s in GS.GFX_STATS}
SL = unreal.SystemLibrary
HIGH, LOW = GS.PRESET_LABELS.index("High"), GS.PRESET_LABELS.index("Low")
SETTLE, MEASURE = 1.5, 3.0

# A group row's setter -> its section of the ini and its sg.* variable.
SECTION = {"SetGlobalIlluminationQuality": "GlobalIlluminationQuality",
           "SetReflectionQuality": "ReflectionQuality", "SetShadowQuality": "ShadowQuality",
           "SetPostProcessingQuality": "PostProcessQuality",
           "SetVisualEffectQuality": "EffectsQuality", "SetTextureQuality": "TextureQuality",
           "SetShadingQuality": "ShadingQuality", "SetFoliageQuality": "FoliageQuality",
           "SetAntiAliasingQuality": "AntiAliasingQuality",
           "SetViewDistanceQuality": "ViewDistanceQuality"}
ROW_CVARS = {s.target: s for s in GS.GFX_STATS if s.how == GS.CVAR}


def _log(msg):
    unreal.log_warning(f"[BENCH] {msg}")


def _sections():
    """{(group, level): {cvar: float}} of the engine's BaseScalability.ini."""
    path = os.path.join(unreal.Paths.convert_relative_path_to_full(
        unreal.Paths.engine_config_dir()), "BaseScalability.ini")
    out, here = {}, None
    with open(path) as f:
        for line in f:
            line = line.strip()
            head = re.fullmatch(r"\[(\w+)@(\d)\]", line)
            if line.startswith("["):
                here = out.setdefault((head.group(1), int(head.group(2))), {}) if head else None
            elif here is not None and "=" in line and not line.startswith(";"):
                name, value = line.split("=", 1)
                try:
                    here[name.strip()] = float(value)
                except ValueError:
                    pass
    return out


def _project_pinned():
    """The cvars DefaultEngine.ini sets: project settings outrank scalability,
    so no group moves them (the tuner's docstring)."""
    path = os.path.join(unreal.Paths.convert_relative_path_to_full(
        unreal.Paths.project_config_dir()), "DefaultEngine.ini")
    with open(path) as f:
        return {m.group(1) for m in re.finditer(r"^(r\.[\w.]+)=", f.read(), re.M)}


def _read(names):
    return {n: SL.get_console_variable_float_value(n) for n in names}


def _diff(before, after):
    return {n: after[n] for n in after if abs(after[n] - before[n]) > 1e-6}


def _same(got, want):
    return set(got) == set(want) and all(abs(got[n] - want[n]) < 1e-4 for n in want)


def _moves(sections, group, old, new, skip=()):
    """What a group going old -> new should change: the cvars the new level's
    section has unlike the old's, and its sg.* level."""
    a, b = sections[(group, old)], sections[(group, new)]
    want = {n: v for n, v in b.items() if n not in skip and abs(a.get(n, v + 1) - v) > 1e-6}
    want[f"sg.{group}"] = float(new)
    return want


def _nudge(p, hud, tuner, column, step):
    p.set(hud, TAB.row_var, ROW[column])
    p.set(hud, TAB.nudge_var, step)
    yield lambda: p.get(hud, TAB.nudge_var) == 0
    yield 0.2           # the hand-over on the next Tick, then the tuner's Tick
    yield lambda: not p.get(tuner, GC.TUNER_DIRTY_VAR)


def _preset(p, hud, tuner, q):
    p.set(hud, MV.Quality, q)
    yield lambda: (p.get(hud, GC.GFX_APPLIED_VAR) == q
                   and not p.get(tuner, GC.TUNER_DIRTY_VAR))
    yield 0.3


def _measure(p, cycle, label, out):
    p.set(cycle, DV.Clock, hour_to_clock(12.0))
    yield SETTLE
    p.set(cycle, DV.Clock, hour_to_clock(12.0))
    f0, t0 = SL.get_frame_count(), time.perf_counter()
    yield MEASURE
    frames = max(1, SL.get_frame_count() - f0)
    out[label] = (time.perf_counter() - t0) * 1000.0 / frames
    _log(f"{label:44s} {out[label]:7.2f} ms  ({frames} frames)")


def probe(p):
    save = os.path.join(unreal.Paths.project_saved_dir(), "SaveGames",
                        f"{GC.GFX_SAVE_SLOT}.sav")
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
        return hud if hud is not None and p.get(hud, PROFILE_CHECKED_VAR) else None

    yield lambda: live() is not None
    hud, cycle = live(), p.actor_of(DAY_NIGHT_CLASS_PATH)
    tuner = p.get(hud, GC.TUNER_COMPONENT)
    yield lambda: (p.get(hud, GC.GFX_APPLIED_VAR) != GC.GFX_APPLIED_DEFAULT
                   and not p.get(tuner, GC.TUNER_DIRTY_VAR))
    SL.execute_console_command(p.world(), "t.MaxFPS 0")
    SL.execute_console_command(p.world(), "r.VSync 0")

    sections, pinned = _sections(), _project_pinned()
    groups = {s.column: SECTION[s.target] for s in GS.GFX_STATS if s.how == GS.GROUP}
    names = sorted({n for cvars in sections.values() for n in cvars} | set(ROW_CVARS)
                   | {f"sg.{g}" for g, _lv in sections})
    rows = GS.preset_rows()

    spot, yaw, n_near, n_all = _forest_spot(p, _trees(p))
    _log(f"forest spot {spot.x:.0f},{spot.y:.0f} yaw {yaw:.0f}: {n_near} of {n_all} trees")
    p.pawn().set_actor_location(spot, False, True)
    p.controller().set_control_rotation(unreal.Rotator(pitch=12.0, yaw=yaw, roll=0.0))
    yield from _preset(p, hud, tuner, HIGH)
    p.set(hud, MV.MenuOpen, True)
    p.set(hud, TAB.open_var, True)
    yield 4.0       # shaders, streaming
    ms = {}

    # ── High, and Lumen GI quality one down ──
    high = _read(names)
    levels = {c: high[f"sg.{g}"] for c, g in groups.items()}
    p.check("High runs every engine quality group at 3, as its one engine quality did",
            set(levels.values()) == {3.0}, str(levels))
    yield from _measure(p, cycle, "High", ms)
    yield from _nudge(p, hud, tuner, "gi_quality", -1)
    gi = _read(names)
    want = _moves(sections, "GlobalIlluminationQuality", 3, 2, skip=pinned)
    got = _diff(high, gi)
    p.check(f"Lumen GI quality 3 -> 2 moves sg.GlobalIlluminationQuality and the {len(want) - 1} "
            "cvars its section has unlike level 3's, and no other cvar of any group or row",
            _same(got, want) and len(want) > 5,
            f"unexpected {sorted(set(got) - set(want))}, missing {sorted(set(want) - set(got))}, "
            f"wrong {[n for n in want if n in got and abs(got[n] - want[n]) > 1e-4]}")
    yield from _measure(p, cycle, "High, Lumen GI quality 2", ms)
    yield from _nudge(p, hud, tuner, "reflection_quality", -1)
    yield from _measure(p, cycle, "High, Lumen GI and reflection quality 2", ms)
    yield from _nudge(p, hud, tuner, "reflection_quality", 1)

    # ── a cvar row, a group over cvars that rows hold, a row after its group ──
    before = _read(names)
    yield from _nudge(p, hud, tuner, "shadow_resolution", -1)
    after = _read(names)
    step = STAT["shadow_resolution"]
    res = rows[HIGH][GS.index_of("shadow_resolution")] - step.step
    p.check(f"shadow resolution down a step is {step.target} {res:.0f}, and no other cvar",
            _same(_diff(before, after), {step.target: res}), str(_diff(before, after)))
    yield from _measure(p, cycle, f"...and shadow resolution {res:.0f}", ms)

    held = sorted(set(ROW_CVARS) & set(sections[("ShadowQuality", 2)]))
    yield from _nudge(p, hud, tuner, "shadow_detail", -1)
    moved = _diff(after, _read(names))
    want = _moves(sections, "ShadowQuality", 3, 2, skip=set(held) | pinned)
    p.check(f"shadow detail 3 -> 2 still moves its group's other cvars ({len(want) - 1}) "
            f"after rows set {len(held)} of the group's by console, and those stay their "
            f"rows' ({', '.join(held)})",
            _same(moved, want) and len(want) > 3 and len(held) >= 5,
            f"unexpected {sorted(set(moved) - set(want))}, "
            f"missing {sorted(set(want) - set(moved))}")
    before = _read(names)
    yield from _nudge(p, hud, tuner, "shadow_cascades", -1)
    casc = STAT["shadow_cascades"]
    count = rows[HIGH][GS.index_of("shadow_cascades")] - 1
    p.check(f"...and the cascades row still moves {casc.target} after its group moved "
            f"({count:.0f}), and no other cvar",
            _same(_diff(before, _read(names)), {casc.target: count}),
            str(_diff(before, _read(names))))

    # ── Low ──
    yield from _preset(p, hud, tuner, LOW)
    low = _read(names)
    want = {f"sg.{g}": 0.0 for g in groups.values()}
    for g in groups.values():
        want.update({n: v for n, v in sections[(g, 0)].items() if n not in pinned})
    want.update({name: rows[LOW][GS.index_of(s.column)] * s.scale
                 for name, s in ROW_CVARS.items()})
    wrong = {n: (low[n], v) for n, v in want.items() if abs(low[n] - v) > 1e-4}
    p.check(f"Low is engine quality 0 in every group ({len(want)} cvars: each @0 section "
            "as the ini has it, the cvar rows as Low's row has them)",
            not wrong and len(want) > 100, str(dict(list(wrong.items())[:8])))

    p.set(hud, TAB.open_var, False)
    p.set(hud, MV.MenuOpen, False)
    base, one = ms["High"], ms["High, Lumen GI quality 2"]
    both = ms["High, Lumen GI and reflection quality 2"]
    _log(f"Lumen GI quality 3 -> 2 at High: {base:.1f} -> {one:.1f} ms ({base - one:+.1f}); "
         f"with reflection quality 2 too: {both:.1f} ms ({base - both:+.1f}; the strategy "
         "measured 8 ms for both groups one level down)")
    p.check("the frame time was measured before and after the Lumen nudge",
            all(v > 0 for v in ms.values()) and len(ms) == 4,
            ", ".join(f"{k}: {v:.1f} ms" for k, v in ms.items()))
