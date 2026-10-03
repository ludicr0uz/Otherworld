"""graph_fingerprint.py -- what every authored Blueprint IS, with no positions.

The safety net for refactors of the authoring code: two builds whose
fingerprints are equal produced structurally identical Blueprints. One JSON
file per Blueprint: member variables (type and CDO default), components, and
per graph the node records and the connections between them.

From a shell (it hands itself to the open editor through uepy.py):
    python3 Scripts/dev/graph_fingerprint.py <label | directory>
A bare label writes Saved/uepy/fingerprint/<label>/. Compare two with
graph_fingerprint_diff.py.

Scope: every Blueprint and WidgetBlueprint under /Game outside the packs and
scratch folders (EXCLUDED), plus the three stock assets the builders patch.
"""

import hashlib
import json
import os
import re
import subprocess
import sys

try:
    import unreal
except ImportError:          # on the host: only the launcher below runs
    unreal = None

PROJECT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
FINGERPRINT_ROOT = os.path.join(PROJECT, "Saved", "uepy", "fingerprint")
REQUEST = os.path.join(FINGERPRINT_ROOT, "_request.json")

EXCLUDED = ("/Game/Fab", "/Game/Sourced", "/Game/FPS_Weapon_Bundle", "/Game/Characters",
            "/Game/LevelPrototyping", "/Game/Tmp")
PATCHED_STOCK = ("ABP_Unarmed", "BP_ThirdPersonCharacter", "BP_ThirdPersonGameMode")
CLASSES = ("Blueprint", "WidgetBlueprint")


# ─── Host side ───────────────────────────────────────────────────────────────

def out_dir(arg):
    """A bare label is a directory under Saved/uepy/fingerprint."""
    if os.sep in arg or arg.startswith("."):
        return os.path.abspath(arg)
    return os.path.join(FINGERPRINT_ROOT, arg)


def launch(argv):
    target = out_dir(argv[0] if argv else "latest")
    os.makedirs(FINGERPRINT_ROOT, exist_ok=True)
    with open(REQUEST, "w") as fh:
        json.dump({"out": target}, fh)
    uepy = os.path.join(PROJECT, "Scripts", "dev", "uepy.py")
    return subprocess.call([sys.executable, uepy, "--summary", os.path.abspath(__file__)])


# ─── Values ──────────────────────────────────────────────────────────────────

_TEXT_KEY = re.compile(r'(NSLOCTEXT\("[^"]*", )"[0-9A-Fa-f]{32}", ')


def literal(text):
    """A pin literal, canonical: a default reads "" or "0.0" depending on
    which editor authored it, and numerics differ only in formatting."""
    text = str(text)
    if text == "":
        return "0"
    # A text literal's key is a fresh GUID on every build.
    text = _TEXT_KEY.sub(r'\1"", ', text)
    try:
        return format(float(text), ".6g")
    except ValueError:
        return text.lower() if text.lower() in ("true", "false") else text


def value(v, depth=0):
    """A CDO default as JSON, by combat.graph._same's rules: structs through
    to_tuple(), objects by path, FKey through export_text(), arrays by element."""
    if v is None or isinstance(v, (bool, int, str)):
        return v
    if isinstance(v, float):
        return float(format(v, ".6g"))
    if depth > 6:
        return "<deep>"
    if isinstance(v, unreal.Key):
        return v.export_text()
    if isinstance(v, (unreal.Name, unreal.Text)):
        return str(v)
    if isinstance(v, unreal.Map):
        return sorted(([value(k, depth + 1), value(x, depth + 1)] for k, x in v.items()),
                      key=json.dumps)
    if isinstance(v, unreal.Set):
        return sorted((value(x, depth + 1) for x in v), key=json.dumps)
    if isinstance(v, (list, tuple, unreal.Array, unreal.FixedArray)):
        return [value(x, depth + 1) for x in v]
    if isinstance(v, unreal.EnumBase):
        return f"{type(v).__name__}.{v.name}"
    if hasattr(v, "get_path_name"):
        return v.get_path_name()
    if hasattr(v, "to_tuple"):
        fields = v.to_tuple()
        if fields:
            return [type(v).__name__] + [value(x, depth + 1) for x in fields]
        return [type(v).__name__, v.export_text()]
    # A delegate reads back as one wrapper type or another from run to run.
    return "<opaque>"


_TYPE_FIELDS = ("PinCategory", "PinSubCategory", "PinSubCategoryObject", "ContainerType")


def pin_type(t):
    text = t.export_text()
    out = []
    for field in _TYPE_FIELDS:
        m = re.search(field + r'=("(?:[^"\\]|\\.)*"|[^,()]*)', text)
        out.append(m.group(1).strip('"') if m else "")
    return "|".join(out)


# ─── One Blueprint ───────────────────────────────────────────────────────────

def variables(bp, BEL):
    cdo = unreal.get_default_object(BEL.generated_class(bp))
    out = {}
    for name in sorted(str(n) for n in BEL.list_member_variable_names(bp)):
        # An inherited variable is listed by its full path; its default on
        # this class is still this Blueprint's (a gun's numbers are all that).
        prop = name.rsplit(".", 1)[-1]
        try:
            default = value(cdo.get_editor_property(prop))
        except Exception as exc:                      # not exposed to Python
            default = f"<unreadable: {type(exc).__name__}>"
        try:
            kind = pin_type(BEL.get_member_variable_type(bp, name))
        except Exception as exc:
            kind = f"<untyped: {type(exc).__name__}>"
        out[name] = {"type": kind, "default": default}
    return out


def components(bp):
    SDL = unreal.SubobjectDataBlueprintFunctionLibrary
    sds = unreal.get_engine_subsystem(unreal.SubobjectDataSubsystem)
    out = set()
    for handle in sds.k2_gather_subobject_data_for_blueprint(bp):
        data = sds.k2_find_subobject_data_from_handle(handle)
        if not data:
            continue
        obj = SDL.get_object(data)
        parent = SDL.get_parent_handle(data)
        parent_data = sds.k2_find_subobject_data_from_handle(parent) if parent else None
        out.add(" | ".join((
            str(SDL.get_variable_name(data)),
            obj.get_class().get_path_name() if obj else "",
            str(SDL.get_variable_name(parent_data)) if parent_data else "")))
    return sorted(out)


def _ordinal_key(name):
    """Creation order: the trailing integer of the node's object name."""
    m = re.search(r"_(\d+)$", name)
    return (int(m.group(1)) if m else -1, name)


def _pin_label(pin, PIN):
    return f"{PIN.get_pin_name(pin)}:{PIN.get_pin_type_display_string(pin)}"


def graph(ed, BEL, PIN):
    """{"nodes": {id: record}, "connections": [...]}. A node's id is a hash of
    its record plus an ordinal among the nodes sharing that record."""
    records, links = {}, []
    for node in ed.list_all_nodes():
        cls = node.get_class().get_name()
        if cls == "EdGraphNode_Comment":
            continue
        name = node.get_name()
        ins, outs, loose = [], [], []
        for pin in BEL.list_input_pins(node):
            ins.append(_pin_label(pin, PIN))
            if not PIN.list_connected_pins(pin):
                loose.append(f"{PIN.get_pin_name(pin)}={literal(PIN.get_pin_value(pin))}")
        for pin in BEL.list_output_pins(node):
            outs.append(_pin_label(pin, PIN))
            for other in PIN.list_connected_pins(pin):
                links.append((name, str(PIN.get_pin_name(pin)),
                              PIN.get_owning_node(other).get_name(),
                              str(PIN.get_pin_name(other))))
        title = str(BEL.get_node_title(node)).replace("\n", " / ")
        records[name] = " | ".join((cls, title, ",".join(sorted(ins)),
                                    ",".join(sorted(outs)), ";".join(sorted(loose))))
    ids, seen = {}, {}
    for name in sorted(records, key=_ordinal_key):
        digest = hashlib.sha1(records[name].encode()).hexdigest()[:10]
        seen[digest] = seen.get(digest, 0) + 1
        ids[name] = f"{digest}#{seen[digest]}"
    return {
        "nodes": {ids[n]: records[n] for n in sorted(records, key=lambda n: ids[n])},
        "connections": sorted(f"{ids[a]}.{pa} -> {ids[b]}.{pb}"
                              for a, pa, b, pb in links if a in ids and b in ids),
    }


def fingerprint(bp):
    BEL, PIN, BGE = (unreal.BlueprintEditorLibrary, unreal.BlueprintGraphPinLibrary,
                     unreal.BlueprintGraphEditor)
    parent = BEL.get_blueprint_parent_class(bp)
    graphs = {}
    for name in sorted(str(n) for n in BEL.list_graph_names(bp)):
        ed = BGE.get_graph_editor_by_name(bp, name)
        if ed:
            graphs[name] = graph(ed, BEL, PIN)
    return {
        "path": bp.get_path_name().split(".")[0],
        "class": type(bp).__name__,
        "parent": parent.get_path_name() if parent else "",
        "variables": variables(bp, BEL),
        "components": components(bp),
        "graphs": graphs,
    }


# ─── The sweep ───────────────────────────────────────────────────────────────

def in_scope():
    """Package paths, from the asset registry."""
    registry = unreal.AssetRegistryHelpers.get_asset_registry()
    found = registry.get_assets(unreal.ARFilter(
        package_paths=["/Game"], recursive_paths=True, recursive_classes=True,
        class_paths=[unreal.TopLevelAssetPath("/Script/Engine", "Blueprint")]))
    out = set()
    for asset in found:
        package = str(asset.package_name)
        if str(asset.asset_name) in PATCHED_STOCK:
            out.add(package)
        elif (str(asset.asset_class_path.asset_name) in CLASSES
              and not any(package == x or package.startswith(x + "/") for x in EXCLUDED)):
            out.add(package)
    return sorted(out)


def run():
    target = os.path.join(FINGERPRINT_ROOT, "latest")
    if os.path.exists(REQUEST):
        with open(REQUEST) as fh:
            target = json.load(fh)["out"]
    os.makedirs(target, exist_ok=True)
    for stale in os.listdir(target):
        if stale.endswith(".json"):
            os.remove(os.path.join(target, stale))
    packages = in_scope()
    nodes = 0
    for package in packages:
        bp = unreal.load_asset(package)
        if not bp:
            raise RuntimeError(f"could not load {package}")
        data = fingerprint(bp)
        nodes += sum(len(g["nodes"]) for g in data["graphs"].values())
        with open(os.path.join(target, package.strip("/").replace("/", ".") + ".json"), "w") as fh:
            json.dump(data, fh, indent=1, sort_keys=True)
    unreal.log_warning(f"[GEN] fingerprint: {len(packages)} Blueprints, {nodes} nodes -> {target}")


if __name__ == "__main__":
    if unreal is None:
        sys.exit(launch(sys.argv[1:]))
    run()
