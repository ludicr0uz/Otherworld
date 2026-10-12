"""verify.glimmer -- the glimmer over an item on the ground (combat/glimmer.py):
the collection and its switch, the material, the sprite on BP_WeaponItem and
on BP_AmmoPickup, and the Tick step that shows it once the item has been
Dropped for GLIMMER_DELAY_S, on the base item and on every child whose own
Tick overrides the base's; the ammo pickup's one wait from BeginPlay.

That the switch is written from the WORLD SETTINGS row is verify_day_night's
(world/verify/blueprint.py); that it shows in a game, probes/probe_item_glimmer.py.
"""

import unreal

from combat import item_vars as IV
from combat.glimmer import EXPRESSION_COUNT
from combat.glimmer_tuning import (
    GLIMMER, GLIMMER_DELAY_S, GLIMMER_EMISSIVE, GLIMMER_FAR_CM, GLIMMER_HALF_SIZE_CM,
    GLIMMER_NEAR_CM, GLIMMER_REST, HIGHLIGHT_DEFAULT, MAT_ITEM_GLIMMER,
    MPC_ITEM_GLIMMER, MPC_NAME, PARAM_HIGHLIGHT,
)
from combat.paths import AMMO_BP_PATH, ITEM_BP_PATH, ITEM_CLASS_PATH
from combat.verify.common import (
    BEL, PIN, by_pins, check, component_template, graph, has_in_pin, load, pin_value,
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
          "(whole at a few metres, nothing past twelve)",
          GLIMMER_REST == 0.0 and GLIMMER_EMISSIVE <= 4.0
          and 200.0 <= GLIMMER_NEAR_CM < GLIMMER_FAR_CM <= 1200.0,
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


def _literal(node, pin):
    """A float pin's literal; one equal to the pin's default reads "" once
    loaded from disk."""
    try:
        return float(pin_value(node, pin) or 0.0)
    except (TypeError, ValueError):
        return None


def _counts_dropped(store):
    """Whether a Set GlimmerWait stores min(GlimmerWait + dt, the delay) while
    the item is Dropped, and SelectFloat's other side (0) while it is not."""
    for pick in _feeders(store, IV.GlimmerWait):
        if [_title(f) for f in _feeders(pick, "bPickA")] != [f"Get {IV.Dropped}"]:
            continue
        zero = _literal(pick, "B")
        for cap in _feeders(pick, "A"):
            if (zero == 0.0 and _literal(cap, "B") == GLIMMER_DELAY_S
                    and any(_title(v) == f"Get {IV.GlimmerWait}"
                            for add in _feeders(cap, "A") for v in _feeders(add, "A"))):
                return True
    return False


def _arms_behind(node, gate, limit=60):
    """The exec outputs of ``gate`` that reach ``node``, by name."""
    arms, seen, todo = set(), [], [node]
    while todo and len(seen) < limit:
        for p in BEL.list_input_pins(todo.pop()):
            if str(PIN.get_pin_name(p)) != "execute":
                continue
            for q in PIN.list_connected_pins(p):
                f = PIN.get_owning_node(q)
                if f == gate:
                    arms.add(str(PIN.get_pin_name(q)))
                elif f not in seen:
                    seen.append(f)
                    todo.append(f)
    return arms


def _reads_behind(node, pin, limit=60):
    """The variables read by the pure nodes feeding ``pin`` of ``node``."""
    names, seen, todo = set(), [], list(_feeders(node, pin))
    while todo and len(seen) < limit:
        cur = todo.pop()
        if cur in seen:
            continue
        seen.append(cur)
        if _title(cur).startswith("Get "):
            names.add(_title(cur)[4:])
        for p in BEL.list_input_pins(cur):
            if str(PIN.get_pin_name(p)) != "execute":
                todo.extend(PIN.get_owning_node(q) for q in PIN.list_connected_pins(p))
    return names


def _glimmer_steps(nodes):
    """The glimmer's SetVisibility nodes that are run straight after the count
    of the seconds the item has been Dropped, and show from GLIMMER_DELAY_S
    of them."""
    def waited(n):
        return any(_literal(ge, "B") == GLIMMER_DELAY_S
                   and [_title(v) for v in _feeders(ge, "A")] == [f"Get {IV.GlimmerWait}"]
                   for ge in _feeders(n, "bNewVisibility"))

    def counted(n):
        before = _feeders(n, "execute")
        return (len(before) == 1 and _title(before[0]) == f"Set {IV.GlimmerWait}"
                and _counts_dropped(before[0]))

    return [n for n in by_pins(nodes, "bNewVisibility") if is_glimmer_node(n)
            and waited(n) and counted(n)]


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
    # Between the Tick and the step (item_world.py): a Branch on HasAuthority,
    # whose true arm is the server's item entering the world and resting
    # (Branches of their own: verify/world_items.py, verify/relevancy.py)
    # and whose false arm is what a client's copy of a replicated item shows
    # at all. The one such Branch is fed by the Tick alone.
    # (...and the step's own first node, the count.)
    count = _feeders(steps[0], "execute") if len(steps) == 1 else []
    before = _feeders(count[0], "execute") if count else []
    gate = [n for n in nodes if _title(n) == "Branch"
            and any("HasAuthority" in _title(c).replace(" ", "")
                    for c in _feeders(n, "Condition"))]
    check(f"BP_WeaponItem's Tick shows {GLIMMER} once the item has been {IV.Dropped} "
          f"for {GLIMMER_DELAY_S:g} s ({IV.GlimmerWait} counts them, and is 0 while it "
          "is not), in one place: nothing that drops or takes an item is told",
          len(steps) == 1 and len(_wired_ticks(nodes)) == 1 and len(gate) == 1
          and [_title(f) for f in _feeders(gate[0], "execute")] == ["Event Tick"],
          f"{len(steps)} step(s), {len(_wired_ticks(nodes))} Tick(s), {len(gate)} gate(s)")
    hides = [f for f in before if "bNewHidden" in {
        str(PIN.get_pin_name(p)) for p in BEL.list_input_pins(f)}]
    # R2: hidden unless it lies in the world (InWorld and Dropped), and one
    # that has just come to rest after a throw until the stand-in that flew
    # for it gives way (Released) or ShowAt passes.
    arms = _arms_behind(hides[0], gate[0]) if len(hides) == 1 and len(gate) == 1 else set()
    reads = _reads_behind(hides[0], "bNewHidden") if len(hides) == 1 else set()
    check(f"...after a client's copy of a replicated item is hidden while it does not "
          f"lie in the world ({IV.InWorld} and {IV.Dropped}), or has only just come to "
          f"rest after a throw ({IV.Released}, {IV.ShowAt}): off the false arm of a "
          "Branch on HasAuthority, in one place",
          len(hides) == 1 and len(gate) == 1 and arms == {"else"}
          and {str(IV.InWorld), str(IV.Dropped), str(IV.Released), str(IV.ShowAt)} <= reads,
          f"{len(hides)} hide(s), arm(s) {sorted(arms)}, reads {sorted(reads)}")

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
    ammo = load(AMMO_BP_PATH)
    _check_sprite("BP_AmmoPickup", ammo, visible=False)
    nodes = graph(ammo).list_all_nodes()
    shows = [n for n in by_pins(nodes, "bNewVisibility") if is_glimmer_node(n)]
    waits = [w for n in shows for w in _feeders(n, "execute")]
    check(f"...and shown {GLIMMER_DELAY_S:g} s after BeginPlay: a Delay, then the one "
          "SetVisibility(true)",
          len(shows) == 1 and len(waits) == 1 and has_in_pin(waits[0], "Duration")
          and _literal(waits[0], "Duration") == GLIMMER_DELAY_S
          and str(pin_value(shows[0], "bNewVisibility")).lower() == "true"
          and any(_title(b) == "Event BeginPlay" for life in _feeders(waits[0], "execute")
                  for b in _feeders(life, "execute")),
          f"{len(shows)} show(s), {len(waits)} wait(s)")


def run():
    check_collection_and_material()
    check_item_glimmer()
    check_ammo_glimmer()
