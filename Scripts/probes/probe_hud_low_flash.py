"""A stat bar's group blinks while the bar is low, and only then.

HP and FOOD are set low, the probe calls ReceiveDrawHUD itself over a second
and a half of wall clock (the blink runs on real time; -nullrhi never draws),
and reads each group's render opacity back, one draw a frame. Then both are refilled and the
blink has to stop at full opacity.

    python3 Scripts/dev/uepy.py --game --probe Scripts/probes/probe_hud_low_flash.py
"""

import time

from combat.paths import HEALTH_BP_PATH, HEALTH_CLASS_PATH
from graphics_menu import umg_consts as C
from survival.paths import SURVIVAL_BP_PATH, SURVIVAL_CLASS_PATH
from combat import health_vars as HV
from survival import component_vars as UV

WRITABLE = [(HEALTH_BP_PATH, HV.Health), (SURVIVAL_BP_PATH, UV.Hunger)]


def _sample(hud, ui, groups, seconds, seen):
    """Fill ``seen`` ({group: opacities}) over ``seconds`` of wall clock, one
    draw a frame: GetRealTimeSeconds only moves between frames, so drawing
    in a loop inside one frame would see a single phase of the blink."""
    end = time.time() + seconds
    while time.time() < end:
        hud.call_method("ReceiveDrawHUD", (1920, 1080))
        for g in groups:
            seen[g].add(round(ui.get_editor_property(g).get_render_opacity(), 3))
        step = time.time() + 0.05
        yield lambda: time.time() > step


def probe(p):
    yield lambda: p.hud() is not None and p.get(p.hud(), "UiHud") is not None
    yield 0.3
    hud, pawn = p.hud(), p.pawn()
    ui = p.get(hud, "UiHud")
    health = p.component(pawn, HEALTH_CLASS_PATH)
    survival = p.component(pawn, SURVIVAL_CLASS_PATH)
    hunger, thirst = C.stat_group("Hunger"), C.stat_group("Thirst")
    groups = (C.HP_GROUP, hunger, thirst)

    p.set(health, "Health", 0.1 * p.get(health, "MaxHealth"))
    p.set(survival, "Hunger", 0.1 * p.get(survival, "MaxHunger"))
    seen = {g: set() for g in groups}
    yield from _sample(hud, ui, groups, 1.5, seen)
    dim, full = round(C.FLASH_DIM, 3), 1.0
    p.check("HP at 10% blinks between full and dim",
            seen[C.HP_GROUP] == {full, dim}, str(sorted(seen[C.HP_GROUP])))
    p.check("hunger at 10% blinks between full and dim",
            seen[hunger] == {full, dim}, str(sorted(seen[hunger])))
    t = p.get(survival, "Thirst") / p.get(survival, "MaxThirst")
    p.check(f"thirst at {t:.0%} stays steady at full", seen[thirst] == {full},
            str(sorted(seen[thirst])))

    p.set(health, "Health", p.get(health, "MaxHealth"))
    p.set(survival, "Hunger", p.get(survival, "MaxHunger"))
    seen = {g: set() for g in groups}
    yield from _sample(hud, ui, groups, 1.0, seen)
    p.check("refilled, HP and hunger stop blinking at full opacity",
            seen[C.HP_GROUP] == {full} and seen[hunger] == {full},
            f"HP {sorted(seen[C.HP_GROUP])}, FOOD {sorted(seen[hunger])}")
