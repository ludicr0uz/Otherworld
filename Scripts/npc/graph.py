"""Authoring helpers every NPC module shares: create/load a Blueprint, find
and connect pins, place nodes, set a pin literal and prove it landed, and
resolve a creature asset against its mannequin fallback.
"""

import unreal

from npc.nodes import FN_LITERAL_NAME


BGE = unreal.BlueprintGraphEditor
BEL = unreal.BlueprintEditorLibrary
PIN = unreal.BlueprintGraphPinLibrary


def _log(msg):
    unreal.log_warning(f"[NPC] {msg}")


def _try_set(obj, prop, value):
    """Set a property, logging instead of raising if the name moved."""
    try:
        obj.set_editor_property(prop, value)
    except Exception as exc:
        unreal.log_warning(f"[NPC] could not set {prop}: {exc}")


def _asset_sub():
    return unreal.get_editor_subsystem(unreal.EditorAssetSubsystem)


def _create_blueprint(path, parent_class):
    """
    Load the Blueprint at ``path``, creating it if absent.

    Deliberately does NOT delete-and-recreate: an existing asset is usually
    still referenced (by the level's NPC actor, or by the other blueprint's
    ai_controller_class), the delete then silently fails, and asset creation
    errors out. Updating in place is both more robust and idempotent.
    """
    eas = _asset_sub()
    if eas.does_asset_exist(path):
        existing = eas.load_asset(path)
        if existing:
            return existing
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


def _at(node, x, y):
    BEL.set_node_pos(node, unreal.IntPoint(int(x), int(y)))
    return node


def _node(ed, function_path):
    """add_call_function_node, but loud when the path does not resolve.

    An unresolvable path yields a *pinless* node rather than None, which
    surfaces much later as a baffling "pin 'self' not found on ''".
    """
    n = ed.add_call_function_node(function_path)
    if not n or not BEL.list_all_pins(n):
        raise RuntimeError(f"{function_path} is not a Blueprint-callable function")
    return n


def _palette(ed, name, x=0.0, y=0.0):
    n = ed.create_node_from_name(name, unreal.Vector2D(float(x), float(y)), [])
    if not n:
        raise RuntimeError(f"palette node {name!r} could not be created")
    return n


def _name_literal(ed, value, x, y):
    """A MakeLiteralName node holding ``value``; returns its output pin. See
    FN_LITERAL_NAME for which pins need it."""
    n = _at(_node(ed, FN_LITERAL_NAME), x, y)
    _set(n, "Value", value)
    return _pin(n, "ReturnValue", is_input=False)


def _loose_pin(node, wanted, is_input=True):
    """Find a pin ignoring spaces and case -- cast nodes name their output after
    the class with spaces inserted ("AsBP Health Component")."""
    key = wanted.replace(" ", "").lower()
    for p in (BEL.list_input_pins(node) if is_input else BEL.list_output_pins(node)):
        if str(PIN.get_pin_name(p)).replace(" ", "").lower() == key:
            return p
    raise RuntimeError(f"no pin like {wanted!r} on {BEL.get_node_title(node)}")


def _set(node, name, value):
    """Set a pin's literal and prove it landed.

    set_pin_value's return is not a usable signal (False means both "rejected"
    and "already equal to the default"), and a pin that quietly stays empty
    compiles as **zero** -- a melee attack for 0 damage at a range of 0, which
    looks perfect in the graph.
    """
    pin = _pin(node, name)
    pin.set_pin_value(str(value))
    got = str(PIN.get_pin_value(pin))
    if got == str(value):
        return
    try:
        if abs(float(got or 0.0) - float(value)) < 1e-6:
            return
    except ValueError:
        pass
    if got.lower() == str(value).lower() or got.endswith(f"::{value}"):
        return
    raise RuntimeError(f"pin {name!r} would not take {value!r} — reads back {got!r}")


# ── Body and animation ───────────────────────────────────────────────────────
#
# The wanderers wear Meshy creatures, each on its OWN skeleton, animated by
# its own A_<Creature>_ABP_Unarmed -- ABP_Unarmed retargeted onto that
# skeleton, state machine and blend space included, by
# Scripts/asset_pipeline/build_retarget.py.
# An anim BP is bound to one skeleton, so the mannequin's cannot drive a
# creature; retargeting the BLUEPRINT rather than a folder of clips is what
# makes the monsters usable by a Character at all.
#
# Every one of these lives under /Game/Sourced, which is git-ignored and
# rebuilt from assets/cache/meshy.  A checkout that has not run the asset
# pipeline therefore has none of them, and the mannequin pair it falls back to
# is the combination that shipped before the creatures existed -- a wanderer
# that looks wrong is a far better failure than a build that stops, and the log
# says loudly which one happened.
def _resolve(preferred, fallback, what):
    """First of the two that exists on disk, as an OBJECT path."""
    eas = _asset_sub()
    for pkg in (preferred, fallback):
        if eas.does_asset_exist(pkg):
            if pkg is fallback:
                unreal.log_warning(
                    f"[NPC] {what}: {preferred} is missing -- falling back to "
                    f"{pkg}. Run Scripts/asset_pipeline to build the creatures.")
            return f"{pkg}.{pkg.rsplit('/', 1)[-1]}"
    raise RuntimeError(f"[NPC] neither {preferred} nor {fallback} exists ({what})")


def _mesh_object(pkg):
    return f"{pkg}.{pkg.rsplit('/', 1)[-1]}"
