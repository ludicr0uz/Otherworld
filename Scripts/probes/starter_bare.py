"""A probe's player starts with nothing worn, unless the probe says otherwise.

The game issues the pants already worn (the weapon component's
StarterPantsClass, combat/weapon_component/starter_worn.py). The probes were
written against a player who wears nothing: they count what is worn, read the
body bare and wear the test pants into an empty slot. So a launch empties the
class on the loaded Blueprint -- in memory, never saved -- before its level
opens, in every process of it, and each player is spawned bare.

A probe of the starting garment itself declares, at module level,

    STARTER_WORN = True

and a launch keeps the class when every probe in it does: the class is the
launch's, not a probe's, so such a probe batched with others runs bare and
passes only alone (the nightly sweep re-runs a batch's failure alone).
"""

import ast

FLAG = "STARTER_WORN"


def declared(path):
    """Does the probe file say ``STARTER_WORN = True``?"""
    try:
        with open(path, encoding="utf-8") as fh:
            body = ast.parse(fh.read()).body
    except (OSError, SyntaxError):
        return False
    for node in body:
        if isinstance(node, ast.Assign) and any(getattr(t, "id", "") == FLAG
                                                for t in node.targets):
            try:
                return ast.literal_eval(node.value) is True
            except ValueError:
                return False
    return False


def bare(paths):
    """Is this launch's player to start bare? Yes, unless every probe of it
    (and there is one) declares the starting garment."""
    return not (paths and all(declared(p) for p in paths))


def strip(keep):
    """Empty the weapon component's StarterPantsClass for this run. ``keep``
    holds the Blueprint, as make_writable's does: collected, it would load
    again from disk with the class."""
    import unreal
    from combat.paths import WEAPON_COMP_BP_PATH
    from combat.wear_tuning import STARTER_PANTS_CLASS_VAR
    bel = unreal.BlueprintEditorLibrary
    bp = unreal.load_asset(WEAPON_COMP_BP_PATH)
    unreal.get_default_object(bel.generated_class(bp)).set_editor_property(
        STARTER_PANTS_CLASS_VAR, None)
    bel.compile_blueprint(bp)
    keep.extend([bp, bel.generated_class(bp)])
    left = unreal.get_default_object(bel.generated_class(bp)).get_editor_property(
        STARTER_PANTS_CLASS_VAR)
    return [] if left is None else [f"{STARTER_PANTS_CLASS_VAR} would not empty: {left}"]
