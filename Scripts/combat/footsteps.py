"""BP_FootstepComponent: distance-driven footfalls for the player and every
wanderer, the random-sound picker it plays through, and the noise the
player's steps make for the wanderers to hear.
"""

import unreal

from combat.audio import CREATURE_AUDIO_DIR, FOOTSTEP_NAMES
from combat.log import _log
from uebp.graph import (
    BEL, BGE, _apply_defaults, _assets, _connect, _create_blueprint, _events, _loose_pin,
    _node, _palette, _pin, _set, else_, out, then)
from uebp.layout import arrange
from combat.noise import _author_make_noise
from combat.paths import WEAPON_DIR
from combat.tuning import COMBAT
from uebp.nodes.actor import (
    FN_ACTOR_LOC, FN_GET_OWNER, FN_IS_PLAYER_CONTROLLED, FN_ON_GROUND, FN_VELOCITY)
from uebp.nodes.array import FN_ARR_GET, FN_ARR_LEN
from uebp.nodes.math import (
    FN_ADD_FF, FN_AND, FN_GE_FF, FN_GREATER_FF, FN_GREATER_II, FN_MUL_FF, FN_RAND_INT,
    FN_SUB_FF, FN_SUB_II, FN_VSIZE_XY)
from uebp.nodes.palette import NODE_CAST_CHARACTER
from uebp.nodes.system import FN_PLAY_SOUND
from uebp.vars import declare, defaults
from uebp import props as EP
from combat import footstep_vars as FV


# --- footsteps ---------------------------------------------------------------
# One component, on the player and on every wanderer, because a footfall is a
# fact about having legs and not about which side you are on.
#
# Driven by DISTANCE TRAVELLED, not by a timer. That is the whole design: a
# timer has to be told how fast its owner is moving and gets it wrong the
# moment anything else changes the speed, and three things already do -- sprint
# (900 vs 600), the per-instance gait variance, and the wendigo's 1.15x. An
# accumulator over ground covered needs to know none of them and cannot
# disagree with any of them; the faster something moves, the sooner it has
# covered a stride.
#
# 160 cm is one footfall of a run at 600 cm/s, which works out at about 3.7
# steps a second. It is a compromise across the speed range -- the same stride
# at a walk is slightly long -- and a compromise is the right answer here,
# because the alternative is a speed-to-stride curve that nobody can hear.
#
# The remainder is CARRIED rather than reset to zero when a step fires, or the
# effective stride would be "160 cm plus however far this frame happened to
# take us", which makes the step rate depend on framerate.
FOOTSTEP_STRIDE_CM = 160.0
# Below this the owner is shuffling against a wall, not walking.
FOOTSTEP_MIN_SPEED_CMS = 40.0
FOOTSTEP_BP_PATH = f"{WEAPON_DIR}/BP_FootstepComponent"


def _author_random_sound(ed, var_name, at_pin, exec_in, volume_pin=None):
    """Play a random element of the ``var_name`` sound array at ``at_pin``,
    at ``volume_pin`` if one is given (the stance's StepVolume).

    Returns ``(nodes, then_pin)``. Guarded on the array's own length, because
    RandomIntegerInRange(0, -1) into Array_Get is an access-none rather than
    silence -- and an empty array is the normal state of a checkout that has
    not run Scripts/make_creature_sounds.py yet.

    The same shape exists in build_npc_blueprints.py. Two copies rather than a
    shared module because the two files each carry their own _pin/_connect/_set
    authoring helpers, and hoisting one function would mean hoisting those.
    """
    made = []

    def keep(n):
        made.append(n)
        return n

    table = keep(ed.add_get_member_variable_node(var_name))
    table_out = out(table, var_name)
    count = keep(_node(ed, FN_ARR_LEN))
    _connect(table_out, _pin(count, "TargetArray"))
    stocked = keep(_node(ed, FN_GREATER_II))
    _connect(out(count), _pin(stocked, "A"))
    _set(stocked, "B", 0)

    have = keep(ed.add_branch_node())
    _connect(out(stocked), _pin(have, "Condition"))
    _connect(exec_in, _pin(have, "execute"))

    top = keep(_node(ed, FN_SUB_II))
    _connect(out(count), _pin(top, "A"))
    _set(top, "B", 1)
    which = keep(_node(ed, FN_RAND_INT))
    _set(which, "Min", 0)
    _connect(out(top), _pin(which, "Max"))
    pick = keep(_node(ed, FN_ARR_GET))
    _connect(table_out, _pin(pick, "TargetArray"))
    _connect(out(which), _pin(pick, "Index"))

    play = keep(_node(ed, FN_PLAY_SOUND))
    _connect(out(pick, "Item"), _pin(play, "Sound"))
    _connect(at_pin, _pin(play, "Location"))
    if volume_pin is not None:
        _connect(volume_pin, _pin(play, "VolumeMultiplier"))
    _connect(then(have), _pin(play, "execute"))

    join = keep(ed.add_branch_node())
    _set(join, "Condition", "true")
    _connect(then(play), _pin(join, "execute"))
    _connect(else_(have), _pin(join, "execute"))
    return made, then(join)


def build_footstep_component(rebuild=True):
    """A footfall every FOOTSTEP_STRIDE_CM of ground covered.

        [Tick] -> cast owner to Character -> [movement on the ground?]
                    no  -> Travelled = 0          (a jump restarts the stride)
                    yes -> Travelled += speed * dt
                        -> [Travelled >= stride AND moving?]
                             yes -> Travelled -= stride
                                 -> play one of Sounds at the owner,
                                    at StepVolume
                             no  -> done

    Distance rather than time: see FOOTSTEP_STRIDE_CM. Nothing here knows about
    sprint, about the gait variance the level generator applies per wanderer,
    or about the wendigo being 15% faster -- all three change how far the owner
    moves per second, and all three therefore change the step rate for free.

    Subtracting the stride rather than zeroing Travelled is what keeps the rate
    independent of framerate: zeroing throws away the overshoot, so the real
    stride becomes 160 cm plus whatever one frame added.
    """
    bp = _create_blueprint(FOOTSTEP_BP_PATH, unreal.ActorComponent)
    ed = BGE.get_graph_editor_by_name(bp, "EventGraph")
    tick, _begin = _events(ed, rebuild)

    declare(ed, FV.TABLE)

    owner = _node(ed, FN_GET_OWNER)
    owner_out = out(owner)
    as_char = _palette(ed, NODE_CAST_CHARACTER)
    _connect(owner_out, _pin(as_char, "Object"))
    _connect(then(tick), _pin(as_char, "execute"))
    char_out = _loose_pin(as_char, "AsCharacter", is_input=False)

    movement = ed.add_get_member_variable_node(EP.CHARACTER_MOVEMENT, "/Script/Engine.Character")
    _connect(char_out, _pin(movement, "self"))
    grounded = _node(ed, FN_ON_GROUND)
    _connect(out(movement, EP.CHARACTER_MOVEMENT), _pin(grounded, "self"))

    walking = ed.add_branch_node()
    _connect(out(grounded), _pin(walking, "Condition"))
    _connect(then(as_char), _pin(walking, "execute"))

    # Airborne: forget the part-stride, so landing does not immediately fire a
    # step that was 90% accumulated before the jump.
    reset = ed.add_set_member_variable_node(FV.Travelled)
    _set(reset, FV.Travelled, 0.0)
    _connect(else_(walking), _pin(reset, "execute"))

    speed_v = _node(ed, FN_VELOCITY)
    _connect(owner_out, _pin(speed_v, "self"))
    # Horizontal speed only: falling at terminal velocity is not walking, and
    # VSize would count it.
    speed = _node(ed, FN_VSIZE_XY)
    _connect(out(speed_v), _pin(speed, "A"))
    speed_out = out(speed)

    step = _node(ed, FN_MUL_FF)
    _connect(speed_out, _pin(step, "A"))
    _connect(out(tick, "DeltaSeconds"), _pin(step, "B"))
    sofar = ed.add_get_member_variable_node(FV.Travelled)
    total = _node(ed, FN_ADD_FF)
    _connect(out(sofar, FV.Travelled), _pin(total, "A"))
    _connect(out(step), _pin(total, "B"))
    advance = ed.add_set_member_variable_node(FV.Travelled)
    _connect(out(total), _pin(advance, FV.Travelled))
    _connect(then(walking), _pin(advance, "execute"))
    # Read the STORED total from here on. The add is pure and would be
    # re-evaluated against the new Travelled on a second read -- the same trap
    # the NPC id and the reload arithmetic ran into.
    have = ed.add_get_member_variable_node(FV.Travelled)
    have_out = out(have, FV.Travelled)

    stride = ed.add_get_member_variable_node(FV.StrideCm)
    stride_out = out(stride, FV.StrideCm)
    far_enough = _node(ed, FN_GE_FF)
    _connect(have_out, _pin(far_enough, "A"))
    _connect(stride_out, _pin(far_enough, "B"))
    quick_enough = _node(ed, FN_GREATER_FF)
    _connect(speed_out, _pin(quick_enough, "A"))
    _set(quick_enough, "B", FOOTSTEP_MIN_SPEED_CMS)
    both = _node(ed, FN_AND)
    _connect(out(far_enough), _pin(both, "A"))
    _connect(out(quick_enough), _pin(both, "B"))

    lands = ed.add_branch_node()
    _connect(out(both), _pin(lands, "Condition"))
    _connect(then(advance), _pin(lands, "execute"))

    left = _node(ed, FN_SUB_FF)
    _connect(have_out, _pin(left, "A"))
    _connect(stride_out, _pin(left, "B"))
    charge = ed.add_set_member_variable_node(FV.Travelled)
    _connect(out(left), _pin(charge, FV.Travelled))
    _connect(then(lands), _pin(charge, "execute"))

    at = _node(ed, FN_ACTOR_LOC)
    _connect(owner_out, _pin(at, "self"))
    volume = ed.add_get_member_variable_node(FV.StepVolume)
    _sounded, stepped = _author_random_sound(
        ed, FV.Sounds, out(at),
        then(charge),
        volume_pin=out(volume, FV.StepVolume))

    # --- and the wanderers may hear it ---------------------------------------
    # Only the player's steps: the wanderers wear this same component, and a
    # pack that woke itself up with its own feet would never patrol at all.
    # The reach is proportional to speed (COMBAT.footstep_noise_range_cm at
    # the reference speed), so a sprint carries further than a walk and
    # aiming's half-speed creep carries half as far, without this graph
    # knowing about either. StepNoise then scales it for the stance: a crouched
    # or prone step is slower AND quieter.
    mine = _node(ed, FN_IS_PLAYER_CONTROLLED)
    _connect(char_out, _pin(mine, "self"))
    players = ed.add_branch_node()
    _connect(out(mine), _pin(players, "Condition"))
    _connect(stepped, _pin(players, "execute"))
    reach = _node(ed, FN_MUL_FF)
    _connect(speed_out, _pin(reach, "A"))
    _set(reach, "B", COMBAT.footstep_noise_range_cm
         / COMBAT.footstep_noise_reference_speed_cms)
    hushed = _node(ed, FN_MUL_FF)
    _connect(out(reach), _pin(hushed, "A"))
    _connect(out(ed.add_get_member_variable_node(FV.StepNoise), FV.StepNoise), _pin(hushed, "B"))
    _author_make_noise(ed, then(players), out(at), out(hushed))

    ed.add_comment_to_nodes(
        f"A footfall every {FOOTSTEP_STRIDE_CM:.0f} cm of ground covered, "
        f"which is about {600.0 / FOOTSTEP_STRIDE_CM:.1f} a second at a "
        f"600 cm/s run. Distance, not a timer: sprint, the per-wanderer gait "
        f"variance and the wendigo's 1.15x all change how fast their owner "
        f"moves, and an accumulator over distance tracks every one of them "
        f"without being told. The remainder is carried, not zeroed, so the "
        f"rate does not depend on framerate.",
        ed.list_all_nodes())

    arrange(ed)
    if not BEL.compile_blueprint(bp):
        raise RuntimeError("BP_FootstepComponent failed to compile")

    eas = _assets()
    found = [eas.load_asset(f"{CREATURE_AUDIO_DIR}/{n}") for n in FOOTSTEP_NAMES
             if eas.does_asset_exist(f"{CREATURE_AUDIO_DIR}/{n}")]
    _apply_defaults(bp, {**defaults(FV.TABLE), FV.StrideCm: FOOTSTEP_STRIDE_CM, FV.Sounds: found})
    _log(f"built {FOOTSTEP_BP_PATH} "
         f"({len(found)} steps, one every {FOOTSTEP_STRIDE_CM:.0f} cm)")
    return bp
