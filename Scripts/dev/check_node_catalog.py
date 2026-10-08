"""check_node_catalog.py -- every path in uebp/nodes resolves in this editor.

    python3 Scripts/dev/uepy.py --summary Scripts/dev/check_node_catalog.py

A function path that does not resolve yields a pinless node, and a palette
name that does not exist yields nothing: either way the failure surfaces much
later, in whichever builder first uses it. This makes each node in a scratch
Blueprint under /Game/Tmp (one per kind of graph a builder authors: an actor,
a HUD, a game instance, a controller, a widget, a BT task, an ability, an anim graph and an anim Blueprint's event graph), asserts
it has pins exactly as uebp.graph._node does, and deletes the scratch assets.
A path passes if it resolves in any of them. Exits non-zero on a miss.
"""

import importlib
import os
import pkgutil
import sys

import unreal

SCRIPTS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, SCRIPTS)
for _name in [m for m in sys.modules if m.split(".")[0] == "uebp"]:
    del sys.modules[_name]

import uebp.nodes                                                 # noqa: E402

BEL = unreal.BlueprintEditorLibrary
BGE = unreal.BlueprintGraphEditor
SCRATCH = "/Game/Tmp"
EXCLUDED = ("/Game/Fab", "/Game/Sourced", "/Game/FPS_Weapon_Bundle", "/Game/Characters",
            "/Game/LevelPrototyping", "/Game/Tmp")
# (name, parent class path, graph): the kinds of graph the builders author.
CONTEXTS = (
    ("Actor", "/Script/Engine.Actor", "EventGraph"),
    ("HUD", "/Script/Engine.HUD", "EventGraph"),
    ("GameInstance", "/Script/Engine.GameInstance", "EventGraph"),
    ("AIController", "/Script/AIModule.AIController", "EventGraph"),
    ("Widget", "/Script/UMG.UserWidget", "EventGraph"),
    ("BTTask", "/Script/AIModule.BTTask_BlueprintBase", "EventGraph"),
    ("Ability", "/Script/GameplayAbilities.GameplayAbility", "EventGraph"),
)


def catalog():
    """{constant name: path}, from every module of uebp.nodes."""
    out = {}
    for info in pkgutil.iter_modules(uebp.nodes.__path__):
        module = importlib.import_module(f"uebp.nodes.{info.name}")
        for name, value in vars(module).items():
            if name.startswith(("FN_", "NODE_", "MACRO_")) and isinstance(value, str):
                out[name] = value
    return out


def load_project_classes():
    """A cast node exists only for a loaded class: load every project Blueprint."""
    registry = unreal.AssetRegistryHelpers.get_asset_registry()
    for asset in registry.get_assets(unreal.ARFilter(
            package_paths=["/Game"], recursive_paths=True, recursive_classes=True,
            class_paths=[unreal.TopLevelAssetPath("/Script/Engine", "Blueprint")])):
        package = str(asset.package_name)
        if not any(package.startswith(x) for x in EXCLUDED):
            unreal.load_asset(package)


def scratch_graphs():
    """[(context name, graph editor, asset path)]: one empty graph per context,
    plus the anim graph of a scratch copy of ABP_Unarmed."""
    tools = unreal.AssetToolsHelpers.get_asset_tools()
    out = []
    for name, parent_path, graph in CONTEXTS:
        parent = unreal.load_class(None, parent_path)
        if not parent:
            unreal.log_warning(f"[VERIFY] note: no class {parent_path}; context skipped")
            continue
        path = f"{SCRATCH}/BP_NodeCheck_{name}"
        if unreal.EditorAssetLibrary.does_asset_exist(path):
            unreal.EditorAssetLibrary.delete_asset(path)
        factory = unreal.BlueprintFactory()
        factory.set_editor_property("parent_class", parent)
        bp = tools.create_asset(path.rsplit("/", 1)[1], SCRATCH, unreal.Blueprint, factory)
        ed = BGE.get_graph_editor_by_name(bp, graph) if bp else None
        if not ed:
            unreal.log_warning(f"[VERIFY] note: no {graph} in a {name} Blueprint")
            continue
        nodes = ed.list_all_nodes()
        if nodes:
            ed.remove_nodes(nodes)       # the placeholder events block their own palette entry
        out.append((name, ed, path))
    registry = unreal.AssetRegistryHelpers.get_asset_registry()
    stock = [str(a.package_name) for a in registry.get_assets_by_class(
        unreal.TopLevelAssetPath("/Script/Engine", "AnimBlueprint"))
        if str(a.asset_name) == "ABP_Unarmed"]
    if stock:
        path = f"{SCRATCH}/ABP_NodeCheck_Anim"
        if unreal.EditorAssetLibrary.does_asset_exist(path):
            unreal.EditorAssetLibrary.delete_asset(path)
        copy = unreal.EditorAssetLibrary.duplicate_asset(stock[0], path)
        ed = BGE.get_graph_editor_by_name(copy, "AnimGraph") if copy else None
        if ed:
            out.append(("AnimGraph", ed, path))
        # ...and its event graph, emptied: an anim instance's own events
        # (BlueprintInitializeAnimation) are in no other graph's palette.
        events = BGE.get_graph_editor_by_name(copy, "EventGraph") if copy else None
        if events:
            events.remove_nodes(events.list_all_nodes())
            out.append(("AnimEvents", events, path))
    return out


def resolves(ed, name, path):
    if name.startswith("FN_"):
        node = ed.add_call_function_node(path)
    elif name.startswith("MACRO_"):
        node = ed.add_macro_node(path)
    else:
        node = ed.create_node_from_name(path, unreal.Vector2D(0.0, 0.0), [])
    return bool(node) and bool(BEL.list_all_pins(node))


def main():
    load_project_classes()
    graphs = scratch_graphs()
    paths = catalog()
    missed = []
    try:
        for name in sorted(paths):
            where = next((ctx for ctx, ed, _p in graphs if resolves(ed, name, paths[name])),
                         None)
            if not where:
                missed.append(name)
            unreal.log_warning(f"[VERIFY] {'PASS' if where else 'FAIL'}  {name}"
                               + (f" — {paths[name]} resolves nowhere" if not where else ""))
    finally:
        for path in sorted({path for _ctx, _ed, path in graphs}):
            unreal.EditorAssetLibrary.delete_asset(path)
    unreal.log_warning(f"[VERIFY] {len(paths) - len(missed)}/{len(paths)} checks passed "
                       f"(node catalog paths, over {len(graphs)} graph contexts)")
    if missed:
        raise RuntimeError(f"{len(missed)} catalog paths do not resolve: {', '.join(missed)}")


if __name__ == "__main__":
    main()
