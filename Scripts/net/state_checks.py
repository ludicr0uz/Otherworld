"""The verifiers' checks for where state lives (state.py, state_graph.py):
the two Blueprints, their replicated variables, the GameMode that names them
and no longer holds what moved, and the rule the move is for: no graph that
can run on a client reads the GameMode.

    check_state                 the assets (the weapons verifier)
    check_no_client_game_mode   the rule, over every Blueprint of the game
                                (the menu verifier: the HUD is built last)
"""

import unreal

from combat.game_state import MOVED_VARS
from combat.paths import GAME_MODE_BP_PATH
from net import state_consts as S
from uebp import net

BEL = unreal.BlueprintEditorLibrary
BGE = unreal.BlueprintGraphEditor
PIN = unreal.BlueprintGraphPinLibrary

# Content nobody here authors (dev/graph_fingerprint.py's list).
EXCLUDED = ("/Game/Fab", "/Game/Sourced", "/Game/FPS_Weapon_Bundle", "/Game/Characters",
            "/Game/LevelPrototyping", "/Game/Tmp", "/Game/Scratch", "/Game/GAS")
# Classes whose instances exist on the server alone (and in single player):
# a client has no GameMode, no AI controller and runs no behaviour tree.
SERVER_ONLY = ("GameModeBase", "AIController", "BTNode")
GET_MODE = "GetGameMode"
SWITCH = "SwitchHasAuthority"
AUTHORITY = "Authority"


def _bare(n):
    return "".join(str(BEL.get_node_title(n)).split())


def _parent(bp):
    return BEL.get_blueprint_parent_class(bp)


def check_state(check):
    made = ((S.PLAYER_STATE_BP_PATH, unreal.PlayerState, S.PLAYER_TABLE, "one player's"),
            (S.GAME_STATE_BP_PATH, unreal.GameStateBase, S.GAME_TABLE, "the world's"))
    mode = unreal.load_asset(GAME_MODE_BP_PATH)
    mode_cdo = unreal.get_default_object(BEL.generated_class(mode))
    for (path, parent, table, whose), prop in zip(
            made, (S.PLAYER_STATE_PROP, S.GAME_STATE_PROP)):
        name = path.rsplit("/", 1)[-1]
        bp = unreal.load_asset(path)
        check(f"{name} exists, a {parent.static_class().get_name()}",
              bool(bp) and _parent(bp) == parent.static_class(), str(bp))
        if not bp:
            continue
        cdo = unreal.get_default_object(BEL.generated_class(bp))
        flags = {str(v): net.compiled_replication(bp, v)[0] for v in table}
        check(f"{name} holds {whose} state, every variable Replicated: "
              f"{', '.join(table)}",
              all(k == net.REPLICATED for k in flags.values()), str(flags))
        got = {str(v): cdo.get_editor_property(v) for v in table}
        check(f"{name} starts at its defaults",
              got == {str(v): v.default for v in table}, str(got))
        check(f"{name} replicates, as the engine's own does",
              bool(cdo.get_editor_property("replicates")))
        check(f"the GameMode names {name}",
              mode_cdo.get_editor_property(prop) == BEL.generated_class(bp),
              str(mode_cdo.get_editor_property(prop)))
    left = sorted(str(n) for n in BEL.list_member_variable_names(mode)
                  if str(n).rsplit(".", 1)[-1] in MOVED_VARS)
    check("the GameMode no longer holds what a client reads: "
          f"{', '.join(MOVED_VARS)}", not left, str(left))


def _packages():
    registry = unreal.AssetRegistryHelpers.get_asset_registry()
    found = registry.get_assets(unreal.ARFilter(
        package_paths=["/Game"], recursive_paths=True, recursive_classes=True,
        class_paths=[unreal.TopLevelAssetPath("/Script/Engine", "Blueprint")]))
    return sorted({str(a.package_name) for a in found
                   if not any(str(a.package_name).startswith(x + "/") for x in EXCLUDED)})


def _is_a(bp, names):
    """Whether the Blueprint's class descends from one of the native ``names``."""
    cdo = unreal.get_default_object(BEL.generated_class(bp))
    return any(isinstance(cdo, getattr(unreal, n)) for n in names if hasattr(unreal, n))


def _guarded(get):
    """A GetGameMode whose every reader is a cast run only off the Authority
    arm of a Switch Has Authority (state_graph.server_game_mode)."""
    readers = [PIN.get_owning_node(p)
               for o in BEL.list_output_pins(get) for p in PIN.list_connected_pins(o)]
    if not readers:
        return False
    for cast in readers:
        run = BEL.find_input_pin(cast, "execute")
        feeds = PIN.list_connected_pins(run) if run else []
        if not feeds or not all(
                _bare(PIN.get_owning_node(f)) == SWITCH
                and str(PIN.get_pin_name(f)) == AUTHORITY for f in feeds):
            return False
    return True


def scan_game_mode_reads():
    """Every GetGameMode in the game's Blueprints, sorted three ways:
    ``(server_only, guarded, bare)``, each a list of "Blueprint.Graph"."""
    server_only, guarded, bare = [], [], []
    for package in _packages():
        bp = unreal.load_asset(package)
        if not bp or not BEL.generated_class(bp):
            continue
        name = package.rsplit("/", 1)[-1]
        only = _is_a(bp, SERVER_ONLY)
        for graph in sorted(str(g) for g in BEL.list_graph_names(bp)):
            ed = BGE.get_graph_editor_by_name(bp, graph)
            if not ed:
                continue
            for n in ed.list_all_nodes():
                if _bare(n) != GET_MODE:
                    continue
                where = f"{name}.{graph}"
                (server_only if only else guarded if _guarded(n) else bare).append(where)
    return server_only, guarded, bare


def check_no_client_game_mode(check):
    server_only, guarded, bare = scan_game_mode_reads()
    check("no graph that can run on a client reads the GameMode: every "
          "GetGameMode outside the server's own classes (the GameMode, an AI "
          "controller, a behaviour tree's node) runs off Switch Has Authority",
          not bare, ", ".join(sorted(set(bare))) or
          f"{len(guarded)} behind the switch, {len(server_only)} in server-only classes")
    # The scan has to be seeing reads at all for "none bare" to mean anything.
    homes = {w.split(".")[0] for w in guarded}
    check("the scan finds the server's reads where they are: the health "
          "component's (spawn counter, gun drop) and the noise's writers "
          "behind the switch, the wanderers' hearing in their AI controller",
          {"BP_HealthComponent", "BP_WeaponComponent", "BP_FootstepComponent"} <= homes
          and bool(server_only), f"guarded {sorted(homes)}; "
          f"server-only {sorted({w.split('.')[0] for w in server_only})}")
