"""The player's default movement is a jog, not a walk (combat/player_gait.py).

Pushed forward with no key held, the player:
  - moves at player_tuning.csv's jog speed;
  - lifts their feet as the jog clip does, not as the walk clip does: the
    left foot's rise over the run, against each clip's own. (A blend of the
    two, or a blend space reading the wrong samples, rises far less.)

The mannequin fallback's anim Blueprint is not scaled: the probe then only
checks the speed.
"""

import time

import unreal

from asset_pipeline.rig_util import _bone_world
from combat.player_gait import STOCK_DIR
from combat.tuning import COMBAT

FOOT = "LeftFoot"
JOG_S = 2.0             # game seconds of jogging measured, after the run-up
WALL_WAIT_S = 60.0
CLIP_STEPS = 60


def _until(cond):
    end = time.time() + WALL_WAIT_S
    return lambda: cond() or time.time() > end


def _clip_lift(clip):
    """cm the foot rises over the clip, lowest to highest."""
    length = clip.get_editor_property("sequence_length")
    zs = [_bone_world(clip, FOOT, length * i / CLIP_STEPS).z
          for i in range(CLIP_STEPS + 1)]
    return max(zs) - min(zs)


def probe(p):
    player = p.pawn()
    mesh = player.mesh
    jog = COMBAT.jog_speed_cms
    now = lambda: unreal.GameplayStatics.get_time_seconds(p.world())  # noqa: E731

    # Headless, nothing is rendered, and an unrendered mesh is not posed.
    mesh.set_editor_property(
        "visibility_based_anim_tick_option",
        unreal.VisibilityBasedAnimTickOption.ALWAYS_TICK_POSE_AND_REFRESH_BONES,
        unreal.PropertyAccessChangeNotifyMode.NEVER)

    def push():
        player.add_movement_input(player.get_actor_forward_vector(), 1.0)

    def run_up():
        push()
        return player.get_velocity().length() > jog * 0.95
    yield _until(run_up)
    t0 = now()

    def settled():          # the blend space eases onto its row
        push()
        return now() - t0 >= 1.0
    yield _until(settled)

    t0 = now()
    speeds, feet = [], []

    def jogging():
        push()
        speeds.append(player.get_velocity().length())
        feet.append(mesh.get_socket_location(FOOT).z - player.get_actor_location().z)
        return now() - t0 >= JOG_S
    yield _until(jogging)
    speeds.sort()
    median = speeds[len(speeds) // 2] if speeds else 0.0
    p.check(f"pushed forward with no key held, the player moves at the jog's "
            f"{jog:.0f} cm/s", abs(median - jog) < jog * 0.05,
            f"median {median:.0f} cm/s over {len(speeds)} frames")

    # The worn body's own clips, beside its anim Blueprint.
    abp = mesh.get_editor_property("anim_class").get_path_name().split(".")[0]
    if abp.startswith(STOCK_DIR):
        p.note("the mannequin's anim Blueprint: its speed is not scaled")
        return
    stem = abp.replace("ABP_Unarmed", "")
    walk_lift = _clip_lift(unreal.load_asset(stem + "Walk_Fwd"))
    jog_lift = _clip_lift(unreal.load_asset(stem + "Jog_Fwd"))
    lift = max(feet) - min(feet) if feet else 0.0
    p.check("the feet lift as the jog clip's do, not as the walk clip's",
            abs(lift - jog_lift) < abs(lift - walk_lift)
            and abs(jog_lift - walk_lift) > 3.0,
            f"the left foot rises {lift:.1f} cm; the walk clip's rises "
            f"{walk_lift:.1f}, the jog clip's {jog_lift:.1f}")
