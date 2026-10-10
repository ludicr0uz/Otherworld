"""BP_HealthComponent: Health/MaxHealth, damage bookkeeping, and the Tick
that drives death, respawn, hit reactions and the world-floor safety net.
The death, replacement and flinch fragments are authored in death.py,
replacement.py and hit_reaction.py; this module wires them together.
"""

from combat import health_native
from combat.damage import author_health_changed, replicate_health
from combat.debuff_drain import _author_debuff_drain
from combat.death import (
    CORPSE_SECONDS, PLAYER_RESPAWN_WAIT, _author_corpse, _author_death_collapse,
    _author_kill_count, _author_player_death,
)
from combat.game_state import DAMAGED_BY_PLAYER_VAR, LAST_DAMAGE_VAR, NEVER_DAMAGED
from combat.log import _log
from uebp.graph import (
    BEL, BGE, _apply_defaults, _assets, _connect, _create_blueprint, _events, _node, _palette,
    _pin, _post_physics_tick, _set, else_, out, then,
)
from uebp import net
from uebp.layout import arrange
from combat.hit_reaction import (
    NEXT_REACT_VAR, PREV_HEALTH_VAR, STEADY_VAR, _author_hit_reaction, _author_steady_gate,
)
from combat.hit_zones import HEAD_MULT_VAR, LIMB_MULT_VAR
from combat.paths import HEALTH_BP_PATH, ITEM_BP_PATH
from combat.player_kill import author_player_kill
from combat.player_respawn import author_player_respawn
from combat.replacement import _author_replacement
from combat.respawn import (
    RESPAWN_DELAY, RESPAWN_DELAY_VAR, _author_health_begin_play,
    _author_world_floor_net,
)
from combat.tuning import COMBAT
from Sound.sound_world import (
    _author_death_voice, _author_heartbeat, _author_hurt_voice, voice_defaults)
from loot.consts import BODY_ARRAYS
from loot.roll import declare_loot_vars
from uebp.nodes.health import FN_DIE, NODE_EVENT_DIED
from uebp.nodes.math import FN_LE_FF
from uebp.nodes.palette import MACRO_SWITCH_AUTHORITY_COMP
from uebp.vars import declare, defaults
from combat import health_vars as HV


def build_health_component(rebuild=True):
    """Health, plus what happens when it runs out.

    Health is a component rather than a variable on each character so that the
    shooter and the HUD share one lookup -- GetComponentByClass -> Cast ->
    Health -- that works on the player, on the NPC, and on anything given the
    component later.

    Death lives here too, and is driven by three defaults rather than by
    subclassing:

        DespawnOnDeath   this is a wanderer: at 0 HP count the kill, kill
                         the AI, let the body rot for CORPSE_SECONDS and,
                         RespawnDelay seconds on, spawn a replacement. False
                         on the player, whose body stays
                         where it fell until the level reopens.
        RespawnClass     what to spawn in the dead actor's place. Left empty on
                         the player; on a wanderer it is overwritten at
                         BeginPlay with the owner's OWN class, so each creature
                         respawns as itself rather than as whatever the shared
                         component template happened to name.

    Where the replacement appears is the RESPAWN_BAND: a random bearing and a
    random distance in the same 75-100 m annulus the level generator uses,
    measured from the player's current location and then snapped onto the
    navmesh. So a kill thins the pack for RESPAWN_DELAY seconds, then it is
    back to strength, every one at a distance the player can see coming.

    Because the replacement carries the same component with the same defaults,
    one death begets one respawn indefinitely with nothing tracking it.

    Damage is this component's own TakeHit (damage.py; C++, the native parent's
    since W3), which every
    blow calls and only the server runs, rather than the engine's ApplyDamage /
    Event AnyDamage. AnyDamage is an *Actor* event, so routing through it would
    mean authoring a graph on both characters -- and BP_ThirdPersonCharacter's
    graph is the Enhanced Input template, which the graph API cannot partially
    rebuild.

    What runs where, on a Tick every copy has (damage.py has what travels):

        the world-floor net, the drain     the server (and single player)
        the grunt, the heart, the flinch   every copy, off what was replicated
        Health at 0: Die (C++), which marks Dead   the server
        the death path, off OnDied, once       every copy: the cry and the collapse
            the kill, the replacement          the server
    """
    # The weapon-drop path casts the spawned actor to BP_WeaponItem, and a cast
    # node only appears in the palette for a class that is already loaded.
    if not _assets().load_asset(ITEM_BP_PATH):
        raise RuntimeError(f"could not load {ITEM_BP_PATH} for its cast node")

    # A child of the native base (health_native.py): Health, Dead, the blow
    # and the death's mark are C++.
    bp = _create_blueprint(HEALTH_BP_PATH, health_native.base_class())
    ed = BGE.get_graph_editor_by_name(bp, "EventGraph")
    health_native.reparent(bp, ed)
    # The reparent compiled the Blueprint: the graph is asked for again.
    ed = BGE.get_graph_editor_by_name(bp, "EventGraph")
    tick, begin = _events(ed, rebuild)

    declare(ed, HV.TABLE)
    # Corpse loot: the table loot/install.py fills, and what this body carries.
    declare_loot_vars(ed)
    # The respawn's, the hit boxes' and the flinch's (health_vars.py).
    declare(ed, HV.STATE)

    # SpawnOrigin used to hold where this actor started, back when a replacement
    # appeared near the dead one's own spawn point. It has to be removed
    # explicitly: this builder updates blueprints in place, so a variable it
    # simply stops declaring stays on the asset forever.
    ed.remove_member_variable("SpawnOrigin")

    _author_health_begin_play(ed, begin)
    author_health_changed(ed)

    # Health is the server's: only it writes one off or drains one. A
    # client's copy goes straight on to what it shows of the Health it is sent.
    owns = ed.add_macro_node(MACRO_SWITCH_AUTHORITY_COMP)
    _connect(then(tick), _pin(owns, "execute"))
    lost, write_off = _author_world_floor_net(ed, out(owns, "Authority"))

    # --- Tick: has it died this frame? ---------------------------------------
    health = ed.add_get_member_variable_node(HV.Health)
    dying = _node(ed, FN_LE_FF)
    _connect(out(health, HV.Health), _pin(dying, "A"))
    _set(dying, "B", 0.0)

    at_zero = ed.add_branch_node()
    _connect(out(dying), _pin(at_zero, "Condition"))
    # Both arms of the net fall through the debuff drain to here. The Health
    # getter above is pure, so it is read at *this* branch -- after the net's
    # write and the drain's -- and a wanderer written off this frame, or a
    # starving player drained past zero, dies this frame.
    drained = (*_author_debuff_drain(ed, tick, (then(write_off), else_(lost))),
               out(owns, "Remote"))
    # A blow is grunted at on the way (voice.py): before the death branch, so
    # it is heard on a frame the player lives through and on no other.
    # ...and, badly hurt, the player's heart is heard.
    for e in _author_heartbeat(ed, _author_hurt_voice(ed, drained)):
        _connect(e, _pin(at_zero, "execute"))

    # --- Tick: took a hit and lived --------------------------------------
    # The other arm of the same branch, and that is the whole "and survived":
    # this exec pin is reached only on frames the owner is still above zero.
    # ...unless its sights are up (Steady): then the hit is only remembered.
    steady, flinch = _author_steady_gate(ed, else_(at_zero))
    _author_hit_reaction(ed, flinch, skips=(steady,))

    # At zero, the server says so, once: Die (C++) marks Dead, which
    # replicates, and tells OnDied here; a client's call does nothing, and
    # its OnDied comes when Dead arrives.
    dead_get = ed.add_get_member_variable_node(HV.Dead)
    already = ed.add_branch_node()
    _connect(out(dead_get, HV.Dead), _pin(already, "Condition"))
    _connect(then(at_zero), _pin(already, "execute"))
    die = _node(ed, FN_DIE)
    _connect(else_(already), _pin(die, "execute"))

    # --- OnDied: what dying is, once on each machine -------------------------
    # DeathPlayed is this machine's own latch, beside the base's: nothing
    # that tells the event twice runs the path twice.
    died = _palette(ed, NODE_EVENT_DIED)
    played_get = ed.add_get_member_variable_node(HV.DeathPlayed)
    once = ed.add_branch_node()
    _connect(out(played_get, HV.DeathPlayed), _pin(once, "Condition"))
    _connect(then(died), _pin(once, "execute"))
    played = ed.add_set_member_variable_node(HV.DeathPlayed)
    _set(played, HV.DeathPlayed, True)
    _connect(else_(once), _pin(played, "execute"))

    despawn_get = ed.add_get_member_variable_node(HV.DespawnOnDeath)
    should = ed.add_branch_node()
    _connect(out(despawn_get, HV.DespawnOnDeath), _pin(should, "Condition"))
    for e in _author_death_voice(ed, (then(played),)):
        _connect(e, _pin(should, "execute"))

    # --- count it, leave a corpse, and later a replacement -------------------------
    counted = _author_kill_count(ed, then(should))

    # The corpse straight off the count: dying does not wait for the
    # replacement, which comes RESPAWN_DELAY seconds later (replacement.py).
    corpsed = _author_corpse(ed, counted)

    # Both arms of the death branch collapse the same way and through the same
    # nodes: the player straight off the branch, the wanderer once its
    # brain is gone.
    fell, no_body = _author_death_collapse(ed, (corpsed, else_(should)))
    # ...and only the player gets a menu out of it. A second read of
    # DespawnOnDeath rather than routing the two arms separately, so there is
    # exactly one place that says what dying looks like.
    mine_again = ed.add_get_member_variable_node(HV.DespawnOnDeath)
    is_player = ed.add_branch_node()
    _connect(out(mine_again, HV.DespawnOnDeath), _pin(is_player, "Condition"))
    for tail in (fell, no_body):
        _connect(tail, _pin(is_player, "execute"))
    # A player's death is first credited to the player who struck the last
    # blow, if one did (player_kill.py): the wanderer's count's twin.
    shared = _author_player_death(ed, author_player_kill(ed, else_(is_player)))
    # ...which in standalone ends there, paused. On a server the player is
    # given a new body (the mode table's death row).
    author_player_respawn(ed, [shared])
    # ...and only a wanderer a replacement, once it is down, and only from
    # the server: a client's copy of the body spawns nothing.
    spawns = ed.add_macro_node(MACRO_SWITCH_AUTHORITY_COMP)
    _connect(then(is_player), _pin(spawns, "execute"))
    _author_replacement(ed, out(spawns, "Authority"))

    ed.add_comment_to_nodes(
        f"At 0 HP the server calls Die, which marks Dead (it replicates). OnDied, once "
        f"on each machine: (if DespawnOnDeath) count the kill and "
        f"leave this one on the ground for {CORPSE_SECONDS:.0f} s; its "
        f"replacement follows {RESPAWN_DELAY:.0f} s later. The player's copy "
        "has DespawnOnDeath false and no RespawnClass, so none of that runs "
        "on them.",
        [health, dying, at_zero, dead_get, already, die, died, played_get, once, played,
         despawn_get, should, mine_again, is_player, spawns])

    # After every declare above: a re-declared variable loses its replication.
    replicate_health(bp)
    # What a body carries is the server's, and every machine's loot window
    # shows it: a wanderer's roll, a dead player's gear.
    for var in BODY_ARRAYS:
        net.replicate(bp, var)
    _post_physics_tick(bp)
    arrange(ed)
    if not BEL.compile_blueprint(bp):
        raise RuntimeError("BP_HealthComponent failed to compile")
    _apply_defaults(bp, {**defaults(HV.TABLE), **defaults(HV.NATIVE), **voice_defaults(),
        RESPAWN_DELAY_VAR: RESPAWN_DELAY,
        HV.PlayerRespawnWait: PLAYER_RESPAWN_WAIT,
        # Far enough in the past that nothing counts as recently hurt at level
        # start -- a zero here would float every wanderer's bar for the first
        # five seconds of the game.
        LAST_DAMAGE_VAR: NEVER_DAMAGED,
        DAMAGED_BY_PLAYER_VAR: False,
        HEAD_MULT_VAR: COMBAT.head_multiplier,
        LIMB_MULT_VAR: COMBAT.limb_multiplier,
        # Seeded at full health, so the very first Tick compares like with like
        # and nobody flinches on the frame they spawn. (A wanderer's real
        # maximum is written over this at possession -- see
        # _author_stats_and_voice in build_npc_blueprints.py -- and the poll
        # only ever looks for a DECREASE, so the correction cannot fire one.)
        PREV_HEALTH_VAR: COMBAT.start_health,
        # Zero, not NEVER_DAMAGED: world time starts at zero and this is a
        # deadline, so anything at or before it means "ready now".
        NEXT_REACT_VAR: 0.0,
        STEADY_VAR: False,
    })
    # The component replicates: a class default, written after a compile.
    net.replicate_component(bp)
    if not BEL.compile_blueprint(bp):
        raise RuntimeError("BP_HealthComponent failed to compile")
    _assets().save_loaded_asset(bp)
    _log(f"built {HEALTH_BP_PATH} (Health = MaxHealth = {COMBAT.start_health})")
    return bp
