"""Horde Mode, entered as a player enters it: from the real title, through
its Single Player row and that page's second row.

    python3 Scripts/dev/uepy.py --game --title --probe Scripts/probes/probe_title_horde.py

``--title`` leaves -nomenu off, so BeginPlay's own path runs
(probe_title_single.py is the Survival row's half).

  the title            the menu on its own rows, no session
  Single Player        its page: Survival (or Continue Survival) over Horde
                       Mode; nothing starts
  Horde Mode           the horde level opens and plays, not the 1 km forest:
                       a new world and HUD in play, unpaused, the menu shut,
                       the player walking, the issued loadout in the bag
"""

SYSTEMS = ('title',)
LEVEL = "/Game/Maps/Lvl_Title"
# The horde level's load is in it.
TIMEOUT = 150.0

import unreal

from graphics_menu import hud_vars as MV
from graphics_menu import mode_consts as MC
from graphics_menu import umg_consts as C
from graphics_menu.settings_rows import PAGE_TITLE
from probes import title as T
from title import paths as P

WRITABLE = list(T.WRITABLE)
WEAPON_COMP = "/Game/Weapons/BP_WeaponComponent.BP_WeaponComponent_C"
WALK_CM, WALK_S = 100.0, 8.0
LOAD_WAIT = 60.0
HORDE_NAME = P.HORDE_LEVEL.rsplit("/", 1)[1]
PLAY_NAME = P.PLAY_LEVEL.rsplit("/", 1)[1]
GS = unreal.GameplayStatics


def probe(p):
    yield from T.wait(lambda: T.on_title(p))
    if not T.on_title(p):
        p.check("the game opens on the title (run with uepy.py --game --title)", False,
                "no title: -nomenu is on the command line")
        return
    hud = p.hud()
    yield from T.take_row(p, C.START_ACTION, lambda: p.get(hud, MV.MenuPage) == MC.PAGE_SINGLE)
    p.check("the Single Player row opens its page, and starts nothing",
            p.get(hud, MV.MenuPage) == MC.PAGE_SINGLE and T.on_title(p),
            f"page {p.get(hud, MV.MenuPage)}")
    yield from T.wait(lambda: T.row_text(p, MC.SINGLE.rows_box, MC.SINGLE_START_ROW)
                      in (C.START_ROW_LABEL, C.CONTINUE_ROW_LABEL), 2.0)
    first = T.row_text(p, MC.SINGLE.rows_box, MC.SINGLE_START_ROW)
    second = T.row_text(p, MC.SINGLE.rows_box, MC.SINGLE_HORDE_ROW)
    p.check(f"its rows read {C.START_ROW_LABEL} (or {C.CONTINUE_ROW_LABEL}) over "
            f"{C.HORDE_ROW_LABEL}",
            first in (C.START_ROW_LABEL, C.CONTINUE_ROW_LABEL) and second == C.HORDE_ROW_LABEL,
            f"'{first}', '{second}'")

    def world_of(level, name):
        return unreal.find_object(None, f"{level}.{name}")

    def horde_hud():
        world = world_of(P.HORDE_LEVEL, HORDE_NAME)
        pc = GS.get_player_controller(world, 0) if world else None
        return pc.get_hud() if pc else None

    def playing():
        hud = horde_hud()
        return bool(hud and GS.get_player_pawn(world_of(P.HORDE_LEVEL, HORDE_NAME), 0)
                    and p.get(hud, C.GAME_STARTED_VAR))
    yield from T.take_page_row(p, MC.SINGLE_HORDE_ROW, playing, LOAD_WAIT)
    world, hud = world_of(P.HORDE_LEVEL, HORDE_NAME), horde_hud()
    p.check(f"Horde Mode opens {HORDE_NAME}, in play: unpaused, the menu shut, on its "
            f"rows, the title's world gone",
            playing() and not GS.is_game_paused(world) and p.get(hud, MV.MenuOpen) is False
            and p.get(hud, MV.MenuPage) == PAGE_TITLE and p.world() is None,
            f"horde level {world is not None}, open {hud and p.get(hud, MV.MenuOpen)}")
    if not playing():
        return
    p.check(f"...not the Survival forest ({PLAY_NAME}), in this process alone",
            world_of(P.PLAY_LEVEL, PLAY_NAME) is None
            and unreal.SystemLibrary.is_standalone(world))

    me = GS.get_player_pawn(world, 0)
    start = me.get_actor_location()
    forward = me.get_actor_forward_vector()

    def walked():
        me.add_movement_input(forward, 1.0)
        return (me.get_actor_location() - start).length() >= WALK_CM
    yield from T.wait(walked, WALK_S)
    went = (me.get_actor_location() - start).length()
    p.check("the game plays: the player walks", went >= WALK_CM, f"{went:.0f} cm")
    bag = list(p.get(p.component(me, WEAPON_COMP), "Inventory"))
    p.check("...with the issued loadout", len(bag) >= 6, f"{len(bag)} items")
