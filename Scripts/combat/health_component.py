"""BP_HealthComponent: Health/MaxHealth, damage bookkeeping, and the Tick
that drives death, respawn, hit reactions and the world-floor safety net.
The death, replacement and flinch fragments are authored in death.py,
replacement.py and hit_reaction.py; this module wires them together.
"""

import unreal

from combat.debuff_drain import _author_debuff_drain
from combat.death import (
    CORPSE_SECONDS, _author_corpse, _author_death_collapse,
    _author_kill_count, _author_player_death,
)
from combat.game_state import (
    DAMAGED_BY_PLAYER_VAR, LAST_DAMAGE_VAR, NEVER_DAMAGED, NPC_ID_VAR,
    SPAWNED_AT_VAR,
)
from combat.log import _log
from uebp.graph import (
    BEL, BGE, _apply_defaults, _assets, _connect, _create_blueprint, _declare, _events,
    _float_type, _node, _pin, _post_physics_tick, _set, _struct_type, else_, out, then)
from uebp.layout import arrange
from combat.hit_reaction import (
    HIT_REACTIONS_VAR, LAST_HIT_FROM_VAR, NEXT_REACT_VAR, PREV_HEALTH_VAR,
    REACT_INDEX_VAR, STEADY_VAR, _author_hit_reaction, _author_steady_gate,
)
from combat.hit_zones import (
    HEAD_BONES_VAR, HEAD_MULT_VAR, LIMB_BONES_VAR, LIMB_MULT_VAR,
)
from combat.paths import HEALTH_BP_PATH, ITEM_BP_PATH
from combat.replacement import _author_replacement
from combat.respawn import (
    RESPAWN_DELAY, RESPAWN_DELAY_VAR, _author_health_begin_play,
    _author_world_floor_net,
)
from combat.tuning import COMBAT
from loot.roll import declare_loot_vars
from uebp.nodes.math import FN_LE_FF


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

    Damage is applied by the weapon writing Health directly rather than through
    ApplyDamage / Event AnyDamage. AnyDamage is an *Actor* event, so routing
    through it would mean authoring a graph on both characters -- and
    BP_ThirdPersonCharacter's graph is the Enhanced Input template, which the
    graph API cannot partially rebuild.
    """
    # The weapon-drop path casts the spawned actor to BP_WeaponItem, and a cast
    # node only appears in the palette for a class that is already loaded.
    if not _assets().load_asset(ITEM_BP_PATH):
        raise RuntimeError(f"could not load {ITEM_BP_PATH} for its cast node")

    bp = _create_blueprint(HEALTH_BP_PATH, unreal.ActorComponent)
    ed = BGE.get_graph_editor_by_name(bp, "EventGraph")
    tick, begin = _events(ed, rebuild)

    for name in ("Health", "MaxHealth", LAST_DAMAGE_VAR):
        _declare(ed, name, _float_type())
    for name in ("Dead", "DespawnOnDeath", DAMAGED_BY_PLAYER_VAR):
        _declare(ed, name, BEL.get_basic_type_by_name("bool"))
    _declare(ed, "RespawnClass",
             BEL.get_class_reference_type(unreal.Actor.static_class()))
    # What a killed wanderer leaves on the ground. Typed as a class rather than
    # hard-coded in the graph so this component still compiles when
    # BP_AmmoPickup does not exist yet -- which is the case every time this
    # builder runs from scratch, because the pickup casts to BP_WeaponComponent
    # and so has to be built after it. main() fills the default in afterwards.
    _declare(ed, "AmmoClass",
             BEL.get_class_reference_type(unreal.Actor.static_class()))
    # The weapons a kill can leave behind, class-of-Actor for the same reason
    # AmmoClass is, and filled by main() once every weapon blueprint exists.
    # Empty is a legal state and means "no weapon ever drops" -- the graph
    # checks the length before it draws an index.
    _declare(ed, "DropClasses", BEL.get_array_type(
        BEL.get_class_reference_type(unreal.Actor.static_class())))
    # Corpse loot: the table loot/install.py fills, and what this body carries.
    declare_loot_vars(ed)
    # Where the replacement will appear. Written three times on the way to the
    # spawn -- the request, then whichever navmesh point it resolved to -- so
    # that the random draw and the nav query are each evaluated exactly once.
    _declare(ed, "RespawnPoint", _struct_type(unreal.Vector.static_struct()))
    # How long after a death its replacement appears.
    _declare(ed, RESPAWN_DELAY_VAR, _float_type())
    # The number this wanderer was given at spawn. The HUD draws it beside the
    # health bar; the log line below records where that number appeared.
    _declare(ed, NPC_ID_VAR, BEL.get_basic_type_by_name("int"))
    # Where this wanderer was put. Recorded for diagnosis, not for gameplay --
    # the respawn point is computed from the player, not from here (the old
    # SpawnOrigin, which anchored respawns to it, is gone on purpose). It is
    # what lets the safety net report the spawn that produced a faller.
    _declare(ed, SPAWNED_AT_VAR, _struct_type(unreal.Vector.static_struct()))
    # Hit boxes: which physics-asset bodies are head and which are limbs, and
    # what each is worth. On the target rather than on the weapon, because the
    # tables are a fact about the target's skeleton -- install_on_character
    # and install_on_npc fill them from each one's own mesh. Empty here, which
    # makes a target nobody has zoned take every hit at 1.0x.
    for name in (HEAD_BONES_VAR, LIMB_BONES_VAR):
        _declare(ed, name, BEL.get_array_type(BEL.get_basic_type_by_name("name")))
    for name in (HEAD_MULT_VAR, LIMB_MULT_VAR):
        _declare(ed, name, _float_type())

    # Flinching. Four variables and a clip table, all on the component rather
    # than on either character, because both of them react the same way and
    # neither of their Blueprints has a graph this could be written into.
    _declare(ed, HIT_REACTIONS_VAR, BEL.get_array_type(
        BEL.get_object_reference_type(unreal.AnimSequenceBase.static_class())))
    _declare(ed, LAST_HIT_FROM_VAR, _struct_type(unreal.Vector.static_struct()))
    for name in (PREV_HEALTH_VAR, NEXT_REACT_VAR):
        _declare(ed, name, _float_type())
    _declare(ed, REACT_INDEX_VAR, BEL.get_basic_type_by_name("int"))
    _declare(ed, STEADY_VAR, BEL.get_basic_type_by_name("bool"))

    # SpawnOrigin used to hold where this actor started, back when a replacement
    # appeared near the dead one's own spawn point. It has to be removed
    # explicitly: this builder updates blueprints in place, so a variable it
    # simply stops declaring stays on the asset forever.
    ed.remove_member_variable("SpawnOrigin")

    _author_health_begin_play(ed, begin)

    lost, write_off = _author_world_floor_net(ed, tick)

    # --- Tick: has it died this frame? ---------------------------------------
    health = ed.add_get_member_variable_node("Health")
    dying = _node(ed, FN_LE_FF)
    _connect(out(health, "Health"), _pin(dying, "A"))
    _set(dying, "B", 0.0)

    at_zero = ed.add_branch_node()
    _connect(out(dying), _pin(at_zero, "Condition"))
    # Both arms of the net fall through the debuff drain to here. The Health
    # getter above is pure, so it is read at *this* branch -- after the net's
    # write and the drain's -- and a wanderer written off this frame, or a
    # starving player drained past zero, dies this frame.
    drained = _author_debuff_drain(ed, tick, (then(write_off), else_(lost)))
    for e in drained:
        _connect(e, _pin(at_zero, "execute"))

    # --- Tick: took a hit and lived --------------------------------------
    # The other arm of the same branch, and that is the whole "and survived":
    # this exec pin is reached only on frames the owner is still above zero.
    # ...unless its sights are up (Steady): then the hit is only remembered.
    steady, flinch = _author_steady_gate(ed, else_(at_zero))
    _author_hit_reaction(ed, flinch, skips=(steady,))

    # Branch on Dead and use its *False* pin -- one node cheaper than a NOT, and
    # it is what stops the death path running again every frame after the first.
    dead_get = ed.add_get_member_variable_node("Dead")
    already = ed.add_branch_node()
    _connect(out(dead_get, "Dead"), _pin(already, "Condition"))
    _connect(then(at_zero), _pin(already, "execute"))

    mark = ed.add_set_member_variable_node("Dead")
    _set(mark, "Dead", "true")
    _connect(else_(already), _pin(mark, "execute"))

    despawn_get = ed.add_get_member_variable_node("DespawnOnDeath")
    should = ed.add_branch_node()
    _connect(out(despawn_get, "DespawnOnDeath"), _pin(should, "Condition"))
    _connect(then(mark), _pin(should, "execute"))

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
    mine_again = ed.add_get_member_variable_node("DespawnOnDeath")
    is_player = ed.add_branch_node()
    _connect(out(mine_again, "DespawnOnDeath"), _pin(is_player, "Condition"))
    for tail in (fell, no_body):
        _connect(tail, _pin(is_player, "execute"))
    _author_player_death(ed, (else_(is_player),))
    # ...and only a wanderer a replacement, once it is down.
    _author_replacement(ed, then(is_player))

    ed.add_comment_to_nodes(
        f"At 0 HP: mark Dead once, then (if DespawnOnDeath) count the kill and "
        f"leave this one on the ground for {CORPSE_SECONDS:.0f} s; its "
        f"replacement follows {RESPAWN_DELAY:.0f} s later. The player's copy "
        "has DespawnOnDeath false and no RespawnClass, so none of that runs "
        "on them.",
        [health, dying, at_zero, dead_get, already, mark, despawn_get, should,
         mine_again, is_player])

    _post_physics_tick(bp)
    arrange(ed)
    if not BEL.compile_blueprint(bp):
        raise RuntimeError("BP_HealthComponent failed to compile")
    _apply_defaults(bp, {
        "Health": COMBAT.start_health,
        "MaxHealth": COMBAT.start_health,
        "Dead": False,
        "DespawnOnDeath": False,
        RESPAWN_DELAY_VAR: RESPAWN_DELAY,
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
    _log(f"built {HEALTH_BP_PATH} (Health = MaxHealth = {COMBAT.start_health})")
    return bp
