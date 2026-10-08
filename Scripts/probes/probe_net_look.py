"""Another player's character is posed as its own player has it (M13).

    python3 Scripts/dev/uepy.py --net --clients 2 --probe-timeout 240 --probe Scripts/probes/probe_net_look.py
    OW_LOOK_SHOTS=1 python3 Scripts/dev/uepy.py --net --clients 2 --windowed --probe-timeout 240 --probe Scripts/probes/probe_net_look.py

Client 1 acts: it walks a few metres off (two players start exactly two
capsule radii apart, where the server will not let a crouched one stand:
Scripts/net/CLAUDE.md), crouches, lies down, stands, aims over the shoulder, then
down the sights with the view up and down, lets go, and brings to hand a
pistol, a knife, the matches, the stick and a rifle. After each step it posts what its
own character is doing; client 2 and the server then look at THEIR copy of
that character (weapon_component/look.py): the stance and the capsule, the
aim mode, the gun raised or lowered, the hand's pose and that it is playing,
and the upper body's pitch.

The rifle is not an issued item, and nothing hands a client of a server one
yet (the cheat is single player's, a drop is a one-in-ten roll), so the
rifle's step is its ready pose: client 1's shotgun is given the rifle's
AimPose, as torch.py gives a stick its UsePose, and re-equipped. What stands
in a copy's hand is that copy's own item until the inventory replicates
(M18); the pose is what travels here.

With --windowed and OW_LOOK_SHOTS=1 client 2 turns to client 1's character
and saves a picture of each step to Saved/Screenshots/MacEditor.

``probe`` is single player's arm (--game): the one machine is local, so the
look is the keys' own, and the pose the equip plays is still Held's.
"""

import os
import time

import unreal

from combat import item_vars as IV
from combat.aim_pitch import AIM_PITCH_VAR
from combat.anim_blueprint import AIM_SLOT
from combat.body_pose import POSE_CROUCH, POSE_PRONE
from combat.carry_tuning import LOWERED_VAR, RAISE_FORCED_VAR
from combat.paths import (
    HOLD_ITEM_ANIM_PATH, HOLD_KNIFE_ANIM_PATH, ITEM_BP_PATH, RIFLE_BP_PATH, SHOTGUN_AIM_ANIM_PATH,
    WEAPON_COMP_BP_PATH, WEAPON_COMP_CLASS_PATH)
from combat.seat_tuning import SIGHTS_FORCED_VAR
from combat.tuning import COMBAT
from combat.weapon_component import vars as WV
from combat.weapon_component.ads import AIM_FORCED_VAR
from combat.weapon_component.look_vars import HIP, SHOULDER, SIGHTS, HandPose, LookPose
from combat.weapon_component.stance import CROUCH, PRONE, STANCE_VAR, STAND

RUNS_ON = ("server", "client", "standalone")
WRITABLE = [(WEAPON_COMP_BP_PATH, v) for v in (
    STANCE_VAR, AIM_FORCED_VAR, SIGHTS_FORCED_VAR, RAISE_FORCED_VAR, WV.EquippedIndex)]
WRITABLE += [(WEAPON_COMP_BP_PATH, WV.NeedsRefresh), (ITEM_BP_PATH, IV.AimPose)]

MOVE = unreal.OtherworldMovementLibrary
RIFLE_CLASS_PATH = f"{RIFLE_BP_PATH}.{RIFLE_BP_PATH.rsplit('/', 1)[1]}_C"
SHOTS = bool(os.environ.get("OW_LOOK_SHOTS"))
WAIT = 30.0          # wall seconds any one step may take
SEEN_S = 4.0         # ... and a watcher's copy has to follow within
SETTLE_S = 0.6       # wall seconds the actor holds a step before it posts
WALK_CM = 350.0      # how far client 1 walks off before it acts
PITCH_DEG = 30.0     # the view up, then down, on the sights
PITCH_NEAR_DEG = 5.0
HEIGHT_NEAR_CM = 1.5
STANDING_CM = 90.0   # the standing capsule's half height, least
POSES = {"knife": HOLD_KNIFE_ANIM_PATH, "matches": HOLD_ITEM_ANIM_PATH,
         "shotgun": SHOTGUN_AIM_ANIM_PATH}


def _await(ready, seconds=WAIT):
    until = time.time() + seconds
    yield lambda: ready() or time.time() > until


def _xyz(actor):
    v = actor.get_actor_location()
    return [v.x, v.y, v.z]


def _name(asset):
    return asset.get_name() if asset else None


def _look(p, pawn):
    """What this machine's copy of ``pawn`` is posed by."""
    wc = p.component(pawn, WEAPON_COMP_CLASS_PATH)
    anim = pawn.mesh.get_anim_instance()
    # The pose variables are the weapon layers' instance's (probes/context.py).
    layers = p.pose_instance(pawn.mesh)
    aim = (SIGHTS if p.get(wc, WV.SightAiming) else SHOULDER) if p.get(wc, WV.Aiming) else HIP
    return {
        "stance": p.get(wc, STANCE_VAR),
        "moves": MOVE.get_stance(pawn),
        "height": pawn.capsule_component.get_unscaled_capsule_half_height(),
        "feet": pawn.mesh.get_world_location().z - (
            pawn.get_actor_location().z
            - pawn.capsule_component.get_unscaled_capsule_half_height()),
        "aim": aim,
        "lowered": bool(p.get(wc, LOWERED_VAR)),
        "pose": _name(p.get(wc, HandPose)),
        "playing": bool(anim and anim.is_slot_active(AIM_SLOT)),
        "crouch": float(p.get(layers, POSE_CROUCH)) if layers else 0.0,
        "prone": float(p.get(layers, POSE_PRONE)) if layers else 0.0,
        "pitch": float(p.get(layers, AIM_PITCH_VAR)) if layers else 0.0,
    }


def _agrees(here, there, step):
    """{label: (ok, detail)}: this copy against what the actor posted."""
    out = {}
    out["stance"] = (here["stance"] == there["stance"] == here["moves"],
                     f"{here['stance']} (movement {here['moves']}); the player's {there['stance']}")
    out["capsule"] = (abs(here["height"] - there["height"]) <= HEIGHT_NEAR_CM,
                      f"{here['height']:.1f} cm; the player's {there['height']:.1f}")
    out["aim mode"] = (here["aim"] == there["aim"], f"{here['aim']}; the player's {there['aim']}")
    out["lowered"] = (here["lowered"] == there["lowered"],
                      f"{here['lowered']}; the player's {there['lowered']}")
    out["hand pose"] = (here["pose"] == there["pose"],
                        f"{here['pose']}; the player's {there['pose']}")
    return out


def _poses(here, there):
    """The anim instance's side of it: a client's alone (it draws)."""
    out = {}
    wants = there["pose"] is not None and not there["lowered"]
    out["the pose is playing"] = (here["playing"] == wants, f"{here['playing']}, wanted {wants}")
    low = {STAND: (0.0, 0.0), CROUCH: (1.0, 0.0), PRONE: (0.0, 1.0)}[there["stance"]]
    out["the stance's weights"] = (
        abs(here["crouch"] - low[0]) < 0.15 and abs(here["prone"] - low[1]) < 0.15,
        f"crouch {here['crouch']:.2f}, prone {here['prone']:.2f}")
    out["the body's pitch"] = (abs(here["pitch"] - there["pitch"]) <= PITCH_NEAR_DEG,
                               f"{here['pitch']:.1f}; the player's {there['pitch']:.1f}")
    out["the feet on the ground"] = (abs(here["feet"] - there["feet"]) <= 3.0,
                                     f"mesh {here['feet']:.1f} cm off the capsule's foot; "
                                     f"the player's {there['feet']:.1f}")
    return out


# ─── client 1 acts ───────────────────────────────────────────────────────────

def _index(p, wc, word):
    for i, item in enumerate(p.get(wc, WV.Inventory)):
        if word in item.get_class().get_name().lower():
            return i
    return -1


def _steps(p, pawn, wc):
    """(name, what to do) in order. Each is done, held, then posted."""
    pc = p.controller()

    def view(pitch):
        rot = pc.get_control_rotation()
        pc.set_control_rotation(unreal.Rotator(pitch=pitch, yaw=rot.yaw, roll=0.0))

    def hold(word, raised=False):
        def do():
            p.set(wc, RAISE_FORCED_VAR, raised)
            p.hold(wc, _index(p, wc, word))
        return do

    def rifle_pose():
        gun = p.get(wc, WV.Inventory)[_index(p, wc, "shotgun")]
        rifle = unreal.get_default_object(p.load_class(RIFLE_CLASS_PATH))
        p.set(gun, IV.AimPose, rifle.get_editor_property(IV.AimPose))
        p.set(wc, WV.NeedsRefresh, True)

    def aim(shoulder, sights, pitch=0.0):
        def do():
            p.set(wc, AIM_FORCED_VAR, shoulder)
            p.set(wc, SIGHTS_FORCED_VAR, sights)
            view(pitch)
        return do

    return [
        ("standing", lambda: p.set(wc, STANCE_VAR, STAND)),
        ("crouched", lambda: p.set(wc, STANCE_VAR, CROUCH)),
        ("prone", lambda: p.set(wc, STANCE_VAR, PRONE)),
        ("standing again", lambda: p.set(wc, STANCE_VAR, STAND)),
        ("the shoulder aim", aim(True, False)),
        ("the sights", aim(False, True)),
        ("the sights, looking up", aim(False, True, PITCH_DEG)),
        ("the sights, looking down", aim(False, True, -PITCH_DEG)),
        ("the aim let go", aim(False, False)),
        ("a pistol, lowered", hold("pistol")),
        ("a pistol, raised", hold("pistol", True)),
        ("a knife", hold("knife")),
        ("an item (the matches), lowered", hold("matches")),
        ("an item (the matches), raised", hold("matches", True)),
        ("an item carried up (the stick)", hold("stick")),
        ("a long gun again (the shotgun), raised", hold("shotgun", True)),
        ("a rifle's ready pose, raised", rifle_pose),
    ]


def _walk_off(p, pawn, other):
    """Away from the other player, far enough to be looked at and to stand up."""
    start = pawn.get_actor_location()
    away = start - other.get_actor_location()
    away = unreal.Vector(away.x, away.y, 0.0)
    away = away.normal() if away.length() > 1.0 else pawn.get_actor_forward_vector()

    def walking():
        pawn.add_movement_input(away, 1.0)
        return (pawn.get_actor_location() - start).length() >= WALK_CM
    yield from _await(walking, 12.0)
    yield from _await(lambda: False, SETTLE_S)
    p.check("client 1 walked clear of the other player",
            (pawn.get_actor_location() - start).length() >= 0.5 * WALK_CM,
            f"{(pawn.get_actor_location() - start).length():.0f} cm")


def _act(p, pawn, wc, other):
    yield from _walk_off(p, pawn, other)
    watchers = ["client 2", "server"]
    done = []
    for name, do in _steps(p, pawn, wc):
        do()
        yield from _await(lambda: False, SETTLE_S)
        mine = _look(p, pawn)
        p.post(f"did {name}", mine)
        done.append(name)
        yield from _await(lambda: all(p.posted(w, f"saw {name}") for w in watchers))
    held = {n: p.posted("client 1", f"did {n}")["pose"] for n in done}
    p.check("client 1's own poses are the items' own: the knife's, the item's",
            held.get("a knife") == POSES["knife"].rsplit("/", 1)[1]
            and held.get("an item (the matches), raised") == POSES["matches"].rsplit("/", 1)[1],
            str({k: v for k, v in held.items() if k.startswith("a")}))
    rifle = held.get("a rifle's ready pose, raised")
    p.check("...and the rifle's is not the pistol's nor the shotgun's",
            rifle not in (held["a pistol, raised"], held["standing"], None),
            f"rifle {rifle}, pistol {held['a pistol, raised']}, shotgun {held['standing']}")
    p.post("steps", done)
    p.post("done")


# ─── the others watch ────────────────────────────────────────────────────────

def _shot(p, other):
    """Turn to the other player's character and save a picture (windowed)."""
    if not SHOTS:
        return
    pc, me = p.controller(), p.pawn()
    to = other.get_actor_location() - me.get_actor_location()
    pc.set_control_rotation(unreal.Rotator(pitch=-8.0, yaw=to.rotator().yaw, roll=0.0))
    unreal.SystemLibrary.execute_console_command(p.world(), "FOV 35", pc)
    yield from _await(lambda: False, 0.7)
    unreal.SystemLibrary.execute_console_command(p.world(), "shot")
    yield from _await(lambda: False, 0.5)
    unreal.SystemLibrary.execute_console_command(p.world(), "FOV 0", pc)


def _watch(p, other, draws):
    """Follow client 1's steps on this machine's copy of its character."""
    names = [n for n, _ in _steps(p, other, p.component(other, WEAPON_COMP_CLASS_PATH))]
    for name in names:
        yield from _await(lambda: p.posted("client 1", f"did {name}")
                          or p.posted("client 1", "steps"))
        there = p.posted("client 1", f"did {name}")
        if not there:
            p.check(f"{p.where} heard that client 1 did: {name}", False, "no post")
            continue

        def verdict():
            here = _look(p, other)
            found = _agrees(here, there, name)
            if draws:
                found.update(_poses(here, there))
            return found
        yield from _await(lambda: all(ok for ok, _ in verdict().values()), SEEN_S)
        for label, (ok, detail) in verdict().items():
            p.check(f"{p.where} sees client 1 {name}: {label}", ok, detail)
        if draws:
            p.note(f"picture: {name}" if SHOTS else f"seen: {name}")
            yield from _shot(p, other)
        p.post(f"saw {name}")
    yield from _await(lambda: p.posted("client 1", "done"))


def _others(p, mine):
    return [a for a in unreal.GameplayStatics.get_all_actors_of_class(p.world(), mine.get_class())
            if a != mine]


def probe_client(p):
    if p.clients != 2:
        p.check("this probe wants two clients", False, f"--clients {p.clients}")
        return
    yield from _await(lambda: p.pawn() and _others(p, p.pawn()))
    me = p.pawn()
    others = _others(p, me) if me else []
    if not p.check(f"{p.where} sees the other player's character", len(others) == 1,
                   f"{len(others)} other character(s) of its class"):
        return
    wc = p.component(me, WEAPON_COMP_CLASS_PATH)
    yield from _await(lambda: p.get(wc, WV.Held) is not None, 10.0)
    p.post("start", _xyz(me))
    yield from _await(lambda: p.posted(f"client {3 - p.client}", "start")
                      and p.posted("server", "start"))
    if p.client == 1:
        yield from _act(p, me, wc, others[0])
    else:
        yield from _watch(p, others[0], draws=True)


def probe_server(p):
    if p.clients != 2:
        return
    yield from _await(lambda: p.posted("client 1", "start"), 3 * WAIT)
    there = p.posted("client 1", "start")
    pawns = [c.get_controlled_pawn() for c in p.players()]
    pawns = [a for a in pawns if a]
    if not p.check("the server has client 1's character", bool(there) and len(pawns) == 2,
                   f"{len(pawns)} pawns"):
        return
    acting = min(pawns, key=lambda a: sum((x - y) ** 2 for x, y in zip(_xyz(a), there)))
    p.post("start")
    yield from _watch(p, acting, draws=False)


# ─── single player ───────────────────────────────────────────────────────────

def probe(p):
    yield lambda: p.pawn() is not None
    pawn = p.pawn()
    wc = p.component(pawn, WEAPON_COMP_CLASS_PATH)
    yield lambda: p.get(wc, WV.Held) is not None
    yield 0.3

    def pose_is_helds(what):
        held = p.get(wc, WV.Held)
        want = _name(p.get(held, "AimPose")) if held else None
        look = _look(p, pawn)
        p.check(f"single player, {what}: the hand's pose is the held item's own",
                look["pose"] == want and want is not None, f"{look['pose']}; Held's {want}")
        p.check("...and what the one machine keeps for other players is the same",
                _name(p.get(wc, LookPose)) == want, str(_name(p.get(wc, LookPose))))
        return look

    # A game's first moments count as just after a shot (NextFireTime is 0).
    # ...and the slot is active until the pose has blended out.
    yield from _await(lambda: _look(p, pawn)["lowered"] and not _look(p, pawn)["playing"], 20.0)
    look = pose_is_helds("the issued shotgun")
    p.check("...a gun at rest is lowered, its pose not playing",
            look["lowered"] and not look["playing"], str(look))
    p.hold(wc, _index(p, wc, "knife"))
    yield 0.5
    look = pose_is_helds("the knife")
    p.check("...the knife is held up in its pose, playing",
            not look["lowered"] and look["playing"]
            and look["pose"] == POSES["knife"].rsplit("/", 1)[1], str(look))
    for stance, low in ((CROUCH, COMBAT.crouch_half_height_cm),
                        (PRONE, COMBAT.prone_half_height_cm), (STAND, None)):
        p.set(wc, STANCE_VAR, stance)
        yield 0.4
        look = _look(p, pawn)
        p.check(f"single player, stance {stance}: the movement component says the same",
                look["moves"] == stance, str(look["moves"]))
        p.check("...and the capsule is that stance's",
                (look["height"] >= STANDING_CM) if low is None
                else abs(look["height"] - low) <= HEIGHT_NEAR_CM, f"{look['height']:.1f} cm")
