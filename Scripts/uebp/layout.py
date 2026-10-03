"""Laying a graph out after it is authored, so no builder carries coordinates.

``arrange(ed)`` places every node of one graph on a grid: a column per step
along the wires, a row per node within the column. Nothing reads positions
back; this only keeps the node bodies from piling up on the origin for
whoever opens the Blueprint in the editor.
"""

try:
    import unreal
except ImportError:          # the dev tests exercise columns() on the host
    unreal = None

BEL = unreal.BlueprintEditorLibrary if unreal else None
PIN = unreal.BlueprintGraphPinLibrary if unreal else None

COLUMN_PITCH = 400
ROW_PITCH = 200
LIMIT = 100000          # node positions stay within +-LIMIT


def _wires(nodes):
    """(successors, has_exec): who each node's outputs feed, by node name, and
    which nodes sit on an exec chain."""
    known = {n.get_name() for n in nodes}
    successors, has_exec = {}, set()
    for node in nodes:
        name = node.get_name()
        fed = successors.setdefault(name, [])
        for pin in BEL.list_output_pins(node):
            if str(PIN.get_pin_type_display_string(pin)).lower() == "exec":
                has_exec.add(name)
            for other in PIN.list_connected_pins(pin):
                target = PIN.get_owning_node(other).get_name()
                if target in known and target != name and target not in fed:
                    fed.append(target)
        for pin in BEL.list_input_pins(node):
            if str(PIN.get_pin_type_display_string(pin)).lower() == "exec":
                has_exec.add(name)
    return successors, has_exec


def _topological(order, successors):
    """``order`` sorted so every node follows its suppliers, and the back edges
    that had to be ignored to get there (an exec loop is the one cycle a graph
    here has)."""
    done, on_path, out, back = set(), set(), [], set()
    for root in order:
        if root in done:
            continue
        stack = [(root, iter(successors[root]))]
        on_path.add(root)
        while stack:
            name, rest = stack[-1]
            for target in rest:
                if target in on_path:
                    back.add((name, target))
                elif target not in done:
                    on_path.add(target)
                    stack.append((target, iter(successors[target])))
                    break
            else:
                stack.pop()
                on_path.discard(name)
                done.add(name)
                out.append(name)
    out.reverse()
    return out, back


def columns(order, successors, has_exec):
    """{name: column}. An exec node sits one column right of the furthest node
    feeding it; a pure node one column left of its nearest consumer."""
    ordered, back = _topological(order, successors)
    column = {}
    for name in ordered:
        if name in has_exec:
            column.setdefault(name, 0)
            for target in successors[name]:
                if target in has_exec and (name, target) not in back:
                    column[target] = max(column.get(target, 0), column[name] + 1)
    for name in reversed(ordered):
        if name in has_exec:
            continue
        fed = [column[t] for t in successors[name] if (name, t) not in back and t in column]
        column[name] = min(fed) - 1 if fed else 0
    low = min(column.values(), default=0)
    return {name: col - low for name, col in column.items()}, back


def arrange(ed):
    """Lay out every node of ``ed``'s graph. Call it once the graph is
    authored, before the compile."""
    nodes = [n for n in ed.list_all_nodes()
             if n.get_class().get_name() != "EdGraphNode_Comment"]
    if not nodes:
        return
    order = [n.get_name() for n in nodes]          # creation order
    successors, has_exec = _wires(nodes)
    column, back = columns(order, successors, has_exec)
    rows = {}
    for name in order:
        rows.setdefault(column[name], []).append(name)
    width = (max(rows) + 1) * COLUMN_PITCH
    height = max(len(r) for r in rows.values()) * ROW_PITCH
    # From the origin while that fits, centred on it once it does not.
    left = -min(LIMIT, width // 2) if width > LIMIT else 0
    top = -min(LIMIT, height // 2) if height > LIMIT else 0
    by_name = {n.get_name(): n for n in nodes}
    for col, names in rows.items():
        for row, name in enumerate(names):
            x = max(-LIMIT, min(LIMIT, left + col * COLUMN_PITCH))
            y = max(-LIMIT, min(LIMIT, top + row * ROW_PITCH))
            BEL.set_node_pos(by_name[name], unreal.IntPoint(x, y))
    graph = ed.get_graph()
    where = f"{graph.get_outer().get_name()}/{graph.get_name()}" if graph else "?"
    unreal.log_warning(
        f"[GEN] layout {where}: {len(nodes)} nodes, {len(rows)} columns, "
        f"{height // ROW_PITCH} rows at most"
        + (f", {len(back)} loop wire(s) ignored" if back else ""))
