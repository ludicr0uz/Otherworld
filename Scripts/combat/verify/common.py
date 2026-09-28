"""verify.common -- the check() ledger and the asset/graph reading helpers
every verifier section uses. No checks run here.
"""

import importlib
import pkgutil

import unreal

from combat.hit_zones import HEAD_BONES_VAR, LIMB_BONES_VAR


BGE = unreal.BlueprintGraphEditor
BEL = unreal.BlueprintEditorLibrary
PIN = unreal.BlueprintGraphPinLibrary
SDL = unreal.SubobjectDataBlueprintFunctionLibrary

PASS, FAIL = [], []


def check(label, ok, detail=""):
    (PASS if ok else FAIL).append(label)
    unreal.log_warning(f"[VERIFY] {'PASS' if ok else 'FAIL'}  {label}"
                       + (f" — {detail}" if detail else ""))


def load(path):
    return unreal.get_editor_subsystem(unreal.EditorAssetSubsystem).load_asset(path)


def graph(bp, name="EventGraph"):
    return BGE.get_graph_editor_by_name(bp, name)


def in_pins(node):
    return {str(PIN.get_pin_name(p)).replace(" ", "")
            for p in BEL.list_input_pins(node)}


def has_in_pin(node, name):
    """Does this node really have an input pin called ``name``?

    BEL.find_input_pin answers with an INVALID pin rather than None for a name
    the node does not have, so the obvious truthiness test matches every node in
    the graph -- it matched all 414 of them once, which is how this exists.
    """
    pin = BEL.find_input_pin(node, name)
    return bool(pin) and pin.is_valid()


def by_pins(nodes, *required):
    want = {r.replace(" ", "") for r in required}
    return [n for n in nodes if want <= in_pins(n)]


def pin_value(node, name):
    return str(PIN.get_pin_value(BEL.find_input_pin(node, name)))


def num_pin(node, name):
    """pin_value as a float, or None when the pin does not hold one.

    Sweeps like "is there any node whose B pin is 0.1" run over every node with
    a B pin, and in a graph with booleans in it that includes pins reading
    'false'. float() on those is a ValueError that stops the whole verifier.
    """
    try:
        return float(pin_value(node, name))
    except (TypeError, ValueError):
        return None


def cdo(bp):
    return unreal.get_default_object(BEL.generated_class(bp))


def component_template(bp, name):
    sds = unreal.get_engine_subsystem(unreal.SubobjectDataSubsystem)
    for h in sds.k2_gather_subobject_data_for_blueprint(bp):
        data = sds.k2_find_subobject_data_from_handle(h)
        if data and str(SDL.get_variable_name(data)) == name:
            return SDL.get_object(data)
    return None


def components(bp):
    sds = unreal.get_engine_subsystem(unreal.SubobjectDataSubsystem)
    out = []
    for h in sds.k2_gather_subobject_data_for_blueprint(bp):
        data = sds.k2_find_subobject_data_from_handle(h)
        if data:
            out.append(str(SDL.get_variable_name(data)))
    return out


def titled(nodes, title):
    """Nodes by their displayed title.

    The only handle Python gets on *which* function a call node wraps:
    BlueprintEditorLibrary exposes no get_function_name, and pin sets alone
    cannot tell GetCameraLocation from any other self-and-return node.
    """
    return [n for n in nodes
            if str(BEL.get_node_title(n)).replace("\n", " ") == title]


def out_pins(node):
    return {str(PIN.get_pin_name(p)) for p in BEL.list_output_pins(node)}


def _mesh_asset(bp):
    for name in components(bp):
        t = component_template(bp, name)
        if isinstance(t, unreal.SkeletalMeshComponent):
            return t.get_editor_property("skeletal_mesh_asset")
    return None


def zone_tables(bp):
    """The (head, limb) bone tables installed on bp's HealthComponent."""
    comp = component_template(bp, "HealthComponent")
    if not comp:
        return [], []
    return ([str(b) for b in comp.get_editor_property(HEAD_BONES_VAR)],
            [str(b) for b in comp.get_editor_property(LIMB_BONES_VAR)])


def builder_modules():
    """Every module of the combat builder package (not this verifier)."""
    import combat
    return [importlib.import_module(info.name)
            for info in pkgutil.walk_packages(combat.__path__, "combat.")
            if not info.name.startswith("combat.verify")]
