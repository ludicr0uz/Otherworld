"""graph_fingerprint_diff.py -- compare two graph_fingerprint.py directories.

    python3 Scripts/dev/graph_fingerprint_diff.py baseline_a after_phase_1

Prints the Blueprints added and removed, then per Blueprint the variable,
component, node and connection records added and removed. Exit code 1 on any
difference. Plain Python: no editor needed.
"""

import json
import os
import sys

PROJECT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
FINGERPRINT_ROOT = os.path.join(PROJECT, "Saved", "uepy", "fingerprint")
MAX_LINES = 40          # per section, so one broken graph does not bury the rest


def resolve(arg):
    if os.path.isdir(arg):
        return arg
    return os.path.join(FINGERPRINT_ROOT, arg)


def load(directory):
    out = {}
    for name in sorted(os.listdir(directory)):
        if name.endswith(".json") and not name.startswith("_"):
            with open(os.path.join(directory, name)) as fh:
                out[name[:-5]] = json.load(fh)
    return out


def _readable(link, nodes):
    """A connection with each node id replaced by its record's first fields."""
    def end(text):
        node_id, _, pin = text.partition(".")
        record = nodes.get(node_id, "?")
        return f"[{' | '.join(record.split(' | ')[:2])} {node_id}].{pin}"
    a, _, b = link.partition(" -> ")
    return f"{end(a)} -> {end(b)}"


def _graph_lines(name, a, b):
    lines = []
    nodes_a, nodes_b = a.get("nodes", {}), b.get("nodes", {})
    for node_id in sorted(set(nodes_a) - set(nodes_b)):
        lines.append(f"  {name}: - node {node_id} {nodes_a[node_id]}")
    for node_id in sorted(set(nodes_b) - set(nodes_a)):
        lines.append(f"  {name}: + node {node_id} {nodes_b[node_id]}")
    links_a, links_b = set(a.get("connections", [])), set(b.get("connections", []))
    for link in sorted(links_a - links_b):
        lines.append(f"  {name}: - link {_readable(link, nodes_a)}")
    for link in sorted(links_b - links_a):
        lines.append(f"  {name}: + link {_readable(link, nodes_b)}")
    return lines


def diff_blueprint(a, b):
    """The lines that differ between two fingerprints of one Blueprint."""
    lines = []
    for key in ("class", "parent"):
        if a.get(key) != b.get(key):
            lines.append(f"  {key}: {a.get(key)!r} -> {b.get(key)!r}")
    vars_a, vars_b = a.get("variables", {}), b.get("variables", {})
    for name in sorted(set(vars_a) - set(vars_b)):
        lines.append(f"  - variable {name} {json.dumps(vars_a[name], sort_keys=True)}")
    for name in sorted(set(vars_b) - set(vars_a)):
        lines.append(f"  + variable {name} {json.dumps(vars_b[name], sort_keys=True)}")
    for name in sorted(set(vars_a) & set(vars_b)):
        if vars_a[name] != vars_b[name]:
            lines.append(f"  ~ variable {name}: {json.dumps(vars_a[name], sort_keys=True)}"
                         f" -> {json.dumps(vars_b[name], sort_keys=True)}")
    comps_a, comps_b = set(a.get("components", [])), set(b.get("components", []))
    lines += [f"  - component {c}" for c in sorted(comps_a - comps_b)]
    lines += [f"  + component {c}" for c in sorted(comps_b - comps_a)]
    graphs_a, graphs_b = a.get("graphs", {}), b.get("graphs", {})
    for name in sorted(set(graphs_a) | set(graphs_b)):
        if name not in graphs_b:
            lines.append(f"  - graph {name}")
        elif name not in graphs_a:
            lines.append(f"  + graph {name}")
        else:
            lines += _graph_lines(name, graphs_a[name], graphs_b[name])
    return lines


def diff(dir_a, dir_b):
    """Every difference between two fingerprint directories, as lines."""
    a, b = load(dir_a), load(dir_b)
    lines = [f"- Blueprint {name}" for name in sorted(set(a) - set(b))]
    lines += [f"+ Blueprint {name}" for name in sorted(set(b) - set(a))]
    for name in sorted(set(a) & set(b)):
        changed = diff_blueprint(a[name], b[name])
        if changed:
            lines.append(f"~ Blueprint {name}: {len(changed)} differences")
            lines += changed[:MAX_LINES]
            if len(changed) > MAX_LINES:
                lines.append(f"  ... {len(changed) - MAX_LINES} more")
    return lines, len(a), len(b)


def main(argv):
    if len(argv) != 2:
        print(__doc__)
        return 2
    dir_a, dir_b = resolve(argv[0]), resolve(argv[1])
    lines, count_a, count_b = diff(dir_a, dir_b)
    for line in lines:
        print(line)
    print(f"[fingerprint-diff] {argv[0]} ({count_a} Blueprints) vs {argv[1]} ({count_b}): "
          + ("identical" if not lines else f"{len(lines)} lines differ"))
    if not count_a or not count_b:
        print("[fingerprint-diff] an empty directory proves nothing")
        return 1
    return 1 if lines else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
