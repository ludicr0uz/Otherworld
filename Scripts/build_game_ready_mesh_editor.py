"""build_game_ready_mesh_editor.py -- the editor's half of
build_game_ready_mesh.py, which runs it through uepy.py. Not run by hand: it
does the stage that script's request names (mesh_lod/editor_build.py).
"""

import os
import sys

import unreal

SCRIPTS = os.path.join(unreal.Paths.project_dir(), "Scripts")
if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)
for _name in [m for m in sys.modules if m.startswith(("mesh_lod", "forest_import.tree_assets"))]:
    del sys.modules[_name]

from mesh_lod import editor_build    # noqa: E402

editor_build.main()
