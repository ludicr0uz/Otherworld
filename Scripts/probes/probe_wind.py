"""Wind: the graphics tab's four wind rows reach the grass and the trees.

  - the preset applied at the start (whichever the game opened on) has its
    wind: every grass, bush and tree cell evaluates world-position offset
    (or not) as its wind row says, with the WPO disable distance its wind
    distance row's metres, and MPC_Wind's Strength and Speed its look rows;
  - wind off: every cell stops evaluating WPO, and Strength is 0;
  - wind on again: back, and Strength back;
  - wind distance up a step: every cell's disable distance follows;
  - wind strength and speed up: MPC_Wind's scalars follow, and the look
    numbers are in every preset's row.

The keys are raised by writing the HUD's GfxTuneRow / GfxTuneNudge (a probe
has no keyboard). A nudge saves the player's graphics, so their save
(Saved/SaveGames/OtherworldGraphics.sav) is set aside first and put back.
What the wind looks like needs a rendered run: a headless one draws nothing.
"""

SYSTEMS = ('world',)

import os
import shutil

import unreal

from forest_generator.wind import MPC_PATH, PARAM_SPEED, PARAM_STRENGTH
from graphics_menu import gfx_stats as GS
from graphics_menu import gfx_tune_consts as GC
from graphics_menu.profile_consts import PROFILE_CHECKED_VAR
from graphics_menu import hud_vars as MV

HUD_BP_PATH = "/Game/UI/BP_GraphicsMenuHUD"
TAB = GC.GFX_TAB
WRITABLE = [(HUD_BP_PATH, v) for v in (TAB.open_var, TAB.row_var, TAB.nudge_var, MV.MenuOpen)]
ROW = {s.column: i + 1 for i, s in enumerate(GS.GFX_STATS)}
ISM = unreal.InstancedStaticMeshComponent


def _save_file():
    return os.path.join(unreal.Paths.project_saved_dir(), "SaveGames",
                        f"{GC.GFX_SAVE_SLOT}.sav")


def probe(p):
    save, kept = _save_file(), _save_file() + ".probe-backup"
    if os.path.exists(save):
        shutil.copy2(save, kept)
    try:
        yield from _run(p)
    finally:
        if os.path.exists(save):
            os.remove(save)
        if os.path.exists(kept):
            shutil.move(kept, save)


def _settled(p, hud):
    return (p.get(hud, GC.GFX_APPLIED_VAR) == p.get(hud, "Quality")
            and not p.get(p.get(hud, GC.TUNER_COMPONENT), GC.TUNER_DIRTY_VAR))


def _nudge(p, hud, column, step):
    p.set(hud, TAB.row_var, ROW[column])
    p.set(hud, TAB.nudge_var, step)
    yield lambda: p.get(hud, TAB.nudge_var) == 0
    yield 0.15          # the hand-over on the next Tick, then the tuner's Tick
    yield lambda: _settled(p, hud)


def _cell(p, hud, column):
    values = list(p.get(hud, TAB.values_var))
    return float(values[p.get(hud, "Quality") * GS.STAT_COUNT + GS.index_of(column)])


def _cells(p):
    """Every actor whose root is an instanced mesh: grass, bushes, trees."""
    out = []
    for a in unreal.GameplayStatics.get_all_actors_of_class(p.world(), unreal.Actor):
        root = a.get_editor_property("root_component")
        if isinstance(root, ISM):
            out.append(root)
    return out


def _wpo(cells):
    return sorted({(bool(c.get_editor_property("evaluate_world_position_offset")),
                    int(c.get_editor_property("world_position_offset_disable_distance")))
                   for c in cells})


def _mpc(p, name):
    return unreal.MaterialLibrary.get_scalar_parameter_value(
        p.world(), unreal.load_asset(MPC_PATH), name)


def _want(p, hud):
    on = _cell(p, hud, "wind") >= 1
    return ([(on, int(round(_cell(p, hud, "wind_distance"))) * 100)],
            _cell(p, hud, "wind_strength") * 0.01 * on,
            _cell(p, hud, "wind_speed") * 0.01)


def _check_state(p, hud, cells, label):
    flags, strength, speed = _want(p, hud)
    got = (_wpo(cells), _mpc(p, PARAM_STRENGTH), _mpc(p, PARAM_SPEED))
    p.check(label, got[0] == flags and abs(got[1] - strength) < 1e-4
            and abs(got[2] - speed) < 1e-4,
            f"cells {got[0]} want {flags}; Strength {got[1]:.3f} want {strength:.3f}; "
            f"Speed {got[2]:.3f} want {speed:.3f}")


def _run(p):
    yield lambda: (p.hud() is not None and p.get(p.hud(), PROFILE_CHECKED_VAR)
                   and _settled(p, p.hud()))
    hud = p.hud()
    cells = _cells(p)
    p.check("the level has grass, bush and tree cells", len(cells) > 10, str(len(cells)))
    preset = GS.PRESET_LABELS[p.get(hud, "Quality")]
    _check_state(p, hud, cells, f"the preset the game opened on ({preset}) is applied: "
                 "each cell's WPO and disable distance, MPC_Wind's Strength and Speed")

    p.set(hud, "MenuOpen", True)
    p.set(hud, TAB.open_var, True)
    if _cell(p, hud, "wind") < 1:
        yield from _nudge(p, hud, "wind", 1)
    yield from _nudge(p, hud, "wind", -1)
    p.check("wind off: the row reads 0", _cell(p, hud, "wind") == 0)
    _check_state(p, hud, cells, "...every cell stops evaluating WPO and Strength is 0")
    yield from _nudge(p, hud, "wind", 1)
    _check_state(p, hud, cells, "wind on again: every cell evaluates WPO, Strength is back")

    was = _cell(p, hud, "wind_distance")
    yield from _nudge(p, hud, "wind_distance", 1)
    p.check("wind distance up a step", _cell(p, hud, "wind_distance") == was
            + GS.GFX_STATS[GS.index_of("wind_distance")].step)
    _check_state(p, hud, cells, "...every cell's WPO disable distance follows (m x 100)")

    yield from _nudge(p, hud, "wind_strength", 1)
    yield from _nudge(p, hud, "wind_speed", 2)
    _check_state(p, hud, cells, "wind strength and speed up: MPC_Wind's scalars follow")
    values = list(p.get(hud, TAB.values_var))
    spread = {float(values[q * GS.STAT_COUNT + GS.index_of(c)])
              for q in range(len(GS.PRESET_LABELS)) for c in ("wind_strength",)}
    p.check("...and the strength is in every preset's row (a look number)",
            spread == {_cell(p, hud, "wind_strength")}, str(spread))
