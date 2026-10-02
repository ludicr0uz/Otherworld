"""The MONSTER TUNING tab's "hunt:" and "fire:" rows change a live wendigo's
hunt at once (npc/monster_tuning.MONSTER_STATS, the TuneStalk* and TuneWard*
variables its Stalk and Ward steps read).

graphics_menu/monster_tune_checks.py and npc/verify_stalk.py read the graphs;
this tunes one in the game, as probe_monster_tuning.py does a zombie. The
keys are raised by writing the HUD's variables (a probe has no keyboard).
With the wendigo row picked:

  - a nudge on the hunt's speed lands on every live wendigo's TuneStalkSpeed,
    and on no zombie's;
  - the time it is held off by fire, nudged down, stops at its minimum;
  - a wendigo stood in sight of the player runs its leg at the tuned share of
    its run;
  - the charge range nudged out past where it stands, it charges from there:
    further off than the built range;
  - the save writes the wendigo's row, and leaves the zombie's as it was.

monster_tuning.csv is set aside first and put back.
"""

import shutil

import unreal

from graphics_menu import monster_tune_consts as MC
from npc.monster_tuning import (
    CSV_PATH, MONSTER_STATS, monster_specs, read_table, stock_run_speed,
)
from npc.paths import AGGRO_VAR, RUN_SPEED_VAR, STALK_CHARGING_VAR, STALK_LEGS_VAR
from probes.probe_monster_tuning import (
    COLS, STEP, TAB, VAR, _controllers, _live_hud, _nudge,
)
from probes.probe_wendigo_stalk import (
    START_CM, _about, _on_navmesh, _stand_in_sight, _walk_speed,
)

HUD_BP_PATH = "/Game/UI/BP_GraphicsMenuHUD"
WRITABLE = [(HUD_BP_PATH, v) for v in (TAB.open_var, TAB.row_var, TAB.pick_var,
                                       TAB.nudge_var, TAB.save_var, "MenuOpen")]
MINS = {s[0]: s[4] for s in MONSTER_STATS}
BEAT_S = 0.7            # the tree's 0.5 s beat, and a sample or two
WAIT_S = 12.0
MARGIN_CM = 300.0       # the charge range is put this far past the wendigo


def probe(p):
    backup = CSV_PATH + ".probe-backup"
    shutil.copy2(CSV_PATH, backup)
    try:
        yield from _run(p)
    finally:
        shutil.move(backup, CSV_PATH)


def _run(p):
    yield lambda: (_live_hud(p) is not None and _controllers(p, "Wendigo")
                   and _controllers(p, "Zombie"))
    yield 1.0
    hud = _live_hud(p)
    built = monster_specs("Wendigo")
    wendigos, zombies = _controllers(p, "Wendigo"), _controllers(p, "Zombie")
    ctrl = wendigos[0]
    held = {c: float(p.get(ctrl, VAR[c])) for c in COLS}
    zombie_before = [float(p.get(zombies[0], VAR[c])) for c in COLS]
    p.check("a live wendigo's Tune variables hold its built row",
            all(abs(held[c] - built[c]) < 1e-3 for c in COLS),
            str({c: held[c] for c in COLS if abs(held[c] - built[c]) >= 1e-3}))

    p.set(hud, TAB.pick_var, list(MC.MON_CREATURES).index("Wendigo"))
    yield from _nudge(p, hud, "stalk_run_scale", 1)
    share = built["stalk_run_scale"] + STEP["stalk_run_scale"]
    got = [float(p.get(c, VAR["stalk_run_scale"])) for c in wendigos]
    p.check("one nudge up raises every live wendigo's hunt speed by its step",
            all(abs(g - share) < 1e-3 for g in got), f"{built['stalk_run_scale']} -> {got}")
    yield from _nudge(p, hud, "ward_hold_s", -1,
                      times=int(built["ward_hold_s"] / STEP["ward_hold_s"]) + 5)
    p.check(f"the fire's hold nudged down stops at its minimum, {MINS['ward_hold_s']:g} s",
            float(p.get(ctrl, VAR["ward_hold_s"])) == MINS["ward_hold_s"],
            str(p.get(ctrl, VAR["ward_hold_s"])))
    p.check("the zombies are untouched",
            [float(p.get(zombies[0], VAR[c])) for c in COLS] == zombie_before)

    # --- the tuned speed reaches a leg ----------------------------------------
    npc, player = ctrl.get_controlled_pawn(), p.pawn()
    if _on_navmesh(p, player.get_actor_location()) is None:
        unreal.SystemLibrary.execute_console_command(
            p.world(), "RebuildNavigation", p.controller())
        p.note("no navmesh under the player: sent RebuildNavigation")
    yield lambda: _on_navmesh(p, player.get_actor_location()) is not None
    yaw = _stand_in_sight(p, ctrl, npc, player)
    p.check(f"a wendigo is stood {START_CM / 100:.0f} m off, where it can see the player",
            yaw is not None, f"bearing {yaw}")
    if yaw is None:
        return
    limit = p.time() + WAIT_S
    yield lambda: bool(p.get(ctrl, AGGRO_VAR)) or p.time() > limit
    limit = p.time() + WAIT_S
    yield lambda: int(p.get(ctrl, STALK_LEGS_VAR)) >= 1 or p.time() > limit
    yield BEAT_S
    want = (float(p.get(ctrl, RUN_SPEED_VAR)) * float(p.get(ctrl, VAR["run_speed_cms"]))
            / stock_run_speed("Wendigo") * share)
    p.check(f"it runs its leg at the tuned {share:.0%} of its run",
            int(p.get(ctrl, STALK_LEGS_VAR)) >= 1 and abs(_walk_speed(npc) - want) < 1.0,
            f"{_walk_speed(npc):.0f} cm/s, want {want:.0f}")

    # --- the charge range, put past where it stands ---------------------------
    gap = _about(npc.get_actor_location(), player.get_actor_location())[0]
    p.check("it is still hunting, outside the built charge range",
            not p.get(ctrl, STALK_CHARGING_VAR) and gap > built["stalk_charge_cm"] + 100.0,
            f"{gap:.0f} cm off, the range is {built['stalk_charge_cm']:.0f}")
    times = int((gap + MARGIN_CM - built["stalk_charge_cm"]) / STEP["stalk_charge_cm"]) + 1
    yield from _nudge(p, hud, "stalk_charge_cm", 1, times=times)
    tuned = float(p.get(ctrl, VAR["stalk_charge_cm"]))
    limit = p.time() + 3.0
    yield lambda: bool(p.get(ctrl, STALK_CHARGING_VAR)) or p.time() > limit
    gap = _about(npc.get_actor_location(), player.get_actor_location())[0]
    p.check(f"the charge range nudged out to {tuned:.0f} cm, it charges from there",
            abs(tuned - (built["stalk_charge_cm"] + times * STEP["stalk_charge_cm"])) < 1e-3
            and bool(p.get(ctrl, STALK_CHARGING_VAR))
            and gap > built["stalk_charge_cm"] + 100.0,
            f"charging {bool(p.get(ctrl, STALK_CHARGING_VAR))}, {gap:.0f} cm off")

    # --- the save -------------------------------------------------------------
    old = read_table()
    p.set(hud, TAB.save_var, True)
    yield lambda: not p.get(hud, TAB.save_var)
    new = read_table()
    want_row = dict(old.get("Wendigo", {}), stalk_run_scale=share,
                    ward_hold_s=MINS["ward_hold_s"], stalk_charge_cm=tuned)
    p.check("the save writes the tuned wendigo into monster_tuning.csv",
            bool(p.get(hud, TAB.saved_var))
            and all(abs(new.get("Wendigo", {}).get(c, -1) - v) < 1e-6
                    for c, v in want_row.items()), str(new.get("Wendigo")))
    p.check("...and the zombie as it was", new.get("Zombie") == old.get("Zombie"))
