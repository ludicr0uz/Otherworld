"""Writing the bindings: each sound's takes into the Blueprint variable (or
component) that plays them.

The Blueprints' own builders call defaults_for() as they build; build_sound.py
calls apply_bindings() to write every binding again onto the Blueprints as
they stand, which is what lets a sound's mapping change with no other build.
"""

from combat.log import _log
from uebp.graph import (
    _apply_defaults, _assets, _component_object, _find_handle, _must_load)


def value_of(binding):
    """What the variable holds: the first take (``single``), else every take
    that has been imported -- an empty array is silence, not an error, so a
    checkout with no sounds installed still builds and plays."""
    if binding.single:
        return _must_load(binding.sound.paths[0])
    eas = _assets()
    return [eas.load_asset(p) for p in binding.sound.paths if eas.does_asset_exist(p)]


def defaults_for(blueprint, bindings):
    """{variable: its takes, loaded} for the Blueprint's class defaults."""
    return {b.variable: value_of(b) for b in bindings
            if b.blueprint == blueprint and not b.component}


def takes_of(blueprint, bindings):
    """{variable: the take names} of the Blueprint's array bindings."""
    return {b.variable: b.sound.names for b in bindings
            if b.blueprint == blueprint and not b.component and not b.single}


def apply_bindings(bindings):
    """Every binding onto its Blueprint, compiled and saved. A Blueprint that
    has not been built yet is skipped: its builder writes its own. Returns the
    Blueprints written."""
    eas = _assets()
    written = []
    for path in dict.fromkeys(b.blueprint for b in bindings):
        if not eas.does_asset_exist(path):
            _log(f"note: {path} is not built yet -- its builder gives it its sounds")
            continue
        bp = _must_load(path)
        rows = [b for b in bindings if b.blueprint == path]
        for b in rows:
            if not b.component:
                continue
            handle = _find_handle(bp, b.component)
            if handle is None:
                raise RuntimeError(f"{path} has no component {b.component}")
            _component_object(handle).set_editor_property(b.variable, value_of(b))
        _apply_defaults(bp, defaults_for(path, rows))
        written.append(path)
        _log(f"{path.rsplit('/', 1)[-1]}: " + ", ".join(
            f"{b.component + '.' if b.component else ''}{b.variable} = "
            f"{b.sound.names[0] if b.single else f'{len(b.sound.names)} x {b.sound.key}'}"
            for b in rows))
    return written
