"""Pictures of the MetaHuman player from in front: standing, walking,
sidestepping, with the axe (held, and in the middle of its swing), with the
rifle carried and then down its sights (from in front, from the side, and the
player's own sight picture).

A way to SEE the MetaHuman wear the mannequin's animation, which the game's
own camera cannot show; its only checks are the axe's: that what holds it and
what swings it are Mixamo's clips (combat/melee_clips.py), moving ones, and
not the keyed poses they replaced. probe_bound_look.py's eye (a
hidden wanderer carried in front of the player). Run windowed:

    python3 Scripts/dev/uepy.py --game --windowed --probe Scripts/probes/probe_metahuman_look.py

Each picture lands in Saved/Screenshots/MacEditor, and the log says which
numbers are which.
"""

SYSTEMS = ('animation',)

import os

import unreal

from combat.anim_blueprint import AIM_SLOT
from combat.game_state import DEBUG_MODE_VAR
from combat.paths import (
    AXE_ANIM_PATH, HOLD_AXE_ANIM_PATH, WEAPON_COMP_BP_PATH, WEAPON_COMP_CLASS_PATH,
)
from combat.skin import skin_of_mesh
from combat.tuning import COMBAT
from combat.weapon_component.knife import AXE_ANIM_VAR, KNIFE_QUEUED_VAR
from combat.seat_tuning import SEAT_VAR, SIGHTS_FORCED_VAR
from combat.weapon_component import vars as WV
from graphics_menu.dev_consts import DEV_GUNS_REQUEST_VAR
from net.state_consts import GAME_STATE_BP_PATH

HUD_BP_PATH = "/Game/UI/BP_GraphicsMenuHUD"
WRITABLE = [(WEAPON_COMP_BP_PATH, WV.EquippedIndex), (GAME_STATE_BP_PATH, DEBUG_MODE_VAR),
            (WEAPON_COMP_BP_PATH, SIGHTS_FORCED_VAR), (HUD_BP_PATH, DEV_GUNS_REQUEST_VAR),
            (WEAPON_COMP_BP_PATH, KNIFE_QUEUED_VAR)]
AXE = "BP_Axe_C"
# A clip, not a pose: over its length the right hand goes further than this.
CLIP_MOVES_CM = 5.0
# The rifle is a drop: the dev-all-guns request puts one in the bag.
RIFLE = "BP_AssaultRifle_C"
HOLD = (("empty hands", None), ("axe", "BP_Axe_C"), ("rifle", RIFLE))
# Far enough back that the legs are in the picture: a strafe is told by them.
EYE_AHEAD_CM, EYE_UP_CM, EYE_FOV = 420.0, 10.0, 50.0
LOOK_AT_UP_CM = 0.0
MOVES = (("standing", 0.0, 0.0), ("walking forward", 1.0, 0.0),
         ("sidestepping right", 0.0, 1.0))
REST_S, SETTLE_S = 0.8, 2.2
SHOTS_DIR = os.path.join(unreal.Paths.project_saved_dir(), "Screenshots", "MacEditor")


def _count():
    return len(os.listdir(SHOTS_DIR)) if os.path.isdir(SHOTS_DIR) else 0


def _hand_travel(clip, bone):
    """How far ``bone`` gets from where it starts, over ``clip`` (cm)."""
    def at(t):
        pose = unreal.AnimPoseExtensions.get_anim_pose_at_time(
            clip, t, unreal.AnimPoseEvaluationOptions())
        return unreal.AnimPoseExtensions.get_bone_pose(
            pose, bone, unreal.AnimPoseSpaces.WORLD).translation
    n = 20
    return max((at(i * clip.get_play_length() / n) - at(0.0)).length() for i in range(n + 1))


def _axe_clips(p, player, wc, moving, shot):
    """The axe in hand: it is held in Mixamo's idle and swung in Mixamo's
    chop, and a picture is taken as the blow lands."""
    mesh = player.get_editor_property("mesh")
    anim = mesh.get_anim_instance()
    skin = skin_of_mesh(mesh.get_editor_property("skeletal_mesh_asset").get_path_name())
    hand = skin.pose_bones["hand_r"] if skin else "hand_r"
    ready = p.get(p.get(wc, "Held"), "AimPose")
    p.check("the axe is held in A_HoldAxe, playing in the slot",
            ready is not None and ready.get_path_name().split(".")[0] == HOLD_AXE_ANIM_PATH
            and anim.is_playing_slot_animation(ready, AIM_SLOT), str(ready))
    if ready is not None:
        travel = _hand_travel(ready, hand)
        p.check("...a clip, not a pose: Mixamo's idle moves the hand",
                travel > CLIP_MOVES_CM and ready.get_play_length() > 1.0,
                f"{travel:.1f} cm over {ready.get_play_length():.2f} s")
    p.set(wc, KNIFE_QUEUED_VAR, True)
    yield lambda: not p.get(wc, KNIFE_QUEUED_VAR)
    swing = p.get(wc, AXE_ANIM_VAR)
    p.check("its swing is A_AxeSwing, playing in the slot",
            swing is not None and swing.get_path_name().split(".")[0] == AXE_ANIM_PATH
            and anim.is_playing_slot_animation(swing, AIM_SLOT),
            str(anim.get_current_active_montage()))
    if swing is not None:
        travel = _hand_travel(swing, hand)
        p.check("...a clip, not three keyed turns: Mixamo's chop carries the hand "
                "from overhead to the waist",
                travel > 60.0, f"{travel:.0f} cm")
    yield moving(0.0, 0.0, COMBAT.knife_impact_s)
    shot("axe, as the swing's blow lands")
    yield moving(0.0, 0.0, 0.6, side=250.0)
    p.set(wc, KNIFE_QUEUED_VAR, True)
    yield lambda: not p.get(wc, KNIFE_QUEUED_VAR)
    yield moving(0.0, 0.0, COMBAT.knife_impact_s, side=250.0)
    shot("axe, as the swing's blow lands, from the right")
    yield moving(0.0, 0.0, 1.0)


def probe(p):
    yield 0.5
    player, pc = p.pawn(), p.controller()
    wc = p.component(player, WEAPON_COMP_CLASS_PATH)
    world = p.world()
    ctrls = unreal.GameplayStatics.get_all_actors_of_class(world, unreal.AIController)
    eye = next((c.get_controlled_pawn() for c in ctrls
                if c.get_controlled_pawn() is not None), None)
    if eye is None:
        p.note("no wanderer to look through")
        return
    # Debug mode (a saved setting) draws each wanderer's sight cone, and the
    # eye's own starts at the camera: off for the pictures.
    p.set(p.game_state(), DEBUG_MODE_VAR, False)
    eye.set_actor_hidden_in_game(True)
    eye.set_actor_enable_collision(False)
    pc.set_view_target_with_blend(eye)
    unreal.SystemLibrary.execute_console_command(world, f"FOV {EYE_FOV:g}", pc)

    def watch(side=0.0):
        here, ahead = player.get_actor_location(), player.get_actor_forward_vector()
        right = player.get_actor_right_vector()
        eye.set_actor_location_and_rotation(
            here + ahead * EYE_AHEAD_CM + right * side + unreal.Vector(0.0, 0.0, EYE_UP_CM),
            unreal.MathLibrary.find_look_at_rotation(
                eye.get_actor_location(), here + unreal.Vector(0.0, 0.0, LOOK_AT_UP_CM)),
            False, True)

    def moving(fwd, right, seconds, side=0.0):
        t0 = unreal.GameplayStatics.get_time_seconds(world)

        def step():
            if fwd:
                player.add_movement_input(player.get_actor_forward_vector(), fwd)
            if right:
                player.add_movement_input(player.get_actor_right_vector(), right)
            watch(side)
            return unreal.GameplayStatics.get_time_seconds(world) - t0 >= seconds
        return step

    def shot(label):
        unreal.SystemLibrary.execute_console_command(world, "shot")
        p.note(f"{label}: speed {player.get_velocity().length():.0f}, shot #{_count()}")

    p.set(p.hud(), DEV_GUNS_REQUEST_VAR, True)
    yield lambda: not p.get(p.hud(), DEV_GUNS_REQUEST_VAR)
    for label, cls in HOLD:
        bag = [i.get_class().get_name() for i in p.get(wc, "Inventory")]
        if cls:
            if cls not in bag:
                p.note(f"no {cls} in the bag: {bag}")
                continue
            p.hold(wc, bag.index(cls))
        yield moving(0.0, 0.0, 1.0)
        for name, fwd, right in MOVES:
            # From standing, and long enough to be past the start: motion
            # matching plays a start or a pivot first, and the picture is of
            # the move itself.
            yield moving(0.0, 0.0, REST_S)
            yield moving(fwd, right, SETTLE_S)
            shot(f"{label}, {name}")
            yield moving(fwd, right, 0.33)
            shot(f"{label}, {name}, a third of a second on")
        # Once from the side, standing.
        yield moving(0.0, 0.0, 0.6, side=250.0)
        shot(f"{label}, standing, from the right")
        if cls == AXE:
            yield from _axe_clips(p, player, wc, moving, shot)
    # Down the rifle's sights (the sights key's stand-in, held): from in front,
    # from the side, and then the player's own view, the sight picture.
    if p.get(wc, "Held") is not None and p.get(wc, "Held").get_class().get_name() == RIFLE:
        p.set(wc, SIGHTS_FORCED_VAR, True)
        yield lambda: p.get(wc, SEAT_VAR) > 0.99
        yield moving(0.0, 0.0, 0.6)
        shot("rifle, down the sights")
        yield moving(0.0, 0.0, 0.6, side=250.0)
        shot("rifle, down the sights, from the right")
        unreal.SystemLibrary.execute_console_command(world, "FOV 0", pc)
        pc.set_view_target_with_blend(player)
        yield 0.6
        shot("rifle, down the sights: the player's own view")
        yield 0.3
        p.set(wc, SIGHTS_FORCED_VAR, False)
    unreal.SystemLibrary.execute_console_command(world, "FOV 0", pc)
    pc.set_view_target_with_blend(player)
