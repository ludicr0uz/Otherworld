"""Another player's crawl goes the way it moves (P2), on every machine.

    python3 Scripts/dev/uepy.py --net --clients 2 --probe Scripts/probes/probe_net_crawl.py
    python3 Scripts/dev/uepy.py --net --clients 2 --lag 120 --probe Scripts/probes/probe_net_crawl.py

Client 1 lies down empty-handed and crawls right, left, back and back left
of its own body (left first when client 2's character is at its right). Its
own copy, client 2's copy of it (a simulated one: only the replicated
movement) and the dedicated server's are each watched over the same stretch,
and each is held to that direction's own motion (crawl_watch.own_motion: the
forward loop passes none of these) and to what client 1 measured on itself.

The direction is the pawn's velocity in its own frame, read by the weapon
layers' event graph on each machine (combat/crawl_direction.py): the movement
component has it on the owner, on the server and, from the replicated
movement, on a simulated copy, so nothing is replicated for it. This probe is
what shows that holds.

No key can be injected, so client 1 writes its Stance as the Z toggle does
and feeds movement input (the same path a key takes: predicted, then sent).
"""

SYSTEMS = ('net', 'animation', 'movement')

import time

import unreal

from combat import anim_vars as AN
from combat.crawl_consts import BY_NAME, CRAWL_CMS, alphas
from combat.record_vars import MoveForcedFrom, MoveForcedTo
from combat.paths import WEAPON_COMP_BP_PATH, WEAPON_COMP_CLASS_PATH
from combat.slot_tuning import HAND, PRIMARY
from combat.weapon_component.stance import PRONE, STANCE_VAR, STAND
from probes import crawl_watch as CW
from probes.probe_hot_blade import _wanderers

RUNS_ON = ("server", "client")
WRITABLE = [(WEAPON_COMP_BP_PATH, str(v)) for v in (STANCE_VAR, MoveForcedFrom, MoveForcedTo)]
TIMEOUT = 150.0         # wall seconds: four directions on three machines
WAIT = 40.0             # wall seconds any one step may take
# The two characters start side by side, either way round by who joined
# first: client 1 goes away from the other one first (_order).
WAYS = ("right", "left", "back", "back left")
# Seconds of client 1's world (a headless game's clock is not the wall's): it
# crawls START_S for the eased weights to arrive everywhere, lag included, says
# so, is read for READ_S by every machine, says so and crawls TAIL_S more, so
# that a copy is still crawling when its machine hears.
START_S, READ_S, TAIL_S, REST_S = 1.5, 3.5, 0.5, 1.0
# A copy against client 1's own: the lean and each hand's reach (cm).
LEAN_CM, REACH_CM = 2.5, 6.0
# The weights that choose the loop, against crawl_consts.alphas.
WEIGHTS = (AN.CrawlMove, AN.CrawlDiag, AN.CrawlSide, AN.CrawlBack, AN.CrawlRight)


def _await(ready, seconds=WAIT):
    until = time.time() + seconds
    yield lambda: ready() or time.time() > until


def _read(p, pawn, done):
    """Watch ``pawn`` tick by tick until ``done()``: {"sig", "vel", "weights",
    "span"}, into the dict this returns with the step to yield."""
    anim = p.pose_instance(pawn.get_editor_property("mesh"))
    now = lambda: unreal.GameplayStatics.get_time_seconds(p.world())
    track, vel, got = [], [], {}

    def step():
        track.append((now(), CW.joints(pawn)))
        vel.append(CW.local_velocity(pawn))
        if not done() or len(track) < 2:
            return False
        got["sig"] = CW.signature(track)
        got["vel"] = [sum(v[i] for v in vel) / len(vel) for i in (0, 1)]
        got["weights"] = [round(p.get(anim, str(v)), 2) for v in WEIGHTS]
        got["span"] = f"{len(track)} frames, {track[-1][0] - track[0][0]:.1f} s"
        return True
    return got, step


def _judge(p, whose, name, got, own=None):
    d, sig = BY_NAME[name], got["sig"]
    want = [round(a, 2) for a in alphas(d.ahead * CRAWL_CMS, d.right * CRAWL_CMS)]
    # Which side, or which end, of a body that goes to neither weighs nothing.
    for i, along in ((3, d.ahead), (4, d.right)):
        if not along:
            want[i] = got["weights"][i]
    going = got["vel"][0] * d.ahead + got["vel"][1] * d.right
    speed = (got["vel"][0] ** 2 + got["vel"][1] ** 2) ** 0.5
    others = [n for n in CW.OWN if n != name and CW.own_motion(n, sig)]
    p.check(f"{p.where}: {whose} goes {name} of its body, its weights choose that "
            "direction's loop and its hands do what that loop does (and not the "
            "forward one's), nothing under the ground",
            speed > 60.0 and going > 0.95 * speed and got["weights"] == want
            and CW.own_motion(name, sig) and not others and sig["low"] > -1.0,
            f"{got['span']}: {got['vel'][0]:+.0f} ahead {got['vel'][1]:+.0f} right; weights "
            f"{got['weights']} for {want}; {CW.brief(sig)}"
            + (f"; reads as {others}" if others else ""))
    if own is None:
        return
    p.check(f"{p.where}: {whose} crawls {name} as client 1 does on its own machine "
            f"(the lean within {LEAN_CM:g} cm, each hand's reach within {REACH_CM:g})",
            abs(sig["lean"] - own["lean"]) < LEAN_CM
            and all(abs(sig[k] - own[k]) < REACH_CM for k in ("reach_l", "reach_r")),
            f"lean {sig['lean']:+.1f} against {own['lean']:+.1f}, reach "
            f"{sig['reach_l']:.1f}/{sig['reach_r']:.1f} against "
            f"{own['reach_l']:.1f}/{own['reach_r']:.1f}")


def _clear_pack(p):
    """A player lying down for half a minute is the pack's: the server takes
    the pack away (a body that respawns is taken again)."""
    for ctrl in _wanderers(p):
        pawn = ctrl.get_controlled_pawn()
        if pawn:
            pawn.destroy_actor()


def _order(p, me):
    """WAYS, the side the other character is not on first."""
    others = [a for a in unreal.GameplayStatics.get_all_actors_of_class(
        p.world(), me.get_class()) if a != me]
    right = any((a.get_actor_location() - me.get_actor_location())
                .dot(me.get_actor_right_vector()) > 0.0 for a in others)
    return [WAYS[1], WAYS[0], *WAYS[2:]] if right else list(WAYS)


def _watch_copy(p, pawn, whose):
    CW.always_pose(pawn.get_editor_property("mesh"))
    yield from _await(lambda: p.posted("client 1", "order"))
    for name in p.posted("client 1", "order") or ():
        if p.where == "server":
            _clear_pack(p)
        yield from _await(lambda: p.posted("client 1", f"go {name}")
                          or p.posted("client 1", "done"))
        if not p.posted("client 1", f"go {name}"):
            p.check(f"{p.where}: client 1 crawled {name}", False, "it never did")
            return
        until = time.time() + WAIT
        got, step = _read(p, pawn, lambda: p.posted("client 1", f"sig {name}")
                          or time.time() > until)
        yield step
        _judge(p, whose, name, got, p.posted("client 1", f"sig {name}"))


def probe_client(p):
    yield from _await(lambda: p.pawn() is not None)
    me = p.pawn()
    if p.client != 1:
        others = lambda: [a for a in unreal.GameplayStatics.get_all_actors_of_class(
            p.world(), me.get_class()) if a != me]
        yield from _await(lambda: bool(others()))
        if p.check(f"{p.where} sees client 1's character", len(others()) == 1,
                   f"{len(others())} other character(s)"):
            yield from _watch_copy(p, others()[0], "its copy of client 1's character")
        return
    wc = p.component(me, WEAPON_COMP_CLASS_PATH)
    CW.always_pose(me.get_editor_property("mesh"))
    yield from _await(lambda: p.posted("server", "no pack"))
    yield 1.0
    # Empty hands: the loops are read off the hands, and a gun holds them up.
    p.ask_move(wc, HAND, PRIMARY)
    yield from _await(lambda: p.get(wc, "Held") is None, 10.0)
    p.set(wc, STANCE_VAR, PRONE)
    anim = p.pose_instance(me.get_editor_property("mesh"))
    yield from _await(lambda: p.get(anim, str(AN.PoseProne)) > 0.98)
    yield 0.5
    now = lambda: unreal.GameplayStatics.get_time_seconds(p.world())

    def crawl(d, seconds):
        until = now() + seconds

        def step():
            CW.push(me, d.ahead, d.right)
            return now() >= until
        return step
    order = _order(p, me)
    p.post("order", order)
    for name in order:
        d = BY_NAME[name]
        yield crawl(d, START_S)
        p.post(f"go {name}")
        until = now() + READ_S
        got, step = _read(p, me, lambda: now() >= until)
        yield lambda: CW.push(me, d.ahead, d.right) or step()
        _judge(p, "its own character", name, got)
        p.post(f"sig {name}", {k: got["sig"][k] for k in ("lean", "reach_l", "reach_r")})
        yield crawl(d, TAIL_S)
        yield REST_S
    p.set(wc, STANCE_VAR, STAND)
    p.post("done")


def probe_server(p):
    yield from _await(lambda: len(p.players()) >= 2 and all(
        c.get_controlled_pawn() for c in p.players()))
    pawns = [c.get_controlled_pawn() for c in p.players()]
    _clear_pack(p)
    p.post("no pack")
    for a in pawns:
        CW.always_pose(a.get_editor_property("mesh"))
    yield from _await(lambda: any(p.posted("client 1", f"go {name}") for name in WAYS[:2]))
    # Client 1's is the one that moves.
    yield from _await(lambda: max(a.get_velocity().length() for a in pawns) > 40.0, 5.0)
    mover = max(pawns, key=lambda a: a.get_velocity().length())
    if p.check("the server has client 1's character crawling",
               mover.get_velocity().length() > 40.0,
               f"{mover.get_velocity().length():.0f} cm/s"):
        yield from _watch_copy(p, mover, "the server's copy of client 1's character")
