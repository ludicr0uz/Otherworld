"""The swing: range and cooldown check, the attack montage, the damage and
its direction, the impact sound, and what the hit can leave on the player
(the on-hit effects: survival/on_hit.py).
"""

from combat.damage import hit as take_hit
from forest_generator.npc_placement import (
    NPC_MELEE_BLEND_S, NPC_MELEE_MONTAGE, NPC_MELEE_MONTAGE_FALLBACK,
)
from npc.paths import (
    ATTACK_VOICES_VAR, HEALTH_BP_PATH, HEALTH_CLASS_PATH, HIT_DAMAGE_VAR, HIT_SOUNDS_VAR,
    MELEE_SLOT)
from npc.graph import _log
from net.players import nearest_living_player, player_pin
from uebp.graph import (
    BEL, _assets, _connect, _loose_pin, _node, _palette, _pin, _resolve, _set, else_, out,
    then)
from npc.block import _author_block_check
from npc.combat_trace import _author_melee_trace
from Sound.play import _author_random_sound
from npc.tuned import tuned
from survival.on_hit_graph import _author_on_hit
from uebp.nodes.actor import (
    FN_ACTOR_LOC, FN_ANIM_INSTANCE, FN_GET_COMP, FN_GET_INSTIGATOR_CONTROLLER, FN_GET_PAWN,
    FN_PLAY_SLOT)
from uebp.nodes.math import (
    FN_ADD_FF, FN_AND, FN_DISTANCE, FN_GE_FF, FN_LE_FF, FN_NORMAL, FN_SUB_VV)
from uebp.nodes.palette import NODE_CAST_CHARACTER, NODE_CAST_HEALTH
from uebp.nodes.system import FN_TIME_SECONDS
from uebp import props as EP
from npc import controller_vars as NV


# An object pin holds the full object path (package + object name), and it
# normalises whatever is written into that form -- so write it that way, or the
# read-back guard in _set() reports a mismatch that is not one.
#
# Resolved when the graph is authored rather than at import, because which of
# the two montages exists depends on whether the asset pipeline has run, and
# _resolve needs the editor's asset subsystem.
def _melee_montage_object():
    return _resolve(NPC_MELEE_MONTAGE, NPC_MELEE_MONTAGE_FALLBACK, "melee montage")


def _author_melee(ed, after_move, delay, melee_anim=None, on_hit=(),
                  clears=()):
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
                                --> HitDamage = TuneMeleeDamage, or less
                                    on the player's guard (npc/block.py)
                                --> player Health -= HitDamage
                                --> player LastDamageTime = now (the HUD's
                                    save-and-exit is called off by a hit)
                                --> roll ``on_hit``, this creature's on-hit
                                    effects, onto the player (a blocked
                                    swing rolls them too: it still lands)
                                --> each of ``clears`` = 0: the controller's
                                    own timers a landed blow starts over
                                    (the fire's hold: npc/ward_roar.py)
                          false -------------------------------------> Delay

    Range is centre-to-centre between the two capsules, which is why
    TuneMeleeRange (200) has to exceed NPC_ACCEPTANCE_RADIUS_CM (120): the
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
    eas = _assets()
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
    self_pawn = keep(_node(ed, FN_GET_PAWN))
    self_loc = keep(_node(ed, FN_ACTOR_LOC))
    _connect(out(self_pawn), _pin(self_loc, "self"))

    player = keep(nearest_living_player(ed, out(self_loc)))
    player_out = player_pin(player)
    player_loc = keep(_node(ed, FN_ACTOR_LOC))
    _connect(player_out, _pin(player_loc, "self"))

    gap = keep(_node(ed, FN_DISTANCE))
    _connect(out(self_loc), _pin(gap, "V1"))
    _connect(out(player_loc), _pin(gap, "V2"))

    in_range = keep(_node(ed, FN_LE_FF))
    _connect(out(gap), _pin(in_range, "A"))
    reach, reach_out = tuned(ed, "melee_range_cm")
    keep(reach)
    _connect(reach_out, _pin(in_range, "B"))

    # --- has this NPC's cooldown expired? ------------------------------------
    now = keep(_node(ed, FN_TIME_SECONDS))
    now_out = out(now)
    next_at = keep(ed.add_get_member_variable_node(NV.NextAttackTime))
    ready = keep(_node(ed, FN_GE_FF))
    _connect(now_out, _pin(ready, "A"))
    _connect(out(next_at, NV.NextAttackTime), _pin(ready, "B"))

    both = keep(_node(ed, FN_AND))
    _connect(out(in_range), _pin(both, "A"))
    _connect(out(ready), _pin(both, "B"))

    swing = keep(ed.add_branch_node())
    _connect(out(both), _pin(swing, "Condition"))
    for tail in after_move:
        _connect(tail, _pin(swing, "execute"))
    # Not in range, or still on cooldown: straight on to the re-path delay.
    _connect(else_(swing), BEL.find_execute_pin(delay))

    # --- arm the next swing --------------------------------------------------
    when = keep(_node(ed, FN_ADD_FF))
    _connect(now_out, _pin(when, "A"))
    gap_s, gap_out = tuned(ed, "melee_interval_s")
    keep(gap_s)
    _connect(gap_out, _pin(when, "B"))
    arm = keep(ed.add_set_member_variable_node(NV.NextAttackTime))
    _connect(out(when), _pin(arm, NV.NextAttackTime))
    _connect(then(swing), _pin(arm, "execute"))

    # --- play the swing ------------------------------------------------------
    # The montage goes through the pawn's own AnimInstance, so it animates
    # whichever body this controller happens to possess rather than assuming
    # BP_ForestWanderer.
    # ...and is heard: one of its AttackVoices as the swing starts, whether
    # or not it lands. Empty on a creature with none: silence.
    snarl, snarled = _author_random_sound(ed, ATTACK_VOICES_VAR, out(self_loc), then(arm))
    made.extend(snarl)
    as_char = keep(_palette(ed, NODE_CAST_CHARACTER))
    _connect(out(self_pawn), _pin(as_char, "Object"))
    _connect(snarled, _pin(as_char, "execute"))
    char_out = _loose_pin(as_char, "AsCharacter", is_input=False)

    mesh = keep(ed.add_get_member_variable_node(EP.MESH, "/Script/Engine.Character"))
    _connect(char_out, _pin(mesh, "self"))

    anim = keep(_node(ed, FN_ANIM_INSTANCE))
    _connect(out(mesh, "Mesh"), _pin(anim, "self"))

    montage = keep(_node(ed, FN_PLAY_SLOT))
    _connect(out(anim), _pin(montage, "self"))
    _set(montage, "Asset", melee_anim or _melee_montage_object())
    _set(montage, "SlotNodeName", MELEE_SLOT)
    _set(montage, "BlendInTime", NPC_MELEE_BLEND_S)
    _set(montage, "BlendOutTime", NPC_MELEE_BLEND_S)
    _connect(then(as_char), _pin(montage, "execute"))

    # --- land the hit --------------------------------------------------------
    comp = keep(_node(ed, FN_GET_COMP))
    _connect(player_out, _pin(comp, "self"))
    _pin(comp, "ComponentClass").set_pin_value(HEALTH_CLASS_PATH)

    hit = keep(_palette(ed, NODE_CAST_HEALTH))
    _connect(out(comp), _pin(hit, "Object"))
    _connect(then(montage), _pin(hit, "execute"))
    as_health = _loose_pin(hit, "AsBPHealthComponent", is_input=False)

    # --- the bearing: which way the swing comes from -----------------------
    # The unit vector from the player to the wanderer that swung. The guard
    # reads it to decide whether the swing met the player's front, and it is
    # stored below as LastHitFrom for the flinch.
    toward = keep(_node(ed, FN_SUB_VV))
    _connect(out(self_loc), _pin(toward, "A"))
    _connect(out(player_loc), _pin(toward, "B"))
    bearing = keep(_node(ed, FN_NORMAL))
    _connect(out(toward), _pin(bearing, "A"))
    bearing_out = out(bearing)

    # --- how much of it lands: the player's guard --------------------------
    # Its nodes stay out of `made`: they have their own comment box.
    _, guarded = _author_block_check(ed, then(hit), player_out, bearing_out)

    # The player takes it: their health component's TakeHit (combat/damage.py),
    # which only the server runs, as only the server runs this controller.
    #
    # Which way it came from: the player's flinch is picked by direction, and a
    # punch has no impact normal to read it off -- so it is stated: the bearing
    # above.  Whichever of the ten lands the blow states its own bearing, so
    # being surrounded reads as being hit from all sides rather than as one
    # repeated stagger.
    #
    # When: TakeHit stamps the moment the player was last hit. The save-and-exit
    # countdown reads it, because being hit calls the exit off. A time rather
    # than a flag: nothing has to clear it, and a drop in Health would also
    # count the starvation drain, which is not a hit.
    #
    # Who and with what: this wanderer's controller, and the wanderer.
    dealt = keep(ed.add_get_member_variable_node(HIT_DAMAGE_VAR))
    who = keep(_node(ed, FN_GET_INSTIGATOR_CONTROLLER))
    _connect(out(self_pawn), _pin(who, "self"))
    struck_out, struck = take_hit(ed, as_health, out(dealt, HIT_DAMAGE_VAR), bearing_out,
                                  out(who), out(self_pawn), guarded)
    keep(struck)

    # --- and, when the combat trace is on, say who did it -------------------
    # After the hit, so the line quotes the health just written. Every exit of
    # the trace, logged or not, carries on to the thud.
    # The trace's nodes stay out of `made`: they have their own comment box.
    _, trace_tails = _author_melee_trace(
        ed, struck_out,
        out(self_pawn),
        out(self_loc), player_out,
        out(player_loc),
        out(gap), as_health)

    # --- and make a noise landing it ----------------------------------------
    # At the PLAYER's location rather than the wanderer's: the sound is the
    # impact, and the impact happens where the hit lands. With ten wanderers
    # around one player the difference is audible -- from the attacker it
    # smears around the listener, from the target it is one solid thump in
    # front of them.
    thud, after_thud = _author_random_sound(ed, HIT_SOUNDS_VAR, out(player_loc),
                                            list(trace_tails))
    made.extend(thud)

    # --- and the timers it starts over --------------------------------------
    for name in clears:
        cleared = keep(ed.add_set_member_variable_node(name))
        _set(cleared, name, 0.0)
        _connect(after_thud, _pin(cleared, "execute"))
        after_thud = then(cleared)

    # --- and what it leaves behind -------------------------------------------
    # Its nodes stay out of `made`: they have their own comment box.
    _, after_effects = _author_on_hit(ed, after_thud, player_out, on_hit)

    # Every exit -- hit, missing health component, not a Character -- has to
    # reach the Delay, or the chase loop ends on the first swing and the NPC
    # stands still forever.  A cast's failure pin left dangling is exactly that
    # bug, and it only shows up in a level where the player has no health
    # component.
    for tail in (*after_effects, out(hit, "CastFailed"), out(as_char, "CastFailed")):
        _connect(tail, BEL.find_execute_pin(delay))

    return made
