"""The title is a stage of its own, with the character on it in the saved
gear, and no forest loaded until New Game.

    python3 Scripts/dev/uepy.py --game --title --probe Scripts/probes/probe_title_figure.py

``--title`` leaves -nomenu off, so BeginPlay's own path runs on the title
level (Scripts/title; GameDefaultMap).

  the title level     the game opens on Lvl_Title: the menu held open, the
                      world standalone, not paused (nothing on the stage to
                      pause), time running; the view is the stage's camera
  the figure          the player's character, on the stage in front of it,
                      with the MetaHuman body; with no profile, bare: the
                      three drawable parts (Torso, Legs, Feet) show nothing;
                      and it holds nothing: the issued gun is stowed
  the saved gear      a profile wearing the jacket, the pants and the boots
                      written and the title reopened: the figure stands in
                      them (the hoodie, the jeans, the shoes drawn on it)
  New Game            opens the play level: the forest comes up in play, the
                      title's level gone

The profile on disk is set aside first and put back at the end.
"""

SYSTEMS = ('title', 'clothing', 'menu')
LEVEL = "/Game/Maps/Lvl_Title"

import os
import shutil

import unreal

from graphics_menu import mode_consts as MC
from graphics_menu import umg_consts as C
from graphics_menu.profile_consts import (
    PROFILE_BP_PATH, PROFILE_CLASS_PATH, PROFILE_SLOT, PROFILE_USER_INDEX, WORN_CLASSES_FIELD)
from graphics_menu.title_figure import TITLE_DRESSED_VAR
from probes import title as T
from probes.dressed import drawn, part
from combat.paths import WEAPON_COMP_CLASS_PATH
from combat.weapon_component import vars as WV
from clothing.specs import GARMENTS
from title import paths as P

WRITABLE = list(T.WRITABLE) + [(PROFILE_BP_PATH, WORN_CLASSES_FIELD)]
WORN = ("Jacket", "Pants", "Boots")
NEAR_CM = 150.0
PLAY_LEVEL_NAME = P.PLAY_LEVEL.rsplit("/", 1)[1]
LOAD_WAIT = 60.0
# The forest's load is in it: the run's default would cut the wait short.
TIMEOUT = 150.0
GS = unreal.GameplayStatics


def _file():
    return os.path.join(unreal.Paths.project_saved_dir(), "SaveGames", f"{PROFILE_SLOT}.sav")


def _spec(display):
    return next(g for g in GARMENTS if g.display == display)


def _dressed(p):
    try:
        return T.on_title(p) and bool(p.get(p.hud(), TITLE_DRESSED_VAR))
    except Exception:           # a world mid-travel
        return False


def _wc(p):
    return p.component(p.pawn(), WEAPON_COMP_CLASS_PATH)


def _empty_handed(p):
    try:
        return p.get(_wc(p), WV.Held) is None
    except Exception:           # a world mid-travel
        return False


def _write_profile(p):
    """A profile wearing WORN, nothing else in it."""
    prof = GS.create_save_game_object(p.load_class(PROFILE_CLASS_PATH))
    last = max(_spec(d).slot_index for d in WORN)
    worn = [None] * (last + 1)
    for d in WORN:
        worn[_spec(d).slot_index] = p.load_class(_spec(d).class_path)
    p.set(prof, WORN_CLASSES_FIELD, worn)
    if not GS.save_game_to_slot(prof, PROFILE_SLOT, PROFILE_USER_INDEX):
        raise RuntimeError("the profile would not save")


def _reopen(p):
    """The title level opened again: a new world and a new HUD."""
    old = p.world()
    GS.open_level(old, P.TITLE_LEVEL, True, "")
    yield from T.wait(lambda: p.world() is not None and p.world() != old and _dressed(p), 30.0)


def probe(p):
    backup = _file() + ".probe-backup"
    if os.path.exists(_file()):
        shutil.move(_file(), backup)
    try:
        yield from _run(p)
    finally:
        if os.path.exists(_file()):
            os.remove(_file())
        if os.path.exists(backup):
            shutil.move(backup, _file())


def _run(p):
    yield from T.wait(lambda: T.on_title(p))
    if not T.on_title(p):
        p.check("the game opens on the title level (run with uepy.py --game --title)", False,
                f"level {T.level_name(p) if p.world() else None}")
        return
    hud = p.hud()
    t0 = unreal.GameplayStatics.get_time_seconds(p.world())
    yield from T.wait(lambda: False, 0.5)
    ran = unreal.GameplayStatics.get_time_seconds(p.world()) - t0
    p.check(f"the game opens on {P.TITLE_LEVEL_NAME}: the menu held open, standalone, "
            f"in no session, and not paused -- time runs on the stage",
            T.alone(p) and not T.paused(p) and ran > 0.0
            and p.get(hud, C.GAME_STARTED_VAR) is False,
            f"paused {T.paused(p)}, {ran:.2f} game s in 0.5 wall s")

    view = p.controller().get_view_target()
    at = view.get_actor_location() if view else None
    p.check("the title is seen through the stage's camera (a CameraActor, where the "
            "builder put it), not the character's own",
            isinstance(view, unreal.CameraActor) and at is not None
            and (at - unreal.Vector(*P.CAMERA)).length() < 1.0,
            f"{type(view).__name__} at {at}")

    me = p.pawn()
    here = me.get_actor_location()
    start = unreal.Vector(*P.PLAYER_START)
    flat = unreal.Vector(here.x - start.x, here.y - start.y, 0.0).length()
    p.check("the figure is the player's character, standing on the stage in front "
            "of the camera, with the MetaHuman body under it",
            flat < NEAR_CM and here.z > P.FLOOR_Z and part(me, "Jacket") is not None,
            f"{flat:.0f} cm from the start, z {here.z:.0f}")

    yield from T.wait(lambda: _dressed(p))
    bare = [d for d in WORN if not drawn(part(me, d), d)]
    p.check("with no profile saved, the figure is the basic character: nothing drawn "
            "on its torso, legs or feet",
            bool(p.get(hud, TITLE_DRESSED_VAR)) and sorted(bare) == sorted(WORN),
            f"dressed {p.get(hud, TITLE_DRESSED_VAR)}, bare {bare}")
    yield from T.wait(lambda: _empty_handed(p), 5.0)
    p.check("...and holds nothing: the issued gun is stowed in its slot (Held is None, "
            "the loadout still carried)",
            _empty_handed(p) and len(p.get(_wc(p), WV.Inventory)) > 0,
            f"held {p.get(_wc(p), WV.Held)}")

    # --- the saved gear ---------------------------------------------------
    _write_profile(p)
    yield from _reopen(p)
    if not _dressed(p):
        p.check("the title reopened with the profile written", False,
                f"on title {T.on_title(p) if p.world() else None}")
        return
    me = p.pawn()
    worn = [d for d in WORN if drawn(part(me, d), d)]
    p.check("with a profile wearing the jacket, the pants and the boots, the figure "
            "stands in them: the hoodie, the jeans and the shoes drawn on the body",
            sorted(worn) == sorted(WORN), f"drawn {worn}")
    yield from T.wait(lambda: _empty_handed(p), 5.0)
    p.check("...holding nothing, dressed as well as bare", _empty_handed(p),
            f"held {p.get(_wc(p), WV.Held)}")
    p.check("...and the game is still not loaded: the title level, not started",
            T.on_title(p), T.level_name(p))

    # --- New Game ----------------------------------------------------------
    os.remove(_file())
    hud = p.hud()
    yield from T.take_row(p, C.START_ACTION, lambda: p.get(hud, "MenuPage") == MC.PAGE_SINGLE)
    p.check("the Single Player row opens its page, and loads nothing",
            p.get(hud, "MenuPage") == MC.PAGE_SINGLE and T.on_title(p),
            f"page {p.get(hud, 'MenuPage')}")

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
    hud = play_hud()
    p.check(f"New Game opens the play level: {PLAY_LEVEL_NAME} comes up in play, "
            f"the menu shut, the title's level gone",
            playing() and not GS.is_game_paused(play_world())
            and p.get(hud, "MenuOpen") is False and p.world() is None,
            f"play level {play_world() is not None}, started "
            f"{p.get(hud, C.GAME_STARTED_VAR) if hud else None}, title world {p.world()}")
