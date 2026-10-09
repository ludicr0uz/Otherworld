"""BP_Profile: the SaveGame that holds a character between sessions.

A record, no graph -- the HUD fills it (profile_write.py) and reads it
(profile_read.py). Where the character stood is deliberately not in it: a
loaded profile starts wherever the level puts the player.
"""

from uebp.vars import declare
from graphics_menu.profile_consts import PROFILE_TABLE
import unreal

from combat.log import _log
from uebp.graph import BEL, BGE, _create_blueprint
from uebp.layout import arrange
from graphics_menu.profile_consts import PROFILE_BP_PATH, PROFILE_SLOT


def build_profile_savegame():
    """Create (or re-declare) BP_Profile and compile it."""
    bp = _create_blueprint(PROFILE_BP_PATH, unreal.SaveGame)
    ed = BGE.get_graph_editor_by_name(bp, "EventGraph")
    declare(ed, PROFILE_TABLE)
    arrange(ed)
    if not BEL.compile_blueprint(bp):
        raise RuntimeError("BP_Profile failed to compile")
    unreal.get_editor_subsystem(unreal.EditorAssetSubsystem).save_loaded_asset(bp)
    _log(f"built {PROFILE_BP_PATH} (slot {PROFILE_SLOT!r})")
    return bp
