"""The wanderers' Blackboard (BB_ForestWanderer, shared) and each controller's
Behavior Tree (BT_<controller>), authored as the RUNTIME tree.

    Wanderer (selector)
      Alive (sequence)
        Pulse                        possessed? corpse? stats, voice, patrol setup
        Act (selector)
          Hunt (sequence)  [Blackboard: Aggro is set]
            Chase, Swing, Wait 0.5
            (a stalker: Approach (selector): Stalk, Chase -- then Swing, Wait)
            (afraid of fire: Engage (selector): Ward, Attack (sequence):
             the approach, Swing -- then Wait)
          Notice (sequence)
            PlayerPresent
            Senses (selector): Hurt, Sight, Touch, Sound    (priority order)
          Patrol (sequence)
            Stroll, Wait 0.5
      Idle: Wait 0.5                 no pawn yet

A sense that fires sets Aggro (controller and Blackboard) and Notice
succeeds, so the next pass takes Hunt. Nothing clears Aggro. A corpse's
Pulse stops the tree (npc/corpse.py).

A stalker (forest_generator/npc_stalk.NPC_STALK_ROAR: the wendigo) hunts
before it chases. Its Stalk step (npc/stalk.py) succeeds while it roars and
comes in from tree to tree, having given its own move order, and fails once
it is close: the Approach selector then runs Chase, on that pass and every
one after.

A creature afraid of fire (forest_generator/npc_ward.NPC_WARD_FEARS: the
wendigo) tries its Ward step (npc/ward.py) before any of that. Held off, or
running away, the step succeeds and the pass is over: the approach and the
Swing sit together in a sequence the selector never reaches, which is what
keeps it from attacking. With no fire between them the step fails and the
attack runs as it always did. The Wait stays outside, one for both.

Why the runtime tree and not the editor graph: Python can write a
BehaviorTree's RootNode and each composite's Children, but it cannot build
the editor's graph nodes. It does not need to. An asset with no editor graph
gets one built FROM the runtime tree the first time it is opened in the BT
editor (UBehaviorTreeGraph::OnCreated -> SpawnMissingNodes), so the tree
shows and debugs as usual. The builder recreates the asset each run, because
an editor graph saved by hand would be stale against the new tree, and the
editor writes its graph back over the runtime tree when it saves.
"""

import unreal

from forest_generator.npc_placement import NPC_REPATH_SECONDS
from npc.graph import _asset_sub, _log
from npc.paths import (
    BB_AGGRO_KEY, BB_PATH, BB_REASON_KEY, STEP_CHASE, STEP_PRESENT, STEP_PULSE,
    STEP_STALK, STEP_STROLL, STEP_SWING, STEP_VAR, STEP_WARD,
)

_KEY_TYPES = {BB_AGGRO_KEY: "BlackboardKeyType_Bool",
              BB_REASON_KEY: "BlackboardKeyType_String"}


def _create(path, cls, factory):
    package, name = path.rsplit("/", 1)
    asset = unreal.AssetToolsHelpers.get_asset_tools().create_asset(
        name, package, cls, factory)
    if not asset:
        raise RuntimeError(f"could not create {path}")
    return asset


def build_blackboard():
    """BB_ForestWanderer: SelfActor (the factory's), Aggro, AggroReason."""
    eas = _asset_sub()
    bb = (eas.load_asset(BB_PATH) if eas.does_asset_exist(BB_PATH)
          else _create(BB_PATH, unreal.BlackboardData, unreal.BlackboardDataFactory()))
    keys = [k for k in bb.get_editor_property("keys")
            if str(k.get_editor_property("entry_name")) not in _KEY_TYPES]
    for name, type_name in _KEY_TYPES.items():
        entry = unreal.BlackboardEntry()
        entry.set_editor_property("entry_name", name)
        kind = unreal.load_class(None, f"/Script/AIModule.{type_name}")
        entry.set_editor_property("key_type", unreal.new_object(kind, bb))
        keys.append(entry)
    bb.set_editor_property("keys", keys)
    eas.save_loaded_asset(bb, False)
    return bb


def fresh_tree(path):
    """An empty BehaviorTree at ``path``: the old one deleted first, so no
    stale editor graph survives (see the module docstring). If the delete is
    refused, the old asset is reused and its runtime tree replaced."""
    eas = _asset_sub()
    if eas.does_asset_exist(path) and not eas.delete_asset(path):
        _log(f"note: could not delete {path}; rebuilding its tree in place "
             f"(an editor graph saved in it would now be stale)")
        return eas.load_asset(path)
    return _create(path, unreal.BehaviorTree, unreal.BehaviorTreeFactory())


# ── Nodes ────────────────────────────────────────────────────────────────────
#
# A child is (node, decorators). Every node is outered to the tree, so it is
# saved in the tree's package.

def _named(node, name):
    node.set_editor_property("node_name", name)
    return node


def _composite(bt, cls, name, children):
    node = _named(unreal.new_object(cls, bt), name)
    out = []
    for child, decorators in children:
        entry = unreal.BTCompositeChild()
        slot = ("child_composite" if isinstance(child, unreal.BTCompositeNode)
                else "child_task")
        entry.set_editor_property(slot, child)
        entry.set_editor_property("decorators", decorators)
        out.append(entry)
    node.set_editor_property("children", out)
    return node


def _step(bt, task_class, step):
    node = _named(unreal.new_object(task_class, bt), step)
    node.set_editor_property(STEP_VAR, step)
    return node


def _wait(bt, name):
    node = _named(unreal.new_object(unreal.BTTask_Wait, bt), name)
    seconds = node.get_editor_property("wait_time")
    seconds.set_editor_property("default_value", NPC_REPATH_SECONDS)
    node.set_editor_property("wait_time", seconds)
    return node


def _key_is_set(bt, key):
    node = _named(unreal.new_object(unreal.BTDecorator_Blackboard, bt), f"{key}?")
    selector = node.get_editor_property("blackboard_key")
    selector.set_editor_property("selected_key_name", key)
    node.set_editor_property("blackboard_key", selector)
    node.set_editor_property("basic_operation", unreal.BasicKeyOperation.SET)
    return node


def fill_tree(bt, bb, task_class, senses, stalks=False, wards=False):
    """Write the tree above into ``bt`` and save it. ``senses`` is the sense
    step names in priority order (npc/steps.py); ``stalks`` puts the Stalk
    step ahead of Chase, ``wards`` the Ward step ahead of the whole attack."""
    sel, seq = unreal.BTComposite_Selector, unreal.BTComposite_Sequence

    def step(name):
        return _step(bt, task_class, name), []

    approach = step(STEP_CHASE)
    if stalks:
        approach = (_composite(bt, sel, "Approach", [step(STEP_STALK), approach]), [])
    attack = [approach, step(STEP_SWING)]
    if wards:
        attack = [(_composite(bt, sel, "Engage", [
            step(STEP_WARD), (_composite(bt, seq, "Attack", attack), [])]), [])]
    hunt = _composite(bt, seq, "Hunt", attack + [(_wait(bt, "Re-path"), [])])
    feel = _composite(bt, sel, "Senses", [step(s) for s in senses])
    notice = _composite(bt, seq, "Notice", [step(STEP_PRESENT), (feel, [])])
    patrol = _composite(bt, seq, "Patrol", [step(STEP_STROLL),
                                            (_wait(bt, "Rest"), [])])
    act = _composite(bt, sel, "Act", [(hunt, [_key_is_set(bt, BB_AGGRO_KEY)]),
                                      (notice, []), (patrol, [])])
    alive = _composite(bt, seq, "Alive", [step(STEP_PULSE), (act, [])])
    root = _composite(bt, sel, "Wanderer", [(alive, []), (_wait(bt, "Idle"), [])])

    bt.set_editor_property("blackboard_asset", bb)
    bt.set_editor_property("root_node", root)
    _asset_sub().save_loaded_asset(bt, False)
    _log(f"built {bt.get_path_name()} (senses {', '.join(senses)}"
         f"{'; stalks before it chases' if stalks else ''}"
         f"{'; held off by fire' if wards else ''})")
    return bt
