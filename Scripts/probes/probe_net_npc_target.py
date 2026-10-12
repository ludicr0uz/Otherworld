"""A wanderer among several players: whom it hunts, and that every machine
hears and sees it (task M27).

    python3 Scripts/dev/uepy.py --net --clients 2 --probe Scripts/probes/probe_net_npc_target.py

The server stands one calm zombie between the two players, one at arm's
length and one 30 m off (past its sight, inside the scan of npc/target.py),
with every other wanderer's tree stopped. Then:

  - it notices the nearer one, and its Target is that player;
  - it keeps them: the far player brought beside it and the near one stepped
    back, Target does not change and it leaves the one beside it to go
    after its own (the nearest was asked at every read before);
  - the hunted player dies (their PlayerState says PlayerDead, as
    combat/death.py writes it): Target is the other player, and it swings at
    them;
  - both dead: Target is no one, it is still Aggro, and the hunt's steps do
    not run (no swing, no error); the first to live again is hunted.

Each client then reads its own copies of the wanderers' bodies: they have
played voices and clips (VoicesPlayed, ClipsPlayed: npc/body_fx.py's two
Multicasts), which before M27 only the server did.

npc/verify_target.py and verify_body_fx.py hold the graphs; a wendigo's hunt
starting over at a switch is the verifier's alone.
"""

SYSTEMS = ('npc', 'net')

import time

import unreal

from net import state_consts as S
from npc import body_vars as BV
from npc.paths import AGGRO_REASON_VAR, AGGRO_VAR, TARGET_VAR

# The far player stands past a zombie's 20 m of sight, which the 50 m level has no room for.
LEVEL = "/Game/Maps/Lvl_Forest_200m"

WRITABLE = [(S.PLAYER_STATE_BP_PATH, S.Dead)]

WAIT = 60.0           # wall seconds: a headless frame can be slow
BESIDE_CM = 150.0     # inside a zombie's touch range (250)
BACK_CM = 700.0       # outside touch and its swing, in plain view
FAR_CM = 3000.0       # past its sight (20 m), inside the scan (60 m)
PASSES = 1.6          # game seconds: three passes of the tree


def _await(ready, seconds=WAIT):
    until = time.time() + seconds
    yield lambda: ready() or time.time() > until


def _controllers(p):
    ctrls = unreal.GameplayStatics.get_all_actors_of_class(p.world(), unreal.AIController)
    return [c for c in ctrls if "ForestWandererAI" in c.get_class().get_name()
            and c.get_controlled_pawn() is not None]


def _bodies(p):
    return [a for a in unreal.GameplayStatics.get_all_actors_of_class(
        p.world(), unreal.Character) if "Wanderer" in a.get_class().get_name()]


def _name(a):
    return a.get_name() if a else "no one"


def _is(p, ctrl, pawn):
    got = p.get(ctrl, TARGET_VAR)
    return bool(got) and bool(pawn) and got.get_name() == pawn.get_name()


def _stand(pawn, anchor, toward, gap):
    """Put ``pawn`` ``gap`` cm from ``anchor`` along the unit vector ``toward``."""
    pawn.set_actor_location(unreal.Vector(anchor.x + toward.x * gap, anchor.y + toward.y * gap,
                                          anchor.z + 100.0), False, True)


def probe_server(p):
    yield from _await(lambda: len(_controllers(p)) > 0
                      and all(c.get_controlled_pawn() for c in p.players()))
    yield 1.0
    players = list(p.players())
    p.check("two players are in the game", len(players) == 2, f"{len(players)}")
    calm = [c for c in _controllers(p) if not p.get(c, AGGRO_VAR)]
    zombies = [c for c in calm if "Zombie" in c.get_class().get_name()]
    p.check("a calm zombie is there to stage", len(zombies) > 0,
            f"{len(zombies)} of {len(calm)} calm")
    if len(players) != 2 or not zombies:
        p.post("done", 0)
        return
    ctrl = zombies[0]
    body = ctrl.get_controlled_pawn()
    for other in _controllers(p):
        if other != ctrl:
            other.get_editor_property("brain_component").stop_logic("probe")
    near, far = [c.get_controlled_pawn() for c in players]
    near_state, far_state = [c.player_state for c in players]

    # Toward the middle of the map from where it stands: room for 30 m.
    here = body.get_actor_location()
    inward = unreal.Vector(-here.x, -here.y, 0.0)
    inward = inward.normal() if inward.length() > 1.0 else unreal.Vector(1.0, 0.0, 0.0)
    _stand(far, here, inward, FAR_CM)
    _stand(near, here, inward, BESIDE_CM)

    yield from _await(lambda: p.get(ctrl, AGGRO_VAR))
    p.check("it notices the player at arm's length (by sight or by touch)",
            p.get(ctrl, AGGRO_VAR) and p.get(ctrl, AGGRO_REASON_VAR) in ("sight", "touch"),
            f"reason {p.get(ctrl, AGGRO_REASON_VAR)!r}")
    p.check("...and its Target is that player, not the one 30 m off",
            _is(p, ctrl, near), _name(p.get(ctrl, TARGET_VAR)))
    yield PASSES
    p.check("...and stays them over the passes that follow",
            _is(p, ctrl, near), _name(p.get(ctrl, TARGET_VAR)))

    # The other player is now the nearer: it does not turn on them.
    spot = body.get_actor_location()
    _stand(near, spot, inward, BACK_CM)
    _stand(far, spot, inward, -BESIDE_CM)
    yield PASSES
    gaps = [(a.get_actor_location() - body.get_actor_location()).length() for a in (near, far)]
    p.check("the other player beside it and its own stepped back, it keeps its "
            "Target and goes after them",
            _is(p, ctrl, near) and gaps[0] < gaps[1],
            f"{_name(p.get(ctrl, TARGET_VAR))}; three passes on it is {gaps[0]:.0f} cm "
            f"from the hunted and {gaps[1]:.0f} cm from the other")

    # The hunted player dies.
    swings = p.get(body, BV.ClipsPlayed)
    p.set(near_state, S.Dead, True)
    yield from _await(lambda: _is(p, ctrl, far))
    p.check("the hunted player dead, its Target is the other player",
            _is(p, ctrl, far) and p.get(ctrl, AGGRO_VAR), _name(p.get(ctrl, TARGET_VAR)))
    yield from _await(lambda: p.get(body, BV.ClipsPlayed) > swings
                      or (_stand(far, body.get_actor_location(), inward, BESIDE_CM) and False))
    p.check("...and it swings at them",
            p.get(body, BV.ClipsPlayed) > swings,
            f"clips {swings} -> {p.get(body, BV.ClipsPlayed)}")

    # No one lives: the hunt's steps do not run.
    p.set(far_state, S.Dead, True)
    yield from _await(lambda: p.get(ctrl, TARGET_VAR) is None)
    swings = p.get(body, BV.ClipsPlayed)
    yield PASSES
    p.check("both dead, its Target is no one, it is still Aggro and it swings at nothing",
            p.get(ctrl, TARGET_VAR) is None and p.get(ctrl, AGGRO_VAR)
            and p.get(body, BV.ClipsPlayed) == swings,
            f"{_name(p.get(ctrl, TARGET_VAR))}, clips {swings} -> "
            f"{p.get(body, BV.ClipsPlayed)}")
    p.set(near_state, S.Dead, False)
    yield from _await(lambda: _is(p, ctrl, near))
    p.check("the first to live again is hunted", _is(p, ctrl, near),
            _name(p.get(ctrl, TARGET_VAR)))
    p.set(far_state, S.Dead, False)

    played = (p.get(body, BV.VoicesPlayed), p.get(body, BV.ClipsPlayed))
    p.check("the server's copy of its body has played voices and clips (its "
            "pose is what a shot is traced against)", min(played) > 0, f"{played}")
    yield 0.5
    p.post("done", list(played))


def probe_client(p):
    yield from _await(lambda: p.posted("server", "done") is not None, 4 * WAIT)
    sent = p.posted("server", "done")
    p.check("the server staged the hunt", bool(sent), f"{sent}")
    bodies = _bodies(p)
    voices = sum(p.get(b, BV.VoicesPlayed) for b in bodies)
    clips = sum(p.get(b, BV.ClipsPlayed) for b in bodies)
    p.check("this client's copies of the wanderers were heard: Multicast_Voice arrived",
            voices > 0, f"{voices} over {len(bodies)} bodies; the server's one played {sent}")
    p.check("...and seen to swing: Multicast_Clip arrived", clips > 0, f"{clips}")
