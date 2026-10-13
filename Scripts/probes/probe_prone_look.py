"""Pictures of the player lying down: still and crawling forward, with empty
hands and with the rifle, from the side and from in front.

A way to SEE the prone (P1: the Free Animation Library's idle and forward
crawl, combat/stance_clips.py) on the drawn MetaHuman, which the game's own
camera shows only from behind; probe_stance_clips.py holds the numbers. Its
one check is that the pictures were taken. Its eye is a scene capture carried
beside the player (lying down, the player's camera kept the view from
probe_metahuman_look.py's wanderer). Run windowed:

    python3 Scripts/dev/uepy.py --game --windowed --probe Scripts/probes/probe_prone_look.py

Each picture lands in Saved/Screenshots/MacEditor as prone_<what>.png.
"""

LEVEL = "/Game/Maps/Lvl_Forest_200m"  # trees and light to see the body against
SYSTEMS = ('animation',)

import os

import unreal

from combat.game_state import DEBUG_MODE_VAR
from combat.paths import WEAPON_COMP_BP_PATH, WEAPON_COMP_CLASS_PATH
from combat.slot_tuning import HAND, PRIMARY
from combat.weapon_component import vars as WV
from graphics_menu.dev_consts import DEV_GUNS_REQUEST_VAR
from net.state_consts import GAME_STATE_BP_PATH

HUD_BP_PATH = "/Game/UI/BP_GraphicsMenuHUD"
WRITABLE = [(WEAPON_COMP_BP_PATH, WV.Stance), (WEAPON_COMP_BP_PATH, WV.EquippedIndex),
            (GAME_STATE_BP_PATH, DEBUG_MODE_VAR), (HUD_BP_PATH, DEV_GUNS_REQUEST_VAR)]
RIFLE = "BP_AssaultRifle_C"
EYE_FOV = 50.0
# (name, cm ahead of the player, cm to its right, cm up).
VIEWS = (("from the right", 40.0, 300.0, 50.0), ("from in front", 300.0, 90.0, 70.0))
LOOK_AT_UP_CM = -30.0
SHOTS_DIR = os.path.join(unreal.Paths.project_saved_dir(), "Screenshots", "MacEditor")


def probe(p):
    yield 0.5
    player = p.pawn()
    wc = p.component(player, WEAPON_COMP_CLASS_PATH)
    world = p.world()
    os.makedirs(SHOTS_DIR, exist_ok=True)
    p.set(p.game_state(), DEBUG_MODE_VAR, False)
    target = unreal.RenderingLibrary.create_render_target2d(
        world, 1280, 720, unreal.TextureRenderTargetFormat.RTF_RGBA8)
    eye = unreal.OtherworldLoadLibrary.spawn_actor_at(
        world, unreal.SceneCapture2D, unreal.Transform())
    cap = eye.capture_component2d
    cap.set_editor_property("texture_target", target)
    cap.set_editor_property("capture_source", unreal.SceneCaptureSource.SCS_FINAL_COLOR_LDR)
    cap.set_editor_property("fov_angle", EYE_FOV)
    # Every frame and with its state kept, so the exposure settles as the game's does.
    cap.set_editor_property("capture_every_frame", True)
    cap.set_editor_property("always_persist_rendering_state", True)
    eye.root_component.set_mobility(unreal.ComponentMobility.MOVABLE)
    taken = []

    def moving(fwd, seconds, view):
        _name, ahead_cm, side_cm, up_cm = view
        t0 = unreal.GameplayStatics.get_time_seconds(world)

        def step():
            if fwd:
                player.add_movement_input(player.get_actor_forward_vector(), fwd)
            here = player.get_actor_location()
            at = (here + player.get_actor_forward_vector() * ahead_cm
                  + player.get_actor_right_vector() * side_cm
                  + unreal.Vector(0.0, 0.0, up_cm))
            eye.set_actor_location_and_rotation(
                at, unreal.MathLibrary.find_look_at_rotation(
                    at, here + unreal.Vector(0.0, 0.0, LOOK_AT_UP_CM)), False, True)
            return unreal.GameplayStatics.get_time_seconds(world) - t0 >= seconds
        return step

    def shot(label):
        name = "prone_" + "_".join(label.replace(",", "").replace(".", "").split()) + ".png"
        unreal.RenderingLibrary.export_render_target(world, target, SHOTS_DIR, name)
        taken.append(name)
        p.note(f"{label}: speed {player.get_velocity().length():.0f}, {name}")

    # The issued shotgun starts in hand: onto its slot, as a drag puts it
    # (before the dev guns fill the weapon slots: a filled one would swap).
    p.ask_move(wc, HAND, PRIMARY)
    yield lambda: p.get(wc, "Held") is None
    p.set(p.hud(), DEV_GUNS_REQUEST_VAR, True)
    yield lambda: not p.get(p.hud(), DEV_GUNS_REQUEST_VAR)
    p.set(wc, "Stance", 2)
    for label, cls in (("empty hands", None), ("rifle", RIFLE)):
        if cls:
            bag = [i.get_class().get_name() for i in p.get(wc, "Inventory")]
            if cls not in bag:
                p.note(f"no {cls} in the bag: {bag}")
                continue
            p.hold(wc, bag.index(cls))
        for view in VIEWS:
            yield moving(0.0, 1.5, view)
            shot(f"{label}, lying still, {view[0]}")
            yield moving(0.0, 0.3, view)
            yield moving(1.0, 1.6, view)
            shot(f"{label}, crawling forward, {view[0]}")
            yield moving(1.0, 0.4, view)
            shot(f"{label}, crawling forward, {view[0]}, 0.4 s on")
            yield moving(1.0, 0.2, view)
    yield moving(0.0, 0.5, VIEWS[0])
    p.set(wc, "Stance", 0)
    eye.destroy_actor()
    there = [n for n in taken if os.path.isfile(os.path.join(SHOTS_DIR, n))]
    p.check("twelve pictures of the prone were taken", len(there) == 12, f"{len(there)}")
