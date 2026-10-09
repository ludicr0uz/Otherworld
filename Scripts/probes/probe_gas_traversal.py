"""The moves the Game Animation Sample ships beyond the walk and the run, on
the game's own inputs (task G5): the player crouches, slides out of a sprint
and mantles a block one metre high.

    python3 Scripts/dev/uepy.py --game --probe Scripts/probes/probe_gas_traversal.py

    the legs      with the gun raised (its ready pose plays in a slot named as
                  the sample's own) the motion matching still runs the legs
    the crouch    the crouch key (its stand-in, CrouchForced): the movement
                  component crouches, the motion matching is told Stance =
                  Crouch and picks out of the sample's crouch databases,
                  still and walking; the key again stands it up
    the slide     the crouch key in a sprint: the movement component slides
                  (it coasts with nothing steered, faster than a crouch,
                  slowing), the weapon layers blend the sample's slide loop
                  in, and it ends crouched. The same key at a jog only crouches
    the mantle    the jump key (JumpPressed, the event the key calls: no key
                  can be injected into a headless game) in front of a
                  LevelBlock_Traversable one metre high, spawned here: the
                  sample's component finds it, plays one of its traversal
                  montages, and the player ends standing on the block. With
                  nothing in front the same key jumps

Each is behind its own switch (combat/gas_moves_tuning.py); a switch that is
off is noted and its part skipped.
"""

SYSTEMS = ('animation', 'movement')

import math
import types

import unreal

from combat import gas_moves_tuning as T
from combat.carry_tuning import RAISE_FORCED_VAR
from combat.gas_locomotion_consts import ABP_LOCOMOTION
from combat.gas_traversal import TRAVERSAL_CLASS
from combat.paths import WEAPON_COMP_BP_PATH, WEAPON_COMP_CLASS_PATH
from combat.slot_tuning import MELEE_SLOT
from combat.sprint_tuning import SPRINT_FORCED_VAR
from combat.tuning import COMBAT
from combat.weapon_component.stance import CROUCH_FORCED_VAR

RUNS_ON = ("standalone",)
WRITABLE = [(WEAPON_COMP_BP_PATH, SPRINT_FORCED_VAR), (WEAPON_COMP_BP_PATH, CROUCH_FORCED_VAR),
            (WEAPON_COMP_BP_PATH, RAISE_FORCED_VAR)]

INDEX_WAIT_S = 60.0         # game seconds the search indices may take to load
CLEAR_RUN_CM = 2500.0       # the open ground a sprint and a slide need
BLOCK_HEIGHT_CM = 100.0
BLOCK_AHEAD_CM = 60.0       # from the player's middle to the block's near face: a
                            # standing player's sweep reaches TRACE_NEAR_CM (75)
MOVE = unreal.OtherworldMovementLibrary


def _name(obj):
    return obj.get_name() if obj else "None"


def _clear_yaw(world, pawn):
    """The yaw with the longest open run from where the player stands."""
    here = pawn.get_actor_location() + unreal.Vector(0, 0, 20)
    best = (0.0, 0.0)
    for step in range(24):
        yaw = step * 15.0
        way = unreal.Vector(math.cos(math.radians(yaw)), math.sin(math.radians(yaw)), 0.0)
        hit = unreal.SystemLibrary.line_trace_single(
            world, here, here + way * CLEAR_RUN_CM, unreal.TraceTypeQuery.TRACE_TYPE_QUERY1,
            False, [pawn], unreal.DrawDebugTrace.NONE, True)
        run = hit.to_tuple()[3] if hit else CLEAR_RUN_CM
        if run > best[0]:
            best = (run, yaw)
    return best


def probe(p):
    yield 0.5
    pawn, pc, world = p.pawn(), p.controller(), p.world()
    mesh = pawn.get_editor_property("mesh")
    inst = mesh.get_anim_instance()
    want_class = ABP_LOCOMOTION.rsplit("/", 1)[1] + "_C"
    if inst is None or inst.get_class().get_name() != want_class:
        p.check("the player's mesh runs the motion-matching anim Blueprint", False,
                _name(inst.get_class()) if inst else "no anim instance")
        return
    wc = p.component(pawn, WEAPON_COMP_CLASS_PATH)
    move = pawn.get_component_by_class(unreal.CharacterMovementComponent)
    capsule = pawn.get_component_by_class(unreal.CapsuleComponent)
    layers = p.pose_instance(mesh)
    now = lambda: unreal.GameplayStatics.get_time_seconds(world)
    read = lambda var: inst.get_editor_property(var)
    state = lambda var: str(read(var)).split(".")[-1].split(":")[0].strip("<> ")
    picked = lambda: f"{_name(read('CurrentSelectedAnim'))} {_name(read('CurrentSelectedDatabase'))}"
    speed = lambda: pawn.get_velocity().length()

    t0 = now()
    yield lambda: read("CurrentSelectedAnim") is not None or now() - t0 > INDEX_WAIT_S
    run_cm, yaw = _clear_yaw(world, pawn)
    pc.set_control_rotation(unreal.Rotator(0.0, 0.0, yaw))
    yield 1.0
    home = pawn.get_actor_location()
    p.note(f"facing yaw {yaw:.0f}: {run_cm:.0f} cm of open ground ahead")

    def held(seconds, fwd=0.0, each=None):
        """Steer forward (or not) for a stretch of game time."""
        start = now()
        while now() - start < seconds:
            if fwd:
                pawn.add_movement_input(pawn.get_actor_forward_vector(), fwd)
            yield 0.0
            if each:
                each()

    def back_home():
        pawn.set_actor_location(home, False, True)
        yield from held(1.0)

    r = types.SimpleNamespace(
        p=p, pawn=pawn, world=world, wc=wc, mesh=mesh, inst=inst, move=move,
        capsule=capsule, layers=layers, now=now, state=state, picked=picked, speed=speed,
        held=held, back_home=back_home, yaw=yaw)
    for part in (_legs, _crouch, _slide, _mantle, _vault_hurdle):
        yield from part(r)


def _legs(r):
    """The motion matching runs the legs under a raised gun."""
    p, wc, inst, picked, held, back_home = r.p, r.wc, r.inst, r.picked, r.held, r.back_home
    # The sample's montage slot is in the pose line for traversal's sake, and
    # the gun's ready pose plays in a slot of the same name: with the gun up
    # the legs must still be the motion matching's (gas_traversal_slot.py).
    p.set(wc, RAISE_FORCED_VAR, True)
    yield from held(1.0)
    seen = []
    yield from held(2.0, fwd=1.0, each=lambda: seen.append(picked()))
    p.check("with the gun raised (its ready pose playing in a slot) the motion matching "
            "still picks the run: the pose is the upper body's alone",
            inst.get_current_active_montage() is not None
            and any("Run_Loop" in c for c in seen[len(seen) // 2:]),
            f"{sorted(set(seen[len(seen) // 2:]))[:3]}")
    p.set(wc, RAISE_FORCED_VAR, False)
    yield from back_home()


def _crouch(r):
    """The crouch key: the sample's crouch set, still and walking, and up again."""
    p, pawn, wc, mesh, move, capsule = r.p, r.pawn, r.wc, r.mesh, r.move, r.capsule
    state, picked, speed, held, back_home = r.state, r.picked, r.speed, r.held, r.back_home
    if not T.GAS_CROUCH:
        p.note("GAS_CROUCH is off: the crouch is the weapon layers' clips, not probed here")
        return
    stand_head = mesh.get_socket_location("head").z - pawn.get_actor_location().z
    stand_half = capsule.get_scaled_capsule_half_height()
    p.set(wc, CROUCH_FORCED_VAR, True)
    yield from held(1.5)
    low_head = mesh.get_socket_location("head").z - pawn.get_actor_location().z
    low_half = capsule.get_scaled_capsule_half_height()
    p.check("the crouch key crouches the movement component (stance 1, the capsule "
            f"at {COMBAT.crouch_half_height_cm:g} cm) and spends the probe's press",
            MOVE.get_stance(pawn) == 1 and abs(low_half - COMBAT.crouch_half_height_cm) < 1.0
            and not p.get(wc, CROUCH_FORCED_VAR),
            f"stance {MOVE.get_stance(pawn)}, half height {stand_half:.0f} -> {low_half:.0f}")
    p.check("crouched, still: the motion matching is told Stance = Crouch and picks "
            "a 'Crouch' clip of the sample's",
            state("Stance") == "CROUCH" and "Crouch" in picked(),
            f"{state('Stance')}; {picked()}")
    # The capsule comes down 30 cm with the feet where they were, so the
    # head against the capsule's middle says little: against the ground.
    p.check("...and the head is at least 25 cm nearer the ground than standing",
            (stand_head + stand_half) - (low_head + low_half) > 25.0,
            f"{stand_head + stand_half:.0f} -> {low_head + low_half:.0f} cm over the feet")
    seen = []
    yield from held(2.5, fwd=1.0, each=lambda: seen.append((picked(), speed())))
    walked = [s for s in seen[len(seen) // 2:]]
    p.check("crouched, walking: 'Crouch' clips from the sample's crouch databases, at "
            "the crouch's pace",
            walked and all("Crouch" in c for c, _ in walked)
            and abs(walked[-1][1] - COMBAT.crouch_speed_scale * move.max_walk_speed) < 20.0,
            f"{sorted({c for c, _ in walked})[:3]}, {walked[-1][1]:.0f} cm/s")
    yield from held(0.5)
    p.set(wc, CROUCH_FORCED_VAR, True)
    yield from held(1.5)
    p.check("the key again stands up: stance 0, Stance = Stand, no crouch clip",
            MOVE.get_stance(pawn) == 0 and state("Stance") == "STAND"
            and "Crouch" not in picked(), f"{MOVE.get_stance(pawn)}; {picked()}")
    yield from back_home()


def _slide(r):
    """The crouch key at a jog and in a sprint: a crouch, and a slide."""
    p, pawn, wc, move, capsule = r.p, r.pawn, r.wc, r.move, r.capsule
    layers, now, speed, held, back_home = r.layers, r.now, r.speed, r.held, r.back_home
    if not T.GAS_SLIDE:
        p.note("GAS_SLIDE is off: the crouch key in a sprint does nothing, not probed here")
        return
    yield from held(1.0, fwd=1.0)
    p.set(wc, CROUCH_FORCED_VAR, True)
    yield from held(0.4, fwd=1.0)
    p.check("the crouch key at a jog only crouches: no slide",
            MOVE.get_stance(pawn) == 1 and not MOVE.is_sliding(pawn),
            f"stance {MOVE.get_stance(pawn)}, sliding {MOVE.is_sliding(pawn)}")
    p.set(wc, CROUCH_FORCED_VAR, True)
    yield from held(1.0)
    yield from back_home()

    p.set(wc, SPRINT_FORCED_VAR, True)
    yield from held(1.5, fwd=1.0)
    fast = speed()
    p.set(wc, CROUCH_FORCED_VAR, True)
    # Still steering: a sprint is a sprint only while it is steered ahead.
    pressed_at = now()
    while not MOVE.is_sliding(pawn) and now() - pressed_at < 0.5:
        pawn.add_movement_input(pawn.get_actor_forward_vector(), 1.0)
        yield 0.0
    p.set(wc, SPRINT_FORCED_VAR, False)
    began, track = pawn.get_actor_location(), []
    slid_at = now()

    def sample():
        if MOVE.is_sliding(pawn):
            track.append((now() - slid_at, speed(), layers.get_editor_property(T.POSE_SLIDE),
                          capsule.get_scaled_capsule_half_height()))
    # Nothing is steered: what moves the player now is the slide.
    yield from held(T.SLIDE_SECONDS + 0.6, each=sample)
    went = (pawn.get_actor_location() - began).length()
    crouch_pace = COMBAT.crouch_speed_scale * move.max_walk_speed
    p.check("the crouch key in a sprint slides: the movement component says so, from "
            f"the sprint's speed ({fast:.0f} cm/s)",
            bool(track) and fast > 0.9 * COMBAT.sprint_speed_cms,
            f"{len(track)} sliding frames")
    if track:
        mid = [s for t, s, _w, _h in track if 0.2 < t < 0.5]
        p.check("...it coasts with nothing steered, faster than a crouch walks and "
                "slowing, in the crouch's capsule",
                mid and min(mid) > crouch_pace + 50.0 and track[-1][1] < track[0][1]
                and all(abs(h - COMBAT.crouch_half_height_cm) < 1.0 for *_x, h in track[2:]),
                f"{track[0][1]:.0f} -> {track[-1][1]:.0f} cm/s over {track[-1][0]:.2f} s, "
                f"{went:.0f} cm")
        p.check(f"...for {T.SLIDE_SECONDS:g} s, with the sample's slide loop blended in "
                f"({T.POSE_SLIDE} past 0.9)",
                abs(track[-1][0] - T.SLIDE_SECONDS) < 0.15
                and max(w for _t, _s, w, _h in track) > 0.9,
                f"{track[-1][0]:.2f} s, {T.POSE_SLIDE} up to "
                f"{max(w for _t, _s, w, _h in track):.2f}")
    p.check("...and ends crouched, the slide's pose gone",
            not MOVE.is_sliding(pawn) and MOVE.get_stance(pawn) == 1
            and layers.get_editor_property(T.POSE_SLIDE) < 0.1,
            f"stance {MOVE.get_stance(pawn)}, {T.POSE_SLIDE} "
            f"{layers.get_editor_property(T.POSE_SLIDE):.2f}")
    p.set(wc, CROUCH_FORCED_VAR, True)
    yield from held(1.0)
    yield from back_home()


def _mantle(r):
    """The jump key with nothing in front, and in front of a block a metre high."""
    p, pawn, wc = r.p, r.pawn, r.wc
    inst, move, capsule, now, held = r.inst, r.move, r.capsule, r.now, r.held
    world, yaw = r.world, r.yaw
    if not T.GAS_TRAVERSAL:
        p.note("GAS_TRAVERSAL is off: the jump key jumps, not probed here")
        return
    comp = pawn.get_component_by_class(unreal.load_class(None, TRAVERSAL_CLASS))
    p.check("the player has the sample's traversal component", comp is not None)
    if comp is None:
        return
    def press_jump():
        pawn.call_method(T.JUMP_EVENT)

    # Nothing in front: the key is a jump still.
    press_jump()
    start = now()
    yield lambda: move.is_falling() or now() - start > 1.0
    p.check("the jump key with nothing in front jumps",
            move.is_falling() and not comp.get_editor_property(T.DOING_VAR),
            f"falling {move.is_falling()}")
    yield lambda: not move.is_falling()
    yield from held(1.0)

    stood_at = pawn.get_actor_location()
    block_class = unreal.load_class(None, f"{T.BLOCK_BP}.{T.BLOCK_BP.rsplit('/', 1)[1]}_C")
    feet = pawn.get_actor_location() - unreal.Vector(0, 0, capsule.get_scaled_capsule_half_height())
    ahead = pawn.get_actor_forward_vector()
    block = unreal.OtherworldLoadLibrary.spawn_actor_at(world, block_class, unreal.Transform(
        feet + ahead * 300.0, unreal.Rotator(0.0, 0.0, yaw), unreal.Vector(2.0, 2.0, 1.0)))
    p.check("a LevelBlock_Traversable spawns in front of the player", block is not None)
    if block is None:
        return
    yield 0.2
    origin, extent = block.get_actor_bounds(True)
    # Onto the ground, its near face BLOCK_AHEAD_CM ahead, whatever its pivot
    # is. It is turned to face the player, so its depth is not the box's that
    # the bounds are: it is the mesh's own, along its X.
    shape = block.get_component_by_class(unreal.StaticMeshComponent)
    low, high = shape.get_local_bounds()
    depth = (high.x - low.x) * shape.get_world_scale().x
    block.set_actor_location(
        block.get_actor_location() + (feet + ahead * (BLOCK_AHEAD_CM + depth / 2.0))
        - unreal.Vector(origin.x, origin.y, origin.z - extent.z), False, True)
    yield 0.2
    origin, extent = block.get_actor_bounds(True)
    top = origin.z + extent.z
    p.check(f"...{BLOCK_HEIGHT_CM:g} cm high, its top a metre over the player's feet",
            abs(2.0 * extent.z - BLOCK_HEIGHT_CM) < 2.0 and abs(top - feet.z - BLOCK_HEIGHT_CM) < 5.0,
            f"{2 * extent.x:.0f} x {2 * extent.y:.0f} x {2 * extent.z:.0f} cm, top "
            f"{top - feet.z:.0f} cm up")

    press_jump()
    seen = dict(doing=False, montage=set(), flying=False, fell=False)
    start = now()

    def watch():
        seen["doing"] |= bool(comp.get_editor_property(T.DOING_VAR))
        montage = inst.get_current_active_montage()
        if montage:
            seen["montage"].add(montage.get_name())
        seen["flying"] |= move.movement_mode == unreal.MovementMode.MOVE_FLYING
        seen["fell"] |= move.is_falling() and not seen["doing"]
    yield from held(0.5, each=watch)
    p.check("the jump key in front of the block starts a traversal, not a jump: the "
            "component is doing one and a traversal montage of the sample's plays",
            seen["doing"] and any("Traversal" in m for m in seen["montage"]) and not seen["fell"],
            f"doing {seen['doing']}, {sorted(seen['montage'])}, jumped {seen['fell']}")
    while (comp.get_editor_property(T.DOING_VAR) or move.movement_mode
           != unreal.MovementMode.MOVE_WALKING) and now() - start < 8.0:
        yield from held(0.1, each=watch)
    yield from held(0.5)
    at = pawn.get_actor_location()
    stood = at.z - capsule.get_scaled_capsule_half_height()
    p.check("...in the flying mode the component puts the movement in while it plays",
            seen["flying"], f"flying {seen['flying']}")
    p.check("the player ends standing on the block: walking again, the feet at its top, "
            "over it",
            move.movement_mode == unreal.MovementMode.MOVE_WALKING
            and not comp.get_editor_property(T.DOING_VAR) and abs(stood - top) < 6.0
            and abs(at.x - origin.x) < extent.x and abs(at.y - origin.y) < extent.y,
            f"feet {stood - feet.z:.0f} cm up after {now() - start:.1f} s, "
            f"{sorted(seen['montage'])}")

    # Again with the knife out: its hold pose is a looping montage, and a
    # traversal's montage is the whole body's. The pose must not cut the climb
    # short, and must be back in the hand after it.
    pawn.set_actor_location(stood_at, False, True)
    p.ask_slot(wc, MELEE_SLOT)
    yield from held(1.5)
    posed = inst.get_current_active_montage()
    press_jump()
    seen = dict(doing=False, montage=set(), flying=False, fell=False)
    start = now()
    yield from held(0.5, each=watch)
    while (comp.get_editor_property(T.DOING_VAR) or move.movement_mode
           != unreal.MovementMode.MOVE_WALKING) and now() - start < 8.0:
        yield from held(0.1, each=watch)
    took = now() - start
    yield from held(1.0)
    at = pawn.get_actor_location()
    stood = at.z - capsule.get_scaled_capsule_half_height()
    after = inst.get_current_active_montage()
    p.check("with the knife out (a hold pose playing) the mantle plays through all the "
            "same, and the hold pose is back in the hand after it",
            posed is not None and seen["doing"] and abs(stood - top) < 6.0 and took > 1.0
            and any("Traversal" in m for m in seen["montage"])
            and after is not None and "Traversal" not in after.get_name(),
            f"before {_name(posed)}; {sorted(seen['montage'])}, feet {stood - feet.z:.0f} cm "
            f"up after {took:.1f} s; then {_name(after)}")
    block.destroy_actor()


def _vault_hurdle(r):
    """A thin block, a metre high and half that, is hurdled: the player ends on
    the far side of each, the sample's own montage played. The sample's chooser
    gives a thin block a hurdle and a deep one (60 cm) a mantle; no block of
    this one-cube mesh got a vault out of it, standing or on the run."""
    p, pawn, inst, move, capsule, now, held = r.p, r.pawn, r.inst, r.move, r.capsule, r.now, r.held
    if not T.GAS_TRAVERSAL:
        return
    comp = pawn.get_component_by_class(unreal.load_class(None, TRAVERSAL_CLASS))
    block_class = unreal.load_class(None, f"{T.BLOCK_BP}.{T.BLOCK_BP.rsplit('/', 1)[1]}_C")
    for word, scale in (("hurdle a metre", unreal.Vector(0.3, 3.0, 1.0)),
                        ("hurdle half a metre", unreal.Vector(0.3, 3.0, 0.5))):
        yield from r.back_home()
        feet = pawn.get_actor_location() - unreal.Vector(0, 0, capsule.get_scaled_capsule_half_height())
        ahead = pawn.get_actor_forward_vector()
        block = unreal.OtherworldLoadLibrary.spawn_actor_at(r.world, block_class, unreal.Transform(
            feet + ahead * 300.0, unreal.Rotator(0.0, 0.0, r.yaw), scale))
        p.check(f"a thin block to {word} spawns", block is not None)
        if block is None:
            continue
        block.set_actor_scale3d(scale)
        yield 0.2
        origin, extent = block.get_actor_bounds(True)
        shape = block.get_component_by_class(unreal.StaticMeshComponent)
        low, high = shape.get_local_bounds()
        depth = (high.x - low.x) * shape.get_world_scale().x
        block.set_actor_location(
            block.get_actor_location() + (feet + ahead * (BLOCK_AHEAD_CM + depth / 2.0))
            - unreal.Vector(origin.x, origin.y, origin.z - extent.z), False, True)
        yield 0.2
        origin, extent = block.get_actor_bounds(True)
        p.note(f"{word} block {2 * extent.x:.0f} x {2 * extent.y:.0f} x {2 * extent.z:.0f} cm")
        before = pawn.get_actor_location()
        seen = set()

        def watch():
            montage = inst.get_current_active_montage()
            if montage:
                seen.add(montage.get_name())
        pawn.call_method(T.JUMP_EVENT)
        start = now()
        yield from held(0.5, each=watch)
        while (comp.get_editor_property(T.DOING_VAR) or move.movement_mode
               != unreal.MovementMode.MOVE_WALKING) and now() - start < 8.0:
            yield from held(0.1, each=watch)
        yield from held(0.5)
        went = (pawn.get_actor_location() - before).dot(ahead)
        p.check(f"the jump key in front of a thin block plays the sample's hurdle ({word}) and the "
                "player ends past it, on the ground",
                any("Hurdle" in m for m in seen) and went > BLOCK_AHEAD_CM + depth,
                f"{sorted(seen)}, {went:.0f} cm ahead, feet "
                f"{pawn.get_actor_location().z - capsule.get_scaled_capsule_half_height() - feet.z:.0f} up")
        block.destroy_actor()
