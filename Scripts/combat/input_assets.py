"""The Enhanced Input assets (I1): IA_Fire and the game's mapping context,
IMC_Default, and their names on the player character's class defaults.

The fire key is the first key that is an input action rather than a poll on
the weapon component's Tick. The action is a bool with no trigger of its
own: its Started is the press, its Completed the release, and the native
character hands both to the weapon component (weapon_component/trigger.py
has the graph's half). The context maps it to the default key in
tuning.FIRE_KEY; the settings page's rebinding rewrites that one row at
runtime (OtherworldCharacter::SetFireKey), from the saved Binds.

    trigger_when_paused   on: paused, the engine reports no trigger state at
                          all, so a button still down when the pause ends
                          would read as a fresh press, and the click that
                          closed the menu would be a shot. The native side
                          drops a press that arrives paused instead.
    consume_input         off: a player may bind the trigger to a key
                          another context reads, and the polled keys never
                          took a key from anything either.
"""

import unreal

from combat.input_consts import (
    CONTEXT_PROP, FIRE_ACTION_PROP, IA_FIRE, IMC_DEFAULT, MAPPINGS)
from combat.log import _log
from uebp.graph import BEL, _must_load


def _assets():
    return unreal.get_editor_subsystem(unreal.EditorAssetSubsystem)


def _ensure(path, cls, factory):
    if _assets().does_asset_exist(path):
        return _must_load(path)
    folder, name = path.rsplit("/", 1)
    asset = unreal.AssetToolsHelpers.get_asset_tools().create_asset(name, folder, cls, factory)
    if asset is None:
        raise RuntimeError(f"could not create {path}")
    return asset


def build_action(path):
    """A pressed-or-not action at ``path``. Returns it."""
    action = _ensure(path, unreal.InputAction, unreal.InputAction_Factory())
    action.set_editor_property("value_type", unreal.InputActionValueType.BOOLEAN)
    action.set_editor_property("trigger_when_paused", True)
    action.set_editor_property("consume_input", False)
    action.set_editor_property("triggers", [])
    action.set_editor_property("modifiers", [])
    _assets().save_loaded_asset(action, only_if_is_dirty=False)
    return action


def build_input_assets():
    """Every action of MAPPINGS and the context that maps each to its
    default key, one row per action. Returns the context."""
    context = _ensure(IMC_DEFAULT, unreal.InputMappingContext,
                      unreal.InputMappingContext_Factory())
    context.unmap_all()
    for path, key_name in MAPPINGS:
        key = unreal.Key()
        key.import_text(key_name)
        context.map_key(build_action(path), key)
    _assets().save_loaded_asset(context, only_if_is_dirty=False)
    _log(f"input: {IMC_DEFAULT.rsplit('/', 1)[1]} maps "
         f"{', '.join(f'{p.rsplit(chr(47), 1)[1]} to {k}' for p, k in MAPPINGS)}")
    return context


def install_input(bp):
    """Name the context and the trigger on the player character's class
    defaults, where the native parent reads them."""
    cdo = unreal.get_default_object(BEL.generated_class(bp))
    for prop, path in ((CONTEXT_PROP, IMC_DEFAULT), (FIRE_ACTION_PROP, IA_FIRE)):
        asset = _must_load(path)
        cdo.set_editor_property(prop, asset)
        if cdo.get_editor_property(prop) != asset:
            raise RuntimeError(f"{bp.get_name()}.{prop} did not take {path}")
