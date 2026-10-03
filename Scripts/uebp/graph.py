"""Blueprint-authoring helpers shared by every builder: node/pin/connect/set,
variable declaration, component (subobject) helpers, events and the tick
group. No game logic lives here.
"""

import unreal

from uebp.nodes.math import FN_MAKE_VECTOR
from uebp.nodes.palette import NODE_BEGIN_PLAY, NODE_TICK
from uebp.nodes.system import FN_LITERAL_NAME


BGE = unreal.BlueprintGraphEditor
BEL = unreal.BlueprintEditorLibrary
PIN = unreal.BlueprintGraphPinLibrary
SDL = unreal.SubobjectDataBlueprintFunctionLibrary


def make_log(prefix):
    """A package's ``_log``: each builder logs under its own prefix."""
    def _log(msg):
        unreal.log_warning(f"[{prefix}] {msg}")
    return _log


def _assets():
    return unreal.get_editor_subsystem(unreal.EditorAssetSubsystem)


def _subobjects():
    return unreal.get_engine_subsystem(unreal.SubobjectDataSubsystem)


# ─── Graph helpers ───────────────────────────────────────────────────────────

def _node(ed, function_path):
    """add_call_function_node, but loud when the path does not resolve.

    An unresolvable path yields a *pinless* node rather than None, and the
    failure then surfaces much later as "pin 'self' not found on ''".
    """
    n = ed.add_call_function_node(function_path)
    if not n or not BEL.list_all_pins(n):
        raise RuntimeError(f"{function_path} is not a Blueprint-callable function")
    return n


def _palette(ed, name):
    n = ed.create_node_from_name(name, unreal.Vector2D(0.0, 0.0), [])
    if not n:
        raise RuntimeError(f"palette node {name!r} could not be created")
    return n


def _pin(node, name, is_input=True):
    p = (BEL.find_input_pin(node, name) if is_input
         else BEL.find_output_pin(node, name))
    if not p or not p.is_valid():
        raise RuntimeError(f"pin {name!r} ({'in' if is_input else 'out'}) not found; "
                           f"node has {_pin_names(node)}")
    return p


def _pin_names(node):
    return ([str(PIN.get_pin_name(p)) for p in BEL.list_input_pins(node)],
            [str(PIN.get_pin_name(p)) for p in BEL.list_output_pins(node)])


def _loose_pin(node, wanted, is_input=True):
    """Find a pin ignoring spaces and case.

    Macro nodes name their pins "First Index" / "Loop Body", and whether the
    space is there is not something to rely on.
    """
    key = wanted.replace(" ", "").lower()
    for p in (BEL.list_input_pins(node) if is_input else BEL.list_output_pins(node)):
        if str(PIN.get_pin_name(p)).replace(" ", "").lower() == key:
            return p
    raise RuntimeError(f"no pin like {wanted!r} on node; has {_pin_names(node)}")


def _connect(a, b):
    if not a.try_create_connection(b):
        raise RuntimeError("could not connect pins")


def _set(node, name, value):
    """Set a pin's literal, and prove it landed.

    set_pin_value's return is not a usable signal: it is False when the set
    genuinely failed *and* when the value already equalled the pin's default.
    Reading the pin back is. A pin that silently stayed empty compiles as zero,
    which is how a 1 km aiming ray quietly became a 0 cm one -- and the shape of
    the graph looked perfect the whole time.
    """
    pin = _pin(node, name)
    pin.set_pin_value(str(value))
    got = str(PIN.get_pin_value(pin))
    if not _literal_matches(got, value):
        raise RuntimeError(f"pin {name!r} would not take {value!r} — it reads "
                           f"back as {got!r} (struct pins reject every format; "
                           "build the constant as a node instead)")


def _literal_matches(got, want):
    want = str(want)
    if got == want:
        return True
    try:
        # An empty numeric pin *is* zero -- the compiler reads a blank literal
        # as 0 -- so setting a pin to zero and reading back "" is a real match,
        # not the silent failure this guard is looking for.
        return abs(float(got or 0.0) - float(want)) < 1e-6
    except ValueError:
        pass
    # Enum literals read back namespaced (EDrawDebugTrace::ForDuration), and
    # bools read back lower-cased.
    return got.lower() == want.lower() or got.endswith(f"::{want}")


def out(node, name="ReturnValue"):
    return _pin(node, name, is_input=False)


def then(node):
    return BEL.find_then_pin(node)


def else_(node):
    return BEL.find_else_pin(node)


def _create_blueprint(path, parent_class):
    eas = _assets()
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
        raise RuntimeError(f"could not create Blueprint {path}")
    return bp


def _float_type():
    """The pin type for a Blueprint float.

    NOT get_basic_type_by_name("float") -- that name is not recognised and the
    library silently falls back to **int**, logging only
    `Primitive type: float not recognized, defaulting to int`. "double" does the
    same. UE 5 calls the Blueprint float type "real", and it is the only spelling
    that produces a float property. Integral defaults like 100.0 or 4000.0 hide
    the bug completely, so it surfaces only once something needs a fraction.
    """
    return BEL.get_basic_type_by_name("real")


def _declare(ed, name, pin_type):
    """Re-declare a member variable so a type change in this file actually lands."""
    ed.remove_member_variable(name)
    if not ed.add_member_variable(name, pin_type):
        raise RuntimeError(f"could not declare {name}")


def _must_load(path):
    """load_asset, but a miss is an error rather than a None.

    _same() compares a read-back default against what was written, and None
    against None is equal -- so a weapon whose FireSound path was misspelt
    would build, apply, verify and ship in silence, and the only symptom would
    be a gun that makes no noise. Every asset reference written as a default
    goes through here.
    """
    asset = _assets().load_asset(path)
    if not asset:
        raise RuntimeError(f"could not load {path}")
    return asset


def _same(a, b):
    """Compare a read-back default with what was written.

    str() on a UE struct embeds its address, so two identical Vectors never
    compare equal that way -- to_tuple() is the field-wise view. Objects compare
    by path, since the read-back is a different wrapper around the same asset.
    An array comes back as unreal.Array, which is not a list and whose repr is
    an address too, so it is compared element-wise by this same function.
    """
    if isinstance(b, (list, tuple)):
        return len(a) == len(b) and all(_same(x, y) for x, y in zip(a, b))
    if isinstance(b, bool):
        return bool(a) == b
    if isinstance(b, float):
        return abs(float(a) - b) < 1e-6
    if isinstance(b, int):
        return int(a) == b
    if hasattr(b, "get_path_name"):
        return a is not None and a.get_path_name() == b.get_path_name()
    if isinstance(b, unreal.Key):
        # BEFORE the to_tuple arm, and that order is the whole point: FKey
        # exposes no struct fields to Python, so to_tuple() is () for every key
        # and comparing two of them that way passes unconditionally. Python's ==
        # on the wrapper is identity, which fails unconditionally. export_text()
        # is the only view that answers the question -- and it is the same bare
        # key name a pin literal uses.
        return a is not None and a.export_text() == b.export_text()
    if hasattr(b, "to_tuple"):
        return (a is not None and hasattr(a, "to_tuple")
                and all(abs(x - y) < 1e-4 for x, y in zip(a.to_tuple(), b.to_tuple())))
    return str(a) == str(b)


def _apply_defaults(bp, defaults):
    """Write variable defaults onto the CDO, because add_member_variable cannot.

    ``add_member_variable(name, type, "100.0")`` returns True, and then the
    compiler logs `Can't parse default value '100.0'` and leaves the property at
    zero -- a default that reads as set everywhere except where it matters. UE
    5.8 exposes no Python API for a *member* variable's default (only
    set_local_variable_default_value, for locals), so the value is written to
    the compiled class's default object and baked in by recompiling.

    The read-back is the point: a weapon that silently does 0 damage, or a
    health component that starts dead, looks exactly like a working one until
    something shoots at it.
    """
    cdo = unreal.get_default_object(BEL.generated_class(bp))
    for name, value in defaults.items():
        cdo.set_editor_property(name, value)
    if not BEL.compile_blueprint(bp):
        raise RuntimeError(f"{bp.get_name()} failed to recompile after defaults")
    _assets().save_loaded_asset(bp)
    fresh = unreal.get_default_object(BEL.generated_class(bp))
    for name, value in defaults.items():
        got = fresh.get_editor_property(name)
        if not _same(got, value):
            raise RuntimeError(f"default for {name} did not stick: {got!r} != {value!r}")


# ─── Component helpers ───────────────────────────────────────────────────────

def _handles(bp):
    out = []
    for h in _subobjects().k2_gather_subobject_data_for_blueprint(bp):
        data = _subobjects().k2_find_subobject_data_from_handle(h)
        if not data:
            continue
        out.append((h, str(SDL.get_variable_name(data))))
    return out


def _find_handle(bp, name):
    for h, var in _handles(bp):
        if var == name:
            return h
    return None


def _root_handle(bp):
    handles = _subobjects().k2_gather_subobject_data_for_blueprint(bp)
    if not handles:
        raise RuntimeError("blueprint has no subobject root")
    return handles[0]


def _drop_components(bp, names):
    """Delete each named component *and everything hanging off it*.

    Deleting the root alone is not enough. delete_subobject does not cascade,
    and the orphans it leaves behind come back on the next run under generated
    names (StaticMesh7, StaticMesh13, ...) which then hold the names the real
    parts want -- so rename_subobject quietly fails and the actor accumulates a
    second, nameless copy of the weapon on every run.
    """
    sds = _subobjects()
    targets = set(names)
    # One delete per gather: every handle in a batch goes stale as soon as the
    # first of them is removed, and reusing one trips an ensure inside
    # USimpleConstructionScript::RemoveNodeAndPromoteChildren.
    for _ in range(200):
        entries = []
        for h in sds.k2_gather_subobject_data_for_blueprint(bp):
            data = sds.k2_find_subobject_data_from_handle(h)
            if not data:
                continue
            parent = SDL.get_parent_handle(data)
            parent_data = (sds.k2_find_subobject_data_from_handle(parent)
                           if parent else None)
            entries.append((str(SDL.get_variable_name(data)),
                            str(SDL.get_variable_name(parent_data))
                            if parent_data else "",
                            h))
        grew = True
        while grew:
            grew = False
            for var, parent, _h in entries:
                if parent in targets and var not in targets:
                    targets.add(var)
                    grew = True
        doomed = [(var, h) for var, parent, h in entries if var in targets]
        if not doomed:
            return
        claimed = {parent for _v, parent, _h in entries}
        leaves = [h for var, h in doomed if var not in claimed]
        sds.delete_subobject(_root_handle(bp), (leaves or [doomed[0][1]])[0], bp)
    raise RuntimeError(f"could not clear components {sorted(targets)}")


def _add_component(bp, parent_handle, cls, name):
    params = unreal.AddNewSubobjectParams()
    params.set_editor_property("parent_handle", parent_handle)
    params.set_editor_property("new_class", cls)
    params.set_editor_property("blueprint_context", bp)
    handle, failure = _subobjects().add_new_subobject(params)
    if failure and str(failure):
        raise RuntimeError(f"could not add {name}: {failure}")
    _subobjects().rename_subobject(handle, name)
    # Renaming onto a name something else already holds fails silently and
    # leaves the generated one, which is how duplicates went unnoticed before.
    got = str(SDL.get_variable_name(
        _subobjects().k2_find_subobject_data_from_handle(handle)))
    if got != name:
        raise RuntimeError(
            f"component came out named {got!r}, not {name!r} -- something stale "
            "is still holding that name")
    return handle


def _component_object(handle):
    return SDL.get_object(_subobjects().k2_find_subobject_data_from_handle(handle))


def _rot(pitch=0.0, yaw=0.0, roll=0.0):
    r = unreal.Rotator()
    r.pitch, r.yaw, r.roll = pitch, yaw, roll
    return r


# ─── BP_WeaponItem and its two children ──────────────────────────────────────

def _struct_type(struct):
    return BEL.get_struct_type(struct)


def _key(name):
    """An FKey value for a CDO default.

    unreal.Key takes no constructor argument and exposes no fields, so the only
    two ways in are set_editor_property("key_name", ...) and import_text(). The
    property form is used here because it fails loudly on a misspelling, where
    import_text returns True for anything.
    """
    k = unreal.Key()
    k.set_editor_property("key_name", name)
    return k


def _vec(ed, x, y, z):
    """A constant vector, as a MakeVector node rather than as a pin default.

    A struct pin refuses set_pin_value outright -- every format returns False
    and the pin keeps an empty default, which the compiler then reads as the
    zero vector. A zero scale on a spawn transform makes the actor invisible,
    so these have to be real nodes.
    """
    n = _node(ed, FN_MAKE_VECTOR)
    for axis, value in (("X", x), ("Y", y), ("Z", z)):
        _set(n, axis, float(value))
    return _pin(n, "ReturnValue", is_input=False)


def _events(ed, rebuild):
    """Return (tick, begin_play), wiping the graph first when rebuilding.

    A builder whose "already authored, reusing" guard has no escape hatch means
    no edit to the builder ever reaches the asset, so rebuild is the default
    everywhere in this file.
    """
    if rebuild:
        nodes = ed.list_all_nodes()
        if nodes:
            ed.remove_nodes(nodes)
    tick = ed.find_event_node("ReceiveTick")
    if not tick:
        tick = _palette(ed, NODE_TICK)
    begin = ed.find_event_node("ReceiveBeginPlay")
    if not begin:
        begin = _palette(ed, NODE_BEGIN_PLAY)
    return tick, begin


def _post_physics_tick(bp):
    """Tick after the player controller has processed input this frame.

    WasInputKeyJustPressed reads EventCounts, which UPlayerInput::
    ProcessInputStack swaps out once per frame during the controller's
    TG_PrePhysics tick. A component defaults to TG_PrePhysics too, with no
    defined order against the controller, so a trigger polled there fires or
    does not fire depending on registration order.

    Nothing here enables ticking, and nothing needs to: bCanEverTick is not a
    UPROPERTY, but FKismetCompilerContext::SetCanEverTick turns it on at compile
    time for any Blueprint whose first native parent is UActorComponent and
    whose Tick event has its exec pin connected. Leave Tick wired.
    """
    cdo = unreal.get_default_object(BEL.generated_class(bp))
    tick_fn = cdo.get_editor_property("primary_component_tick")
    tick_fn.set_editor_property("tick_group", unreal.TickingGroup.TG_POST_PHYSICS)
    cdo.set_editor_property("primary_component_tick", tick_fn)


# ─── Variants the NPC builders use ───────────────────────────────────────────

def _try_set(obj, prop, value):
    """Set a property, logging instead of raising if the name moved."""
    try:
        obj.set_editor_property(prop, value)
    except Exception as exc:
        unreal.log_warning(f"[NPC] could not set {prop}: {exc}")


def _name_literal(ed, value):
    """A MakeLiteralName node holding ``value``; returns its output pin. See
    FN_LITERAL_NAME for which pins need it."""
    n = _node(ed, FN_LITERAL_NAME)
    _set(n, "Value", value)
    return _pin(n, "ReturnValue", is_input=False)


def _resolve(preferred, fallback, what):
    """First of the two that exists on disk, as an OBJECT path."""
    eas = _assets()
    for pkg in (preferred, fallback):
        if eas.does_asset_exist(pkg):
            if pkg is fallback:
                unreal.log_warning(
                    f"[NPC] {what}: {preferred} is missing -- falling back to "
                    f"{pkg}. Run Scripts/asset_pipeline to build the creatures.")
            return f"{pkg}.{pkg.rsplit('/', 1)[-1]}"
    raise RuntimeError(f"[NPC] neither {preferred} nor {fallback} exists ({what})")
