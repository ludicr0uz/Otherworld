"""Build the dark grass's material instances (the meadow's and the six other
types', L.LOW_GRASS_TYPES), tint the ground under them, and verify all of
it.

Called by the generated import_<Level>.py (step 5a) and verify_<Level>.py. The
numbers and the reasons are forest_generator/grass_look.py's.

The instances are ours, under /Game/Forest/Materials, each a child of its grass
pack's own instance: the pack asset is read and never written. The ground
material is ours too but no script authors it (it was made by hand and is
only assigned by the import), so it is patched in place: its base colour goes
through a desaturation and a multiply, each driven by a parameter, and a
second run only rewrites the two parameters.
"""

import unreal

from forest_generator import grass_look as L
from forest_import.undergrowth_assets import dependencies

MEL = unreal.MaterialEditingLibrary
BASE_COLOR = unreal.MaterialProperty.MP_BASE_COLOR
_TOLERANCE = 1e-4


def _log(msg):
    unreal.log_warning(f"[GEN] {msg}")


def _must_load(path):
    asset = unreal.get_editor_subsystem(unreal.EditorAssetSubsystem).load_asset(path)
    if not asset:
        raise RuntimeError(f"{path} is missing")
    return asset


def _color(rgb):
    return unreal.LinearColor(rgb[0], rgb[1], rgb[2], 1.0)


def _same_color(color, rgb):
    return all(abs(a - b) < _TOLERANCE for a, b in zip((color.r, color.g, color.b), rgb))


# ─── The grass's instance ────────────────────────────────────────────────────

def _ensure_instance(path, parent_path, tint):
    """One dark instance: ``path``, a child of ``parent_path``, with
    GRASS_SCALARS and ``tint``."""
    eas = unreal.get_editor_subsystem(unreal.EditorAssetSubsystem)
    parent = _must_load(parent_path)
    if eas.does_asset_exist(path):
        instance = _must_load(path)
    else:
        folder, name = path.rsplit("/", 1)
        instance = unreal.AssetToolsHelpers.get_asset_tools().create_asset(
            name, folder, unreal.MaterialInstanceConstant,
            unreal.MaterialInstanceConstantFactoryNew())
        if not instance:
            raise RuntimeError(f"could not create {path}")
    MEL.set_material_instance_parent(instance, parent)
    known = {str(n) for n in MEL.get_scalar_parameter_names(parent)}
    for name, value in L.GRASS_SCALARS.items():
        if name not in known:
            raise RuntimeError(f"{parent_path} has no parameter {name!r}")
        MEL.set_material_instance_scalar_parameter_value(instance, name, value)
    MEL.set_material_instance_vector_parameter_value(instance, "Tint", _color(tint))
    MEL.update_material_instance(instance)
    eas.save_loaded_asset(instance, False)
    _log(f"   {path}: tint {tint}, {L.GRASS_SCALARS}")


def _ensure_grass_material():
    _ensure_instance(L.GRASS_MATERIAL, L.GRASS_MATERIAL_PARENT, L.GRASS_TINT)
    for t in L.LOW_GRASS_TYPES:
        _ensure_instance(t.material, t.material_parent, t.tint)


# ─── The ground ──────────────────────────────────────────────────────────────

def _parameters(material):
    """The ground material's two look parameters, by name, found by walking
    back from its base colour ({} for a material not patched yet)."""
    found, seen = {}, []
    todo = [MEL.get_material_property_input_node(material, BASE_COLOR)]
    while todo:
        node = todo.pop()
        if node is None or node in seen:
            continue
        seen.append(node)
        if isinstance(node, (unreal.MaterialExpressionVectorParameter,
                             unreal.MaterialExpressionScalarParameter)):
            found[str(node.get_editor_property("parameter_name"))] = node
        todo.extend(MEL.get_inputs_for_material_expression(material, node))
    return {name: found[name] for name in (L.GROUND_TINT_PARAM, L.GROUND_SATURATION_PARAM)
            if name in found}


def _patch_ground(material):
    """base colour -> desaturate(1 - GroundSaturation) -> x GroundTint."""
    source = MEL.get_material_property_input_node(material, BASE_COLOR)
    output = MEL.get_material_property_input_node_output_name(material, BASE_COLOR)
    if source is None:
        raise RuntimeError(f"{L.GROUND_MATERIAL} has no base colour to tint")

    def make(cls):
        return MEL.create_material_expression(material, cls)

    saturation = make(unreal.MaterialExpressionScalarParameter)
    saturation.set_editor_property("parameter_name", L.GROUND_SATURATION_PARAM)
    tint = make(unreal.MaterialExpressionVectorParameter)
    tint.set_editor_property("parameter_name", L.GROUND_TINT_PARAM)
    one_minus = make(unreal.MaterialExpressionOneMinus)
    dull = make(unreal.MaterialExpressionDesaturation)
    multiply = make(unreal.MaterialExpressionMultiply)
    links = ((source, output, dull, ""), (saturation, "", one_minus, ""),
             (one_minus, "", dull, "Fraction"), (dull, "", multiply, "A"),
             (tint, "", multiply, "B"))
    for from_node, from_output, to_node, to_input in links:
        if not MEL.connect_material_expressions(from_node, from_output, to_node, to_input):
            raise RuntimeError(f"ground material: could not link into {to_input!r} of "
                               f"{type(to_node).__name__}")
    if not MEL.connect_material_property(multiply, "", BASE_COLOR):
        raise RuntimeError("ground material: could not link the base colour")


def _ensure_ground_material():
    material = _must_load(L.GROUND_MATERIAL)
    if len(_parameters(material)) < 2:
        _patch_ground(material)
    nodes = _parameters(material)
    nodes[L.GROUND_TINT_PARAM].set_editor_property("default_value", _color(L.GROUND_TINT))
    nodes[L.GROUND_SATURATION_PARAM].set_editor_property("default_value",
                                                         L.GROUND_SATURATION)
    MEL.recompile_material(material)
    unreal.get_editor_subsystem(unreal.EditorAssetSubsystem).save_loaded_asset(material, False)
    _log(f"   {L.GROUND_MATERIAL}: tint {L.GROUND_TINT}, saturation {L.GROUND_SATURATION}")


def ensure_grass_look():
    """Build or update both. The ground material is every level's."""
    _ensure_grass_material()
    _ensure_ground_material()


# ─── Verification ────────────────────────────────────────────────────────────

def verify_grass_look(check):
    """``check`` is the verify script's harness."""
    eas = unreal.get_editor_subsystem(unreal.EditorAssetSubsystem)
    instance = eas.load_asset(L.GRASS_MATERIAL)
    check("Dark Grass Material Exists", bool(instance), L.GRASS_MATERIAL)
    if instance:
        parent = instance.get_editor_property("parent")
        check("Dark Grass Material Is A Child Of The Pack's",
              bool(parent) and parent.get_path_name().split(".")[0] == L.GRASS_MATERIAL_PARENT,
              str(parent.get_path_name() if parent else None))
        off = [f"{name}: {got:.3f}, expected {want}" for name, want, got in (
            (n, w, MEL.get_material_instance_scalar_parameter_value(instance, n))
            for n, w in L.GRASS_SCALARS.items()) if abs(got - want) > _TOLERANCE]
        tint = MEL.get_material_instance_vector_parameter_value(instance, "Tint")
        if not _same_color(tint, L.GRASS_TINT):
            off.append(f"Tint: ({tint.r:.3f}, {tint.g:.3f}, {tint.b:.3f})")
        check("Dark Grass Material Has Its Colours", not off, str(off))
        base = instance.get_base_material()
        check("Dark Grass Material Draws On Instances",
              bool(base) and base.get_editor_property("used_with_instanced_static_meshes"))
        stray = sorted(dependencies(L.GRASS_MATERIAL) - set(L.GRASS_MATERIAL_PACKAGES))
        check("Dark Grass Material Needs Nothing The Repository Does Not Carry",
              not stray, str(stray[:3]))

    _verify_low_grass(check, eas)

    ground = eas.load_asset(L.GROUND_MATERIAL)
    check("Ground Material Exists", bool(ground), L.GROUND_MATERIAL)
    if ground:
        root = MEL.get_material_property_input_node(ground, BASE_COLOR)
        nodes = _parameters(ground)
        check("Ground Base Colour Goes Through The Tint",
              isinstance(root, unreal.MaterialExpressionMultiply) and len(nodes) == 2,
              f"({type(root).__name__}, parameters {sorted(nodes)})")
        tint = MEL.get_material_default_vector_parameter_value(ground, L.GROUND_TINT_PARAM)
        dull = MEL.get_material_default_scalar_parameter_value(ground,
                                                               L.GROUND_SATURATION_PARAM)
        check("Ground Is The Grass's Hue",
              _same_color(tint, L.GROUND_TINT)
              and abs(dull - L.GROUND_SATURATION) < _TOLERANCE,
              f"(tint ({tint.r:.3f}, {tint.g:.3f}, {tint.b:.3f}), saturation {dull:.3f})")


def _instance_off(instance, tint):
    """What of GRASS_SCALARS and ``tint`` ``instance`` does not hold."""
    off = [f"{name}: {got:.3f}, expected {want}" for name, want, got in (
        (n, w, MEL.get_material_instance_scalar_parameter_value(instance, n))
        for n, w in L.GRASS_SCALARS.items()) if abs(got - want) > _TOLERANCE]
    got = MEL.get_material_instance_vector_parameter_value(instance, "Tint")
    if not _same_color(got, tint):
        off.append(f"Tint: ({got.r:.3f}, {got.g:.3f}, {got.b:.3f})")
    return off


def _verify_low_grass(check, eas):
    """The six other types' dark instances (L.LOW_GRASS_TYPES), one check
    each for all six."""
    missing, orphans, off, flat, stray = [], [], [], [], []
    for t in L.LOW_GRASS_TYPES:
        instance = eas.load_asset(t.material)
        if not instance:
            missing.append(t.material)
            continue
        parent = instance.get_editor_property("parent")
        if not parent or parent.get_path_name().split(".")[0] != t.material_parent:
            orphans.append(t.name)
        off += [f"{t.name} {o}" for o in _instance_off(instance, t.tint)]
        base = instance.get_base_material()
        if not (base and base.get_editor_property("used_with_instanced_static_meshes")):
            flat.append(t.name)
        allowed = {t.material} | set(t.mesh.packages)
        stray += sorted(dependencies(t.material) - allowed)
    check("Low Grass Dark Materials Exist", not missing, str(missing))
    check("Low Grass Dark Materials Are Children Of The Pack's", not orphans, str(orphans))
    check("Low Grass Dark Materials Have Their Colours", not off, str(off[:3]))
    check("Low Grass Dark Materials Draw On Instances", not flat, str(flat))
    check("Low Grass Dark Materials Need Nothing The Repository Does Not Carry",
          not stray, str(stray[:3]))
