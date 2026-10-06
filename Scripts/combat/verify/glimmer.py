"""verify.glimmer -- the glimmer over an item on the ground (combat/glimmer.py):
the collection and its switch, the material, the sprite on BP_WeaponItem and
on BP_AmmoPickup, and the Tick step that shows it while the item is Dropped,
on the base item and on every child whose own Tick overrides the base's.

That the switch is written from the WORLD SETTINGS row is verify_day_night's
(world/verify/blueprint.py); that it shows in a game, probes/probe_item_glimmer.py.
"""

import unreal

from combat import item_vars as IV
from combat.glimmer import EXPRESSION_COUNT
from combat.glimmer_tuning import (
    GLIMMER, GLIMMER_EMISSIVE, GLIMMER_FAR_CM, GLIMMER_HALF_SIZE_CM, GLIMMER_NEAR_CM,
    GLIMMER_REST, HIGHLIGHT_DEFAULT, MAT_ITEM_GLIMMER,
    MPC_ITEM_GLIMMER, MPC_NAME, PARAM_HIGHLIGHT,
)
from combat.paths import AMMO_BP_PATH, ITEM_BP_PATH, ITEM_CLASS_PATH
from combat.verify.common import (
    BEL, PIN, by_pins, check, component_template, graph, has_in_pin, load,
)

MEL = unreal.MaterialEditingLibrary
# Where the item Blueprints are built.
ITEM_DIRS = ("/Game/Weapons", "/Game/Survival", "/Game/Clothing")


def _title(n):
    return str(BEL.get_node_title(n)).replace("\n", " ")


def _feeders(node, pin):
    p = BEL.find_input_pin(node, pin)
    return [PIN.get_owning_node(q) for q in PIN.list_connected_pins(p)] if p else []


def is_glimmer_node(node):
    """The Tick step's one node: SetVisibility on the Glimmer sprite. The
    older counts of an item graph's SetVisibility nodes set it aside."""
    return (has_in_pin(node, "bNewVisibility")
            and [_title(f) for f in _feeders(node, "self")] == [f"Get {GLIMMER}"])


def check_collection_and_material():
    mpc = load(MPC_ITEM_GLIMMER)
    params = {str(p.get_editor_property("parameter_name")):
              p.get_editor_property("default_value")
              for p in (mpc.get_editor_property("scalar_parameters") if mpc else [])}
    check(f"{MPC_NAME} holds one scalar, {PARAM_HIGHLIGHT}, on as built",
          params == {PARAM_HIGHLIGHT: HIGHLIGHT_DEFAULT} and HIGHLIGHT_DEFAULT == 1.0,
          str(params))
    check("the glimmer is slight: gone between flashes, and only near the camera "
          "(whole at a few metres, nothing past ten)",
          GLIMMER_REST == 0.0 and GLIMMER_EMISSIVE <= 4.0
          and 200.0 <= GLIMMER_NEAR_CM < GLIMMER_FAR_CM <= 1000.0,
          f"rest {GLIMMER_REST}, emissive {GLIMMER_EMISSIVE}, "
          f"{GLIMMER_NEAR_CM:g}..{GLIMMER_FAR_CM:g} cm")
    mat = load(MAT_ITEM_GLIMMER)
    check("M_ItemGlimmer is unlit and additive: light added over the scene, "
          "nothing where it is dark",
          mat is not None
          and mat.get_editor_property("blend_mode") == unreal.BlendMode.BLEND_ADDITIVE
          and mat.get_editor_property("shading_model") == unreal.MaterialShadingModel.MSM_UNLIT,
          str(mat))
    if not mat:
        return
    n = MEL.get_num_material_expressions(mat)
    check(f"...authored once ({EXPRESSION_COUNT} expressions: a rerun must not stack them)",
          n == EXPRESSION_COUNT, str(n))
    stats = MEL.get_statistics(mat)
    ps = stats.get_editor_property("num_pixel_shader_instructions")
    check("...and its Custom node compiled (a failed one draws the default material)",
          ps > 0, f"{ps} pixel shader instructions")


def _check_sprite(name, bp, visible):
    sprite = component_template(bp, GLIMMER)
    ok = isinstance(sprite, unreal.MaterialBillboardComponent)
    elements = list(sprite.get_editor_property("elements")) if ok else []
    mats = [e.get_editor_property("material") for e in elements]
    check(f"{name} carries the {GLIMMER} sprite, drawn with M_ItemGlimmer, "
          f"{2 * GLIMMER_HALF_SIZE_CM:g} cm across",
          ok and len(elements) == 1 and mats[0] is not None
          and mats[0].get_path_name().split(".")[0] == MAT_ITEM_GLIMMER
          and abs(elements[0].get_editor_property("base_size_x") - GLIMMER_HALF_SIZE_CM) < 1e-3
          and abs(elements[0].get_editor_property("base_size_y") - GLIMMER_HALF_SIZE_CM) < 1e-3,
          f"{type(sprite).__name__}, {len(elements)} element(s)")
    if not ok:
        return
    shown = bool(sprite.get_editor_property("visible"))
    check(f"...{'showing' if visible else 'hidden'} as built, casting no shadow and "
          "blocking nothing",
          shown is visible and not sprite.get_editor_property("cast_shadow")
          and str(sprite.get_collision_profile_name()) == "NoCollision",
          f"visible {shown}, {sprite.get_collision_profile_name()}")


def _glimmer_steps(nodes):
    """The glimmer's SetVisibility nodes that read Dropped and are run."""
    return [n for n in by_pins(nodes, "bNewVisibility") if is_glimmer_node(n)
            and [_title(f) for f in _feeders(n, "bNewVisibility")] == [f"Get {IV.Dropped}"]
            and len(_feeders(n, "execute")) > 0]


def _then_of(node):
    """The nodes a Tick event's exec pin runs."""
    return [PIN.get_owning_node(q) for p in BEL.list_output_pins(node)
            if str(PIN.get_pin_name(p)) == "then" for q in PIN.list_connected_pins(p)]


def _wired_ticks(nodes):
    """The Tick events that run something."""
    return [n for n in nodes if _title(n) == "Event Tick" and len(_then_of(n)) > 0]


def _own_ticks(nodes):
    """...of the class's own: a chain that replaces its parent's. A child
    Blueprint's placeholder Tick runs "Parent: Tick" and nothing else."""
    return [n for n in _wired_ticks(nodes)
            if not any(_title(m) == "Parent: Tick" for m in _then_of(n))]


def _item_children():
    """Every Blueprint under ITEM_DIRS whose class is a BP_WeaponItem's child."""
    base = unreal.load_class(None, ITEM_CLASS_PATH)
    registry = unreal.AssetRegistryHelpers.get_asset_registry()
    found = []
    for folder in ITEM_DIRS:
        for data in registry.get_assets_by_path(folder, recursive=True):
            if str(data.asset_class_path.asset_name) != "Blueprint":
                continue
            bp = load(str(data.package_name))
            cls = BEL.generated_class(bp) if bp else None
            if cls and cls != base and unreal.MathLibrary.class_is_child_of(cls, base):
                found.append(bp)
    return found


def check_item_glimmer():
    item = load(ITEM_BP_PATH)
    _check_sprite("BP_WeaponItem", item, visible=False)
    nodes = graph(item).list_all_nodes()
    steps = _glimmer_steps(nodes)
    # Between the Tick and the step: what a client's copy of a replicated item
    # shows at all (item_world.py), a Branch on HasAuthority and its false arm.
    before = _feeders(steps[0], "execute") if len(steps) == 1 else []
    gate = [f for f in before if _title(f) == "Branch"]
    check(f"BP_WeaponItem's Tick shows {GLIMMER} while the item is {IV.Dropped}, in one "
          "place: nothing that drops or takes an item is told",
          len(steps) == 1 and len(_wired_ticks(nodes)) == 1 and len(gate) == 1
          and [_title(f) for f in _feeders(gate[0], "execute")] == ["Event Tick"],
          f"{len(steps)} step(s), {len(_wired_ticks(nodes))} Tick(s)")
    hides = [f for f in before if "bNewHidden" in {
        str(PIN.get_pin_name(p)) for p in BEL.list_input_pins(f)}]
    check(f"...after a client's copy of a replicated item is hidden while it is not "
          f"{IV.InWorld}: off the false arm of a Branch on HasAuthority",
          len(hides) == 1 and len(gate) == 1
          and any("HasAuthority" in _title(c).replace(" ", "")
                  for c in _feeders(gate[0], "Condition"))
          and [str(PIN.get_pin_name(q)) for q in PIN.list_connected_pins(
              BEL.find_input_pin(hides[0], "execute"))] == ["else"]
          and any(_title(v) == f"Get {IV.InWorld}" for n in _feeders(hides[0], "bNewHidden")
                  for v in _feeders(n, "A")),
          f"{len(hides)} hide(s)")

    children = _item_children()
    own, forgot = [], []
    for bp in children:
        nodes = graph(bp).list_all_nodes()
        if _own_ticks(nodes):
            own.append(bp.get_name())
            if len(_glimmer_steps(nodes)) != 1:
                forgot.append(bp.get_name())
    check("every item with a Tick of its own (which overrides the base's) shows "
          "its glimmer there too",
          len(children) >= 9 and len(own) >= 3 and not forgot,
          f"{len(children)} items, own Tick: {sorted(own)}, without the step: {forgot}")


def check_ammo_glimmer():
    _check_sprite("BP_AmmoPickup", load(AMMO_BP_PATH), visible=True)


def run():
    check_collection_and_material()
    check_item_glimmer()
    check_ammo_glimmer()
