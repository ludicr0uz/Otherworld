"""Another player's copy steps round after that player's view too
(combat/gas_turn.py).

    python3 Scripts/dev/uepy.py --net --clients 2 --probe Scripts/probes/probe_net_turn_in_place.py

Client 1 stands and turns its view a half circle in a second, twice: as it
joined, and then with the shotgun down the sights (a raised gun's pose is in
the slot whose name the sample's root offset used to ask after). Its own
copy, client 2's copy of it (a simulated one: only the replicated movement)
and the dedicated server's are each read through both turns: the actor turned
with the view, the motion matching picked a clip of the sample's
turn-in-place database, and afterwards the root it draws is back under the
actor. On the two clients the feet are read as well: both step, and the one
on the ground stays put (probe_turn_in_place.py has the measure). The flag
that offers the turn is the movement's own velocity and stance on every
machine, so nothing is replicated for it.

Every mesh read is made to pose every frame (a headless game renders nothing,
and an unrendered mesh keeps its last bones, which then turn with the capsule
like a statue's), and the server takes the pack away first.
"""

SYSTEMS = ('net', 'animation', 'movement')

import math
import time

import unreal

from combat.paths import WEAPON_COMP_BP_PATH, WEAPON_COMP_CLASS_PATH
from combat.record_vars import SlotForced
from combat.seat_tuning import SIGHTS_FORCED_VAR
from combat.weapon_component import vars as WV
from probes import crawl_watch as CW
from probes.probe_hot_blade import _wanderers

RUNS_ON = ("server", "client")
WRITABLE = [(WEAPON_COMP_BP_PATH, v) for v in (SIGHTS_FORCED_VAR, SlotForced)]

WAIT = 40.0             # wall seconds any one step may take
TURN_DEG, TURN_S = 180.0, 1.0
SETTLE_S = 3.5          # game seconds client 1 stands after a turn
TAIL_S = 8.0            # wall seconds a watcher lets the turn clip's tail take
TURNED_DEG = 150.0      # the actor's yaw has gone at least this far round
CAUGHT_UP_DEG = 10.0    # the drawn root against the actor, after the turn
STEP_CM = 40.0          # each ball of the foot goes at least this far round
PLANTED_CM = 15.0       # ...and the slower of the two, frame by frame, under this
TURN_TAG = "TurnInPlace"
PHASES = ("as it joined", "down the sights")


def _await(ready, seconds=WAIT):
    until = time.time() + seconds
    yield lambda: ready() or time.time() > until


def _d(a, b):
    return (a - b + 180.0) % 360.0 - 180.0


class _Seen:
    """One copy of client 1's character, read every frame of one turn."""

    def __init__(self, pawn):
        self.pawn = pawn
        self.mesh = pawn.get_editor_property("mesh")
        # Nothing is rendered here, and an unrendered mesh keeps its last
        # bones: they would turn with the capsule like a statue's.
        CW.always_pose(self.mesh)
        self.inst = self.mesh.get_anim_instance()
        self.yaw0 = pawn.get_actor_rotation().yaw
        self.clips, self.all, self.planted = [], [0.0, 0.0], 0.0
        self.last = self._balls()

    def _balls(self):
        return [self.mesh.get_socket_location(s) for s in ("ball_l", "ball_r")]

    def turned(self):
        return abs(_d(self.pawn.get_actor_rotation().yaw, self.yaw0))

    def behind(self):
        root = self.inst.get_editor_property("RootTransform").rotation.rotator().yaw
        return _d(root, self.pawn.get_actor_rotation().yaw)

    def turning(self):
        return TURN_TAG in [str(t) for t in self.inst.get_editor_property("CurrentDatabaseTags")]

    def sample(self):
        clip = self.inst.get_editor_property("CurrentSelectedAnim")
        if clip and self.turning() and clip.get_name() not in self.clips:
            self.clips.append(clip.get_name())
        balls = self._balls()
        steps = [math.hypot(at.x - was.x, at.y - was.y)
                 for was, at in zip(self.last, balls)]
        self.all = [a + s for a, s in zip(self.all, steps)]
        self.planted += min(steps)
        self.last = balls

    def report(self, p, whose, phase, feet):
        head = f"{p.where}, {phase}: {whose}"
        p.check(f"{head} turned with the view (over {TURNED_DEG:g} deg)",
                self.turned() > TURNED_DEG, f"{self.turned():.0f} deg")
        p.check(f"{head} picked a clip of the sample's turn-in-place database",
                bool(self.clips), ", ".join(self.clips) or "none")
        p.check(f"{head}'s legs caught up: the drawn root within {CAUGHT_UP_DEG:g} deg "
                "of the actor, the idle back",
                abs(self.behind()) < CAUGHT_UP_DEG and not self.turning(),
                f"{self.behind():+.1f} deg")
        if feet:
            p.check(f"{head}'s feet step (each over {STEP_CM:g} cm) and the one on the "
                    f"ground does not slide (the slower foot under {PLANTED_CM:g} cm)",
                    min(self.all) > STEP_CM and self.planted < PLANTED_CM,
                    "left {:.0f} cm, right {:.0f} cm, the slower one {:.1f} cm".format(
                        *self.all, self.planted))


def _watch(p, pawns, whose, feet):
    """Read ``pawns`` through each of client 1's turns; the one that turned
    is its character."""
    for phase in PHASES:
        yield from _await(lambda: p.posted("client 1", f"turning {phase}"))
        seen = [_Seen(a) for a in pawns]
        until = time.time() + WAIT
        while not p.posted("client 1", f"turned {phase}") and time.time() < until:
            yield 0.0
            for s in seen:
                s.sample()
        # This machine's clock is its own (a loaded server's runs slow): the
        # clip's tail is given a little longer to play out.
        until = time.time() + TAIL_S
        while any(s.turning() for s in seen) and time.time() < until:
            yield 0.0
            for s in seen:
                s.sample()
        max(seen, key=lambda s: s.turned()).report(p, whose, phase, feet)


def _turn(p, pc, seen):
    now = lambda: unreal.GameplayStatics.get_time_seconds(p.world())
    start, yaw0 = now(), pc.get_control_rotation().yaw
    while now() - start < TURN_S + SETTLE_S:
        part = min(1.0, (now() - start) / TURN_S)
        pc.set_control_rotation(
            unreal.Rotator(pitch=0.0, yaw=yaw0 + TURN_DEG * part, roll=0.0))
        yield 0.0
        seen.sample()


def probe_client(p):
    yield from _await(lambda: p.pawn() is not None)
    me = p.pawn()
    if p.client != 1:
        others = lambda: [a for a in unreal.GameplayStatics.get_all_actors_of_class(
            p.world(), me.get_class()) if a != me]
        yield from _await(lambda: bool(others()))
        if p.check(f"{p.where} sees client 1's character", len(others()) == 1,
                   f"{len(others())} other character(s)"):
            CW.always_pose(others()[0].get_editor_property("mesh"))
            yield from _watch(p, others(), "its copy of client 1's character", True)
        return
    wc = p.component(me, WEAPON_COMP_CLASS_PATH)
    yield from _await(lambda: me.get_editor_property("mesh").get_anim_instance()
                      .get_editor_property("CurrentSelectedAnim") is not None)
    CW.always_pose(me.get_editor_property("mesh"))
    yield from _await(lambda: p.posted("server", "no pack"))
    yield 3.0
    for phase in PHASES:
        if phase == PHASES[1]:
            names = lambda: [i.get_class().get_name() for i in p.get(wc, WV.Inventory) if i]
            yield from _await(lambda: "BP_Shotgun_C" in names())
            p.hold(wc, names().index("BP_Shotgun_C"))
            yield from _await(lambda: p.get(wc, WV.Held) is not None
                              and p.get(wc, WV.Held).get_class().get_name() == "BP_Shotgun_C")
            p.set(wc, SIGHTS_FORCED_VAR, True)
            yield from _await(lambda: p.get(wc, "SightAiming")
                              and p.get(wc, "SightBlend") > 0.99)
            p.check("client 1 has the shotgun down the sights",
                    bool(p.get(wc, "SightAiming")) and p.get(wc, "SightBlend") > 0.99)
            yield 1.5
        held = p.get(wc, WV.Held)
        p.note(f"client 1, {phase}: holding {held.get_class().get_name() if held else 'nothing'}")
        seen = _Seen(me)
        p.post(f"turning {phase}")
        yield 0.3
        yield from _turn(p, p.controller(), seen)
        seen.report(p, "its own character", phase, True)
        p.post(f"turned {phase}")
        yield 1.0
    p.set(wc, SIGHTS_FORCED_VAR, False)


def probe_server(p):
    yield from _await(lambda: len(p.players()) >= 2 and all(
        c.get_controlled_pawn() for c in p.players()))
    pawns = [c.get_controlled_pawn() for c in p.players()]
    # A player standing for half a minute is the pack's: it is taken away.
    for ctrl in _wanderers(p):
        ctrl.get_controlled_pawn().destroy_actor()
    for a in pawns:
        CW.always_pose(a.get_editor_property("mesh"))
    p.post("no pack")
    # The server skips the feet's ground traces (the graph's server branch).
    yield from _watch(p, pawns, "the server's copy of client 1's character", False)
