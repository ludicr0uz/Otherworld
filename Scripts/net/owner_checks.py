"""The verifiers' check for whose pawn a player's own things read: none of them
asks for player 0's.

On a server, player 0 is whoever joined first, so a HUD, a widget, a component
or an animation graph that calls GetPlayerPawn(0) is about someone else's
character. Each has a pawn of its own to ask: the HUD its owning pawn
(``FN_GET_OWNING_PAWN``), a widget its owning player's
(``FN_GET_OWNING_PLAYER_PAWN``), a component its owner, an animation graph the
pawn it animates (TryGetPawnOwner).

    check_no_player_zero_pawn   the rule, over every Blueprint of those four
                                kinds and over the packages that author them
                                (the menu verifier: the HUD is built last)

World actors and the wanderers still read player 0 (M9, M27); they are not of
these kinds, bar the one component named in ``NOT_THE_PLAYERS``.
"""

import os

import unreal

from combat.paths import ABP_PATH
from net.state_checks import _bare, _is_a, _packages

BEL = unreal.BlueprintEditorLibrary
BGE = unreal.BlueprintGraphEditor

# What a player owns, by native class.
OWNED = ("HUD", "UserWidget", "ActorComponent", "AnimInstance")
GET_PAWN = "GetPlayerPawn"
OWN_PAWN = "GetOwningPawn"
# The player's animation Blueprint is stock content the builders patch, in a
# directory the scan otherwise leaves alone.
ALSO = (ABP_PATH,)
# A component of these kinds whose read of player 0 is not about its owner.
NOT_THE_PLAYERS = {
    "BP_HealthComponent": "a dead wanderer's replacement is spawned in a band "
                          "round the player (combat/replacement.py): M9",
}
# The packages whose every module authors something a player owns.
SCRIPTS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OWNED_PACKAGES = ("graphics_menu", "combat/weapon_component", "clothing", "loot")
CATALOG_NAME = "FN_GET_PLAYER_PAWN"


def scan_pawn_reads():
    """``(player_zero, owning)``: where a Blueprint a player owns calls
    GetPlayerPawn, and where a HUD asks for its owning pawn, each a list of
    "Blueprint.Graph"."""
    player_zero, owning = [], []
    for package in sorted({*_packages(), *ALSO}):
        bp = unreal.load_asset(package)
        if not bp or not BEL.generated_class(bp) or not _is_a(bp, OWNED):
            continue
        name = package.rsplit("/", 1)[-1]
        for graph in sorted(str(g) for g in BEL.list_graph_names(bp)):
            ed = BGE.get_graph_editor_by_name(bp, graph)
            if not ed:
                continue
            for n in ed.list_all_nodes():
                title = _bare(n)
                if title == GET_PAWN:
                    player_zero.append(f"{name}.{graph}")
                elif title == OWN_PAWN:
                    owning.append(f"{name}.{graph}")
    return player_zero, owning


def scan_sources():
    """The modules of ``OWNED_PACKAGES`` that name the catalog's GetPlayerPawn."""
    found = []
    for package in OWNED_PACKAGES:
        for root, _dirs, files in os.walk(os.path.join(SCRIPTS, package)):
            for f in sorted(files):
                if not f.endswith(".py"):
                    continue
                path = os.path.join(root, f)
                with open(path, encoding="utf-8") as fh:
                    if CATALOG_NAME in fh.read():
                        found.append(os.path.relpath(path, SCRIPTS))
    return sorted(found)


def check_no_player_zero_pawn(check):
    player_zero, owning = scan_pawn_reads()
    homes = {w.split(".")[0] for w in player_zero}
    wrong = sorted(w for w in set(player_zero) if w.split(".")[0] not in NOT_THE_PLAYERS)
    check("nothing a player owns reads player 0's pawn: no GetPlayerPawn in a "
          "HUD, a widget, a component or an animation graph (the HUD asks for "
          "its owning pawn, a component for its owner)",
          not wrong, ", ".join(wrong) or f"{len(owning)} owning-pawn reads")
    # The scan has to be seeing both nodes for "none" to mean anything.
    check("the scan finds the pawn reads where they are: the HUD's of its "
          "owning pawn, and the one left for M9 (the health component's, for "
          "a wanderer's replacement)",
          {w.split(".")[0] for w in owning} == {"BP_GraphicsMenuHUD"}
          and len(owning) >= 10 and homes == set(NOT_THE_PLAYERS),
          f"owning {len(owning)} in {sorted({w.split('.')[0] for w in owning})}; "
          f"player 0 in {sorted(homes)}")
    named = scan_sources()
    check(f"no builder of what a player owns names {CATALOG_NAME}: "
          f"{', '.join(OWNED_PACKAGES)}", not named, ", ".join(named))
