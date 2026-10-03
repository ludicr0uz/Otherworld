"""BP_Profile: the SaveGame that holds a character between sessions.

A record, no graph -- the HUD fills it (profile_write.py) and reads it
(profile_read.py). Where the character stood is deliberately not in it: a
loaded profile starts wherever the level puts the player.
"""

import unreal

from combat.graph import (
    BEL, BGE, _create_blueprint, _declare, _float_type, _log, _must_load,
)
from combat.paths import ITEM_BP_PATH
from graphics_menu.profile_consts import (
    ITEM_FIELDS, EQUIPPED_FIELD, ITEM_CLASSES_FIELD, KILLS_FIELD,
    PROFILE_BP_PATH, PROFILE_SLOT, STAT_FIELDS,
)


def build_profile_savegame():
    """Create (or re-declare) BP_Profile and compile it."""
    bp = _create_blueprint(PROFILE_BP_PATH, unreal.SaveGame)
    ed = BGE.get_graph_editor_by_name(bp, "EventGraph")
    for field, _owner, _var in STAT_FIELDS:
        _declare(ed, field, _float_type())
    int_type = BEL.get_basic_type_by_name("int")
    _declare(ed, KILLS_FIELD, int_type)
    _declare(ed, EQUIPPED_FIELD, int_type)
    # Class of BP_WeaponItem, not of Actor: SpawnActorFromClass types its
    # return from the Class pin, and the spawned item goes into an array of
    # BP_WeaponItem.
    item_class = BEL.generated_class(_must_load(ITEM_BP_PATH))
    _declare(ed, ITEM_CLASSES_FIELD,
             BEL.get_array_type(BEL.get_class_reference_type(item_class)))
    for field, _item_var in ITEM_FIELDS:
        _declare(ed, field, BEL.get_array_type(int_type))
    if not BEL.compile_blueprint(bp):
        raise RuntimeError("BP_Profile failed to compile")
    unreal.get_editor_subsystem(unreal.EditorAssetSubsystem).save_loaded_asset(bp)
    _log(f"built {PROFILE_BP_PATH} (slot {PROFILE_SLOT!r})")
    return bp
