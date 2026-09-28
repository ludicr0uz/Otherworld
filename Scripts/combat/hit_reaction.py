"""Flinching: the six hit-reaction clips, the direction pick authored into
BP_HealthComponent's Tick, and the per-character clip tables installed on
each health component.
"""

import unreal

from forest_generator.npc_placement import NPC_HIT_REACTION_CLIPS
from combat.anim_blueprint import HIT_SLOT, UPPER_BODY_ROOT
from combat.graph import (
    BEL, _assets, _at, _component_object, _connect, _handles, _log,
    _loose_pin, _node, _palette, _pin, _set,
)
from combat.nodes import (
    FN_ABS, FN_ACTOR_FORWARD, FN_ACTOR_RIGHT, FN_ADD_FF, FN_ADD_II,
    FN_ANIM_INSTANCE, FN_ARR_GET, FN_ARR_LEN, FN_CLAMP_II, FN_CONCAT,
    FN_DISPLAY_NAME, FN_DOT_VV, FN_GET_OWNER, FN_GE_FF, FN_GREATER_II,
    FN_INT_TO_STR, FN_LESS_FF, FN_PLAY_SLOT, FN_RAND_INT, FN_SUB_II,
    FN_TIME_SECONDS, FN_WARN, NODE_CAST_CHARACTER,
)
from combat.tuning import COMBAT


# --- flinching: the hit reaction ---------------------------------------------
# A survivor reacts; a corpse ragdolls. The two are deliberately different
# mechanisms and they cannot both be wanted at once, which is why the reaction
# hangs off the **False** arm of the death branch in BP_HealthComponent's Tick:
# "Health went down since last frame AND it is still above zero".
#
# WHY A POLL AND NOT A CALL. Damage is written straight onto Health by whoever
# did it -- the weapon component's pellet loop, the wanderers' melee, the world
# floor. Triggering the reaction at each of those sites means each of them can
# forget, and the next damage source that appears starts out silent. Comparing
# Health against PrevHealth once per Tick is one place that cannot be forgotten
# and does not care where the damage came from. It also gets "and survived" for
# free: the frame a target dies, the death branch is taken and the reaction arm
# is never reached, so nothing can flinch and ragdoll in the same frame.
#
# WHY ITS OWN SLOT, UPPER BODY. Three montages want the chest at various times
# and playing two into one slot stops the first:
#
#   DefaultSlot    the aim pose, a 9999-loop dynamic montage the player holds
#                  for as long as a weapon is equipped, and the wanderers'
#                  attack swing. Reacting into it would kill the ready pose and
#                  leave the player holding a rifle in the locomotion pose until
#                  the next equip -- "does not break aiming" ruled it out.
#   FullBodySlot   free, and full body. A one-second full-body stagger stops the
#                  legs: the player loses control of a running character mid
#                  firefight and a charging wanderer freezes in the open.
#   HitSlot        added here, downstream of the aim blend and filtered to the
#                  same spine root, so a reaction overrides the ready pose (and
#                  the swing) for its duration and blends back out of it, while
#                  the legs never stop.
#
# A slot with nothing playing passes its input straight through, and the second
# layered blend's two inputs are then the same pose, so this costs nothing until
# something is actually hit.
#
# WHAT A SEPARATE SLOT DOES NOT BUY, and this is the one surprise in the whole
# feature: montages are stopped per GROUP, not per slot. Every slot belongs to
# the skeleton's default group unless USkeleton::SetSlotGroupName says
# otherwise, and UE 5.8 exposes none of that to Python -- `slot_group_names`,
# `slot_to_group_name_map` and `slot_anim_tracks` all fail as editor properties
# on a USkeleton, and the class has no slot or group methods at all (measured).
# So a flinch in HitSlot DOES stop the ready pose in DefaultSlot. What the
# separate slot buys is the POSE -- the reaction lands on top of the aim pose
# for its second instead of replacing the whole upper body for good -- and
# _author_ready_pose_keepalive buys back the rest by restarting the ready pose
# on the first frame after the stagger.
# The six clips, and the ORDER IS THE CONTRACT: the graph picks a direction,
# turns it into a base index into this array, and adds a random offset within
# the run of Fronts. Front first because it is the common case and the one Epic
# authored three of.
#
# They are Epic's MM_HitReact_* set, the flinches Epic ships for this: 0.7-1.2 s
# each, in place, the head moving 3-18 cm and the chest turning at most 55 deg
# before both come back to rest. Not MM_Death_* (see the dying block above and
# HIT_SOURCES in build_retarget.py): those carry the head 1-2 m and two of them
# turn the whole body 105-180 deg, and through HitSlot's mesh-space blend that
# was the chest spinning half round on walking legs. Epic authored no Left or
# Right, so those slots hold the Front whose head moves away from that side --
# see NPC_HIT_REACTION_CLIPS, and the measurement in the verifier.
# Imported, not written out again: the wanderers' AI controllers build their
# own per-creature paths from the same tuple (npc_placement._creature), and two
# copies of an ORDER that three files index by position is the drift this
# project's one-table rule exists to prevent.
HIT_REACTION_CLIPS = NPC_HIT_REACTION_CLIPS
# (base index, count) per direction, derived from the tuple above rather than
# written twice -- the graph bakes these numbers into pin literals, so a
# reordering that only changed the tuple would otherwise play a Left clip for a
# hit in the back and nothing would say so.
HIT_DIR_FRONT = (0, 3)
HIT_DIR_BACK = (3, 1)
HIT_DIR_LEFT = (4, 1)
HIT_DIR_RIGHT = (5, 1)
# Where the six live once retargeted, and the fallback for a checkout with no
# /Game/Sourced. The creature layout mirrors npc_placement._creature and
# build_retarget.anim_dir; it is derived from the mesh's own name at build time
# (see hit_reactions), never written out per creature.
HIT_ANIM_ROOT = "/Game/Sourced/Characters/Anims"
HIT_ANIM_FALLBACK_DIR = "/Game/Characters/Mannequins/Anims/Rifle/HitReact"
# The clips this character can play, on the component, filled per character by
# install_hit_reactions from that character's OWN skeleton -- exactly as the
# hit-zone tables are. An AnimSequence belongs to one skeleton, so a shared
# default here could only ever be right for one body.
HIT_REACTIONS_VAR = "HitReactions"
# Unit vector, world space, pointing from the victim TOWARD whatever hit it.
# Written by the pellet loop (off the impact normal, which already points back
# up the shot) and by a wanderer's punch; read once, by the direction pick.
# Zero is a legal value and means "nobody said" -- the pick is written so that
# it falls to Front, which is the reaction that has three clips.
LAST_HIT_FROM_VAR = "LastHitFrom"
# What Health was on the previous Tick. The whole trigger.
PREV_HEALTH_VAR = "PrevHealth"
# When the next reaction may start, in world seconds. Same shape as the
# wanderers' NextVoiceTime and the weapons' NextFireTime: a deadline, not a
# timer, so nothing has to tick it down.
NEXT_REACT_VAR = "NextReactTime"
# The index the direction pick chose, stored rather than wired because it is
# written on four different exec arms and read by one.
REACT_INDEX_VAR = "ReactIndex"
# TEMPORARY INSTRUMENTATION, and it must stay False.
#
# "A gate that never opens looks identical to one that works": a -game run in
# which nothing flinched and a -game run in which the reaction silently never
# fired produce the same log. Flipping this to True adds one PrintWarning to
# the end of the reaction chain, naming the actor and the clip index, so the
# path can be proved to run -- and it was, see the hit-reaction section of
# CLAUDE.md for the numbers. It is then flipped back and the builder re-run,
# which is what removes the node; verify_weapons_and_combat.py asserts BOTH
# that this is False and that no node in the built graph prints the token, so
# a probe left switched on cannot pass.
HIT_REACT_PROBE = False
HIT_REACT_PROBE_PREFIX = "[HIT-REACT] "
# The other half of the same probe: the ready pose putting itself back.
POSE_BACK_PROBE_PREFIX = "[POSE-BACK] "


def _author_hit_reaction(ed, exec_in, x0, y0):
    """Took a hit and lived: flinch. Returns ``(nodes, then_pin)``.

    Wired onto the **False** arm of the death branch, which is what makes
    "survived" free: the frame a target's Health reaches zero the other arm is
    taken, so nothing can ragdoll and stagger at the same time.

        Health < PrevHealth?                      something hurt us this frame
          -> world time past NextReactTime?       not still mid-flinch
            -> HitReactions is not empty?         this body has clips
              -> which way did it come from?      -> ReactIndex
              -> play it into HitSlot, upper body
              -> NextReactTime = now + cooldown
        (every no, and a non-Character owner) ---> PrevHealth = Health

    WHICH CLIP. The six are Epic's directional set (three Fronts, one each of
    Back/Left/Right -- see HIT_REACTION_CLIPS) and the pick is two dot products,
    no angles:

        f = LastHitFrom . owner forward     f >= |r|        -> Front, one of 3
        r = LastHitFrom . owner right       -f > |r|        -> Back
                                            |f| < r         -> Right
                                            |f| < -r        -> Left

    LastHitFrom is written by whoever did the damage and points from the victim
    toward the source. Nobody is obliged to write it: an unattributed hit leaves
    it at the zero vector, both dots come out 0, and `>=` on the forward test is
    what makes that land on Front -- the direction with three clips and the one
    a player is most likely to be facing anyway.

    THE INDEX IS CLAMPED against the array's real length rather than trusted.
    The base indices are positions in HIT_REACTION_CLIPS, and a body whose
    retarget has not run carries fewer than six clips (or none -- hence the
    length guard above it); an unclamped Back on a three-clip array is an
    Array_Get off the end.
    """
    made = []

    def keep(n):
        made.append(n)
        return n

    # --- did Health go down this frame? --------------------------------------
    now_h = keep(_at(ed.add_get_member_variable_node("Health"), x0, y0 + 240))
    was_h = keep(_at(ed.add_get_member_variable_node(PREV_HEALTH_VAR), x0, y0 + 360))
    dropped = keep(_at(_node(ed, FN_LESS_FF), x0 + 240, y0 + 240))
    _connect(_pin(now_h, "Health", is_input=False), _pin(dropped, "A"))
    _connect(_pin(was_h, PREV_HEALTH_VAR, is_input=False), _pin(dropped, "B"))
    took = keep(_at(ed.add_branch_node(), x0 + 480, y0))
    _connect(_pin(dropped, "ReturnValue", is_input=False), _pin(took, "Condition"))
    _connect(exec_in, _pin(took, "execute"))

    # --- is the last one finished? -------------------------------------------
    now = keep(_at(_node(ed, FN_TIME_SECONDS), x0 + 480, y0 + 380))
    now_out = _pin(now, "ReturnValue", is_input=False)
    due = keep(_at(ed.add_get_member_variable_node(NEXT_REACT_VAR), x0 + 480, y0 + 500))
    ready = keep(_at(_node(ed, FN_GE_FF), x0 + 720, y0 + 380))
    _connect(now_out, _pin(ready, "A"))
    _connect(_pin(due, NEXT_REACT_VAR, is_input=False), _pin(ready, "B"))
    cooled = keep(_at(ed.add_branch_node(), x0 + 960, y0))
    _connect(_pin(ready, "ReturnValue", is_input=False), _pin(cooled, "Condition"))
    _connect(BEL.find_then_pin(took), _pin(cooled, "execute"))

    # --- does this body have any reactions at all? ---------------------------
    clips = keep(_at(ed.add_get_member_variable_node(HIT_REACTIONS_VAR),
                     x0 + 960, y0 + 620))
    clips_out = _pin(clips, HIT_REACTIONS_VAR, is_input=False)
    count = keep(_at(_node(ed, FN_ARR_LEN), x0 + 1200, y0 + 620))
    _connect(clips_out, _pin(count, "TargetArray"))
    count_out = _pin(count, "ReturnValue", is_input=False)
    stocked = keep(_at(_node(ed, FN_GREATER_II), x0 + 1440, y0 + 620))
    _connect(count_out, _pin(stocked, "A"))
    _set(stocked, "B", 0)
    have = keep(_at(ed.add_branch_node(), x0 + 1680, y0))
    _connect(_pin(stocked, "ReturnValue", is_input=False), _pin(have, "Condition"))
    _connect(BEL.find_then_pin(cooled), _pin(have, "execute"))

    # --- which way did it come from? -----------------------------------------
    owner = keep(_at(_node(ed, FN_GET_OWNER), x0 + 1680, y0 + 760))
    owner_out = _pin(owner, "ReturnValue", is_input=False)
    fwd = keep(_at(_node(ed, FN_ACTOR_FORWARD), x0 + 1920, y0 + 760))
    _connect(owner_out, _pin(fwd, "self"))
    rgt = keep(_at(_node(ed, FN_ACTOR_RIGHT), x0 + 1920, y0 + 880))
    _connect(owner_out, _pin(rgt, "self"))
    came = keep(_at(ed.add_get_member_variable_node(LAST_HIT_FROM_VAR),
                    x0 + 1920, y0 + 1000))
    came_out = _pin(came, LAST_HIT_FROM_VAR, is_input=False)

    ahead = keep(_at(_node(ed, FN_DOT_VV), x0 + 2160, y0 + 760))
    _connect(came_out, _pin(ahead, "A"))
    _connect(_pin(fwd, "ReturnValue", is_input=False), _pin(ahead, "B"))
    ahead_out = _pin(ahead, "ReturnValue", is_input=False)
    beside = keep(_at(_node(ed, FN_DOT_VV), x0 + 2160, y0 + 900))
    _connect(came_out, _pin(beside, "A"))
    _connect(_pin(rgt, "ReturnValue", is_input=False), _pin(beside, "B"))
    beside_out = _pin(beside, "ReturnValue", is_input=False)

    fore_aft = keep(_at(_node(ed, FN_ABS), x0 + 2400, y0 + 760))
    _connect(ahead_out, _pin(fore_aft, "A"))
    lateral = keep(_at(_node(ed, FN_ABS), x0 + 2400, y0 + 900))
    _connect(beside_out, _pin(lateral, "A"))
    axis = keep(_at(_node(ed, FN_GE_FF), x0 + 2640, y0 + 760))
    _connect(_pin(fore_aft, "ReturnValue", is_input=False), _pin(axis, "A"))
    _connect(_pin(lateral, "ReturnValue", is_input=False), _pin(axis, "B"))
    front_back = keep(_at(ed.add_branch_node(), x0 + 2880, y0))
    _connect(_pin(axis, "ReturnValue", is_input=False), _pin(front_back, "Condition"))
    _connect(BEL.find_then_pin(have), _pin(front_back, "execute"))

    # Front, and one of the three Epic authored. The random draw is the only
    # thing that keeps a firefight from looking like one animation on a loop,
    # and Front is where it is worth spending because it is the common case.
    facing = keep(_at(_node(ed, FN_GE_FF), x0 + 2880, y0 + 380))
    _connect(ahead_out, _pin(facing, "A"))
    _set(facing, "B", 0.0)
    from_front = keep(_at(ed.add_branch_node(), x0 + 3120, y0 - 260))
    _connect(_pin(facing, "ReturnValue", is_input=False), _pin(from_front, "Condition"))
    _connect(BEL.find_then_pin(front_back), _pin(from_front, "execute"))

    spread = keep(_at(_node(ed, FN_RAND_INT), x0 + 3120, y0 + 380))
    _set(spread, "Min", 0)
    _set(spread, "Max", HIT_DIR_FRONT[1] - 1)
    front_idx = keep(_at(_node(ed, FN_ADD_II), x0 + 3360, y0 + 380))
    _connect(_pin(spread, "ReturnValue", is_input=False), _pin(front_idx, "A"))
    _set(front_idx, "B", HIT_DIR_FRONT[0])

    arms = []
    pick_front = keep(_at(ed.add_set_member_variable_node(REACT_INDEX_VAR),
                          x0 + 3600, y0 - 400))
    _connect(_pin(front_idx, "ReturnValue", is_input=False),
             _pin(pick_front, REACT_INDEX_VAR))
    _connect(BEL.find_then_pin(from_front), _pin(pick_front, "execute"))
    arms.append(BEL.find_then_pin(pick_front))

    pick_back = keep(_at(ed.add_set_member_variable_node(REACT_INDEX_VAR),
                         x0 + 3600, y0 - 180))
    _set(pick_back, REACT_INDEX_VAR, HIT_DIR_BACK[0])
    _connect(BEL.find_else_pin(from_front), _pin(pick_back, "execute"))
    arms.append(BEL.find_then_pin(pick_back))

    to_right = keep(_at(_node(ed, FN_GE_FF), x0 + 2880, y0 + 500))
    _connect(beside_out, _pin(to_right, "A"))
    _set(to_right, "B", 0.0)
    from_side = keep(_at(ed.add_branch_node(), x0 + 3120, y0 + 40))
    _connect(_pin(to_right, "ReturnValue", is_input=False), _pin(from_side, "Condition"))
    _connect(BEL.find_else_pin(front_back), _pin(from_side, "execute"))

    pick_right = keep(_at(ed.add_set_member_variable_node(REACT_INDEX_VAR),
                          x0 + 3600, y0 + 40))
    _set(pick_right, REACT_INDEX_VAR, HIT_DIR_RIGHT[0])
    _connect(BEL.find_then_pin(from_side), _pin(pick_right, "execute"))
    arms.append(BEL.find_then_pin(pick_right))

    pick_left = keep(_at(ed.add_set_member_variable_node(REACT_INDEX_VAR),
                         x0 + 3600, y0 + 260))
    _set(pick_left, REACT_INDEX_VAR, HIT_DIR_LEFT[0])
    _connect(BEL.find_else_pin(from_side), _pin(pick_left, "execute"))
    arms.append(BEL.find_then_pin(pick_left))

    # --- play it, into HitSlot, on whatever body this is ---------------------
    chosen = keep(_at(ed.add_get_member_variable_node(REACT_INDEX_VAR),
                      x0 + 3840, y0 + 620))
    last = keep(_at(_node(ed, FN_SUB_II), x0 + 3840, y0 + 760))
    _connect(count_out, _pin(last, "A"))
    _set(last, "B", 1)
    safe = keep(_at(_node(ed, FN_CLAMP_II), x0 + 4080, y0 + 620))
    _connect(_pin(chosen, REACT_INDEX_VAR, is_input=False), _pin(safe, "Value"))
    _set(safe, "Min", 0)
    _connect(_pin(last, "ReturnValue", is_input=False), _pin(safe, "Max"))
    clip = keep(_at(_node(ed, FN_ARR_GET), x0 + 4320, y0 + 620))
    _connect(clips_out, _pin(clip, "TargetArray"))
    _connect(_pin(safe, "ReturnValue", is_input=False), _pin(clip, "Index"))

    # Through the owner's own AnimInstance, so this works on the player, on a
    # zombie and on a wendigo without knowing which it is holding.
    as_char = keep(_at(_palette(ed, NODE_CAST_CHARACTER), x0 + 3840, y0))
    _connect(owner_out, _pin(as_char, "Object"))
    for tail in arms:
        _connect(tail, _pin(as_char, "execute"))
    char_out = _loose_pin(as_char, "AsCharacter", is_input=False)
    mesh = keep(_at(ed.add_get_member_variable_node("Mesh", "/Script/Engine.Character"),
                    x0 + 4080, y0 + 340))
    _connect(char_out, _pin(mesh, "self"))
    anim = keep(_at(_node(ed, FN_ANIM_INSTANCE), x0 + 4320, y0 + 340))
    _connect(_pin(mesh, "Mesh", is_input=False), _pin(anim, "self"))

    play = keep(_at(_node(ed, FN_PLAY_SLOT), x0 + 4560, y0))
    _connect(_pin(anim, "ReturnValue", is_input=False), _pin(play, "self"))
    _connect(_pin(clip, "Item", is_input=False), _pin(play, "Asset"))
    _set(play, "SlotNodeName", HIT_SLOT)
    _set(play, "BlendInTime", COMBAT.hit_react_blend_s)
    _set(play, "BlendOutTime", COMBAT.hit_react_blend_s)
    _set(play, "InPlayRate", COMBAT.hit_react_rate)
    _set(play, "LoopCount", 1)
    _connect(BEL.find_then_pin(as_char), _pin(play, "execute"))

    # A deadline, not a countdown: nothing has to tick it.
    when = keep(_at(_node(ed, FN_ADD_FF), x0 + 4560, y0 + 480))
    _connect(now_out, _pin(when, "A"))
    _set(when, "B", COMBAT.hit_react_cooldown_s)
    rearm = keep(_at(ed.add_set_member_variable_node(NEXT_REACT_VAR),
                     x0 + 4820, y0))
    _connect(_pin(when, "ReturnValue", is_input=False), _pin(rearm, NEXT_REACT_VAR))
    _connect(BEL.find_then_pin(play), _pin(rearm, "execute"))

    after_play = BEL.find_then_pin(rearm)
    if HIT_REACT_PROBE:
        who = keep(_at(_node(ed, FN_GET_OWNER), x0 + 4820, y0 + 700))
        who_name = keep(_at(_node(ed, FN_DISPLAY_NAME), x0 + 5060, y0 + 700))
        _connect(_pin(who, "ReturnValue", is_input=False), _pin(who_name, "Object"))
        head = keep(_at(_node(ed, FN_CONCAT), x0 + 5300, y0 + 700))
        _set(head, "A", HIT_REACT_PROBE_PREFIX)
        _connect(_pin(who_name, "ReturnValue", is_input=False), _pin(head, "B"))
        idx_str = keep(_at(_node(ed, FN_INT_TO_STR), x0 + 5060, y0 + 840))
        _connect(_pin(safe, "ReturnValue", is_input=False), _pin(idx_str, "InInt"))
        tail_str = keep(_at(_node(ed, FN_CONCAT), x0 + 5300, y0 + 840))
        _set(tail_str, "A", " clip ")
        _connect(_pin(idx_str, "ReturnValue", is_input=False), _pin(tail_str, "B"))
        line = keep(_at(_node(ed, FN_CONCAT), x0 + 5540, y0 + 700))
        _connect(_pin(head, "ReturnValue", is_input=False), _pin(line, "A"))
        _connect(_pin(tail_str, "ReturnValue", is_input=False), _pin(line, "B"))
        say = keep(_at(_node(ed, FN_WARN), x0 + 5540, y0 + 480))
        _connect(_pin(line, "ReturnValue", is_input=False), _pin(say, "InString"))
        _connect(after_play, _pin(say, "execute"))
        after_play = BEL.find_then_pin(say)

    # --- and remember this frame's health, on every path ---------------------
    # Including the ones that did not react. Skipping it on the cooldown arm
    # would make the NEXT hit compare against a health from before this one and
    # fire the moment the cooldown lapses, with nothing new having happened.
    remember = keep(_at(ed.add_set_member_variable_node(PREV_HEALTH_VAR),
                        x0 + 5080, y0))
    _connect(_pin(now_h, "Health", is_input=False), _pin(remember, PREV_HEALTH_VAR))
    for tail in (after_play,
                 _pin(as_char, "CastFailed", is_input=False),
                 BEL.find_else_pin(have),
                 BEL.find_else_pin(cooled),
                 BEL.find_else_pin(took)):
        _connect(tail, _pin(remember, "execute"))

    ed.add_comment_to_nodes(
        f"FLINCH. Health dropped since last frame and is still above zero, so "
        f"whatever it was, this one lived: play one of {len(HIT_REACTION_CLIPS)} "
        f"one-second staggers into {HIT_SLOT} at {COMBAT.hit_react_rate}x, "
        f"chosen by which side LastHitFrom points at, and refuse another for "
        f"{COMBAT.hit_react_cooldown_s} s. {HIT_SLOT} is blended from "
        f"{UPPER_BODY_ROOT} down, so the chest and arms take the hit and the "
        f"legs never stop -- the player keeps running and a wanderer keeps "
        f"closing. Triggered by POLLING Health rather than called by the "
        f"shooter, so every source of damage reacts, including ones that do not "
        f"know this exists.",
        made)
    return made, BEL.find_then_pin(remember)


def hit_reactions(mesh_asset):
    """The six flinches on THIS mesh's own skeleton, in HIT_REACTION_CLIPS order.

    An AnimSequence belongs to exactly one skeleton, so there is no shared
    default that could be right for the adventurer, the zombie and the wendigo
    at once -- which is why this is resolved per character at build time,
    exactly as the hit-zone tables are.

    Where they live is derived from the mesh's own name (SKM_Zombie01 ->
    Anims/Zombie01/A_Zombie01_*), the layout build_retarget.py writes and
    npc_placement._creature reads. A mannequin-skinned checkout, which has no
    /Game/Sourced at all, falls back to Epic's originals -- they are on
    SK_Mannequin, so the skeleton test below passes for exactly the bodies they
    can drive and fails for the rest.

    ALL SIX OR NONE. The directional pick indexes this array by position, so a
    partial set is not a smaller set, it is the wrong clip for three of the four
    directions -- and unlike a missing asset, that failure is silent. Every
    candidate's skeleton is checked for the same reason: a clip on the wrong
    skeleton does not error, it simply never plays.
    """
    skeleton = mesh_asset.get_editor_property("skeleton") if mesh_asset else None
    if not skeleton:
        return []
    name = mesh_asset.get_name()
    family = name[4:] if name.startswith("SKM_") else name
    eas = _assets()
    for folder, prefix in ((f"{HIT_ANIM_ROOT}/{family}", f"A_{family}_"),
                           (HIT_ANIM_FALLBACK_DIR, "")):
        found = []
        for clip in HIT_REACTION_CLIPS:
            path = f"{folder}/{prefix}{clip}"
            asset = eas.load_asset(path) if eas.does_asset_exist(path) else None
            if (isinstance(asset, unreal.AnimSequence)
                    and asset.get_editor_property("skeleton") == skeleton):
                found.append(asset)
        if len(found) == len(HIT_REACTION_CLIPS):
            return found
    return []


def install_hit_reactions(bp, health_handle):
    """Write this character's own six reaction clips onto its HealthComponent.

    Per character and on the component template, for the reason
    install_hit_zones is: the clips describe *this* skeleton.

    Empty is a legal, logged outcome rather than an error. On a from-nothing
    build this runs before build_retarget.py has ever produced a creature's
    clips -- the weapons builder runs twice, see the build-order note in the
    player's-body section of CLAUDE.md -- and the graph guards an empty array:
    the character simply does not flinch, which is what it did before.
    """
    mesh = None
    for handle, _name in _handles(bp):
        obj = _component_object(handle)
        if isinstance(obj, unreal.SkeletalMeshComponent):
            mesh = obj
            break
    if mesh is None:
        raise RuntimeError(f"{bp.get_name()} has no SkeletalMeshComponent")
    clips = hit_reactions(mesh.get_editor_property("skeletal_mesh_asset"))
    comp = _component_object(health_handle)
    comp.set_editor_property(HIT_REACTIONS_VAR, clips)
    got = [a.get_name() for a in comp.get_editor_property(HIT_REACTIONS_VAR)]
    if got != [a.get_name() for a in clips]:
        raise RuntimeError(f"{bp.get_name()}'s hit reactions did not stick: {got}")
    if clips:
        _log(f"{bp.get_name()}: {len(clips)} hit reactions into {HIT_SLOT} "
             f"({got[0]} ... {got[-1]})")
    else:
        _log(f"note: {bp.get_name()} has no hit reactions on its skeleton -- it "
             f"will not flinch. Run Scripts/asset_pipeline/build_retarget.py, "
             f"then this builder again.")
    return clips
