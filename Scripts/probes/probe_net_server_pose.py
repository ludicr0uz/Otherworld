"""A dedicated server poses its bodies at the rate a shot is judged, not the
rate a screen is drawn (task A4: combat/server_pose.py, pose_tuning.py,
combat/server_anim.py; the C++ is Source/Otherworld's OtherworldServerPose
and OtherworldHitHistory).

    python3 Scripts/dev/uepy.py --net --clients 2 --probe-timeout 240 \
        --probe Scripts/probes/probe_net_server_pose.py

On the server: only the mesh the game runs on still ticks on a player's body
(a MetaHuman's body, face and clothes do not); every body's anim instance
took the server arm of its graph; client 2's body, stood 5 m from client
1's, is posed every frame and the hit history has a pose for every frame of
it; a wanderer further than 30 m from both is posed a few times a second,
and the history holds fewer poses of it than frames. Then client 2's body is
moved 60 m off: both players' bodies drop to the far rate too.

On a client: its own body's anim instance took the client arm, and every
skinned mesh on it ticks, as before.
"""

LEVEL = "/Game/Maps/Lvl_Forest_200m"  # needs a wanderer more than 30 m from both players; the 50 m level has none
SYSTEMS = ('net',)

import time

import unreal

from combat.pose_tuning import FAR_HZ, FULL_WITHIN_CM
from combat.server_anim_consts import SERVER_POSE_VAR

RUNS_ON = ("server", "client")

WAIT = 20.0          # wall seconds a state may take to settle
NEAR_CM = 500.0      # where client 2's body is stood from client 1's
APART_CM = 6000.0    # and then: further than FULL_WITHIN_CM from everybody


def _await(ready, seconds=WAIT):
    until = time.time() + seconds
    yield lambda: ready() or time.time() > until


def _pause(seconds):
    until = time.time() + seconds
    yield lambda: time.time() > until


def _every(body):
    return unreal.OtherworldPoseLibrary.server_pose_every_frames(body)


def _history(body):
    lib = unreal.OtherworldShotLibrary
    return lib.hit_history_samples(body), lib.hit_history_poses(body)


def _flag(p, body):
    anim = body.mesh.get_anim_instance()
    return p.get(anim, SERVER_POSE_VAR) if anim else None


def _skinned(body):
    return len(body.get_components_by_class(unreal.SkinnedMeshComponent))


def _dist(a, b):
    return (a.get_actor_location() - b.get_actor_location()).length()


def probe_server(p):
    yield from _await(lambda: len(p.players()) >= p.clients
                      and all(c.get_controlled_pawn() for c in p.players()))
    players = [c.get_controlled_pawn() for c in p.players()]
    everyone = list(unreal.GameplayStatics.get_all_actors_of_class(p.world(), unreal.Character))
    wanderers = [a for a in everyone if a not in players]
    p.check("the server has both players' bodies and the wanderers",
            len(players) == 2 and len(wanderers) >= 1,
            f"{len(players)} player(s), {len(wanderers)} wanderer(s)")
    if len(players) != 2:
        return
    one, two = players

    # --- nothing but the mesh the game runs on ticks -----------------------------
    ticking = [unreal.OtherworldPoseLibrary.ticking_skinned_meshes(b) for b in everyone]
    p.check("on every body only the mesh the game runs on still ticks: what is hung "
            "under it to be drawn (a MetaHuman's body, face and clothes) does not",
            all(t == 1 for t in ticking),
            f"{sorted(set(ticking))} ticking; a player's body has {_skinned(one)} skinned mesh(es)")
    uro = [b.mesh.get_editor_property("enable_update_rate_optimizations") for b in everyone]
    p.check("...and that mesh skips frames by the engine's update rate optimization",
            all(uro), f"{sum(bool(u) for u in uro)} of {len(uro)}")

    # --- the anim graphs took their server arm ------------------------------------
    flags = [_flag(p, b) for b in everyone]
    p.check(f"every body's anim instance has {SERVER_POSE_VAR} set: the graph's server "
            "arm",
            all(f is True for f in flags), f"{sum(f is True for f in flags)} of {len(flags)}")

    # --- near another player: every frame -----------------------------------------
    here = one.get_actor_location()
    two.set_actor_location(here + unreal.Vector(NEAR_CM, 0.0, 0.0), False, True)
    yield from _pause(1.5)
    yield from _await(lambda: _every(one) == 1 and _every(two) == 1, 5.0)
    p.check(f"two players' bodies {NEAR_CM / 100:g} m apart are each posed every frame "
            f"(within {FULL_WITHIN_CM / 100:g} m of another player)",
            _every(one) == 1 and _every(two) == 1, f"every {_every(one)} and {_every(two)} frame(s)")
    yield from _pause(1.2)
    frames, poses = _history(two)
    p.check("...and the hit history has a pose for every frame it holds of one",
            frames >= 10 and poses >= frames - 2, f"{poses} pose(s) in {frames} frame(s)")

    # --- far from every player: a few times a second -------------------------------
    far = [w for w in wanderers if min(_dist(w, one), _dist(w, two)) > FULL_WITHIN_CM + 500.0
           and not w.mesh.is_any_simulating_physics()]
    p.check(f"a wanderer stands further than {FULL_WITHIN_CM / 100:g} m from both",
            bool(far), f"{len(far)} of {len(wanderers)}")
    if far:
        body = max(far, key=lambda w: min(_dist(w, one), _dist(w, two)))
        yield from _await(lambda: _every(body) > 1, 5.0)
        yield from _pause(1.2)
        frames, poses = _history(body)
        p.check(f"...and is posed {FAR_HZ:g} times a second or fewer: every few frames",
                _every(body) >= 2, f"every {_every(body)} frame(s), "
                f"{min(_dist(body, one), _dist(body, two)) / 100:.0f} m from the nearest player")
        p.check("...of which the hit history holds fewer poses than frames, and blends "
                "between them", frames >= 10 and 2 <= poses <= frames * 0.7,
                f"{poses} pose(s) in {frames} frame(s)")

    # --- a player's own body, with nobody near, is throttled too -------------------
    two.set_actor_location(here + unreal.Vector(APART_CM, 0.0, 300.0), False, True)
    yield from _await(lambda: _every(two) > 1, 5.0)
    p.check(f"client 2's body, moved {APART_CM / 100:g} m off, drops to the far rate",
            _every(two) >= 2, f"every {_every(two)} frame(s)")
    p.post("judged")


def probe_client(p):
    yield from _await(lambda: p.pawn() is not None)
    body = p.pawn()
    yield from _await(lambda: body.mesh.get_anim_instance() is not None)
    p.check(f"{p.where}'s own body took its graph's client arm ({SERVER_POSE_VAR} false)",
            _flag(p, body) is False, repr(_flag(p, body)))
    ticking = unreal.OtherworldPoseLibrary.ticking_skinned_meshes(body)
    p.check(f"...and every skinned mesh on it ticks: {p.where} draws them",
            ticking == _skinned(body) and ticking >= 1, f"{ticking} of {_skinned(body)}")
    p.check(f"...none of them throttled by the server's rule",
            unreal.OtherworldPoseLibrary.server_pose_every_frames(body) == 0,
            str(unreal.OtherworldPoseLibrary.server_pose_every_frames(body)))
    yield from _await(lambda: p.posted("server", "judged"), 60.0)
