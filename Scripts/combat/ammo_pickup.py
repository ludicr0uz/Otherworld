"""BP_AmmoPickup: the shells a killed wanderer leaves behind.
"""

import unreal

from combat.graph import (
    BEL, BGE, _add_component, _apply_defaults, _assets, _at,
    _component_object, _connect, _create_blueprint, _declare,
    _drop_components, _events, _log, _loose_pin, _node, _palette, _pin,
    _root_handle, _set,
)
from combat.nodes import (
    FN_ACTOR_LOC, FN_ADD_II, FN_ADD_LOCAL_ROT, FN_AND, FN_DESTROY,
    FN_DISTANCE, FN_GET_COMP, FN_GET_PLAYER_PAWN, FN_IS_VALID, FN_LESS_FF,
    FN_LIFESPAN, FN_MAKE_ROT, FN_MUL_FF, FN_NOT, MACRO_FOR_EACH,
)
from combat.paths import (
    AMMO_BP_PATH, CYLINDER, ITEM_CLASS_PATH, MAT_BRASS,
    WEAPON_COMP_CLASS_PATH,
)
from combat.tuning import (
    AMMO_DROP_SHELLS, AMMO_PICKUP_LIFETIME, AMMO_PICKUP_RADIUS,
    AMMO_SPIN_DEG_PER_S,
)
from combat.weapon_component.common import _prop


# ─── BP_AmmoPickup ───────────────────────────────────────────────────────────

def build_ammo_pickup(rebuild=True):
    """The two shells a killed wanderer leaves behind, and how they are taken.

    Walked into rather than pressed for. E already picks weapons up, and making
    the player press it again for ammunition they obviously want is friction
    with no decision in it -- whereas a *weapon* on the ground is a real choice,
    because the inventory's slots are finite.

    The proximity test runs on the pickup, not on the player, and that is the
    whole reason this is an actor with a graph instead of another
    GetAllActorsOfClass sweep in the weapon component's Tick. There are at most
    a handful of these on the ground; there is exactly one player. One actor
    measuring its own distance costs one Tick each. The alternative re-walks
    every pickup in the level every frame whether any exist or not.

    Credit goes to the weapon in the player's hands, if that weapon takes
    ammunition, and otherwise to the first carried weapon that does. The
    preference is not decoration: with four of the five weapons using
    ammunition, "first in the inventory" means the shells always land in the
    shotgun in slot 0, so a player clearing the forest with the sniper would
    watch their reserve stay at 15 while a gun they are not holding fills up.

    Credited is what stops the fallback loop handing the same two shells to a
    second shotgun -- ForEachLoop has no break pin, so the guard has to be a
    flag the body sets -- and it is also what the destroy is gated on.
    """
    eas = _assets()
    bp = _create_blueprint(AMMO_BP_PATH, unreal.Actor)

    _drop_components(bp, {"Pack", "ShellA", "ShellB"})
    root = _add_component(bp, _root_handle(bp), unreal.SceneComponent, "Pack")
    # Two of them, because two is what a kill drops and the pickup should look
    # like what it gives you.
    for name, y in (("ShellA", -5.0), ("ShellB", 5.0)):
        handle = _add_component(bp, root, unreal.StaticMeshComponent, name)
        obj = _component_object(handle)
        obj.set_editor_property("static_mesh", eas.load_asset(CYLINDER))
        obj.set_editor_property("relative_location", unreal.Vector(0.0, y, 0.0))
        obj.set_editor_property("relative_scale3d", unreal.Vector(0.08, 0.08, 0.14))
        obj.set_editor_property("override_materials", [eas.load_asset(MAT_BRASS)])
        try:
            obj.set_collision_profile_name("NoCollision")
        except Exception as exc:                                  # noqa: BLE001
            _log(f"  note: could not set NoCollision on {name}: {exc}")

    ed = BGE.get_graph_editor_by_name(bp, "EventGraph")
    tick, begin = _events(ed, rebuild)
    _declare(ed, "Shells", BEL.get_basic_type_by_name("int"))
    _declare(ed, "Credited", BEL.get_basic_type_by_name("bool"))

    # --- BeginPlay: tidy yourself away eventually ---------------------------
    life = _at(_node(ed, FN_LIFESPAN), 320, -500)
    _set(life, "InLifespan", AMMO_PICKUP_LIFETIME)
    _connect(BEL.find_then_pin(begin), _pin(life, "execute"))

    # --- Tick: spin, then check the distance --------------------------------
    # The spin is what makes a 10 cm object findable on a forest floor at night;
    # the emissive brass does the rest.
    turn = _at(_node(ed, FN_MUL_FF), 320, 300)
    _connect(_pin(tick, "DeltaSeconds", is_input=False), _pin(turn, "A"))
    _set(turn, "B", AMMO_SPIN_DEG_PER_S)
    delta = _at(_node(ed, FN_MAKE_ROT), 560, 300)
    _connect(_pin(turn, "ReturnValue", is_input=False), _pin(delta, "Yaw"))
    spin = _at(_node(ed, FN_ADD_LOCAL_ROT), 800, 0)
    _connect(_pin(delta, "ReturnValue", is_input=False), _pin(spin, "DeltaRotation"))
    _set(spin, "bSweep", "false")
    _set(spin, "bTeleport", "true")
    _connect(BEL.find_then_pin(tick), _pin(spin, "execute"))

    pawn = _at(_node(ed, FN_GET_PLAYER_PAWN), 800, 300)
    _set(pawn, "PlayerIndex", 0)
    pawn_out = _pin(pawn, "ReturnValue", is_input=False)
    there = _at(_node(ed, FN_ACTOR_LOC), 1040, 300)
    _connect(pawn_out, _pin(there, "self"))
    here = _at(_node(ed, FN_ACTOR_LOC), 1040, 420)
    gap = _at(_node(ed, FN_DISTANCE), 1280, 300)
    _connect(_pin(there, "ReturnValue", is_input=False), _pin(gap, "V1"))
    _connect(_pin(here, "ReturnValue", is_input=False), _pin(gap, "V2"))
    near = _at(_node(ed, FN_LESS_FF), 1520, 300)
    _connect(_pin(gap, "ReturnValue", is_input=False), _pin(near, "A"))
    _set(near, "B", AMMO_PICKUP_RADIUS)

    reached = _at(ed.add_branch_node(), 1760, 0)
    _connect(_pin(near, "ReturnValue", is_input=False), _pin(reached, "Condition"))
    _connect(BEL.find_then_pin(spin), _pin(reached, "execute"))

    # --- who gets the shells ------------------------------------------------
    comp = _at(_node(ed, FN_GET_COMP), 2000, 300)
    _connect(pawn_out, _pin(comp, "self"))
    _pin(comp, "ComponentClass").set_pin_value(WEAPON_COMP_CLASS_PATH)
    as_weapon_n = _at(_palette(ed, "Utilities|Casting|CastToBP_WeaponComponent"),
                      2280, 0)
    _connect(_pin(comp, "ReturnValue", is_input=False), _pin(as_weapon_n, "Object"))
    _connect(BEL.find_then_pin(reached), _pin(as_weapon_n, "execute"))
    as_weapon = _loose_pin(as_weapon_n, "AsBPWeaponComponent", is_input=False)

    # --- first choice: whatever is in the player's hands ---------------------
    # Two nested branches rather than one AND, and for the reason this file has
    # now hit four times: UsesAmmo is a pure read off Held, and pulling it while
    # Held is None is an Accessed None. The validity test has to be a gate the
    # second read sits behind, not a term beside it.
    held_get = _at(ed.add_get_member_variable_node("Held", WEAPON_COMP_CLASS_PATH),
                   2560, 300)
    _connect(as_weapon, _pin(held_get, "self"))
    held = _pin(held_get, "Held", is_input=False)
    armed = _at(_node(ed, FN_IS_VALID), 2800, 300)
    _connect(held, _pin(armed, "Object"))
    has_gun = _at(ed.add_branch_node(), 3040, -700)
    _connect(_pin(armed, "ReturnValue", is_input=False), _pin(has_gun, "Condition"))
    _connect(BEL.find_then_pin(as_weapon_n), _pin(has_gun, "execute"))

    held_uses, held_uses_n = _prop(ed, "UsesAmmo", held, 3300, -400)
    takes_ammo = _at(ed.add_branch_node(), 3560, -700)
    _connect(held_uses, _pin(takes_ammo, "Condition"))
    _connect(BEL.find_then_pin(has_gun), _pin(takes_ammo, "execute"))

    held_res, held_res_n = _prop(ed, "Reserve", held, 3820, -400)
    held_shells = _at(ed.add_get_member_variable_node("Shells"), 3820, -280)
    held_richer = _at(_node(ed, FN_ADD_II), 4080, -400)
    _connect(held_res, _pin(held_richer, "A"))
    _connect(_pin(held_shells, "Shells", is_input=False), _pin(held_richer, "B"))
    held_store = _at(ed.add_set_member_variable_node("Reserve", ITEM_CLASS_PATH),
                     4340, -700)
    _connect(held, _pin(held_store, "self"))
    _connect(_pin(held_richer, "ReturnValue", is_input=False),
             _pin(held_store, "Reserve"))
    _connect(BEL.find_then_pin(takes_ammo), _pin(held_store, "execute"))
    held_mark = _at(ed.add_set_member_variable_node("Credited"), 4600, -700)
    _set(held_mark, "Credited", "true")
    _connect(BEL.find_then_pin(held_store), _pin(held_mark, "execute"))

    # --- fallback: the first carried weapon that takes ammunition ------------
    # Reached when nothing is held, or when what is held is the pistol. Walking
    # over shells with the pistol out still has to pay into something, or the
    # drop is lost for the sake of a rule about which gun is out.
    inv = _at(ed.add_get_member_variable_node("Inventory", WEAPON_COMP_CLASS_PATH),
              2560, 420)
    _connect(as_weapon, _pin(inv, "self"))

    loop = ed.add_macro_node(MACRO_FOR_EACH)
    if not loop:
        raise RuntimeError("could not create the ForEachLoop macro node")
    _at(loop, 2840, 0)
    _connect(_pin(inv, "Inventory", is_input=False), _loose_pin(loop, "Array"))
    _connect(BEL.find_else_pin(has_gun), _loose_pin(loop, "Exec"))
    _connect(BEL.find_else_pin(takes_ammo), _loose_pin(loop, "Exec"))
    item = _loose_pin(loop, "ArrayElement", is_input=False)

    uses, uses_n = _prop(ed, "UsesAmmo", item, 3140, 300)
    done_get = _at(ed.add_get_member_variable_node("Credited"), 3140, 440)
    fresh = _at(_node(ed, FN_NOT), 3380, 440)
    _connect(_pin(done_get, "Credited", is_input=False), _pin(fresh, "A"))
    wants = _at(_node(ed, FN_AND), 3620, 360)
    _connect(uses, _pin(wants, "A"))
    _connect(_pin(fresh, "ReturnValue", is_input=False), _pin(wants, "B"))

    give = _at(ed.add_branch_node(), 3880, 0)
    _connect(_pin(wants, "ReturnValue", is_input=False), _pin(give, "Condition"))
    _connect(_loose_pin(loop, "LoopBody", is_input=False), _pin(give, "execute"))

    item_res, item_res_n = _prop(ed, "Reserve", item, 4140, 300)
    shells = _at(ed.add_get_member_variable_node("Shells"), 4140, 440)
    richer = _at(_node(ed, FN_ADD_II), 4400, 300)
    _connect(item_res, _pin(richer, "A"))
    _connect(_pin(shells, "Shells", is_input=False), _pin(richer, "B"))
    store = _at(ed.add_set_member_variable_node("Reserve", ITEM_CLASS_PATH), 4660, 0)
    _connect(item, _pin(store, "self"))
    _connect(_pin(richer, "ReturnValue", is_input=False), _pin(store, "Reserve"))
    _connect(BEL.find_then_pin(give), _pin(store, "execute"))

    mark = _at(ed.add_set_member_variable_node("Credited"), 4920, 0)
    _set(mark, "Credited", "true")
    _connect(BEL.find_then_pin(store), _pin(mark, "execute"))

    # --- and only then vanish -----------------------------------------------
    # Gated on Credited rather than destroyed unconditionally at the Completed
    # pin: a player with no shotgun who walks over the shells has not picked
    # anything up, and the drop has to still be there when they find one.
    took_get = _at(ed.add_get_member_variable_node("Credited"), 5180, 300)
    took = _at(ed.add_branch_node(), 5440, 0)
    _connect(_pin(took_get, "Credited", is_input=False), _pin(took, "Condition"))
    _connect(_loose_pin(loop, "Completed", is_input=False), _pin(took, "execute"))
    _connect(BEL.find_then_pin(held_mark), _pin(took, "execute"))
    gone = _at(_node(ed, FN_DESTROY), 5700, 0)
    _connect(BEL.find_then_pin(took), _pin(gone, "execute"))

    ed.add_comment_to_nodes(
        f"{AMMO_DROP_SHELLS} shells, taken by walking within "
        f"{AMMO_PICKUP_RADIUS:.0f} cm of them. The distance is measured HERE "
        "rather than in the weapon component's Tick, so the cost is one Tick "
        "per dropped pickup instead of a GetAllActorsOfClass sweep every frame "
        "whether anything has been dropped or not. The shells go to the weapon "
        "in hand when that weapon takes ammunition, and otherwise to the first "
        "carried one that does -- with four of five weapons using ammunition, "
        "\"first in the inventory\" would mean the shotgun in slot 0, always. "
        "Credited is the break ForEachLoop does not have.",
        [life, turn, delta, spin, pawn, there, here, gap, near, reached, comp,
         as_weapon_n, held_get, armed, has_gun, held_uses_n, takes_ammo,
         held_res_n, held_shells, held_richer, held_store, held_mark,
         inv, loop, uses_n, done_get, fresh, wants, give,
         item_res_n, shells, richer, store, mark, took_get, took, gone])

    if not BEL.compile_blueprint(bp):
        raise RuntimeError("BP_AmmoPickup failed to compile")
    _apply_defaults(bp, {"Shells": AMMO_DROP_SHELLS, "Credited": False})
    _log(f"built {AMMO_BP_PATH} ({AMMO_DROP_SHELLS} shells, "
         f"{AMMO_PICKUP_RADIUS:.0f} cm, {AMMO_PICKUP_LIFETIME:.0f}s)")
    return bp
