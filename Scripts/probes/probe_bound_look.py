"""Pictures of the player moving with something in hand, from in front.

Not a check: a way to SEE the worn body walk and sidestep, which the game's
own camera cannot show (it sits behind the player and turns the body with
it). Run windowed:

    python3 Scripts/dev/uepy.py --game --windowed --probe Scripts/probes/probe_bound_look.py

For each item in HOLD (the axe) and each way of moving, two pictures a third of a
second apart land in Saved/Screenshots/MacEditor, and the log says which
numbers are which.
"""

LEVEL = "/Game/Maps/Lvl_Forest_200m"  # passes here, fails on the 50 m probe level (T11)
SYSTEMS = ('animation',)

import os

import unreal

from combat.paths import WEAPON_COMP_BP_PATH, WEAPON_COMP_CLASS_PATH
from combat.weapon_component import vars as WV

# Holding an item writes SlotRequest, which boot.py opens for a probe that
# declares EquippedIndex.
WRITABLE = [(WEAPON_COMP_BP_PATH, WV.EquippedIndex)]
HOLD = (("axe", "BP_Axe_C"),)
EYE_AHEAD_CM, EYE_UP_CM, EYE_FOV = 300.0, 10.0, 50.0
MOVES = (("standing", 0.0, 0.0), ("walking forward", 1.0, 0.0),
         ("sidestepping right", 0.0, 1.0), ("sidestepping left", 0.0, -1.0),
         ("walking back", -1.0, 0.0))
SHOTS_DIR = os.path.join(unreal.Paths.project_saved_dir(), "Screenshots", "MacEditor")


def _count():
    return len(os.listdir(SHOTS_DIR)) if os.path.isdir(SHOTS_DIR) else 0


def probe(p):
    yield 0.5
    player, pc = p.pawn(), p.controller()
    wc = p.component(player, WEAPON_COMP_CLASS_PATH)
    world = p.world()
    # The eye is a wanderer, hidden and carried along in front of the player
    # (probe_hot_blade.py's way: nothing can be spawned into a running game
    # from here).
    ctrls = unreal.GameplayStatics.get_all_actors_of_class(world, unreal.AIController)
    eye = next((c.get_controlled_pawn() for c in ctrls
                if c.get_controlled_pawn() is not None), None)
    if eye is None:
        p.note("no wanderer to look through")
        return
    eye.set_actor_hidden_in_game(True)
    eye.set_actor_enable_collision(False)
    pc.set_view_target_with_blend(eye)
    unreal.SystemLibrary.execute_console_command(world, f"FOV {EYE_FOV:g}", pc)

    def watch():
        here, ahead = player.get_actor_location(), player.get_actor_forward_vector()
        eye.set_actor_location_and_rotation(
            here + ahead * EYE_AHEAD_CM + unreal.Vector(0.0, 0.0, EYE_UP_CM),
            unreal.Rotator(pitch=0.0, yaw=player.get_actor_rotation().yaw + 180.0, roll=0.0),
            False, True)

    def moving(fwd, right, seconds):
        t0 = unreal.GameplayStatics.get_time_seconds(world)

        def step():
            if fwd:
                player.add_movement_input(player.get_actor_forward_vector(), fwd)
            if right:
                player.add_movement_input(player.get_actor_right_vector(), right)
            watch()
            return unreal.GameplayStatics.get_time_seconds(world) - t0 >= seconds
        return step

    for label, cls in HOLD:
        bag = [i.get_class().get_name() for i in p.get(wc, "Inventory")]
        if cls and cls in bag:
            p.hold(wc, bag.index(cls))
        else:
            p.note(f"no {cls} in the bag: {bag}")
            continue
        yield moving(0.0, 0.0, 1.0)
        for name, fwd, right in MOVES:
            yield moving(fwd, right, 1.2)
            for k in range(2):
                unreal.SystemLibrary.execute_console_command(world, "shot")
                p.note(f"{label}, {name}, picture {k + 1}: speed "
                       f"{player.get_velocity().length():.0f}, shot #{_count()}")
                yield moving(fwd, right, 0.33)
    unreal.SystemLibrary.execute_console_command(world, "FOV 0", pc)
    pc.set_view_target_with_blend(player)
