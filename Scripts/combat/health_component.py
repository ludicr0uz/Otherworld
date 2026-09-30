"""BP_HealthComponent: Health/MaxHealth, damage bookkeeping, and the Tick
that drives death, respawn, hit reactions and the world-floor safety net.
The death and flinch fragments are authored in death.py and
hit_reaction.py; this module wires them together.
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
from combat.graph import (
    BEL, BGE, _apply_defaults, _assets, _at, _connect, _create_blueprint,
    _declare, _events, _float_type, _log, _loose_pin, _node, _palette, _pin,
    _post_physics_tick, _set, _struct_type, _vec,
)
from combat.hit_reaction import (
    HIT_REACTIONS_VAR, LAST_HIT_FROM_VAR, NEXT_REACT_VAR, PREV_HEALTH_VAR,
    REACT_INDEX_VAR, _author_hit_reaction,
)
from combat.hit_zones import (
    HEAD_BONES_VAR, HEAD_MULT_VAR, LIMB_BONES_VAR, LIMB_MULT_VAR,
)
from combat.nodes import (
    FN_ACTOR_LOC, FN_ADD_VV, FN_FORWARD, FN_GET_PLAYER_PAWN,
    FN_IS_VALID_CLASS, FN_LE_FF, FN_MAKE_ROT, FN_MAKE_TRANSFORM, FN_MUL_VF,
    FN_PROJECT_NAV, FN_RANDOM_FLOAT, FN_RANDOM_NAV, FN_TRACE, NODE_BREAK_HIT,
    NODE_SPAWN,
)
from combat.paths import HEALTH_BP_PATH, ITEM_BP_PATH
from combat.respawn import (
    RESPAWN_ATTEMPTS, RESPAWN_BAND, RESPAWN_LIFT, RESPAWN_PROJECT_EXTENT,
    RESPAWN_TRACE_DOWN, RESPAWN_TRACE_UP, _author_health_begin_play,
    _author_world_floor_net,
)
from combat.tuning import COMBAT
from combat.weapon_component.common import _trace_defaults
from loot.roll import declare_loot_vars


def build_health_component(rebuild=True):
    """Health, plus what happens when it runs out.

    Health is a component rather than a variable on each character so that the
    shooter and the HUD share one lookup -- GetComponentByClass -> Cast ->
    Health -- that works on the player, on the NPC, and on anything given the
    component later.

    Death lives here too, and is driven by three defaults rather than by
    subclassing:

        DespawnOnDeath   this is a wanderer: at 0 HP count the kill, spawn a
                         replacement, kill the AI and let the body rot for
                         CORPSE_SECONDS. False on the player, whose body stays
                         where it fell until the level reopens.
        RespawnClass     what to spawn in the dead actor's place. Left empty on
                         the player; on a wanderer it is overwritten at
                         BeginPlay with the owner's OWN class, so each creature
                         respawns as itself rather than as whatever the shared
                         component template happened to name.

    Where the replacement appears is the RESPAWN_BAND: a random bearing and a
    random distance in the same 75-100 m annulus the level generator uses,
    measured from the player's current location and then snapped onto the
    navmesh. So killing one wanderer keeps the population at five and keeps
    every one of them at a distance the player can see coming.

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

    # SpawnOrigin used to hold where this actor started, back when a replacement
    # appeared near the dead one's own spawn point. It has to be removed
    # explicitly: this builder updates blueprints in place, so a variable it
    # simply stops declaring stays on the asset forever.
    ed.remove_member_variable("SpawnOrigin")

    _author_health_begin_play(ed, begin)

    lost, write_off = _author_world_floor_net(ed, tick)

    # --- Tick: has it died this frame? ---------------------------------------
    health = _at(ed.add_get_member_variable_node("Health"), 240, 240)
    dying = _at(_node(ed, FN_LE_FF), 460, 240)
    _connect(_pin(health, "Health", is_input=False), _pin(dying, "A"))
    _set(dying, "B", 0.0)

    at_zero = _at(ed.add_branch_node(), 700, 0)
    _connect(_pin(dying, "ReturnValue", is_input=False), _pin(at_zero, "Condition"))
    # Both arms of the net fall through the debuff drain to here. The Health
    # getter above is pure, so it is read at *this* branch -- after the net's
    # write and the drain's -- and a wanderer written off this frame, or a
    # starving player drained past zero, dies this frame.
    drained = _author_debuff_drain(
        ed, tick, (BEL.find_then_pin(write_off), BEL.find_else_pin(lost)),
        -2600, -1400)
    for e in drained:
        _connect(e, _pin(at_zero, "execute"))

    # --- Tick: took a hit and lived --------------------------------------
    # The other arm of the same branch, and that is the whole "and survived":
    # this exec pin is reached only on frames the owner is still above zero.
    _author_hit_reaction(ed, BEL.find_else_pin(at_zero), 700, 1600)

    # Branch on Dead and use its *False* pin -- one node cheaper than a NOT, and
    # it is what stops the death path running again every frame after the first.
    dead_get = _at(ed.add_get_member_variable_node("Dead"), 700, 240)
    already = _at(ed.add_branch_node(), 940, 0)
    _connect(_pin(dead_get, "Dead", is_input=False), _pin(already, "Condition"))
    _connect(BEL.find_then_pin(at_zero), _pin(already, "execute"))

    mark = _at(ed.add_set_member_variable_node("Dead"), 1180, 0)
    _set(mark, "Dead", "true")
    _connect(BEL.find_else_pin(already), _pin(mark, "execute"))

    despawn_get = _at(ed.add_get_member_variable_node("DespawnOnDeath"), 1180, 240)
    should = _at(ed.add_branch_node(), 1420, 0)
    _connect(_pin(despawn_get, "DespawnOnDeath", is_input=False), _pin(should, "Condition"))
    _connect(BEL.find_then_pin(mark), _pin(should, "execute"))

    # --- count it, then respawn, then leave a corpse -------------------------
    counted = _author_kill_count(ed, BEL.find_then_pin(should), 1420, -1600)

    cls_get = _at(ed.add_get_member_variable_node("RespawnClass"), 1660, 300)
    can_respawn = _at(_node(ed, FN_IS_VALID_CLASS), 1900, 300)
    _connect(_pin(cls_get, "RespawnClass", is_input=False), _pin(can_respawn, "Class"))
    respawns = _at(ed.add_branch_node(), 2120, 0)
    _connect(_pin(can_respawn, "ReturnValue", is_input=False), _pin(respawns, "Condition"))
    for tail in counted:
        _connect(tail, _pin(respawns, "execute"))

    # --- where the replacement goes -----------------------------------------
    # Three steps, and the order matters:
    #
    #   1. build the REQUEST -- a random bearing and distance in the band,
    #      around the player -- and store it, so the random draw happens once;
    #   2. project it onto the navmesh, which is what supplies a real ground
    #      height (the request carries the *player's* Z, which is meaningless
    #      90 m away) and pulls a point that overshot the navigable island back
    #      onto it;
    #   3. only then spawn, lifted by the capsule's half height.
    #
    # Step 1 has to be a variable rather than wires straight into step 2.
    # K2_ProjectPointToNavigation is **pure** (a const BlueprintCallable, which
    # UHT promotes), so it is re-evaluated once per output pin read -- and if
    # its Point pin were driven by the RandomFloatInRange chain, the branch on
    # ReturnValue and the read of ProjectedLocation would each roll fresh
    # numbers and project two different points. Storing the request first makes
    # every re-evaluation deterministic.
    #
    # THIS IS THE BUG THIS SHAPE EXISTS TO FIX: the previous version read the
    # nav query's location output and never looked at its bool, so a failed
    # query -- routine here, because the band's far edge lies outside the
    # navigable island on a 200 m map -- spawned the replacement at the raw
    # request point, at the player's own Z. On any ground higher than the player
    # that is *inside* the terrain, and the capsule falls through the world.
    hero = _at(_node(ed, FN_GET_PLAYER_PAWN), 1660, 560)
    _set(hero, "PlayerIndex", 0)
    hero_loc = _at(_node(ed, FN_ACTOR_LOC), 1900, 560)
    _connect(_pin(hero, "ReturnValue", is_input=False), _pin(hero_loc, "self"))
    hero_out = _pin(hero_loc, "ReturnValue", is_input=False)

    made = [hero, hero_loc]
    flow = BEL.find_then_pin(respawns)
    ready = []          # exec pins that have a good point and may spawn

    for attempt in range(RESPAWN_ATTEMPTS):
        x0 = 2360 + attempt * 1400
        y0 = attempt * 900

        bearing = _at(_node(ed, FN_RANDOM_FLOAT), x0 - 700, y0 + 300)
        _set(bearing, "Min", 0.0)
        _set(bearing, "Max", 360.0)
        facing = _at(_node(ed, FN_MAKE_ROT), x0 - 460, y0 + 300)
        _connect(_pin(bearing, "ReturnValue", is_input=False), _pin(facing, "Yaw"))
        _set(facing, "Pitch", 0.0)
        _set(facing, "Roll", 0.0)
        heading = _at(_node(ed, FN_FORWARD), x0 - 220, y0 + 300)
        _connect(_pin(facing, "ReturnValue", is_input=False), _pin(heading, "InRot"))

        reach = _at(_node(ed, FN_RANDOM_FLOAT), x0 - 460, y0 + 460)
        _set(reach, "Min", RESPAWN_BAND[0])
        _set(reach, "Max", RESPAWN_BAND[1])
        # Multiply_VectorFloat is a wildcard operator whose B pin defaults to a
        # *vector*, so a float literal on it silently does nothing -- but a
        # connected float is fine, and that is what this is.
        offset = _at(_node(ed, FN_MUL_VF), x0, y0 + 300)
        _connect(_pin(heading, "ReturnValue", is_input=False), _pin(offset, "A"))
        _connect(_pin(reach, "ReturnValue", is_input=False), _pin(offset, "B"))

        request = _at(_node(ed, FN_ADD_VV), x0 + 240, y0 + 160)
        _connect(hero_out, _pin(request, "A"))
        _connect(_pin(offset, "ReturnValue", is_input=False), _pin(request, "B"))

        ask = _at(ed.add_set_member_variable_node("RespawnPoint"), x0 + 480, y0)
        _connect(_pin(request, "ReturnValue", is_input=False), _pin(ask, "RespawnPoint"))
        _connect(flow, _pin(ask, "execute"))
        asked = _at(ed.add_get_member_variable_node("RespawnPoint"), x0 + 480, y0 + 200)

        proj = _at(_node(ed, FN_PROJECT_NAV), x0 + 720, y0 + 200)
        _connect(_pin(asked, "RespawnPoint", is_input=False), _pin(proj, "Point"))
        # QueryExtent is a struct pin, and struct pins reject set_pin_value
        # outright -- an empty one compiles as the ZERO vector, i.e. a search box
        # with no volume, which finds nothing and fails every projection.
        _connect(_vec(ed, *RESPAWN_PROJECT_EXTENT, x0 + 480, y0 + 420),
                 _pin(proj, "QueryExtent"))

        landed = _at(ed.add_branch_node(), x0 + 960, y0)
        _connect(_pin(proj, "ReturnValue", is_input=False), _pin(landed, "Condition"))
        _connect(BEL.find_then_pin(ask), _pin(landed, "execute"))

        use_proj = _at(ed.add_set_member_variable_node("RespawnPoint"), x0 + 1200, y0)
        _connect(_pin(proj, "ProjectedLocation", is_input=False),
                 _pin(use_proj, "RespawnPoint"))
        _connect(BEL.find_then_pin(landed), _pin(use_proj, "execute"))

        ready.append(BEL.find_then_pin(use_proj))
        # A failed projection falls through to the next bearing; the draws are
        # independent, so a second one is a real second chance and not a repeat.
        flow = BEL.find_else_pin(landed)
        made += [bearing, facing, heading, reach, offset, request, ask, asked,
                 proj, landed, use_proj]

    # Last resort: no band point anywhere in the search box projected, which in
    # practice means the navmesh has not been generated yet (the first frame of
    # a level, or the tile churn after a burst of deaths). Take any navigable
    # point near the player rather than none -- a replacement standing too close
    # is a gameplay annoyance, one under the terrain is a bug. This call is the
    # *impure* nav function on purpose: it is random, so it must be evaluated
    # exactly once, and only a node with an exec pin can promise that.
    anywhere = _at(_node(ed, FN_RANDOM_NAV), 5400, 1500)
    _connect(hero_out, _pin(anywhere, "Origin"))
    _set(anywhere, "Radius", RESPAWN_BAND[1])
    _connect(flow, _pin(anywhere, "execute"))

    salvaged = _at(ed.add_branch_node(), 5660, 1500)
    _connect(_pin(anywhere, "ReturnValue", is_input=False), _pin(salvaged, "Condition"))
    _connect(BEL.find_then_pin(anywhere), _pin(salvaged, "execute"))

    use_any = _at(ed.add_set_member_variable_node("RespawnPoint"), 5920, 1500)
    _connect(_pin(anywhere, "RandomLocation", is_input=False),
             _pin(use_any, "RespawnPoint"))
    _connect(BEL.find_then_pin(salvaged), _pin(use_any, "execute"))
    ready.append(BEL.find_then_pin(use_any))

    # 3. seat it on the real ground. The point is on the navmesh by now, but the
    # navmesh is a voxelised approximation of the terrain and its Z can be most
    # of a capsule too low -- so keep the XY, throw the Z away, and trace onto
    # the collision geometry the character will actually stand on.
    seat = _at(ed.add_get_member_variable_node("RespawnPoint"), 6180, 600)
    seat_out = _pin(seat, "RespawnPoint", is_input=False)
    above = _at(_node(ed, FN_ADD_VV), 6420, 600)
    _connect(seat_out, _pin(above, "A"))
    _connect(_vec(ed, 0.0, 0.0, RESPAWN_TRACE_UP, 6180, 800), _pin(above, "B"))
    below = _at(_node(ed, FN_ADD_VV), 6420, 780)
    _connect(seat_out, _pin(below, "A"))
    _connect(_vec(ed, 0.0, 0.0, -RESPAWN_TRACE_DOWN, 6180, 960), _pin(below, "B"))

    drop = _at(_node(ed, FN_TRACE), 6680, 300)
    _connect(_pin(above, "ReturnValue", is_input=False), _pin(drop, "Start"))
    _connect(_pin(below, "ReturnValue", is_input=False), _pin(drop, "End"))
    _trace_defaults(drop)
    # The terrain is imported with complex collision, and its simple collision
    # is a box around the whole 200 m mesh -- tracing against that would seat
    # every respawn on an invisible lid.
    _set(drop, "bTraceComplex", "true")
    for tail in ready:
        _connect(tail, _pin(drop, "execute"))

    found = _at(ed.add_branch_node(), 6940, 300)
    _connect(_pin(drop, "ReturnValue", is_input=False), _pin(found, "Condition"))
    _connect(BEL.find_then_pin(drop), _pin(found, "execute"))

    lift = _vec(ed, 0.0, 0.0, RESPAWN_LIFT, 6940, 900)
    brk = _at(_palette(ed, NODE_BREAK_HIT), 7200, 700)
    _connect(_pin(drop, "OutHit", is_input=False), _pin(brk, "Hit"))
    ground = _at(_node(ed, FN_ADD_VV), 7460, 700)
    _connect(_loose_pin(brk, "Location", is_input=False), _pin(ground, "A"))
    _connect(lift, _pin(ground, "B"))
    stand = _at(ed.add_set_member_variable_node("RespawnPoint"), 7460, 500)
    _connect(_pin(ground, "ReturnValue", is_input=False), _pin(stand, "RespawnPoint"))
    _connect(BEL.find_then_pin(found), _pin(stand, "execute"))

    # Nothing under the point at all (it hangs over a hole in the world). Keep
    # the navmesh height and lift off that instead -- worse, but still above
    # whatever the navmesh thinks the floor is.
    airborne = _at(_node(ed, FN_ADD_VV), 7460, 1100)
    _connect(seat_out, _pin(airborne, "A"))
    _connect(lift, _pin(airborne, "B"))
    hover = _at(ed.add_set_member_variable_node("RespawnPoint"), 7460, 950)
    _connect(_pin(airborne, "ReturnValue", is_input=False), _pin(hover, "RespawnPoint"))
    _connect(BEL.find_else_pin(found), _pin(hover, "execute"))

    made += [seat, above, below, drop, found, brk, ground, stand, airborne, hover]

    # 4. spawn, on ground the character can actually stand on.
    chosen = _at(ed.add_get_member_variable_node("RespawnPoint"), 7720, 300)
    xform = _at(_node(ed, FN_MAKE_TRANSFORM), 7960, 300)
    _connect(_pin(chosen, "RespawnPoint", is_input=False), _pin(xform, "Location"))
    _connect(_vec(ed, 1.0, 1.0, 1.0, 7720, 500), _pin(xform, "Scale"))

    spawn = _at(_palette(ed, NODE_SPAWN), 8220, 0)
    _connect(_pin(cls_get, "RespawnClass", is_input=False), _pin(spawn, "Class"))
    _connect(_pin(xform, "ReturnValue", is_input=False), _pin(spawn, "SpawnTransform"))
    # AlwaysSpawn: the nav point is inset from obstacles by the agent radius but
    # may still clip a trunk's collision, and a respawn that silently returns
    # null would empty the forest one death at a time.
    # AdjustIfPossibleButAlwaysSpawn, not AlwaysSpawn: the nav point is inset
    # from obstacles by the agent radius but can still clip a trunk, and a
    # capsule left interpenetrating gets depenetrated -- sometimes downwards,
    # through the terrain. Adjusting nudges it clear first; it still always
    # spawns, so a respawn cannot silently return null and empty the forest.
    _set(spawn, "CollisionHandlingOverride", "AdjustIfPossibleButAlwaysSpawn")
    for tail in (BEL.find_then_pin(stand), BEL.find_then_pin(hover)):
        _connect(tail, _pin(spawn, "execute"))

    # Every path ends at the same corpse; an exec *input* takes more than one
    # link, so no Sequence node is needed. Note the last one: with no navmesh to
    # be found at all, the dead wanderer is NOT replaced -- it still leaves a
    # body. Losing one of ten is recoverable and visible; dropping a replacement
    # through the floor is neither.
    corpsed = _author_corpse(ed, (BEL.find_then_pin(spawn),
                                  BEL.find_else_pin(respawns),
                                  BEL.find_else_pin(salvaged)), 8220, 0)

    # Both arms of the death branch collapse the same way and through the same
    # nodes: the player straight off the branch, the wanderer once its
    # replacement is out and its brain is gone.
    fell, no_body = _author_death_collapse(
        ed, (corpsed, BEL.find_else_pin(should)), 9900, 0)
    # ...and only the player gets a menu out of it. A second read of
    # DespawnOnDeath rather than routing the two arms separately, so there is
    # exactly one place that says what dying looks like.
    mine_again = _at(ed.add_get_member_variable_node("DespawnOnDeath"), 12060, 240)
    is_player = _at(ed.add_branch_node(), 12300, 0)
    _connect(_pin(mine_again, "DespawnOnDeath", is_input=False),
             _pin(is_player, "Condition"))
    for tail in (fell, no_body):
        _connect(tail, _pin(is_player, "execute"))
    _author_player_death(ed, (BEL.find_else_pin(is_player),), 12540, 0)

    ed.add_comment_to_nodes(
        f"At 0 HP: mark Dead once, then (if DespawnOnDeath) ask for a point "
        f"{RESPAWN_BAND[0] / 100:.0f}-{RESPAWN_BAND[1] / 100:.0f} m from the "
        f"player on a random bearing, PROJECT it onto the navmesh (the request "
        f"carries the player's Z, which is not the ground height out there), "
        f"spawn the replacement on that ground and leave this one on the "
        f"ground for {CORPSE_SECONDS:.0f} s "
        f"({RESPAWN_ATTEMPTS} bearings are tried before falling back to any "
        f"navigable point near the player). The replacement carries the same component, so the cycle sustains "
        "itself with nothing tracking it -- the pack stays five strong and every "
        "member still has to cross the forest. The player's copy has "
        "DespawnOnDeath false and no RespawnClass, so none of this runs on them.",
        [health, dying, at_zero, dead_get, already, mark, despawn_get, should,
         cls_get, can_respawn, respawns] + made +
        [anywhere, salvaged, use_any, chosen, xform, spawn, mine_again,
         is_player])

    _post_physics_tick(bp)
    if not BEL.compile_blueprint(bp):
        raise RuntimeError("BP_HealthComponent failed to compile")
    _apply_defaults(bp, {
        "Health": COMBAT.start_health,
        "MaxHealth": COMBAT.start_health,
        "Dead": False,
        "DespawnOnDeath": False,
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
    })
    _log(f"built {HEALTH_BP_PATH} (Health = MaxHealth = {COMBAT.start_health})")
    return bp
