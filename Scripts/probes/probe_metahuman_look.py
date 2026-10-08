"""Pictures of the MetaHuman player from in front: standing, walking,
sidestepping, with the axe and then down the rifle's sights.

Not a check: a way to SEE the MetaHuman wear the mannequin's animation,
which the game's own camera cannot show. probe_bound_look.py's eye (a
hidden wanderer carried in front of the player). Run windowed:

    python3 Scripts/dev/uepy.py --game --windowed --probe Scripts/probes/probe_metahuman_look.py

Each picture lands in Saved/Screenshots/MacEditor, and the log says which
numbers are which.
"""

import os

import unreal

from combat.game_state import DEBUG_MODE_VAR
from combat.paths import WEAPON_COMP_BP_PATH, WEAPON_COMP_CLASS_PATH
from combat.weapon_component import vars as WV
from net.state_consts import GAME_STATE_BP_PATH

WRITABLE = [(WEAPON_COMP_BP_PATH, WV.EquippedIndex), (GAME_STATE_BP_PATH, DEBUG_MODE_VAR)]
HOLD = (("empty hands", None), ("axe", "BP_Axe_C"), ("rifle", "BP_Rifle_C"))
# Far enough back that the legs are in the picture: a strafe is told by them.
EYE_AHEAD_CM, EYE_UP_CM, EYE_FOV = 420.0, 10.0, 50.0
LOOK_AT_UP_CM = 0.0
MOVES = (("standing", 0.0, 0.0), ("walking forward", 1.0, 0.0),
         ("sidestepping right", 0.0, 1.0))
REST_S, SETTLE_S = 0.8, 2.2
SHOTS_DIR = os.path.join(unreal.Paths.project_saved_dir(), "Screenshots", "MacEditor")


def _count():
    return len(os.listdir(SHOTS_DIR)) if os.path.isdir(SHOTS_DIR) else 0


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
    unreal.SystemLibrary.execute_console_command(world, "FOV 0", pc)
    pc.set_view_target_with_blend(player)
