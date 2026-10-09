"""Another player's character is animated by the motion matching too (G3).

    python3 Scripts/dev/uepy.py --net --clients 2 --probe Scripts/probes/probe_net_gas_locomotion.py

Client 1 jogs for a few seconds. Its own copy, client 2's copy of it (a
simulated one: no input, no acceleration of its own, only the replicated
movement) and the dedicated server's are each read while it does: the anim
instance on the hidden mesh has picked a run clip of the sample's, and the
legs move. The anim Blueprint reads the CharacterMovementComponent on every
machine (combat/gas_locomotion.py), so nothing is replicated for it.

On the server the same body is posed with the feet's ground traces skipped
(the graph's server branch), which the legs moving there also shows is not
the whole pose skipped.
"""

SYSTEMS = ('net', 'animation', 'movement')

import time

import unreal

from combat.gas_locomotion_consts import ABP_LOCOMOTION

RUNS_ON = ("server", "client")
WAIT = 40.0             # wall seconds any one step may take
JOG_S = 5.0             # wall seconds client 1 jogs
FEET_MOVE_CM = 8.0      # a foot's travel against the hips, moving
WANT_CLASS = ABP_LOCOMOTION.rsplit("/", 1)[1] + "_C"


def _await(ready, seconds=WAIT):
    until = time.time() + seconds
    yield lambda: ready() or time.time() > until


def _watch(p, pawn, whose):
    """Read ``pawn``'s anim instance while client 1 jogs."""
    mesh = pawn.get_editor_property("mesh")
    inst = mesh.get_anim_instance()
    name = inst.get_class().get_name() if inst else "no anim instance"
    if not p.check(f"{p.where}: {whose} runs the motion-matching anim Blueprint",
                   name == WANT_CLASS, name):
        return
    yield from _await(lambda: p.posted("client 1", "jogging"))
    clips, feet, states = [], [], set()
    until = time.time() + JOG_S * 0.6
    while time.time() < until:
        yield 0.0
        clip = inst.get_editor_property("CurrentSelectedAnim")
        if clip and clip.get_name() not in clips:
            clips.append(clip.get_name())
        states.add(str(inst.get_editor_property("MovementState")).split(".")[-1].split(":")[0])
        pelvis, foot = mesh.get_socket_location("pelvis"), mesh.get_socket_location("foot_l")
        feet.append(foot.z - pelvis.z)
    travel = max(feet) - min(feet) if feet else 0.0
    p.check(f"{p.where}: {whose} is moving to the anim Blueprint, which picked a run clip "
            "of the sample's", "MOVING" in states and any("Run" in c for c in clips),
            f"{sorted(states)}; {clips[:5]}")
    p.check(f"{p.where}: {whose}'s legs move (a foot travels over {FEET_MOVE_CM:.0f} cm "
            "against the hips)", travel > FEET_MOVE_CM, f"{travel:.0f} cm")


def probe_client(p):
    yield from _await(lambda: p.pawn() is not None)
    me = p.pawn()
    if p.client == 1:
        yield 1.5
        p.post("jogging")
        until = time.time() + JOG_S
        watch = _watch(p, me, "its own character")

        def step():
            me.add_movement_input(me.get_actor_forward_vector(), 1.0)
            return time.time() > until
        # Its own copy is read on the same frames it is driven.
        for wait in watch:
            yield lambda: step() or True
            if time.time() > until:
                break
        for _ in watch:
            yield 0.0
        p.post("jogged")
        return
    others = lambda: [a for a in unreal.GameplayStatics.get_all_actors_of_class(
        p.world(), me.get_class()) if a != me]
    yield from _await(lambda: bool(others()))
    if not p.check(f"{p.where} sees client 1's character", len(others()) == 1,
                   f"{len(others())} other character(s)"):
        return
    yield from _watch(p, others()[0], "its copy of client 1's character")


def probe_server(p):
    yield from _await(lambda: len(p.players()) >= 2 and all(
        c.get_controlled_pawn() for c in p.players()))
    # Client 1's is the first to have joined; either way the one that moves
    # is found by watching for it.
    pawns = [c.get_controlled_pawn() for c in p.players()]
    yield from _await(lambda: p.posted("client 1", "jogging"))
    yield 0.6
    mover = max(pawns, key=lambda a: a.get_velocity().length())
    if not p.check("the server has client 1's character moving",
                   mover.get_velocity().length() > 100.0,
                   f"{mover.get_velocity().length():.0f} cm/s"):
        return
    yield from _watch(p, mover, "the server's copy of client 1's character")
