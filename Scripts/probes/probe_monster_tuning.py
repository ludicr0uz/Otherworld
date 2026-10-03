"""Monster tuning: the M panel's monster tuning tab changes live wanderers at once, and
saves monster_tuning.csv.

The keys are raised by writing the HUD's MonTuneRow / MonTuneCreature /
MonTuneNudge / MonTuneSaveRequested (a probe has no keyboard); the keys
themselves are the verifier's. With the zombie row picked:

  - one nudge up on its aggro range lands on every live zombie controller's
    TuneSightRange, and no wendigo's;
  - damage per hit nudged down past zero stops at the minimum, 0;
  - a run speed nudge reaches a zombie's MaxWalkSpeed on its next pass;
  - a health nudge re-applies a zombie's MaxHealth (and fills it);
  - Left on the creature row wraps from the first creature to the last;
  - the save writes those numbers, and only those, into monster_tuning.csv;
  - the panel, drawn by hand, shows the creature and the value on the caret's row.

monster_tuning.csv is set aside first and put back.
"""

import shutil

import unreal

from combat.paths import HEALTH_CLASS_PATH
from graphics_menu import monster_tune_consts as MC
from graphics_menu.profile_consts import PROFILE_CHECKED_VAR
from graphics_menu.umg_consts import ROW_CARET, ROW_VALUE
from npc.monster_tuning import CSV_PATH, MONSTER_STATS, read_table, stock_run_speed
from npc.paths import AGGRO_VAR, APPLIED_HEALTH_VAR, RUN_SPEED_VAR
from graphics_menu import hud_vars as MV

HUD_BP_PATH = "/Game/UI/BP_GraphicsMenuHUD"
TAB = MC.MONSTER_TAB
WRITABLE = [(HUD_BP_PATH, v) for v in (TAB.open_var, TAB.row_var, TAB.pick_var,
                                       TAB.nudge_var, TAB.save_var, MV.MenuOpen)]
COLS = [s[0] for s in MONSTER_STATS]
STEP = {s[0]: s[3] for s in MONSTER_STATS}
VAR = {s[0]: s[1] for s in MONSTER_STATS}


def _live_hud(p):
    try:
        hud = p.hud()
    except Exception:
        return None
    return hud if hud is not None and p.get(hud, PROFILE_CHECKED_VAR) else None


def _controllers(p, key):
    ctrls = unreal.GameplayStatics.get_all_actors_of_class(p.world(), unreal.AIController)
    return [c for c in ctrls if c.get_class().get_name() == f"BP_ForestWandererAI_{key}_C"
            and c.get_controlled_pawn() is not None]


def probe(p):
    backup = CSV_PATH + ".probe-backup"
    shutil.copy2(CSV_PATH, backup)
    try:
        yield from _run(p)
    finally:
        shutil.move(backup, CSV_PATH)


def _nudge(p, hud, column, step, times=1):
    p.set(hud, TAB.row_var, 0 if column is None else 1 + COLS.index(column))
    for _ in range(times):
        p.set(hud, TAB.nudge_var, step)
        yield lambda: p.get(hud, TAB.nudge_var) == 0
    yield 0.1           # the next Tick's apply


def _run(p):
    yield lambda: _live_hud(p) is not None and _controllers(p, "Zombie")
    yield 1.0           # a few tree passes: health applied, patrol set up
    hud = _live_hud(p)
    creatures = [str(c) for c in p.get(hud, TAB.names_var)]
    zombies, wendigos = _controllers(p, "Zombie"), _controllers(p, "Wendigo")
    p.check("the table lists the creatures, and zombies and wendigos are live",
            creatures == list(MC.MON_CREATURES) and zombies and wendigos,
            f"{creatures}: {len(zombies)} zombies, {len(wendigos)} wendigos")
    z, w = zombies[0], wendigos[0]
    before = {c: float(p.get(z, VAR[c])) for c in COLS}
    wendigo_before = [float(p.get(w, VAR[c])) for c in COLS]

    p.set(hud, TAB.pick_var, 0)
    yield from _nudge(p, hud, "vision_range_cm", 1)
    want = before["vision_range_cm"] + STEP["vision_range_cm"]
    got = [float(p.get(c, VAR["vision_range_cm"])) for c in zombies]
    p.check("one nudge up raises every live zombie's aggro range by its step",
            all(abs(g - want) < 1e-3 for g in got), f"{before['vision_range_cm']} -> {got}")

    yield from _nudge(p, hud, "melee_damage", -1, times=15)
    p.check("damage per hit nudged down stops at its minimum, 0",
            float(p.get(z, VAR["melee_damage"])) == 0.0, str(p.get(z, VAR["melee_damage"])))
    p.check("the wendigos are untouched",
            [float(p.get(w, VAR[c])) for c in COLS] == wendigo_before)

    yield from _nudge(p, hud, "run_speed_cms", 1)
    fast = before["run_speed_cms"] + STEP["run_speed_cms"]
    move = z.get_controlled_pawn().get_editor_property("character_movement")

    def speed_wanted():
        walk = 1.0 if p.get(z, AGGRO_VAR) else float(p.get(z, VAR["patrol_speed_scale"]))
        return float(p.get(z, RUN_SPEED_VAR)) * fast / stock_run_speed("Zombie") * walk

    yield lambda: abs(move.get_editor_property("max_walk_speed") - speed_wanted()) < 0.5
    p.check("a run speed nudge reaches the zombie's MaxWalkSpeed on its next pass",
            abs(move.get_editor_property("max_walk_speed") - speed_wanted()) < 0.5,
            f"{move.get_editor_property('max_walk_speed'):.1f} vs {speed_wanted():.1f}")

    yield from _nudge(p, hud, "health", 1)
    health = p.component(z.get_controlled_pawn(), HEALTH_CLASS_PATH)
    more = before["health"] + STEP["health"]
    yield lambda: abs(float(p.get(z, APPLIED_HEALTH_VAR)) - more) < 1e-3
    p.check("a health nudge re-applies the zombie's MaxHealth, full",
            abs(p.get(health, "MaxHealth") - more) < 1e-3
            and abs(p.get(health, "Health") - more) < 1e-3,
            f"{p.get(health, 'Health')}/{p.get(health, 'MaxHealth')}")

    yield from _nudge(p, hud, None, -1)
    p.check("Left on the creature row wraps to the last creature",
            p.get(hud, TAB.pick_var) == len(creatures) - 1, str(p.get(hud, TAB.pick_var)))

    old = read_table()
    p.set(hud, TAB.save_var, True)
    yield lambda: not p.get(hud, TAB.save_var)
    new = read_table()
    p.check("the save succeeds (MonTuneSaved)", p.get(hud, TAB.saved_var))
    want_row = dict(old.get("Zombie", {}), vision_range_cm=want, melee_damage=0.0,
                    run_speed_cms=fast, health=more)
    p.check("the CSV holds the tuned zombie",
            all(abs(new.get("Zombie", {}).get(c, -1) - v) < 1e-6 for c, v in want_row.items()),
            str(new.get("Zombie")))
    p.check("...and the wendigo as it was", new.get("Wendigo") == old.get("Wendigo"))

    ui = p.get(hud, "UiPause")
    panel, rows = (ui.get_editor_property(n) for n in (TAB.panel, TAB.rows_box))
    p.set(hud, "MenuOpen", True)
    p.set(hud, TAB.open_var, True)
    p.set(hud, TAB.pick_var, 0)
    p.set(hud, TAB.row_var, 1 + COLS.index("vision_range_cm"))
    hud.call_method("ReceiveDrawHUD", (1920, 1080))
    shown = str(rows.get_child_at(0).get_editor_property(ROW_VALUE).get_text())
    row = rows.get_child_at(1 + COLS.index("vision_range_cm"))
    value = str(row.get_editor_property(ROW_VALUE).get_text())
    p.check("drawn, the panel shows the creature and its aggro range on the caret's row",
            "COLLAPSED" not in str(panel.get_visibility()).upper() and shown == "Zombie"
            and float(value) == want
            and row.get_editor_property(ROW_CARET).get_render_opacity() == 1.0,
            f"{panel.get_visibility()} {shown!r} {value!r}")
    p.set(hud, TAB.open_var, False)
    hud.call_method("ReceiveDrawHUD", (1920, 1080))
    p.check("shut, the panel is collapsed",
            "COLLAPSED" in str(panel.get_visibility()).upper(), str(panel.get_visibility()))
    p.set(hud, "MenuOpen", False)
