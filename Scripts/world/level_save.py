"""Saving a generated level from the editor, without its navmesh.

The editor re-creates a RecastNavMesh whenever a level with a nav volume is
open (bForceRebuildOnLoad, DefaultEngine.ini), so a plain save writes that
actor into the .umap. A game world then loads it and never builds a tile:
only nav data the game spawns itself is built at start
(UNavigationSystemV1::OnWorldInitDone rebuilds what RequiresInitialRebuild,
which a loaded actor does not). PIE copies the editor's built tiles and so
hides it; a packaged or -game run has wanderers that never leave their spawn.

So every script that saves a generated level saves it through here.
"""

import unreal


def strip_nav_data():
    """Destroy the open level's RecastNavMesh actors. Returns how many."""
    sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    stale = [a for a in sub.get_all_level_actors() if isinstance(a, unreal.RecastNavMesh)]
    for actor in stale:
        sub.destroy_actor(actor)
    return len(stale)


def save_level(level_path):
    """Save the open level with no navmesh in it; raises if the save fails."""
    stripped = strip_nav_data()
    les = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    if not les.save_current_level():
        raise RuntimeError(f"could not save {level_path}")
    unreal.log_warning(f"[LEVEL] {level_path}: saved ({stripped} RecastNavMesh stripped)")
