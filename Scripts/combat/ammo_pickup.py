"""BP_AmmoPickup: the shells a killed wanderer leaves behind.
"""

import unreal

from combat.glimmer import add_glimmer
from combat.log import _log
from uebp.graph import (
    BEL, BGE, _add_component, _apply_defaults, _assets, _component_object, _connect,
    _create_blueprint, _drop_components, _events, _loose_pin, _node, _palette, _pin,
    _root_handle, _set, else_, out, then)
from uebp.layout import arrange
from combat.paths import (
    AMMO_BP_PATH, CYLINDER, ITEM_CLASS_PATH, MAT_BRASS,
    WEAPON_COMP_CLASS_PATH,
)
from combat.tuning import (
    AMMO_DROP_SHELLS, AMMO_PICKUP_LIFETIME, AMMO_PICKUP_RADIUS,
    AMMO_SPIN_DEG_PER_S,
)
from combat.weapon_component.common import _prop
from uebp.nodes.actor import (
    FN_ACTOR_LOC, FN_ADD_LOCAL_ROT, FN_DESTROY, FN_GET_COMP, FN_LIFESPAN)
from uebp.nodes.math import (
    FN_ADD_II, FN_AND, FN_DISTANCE, FN_LESS_FF, FN_MAKE_ROT, FN_MUL_FF, FN_NOT)
from uebp.nodes.palette import MACRO_FOR_EACH
from uebp.nodes.system import FN_GET_PLAYER_PAWN, FN_IS_VALID
from uebp.vars import declare
from combat import ammo_vars as AV
from combat import item_vars as IV
from combat.weapon_component import vars as WV


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
    shells (UsesAmmo and not InfiniteReserve -- the pistol's reserve is
    endless, so shells paid into it would vanish), and otherwise to the first carried weapon that does. The
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

    # It is only ever on the ground, so its glimmer is built showing.
    add_glimmer(bp, root, visible=True)

    ed = BGE.get_graph_editor_by_name(bp, "EventGraph")
    tick, begin = _events(ed, rebuild)
    declare(ed, AV.TABLE)

    # --- BeginPlay: tidy yourself away eventually ---------------------------
    life = _node(ed, FN_LIFESPAN)
    _set(life, "InLifespan", AMMO_PICKUP_LIFETIME)
    _connect(then(begin), _pin(life, "execute"))

    # --- Tick: spin, then check the distance --------------------------------
    # The spin is what makes a 10 cm object findable on a forest floor at night;
    # the emissive brass does the rest.
    turn = _node(ed, FN_MUL_FF)
    _connect(out(tick, "DeltaSeconds"), _pin(turn, "A"))
    _set(turn, "B", AMMO_SPIN_DEG_PER_S)
    delta = _node(ed, FN_MAKE_ROT)
    _connect(out(turn), _pin(delta, "Yaw"))
    spin = _node(ed, FN_ADD_LOCAL_ROT)
    _connect(out(delta), _pin(spin, "DeltaRotation"))
    _set(spin, "bSweep", False)
    _set(spin, "bTeleport", True)
    _connect(then(tick), _pin(spin, "execute"))

    pawn = _node(ed, FN_GET_PLAYER_PAWN)
    _set(pawn, "PlayerIndex", 0)
    pawn_out = out(pawn)
    there = _node(ed, FN_ACTOR_LOC)
    _connect(pawn_out, _pin(there, "self"))
    here = _node(ed, FN_ACTOR_LOC)
    gap = _node(ed, FN_DISTANCE)
    _connect(out(there), _pin(gap, "V1"))
    _connect(out(here), _pin(gap, "V2"))
    near = _node(ed, FN_LESS_FF)
    _connect(out(gap), _pin(near, "A"))
    _set(near, "B", AMMO_PICKUP_RADIUS)

    reached = ed.add_branch_node()
    _connect(out(near), _pin(reached, "Condition"))
    _connect(then(spin), _pin(reached, "execute"))

    # --- who gets the shells ------------------------------------------------
    comp = _node(ed, FN_GET_COMP)
    _connect(pawn_out, _pin(comp, "self"))
    _pin(comp, "ComponentClass").set_pin_value(WEAPON_COMP_CLASS_PATH)
    as_weapon_n = _palette(ed, "Utilities|Casting|CastToBP_WeaponComponent")
    _connect(out(comp), _pin(as_weapon_n, "Object"))
    _connect(then(reached), _pin(as_weapon_n, "execute"))
    as_weapon = _loose_pin(as_weapon_n, "AsBPWeaponComponent", is_input=False)

    # --- first choice: whatever is in the player's hands ---------------------
    # Two nested branches rather than one AND, and for the reason this file has
    # now hit four times: UsesAmmo is a pure read off Held, and pulling it while
    # Held is None is an Accessed None. The validity test has to be a gate the
    # second read sits behind, not a term beside it.
    held_get = ed.add_get_member_variable_node(WV.Held, WEAPON_COMP_CLASS_PATH)
    _connect(as_weapon, _pin(held_get, "self"))
    held = out(held_get, WV.Held)
    armed = _node(ed, FN_IS_VALID)
    _connect(held, _pin(armed, "Object"))
    has_gun = ed.add_branch_node()
    _connect(out(armed), _pin(has_gun, "Condition"))
    _connect(then(as_weapon_n), _pin(has_gun, "execute"))

    # "Takes shells" is UsesAmmo AND NOT InfiniteReserve: the pistol has a
    # magazine now, but shells paid into a reserve that is never spent would
    # simply vanish.
    held_uses, held_uses_n = _prop(ed, IV.UsesAmmo, held)
    held_endless, held_endless_n = _prop(ed, IV.InfiniteReserve, held)
    held_finite = _node(ed, FN_NOT)
    _connect(held_endless, _pin(held_finite, "A"))
    held_wants = _node(ed, FN_AND)
    _connect(held_uses, _pin(held_wants, "A"))
    _connect(out(held_finite), _pin(held_wants, "B"))
    takes_ammo = ed.add_branch_node()
    _connect(out(held_wants), _pin(takes_ammo, "Condition"))
    _connect(then(has_gun), _pin(takes_ammo, "execute"))

    held_res, held_res_n = _prop(ed, IV.Reserve, held)
    held_shells = ed.add_get_member_variable_node(AV.Shells)
    held_richer = _node(ed, FN_ADD_II)
    _connect(held_res, _pin(held_richer, "A"))
    _connect(out(held_shells, AV.Shells), _pin(held_richer, "B"))
    held_store = ed.add_set_member_variable_node(IV.Reserve, ITEM_CLASS_PATH)
    _connect(held, _pin(held_store, "self"))
    _connect(out(held_richer), _pin(held_store, IV.Reserve))
    _connect(then(takes_ammo), _pin(held_store, "execute"))
    held_mark = ed.add_set_member_variable_node(AV.Credited)
    _set(held_mark, AV.Credited, True)
    _connect(then(held_store), _pin(held_mark, "execute"))

    # --- fallback: the first carried weapon that takes ammunition ------------
    # Reached when nothing is held, or when what is held is the pistol. Walking
    # over shells with the pistol out still has to pay into something, or the
    # drop is lost for the sake of a rule about which gun is out.
    inv = ed.add_get_member_variable_node(WV.Inventory, WEAPON_COMP_CLASS_PATH)
    _connect(as_weapon, _pin(inv, "self"))

    loop = ed.add_macro_node(MACRO_FOR_EACH)
    if not loop:
        raise RuntimeError("could not create the ForEachLoop macro node")
    loop
    _connect(out(inv, WV.Inventory), _loose_pin(loop, "Array"))
    _connect(else_(has_gun), _loose_pin(loop, "Exec"))
    _connect(else_(takes_ammo), _loose_pin(loop, "Exec"))
    item = _loose_pin(loop, "ArrayElement", is_input=False)

    uses, uses_n = _prop(ed, IV.UsesAmmo, item)
    endless, endless_n = _prop(ed, IV.InfiniteReserve, item)
    finite = _node(ed, FN_NOT)
    _connect(endless, _pin(finite, "A"))
    counts = _node(ed, FN_AND)
    _connect(uses, _pin(counts, "A"))
    _connect(out(finite), _pin(counts, "B"))
    done_get = ed.add_get_member_variable_node(AV.Credited)
    fresh = _node(ed, FN_NOT)
    _connect(out(done_get, AV.Credited), _pin(fresh, "A"))
    wants = _node(ed, FN_AND)
    _connect(out(counts), _pin(wants, "A"))
    _connect(out(fresh), _pin(wants, "B"))

    give = ed.add_branch_node()
    _connect(out(wants), _pin(give, "Condition"))
    _connect(_loose_pin(loop, "LoopBody", is_input=False), _pin(give, "execute"))

    item_res, item_res_n = _prop(ed, IV.Reserve, item)
    shells = ed.add_get_member_variable_node(AV.Shells)
    richer = _node(ed, FN_ADD_II)
    _connect(item_res, _pin(richer, "A"))
    _connect(out(shells, AV.Shells), _pin(richer, "B"))
    store = ed.add_set_member_variable_node(IV.Reserve, ITEM_CLASS_PATH)
    _connect(item, _pin(store, "self"))
    _connect(out(richer), _pin(store, IV.Reserve))
    _connect(then(give), _pin(store, "execute"))

    mark = ed.add_set_member_variable_node(AV.Credited)
    _set(mark, AV.Credited, True)
    _connect(then(store), _pin(mark, "execute"))

    # --- and only then vanish -----------------------------------------------
    # Gated on Credited rather than destroyed unconditionally at the Completed
    # pin: a player with no shotgun who walks over the shells has not picked
    # anything up, and the drop has to still be there when they find one.
    took_get = ed.add_get_member_variable_node(AV.Credited)
    took = ed.add_branch_node()
    _connect(out(took_get, AV.Credited), _pin(took, "Condition"))
    _connect(_loose_pin(loop, "Completed", is_input=False), _pin(took, "execute"))
    _connect(then(held_mark), _pin(took, "execute"))
    gone = _node(ed, FN_DESTROY)
    _connect(then(took), _pin(gone, "execute"))

    ed.add_comment_to_nodes(
        f"{AMMO_DROP_SHELLS} shells, taken by walking within "
        f"{AMMO_PICKUP_RADIUS:.0f} cm of them. The distance is measured HERE "
        "rather than in the weapon component's Tick, so the cost is one Tick "
        "per dropped pickup instead of a GetAllActorsOfClass sweep every frame "
        "whether anything has been dropped or not. The shells go to the weapon "
        "in hand when that weapon takes shells (UsesAmmo and not InfiniteReserve, "
        "so never the pistol), and otherwise to the first carried one that does -- with four of five weapons using ammunition, "
        "\"first in the inventory\" would mean the shotgun in slot 0, always. "
        "Credited is the break ForEachLoop does not have.",
        [life, turn, delta, spin, pawn, there, here, gap, near, reached, comp,
         as_weapon_n, held_get, armed, has_gun, held_uses_n, held_endless_n,
         held_finite, held_wants, takes_ammo,
         held_res_n, held_shells, held_richer, held_store, held_mark,
         inv, loop, uses_n, endless_n, finite, counts, done_get, fresh, wants, give,
         item_res_n, shells, richer, store, mark, took_get, took, gone])

    arrange(ed)
    if not BEL.compile_blueprint(bp):
        raise RuntimeError("BP_AmmoPickup failed to compile")
    _apply_defaults(bp, {AV.Shells: AMMO_DROP_SHELLS, AV.Credited: False})
    _log(f"built {AMMO_BP_PATH} ({AMMO_DROP_SHELLS} shells, "
         f"{AMMO_PICKUP_RADIUS:.0f} cm, {AMMO_PICKUP_LIFETIME:.0f}s)")
    return bp
