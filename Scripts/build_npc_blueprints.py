"""
build_npc_blueprints.py — Creates the forest NPC Blueprints from Python.

Run inside the editor:
    UnrealEditor-Cmd <uproject> -ExecutePythonScript="<abs>/Scripts/build_npc_blueprints.py" -NoUI -stdout

or import it from a generated level script and call ``ensure_npc_blueprints()``.

Two assets are produced under /Game/Forest/NPC:

  BP_ForestWandererAI  (parent AIController)  — the brain.  Event graph:

      [Event BeginPlay] --> [both ends on the navmesh?]
                                 ^     |            |
                                 |  yes|            |no
                                 |     v            v
                                 | [MoveToActor] [MoveToLocation,
                                 |  (pathfound)   no pathfinding]
                                 |     |            |
                                 |     '-----.------'
                                 |           v
                                 |   [in reach and off cooldown?]
                                 |           |            |
                                 |       yes |            | no
                                 |           v            |
                                 |  [arm next swing]      |
                                 |  [play MM_Attack_01]   |
                                 |  [player Health -= 12] |
                                 |           |            |
                                 '--- [Delay 0.5s] <------'

      [Get Player Pawn 0] --ReturnValue--> [MoveToActor.Goal]

      MoveToActor does the pathfinding, so the NPC runs *around* trees rather
      than into them.  Re-issuing it on a timer (instead of once) means the NPC
      keeps following a player who moves, and recovers on its own if the first
      request fires before the navmesh or the player pawn exist -- and that same
      loop is where the melee check lives, so there is one heartbeat rather than
      two that can disagree.

      The branch in front of it is the answer to a navigation DEAD ZONE: the
      navmesh covers a disc of radius 85 m inside a 200 m square of terrain, so
      a player who walks into the ring outside it cannot be pathed to at all.
      With bAllowPartialPath the request did not even fail -- it succeeded, at
      the island edge, and the pack stood there.  See NAV_REACHABLE_EXTENT_CM
      in npc_placement.py.

  BP_ForestWanderer    (parent Character)     — the body: mannequin mesh,
      running movement speed, and the controller above auto-possessing it.

The numbers (run speed, melee range/damage/interval, spawn band) all live in
forest_generator/npc_placement.py, which imports no `unreal`, so the host-side
generator and its offline checks read exactly what the editor builds.

These assets are level-independent — nothing here depends on map size, seed or
time of day — which is why they live in their own script instead of the
generated per-level one.
"""

import os
import sys

# The tuning constants live in the pure-Python placement module so the host-side
# generator can read them without importing `unreal`.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# A live editor keeps imported modules between runs, so an edit to any npc
# module would otherwise be ignored by the next build in the same editor.
for _name in [m for m in sys.modules if m == "npc" or m.startswith("npc.")]:
    del sys.modules[_name]

from forest_generator.npc_placement import NPC_VARIANTS          # noqa: E402
from npc.character import (                                     # noqa: E402
    build_npc_blueprint, build_variant_blueprint,
)
from npc.controller import build_ai_controller_blueprint         # noqa: E402
from npc.graph import _asset_sub, _log                           # noqa: E402
from npc.paths import AI_BP_PATH, NPC_BP_PATH                    # noqa: E402


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

    ai_bp = build_ai_controller_blueprint(rebuild=force)
    return build_npc_blueprint(ai_bp)


def ensure_npc_variants(force=False):
    """Every creature Blueprint the level can spawn, keyed by variant key.

    This is what a level generator wants; ``ensure_npc_blueprints`` builds the
    shared parent and is kept because the verify scripts address it by name.
    """
    base = ensure_npc_blueprints(force=force)
    eas = _asset_sub()
    out = {}
    for variant in NPC_VARIANTS:
        if not force and eas.does_asset_exist(variant.blueprint):
            out[variant.key] = eas.load_asset(variant.blueprint)
        else:
            out[variant.key] = build_variant_blueprint(base, variant)
    return out


if __name__ == "__main__":
    ensure_npc_variants(force=True)
    _log("done")
