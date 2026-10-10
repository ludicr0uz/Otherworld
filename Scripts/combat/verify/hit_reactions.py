"""verify.hit_reactions -- Flinching: the hit-reaction clips, slot, cooldown and direction pick.
"""

import dataclasses
import math

import unreal

from asset_pipeline.gas_bridge_paths import PLAYER_FAMILY
from combat.anim_blueprint import FULL_BODY_SLOT, HIT_SLOT
from combat.hit_reaction import (
    HIT_ANIM_FALLBACK_DIR, HIT_ANIM_ROOT, HIT_DIR_BACK, HIT_DIR_FRONT,
    HIT_DIR_LEFT, HIT_DIR_RIGHT, HIT_REACTIONS_VAR, HIT_REACTION_CLIPS,
    HIT_REACT_PROBE, HIT_REACT_PROBE_PREFIX, LAST_HIT_FROM_VAR,
    NEXT_REACT_VAR, POSE_BACK_PROBE_PREFIX, PREV_HEALTH_VAR, REACT_INDEX_VAR,
)
from combat.paths import CHARACTER_BP_PATH, NPC_BP_PATH
from combat.tuning import COMBAT, CombatConfig
from combat.damage import ON_HEALTH_CHANGED
from combat.verify.fixtures import (
    _montages, drain_subtracts, drain_writes, exec_reach, h, health_bp, hg, wg,
)
from combat.verify.knife import is_melee_write
from combat.verify.throw_strike import is_strike_node
from combat.verify.common import (
    pellet_calls, take_hits,
    BEL, PIN, _mesh_asset, by_pins, check, component_template, graph, has_in_pin,
    load, num_pin, pin_value, titled,
)
from asset_pipeline.retarget_paths import HIT_SOURCES as RETARGET_HIT_SOURCES
from forest_generator.npc_placement import NPC_HIT_REACTION_CLIPS
from Sound.sound_world import LOW_HEALTH_FRACTION


# ─── Flinching: took a hit and lived ─────────────────────────────────────────

def check_flinching():
    # Everything here is about the difference between a survivor and a corpse. The
    # reaction hangs off the FALSE arm of the death branch, so the two can never run
    # on the same frame; it plays into its own slot, so it cannot cost the player
    # the aim pose permanently; and it is triggered by polling Health rather than
    # called by the shooter, so a damage source that has never heard of it still
    # makes its target flinch.

    check(f"{HIT_REACTIONS_VAR} is an array of animations on the component",
          isinstance(h.get_editor_property(HIT_REACTIONS_VAR), (list, unreal.Array)))
    check(f"{LAST_HIT_FROM_VAR} is a vector, so a direction can be stated",
          isinstance(h.get_editor_property(LAST_HIT_FROM_VAR), unreal.Vector))
    check(f"{PREV_HEALTH_VAR} starts at full health, so nothing flinches on the "
          f"frame it spawns",
          abs(h.get_editor_property(PREV_HEALTH_VAR) - COMBAT.start_health) < 1e-6,
          str(h.get_editor_property(PREV_HEALTH_VAR)))
    check(f"{NEXT_REACT_VAR} starts at zero, so the FIRST hit is never on cooldown",
          abs(h.get_editor_property(NEXT_REACT_VAR)) < 1e-6,
          str(h.get_editor_property(NEXT_REACT_VAR)))

    # The order is the contract: the graph turns a direction into a base index into
    # this tuple and adds a random offset inside the run of Fronts. Three Fronts
    # first, then one each of Back, Left and Right.
    check("the six reaction clips are the shared tuple, not a second copy",
          HIT_REACTION_CLIPS is NPC_HIT_REACTION_CLIPS)
    check("six clips, all from Epic's MM_HitReact_* set -- not MM_Death_*, whose "
          "'staggers' carry the head 1-2 m and spin the body up to 180 deg",
          len(HIT_REACTION_CLIPS) == 6
          and all(c.startswith("MM_HitReact_") for c in HIT_REACTION_CLIPS),
          str(HIT_REACTION_CLIPS))
    check("the four direction buckets tile the six clips, Fronts first",
          [HIT_DIR_FRONT, HIT_DIR_BACK, HIT_DIR_LEFT, HIT_DIR_RIGHT]
          == [(0, 3), (3, 1), (4, 1), (5, 1)])
    check("build_retarget.py retargets exactly those six, from Epic's MM_HitReact_* set",
          [p.rsplit("/", 1)[1] for p in RETARGET_HIT_SOURCES] == list(HIT_REACTION_CLIPS)
          and all(p.startswith(HIT_ANIM_FALLBACK_DIR + "/") for p in RETARGET_HIT_SOURCES),
          str(RETARGET_HIT_SOURCES))


    def _clip_motion(seq, pelvis, chest, head, forward_axis, right_axis):
        """(head's peak push as (forward, right) cm, chest's largest turn in deg).

        The turn is the chest's heading change against frame 0, measured on
        whichever of its axes lies flattest -- the mannequin's spine bones point
        their X up, where a rotator's yaw means nothing. forward/right are the
        mesh's own axes (the mannequin faces +Y, its right is -X).
        """
        opts = unreal.AnimPoseEvaluationOptions()
        ext, world = unreal.AnimPoseExtensions, unreal.AnimPoseSpaces.WORLD
        length = seq.get_play_length()
        at = lambda t: ext.get_anim_pose_at_time(seq, t, opts)
        first = at(0.0)
        q0 = ext.get_bone_pose(first, chest, world).rotation
        axis = min((unreal.Vector(1, 0, 0), unreal.Vector(0, 1, 0), unreal.Vector(0, 0, 1)),
                   key=lambda a: abs(q0.rotate_vector(a).z))
        heading = lambda q: math.degrees(math.atan2(q.rotate_vector(axis).y,
                                                    q.rotate_vector(axis).x))
        h0, head0 = heading(q0), ext.get_bone_pose(first, head, world).translation
        turn, push = 0.0, (0.0, 0.0, 0.0)
        for i in range(41):
            pose = at(length * i / 40)
            d = (heading(ext.get_bone_pose(pose, chest, world).rotation) - h0 + 180) % 360 - 180
            turn = max(turn, abs(d))
            off = ext.get_bone_pose(pose, head, world).translation - head0
            fwd = off.x * forward_axis.x + off.y * forward_axis.y + off.z * forward_axis.z
            right = off.x * right_axis.x + off.y * right_axis.y + off.z * right_axis.z
            if (fwd * fwd + right * right) ** 0.5 > push[0]:
                push = ((fwd * fwd + right * right) ** 0.5, fwd, right)
        return push[1], push[2], turn


    # MEASURED, because the names cannot be trusted twice over: the MM_Death_* set
    # was chosen on its names and spun the chest half round, and Epic authored no
    # Left or Right hit react, so those two slots hold Fronts picked for which way
    # the head goes. A round from a side pushes the head AWAY from it.
    _want = {"Front": lambda f, r: f < 0, "Back": lambda f, r: f > 0,
             "Left": lambda f, r: r > 0, "Right": lambda f, r: r < 0}
    _mesh_fwd, _mesh_right = unreal.Vector(0, 1, 0), unreal.Vector(-1, 0, 0)
    for (base, count), name in ((HIT_DIR_FRONT, "Front"), (HIT_DIR_BACK, "Back"),
                                (HIT_DIR_LEFT, "Left"), (HIT_DIR_RIGHT, "Right")):
        for clip in HIT_REACTION_CLIPS[base:base + count]:
            seq = load(f"{HIT_ANIM_FALLBACK_DIR}/{clip}")
            if not seq:
                check(f"{clip} exists", False)
                continue
            fwd, right, turn = _clip_motion(seq, "pelvis", "spine_05", "head",
                                            _mesh_fwd, _mesh_right)
            check(f"{clip}, in the {name} bucket, pushes the head away from a hit "
                  f"from the {name.lower()}", _want[name](fwd, right),
                  f"head forward {fwd:+.1f} cm, right {right:+.1f} cm")
            check(f"{clip} is a flinch: head moves under 30 cm, chest turns under 60 deg",
                  (fwd * fwd + right * right) ** 0.5 < 30.0 and turn < 60.0,
                  f"head {(fwd * fwd + right * right) ** 0.5:.1f} cm, chest {turn:.0f} deg")

    # And on every creature's retargeted copy: a retarget with a bad spine chain can
    # put the spin back in on its own, and the retargeted copies are what play.
    for _family in sorted({p.split("/")[-2] for p in unreal.EditorAssetLibrary.list_assets(
            HIT_ANIM_ROOT, recursive=True) if "/A_" in p}):
        _turns = {}
        for clip in HIT_REACTION_CLIPS:
            seq = load(f"{HIT_ANIM_ROOT}/{_family}/A_{_family}_{clip}")
            if seq:
                # A generated body's bones, or the mannequin's on the player's
                # UEFN one (asset_pipeline/retarget_to_uefn.py).
                _bones = (("pelvis", "spine_05", "head") if _family == PLAYER_FAMILY
                          else ("Hips", "Spine", "Head"))
                _turns[clip] = _clip_motion(seq, *_bones, _mesh_fwd, _mesh_right)[2]
        check(f"{_family}: all six flinches retargeted, none turning the chest past 60 deg",
              len(_turns) == 6 and max(_turns.values()) < 60.0,
              ", ".join(f"{c[12:]} {t:.0f}" for c, t in _turns.items()))

    # The tuning, and that it is on COMBAT rather than loose in the graph.
    for field, low, high in (("hit_react_cooldown_s", 0.05, 3.0),
                             ("hit_react_rate", 0.25, 4.0),
                             ("hit_react_blend_s", 0.0, 0.5)):
        check(f"COMBAT.{field} is a sane, tunable number",
              field in {f.name for f in dataclasses.fields(CombatConfig)}
              and low <= getattr(COMBAT, field) <= high,
              str(getattr(COMBAT, field, None)))
    # A shotgun puts eight pellets into a target in one frame and the SMG fires
    # eleven rounds a second. Without a cooldown longer than a frame the target
    # stands in the first two frames of a stagger forever -- a vibration, not a
    # reaction.
    check("the cooldown is longer than a frame, or the reaction is a vibration",
          COMBAT.hit_react_cooldown_s > 0.1, str(COMBAT.hit_react_cooldown_s))

    # Every montage in the health graph, and there is exactly one: the flinch.
    check("exactly one montage in the health graph -- the flinch, and nothing else",
          len(_montages) == 1, str(len(_montages)))
    check(f"...and it plays into {HIT_SLOT}, never {FULL_BODY_SLOT}: a full-body "
          f"montage on the death path would blend out and stand the body back up",
          all(pin_value(m, "SlotNodeName") == HIT_SLOT for m in _montages),
          str([pin_value(m, "SlotNodeName") for m in _montages]))
    if _montages:
        m = _montages[0]
        check("the flinch blends in and out rather than popping",
              num_pin(m, "BlendInTime") == COMBAT.hit_react_blend_s
              and num_pin(m, "BlendOutTime") == COMBAT.hit_react_blend_s,
              f"{pin_value(m, 'BlendInTime')}/{pin_value(m, 'BlendOutTime')}")
        check(f"...at COMBAT.hit_react_rate ({COMBAT.hit_react_rate}x), not the "
              f"authored second",
              num_pin(m, "InPlayRate") == COMBAT.hit_react_rate,
              pin_value(m, "InPlayRate"))
        check("...once, not looping: a flinch that loops is a seizure",
              num_pin(m, "LoopCount") == 1, pin_value(m, "LoopCount"))
        # The clip comes out of the array, not off a pin: a literal here would be
        # one skeleton's clip on every body in the game.
        check("the clip is read from the array, never written on the pin",
              bool(PIN.list_connected_pins(BEL.find_input_pin(m, "Asset"))))

    # The trigger. Health compared against PrevHealth, and the whole chain hanging
    # off the death branch's False arm.
    # ...leaving out the debuff drain's pair, which lowers PrevHealth with
    # Health precisely so that it is NOT read as a hit (combat/debuff_drain.py).
    _drain_reads = [PIN.get_owning_node(q) for n in drain_subtracts
                    for q in PIN.list_connected_pins(BEL.find_input_pin(n, "A"))]
    _prev_reads = [n for n in hg if str(BEL.get_node_title(n)).replace("\n", " ")
                   == f"Get {PREV_HEALTH_VAR}" and n not in _drain_reads]
    # ...and a client's, in OnHealthChanged (combat/damage.py), which follows
    # a Health that was no blow for the same reason.
    _told = graph(health_bp).find_event_node(ON_HEALTH_CHANGED)
    _clients = exec_reach([BEL.find_then_pin(_told)]) if _told else []
    _prev_writes = [n for n in hg if has_in_pin(n, PREV_HEALTH_VAR)
                    and n not in drain_writes and n not in _clients]
    check(f"{PREV_HEALTH_VAR} is read once and written once -- the whole trigger",
          len(_prev_reads) == 1 and len(_prev_writes) == 1,
          f"{len(_prev_reads)} reads, {len(_prev_writes)} writes")
    if _prev_writes:
        # Written on EVERY path through the reaction block, not only the one that
        # played something: skipping it on the cooldown arm makes the next hit
        # compare against a health from before this one and fire for nothing.
        _arms = PIN.list_connected_pins(BEL.find_execute_pin(_prev_writes[0]))
        check("...and written on every arm, including the ones that did not react",
              len(_arms) >= 4, f"{len(_arms)} exec links")

    # Direction: two dot products against the owner's own axes, and nothing else.
    _dots = titled(hg, "Dot Product")
    check("the hit direction is two dot products (forward and right), no angles",
          len(_dots) == 2, str(len(_dots)))
    check("...one against the owner's forward",
          len(titled(hg, "GetActorForwardVector")) >= 1)
    check("...and one against the owner's right",
          len(titled(hg, "GetActorRightVector")) >= 1)
    # Four buckets, four writes of the index.
    _index_writes = [n for n in hg if has_in_pin(n, REACT_INDEX_VAR)]
    check("four directions, four writes of the clip index",
          len(_index_writes) == 4, str(len(_index_writes)))
    # Three of the four are pin literals. The fourth -- Front -- has its value
    # WIRED, from a RandomIntegerInRange, which is the only reason a firefight does
    # not look like one animation on a loop; a literal there would read back as 0
    # and pass a naive test, so connected pins are excluded rather than read.
    _wired = [n for n in _index_writes
              if PIN.list_connected_pins(BEL.find_input_pin(n, REACT_INDEX_VAR))]
    _literals = sorted(int(v) for n in _index_writes if n not in _wired
                       for v in [num_pin(n, REACT_INDEX_VAR)] if v is not None)
    check("Back, Left and Right are written as literals",
          _literals == sorted([HIT_DIR_BACK[0], HIT_DIR_LEFT[0],
                               HIT_DIR_RIGHT[0]]), str(_literals))
    check("...and exactly one of the four -- Front -- is wired instead",
          len(_wired) == 1, str(len(_wired)))
    # The draw itself: 0..2 over the three Front clips, offset by the Front base.
    _draws = [n for n in hg if has_in_pin(n, "Min") and has_in_pin(n, "Max")
              and num_pin(n, "Max") == float(HIT_DIR_FRONT[1] - 1)
              and num_pin(n, "Min") == 0.0]
    check(f"the Front pick draws over all {HIT_DIR_FRONT[1]} Front clips, so a "
          f"firefight is not one animation on a loop",
          len(_draws) == 1, str(len(_draws)))
    # An array shorter than six -- a checkout whose retarget has not run -- must
    # clip to the last entry rather than read off the end.
    check("the index is clamped against the array's real length",
          bool(titled(hg, "Clamp")) or bool(by_pins(hg, "Value", "Min", "Max")))
    check("...and the array's length is checked before anything is played",
          bool(titled(hg, "Length")))

    # Who writes the direction. Both damage sources do, and neither of them had to
    # know the reaction exists to make it fire -- only to make it point the right
    # way.
    # (The punch's and the knife's blows write it too; verify/punch.py and
    # verify/knife.py check those; a thrown blade's is verify/throw_strike.py's.)
    # A blow tells the target's TakeHit (combat/damage.py), which writes it.
    _from_writes = [n for n in take_hits(wg)
                    if not is_melee_write(n, "From") and not is_strike_node(n)]
    # The pellet's is the native base's since W1 (FirePellets, C++): it hands
    # TakeHit the hit's own impact normal, which already points back up the
    # shot. The graph has no pellet TakeHit; probes/probe_hit_react.py has
    # the flinch.
    check(f"the pellets tell the target which way they came ({LAST_HIT_FROM_VAR}) from "
          "the native FirePellets, not from a TakeHit in the graph",
          len(_from_writes) == 0 and len(pellet_calls(wg)) == 1,
          f"{len(_from_writes)} graph TakeHit(s), {len(pellet_calls(wg))} FirePellets")

    # THE PROBE IS GONE. "A gate that never opens looks identical to one that
    # works", so the reaction was proved at runtime with a PrintWarning on the end
    # of the chain and a scripted hit on every wanderer -- and both are removed by
    # rebuilding with HIT_REACT_PROBE False. These two checks are what stop one
    # coming back: the switch, and the built graph.
    check("the hit-reaction probe switch is off", HIT_REACT_PROBE is False,
          str(HIT_REACT_PROBE))
    _probe_tokens = (HIT_REACT_PROBE_PREFIX, POSE_BACK_PROBE_PREFIX)
    _probe_nodes = [f"{_g}:{BEL.get_node_title(n)}"
                    for _g, _nodes in (("health", hg), ("weapon", wg))
                    for n in _nodes
                    for _p in BEL.list_input_pins(n)
                    if any(t in str(PIN.get_pin_value(_p)) for t in _probe_tokens)]
    check("...and no probe node survives in either built graph",
          not _probe_nodes, str(_probe_nodes))
    # The scripted hit the probe used to deal itself, too: nothing in the shipped
    # health graph may subtract from Health except the world floor's write of zero.
    # MaxHealth has one reader left, which subtracts nothing: the heartbeat's
    # threshold (Sound/sound_world.py), a product compared with Health.
    _max_reads = [PIN.get_owning_node(q) for n in hg
                  if str(BEL.get_node_title(n)).replace("\n", " ").startswith("Get MaxHealth")
                  for p in BEL.list_output_pins(n) for q in PIN.list_connected_pins(p)]
    check("...and the probe's scripted self-hit is gone with it",
          all(num_pin(n, "B") == LOW_HEALTH_FRACTION for n in _max_reads)
          and len(_max_reads) <= 1,
          "MaxHealth is read by nothing in the health graph but the heartbeat's "
          f"threshold: {len(_max_reads)} reader(s)")

    # Every character carries its OWN six, because an AnimSequence belongs to one
    # skeleton and a shared default could only be right for one body.
    for _bp_path, _who in ((CHARACTER_BP_PATH, "the player"),
                           (NPC_BP_PATH, "a wanderer")):
        _bp = load(_bp_path)
        if not _bp:
            continue
        _comp = component_template(_bp, "HealthComponent")
        if not _comp:
            continue
        _clips = list(_comp.get_editor_property(HIT_REACTIONS_VAR))
        check(f"{_who} carries all six reactions, or none at all",
              len(_clips) in (0, len(HIT_REACTION_CLIPS)), str(len(_clips)))
        if _clips:
            check("...in HIT_REACTION_CLIPS order",
                  # A_Zombie01_MM_HitReact_... on a body with a skeleton of
                  # its own, MM_HitReact_... (Epic's originals) on one bound
                  # to the mannequin's.
                  [c.get_name().split("MM_", 1)[-1] for c in _clips]
                  == [c.split("MM_", 1)[1] for c in HIT_REACTION_CLIPS],
                  str([c.get_name() for c in _clips]))
            _mesh = _mesh_asset(_bp)
            _skel = _mesh.get_editor_property("skeleton") if _mesh else None
            check(f"...all on {_who}'s OWN skeleton, or they would never play",
                  all(c.get_editor_property("skeleton") == _skel for c in _clips),
                  str({c.get_editor_property("skeleton").get_name() for c in _clips}))


def run():
    check_flinching()
