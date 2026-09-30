"""The swing: range and cooldown check, the attack montage, the damage and
its direction, and the impact sound.
"""

from combat.game_state import LAST_DAMAGE_VAR
from forest_generator.npc_placement import (
    NPC_MELEE_BLEND_S, NPC_MELEE_DAMAGE, NPC_MELEE_INTERVAL_S,
    NPC_MELEE_MONTAGE, NPC_MELEE_MONTAGE_FALLBACK, NPC_MELEE_RANGE_CM,
)
from npc.paths import (
    HEALTH_BP_PATH, HEALTH_CLASS_PATH, HIT_DAMAGE_VAR, HIT_SOUNDS_VAR, INF,
    LAST_HIT_FROM_VAR, MELEE_SLOT,
)
from npc.nodes import (
    FN_ACTOR_LOC, FN_ADD_FF, FN_AND, FN_ANIM_INSTANCE, FN_CLAMP, FN_DISTANCE,
    FN_GET_COMP, FN_GET_PAWN, FN_GET_PLAYER_PAWN, FN_GE_FF, FN_LE_FF,
    FN_NORMAL, FN_PLAY_SLOT, FN_SUB_FF, FN_SUB_VV, FN_TIME_SECONDS,
    NODE_CAST_CHARACTER, NODE_CAST_HEALTH,
)
from npc.graph import (
    _asset_sub, _at, BEL, _connect, _log, _loose_pin, _node, _palette, _pin,
    _resolve, _set,
)
from npc.block import _author_block_check
from npc.combat_trace import _author_melee_trace
from npc.sound import _author_random_sound


# An object pin holds the full object path (package + object name), and it
# normalises whatever is written into that form -- so write it that way, or the
# read-back guard in _set() reports a mismatch that is not one.
#
# Resolved when the graph is authored rather than at import, because which of
# the two montages exists depends on whether the asset pipeline has run, and
# _resolve needs the editor's asset subsystem.
def _melee_montage_object():
    return _resolve(NPC_MELEE_MONTAGE, NPC_MELEE_MONTAGE_FALLBACK, "melee montage")


def _author_melee(ed, after_move, delay, x0, y0, melee_anim=None):
    """Swing at the player when the chase has closed the distance.

    ``after_move`` is every exec pin that runs the check -- now the tree's
    Swing step (BT_Swing, npc/steps.py), which follows its Chase step -- and
    ``delay`` is the node every exit runs into: the step's StepResult write.

    The check runs once per pass of the tree's Hunt branch, every
    NPC_REPATH_SECONDS, with no Tick event of its own: the tree is already the
    NPC's heartbeat, and a second one would only add a way for the two to
    disagree about whether the chase is still running.

        MoveToActor --> [in range AND off cooldown?]
                          true  --> NextAttackTime = now + interval
                                --> play MM_Attack_01 on the upper body
                                --> HitDamage = NPC_MELEE_DAMAGE, or less
                                    on the player's guard (npc/block.py)
                                --> player Health -= HitDamage
                                --> player LastDamageTime = now (the HUD's
                                    save-and-exit is called off by a hit)
                          false -------------------------------------> Delay

    Range is centre-to-centre between the two capsules, which is why
    NPC_MELEE_RANGE_CM (200) has to exceed NPC_ACCEPTANCE_RADIUS_CM (120): the
    move order stops the NPC at the acceptance radius, and an NPC that parks
    itself outside its own reach never lands a hit.

    The cooldown is wall-clock rather than a counter of loop iterations so the
    swing rate is independent of NPC_REPATH_SECONDS -- and it lives on the
    *controller*, so five wanderers each keep their own, rather than sharing one
    and machine-gunning the player in lockstep.

    Damage is applied by writing Health on the player's BP_HealthComponent,
    which is exactly what the pellets do (see _author_impact in
    build_weapons_and_combat.py). Routing through ApplyDamage/AnyDamage instead
    would need a graph on BP_ThirdPersonCharacter, whose Enhanced Input template
    graph the Python API cannot partially rebuild.

    Returns the nodes it made (for the comment box), or None when
    BP_HealthComponent is absent -- a project where the weapons have never been
    built still gets a chasing NPC, just not a damaging one.
    """
    eas = _asset_sub()
    if not eas.does_asset_exist(HEALTH_BP_PATH):
        _log(f"note: {HEALTH_BP_PATH} not found — melee skipped, the NPC will "
             f"chase but not attack (run build_weapons_and_combat.py first)")
        return None
    # A cast node only appears in the palette for a class that is already
    # loaded; without this the node name reads like a typo rather than a
    # missing asset.
    if not eas.load_asset(HEALTH_BP_PATH):
        raise RuntimeError(f"could not load {HEALTH_BP_PATH} for its cast node")

    made = []

    def keep(n):
        made.append(n)
        return n

    # --- is the player within reach? ----------------------------------------
    self_pawn = keep(_at(_node(ed, FN_GET_PAWN), x0, y0 + 260))
    self_loc = keep(_at(_node(ed, FN_ACTOR_LOC), x0 + 240, y0 + 260))
    _connect(_pin(self_pawn, "ReturnValue", is_input=False), _pin(self_loc, "self"))

    player = keep(_at(_node(ed, FN_GET_PLAYER_PAWN), x0, y0 + 420))
    _set(player, "PlayerIndex", 0)
    player_out = _pin(player, "ReturnValue", is_input=False)
    player_loc = keep(_at(_node(ed, FN_ACTOR_LOC), x0 + 240, y0 + 420))
    _connect(player_out, _pin(player_loc, "self"))

    gap = keep(_at(_node(ed, FN_DISTANCE), x0 + 480, y0 + 340))
    _connect(_pin(self_loc, "ReturnValue", is_input=False), _pin(gap, "V1"))
    _connect(_pin(player_loc, "ReturnValue", is_input=False), _pin(gap, "V2"))

    in_range = keep(_at(_node(ed, FN_LE_FF), x0 + 720, y0 + 340))
    _connect(_pin(gap, "ReturnValue", is_input=False), _pin(in_range, "A"))
    _set(in_range, "B", NPC_MELEE_RANGE_CM)

    # --- has this NPC's cooldown expired? ------------------------------------
    now = keep(_at(_node(ed, FN_TIME_SECONDS), x0 + 480, y0 + 560))
    now_out = _pin(now, "ReturnValue", is_input=False)
    next_at = keep(_at(ed.add_get_member_variable_node("NextAttackTime"),
                       x0 + 480, y0 + 680))
    ready = keep(_at(_node(ed, FN_GE_FF), x0 + 720, y0 + 560))
    _connect(now_out, _pin(ready, "A"))
    _connect(_pin(next_at, "NextAttackTime", is_input=False), _pin(ready, "B"))

    both = keep(_at(_node(ed, FN_AND), x0 + 960, y0 + 400))
    _connect(_pin(in_range, "ReturnValue", is_input=False), _pin(both, "A"))
    _connect(_pin(ready, "ReturnValue", is_input=False), _pin(both, "B"))

    swing = keep(_at(ed.add_branch_node(), x0 + 1200, y0))
    _connect(_pin(both, "ReturnValue", is_input=False), _pin(swing, "Condition"))
    for tail in after_move:
        _connect(tail, _pin(swing, "execute"))
    # Not in range, or still on cooldown: straight on to the re-path delay.
    _connect(BEL.find_else_pin(swing), BEL.find_execute_pin(delay))

    # --- arm the next swing --------------------------------------------------
    when = keep(_at(_node(ed, FN_ADD_FF), x0 + 1440, y0 + 300))
    _connect(now_out, _pin(when, "A"))
    _set(when, "B", NPC_MELEE_INTERVAL_S)
    arm = keep(_at(ed.add_set_member_variable_node("NextAttackTime"),
                   x0 + 1680, y0))
    _connect(_pin(when, "ReturnValue", is_input=False), _pin(arm, "NextAttackTime"))
    _connect(BEL.find_then_pin(swing), _pin(arm, "execute"))

    # --- play the swing ------------------------------------------------------
    # The montage goes through the pawn's own AnimInstance, so it animates
    # whichever body this controller happens to possess rather than assuming
    # BP_ForestWanderer.
    as_char = keep(_at(_palette(ed, NODE_CAST_CHARACTER), x0 + 1920, y0))
    _connect(_pin(self_pawn, "ReturnValue", is_input=False), _pin(as_char, "Object"))
    _connect(BEL.find_then_pin(arm), _pin(as_char, "execute"))
    char_out = _loose_pin(as_char, "AsCharacter", is_input=False)

    mesh = keep(_at(ed.add_get_member_variable_node("Mesh", "/Script/Engine.Character"),
                    x0 + 1920, y0 + 300))
    _connect(char_out, _pin(mesh, "self"))

    anim = keep(_at(_node(ed, FN_ANIM_INSTANCE), x0 + 2160, y0 + 300))
    _connect(_pin(mesh, "Mesh", is_input=False), _pin(anim, "self"))

    montage = keep(_at(_node(ed, FN_PLAY_SLOT), x0 + 2400, y0))
    _connect(_pin(anim, "ReturnValue", is_input=False), _pin(montage, "self"))
    _set(montage, "Asset", melee_anim or _melee_montage_object())
    _set(montage, "SlotNodeName", MELEE_SLOT)
    _set(montage, "BlendInTime", NPC_MELEE_BLEND_S)
    _set(montage, "BlendOutTime", NPC_MELEE_BLEND_S)
    _connect(BEL.find_then_pin(as_char), _pin(montage, "execute"))

    # --- land the hit --------------------------------------------------------
    comp = keep(_at(_node(ed, FN_GET_COMP), x0 + 2400, y0 + 300))
    _connect(player_out, _pin(comp, "self"))
    _pin(comp, "ComponentClass").set_pin_value(HEALTH_CLASS_PATH)

    hit = keep(_at(_palette(ed, NODE_CAST_HEALTH), x0 + 2640, y0))
    _connect(_pin(comp, "ReturnValue", is_input=False), _pin(hit, "Object"))
    _connect(BEL.find_then_pin(montage), _pin(hit, "execute"))
    as_health = _loose_pin(hit, "AsBPHealthComponent", is_input=False)

    # --- the bearing: which way the swing comes from -----------------------
    # The unit vector from the player to the wanderer that swung. The guard
    # reads it to decide whether the swing met the player's front, and it is
    # stored below as LastHitFrom for the flinch.
    toward = keep(_at(_node(ed, FN_SUB_VV), x0 + 3600, y0 + 300))
    _connect(_pin(self_loc, "ReturnValue", is_input=False), _pin(toward, "A"))
    _connect(_pin(player_loc, "ReturnValue", is_input=False), _pin(toward, "B"))
    bearing = keep(_at(_node(ed, FN_NORMAL), x0 + 3840, y0 + 300))
    _connect(_pin(toward, "ReturnValue", is_input=False), _pin(bearing, "A"))
    bearing_out = _pin(bearing, "ReturnValue", is_input=False)

    # --- how much of it lands: the player's guard --------------------------
    # Its nodes stay out of `made`: they have their own comment box.
    _, guarded = _author_block_check(ed, BEL.find_then_pin(hit), player_out,
                                     bearing_out, x0 + 2880, y0 - 900)

    read = keep(_at(ed.add_get_member_variable_node("Health", HEALTH_CLASS_PATH),
                    x0 + 2880, y0 + 300))
    _connect(as_health, _pin(read, "self"))
    hurt = keep(_at(_node(ed, FN_SUB_FF), x0 + 3120, y0 + 300))
    _connect(_pin(read, "Health", is_input=False), _pin(hurt, "A"))
    dealt = keep(_at(ed.add_get_member_variable_node(HIT_DAMAGE_VAR),
                     x0 + 2880, y0 + 420))
    _connect(_pin(dealt, HIT_DAMAGE_VAR, is_input=False), _pin(hurt, "B"))
    floor = keep(_at(_node(ed, FN_CLAMP), x0 + 3360, y0 + 300))
    _connect(_pin(hurt, "ReturnValue", is_input=False), _pin(floor, "Value"))
    _set(floor, "Min", 0.0)
    _set(floor, "Max", INF)
    write = keep(_at(ed.add_set_member_variable_node("Health", HEALTH_CLASS_PATH),
                     x0 + 3600, y0))
    _connect(as_health, _pin(write, "self"))
    _connect(_pin(floor, "ReturnValue", is_input=False), _pin(write, "Health"))
    for tail in guarded:
        _connect(tail, _pin(write, "execute"))

    # --- and which way it came from ------------------------------------------
    # The player's flinch is picked by direction, and a punch has no impact
    # normal to read it off -- so it is stated: the bearing above.  Whichever of
    # the ten lands the blow writes its own bearing, so being surrounded reads
    # as being hit from all sides rather than as one repeated stagger.
    came_from = keep(_at(ed.add_set_member_variable_node(LAST_HIT_FROM_VAR,
                                                          HEALTH_CLASS_PATH),
                         x0 + 3840, y0))
    _connect(as_health, _pin(came_from, "self"))
    _connect(bearing_out, _pin(came_from, LAST_HIT_FROM_VAR))

    # --- and when: the moment the player was last hit ------------------------
    # The HUD's save-and-exit countdown reads it, because being hit calls the
    # exit off. A time rather than a flag: nothing has to clear it, and a drop
    # in Health would also count the starvation drain, which is not a hit.
    struck = keep(_at(ed.add_set_member_variable_node(LAST_DAMAGE_VAR,
                                                      HEALTH_CLASS_PATH),
                      x0 + 4080, y0))
    _connect(as_health, _pin(struck, "self"))
    _connect(_pin(now, "ReturnValue", is_input=False), _pin(struck, LAST_DAMAGE_VAR))
    _connect(BEL.find_then_pin(came_from), _pin(struck, "execute"))

    # --- and, when the combat trace is on, say who did it -------------------
    # Between the hit and its bearing, so the line quotes the health just
    # written. Every exit of the trace, logged or not, carries on to the bearing.
    # The trace's nodes stay out of `made`: they have their own comment box.
    _, trace_tails = _author_melee_trace(
        ed, BEL.find_then_pin(write),
        _pin(self_pawn, "ReturnValue", is_input=False),
        _pin(self_loc, "ReturnValue", is_input=False), player_out,
        _pin(player_loc, "ReturnValue", is_input=False),
        _pin(gap, "ReturnValue", is_input=False), as_health,
        x0 + 3600, y0 + 1400)
    for tail in trace_tails:
        _connect(tail, _pin(came_from, "execute"))

    # --- and make a noise landing it ----------------------------------------
    # At the PLAYER's location rather than the wanderer's: the sound is the
    # impact, and the impact happens where the hit lands. With ten wanderers
    # around one player the difference is audible -- from the attacker it
    # smears around the listener, from the target it is one solid thump in
    # front of them.
    thud, after_thud = _author_random_sound(
        ed, HIT_SOUNDS_VAR, _pin(player_loc, "ReturnValue", is_input=False),
        BEL.find_then_pin(struck), x0 + 4320, y0)
    made.extend(thud)

    # Every exit -- hit, missing health component, not a Character -- has to
    # reach the Delay, or the chase loop ends on the first swing and the NPC
    # stands still forever.  A cast's failure pin left dangling is exactly that
    # bug, and it only shows up in a level where the player has no health
    # component.
    for tail in (after_thud,
                 _pin(hit, "CastFailed", is_input=False),
                 _pin(as_char, "CastFailed", is_input=False)):
        _connect(tail, BEL.find_execute_pin(delay))

    return made
