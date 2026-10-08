"""Traversal from the Game Animation Sample (task G5): the jump key in front
of a traversable block mantles, vaults or hurdles it. The sample's own
component does the work (AC_TraversalLogic: the sweep, the ledges read off the
block, the montage its chooser picks, the warp targets, the movement mode
while it plays); this file makes it run on the game's character.

    patch_traversal_logic()   the sample's component, patched where it lies
                              (a row of gas_paths.PATCHED, as the anim
                              Blueprint is):
        WHAT IT READS   it asks its owner for S_CharacterPropertiesForTraversal
                        through an interface the sample's character
                        implements (twice: BeginPlay, and each try). Patched,
                        it fills the struct from any Character: the capsule,
                        the mesh, the MotionWarping component, and the gait,
                        the movement mode and the speed off the movement
                        component, as gas_locomotion.py reads them.
        THE GUARD       its one Server event asks the RPC guard first
                        (net/guard.py; no row in the table, so the default
                        rate), then refuses a ledge further from the server's
                        copy of the character than a traversal reaches.
    install_traversal(bp)     the component and a MotionWarping component on
                              the player; the component replicates (its
                              events are a Server and a Multicast)
    unauthor_jump(bp)         the stock jump key back, before the install
                              drops the component its nodes read
    author_jump(bp)           the character's jump key calls JumpPressed, a
                              custom event (a probe calls it too): on the
                              ground and standing it tries a traversal
                              first, and jumps when there is nothing to climb

All three are behind gas_moves.traversal_on(); off, the components are gone
and the jump key is the stock one again. The patch to the sample's component
stays either way: it is how the component runs on any Character.

What it climbs is the sample's LevelBlock_Traversable and nothing else (the
check casts what it hits to that class and reads its ledge splines), so in
the forest it does nothing until such blocks are placed.
"""

import unreal

from combat import gas_moves_tuning as T
from combat.gas_locomotion import _as_enum, _field, _pick, enum_values
from combat.gas_locomotion_consts import ABP_LOCOMOTION, WALK_BELOW_CMS
from combat.gas_moves import traversal_on
from combat.log import _log
from net.guard import author_guard
from uebp import net
from uebp import props as EP
from uebp.g import _G
from uebp.graph import (
    BEL, BGE, PIN, _add_component, _assets, _component_object, _connect, _loose_pin,
    _palette, _pin, _root_handle, out, then,
)
from uebp.layout import arrange
from uebp.nodes.actor import (
    FN_ACTOR_FORWARD, FN_ACTOR_LOC, FN_GET_COMP, FN_GET_OWNER, FN_ON_GROUND, FN_VELOCITY,
)
from uebp.nodes.locomotion import (
    FN_IS_FALLING, FN_MAX_SPEED, NODE_BREAK_TRAVERSAL_RESULT, NODE_BYTE_TO_GAIT,
    NODE_BYTE_TO_MOVEMENT_MODE, NODE_MAKE_TRAVERSAL_INPUTS, NODE_MAKE_TRAVERSAL_PROPERTIES,
)
from uebp.nodes.math import (
    FN_AND, FN_LESS_FF, FN_MAP_CLAMPED, FN_NOT, FN_OR, FN_SUB_VV, FN_VSIZE,
    FN_VSIZE_XY,
)
from uebp.nodes.move import FN_IS_SPRINTING
from uebp.nodes.palette import NODE_CAST_CHARACTER

CHARACTER = "/Script/Engine.Character"
TRAVERSAL_CLASS = f"{T.TRAVERSAL_BP}.{T.TRAVERSAL_BP.rsplit('/', 1)[1]}_C"
# The server takes a client's ledge only this near its own copy of the
# character: the far end of the sweep, and the slack of a move in flight.
LEDGE_REACH_CM = T.TRACE_FAR_CM + 150.0
GUARD_TITLE = "Allow"


def _class(node):
    return node.get_class().get_name()


def _title(node):
    return str(BEL.get_node_title(node)).replace("\n", " ")


def _fed(pin):
    return list(PIN.list_connected_pins(pin))


def _exec_in(node):
    return next(p for p in BEL.list_input_pins(node) if _is_exec(p))


def _is_exec(pin):
    return str(PIN.get_pin_type_display_string(pin)).lower() == "exec"


def _data_feeders(nodes, keep=()):
    """Every node upstream of ``nodes`` through their data inputs, each once.
    Never through an exec pin: what runs a node is not what feeds it, and
    upstream of an exec pin are the graph's events (a walk through them took
    the component's BeginPlay out with an earlier run's nodes)."""
    found, stack, kept = {}, list(nodes), {n.get_name() for n in keep}
    while stack:
        for p in BEL.list_input_pins(stack.pop()):
            if _is_exec(p):
                continue
            for q in _fed(p):
                up = PIN.get_owning_node(q)
                if up.get_name() not in found and up.get_name() not in kept:
                    found[up.get_name()] = up
                    stack.append(up)
    return list(found.values())


def _by_title(ed, title, cls=None):
    return [n for n in ed.list_all_nodes()
            if _title(n) == title and (cls is None or _class(n) == cls)]


# ─── What the component reads of its character ───────────────────────────────

def properties_sources(ed):
    """[(the Set CharacterProperties node, what feeds its value)] of a graph."""
    found = []
    for put in _by_title(ed, f"Set {T.PROPERTIES_VAR}"):
        fed = _fed(_pin(put, T.PROPERTIES_VAR))
        found.append((put, PIN.get_owning_node(fed[0]) if fed else None))
    return found


def _author_properties(ed, values):
    """Each Set CharacterProperties of the graph is fed from the owner as a
    Character, in place of the sample's interface message (or of an earlier
    run's nodes)."""
    for put, source in properties_sources(ed):
        if source is None:
            raise RuntimeError(f"a Set {T.PROPERTIES_VAR} is fed by nothing")
        if _class(source) == "K2Node_Message":
            before = _fed(_exec_in(source))
            ed.remove_nodes([source])
        else:
            # An earlier run's: the cast in the exec line, and what it feeds.
            cast = PIN.get_owning_node(_fed(_exec_in(put))[0])
            before = _fed(_exec_in(cast))
            ed.remove_nodes(_data_feeders([put]))
        g = _G(ed)
        cast = g.keep(_palette(ed, NODE_CAST_CHARACTER))
        _connect(out(g.call(FN_GET_OWNER)), _pin(cast, "Object"))
        for pin in before:
            _connect(pin, _exec_in(cast))
        _connect(then(cast), _exec_in(put))
        char = _loose_pin(cast, "AsCharacter", is_input=False)
        move = g.iget(char, EP.CHARACTER_MOVEMENT, CHARACTER)
        warp = g.call(FN_GET_COMP, self=char)
        _pin(warp, "ComponentClass").set_pin_value(T.WARP_CLASS)
        walking = g.call(FN_LESS_FF, A=out(g.call(FN_MAX_SPEED, self=move)),
                         B=str(WALK_BELOW_CMS))
        gait = _pick(g, out(g.call(FN_IS_SPRINTING, Character=char)),
                     values["Gait"]["SPRINT"],
                     _pick(g, out(walking), values["Gait"]["WALK"], values["Gait"]["RUN"]))
        mode = _pick(g, out(g.call(FN_IS_FALLING, self=move)),
                     values["MovementMode"]["IN_AIR"], values["MovementMode"]["ON_GROUND"])
        make = g.keep(_palette(ed, NODE_MAKE_TRAVERSAL_PROPERTIES))
        fields = {
            "Capsule": g.iget(char, EP.CAPSULE_COMPONENT, CHARACTER),
            "Mesh": g.iget(char, EP.MESH, CHARACTER),
            "MotionWarping": out(warp),
            "MovementMode": _as_enum(g, NODE_BYTE_TO_MOVEMENT_MODE, mode),
            "Gait": _as_enum(g, NODE_BYTE_TO_GAIT, gait),
            "Speed": out(g.call(FN_VSIZE_XY, A=out(g.call(FN_VELOCITY, self=char)))),
        }
        if set(fields) != set(T.TRAVERSAL_FIELDS):
            raise RuntimeError("TRAVERSAL_FIELDS and the fields authored here disagree")
        for name, pin in fields.items():
            _connect(pin, _field(make, name))
        _connect(next(iter(BEL.list_output_pins(make))), _pin(put, T.PROPERTIES_VAR))
        ed.add_comment_to_nodes(
            "What a traversal reads of its character, off any Character (the sample "
            "asked its own through an interface): the capsule, the mesh, the "
            "MotionWarping component, and the gait, the movement mode and the speed "
            "off the movement component. Scripts/combat/gas_traversal.py.", g.made)


# ─── The guard at the head of its Server event ───────────────────────────────

def server_event(ed):
    events = _by_title(ed, T.SERVER_EVENT, "K2Node_CustomEvent")
    if len(events) != 1:
        raise RuntimeError(f"expected one {T.SERVER_EVENT} event, found {len(events)}")
    return events[0]


def _remove_guard(ed, event):
    """Take an earlier run's guard out, and join the event to its body again."""
    first = [PIN.get_owning_node(q) for q in _fed(then(event))]
    if not first or _title(first[0]) != GUARD_TITLE:
        return
    # Allow -> Branch -> Branch (the ledge's reach) -> the body.
    line, node = [], first[0]
    while _title(node) in (GUARD_TITLE, "Branch"):
        line.append(node)
        node = PIN.get_owning_node(_fed(then(node))[0])
    body = _fed(then(line[-1]))
    ed.remove_nodes(line + _data_feeders(line, keep=[event]))
    for pin in body:
        _connect(then(event), pin)


def _author_guard(ed):
    event = server_event(ed)
    _remove_guard(ed, event)
    body = _fed(then(event))
    PIN.break_pin_links(then(event))
    g = _G(ed)
    allowed, _refused = author_guard(g, T.SERVER_EVENT, [then(event)])
    # The ledge the client names, against where the server has the character.
    result = next(p for p in BEL.list_output_pins(event)
                  if "TraversalResult" in str(PIN.get_pin_name(p)))
    parts = g.keep(_palette(ed, NODE_BREAK_TRAVERSAL_RESULT))
    _connect(result, next(iter(BEL.list_input_pins(parts))))
    ledge = next(p for p in BEL.list_output_pins(parts)
                 if str(PIN.get_pin_name(p)).split("_")[0] == "FrontLedgeLocation")
    here = g.call(FN_ACTOR_LOC, self=out(g.call(FN_GET_OWNER)))
    off = g.call(FN_VSIZE, A=out(g.call(FN_SUB_VV, A=ledge, B=out(here))))
    near, _far = g.branch(out(g.call(FN_LESS_FF, A=out(off), B=str(LEDGE_REACH_CM))),
                          [allowed])
    for pin in body:
        _connect(near, pin)
    ed.add_comment_to_nodes(
        "The RPC guard first (net/guard.py: how often a connection may ask), then the "
        f"ledge the client names must be within {LEDGE_REACH_CM:g} cm of the server's "
        "copy of the character. Scripts/combat/gas_traversal.py.", g.made)


def patch_traversal_logic():
    """Patch the sample's AC_TraversalLogic. Idempotent: each part replaces
    an earlier run's."""
    eas = _assets()
    if not eas.does_asset_exist(T.TRAVERSAL_BP):
        raise RuntimeError(f"{T.TRAVERSAL_BP} is not here: run asset_pipeline/import_gas.py")
    bp = eas.load_asset(T.TRAVERSAL_BP)
    values = enum_values(eas.load_asset(ABP_LOCOMOTION))
    events = BGE.get_graph_editor_by_name(bp, "EventGraph")
    tries = BGE.get_graph_editor_by_name(bp, T.TRY_GRAPH)
    if not (events and tries):
        raise RuntimeError(f"{T.TRAVERSAL_BP} lacks EventGraph or {T.TRY_GRAPH}")
    for ed in (events, tries):
        _author_properties(ed, values)
    _author_guard(events)
    for ed in (events, tries):
        arrange(ed)
    if not BEL.compile_blueprint(bp):
        raise RuntimeError(f"{T.TRAVERSAL_BP} failed to compile")
    eas.save_loaded_asset(bp)
    _log(f"{bp.get_name()}: reads any Character (no interface), and its Server event "
         "asks the RPC guard first")
    return bp


# ─── On the player ───────────────────────────────────────────────────────────

def install_traversal(bp):
    """The traversal component and the MotionWarping component its montages
    warp by, on the player. The caller has dropped both; with traversal off
    nothing is added. Returns whether they are there."""
    if not traversal_on():
        return False
    patch_traversal_logic()
    for cls_path, name in ((TRAVERSAL_CLASS, T.TRAVERSAL_COMPONENT),
                           (T.WARP_CLASS, T.WARP_COMPONENT)):
        cls = unreal.load_class(None, cls_path)
        if not cls:
            raise RuntimeError(f"{cls_path} did not load")
        _component_object(_add_component(bp, _root_handle(bp), cls, name))
    return True


def replicate_traversal(bp):
    """After a compile (a template's default): the component's Server and
    Multicast events travel only from a component that replicates."""
    if traversal_on():
        net.replicate_component(bp, T.TRAVERSAL_COMPONENT)


def jump_nodes(ed):
    """(the jump key's event, the Jump call) of the character's event graph."""
    keys = [n for n in ed.list_all_nodes()
            if _class(n) == "K2Node_EnhancedInputAction" and "IA_Jump" in _title(n)]
    jumps = _by_title(ed, "Jump", "K2Node_CallFunction")
    if len(keys) != 1 or len(jumps) != 1:
        raise RuntimeError(f"expected one IA_Jump event and one Jump call, found "
                           f"{len(keys)} and {len(jumps)}")
    return keys[0], jumps[0]


def jump_event(ed):
    """The JumpPressed custom event, or None as stock."""
    events = _by_title(ed, T.JUMP_EVENT, "K2Node_CustomEvent")
    return events[0] if events else None


def between(ed):
    """The exec nodes between the jump key's Started and the Jump call:
    none as stock; authored, the call of JumpPressed, that event and what it
    runs."""
    key, jump = jump_nodes(ed)
    event = jump_event(ed)
    found, stack = {}, [out(key, "Started")]
    if event is not None:
        found[event.get_name()] = event
        stack.append(then(event))
    while stack:
        for q in _fed(stack.pop()):
            node = PIN.get_owning_node(q)
            if node.get_name() == jump.get_name() or node.get_name() in found:
                continue
            found[node.get_name()] = node
            stack.extend(p for p in BEL.list_output_pins(node) if _is_exec(p))
    return list(found.values())


def unauthor_jump(bp):
    """The stock jump key again. First thing in the install, before the
    component is dropped: the traversal's nodes read it, and a graph that
    reads a component that is gone does not compile."""
    _unauthor_jump(BGE.get_graph_editor_by_name(bp, "EventGraph"))


def _unauthor_jump(ed):
    key, jump = jump_nodes(ed)
    mine = between(ed)
    if mine:
        ed.remove_nodes(mine + _data_feeders(mine, keep=[key, jump] + mine))
    PIN.break_pin_links(out(key, "Started"))
    _connect(out(key, "Started"), _exec_in(jump))


def author_jump(bp):
    """The jump key: Started -> JumpPressed, a custom event (a probe's press
    of the key: no key can be injected into a headless game) -> (on the
    ground, standing, not already in one) TryTraversalAction -> Jump when the
    check or the montage choice failed; anything else jumps as before. After
    a compile: it reads the component the install added."""
    ed = BGE.get_graph_editor_by_name(bp, "EventGraph")
    _unauthor_jump(ed)
    if not traversal_on():
        arrange(ed)
        return
    key, jump = jump_nodes(ed)
    PIN.break_pin_links(out(key, "Started"))
    g = _G(ed)
    event = g.keep(net.custom_event(ed, T.JUMP_EVENT))
    # By its bare name: an event of this graph's own, not yet compiled.
    g.call(T.JUMP_EVENT, [out(key, "Started")])
    comp = g.get(T.TRAVERSAL_COMPONENT)
    move = g.get(EP.CHARACTER_MOVEMENT)
    # Crouched or prone is the engine's one flag (and a low stance cannot jump).
    standing = g.call(FN_NOT, A=g.get(EP.IS_CROUCHED))
    busy = g.iget(comp, T.DOING_VAR, TRAVERSAL_CLASS)
    may = g.call(FN_AND, A=out(g.call(FN_AND, A=out(g.call(FN_ON_GROUND, self=move)),
                                      B=out(standing))),
                 B=out(g.call(FN_NOT, A=busy)))
    tries, jumps = g.branch(out(may), [then(event)])

    asks = g.keep(_palette(ed, NODE_MAKE_TRAVERSAL_INPUTS))
    reach = g.call(FN_MAP_CLAMPED, Value=out(g.call(FN_VSIZE_XY, A=out(g.call(FN_VELOCITY)))),
                   InRangeA="0.0", InRangeB=str(T.TRACE_FAR_AT_CMS),
                   OutRangeA=str(T.TRACE_NEAR_CM), OutRangeB=str(T.TRACE_FAR_CM))
    _connect(out(g.call(FN_ACTOR_FORWARD)), _field(asks, "TraceForwardDirection"))
    _connect(out(reach), _field(asks, "TraceForwardDistance"))
    for field, value in (("TraceRadius", T.TRACE_RADIUS_CM),
                         ("TraceHalfHeight", T.TRACE_HALF_HEIGHT_CM)):
        PIN.set_pin_value(_field(asks, field), str(value))
        if abs(float(PIN.get_pin_value(_field(asks, field)) or 0.0) - value) > 1e-6:
            raise RuntimeError(f"the traversal's {field} did not take {value}")
    attempt = g.call(f"{TRAVERSAL_CLASS}:{T.TRY_GRAPH}", [tries], self=comp)
    asked = next(p for p in BEL.list_input_pins(attempt)
                 if "Traversal Check Inputs" in str(PIN.get_pin_type_display_string(p)))
    _connect(next(iter(BEL.list_output_pins(asks))), asked)
    nothing = g.call(FN_OR, A=_loose_pin(attempt, "TraversalCheckFailed", is_input=False),
                     B=_loose_pin(attempt, "MontageSelectionFailed", is_input=False))
    plain, _climbs = g.branch(out(nothing), [then(attempt)])
    for pin in (jumps, plain):
        _connect(pin, _exec_in(jump))
    ed.add_comment_to_nodes(
        "The jump key (G5): on the ground and standing it tries the sample's traversal "
        "first (a mantle, a vault or a hurdle over a traversable block ahead) and "
        "jumps when there is nothing to climb. Scripts/combat/gas_traversal.py.", g.made)
    arrange(ed)
