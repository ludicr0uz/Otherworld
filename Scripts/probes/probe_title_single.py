"""Single player, entered as a player enters it: from the real title, through
its Single Player row and that page's New Game (or Continue Game).

    python3 Scripts/dev/uepy.py --game --title --probe Scripts/probes/probe_title_single.py

``--title`` leaves -nomenu off, so BeginPlay's own path runs: the game opens
on the title level (Scripts/title), unpaused, in a standalone world.
(probe_main_menu.py holds a title up by hand under -nomenu; this is the real
one.)

  the title            GameStarted false, the title level, the menu on its
                       own rows, no session
  Single Player        its page in the rows' place; nothing starts
  New Game             the play level opens and plays: a new world and HUD in
                       play, unpaused, the menu shut, time running, the
                       player walking, the issued loadout in the bag
"""

SYSTEMS = ('title',)
LEVEL = "/Game/Maps/Lvl_Title"
# The forest's load is in it.
TIMEOUT = 150.0

import unreal

from graphics_menu import hud_vars as MV
from graphics_menu import mode_consts as MC
from graphics_menu import umg_consts as C
from graphics_menu.settings_rows import PAGE_TITLE
from net import session_consts as S
from probes import title as T
from title import paths as P

WRITABLE = list(T.WRITABLE)
WEAPON_COMP = "/Game/Weapons/BP_WeaponComponent.BP_WeaponComponent_C"
WALK_CM, WALK_S = 100.0, 8.0
LOAD_WAIT = 60.0
PLAY_LEVEL_NAME = P.PLAY_LEVEL.rsplit("/", 1)[1]
GS = unreal.GameplayStatics


def probe(p):
    yield from T.wait(lambda: T.on_title(p))
    if not T.on_title(p):
        p.check("the game opens on the title (run with uepy.py --game --title)", False,
                "no paused title: -nomenu is on the command line")
        return
    hud, gi = p.hud(), T.session(p)
    p.check("the game opens on the title level: standalone, the menu on its own "
            "rows, in no session",
            p.get(hud, MV.MenuPage) == PAGE_TITLE and str(p.get(gi, S.JoinAddress)) == ""
            and p.get(gi, S.Connecting) is False,
            f"page {p.get(hud, MV.MenuPage)}")

    yield from T.take_row(p, C.START_ACTION, lambda: p.get(hud, MV.MenuPage) == MC.PAGE_SINGLE)
    p.check("the Single Player row opens its page, and starts nothing",
            p.get(hud, MV.MenuPage) == MC.PAGE_SINGLE and T.on_title(p),
            f"page {p.get(hud, MV.MenuPage)}")

    # The probe's own world is the title's, by the run's map: the play level
    # is found by its own path once it is up.
    def play_world():
        return unreal.find_object(None, f"{P.PLAY_LEVEL}.{PLAY_LEVEL_NAME}")

    def play_hud():
        world = play_world()
        pc = GS.get_player_controller(world, 0) if world else None
        return pc.get_hud() if pc else None

    def playing():
        hud = play_hud()
        return bool(hud and GS.get_player_pawn(play_world(), 0)
                    and p.get(hud, C.GAME_STARTED_VAR))
    yield from T.take_page_row(p, MC.SINGLE_START_ROW, playing, LOAD_WAIT)
    world, hud = play_world(), play_hud()
    p.check(f"its row opens the play level, {PLAY_LEVEL_NAME}, in play: unpaused, the menu "
            f"shut, on its rows, the title's world gone",
            playing() and not GS.is_game_paused(world) and p.get(hud, MV.MenuOpen) is False
            and p.get(hud, MV.MenuPage) == PAGE_TITLE and p.world() is None,
            f"play level {world is not None}, open {hud and p.get(hud, MV.MenuOpen)}")
    if not playing():
        return
    p.check("...in this process, alone: a standalone world",
            unreal.SystemLibrary.is_standalone(world))

    # --- and it plays as before ------------------------------------------------
    t0 = GS.get_time_seconds(world)
    me = GS.get_player_pawn(world, 0)
    start = me.get_actor_location()
    forward = me.get_actor_forward_vector()

    def walked():
        me.add_movement_input(forward, 1.0)
        return (me.get_actor_location() - start).length() >= WALK_CM
    yield from T.wait(walked, WALK_S)
    went = (me.get_actor_location() - start).length()
    ran = GS.get_time_seconds(world) - t0
    p.check("the game plays: time runs and the player walks",
            ran > 0.0 and went >= WALK_CM, f"{went:.0f} cm in {ran:.2f} game s")
    bag = list(p.get(p.component(me, WEAPON_COMP), "Inventory"))
    p.check("...with the issued loadout", len(bag) >= 6, f"{len(bag)} items")
