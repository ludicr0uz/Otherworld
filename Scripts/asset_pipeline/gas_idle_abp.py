"""gas_idle_abp -- ABP_GasIdle, the minimal anim blueprint on
SK_UEFN_Mannequin: one sequence player, the sample's standing idle, into the
output pose.  It is the proof of the skeleton bridge and nothing more: the
motion-matching graph (SandboxCharacter_CMC_ABP) takes its place when the
locomotion is wired.
"""

import unreal

from asset_pipeline.gas_bridge_paths import ABP_GAS_IDLE, HIDDEN_SKELETON_GAS, IDLE_CLIP
from asset_pipeline.rig_util import _load, _log
from uebp.graph import _connect, _palette, _pin
from uebp.layout import arrange

EAL = unreal.EditorAssetLibrary
BEL = unreal.BlueprintEditorLibrary

ROOT_CLASS = "AnimGraphNode_Root"
PLAYER_CLASS = "AnimGraphNode_SequencePlayer"


def _play_node_name(clip_pkg):
    """The palette's entry for a sequence player of one clip.  It exists
    only once the clip is loaded and is on the blueprint's skeleton."""
    return f"Animation|Sequences|Play'{clip_pkg.rsplit('/', 1)[1]}'"


def playing(bp):
    """The object paths of the clips ``bp``'s anim graph plays, one per
    sequence player.  The node's Sequence is not a Python property; it is
    read out of the node's text."""
    ed = unreal.BlueprintGraphEditor.get_graph_editor_by_name(bp, "AnimGraph")
    out = []
    for node in ed.list_all_nodes():
        if node.get_class().get_name() != PLAYER_CLASS:
            continue
        text = node.get_editor_property("node").export_text()
        value = text.split("Sequence=", 1)[1].split(",", 1)[0].strip('"')
        out.append(value.split("'")[1] if "'" in value else value)
    return out


def build_idle_blueprint():
    """Create ABP_GasIdle, or wipe its anim graph, and author it."""
    _load(IDLE_CLIP)
    if not EAL.does_asset_exist(ABP_GAS_IDLE):
        factory = unreal.AnimBlueprintFactory()
        factory.set_editor_property("target_skeleton", _load(HIDDEN_SKELETON_GAS))
        factory.set_editor_property("parent_class", unreal.AnimInstance)
        folder, name = ABP_GAS_IDLE.rsplit("/", 1)
        if not unreal.AssetToolsHelpers.get_asset_tools().create_asset(
                name, folder, unreal.AnimBlueprint, factory):
            raise RuntimeError(f"could not create {ABP_GAS_IDLE}")
    bp = _load(ABP_GAS_IDLE)
    ed = unreal.BlueprintGraphEditor.get_graph_editor_by_name(bp, "AnimGraph")
    if not ed:
        raise RuntimeError(f"{ABP_GAS_IDLE} has no AnimGraph")
    stale = [n for n in ed.list_all_nodes() if n.get_class().get_name() != ROOT_CLASS]
    if stale:
        ed.remove_nodes(stale)
    roots = [n for n in ed.list_all_nodes() if n.get_class().get_name() == ROOT_CLASS]
    if len(roots) != 1:
        raise RuntimeError(f"{ABP_GAS_IDLE}: expected one output pose, found {len(roots)}")
    player = _palette(ed, _play_node_name(IDLE_CLIP))
    _connect(_pin(player, "Pose", is_input=False), _pin(roots[0], "Result"))
    arrange(ed)
    if not BEL.compile_blueprint(bp):
        raise RuntimeError(f"{ABP_GAS_IDLE} failed to compile")
    EAL.save_asset(ABP_GAS_IDLE)
    clip = f"{IDLE_CLIP}.{IDLE_CLIP.rsplit('/', 1)[1]}"
    got = playing(_load(ABP_GAS_IDLE))
    if got != [clip]:
        raise RuntimeError(f"{ABP_GAS_IDLE} plays {got}, not {clip}")
    _log(f"{ABP_GAS_IDLE}: plays {IDLE_CLIP.rsplit('/', 1)[1]} on "
         f"{HIDDEN_SKELETON_GAS.rsplit('/', 1)[1]}")
    return bp
