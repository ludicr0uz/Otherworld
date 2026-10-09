"""Single player, entered as a player enters it: from the real title, through
its Single Player row and that page's New Game (or Continue Game).

    python3 Scripts/dev/uepy.py --game --title --probe Scripts/probes/probe_title_single.py

``--title`` leaves -nomenu off, so BeginPlay's own path runs: the game opens
on the title, paused, in a standalone world. (probe_main_menu.py holds a
title up by hand under -nomenu; this is the real one.)

  the title            GameStarted false, the world paused, the menu on its
                       own rows, no session
  Single Player        its page in the rows' place; nothing starts
  New Game             the game starts and plays as before: unpaused, the
                       menu shut and back on its rows, time running, the
                       player walking, the issued loadout in the bag
"""

SYSTEMS = ('title',)

import unreal

from graphics_menu import hud_vars as MV
from graphics_menu import mode_consts as MC
from graphics_menu import umg_consts as C
from graphics_menu.settings_rows import PAGE_TITLE
from net import session_consts as S
from probes import title as T

WRITABLE = list(T.WRITABLE)
WEAPON_COMP = "/Game/Weapons/BP_WeaponComponent.BP_WeaponComponent_C"
WALK_CM, WALK_S = 100.0, 8.0


def probe(p):
    yield from T.wait(lambda: T.on_title(p))
    if not T.on_title(p):
        p.check("the game opens on the title (run with uepy.py --game --title)", False,
                "no paused title: -nomenu is on the command line")
        return
    hud, gi = p.hud(), T.session(p)
    p.check("the game opens on the title: paused, standalone, the menu on its own "
            "rows, in no session",
            p.get(hud, MV.MenuPage) == PAGE_TITLE and str(p.get(gi, S.JoinAddress)) == ""
            and p.get(gi, S.Connecting) is False,
            f"page {p.get(hud, MV.MenuPage)}")

    yield from T.take_row(p, C.START_ACTION, lambda: p.get(hud, MV.MenuPage) == MC.PAGE_SINGLE)
    p.check("the Single Player row opens its page, and starts nothing",
            p.get(hud, MV.MenuPage) == MC.PAGE_SINGLE and T.on_title(p),
            f"page {p.get(hud, MV.MenuPage)}")

    yield from T.take_page_row(p, MC.SINGLE_START_ROW, lambda: T.in_play(p))
    p.check("its row starts the game: unpaused, the menu shut and back on its rows",
            T.in_play(p) and not T.paused(p) and p.get(hud, MV.MenuOpen) is False
            and p.get(hud, MV.MenuPage) == PAGE_TITLE,
            f"paused {T.paused(p)}, open {p.get(hud, MV.MenuOpen)}")
    p.check("...in this process, alone: the same HUD, a standalone world",
            p.hud() == hud and T.alone(p))

    # --- and it plays as before ------------------------------------------------
    t0 = unreal.GameplayStatics.get_time_seconds(p.world())
    me = p.pawn()
    start = me.get_actor_location()
    forward = me.get_actor_forward_vector()

    def walked():
        me.add_movement_input(forward, 1.0)
        return (me.get_actor_location() - start).length() >= WALK_CM
    yield from T.wait(walked, WALK_S)
    went = (me.get_actor_location() - start).length()
    ran = unreal.GameplayStatics.get_time_seconds(p.world()) - t0
    p.check("the game plays: time runs and the player walks",
            ran > 0.0 and went >= WALK_CM, f"{went:.0f} cm in {ran:.2f} game s")
    bag = list(p.get(p.component(me, WEAPON_COMP), "Inventory"))
    p.check("...with the issued loadout", len(bag) >= 6, f"{len(bag)} items")
