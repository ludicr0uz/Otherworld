"""BP_BloodSplash: the droplet and mist layout (seeded, reproducible) and the
short-lived actor spawned at each impact.
"""

import math
import random

import unreal

from combat.graph import (
    BEL, BGE, _add_component, _assets, _at, _component_object, _connect,
    _create_blueprint, _declare, _drop_components, _events, _float_type, _log,
    _loose_pin, _node, _pin, _root_handle, _set, _struct_type, _vec,
)
from combat.nodes import (
    FN_ADD_FF, FN_ADD_VV, FN_ARR_ADD, FN_ARR_GET, FN_BREAK_TRANSFORM,
    FN_BREAK_VECTOR, FN_CLAMP, FN_COMP_REL_XFORM, FN_COMP_SET_REL_LOC,
    FN_COMP_SET_SCALE, FN_DIV_FF, FN_EXP, FN_GET_COMPONENTS, FN_GET_TRANSFORM,
    FN_INV_XFORM_DIR, FN_LIFESPAN, FN_MUL_FF, FN_MUL_VF, FN_SUB_FF,
    MACRO_FOR_EACH,
)
from combat.paths import BLOOD_BP_PATH, MAT_BLOOD, SPHERE


# ─── BP_BloodSplash ──────────────────────────────────────────────────────────

BLOOD_SEED = 7             # laid out once, at build time, so it is reproducible
BLOOD_DROPLETS = 14        # the fast spray
BLOOD_MIST = 5             # fine, slow, near the wound: what is left hanging
BLOOD_CONE_DEG = 34.0      # spray half-angle around the surface normal
BLOOD_MIST_CONE_DEG = 72.0 # the haze is not directional in the way the spray is
BLOOD_LIFETIME = 0.45      # punctuation, not a fountain
BLOOD_FADE_TAIL = 0.14     # the last of the lifetime, spent shrinking to nothing
BLOOD_SPEED_MIN = 140.0    # cm/s -- the laggards
BLOOD_SPEED_MAX = 900.0    # cm/s -- the leading edge of the spray
BLOOD_MIST_SPEED_MIN = 25.0
BLOOD_MIST_SPEED_MAX = 90.0
BLOOD_DRAG = 3.6           # 1/s. Air drag on a 2 mm droplet, near enough
BLOOD_GRAVITY = 980.0      # cm/s^2, real gravity and not a stylised fraction
BLOOD_DROP_SCALE = (0.010, 0.030)   # 1-3 cm droplets off a 100 cm sphere
BLOOD_MIST_SCALE = (0.005, 0.011)   # 0.5-1.1 cm
# The velocity of each droplet is baked into its relative *location*, divided by
# this. Two things fall out of that and both matter:
#
#   * there is no parallel table to keep in step with the components -- the
#     droplet carries its own velocity, so no ordering assumption about what
#     GetComponentsByClass hands back can ever be wrong;
#   * the frame the actor spawns, before BeginPlay has run, the components are
#     still sitting where the builder left them. At 100 that is a 1-9 cm clump
#     around the wound, which is a wound. Store the velocity directly and the
#     first frame of every hit is a nine-metre sphere of blood.
#
# 100 rather than any other number because cm/s over 100 is m/s, so the baked
# location reads as the droplet's launch speed in metres per second and there
# is nothing to decode by hand. The graph converts it back where it scales the
# drag term, not per droplet.
BLOOD_VELOCITY_ENCODE = 100.0
# Damage the spray is sized against. Shotgun pellets are 18 each and there are
# eight of them; the sniper is one large number. Clamped either side so no
# weapon can produce either a mist or a fire hose.
BLOOD_REFERENCE_DAMAGE = 24.0
BLOOD_SCALE_MIN = 0.65
BLOOD_SCALE_MAX = 1.60


def _blood_blobs():
    """A seeded spray of droplet velocities, thrown back along +X.

    +X is the actor's forward, and _author_impact spawns the splash rotated so
    that forward *is* the surface normal of whatever the pellet hit. So the
    spray comes out of the wound rather than out of an arbitrary world axis,
    and a shot to the chest and a shot to the back throw blood opposite ways.

    Each tuple is (x, y, z, scale) where x/y/z is the droplet's launch velocity
    over BLOOD_VELOCITY_ENCODE -- see that constant for why the velocity lives
    in the location.

    Seeded rather than authored by hand: the shape wanted here is "irregular",
    which a person writing tuples produces badly and a seed produces for free --
    and a fixed seed keeps it reproducible, so the verifier can recompute the
    same layout and compare it against the saved components.
    """
    rng = random.Random(BLOOD_SEED)
    blobs = []

    def shoot(cone_deg, speed_lo, speed_hi, scale_lo, scale_hi, bias):
        # sqrt() on the polar draw is what spreads samples evenly over the cap
        # instead of piling them on the axis -- a uniform draw in theta gives a
        # needle with a halo, which is not what a spray looks like.
        theta = math.radians(cone_deg) * math.sqrt(rng.random())
        phi = rng.uniform(0.0, math.tau)
        # Biased toward the top of the range: most of the spray is fast and a
        # few droplets lag badly behind it. Drawn uniformly, every droplet ends
        # the frame at much the same radius and the burst reads as one
        # expanding shell -- the "everything moves at one speed" tell.
        speed = speed_lo + (speed_hi - speed_lo) * (rng.random() ** bias)
        direction = (math.cos(theta),
                     math.sin(theta) * math.cos(phi),
                     math.sin(theta) * math.sin(phi))
        return tuple(round(d * speed / BLOOD_VELOCITY_ENCODE, 5)
                     for d in direction) + (round(rng.uniform(scale_lo, scale_hi), 5),)

    for _ in range(BLOOD_DROPLETS):
        blobs.append(shoot(BLOOD_CONE_DEG, BLOOD_SPEED_MIN, BLOOD_SPEED_MAX,
                           *BLOOD_DROP_SCALE, bias=0.5))
    for _ in range(BLOOD_MIST):
        blobs.append(shoot(BLOOD_MIST_CONE_DEG, BLOOD_MIST_SPEED_MIN,
                           BLOOD_MIST_SPEED_MAX, *BLOOD_MIST_SCALE, bias=1.0))
    return tuple(blobs)


BLOOD_BLOBS = _blood_blobs()


def build_blood_splash(rebuild=True):
    """Small dark droplets thrown out of the wound under drag and real gravity.

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
    droplets are components and the solver is in the graph.

    What each droplet does is the closed-form solution of dv/dt = g - k*v,
    which is a falling drop with linear air drag:

        A(t)  = (1 - e^(-k t)) / k
        B(t)  = (t - A) / k
        local = Velocity * A + Fall * B

    -- one pair of scalars computed once per frame for the whole burst, and one
    multiply-add per droplet. Every droplet has its own launch velocity, so they
    separate as they fly: that separation is most of what the old version was
    missing. It threw ten spheres as one rigid cone at a single speed and swelled
    them on a sine to 35 cm across, which is a cartoon for three separate
    reasons -- one speed, one shape, and blood does not inflate.

    Scale is held flat and then cut to nothing over the last BLOOD_FADE_TAIL of
    the life, so the burst is a punctuation mark rather than something that
    grows.
    """
    eas = _assets()
    bp = _create_blueprint(BLOOD_BP_PATH, unreal.Actor)
    names = {f"Blob{i}" for i in range(max(len(BLOOD_BLOBS), 24))}
    _drop_components(bp, {"Burst"} | names)
    root = _add_component(bp, _root_handle(bp), unreal.SceneComponent, "Burst")
    for i, (x, y, z, scale) in enumerate(BLOOD_BLOBS):
        handle = _add_component(bp, root, unreal.StaticMeshComponent, f"Blob{i}")
        obj = _component_object(handle)
        obj.set_editor_property("static_mesh", eas.load_asset(SPHERE))
        obj.set_editor_property("relative_location", unreal.Vector(x, y, z))
        obj.set_editor_property("relative_scale3d", unreal.Vector(scale, scale, scale))
        obj.set_editor_property("override_materials", [eas.load_asset(MAT_BLOOD)])
        # A droplet is 1-3 cm and gone in under half a second; it has no
        # business in the shadow pass, and 19 of them per pellet times eight
        # pellets is 152 shadow casters for a single shotgun blast.
        obj.set_editor_property("cast_shadow", False)
        try:
            obj.set_collision_profile_name("NoCollision")
        except Exception as exc:                                  # noqa: BLE001
            _log(f"  note: could not set NoCollision on Blob{i}: {exc}")

    ed = BGE.get_graph_editor_by_name(bp, "EventGraph")
    tick, begin = _events(ed, rebuild)
    _declare(ed, "Age", _float_type())
    _declare(ed, "Blobs", BEL.get_array_type(
        BEL.get_object_reference_type(unreal.StaticMeshComponent.static_class())))
    # Launch velocity and untouched size, one entry per component, filled in the
    # same loop that fills Blobs -- so the three arrays are in step by
    # construction and not by an assumption about component ordering.
    _declare(ed, "Velocity", BEL.get_array_type(
        _struct_type(unreal.Vector.static_struct())))
    _declare(ed, "Size", BEL.get_array_type(_float_type()))
    # Gravity, rotated into the actor's own frame once. The actor is spawned
    # facing the hit normal and never turns, so this cannot go stale, and doing
    # it here keeps a transform inverse out of the per-frame path.
    _declare(ed, "Fall", _struct_type(unreal.Vector.static_struct()))

    # --- BeginPlay: read each droplet's velocity back off the component ------
    # Pure, not impure: UHT promotes a const BlueprintCallable to BlueprintPure,
    # so this node has no exec pin to thread and the loop hangs off BeginPlay
    # directly. The same is true of GetRelativeTransform below.
    found = _at(_node(ed, FN_GET_COMPONENTS), 320, -900)
    _pin(found, "ComponentClass").set_pin_value("/Script/Engine.StaticMeshComponent")

    gather = ed.add_macro_node(MACRO_FOR_EACH)
    if not gather:
        raise RuntimeError("could not create the ForEachLoop macro node")
    _at(gather, 620, -900)
    _connect(_pin(found, "ReturnValue", is_input=False), _loose_pin(gather, "Array"))
    _connect(BEL.find_then_pin(begin), _loose_pin(gather, "Exec"))
    blob = _loose_pin(gather, "ArrayElement", is_input=False)

    rel = _at(_node(ed, FN_COMP_REL_XFORM), 920, -900)
    _connect(blob, _pin(rel, "self"))
    parts = _at(_node(ed, FN_BREAK_TRANSFORM), 1180, -640)
    _connect(_pin(rel, "ReturnValue", is_input=False), _pin(parts, "InTransform"))

    keep_blob = _at(_node(ed, FN_ARR_ADD), 1180, -900)
    _connect(_pin(_at(ed.add_get_member_variable_node("Blobs"), 1180, -760),
                  "Blobs", is_input=False),
             _pin(keep_blob, "TargetArray"))
    _connect(blob, _pin(keep_blob, "NewItem"))
    _connect(_loose_pin(gather, "LoopBody", is_input=False), _pin(keep_blob, "execute"))

    keep_vel = _at(_node(ed, FN_ARR_ADD), 1700, -900)
    _connect(_pin(_at(ed.add_get_member_variable_node("Velocity"), 1440, -760),
                  "Velocity", is_input=False),
             _pin(keep_vel, "TargetArray"))
    _connect(_loose_pin(parts, "Location", is_input=False), _pin(keep_vel, "NewItem"))
    _connect(BEL.find_then_pin(keep_blob), _pin(keep_vel, "execute"))

    # Uniform by construction, so X is the whole story.
    axes = _at(_node(ed, FN_BREAK_VECTOR), 1700, -560)
    _connect(_loose_pin(parts, "Scale", is_input=False), _pin(axes, "InVec"))
    keep_size = _at(_node(ed, FN_ARR_ADD), 1960, -900)
    _connect(_pin(_at(ed.add_get_member_variable_node("Size"), 1960, -760),
                  "Size", is_input=False),
             _pin(keep_size, "TargetArray"))
    _connect(_pin(axes, "X", is_input=False), _pin(keep_size, "NewItem"))
    _connect(BEL.find_then_pin(keep_vel), _pin(keep_size, "execute"))

    here = _at(_node(ed, FN_GET_TRANSFORM), 620, -1220)
    local_g = _at(_node(ed, FN_INV_XFORM_DIR), 920, -1220)
    _connect(_pin(here, "ReturnValue", is_input=False), _pin(local_g, "T"))
    _connect(_vec(ed, 0.0, 0.0, -BLOOD_GRAVITY, 620, -1080), _pin(local_g, "Direction"))
    pin_fall = _at(ed.add_set_member_variable_node("Fall"), 1180, -1220)
    _connect(_pin(local_g, "ReturnValue", is_input=False), _pin(pin_fall, "Fall"))
    _connect(_loose_pin(gather, "Completed", is_input=False), _pin(pin_fall, "execute"))

    life = _at(_node(ed, FN_LIFESPAN), 1440, -1220)
    _set(life, "InLifespan", BLOOD_LIFETIME)
    _connect(BEL.find_then_pin(pin_fall), _pin(life, "execute"))

    # --- Tick: two scalars for the whole burst, then one pass over it --------
    age_get = _at(ed.add_get_member_variable_node("Age"), 260, 200)
    add = _at(_node(ed, FN_ADD_FF), 470, 200)
    _connect(_pin(age_get, "Age", is_input=False), _pin(add, "A"))
    _connect(_pin(tick, "DeltaSeconds", is_input=False), _pin(add, "B"))
    age_set = _at(ed.add_set_member_variable_node("Age"), 700, 0)
    _connect(_pin(add, "ReturnValue", is_input=False), _pin(age_set, "Age"))
    _connect(BEL.find_then_pin(tick), _pin(age_set, "execute"))
    # Read the *stored* age from here on. The add is pure, so every re-read of
    # its output would recompute it -- harmless while the inputs hold still, but
    # the stored value is the one the next frame accumulates from, and the two
    # should not be allowed to drift apart.
    age = _at(ed.add_get_member_variable_node("Age"), 700, 240)
    age_out = _pin(age, "Age", is_input=False)

    # A = (1 - e^(-k t)) / k, written as (e^(-k t) - 1) / -k. Algebraically the
    # same; the difference is that every constant then lands on a B pin, and
    # the A pin of these math nodes will not hold a literal -- set_pin_value
    # reports success and the pin reads back empty, which compiles as a zero.
    decay = _at(_node(ed, FN_MUL_FF), 940, 400)
    _connect(age_out, _pin(decay, "A"))
    _set(decay, "B", -BLOOD_DRAG)
    gone_frac = _at(_node(ed, FN_EXP), 1160, 400)
    _connect(_pin(decay, "ReturnValue", is_input=False), _pin(gone_frac, "A"))
    spent = _at(_node(ed, FN_SUB_FF), 1380, 400)
    _connect(_pin(gone_frac, "ReturnValue", is_input=False), _pin(spent, "A"))
    _set(spent, "B", 1.0)
    a_term = _at(_node(ed, FN_DIV_FF), 1600, 400)
    _connect(_pin(spent, "ReturnValue", is_input=False), _pin(a_term, "A"))
    _set(a_term, "B", -BLOOD_DRAG)
    a_out = _pin(a_term, "ReturnValue", is_input=False)
    # A in centimetres, for the velocities stored in metres per second. Done
    # once here rather than per droplet, and not on the Multiply_VectorFloat
    # itself -- that node's float pin rejects a literal default, reading back
    # empty whatever is written to it.
    a_cm = _at(_node(ed, FN_MUL_FF), 1820, 400)
    _connect(a_out, _pin(a_cm, "A"))
    _set(a_cm, "B", BLOOD_VELOCITY_ENCODE)
    a_cm_out = _pin(a_cm, "ReturnValue", is_input=False)

    # B = (t - A) / k
    lag = _at(_node(ed, FN_SUB_FF), 1820, 560)
    _connect(age_out, _pin(lag, "A"))
    _connect(a_out, _pin(lag, "B"))
    b_term = _at(_node(ed, FN_DIV_FF), 2040, 560)
    _connect(_pin(lag, "ReturnValue", is_input=False), _pin(b_term, "A"))
    _set(b_term, "B", BLOOD_DRAG)
    b_out = _pin(b_term, "ReturnValue", is_input=False)

    # fade = clamp((lifetime - age) / tail, 0, 1): flat, then a hard cut. Both
    # signs flipped for the same B-pin reason as the A term above.
    left = _at(_node(ed, FN_SUB_FF), 940, 760)
    _connect(age_out, _pin(left, "A"))
    _set(left, "B", BLOOD_LIFETIME)
    tail = _at(_node(ed, FN_DIV_FF), 1160, 760)
    _connect(_pin(left, "ReturnValue", is_input=False), _pin(tail, "A"))
    _set(tail, "B", -BLOOD_FADE_TAIL)
    fade = _at(_node(ed, FN_CLAMP), 1380, 760)
    _connect(_pin(tail, "ReturnValue", is_input=False), _pin(fade, "Value"))
    _set(fade, "Min", 0.0)
    _set(fade, "Max", 1.0)
    fade_out = _pin(fade, "ReturnValue", is_input=False)

    blobs_get = _at(ed.add_get_member_variable_node("Blobs"), 2300, 240)
    fly = ed.add_macro_node(MACRO_FOR_EACH)
    if not fly:
        raise RuntimeError("could not create the ForEachLoop macro node")
    _at(fly, 2560, 0)
    _connect(_pin(blobs_get, "Blobs", is_input=False), _loose_pin(fly, "Array"))
    _connect(BEL.find_then_pin(age_set), _loose_pin(fly, "Exec"))
    each = _loose_pin(fly, "ArrayElement", is_input=False)
    index = _loose_pin(fly, "ArrayIndex", is_input=False)

    vel_arr = _at(ed.add_get_member_variable_node("Velocity"), 2860, 420)
    vel = _at(_node(ed, FN_ARR_GET), 3080, 420)
    _connect(_pin(vel_arr, "Velocity", is_input=False), _pin(vel, "TargetArray"))
    _connect(index, _pin(vel, "Index"))
    thrown = _at(_node(ed, FN_MUL_VF), 3320, 420)
    _connect(_pin(vel, "Item", is_input=False), _pin(thrown, "A"))
    _connect(a_cm_out, _pin(thrown, "B"))

    fall_get = _at(ed.add_get_member_variable_node("Fall"), 2860, 640)
    dropped = _at(_node(ed, FN_MUL_VF), 3320, 640)
    _connect(_pin(fall_get, "Fall", is_input=False), _pin(dropped, "A"))
    _connect(b_out, _pin(dropped, "B"))

    offset = _at(_node(ed, FN_ADD_VV), 3560, 420)
    _connect(_pin(thrown, "ReturnValue", is_input=False), _pin(offset, "A"))
    _connect(_pin(dropped, "ReturnValue", is_input=False), _pin(offset, "B"))

    put = _at(_node(ed, FN_COMP_SET_REL_LOC), 3820, 0)
    _connect(each, _pin(put, "self"))
    _connect(_pin(offset, "ReturnValue", is_input=False), _pin(put, "NewLocation"))
    # No sweep: the droplets have no collision and the spray is meant to pass
    # through the surface it came off, not to be stopped by it.
    _set(put, "bSweep", "false")
    _set(put, "bTeleport", "true")
    _connect(_loose_pin(fly, "LoopBody", is_input=False), _pin(put, "execute"))

    size_arr = _at(ed.add_get_member_variable_node("Size"), 2860, 900)
    born = _at(_node(ed, FN_ARR_GET), 3080, 900)
    _connect(_pin(size_arr, "Size", is_input=False), _pin(born, "TargetArray"))
    _connect(index, _pin(born, "Index"))
    now_size = _at(_node(ed, FN_MUL_FF), 3320, 900)
    _connect(_pin(born, "Item", is_input=False), _pin(now_size, "A"))
    _connect(fade_out, _pin(now_size, "B"))
    size_v = _at(_node(ed, FN_MUL_VF), 3560, 900)
    _connect(_vec(ed, 1.0, 1.0, 1.0, 3320, 1040), _pin(size_v, "A"))
    _connect(_pin(now_size, "ReturnValue", is_input=False), _pin(size_v, "B"))
    shrink = _at(_node(ed, FN_COMP_SET_SCALE), 4080, 0)
    _connect(each, _pin(shrink, "self"))
    _connect(_pin(size_v, "ReturnValue", is_input=False), _pin(shrink, "NewScale3D"))
    _connect(BEL.find_then_pin(put), _pin(shrink, "execute"))

    ed.add_comment_to_nodes(
        f"{len(BLOOD_BLOBS)} droplets -- {BLOOD_DROPLETS} of spray in a "
        f"{BLOOD_CONE_DEG:.0f} deg cone around the actor's +X, which "
        f"_author_impact points down the surface normal of the hit, plus "
        f"{BLOOD_MIST} slow fine ones that hang at the wound. Each carries its "
        f"own launch velocity ({BLOOD_SPEED_MIN:.0f}-{BLOOD_SPEED_MAX:.0f} cm/s) "
        f"in its build-time relative location over {BLOOD_VELOCITY_ENCODE:.0f}, "
        f"and flies the exact solution of dv/dt = g - {BLOOD_DRAG} v under "
        f"{BLOOD_GRAVITY:.0f} cm/s^2 -- two scalars for the burst, one "
        f"multiply-add each. Flat scale until the last {BLOOD_FADE_TAIL}s of "
        f"{BLOOD_LIFETIME}s, then cut. SetLifeSpan removes the actor.",
        [found, gather, rel, parts, keep_blob, keep_vel, axes, keep_size,
         here, local_g, pin_fall, life, age_get, add, age_set, age, decay,
         gone_frac, spent, a_term, a_cm, lag, b_term, left, tail, fade,
         blobs_get, fly,
         vel_arr, vel, thrown, fall_get, dropped, offset, put, size_arr, born,
         now_size, size_v, shrink])

    if not BEL.compile_blueprint(bp):
        raise RuntimeError("BP_BloodSplash failed to compile")
    eas.save_loaded_asset(bp)
    _log(f"built {BLOOD_BP_PATH} ({len(BLOOD_BLOBS)} droplets, {BLOOD_LIFETIME}s, "
         f"drag {BLOOD_DRAG}, gravity {BLOOD_GRAVITY:.0f}, sprayed along the hit "
         f"normal)")
    return bp
