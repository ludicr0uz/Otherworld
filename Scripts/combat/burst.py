"""The burst solver BP_BloodSplash and BP_BulletImpact share: small pieces thrown
off a surface under drag and gravity, as a short-lived actor (build_burst).

blood.py and bullet_impact.py own what is thrown (the layout, the materials,
the numbers); this owns how it flies, so the two cannot drift apart.
"""

import math
from collections import namedtuple

import unreal

from combat.log import _log
from uebp.graph import (
    BEL, BGE, _add_component, _assets, _component_object, _connect, _create_blueprint,
    _drop_components, _events, _loose_pin, _must_load, _node, _pin, _root_handle, _rot, _set,
    _vec, out, then)
from uebp.layout import arrange
from uebp.nodes.actor import (
    FN_COMP_REL_XFORM, FN_COMP_SET_REL_LOC, FN_COMP_SET_SCALE, FN_GET_COMPONENTS,
    FN_GET_TRANSFORM, FN_LIFESPAN)
from uebp.nodes.array import FN_ARR_ADD, FN_ARR_GET
from uebp.nodes.math import (
    FN_ADD_FF, FN_ADD_VV, FN_BREAK_TRANSFORM, FN_BREAK_VECTOR, FN_CLAMP, FN_DIV_FF, FN_EXP,
    FN_INV_XFORM_DIR, FN_MUL_FF, FN_MUL_VF, FN_SUB_FF)
from uebp.nodes.palette import MACRO_FOR_EACH
from uebp.vars import declare
from combat import burst_vars as BV


# The velocity of each piece is baked into its relative *location*, divided by
# this. Two things fall out of that and both matter:
#
#   * there is no parallel table to keep in step with the components -- the
#     piece carries its own velocity, so no ordering assumption about what
#     GetComponentsByClass hands back can ever be wrong;
#   * the frame the actor spawns, before BeginPlay has run, the components are
#     still sitting where the builder left them. At 100 that is a 1-9 cm clump
#     around the hit, which is a hit. Store the velocity directly and the
#     first frame of every hit is a nine-metre sphere of pieces.
#
# 100 rather than any other number because cm/s over 100 is m/s, so the baked
# location reads as the piece's launch speed in metres per second and there
# is nothing to decode by hand. The graph converts it back where it scales the
# drag term, not per piece.
BURST_VELOCITY_ENCODE = 100.0
# The components are Blob0..N whatever is thrown: the name is the solver's.
BURST_PIECE_PREFIX = "Blob"

# One thrown piece. ``velocity`` is its launch velocity over
# BURST_VELOCITY_ENCODE, +X being the actor's forward (the hit normal);
# ``scale`` is uniform; ``turn`` is an optional (pitch, yaw, roll) it is built
# at and keeps, for pieces that are not spheres.
Piece = namedtuple("Piece", "velocity scale mesh material turn", defaults=(None,))


def throw(rng, cone_deg, speed_lo, speed_hi, scale_lo, scale_hi, bias):
    """One piece's (x, y, z, scale), drawn from ``rng``: a launch velocity
    inside a cone around +X, over BURST_VELOCITY_ENCODE, and a size."""
    # sqrt() on the polar draw is what spreads samples evenly over the cap
    # instead of piling them on the axis -- a uniform draw in theta gives a
    # needle with a halo, which is not what a spray looks like.
    theta = math.radians(cone_deg) * math.sqrt(rng.random())
    phi = rng.uniform(0.0, math.tau)
    # Biased toward the top of the range: most of the spray is fast and a
    # few pieces lag badly behind it. Drawn uniformly, every piece ends
    # the frame at much the same radius and the burst reads as one
    # expanding shell -- the "everything moves at one speed" tell.
    speed = speed_lo + (speed_hi - speed_lo) * (rng.random() ** bias)
    direction = (math.cos(theta),
                 math.sin(theta) * math.cos(phi),
                 math.sin(theta) * math.sin(phi))
    return tuple(round(d * speed / BURST_VELOCITY_ENCODE, 5)
                 for d in direction) + (round(rng.uniform(scale_lo, scale_hi), 5),)


def build_burst(path, pieces, *, lifetime, fade_tail, drag, gravity, note,
                rebuild=True):
    """An actor of small pieces thrown off a surface under drag and gravity.

    **Not Niagara, and the reason is not preference.** UE 5.8 exposes
    NiagaraSystem to Python with no emitter handles, no exposed parameters and
    no renderer access -- `get_editor_property("emitter_handles")` does not
    resolve -- and the one API that *can* build an emitter stack,
    UNiagaraExternalSystemEditorUtilities (AddEmitter / AddModule /
    SetStackInputData, the thing the editor's own external-edit tooling drives),
    is plain C++ statics with no UFUNCTION on them, so none of it reaches
    Python. Duplicating an engine template such as
    /Niagara/DefaultAssets/Templates/Systems/DirectionalBurst gets an asset that
    cannot then be retuned. Cascade is worse: the runtime classes survive in 5.8
    but the editor module and every ParticleModule* reflection type are gone.
    A system nobody can rebuild from a script is not allowed here, so the
    pieces are components and the solver is in the graph.

    What each piece does is the closed-form solution of dv/dt = g - k*v,
    which is a falling drop with linear air drag:

        A(t)  = (1 - e^(-k t)) / k
        B(t)  = (t - A) / k
        local = Velocity * A + Fall * B

    -- one pair of scalars computed once per frame for the whole burst, and one
    multiply-add per piece. Every piece has its own launch velocity, so they
    separate as they fly.

    Scale is held flat and then cut to nothing over the last ``fade_tail`` of
    the life, so the burst is a punctuation mark rather than something that
    grows. ``note`` is the graph comment: what this burst is, in its owner's
    words.
    """
    eas = _assets()
    name = path.rsplit("/", 1)[1]
    bp = _create_blueprint(path, unreal.Actor)
    names = {f"{BURST_PIECE_PREFIX}{i}" for i in range(max(len(pieces), 24))}
    _drop_components(bp, {"Burst"} | names)
    root = _add_component(bp, _root_handle(bp), unreal.SceneComponent, "Burst")
    for i, piece in enumerate(pieces):
        handle = _add_component(bp, root, unreal.StaticMeshComponent,
                                f"{BURST_PIECE_PREFIX}{i}")
        obj = _component_object(handle)
        obj.set_editor_property("static_mesh", _must_load(piece.mesh))
        obj.set_editor_property("relative_location", unreal.Vector(*piece.velocity))
        obj.set_editor_property("relative_scale3d",
                                unreal.Vector(piece.scale, piece.scale, piece.scale))
        if piece.turn is not None:
            obj.set_editor_property("relative_rotation", _rot(*piece.turn))
        obj.set_editor_property("override_materials", [_must_load(piece.material)])
        # A piece is 1-3 cm and gone in about half a second; it has no
        # business in the shadow pass, and 19 of them per pellet times eight
        # pellets is 152 shadow casters for a single shotgun blast.
        obj.set_editor_property("cast_shadow", False)
        try:
            obj.set_collision_profile_name("NoCollision")
        except Exception as exc:                                  # noqa: BLE001
            _log(f"  note: could not set NoCollision on "
                 f"{BURST_PIECE_PREFIX}{i}: {exc}")

    ed = BGE.get_graph_editor_by_name(bp, "EventGraph")
    tick, begin = _events(ed, rebuild)
    declare(ed, BV.TABLE)

    # --- BeginPlay: read each droplet's velocity back off the component ------
    # Pure, not impure: UHT promotes a const BlueprintCallable to BlueprintPure,
    # so this node has no exec pin to thread and the loop hangs off BeginPlay
    # directly. The same is true of GetRelativeTransform below.
    found = _node(ed, FN_GET_COMPONENTS)
    _pin(found, "ComponentClass").set_pin_value("/Script/Engine.StaticMeshComponent")

    gather = ed.add_macro_node(MACRO_FOR_EACH)
    if not gather:
        raise RuntimeError("could not create the ForEachLoop macro node")
    gather
    _connect(out(found), _loose_pin(gather, "Array"))
    _connect(then(begin), _loose_pin(gather, "Exec"))
    blob = _loose_pin(gather, "ArrayElement", is_input=False)

    rel = _node(ed, FN_COMP_REL_XFORM)
    _connect(blob, _pin(rel, "self"))
    parts = _node(ed, FN_BREAK_TRANSFORM)
    _connect(out(rel), _pin(parts, "InTransform"))

    keep_blob = _node(ed, FN_ARR_ADD)
    _connect(out(ed.add_get_member_variable_node(BV.Blobs), BV.Blobs), _pin(keep_blob, "TargetArray"))
    _connect(blob, _pin(keep_blob, "NewItem"))
    _connect(_loose_pin(gather, "LoopBody", is_input=False), _pin(keep_blob, "execute"))

    keep_vel = _node(ed, FN_ARR_ADD)
    _connect(out(ed.add_get_member_variable_node(BV.Velocity), BV.Velocity),
             _pin(keep_vel, "TargetArray"))
    _connect(_loose_pin(parts, "Location", is_input=False), _pin(keep_vel, "NewItem"))
    _connect(then(keep_blob), _pin(keep_vel, "execute"))

    # Uniform by construction, so X is the whole story.
    axes = _node(ed, FN_BREAK_VECTOR)
    _connect(_loose_pin(parts, "Scale", is_input=False), _pin(axes, "InVec"))
    keep_size = _node(ed, FN_ARR_ADD)
    _connect(out(ed.add_get_member_variable_node(BV.Size), BV.Size), _pin(keep_size, "TargetArray"))
    _connect(out(axes, "X"), _pin(keep_size, "NewItem"))
    _connect(then(keep_vel), _pin(keep_size, "execute"))

    here = _node(ed, FN_GET_TRANSFORM)
    local_g = _node(ed, FN_INV_XFORM_DIR)
    _connect(out(here), _pin(local_g, "T"))
    _connect(_vec(ed, 0.0, 0.0, -gravity), _pin(local_g, "Direction"))
    pin_fall = ed.add_set_member_variable_node(BV.Fall)
    _connect(out(local_g), _pin(pin_fall, BV.Fall))
    _connect(_loose_pin(gather, "Completed", is_input=False), _pin(pin_fall, "execute"))

    life = _node(ed, FN_LIFESPAN)
    _set(life, "InLifespan", lifetime)
    _connect(then(pin_fall), _pin(life, "execute"))

    # --- Tick: two scalars for the whole burst, then one pass over it --------
    age_get = ed.add_get_member_variable_node(BV.Age)
    add = _node(ed, FN_ADD_FF)
    _connect(out(age_get, BV.Age), _pin(add, "A"))
    _connect(out(tick, "DeltaSeconds"), _pin(add, "B"))
    age_set = ed.add_set_member_variable_node(BV.Age)
    _connect(out(add), _pin(age_set, BV.Age))
    _connect(then(tick), _pin(age_set, "execute"))
    # Read the *stored* age from here on. The add is pure, so every re-read of
    # its output would recompute it -- harmless while the inputs hold still, but
    # the stored value is the one the next frame accumulates from, and the two
    # should not be allowed to drift apart.
    age = ed.add_get_member_variable_node(BV.Age)
    age_out = out(age, BV.Age)

    # A = (1 - e^(-k t)) / k, written as (e^(-k t) - 1) / -k. Algebraically the
    # same; the difference is that every constant then lands on a B pin, and
    # the A pin of these math nodes will not hold a literal -- set_pin_value
    # reports success and the pin reads back empty, which compiles as a zero.
    decay = _node(ed, FN_MUL_FF)
    _connect(age_out, _pin(decay, "A"))
    _set(decay, "B", -drag)
    gone_frac = _node(ed, FN_EXP)
    _connect(out(decay), _pin(gone_frac, "A"))
    spent = _node(ed, FN_SUB_FF)
    _connect(out(gone_frac), _pin(spent, "A"))
    _set(spent, "B", 1.0)
    a_term = _node(ed, FN_DIV_FF)
    _connect(out(spent), _pin(a_term, "A"))
    _set(a_term, "B", -drag)
    a_out = out(a_term)
    # A in centimetres, for the velocities stored in metres per second. Done
    # once here rather than per droplet, and not on the Multiply_VectorFloat
    # itself -- that node's float pin rejects a literal default, reading back
    # empty whatever is written to it.
    a_cm = _node(ed, FN_MUL_FF)
    _connect(a_out, _pin(a_cm, "A"))
    _set(a_cm, "B", BURST_VELOCITY_ENCODE)
    a_cm_out = out(a_cm)

    # B = (t - A) / k
    lag = _node(ed, FN_SUB_FF)
    _connect(age_out, _pin(lag, "A"))
    _connect(a_out, _pin(lag, "B"))
    b_term = _node(ed, FN_DIV_FF)
    _connect(out(lag), _pin(b_term, "A"))
    _set(b_term, "B", drag)
    b_out = out(b_term)

    # fade = clamp((lifetime - age) / tail, 0, 1): flat, then a hard cut. Both
    # signs flipped for the same B-pin reason as the A term above.
    left = _node(ed, FN_SUB_FF)
    _connect(age_out, _pin(left, "A"))
    _set(left, "B", lifetime)
    tail = _node(ed, FN_DIV_FF)
    _connect(out(left), _pin(tail, "A"))
    _set(tail, "B", -fade_tail)
    fade = _node(ed, FN_CLAMP)
    _connect(out(tail), _pin(fade, "Value"))
    _set(fade, "Min", 0.0)
    _set(fade, "Max", 1.0)
    fade_out = out(fade)

    blobs_get = ed.add_get_member_variable_node(BV.Blobs)
    fly = ed.add_macro_node(MACRO_FOR_EACH)
    if not fly:
        raise RuntimeError("could not create the ForEachLoop macro node")
    fly
    _connect(out(blobs_get, BV.Blobs), _loose_pin(fly, "Array"))
    _connect(then(age_set), _loose_pin(fly, "Exec"))
    each = _loose_pin(fly, "ArrayElement", is_input=False)
    index = _loose_pin(fly, "ArrayIndex", is_input=False)

    vel_arr = ed.add_get_member_variable_node(BV.Velocity)
    vel = _node(ed, FN_ARR_GET)
    _connect(out(vel_arr, BV.Velocity), _pin(vel, "TargetArray"))
    _connect(index, _pin(vel, "Index"))
    thrown = _node(ed, FN_MUL_VF)
    _connect(out(vel, "Item"), _pin(thrown, "A"))
    _connect(a_cm_out, _pin(thrown, "B"))

    fall_get = ed.add_get_member_variable_node(BV.Fall)
    dropped = _node(ed, FN_MUL_VF)
    _connect(out(fall_get, BV.Fall), _pin(dropped, "A"))
    _connect(b_out, _pin(dropped, "B"))

    offset = _node(ed, FN_ADD_VV)
    _connect(out(thrown), _pin(offset, "A"))
    _connect(out(dropped), _pin(offset, "B"))

    put = _node(ed, FN_COMP_SET_REL_LOC)
    _connect(each, _pin(put, "self"))
    _connect(out(offset), _pin(put, "NewLocation"))
    # No sweep: the droplets have no collision and the spray is meant to pass
    # through the surface it came off, not to be stopped by it.
    _set(put, "bSweep", False)
    _set(put, "bTeleport", True)
    _connect(_loose_pin(fly, "LoopBody", is_input=False), _pin(put, "execute"))

    size_arr = ed.add_get_member_variable_node(BV.Size)
    born = _node(ed, FN_ARR_GET)
    _connect(out(size_arr, BV.Size), _pin(born, "TargetArray"))
    _connect(index, _pin(born, "Index"))
    now_size = _node(ed, FN_MUL_FF)
    _connect(out(born, "Item"), _pin(now_size, "A"))
    _connect(fade_out, _pin(now_size, "B"))
    size_v = _node(ed, FN_MUL_VF)
    _connect(_vec(ed, 1.0, 1.0, 1.0), _pin(size_v, "A"))
    _connect(out(now_size), _pin(size_v, "B"))
    shrink = _node(ed, FN_COMP_SET_SCALE)
    _connect(each, _pin(shrink, "self"))
    _connect(out(size_v), _pin(shrink, "NewScale3D"))
    _connect(then(put), _pin(shrink, "execute"))

    ed.add_comment_to_nodes(
        note,
        [found, gather, rel, parts, keep_blob, keep_vel, axes, keep_size,
         here, local_g, pin_fall, life, age_get, add, age_set, age, decay,
         gone_frac, spent, a_term, a_cm, lag, b_term, left, tail, fade,
         blobs_get, fly,
         vel_arr, vel, thrown, fall_get, dropped, offset, put, size_arr, born,
         now_size, size_v, shrink])


    arrange(ed)
    if not BEL.compile_blueprint(bp):
        raise RuntimeError(f"{name} failed to compile")
    eas.save_loaded_asset(bp)
    _log(f"built {path} ({len(pieces)} pieces, {lifetime}s, drag {drag}, "
         f"gravity {gravity:.0f}, thrown along the hit normal)")
    return bp
