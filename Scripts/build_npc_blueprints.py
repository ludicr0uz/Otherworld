"""
build_npc_blueprints.py — Creates the forest NPC Blueprints from Python.

Run inside the editor:
    UnrealEditor-Cmd <uproject> -ExecutePythonScript="<abs>/Scripts/build_npc_blueprints.py" -NoUI -stdout

or import it from a generated level script and call ``ensure_npc_blueprints()``.

Two assets are produced under /Game/Forest/NPC:

  BP_ForestWandererAI  (parent AIController)  — the brain.  Event graph:

      [Event BeginPlay] --exec--> [MoveToActor] --exec--> [Delay 0.5s] --,
                                       ^                                 |
                                       '---------------------------------'
      [Get Player Pawn 0] --ReturnValue--> [MoveToActor.Goal]

      MoveToActor does the pathfinding, so the NPC walks *around* trees
      rather than into them.  Re-issuing it on a timer (instead of once) means
      the NPC keeps following a player who moves, and recovers on its own if
      the first request fires before the navmesh or the player pawn exist.

  BP_ForestWanderer    (parent Character)     — the body: mannequin mesh,
      slow walk speed, and the controller above auto-possessing it.

These assets are level-independent — nothing here depends on map size, seed or
time of day — which is why they live in their own script instead of the
generated per-level one.
"""

import os
import sys

import unreal

# The tuning constants live in the pure-Python placement module so the host-side
# generator can read them without importing `unreal`.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from forest_generator.npc_placement import (
    NPC_WALK_SPEED_CMS,
    NPC_ACCEPTANCE_RADIUS_CM,
    NPC_REPATH_SECONDS,
)

# ─── Configuration ───────────────────────────────────────────────────────────

NPC_DIR = "/Game/Forest/NPC"
AI_BP_PATH = f"{NPC_DIR}/BP_ForestWandererAI"
NPC_BP_PATH = f"{NPC_DIR}/BP_ForestWanderer"

SKELETAL_MESH_PATH = "/Game/Characters/Mannequins/Meshes/SKM_Manny_Simple.SKM_Manny_Simple"
ANIM_BP_PATH = "/Game/Characters/Mannequins/Anims/Unarmed/ABP_Unarmed.ABP_Unarmed_C"

# Function paths for the graph nodes
FN_MOVE_TO_ACTOR = "/Script/AIModule.AIController.MoveToActor"
FN_GET_PLAYER_PAWN = "/Script/Engine.GameplayStatics.GetPlayerPawn"
FN_DELAY = "/Script/Engine.KismetSystemLibrary.Delay"

BGE = unreal.BlueprintGraphEditor
BEL = unreal.BlueprintEditorLibrary


def _log(msg):
    unreal.log_warning(f"[NPC] {msg}")


def _asset_sub():
    return unreal.get_editor_subsystem(unreal.EditorAssetSubsystem)


def _create_blueprint(path, parent_class):
    """Create (replacing any existing) a Blueprint asset with the given parent."""
    eas = _asset_sub()
    if eas.does_asset_exist(path):
        eas.delete_asset(path)
    package_path, asset_name = path.rsplit("/", 1)
    factory = unreal.BlueprintFactory()
    factory.set_editor_property("parent_class", parent_class)
    bp = unreal.AssetToolsHelpers.get_asset_tools().create_asset(
        asset_name, package_path, unreal.Blueprint, factory)
    if not bp:
        raise RuntimeError(f"Could not create Blueprint {path}")
    return bp


def _pin(node, name, is_input=True):
    """Find a pin by name, raising with a useful message if it is missing."""
    p = (BEL.find_input_pin(node, name) if is_input
         else BEL.find_output_pin(node, name))
    if not p or not p.is_valid():
        raise RuntimeError(
            f"pin {name!r} ({'in' if is_input else 'out'}) not found on "
            f"{type(node).__name__}")
    return p


def _connect(a, b):
    if not a.try_create_connection(b):
        raise RuntimeError("could not connect pins")


# ─── The AI controller ──────────────────────────────────────────────────────

def build_ai_controller_blueprint():
    """Create BP_ForestWandererAI and author its chase loop."""
    bp = _create_blueprint(AI_BP_PATH, unreal.AIController)
    ed = BGE.get_graph_editor_by_name(bp, "EventGraph")
    if not ed:
        raise RuntimeError("BP_ForestWandererAI has no EventGraph")

    # A freshly created Blueprint already carries a (disabled) BeginPlay event
    # node; connecting to it is what turns it on.
    begin_play = ed.find_event_node("ReceiveBeginPlay")
    if not begin_play:
        raise RuntimeError("could not find the ReceiveBeginPlay event node")
    origin = BEL.get_node_pos(begin_play)

    move_to = ed.add_call_function_node(FN_MOVE_TO_ACTOR)
    get_pawn = ed.add_call_function_node(FN_GET_PLAYER_PAWN)
    delay = ed.add_call_function_node(FN_DELAY)

    BEL.set_node_pos(move_to, unreal.IntPoint(origin.x + 340, origin.y))
    BEL.set_node_pos(get_pawn, unreal.IntPoint(origin.x + 40, origin.y + 220))
    BEL.set_node_pos(delay, unreal.IntPoint(origin.x + 780, origin.y))

    # Goal = the player pawn
    _pin(get_pawn, "PlayerIndex").set_pin_value("0")
    _connect(_pin(get_pawn, "ReturnValue", is_input=False), _pin(move_to, "Goal"))

    # Pathfinding is what makes it walk around the trees rather than into them.
    _pin(move_to, "AcceptanceRadius").set_pin_value(str(NPC_ACCEPTANCE_RADIUS_CM))
    _pin(move_to, "bUsePathfinding").set_pin_value("true")
    _pin(move_to, "bStopOnOverlap").set_pin_value("true")
    _pin(move_to, "bAllowPartialPath").set_pin_value("true")

    _pin(delay, "Duration").set_pin_value(str(NPC_REPATH_SECONDS))

    # BeginPlay -> MoveToActor -> Delay -> back to MoveToActor (a chase loop)
    _connect(BEL.find_then_pin(begin_play), BEL.find_execute_pin(move_to))
    _connect(BEL.find_then_pin(move_to), BEL.find_execute_pin(delay))
    _connect(BEL.find_then_pin(delay), BEL.find_execute_pin(move_to))

    ed.add_comment_to_nodes(
        "Re-issue a pathfinding move order at the player twice a second.",
        [move_to, get_pawn, delay])

    if not BEL.compile_blueprint(bp):
        raise RuntimeError("BP_ForestWandererAI failed to compile")
    _asset_sub().save_loaded_asset(bp)
    _log(f"built {AI_BP_PATH}")
    return bp


# ─── The character ──────────────────────────────────────────────────────────

def build_npc_blueprint(ai_bp):
    """Create BP_ForestWanderer and point it at the AI controller."""
    bp = _create_blueprint(NPC_BP_PATH, unreal.Character)
    eas = _asset_sub()

    generated = BEL.generated_class(bp)
    cdo = unreal.get_default_object(generated)

    # Possession: the controller must take over wherever the NPC comes from.
    cdo.set_editor_property("ai_controller_class", BEL.generated_class(ai_bp))
    cdo.set_editor_property(
        "auto_possess_ai", unreal.AutoPossessAI.PLACED_IN_WORLD_OR_SPAWNED)

    # Body — reuse the template mannequin so the walk animates.
    mesh_comp = cdo.get_editor_property("mesh")
    skel = eas.load_asset(SKELETAL_MESH_PATH)
    if skel:
        mesh_comp.set_editor_property("skeletal_mesh_asset", skel)
    else:
        unreal.log_error(f"[NPC] missing skeletal mesh {SKELETAL_MESH_PATH}")
    anim_class = unreal.load_class(None, ANIM_BP_PATH)
    if anim_class:
        mesh_comp.set_editor_property("anim_class", anim_class)
    else:
        unreal.log_error(f"[NPC] missing anim blueprint {ANIM_BP_PATH}")
    # Stock Character capsule is 88 cm half-height; drop the mesh to its feet
    # and face it down +X, matching the third-person template.
    mesh_comp.set_editor_property("relative_location", unreal.Vector(0, 0, -89.0))
    mesh_comp.set_editor_property(
        "relative_rotation", unreal.Rotator(pitch=0.0, yaw=-90.0, roll=0.0))

    movement = cdo.get_editor_property("character_movement")
    movement.set_editor_property("max_walk_speed", NPC_WALK_SPEED_CMS)
    # Turn in place smoothly instead of snapping to each new path segment.
    movement.set_editor_property(
        "rotation_rate", unreal.Rotator(pitch=0.0, yaw=180.0, roll=0.0))
    movement.set_editor_property("orient_rotation_to_movement", True)
    # A stock Character has use_controller_rotation_yaw = True, which forces the
    # pawn's yaw to the controller's every frame and fights the line above.
    # The third-person template turns it off for the same reason.
    cdo.set_editor_property("use_controller_rotation_yaw", False)

    if not BEL.compile_blueprint(bp):
        raise RuntimeError("BP_ForestWanderer failed to compile")
    eas.save_loaded_asset(bp)
    _log(f"built {NPC_BP_PATH} (walk speed {NPC_WALK_SPEED_CMS} cm/s)")
    return bp


# ─── Entry point ────────────────────────────────────────────────────────────

def ensure_npc_blueprints(force=False):
    """
    Build both NPC Blueprints, returning the character Blueprint.

    Idempotent: with ``force=False`` existing assets are reused, which keeps
    re-generating a level cheap and preserves any hand edits.
    """
    eas = _asset_sub()
    if not force and eas.does_asset_exist(NPC_BP_PATH) and eas.does_asset_exist(AI_BP_PATH):
        _log("NPC blueprints already exist — reusing")
        return eas.load_asset(NPC_BP_PATH)

    ai_bp = build_ai_controller_blueprint()
    return build_npc_blueprint(ai_bp)


if __name__ == "__main__":
    ensure_npc_blueprints(force=True)
    _log("done")
