"""The verifiers' check for whose pawn a graph reads: none asks for player 0's.

On a server, player 0 is whoever joined first, so a graph that calls
GetPlayerPawn(0) is about someone else's character. Each has a better thing
to ask:

    what a player owns   the HUD its owning pawn (``FN_GET_OWNING_PAWN``), a
                         widget its owning player's, a component its owner,
                         an animation graph the pawn it animates
    everything else      (a world actor, a wanderer's controller, the health
                         component of a dead wanderer) the living players:
                         all of them or the nearest (net/players.py)

    check_no_player_zero_pawn   the rule, over every Blueprint of the game and
                                every builder module (the menu verifier: the
                                HUD is built last)
"""

import os

import unreal

from combat.paths import ABP_PATH
from net import players_consts as P
from net.state_checks import _bare, _is_a, _packages
from uebp.nodes import system

BEL = unreal.BlueprintEditorLibrary
BGE = unreal.BlueprintGraphEditor
PIN = unreal.BlueprintGraphPinLibrary

# What a player owns, by native class.
OWNED = ("HUD", "UserWidget", "ActorComponent", "AnimInstance")
GET_PAWN = "GetPlayerPawn"
OWN_PAWN = "GetOwningPawn"
# The player's animation Blueprint is stock content the builders patch, in a
# directory the scan otherwise leaves alone.
ALSO = (ABP_PATH,)
# Who asks the players library, at the least: the world's own actors, the
# health component (a dead wanderer's replacement) and a wanderer's controller.
ASKERS = {"BP_AmmoPickup", "BP_Campfire", "BP_DayNightCycle", "BP_HealthComponent",
          "BP_ForestWandererAI"}
SCRIPTS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CATALOG_NAME = "FN_GET_PLAYER_PAWN"
# Where the name is not a builder's: this check, the dev tooling, the probes
# (a probe's Python reads a pawn by index on purpose: probes/context.py).
NOT_BUILDERS = ("net/owner_checks.py", "dev/", "probes/")


def _has_exec(n):
    return "execute" in {str(PIN.get_pin_name(p)) for p in BEL.list_input_pins(n)}


def scan_pawn_reads():
    """``(player_zero, owning, asked, exec_nearest)``: where a Blueprint calls
    GetPlayerPawn, where a HUD asks for its owning pawn, where the players
    library is asked, and any NearestLivingPlayer node that is not pure, each
    a list of "Blueprint.Graph"."""
    player_zero, owning, asked, exec_nearest = [], [], [], []
    for package in sorted({*_packages(), *ALSO}):
        bp = unreal.load_asset(package)
        if not bp or not BEL.generated_class(bp):
            continue
        name = package.rsplit("/", 1)[-1]
        owned = _is_a(bp, OWNED)
        for graph in sorted(str(g) for g in BEL.list_graph_names(bp)):
            ed = BGE.get_graph_editor_by_name(bp, graph)
            if not ed:
                continue
            for n in ed.list_all_nodes():
                title = _bare(n)
                if title == GET_PAWN:
                    player_zero.append(f"{name}.{graph}")
                elif title == OWN_PAWN and owned:
                    owning.append(f"{name}.{graph}")
                elif title in (P.LIVING_TITLE, P.NEAREST_TITLE) and package != P.PLAYERS_BP_PATH:
                    asked.append(f"{name}.{graph}")
                    if title == P.NEAREST_TITLE and _has_exec(n):
                        exec_nearest.append(f"{name}.{graph}")
    return player_zero, owning, asked, exec_nearest


def scan_sources():
    """The modules under Scripts/ that name the catalog's GetPlayerPawn."""
    found = []
    for root, _dirs, files in os.walk(SCRIPTS):
        for f in sorted(files):
            if not f.endswith(".py"):
                continue
            path = os.path.join(root, f)
            rel = os.path.relpath(path, SCRIPTS)
            if rel.startswith(NOT_BUILDERS):
                continue
            with open(path, encoding="utf-8") as fh:
                if CATALOG_NAME in fh.read():
                    found.append(rel)
    return sorted(found)


def check_no_player_zero_pawn(check):
    player_zero, owning, asked, exec_nearest = scan_pawn_reads()
    check("no graph reads player 0's pawn: no GetPlayerPawn in any Blueprint "
          "of the game (the HUD asks for its owning pawn, a component for its "
          "owner, a world actor or a wanderer for the living players)",
          not player_zero, ", ".join(sorted(set(player_zero)))
          or f"{len(owning)} owning-pawn reads, {len(asked)} of the living players")
    # The scan has to be seeing the nodes for "none" to mean anything.
    homes = {w.split(".")[0] for w in asked}
    check("the scan finds the pawn reads where they are: the HUD's of its "
          "owning pawn, and the world actors', the health component's and the "
          "wanderers' of the players library (NearestLivingPlayer a pure node)",
          {w.split(".")[0] for w in owning} == {"BP_GraphicsMenuHUD"}
          and len(owning) >= 10 and not exec_nearest
          and all(any(h.startswith(a) for h in homes) for a in ASKERS),
          f"owning {len(owning)} in {sorted({w.split('.')[0] for w in owning})}; "
          f"the players library asked in {sorted(homes)}")
    named = scan_sources()
    check(f"no builder names {CATALOG_NAME}, and the node catalog no longer has it",
          not named and not hasattr(system, CATALOG_NAME), ", ".join(named))
