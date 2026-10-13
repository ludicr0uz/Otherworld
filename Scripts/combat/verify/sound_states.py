"""verify.sound_states -- the sounds of a state or of an item: the heartbeat at
low health, the breath of a spent sprint, a walker's rustle in a bush or a tree's low leaves, a
thrown axe's kill by the head, and each item's own takes, handled and used up
(Sound/sound_world.py, sound_items.py, sound_weapons.py).
"""

import unreal

from combat import footstep_vars as FV
from combat import health_vars as HV
from combat import item_vars as IV
from combat.chop_tuning import CHOPS_VAR
from combat.paths import FOOTSTEP_BP_PATH, MATCHES_BP_PATH, STICK_BP_PATH, WOOD_BP_PATH
from combat.verify.common import BEL, by_pins, cdo, check, graph, load, num_pin, pin_value
from combat.verify.fixtures import _eas, hg, wg
from combat.verify.anchor import feeders as _feeders, pure_feeds as _pure_feeds
from combat.verify import fx as fxv
from combat import fx_vars as FX
from combat.weapon_component import vars as WV
from combat.weapon_component.sprint import SPRINT_SPENT_VAR
from forest_generator.bush_placement import DEFAULT_BUSH_SPECS
from forest_generator.low_leaves import LEAVES, LOW_LEAF_TREE_SPECS, low_leaf_mesh_paths
from forest_generator.tree_meshes import TREE_MESH_RECIPES
from forest_import.tree_assets import GS_SPLIT, _source_geometry
from Sound.sound_items import HANDLE_ITEM, ITEM_HANDLING, ITEM_USE
from Sound.sound_world import (
    ACTOR_CLASS, BREATH_S, GRASS_RUSTLE, HEARTBEAT_S, LEAF_REACH_CM, LOW_HEALTH_FRACTION,
    RUSTLE_REACH_CM, RUSTLE_STRIDE_CM)
from survival.paths import CANTEEN_BP_PATH, MUSHROOM_BP_PATH


def _title(n):
    return str(BEL.get_node_title(n)).replace("\n", " ")


def _reads(node):
    """The titles of every pure node feeding ``node``."""
    return {_title(n) for n in _pure_feeds(node)}


def _plays_of(nodes, var):
    """The play nodes of ``nodes`` whose take is drawn from ``var``."""
    return [n for n in by_pins(nodes, "Sound", "Location") if f"Get {var}" in _reads(n)]


def _again(nodes, due_var, period, what, reads):
    """A sound played again while a state holds: one write of ``due_var``,
    ``period`` on from now, behind one Branch that reads ``reads``."""
    writes = [n for n in nodes if _title(n) == f"Set {due_var}"]
    gates = _feeders(writes[0], "execute") if len(writes) == 1 else []
    check(f"{what}: {due_var} is written in one place, behind one Branch",
          len(writes) == 1 and len(gates) == 1 and _title(gates[0]) == "Branch",
          f"{len(writes)} write(s), {len(gates)} feeder(s)")
    if len(gates) != 1:
        return
    asked = _reads(gates[0])
    check(f"...which asks {', '.join(reads)} and whether {due_var} has come",
          {f"Get {r}" for r in reads} | {f"Get {due_var}"} <= asked, str(sorted(asked)))
    check(f"...and puts it {period:g} s on from now, so the take plays again as it ends",
          any(num_pin(n, "B") == period for n in _feeders(writes[0], due_var)),
          str([pin_value(n, "B") for n in _feeders(writes[0], due_var)]))


def check_heart_and_breath():
    _again(hg, HV.HeartbeatNextTime, HEARTBEAT_S, "the heartbeat",
           (HV.Health, HV.MaxHealth, HV.DespawnOnDeath))
    lows = [n for n in hg if num_pin(n, "B") == LOW_HEALTH_FRACTION
            and "Get MaxHealth" in {_title(f) for f in _feeders(n, "A")}]
    check(f"...under {LOW_HEALTH_FRACTION:g} of MaxHealth", len(lows) == 1, str(len(lows)))
    check("...one of HeartbeatSounds", len(_plays_of(hg, HV.HeartbeatSounds)) == 1)
    _again(wg, WV.BreathNextTime, BREATH_S, "the breath of a spent sprint", (SPRINT_SPENT_VAR,))
    check("...one of BreathSounds", len(_plays_of(wg, WV.BreathSounds)) == 1)


def check_rustle():
    bp = load(FOOTSTEP_BP_PATH)
    fg = graph(bp).list_all_nodes()
    f = cdo(bp)
    meshes = [m.get_path_name().split(".")[0] for m in f.get_editor_property(FV.BushMeshes) if m]
    check("the footstep component knows the bush meshes",
          meshes == [s.mesh_path.split(".")[0] for s in DEFAULT_BUSH_SPECS], str(meshes))
    trees = [m.get_path_name() for m in f.get_editor_property(FV.LeafTreeMeshes) if m]
    check(f"...and both builds of the {len(LOW_LEAF_TREE_SPECS)} tree(s) with low leaves",
          bool(LOW_LEAF_TREE_SPECS) and trees == low_leaf_mesh_paths(), str(trees))
    got = [s.get_name() for s in f.get_editor_property(FV.RustleSounds) if s]
    check(f"...and holds the rustle's {len(GRASS_RUSTLE.names)} takes",
          got == list(GRASS_RUSTLE.names), str(got))
    finds = [n for n in by_pins(fg, "ActorClass") if ACTOR_CLASS in pin_value(n, "ActorClass")]
    check("BeginPlay asks every actor of the level (a tree cell has no tag to be found by)",
          len(finds) == 1, f"{len(finds)} find(s)")
    asks = by_pins(fg, "Center", "Radius")
    for comps, meshes_var, reach, what in (
            (FV.Bushes, FV.BushMeshes, RUSTLE_REACH_CM, "bushes"),
            (FV.LeafTrees, FV.LeafTreeMeshes, LEAF_REACH_CM, "trees with low leaves")):
        adds = [n for n in by_pins(fg, "TargetArray", "NewItem")
                if f"Get {comps}" in {_title(x) for x in _feeders(n, "TargetArray")}]
        check(f"...and keeps the {what}: those whose instanced component's mesh is one of "
              f"{meshes_var}, into {comps}",
              len(adds) == 1 and {f"Get {meshes_var}", "Get StaticMesh"} <= {
                  t for g in _feeders(adds[0], "execute") for t in _reads(g)},
              f"{len(adds)} add(s)")
        mine = [n for n in asks if num_pin(n, "Radius") == reach]
        check(f"a walker asks each of the {what} for an instance within {reach:g} cm of them",
              len(asks) == 2 and len(mine) == 1 and num_pin(mine[0], "Radius") == reach,
              f"{len(mine)} of {len(asks)} overlap node(s)")
    # The rustle's own measure: a bush crossed is more than the one footfall's.
    stride = f.get_editor_property(FV.RustleStrideCm)
    check(f"...every {RUSTLE_STRIDE_CM:g} cm of ground covered (RustleStrideCm), "
          "under a footfall's stride",
          isinstance(stride, float) and stride == RUSTLE_STRIDE_CM
          and stride < f.get_editor_property(FV.StrideCm), str(stride))
    spent = [n for n in fg if _title(n) == f"Set {FV.RustleTravelled}"]
    gates = [n for n in fg if _title(n) == "Branch" and {
        f"Get {FV.RustleTravelled}", f"Get {FV.RustleStrideCm}"} <= _reads(n)]
    check("...measured by RustleTravelled: added to each frame on the ground, and the "
          "stride taken off it behind the one Branch that compares the two",
          len(spent) == 2 and len(gates) == 1
          and sum(gates[0] in _feeders(n, "execute") for n in spent) == 1,
          f"{len(spent)} write(s), {len(gates)} gate(s)")
    rustles = _plays_of(fg, FV.RustleSounds)
    marks = [n for n in fg if _title(n) == f"Set {FV.InBush}"]
    check("...and, at one, plays one of RustleSounds: InBush is lowered before the "
          "walks over Bushes and LeafTrees and raised in each",
          len(rustles) == 1 and len(marks) == 3, f"{len(rustles)} play(s), {len(marks)} write(s)")


# How far a built tree's lowest leaf may be from the table's, in cm.
LEAF_FLOOR_TOLERANCE_CM = 5.0


def check_low_leaves():
    """The measure the choice of trees rests on (forest_generator/low_leaves.py)."""
    for recipe in TREE_MESH_RECIPES:
        slot, floor = LEAVES[recipe.name]
        _all, parts, slots = GS_SPLIT.split_mesh_by_material_i_ds(
            _source_geometry(load(recipe.path)), None)
        low = [unreal.GeometryScript_MeshQueries.get_mesh_bounding_box(part).min.z
               for part, s in zip(parts, slots) if s == slot]
        check(f"{recipe.name}'s lowest leaf is {floor:g} cm over its foot, as the choice of "
              "the trees that rustle has it",
              len(low) == 1 and abs(low[0] - floor) <= LEAF_FLOOR_TOLERANCE_CM, str(low))


def check_head_kill():
    kills = _plays_of(wg, WV.HeadKillSounds)
    stabs = _plays_of(wg, WV.LodgeSounds)
    check("a thrown blade into a body is heard once, by one of two sounds",
          len(kills) == 1 and len(stabs) == 1, f"{len(kills)} kill, {len(stabs)} stab")
    if len(kills) != 1 or len(stabs) != 1:
        return
    # Each play is behind its "are there takes" Branch; the picking Branch is behind that.
    picks = [g for p in (kills[0], stabs[0]) for gate in _feeders(p, "execute")
             for g in _feeders(gate, "execute")]
    check("...picked by one Branch, inside Fx_Stab, on the event's HeadKill",
          len(picks) == 2 and picks[0] == picks[1] and _title(picks[0]) == "Branch"
          and _feeders(picks[0], "Condition") == [fxv.event(FX.fx_event(FX.STAB))],
          str([_title(p) for p in picks]))
    if not picks:
        return
    # What the server tells it: the pure chain feeding the Multicast's HeadKill.
    told = fxv.calls(FX.STAB)
    asked = set().union(*[_reads(c) for c in told]) if told else set()
    check("...the kill's where an item that Chops (the axe) struck the head and took a "
          "body not yet Dead to no Health: what the server's tell of Multicast_Stab reads",
          len(told) == 1 and {f"Get {CHOPS_VAR}", f"Get {HV.Dead}", f"Get {HV.Health}"} <= asked
          and any("Contains" in t.replace(" ", "") for t in asked), str(sorted(asked)))


def _takes(path, var):
    return [s.get_name() for s in cdo(load(path)).get_editor_property(var) if s]


def check_item_sounds():
    wrong = [f"{path.rsplit('/', 1)[-1]}: {_takes(path, IV.HandleSounds)}"
             for path, sound in ITEM_HANDLING.items()
             if _eas.does_asset_exist(path) and _takes(path, IV.HandleSounds) != list(sound.names)]
    check(f"each of the {len(ITEM_HANDLING)} items with a handling sound of its type holds "
          "its takes (a gun's, a blade's, a garment's, the base item's)", not wrong, str(wrong))
    plain = (MATCHES_BP_PATH, STICK_BP_PATH, WOOD_BP_PATH, MUSHROOM_BP_PATH, CANTEEN_BP_PATH)
    wrong = [p.rsplit("/", 1)[-1] for p in plain if _eas.does_asset_exist(p)
             and _takes(p, IV.HandleSounds) != list(HANDLE_ITEM.names)]
    check("...and an item with no row of its own inherits the base item's", not wrong, str(wrong))
    for path, sound in ITEM_USE.items():
        if _eas.does_asset_exist(path):
            check(f"{path.rsplit('/', 1)[-1]} used up plays {sound.key}",
                  _takes(path, IV.UseSounds) == list(sound.names), str(_takes(path, IV.UseSounds)))
    if _eas.does_asset_exist(CANTEEN_BP_PATH):
        check("the canteen has no use sound yet", _takes(CANTEEN_BP_PATH, IV.UseSounds) == [])
    handled = _plays_of(wg, IV.HandleSounds)
    writes = [n for n in wg if _title(n) == f"Set {WV.HandledItem}"]
    named = [n for n in writes if _feeders(n, WV.HandledItem)]
    # Twice over: where the server serves a move (slot_moves.py), and where a
    # client's picture follows the record (view.py: one more write names it).
    check("a slot move names its item in HandledItem (to hand, put back, moved; on a "
          "client, the item whose slot the record changed) and a play draws from that "
          "item's HandleSounds, after which it is let go",
          len(handled) == 2 and len(named) == 4 and len(writes) == 6
          and all(f"Get {WV.HandledItem}" in _reads(h) for h in handled),
          f"{len(handled)} play(s), {len(named)} of {len(writes)} write(s) name an item")
    eaten = _plays_of(wg, IV.UseSounds)
    check("a consumable used up plays one of its own UseSounds, before it is spent",
          len(eaten) == 1, f"{len(eaten)} play(s)")


def run():
    check_heart_and_breath()
    check_rustle()
    check_low_leaves()
    check_head_kill()
    check_item_sounds()
