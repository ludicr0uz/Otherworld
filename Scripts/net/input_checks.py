"""The verifiers' check for whose keys a graph reads: the local player's.

A key is polled on a PlayerController, and which one is the whole question:

    a HUD          its owning controller (the engine makes a HUD only for a
                   local player, and none on a dedicated server)
    a component    LocalPC, this machine's controller of its owner, which the
                   local gate (combat/weapon_component/local.py) wrote this
                   frame; none on the server or on another player's client

Nothing else polls, and nothing asks for a controller or a camera by player
index: GetPlayerController(0) is the local player on a client whatever
character the graph belongs to, and the first joiner on a server.

    check_local_input   the rule, over every Blueprint of the game (the menu
                        verifier: the HUD is built last)
"""

import unreal

from combat.paths import ABP_PATH
from combat.weapon_component import vars as WV
from net.state_checks import _bare, _is_a, _packages
from uebp.nodes import system

BEL = unreal.BlueprintEditorLibrary
BGE = unreal.BlueprintGraphEditor
PIN = unreal.BlueprintGraphPinLibrary

POLLS = ("WasInputKeyJustPressed", "IsInputKeyDown", "WasInputKeyJustReleased",
         "GetInputKeyTimeDown", "GetInputAnalogKeyState")
BY_INDEX = ("GetPlayerController", "GetPlayerCameraManager", "GetPlayerCharacter")
HUD_PC = "GetOwningPlayerController"
LOCAL_PC = "Get" + WV.LocalPC
IS_LOCAL = "IsLocalController"
COMPONENT = "BP_WeaponComponent"
GONE = ("FN_GET_PC", "FN_GET_CAM")
ALSO = (ABP_PATH,)
# Stock template content the game never shows: the touch screen's thumbsticks.
STOCK = ("/Game/Input/",)
INDEX_PIN = "PlayerIndex"


def _source(n):
    """The title of the node a poll's self pin is fed by, or ""."""
    pin = BEL.find_input_pin(n, "self")
    fed = PIN.list_connected_pins(pin) if pin else []
    return _bare(PIN.get_owning_node(fed[0])) if fed else ""


def _by_index(n):
    """A variable node reading a controller's PlayerCameraManager has the
    function's title: the function is the one with the index pin."""
    # By name: find_input_pin hands back a handle for a pin that is not there.
    return INDEX_PIN in {str(PIN.get_pin_name(p)) for p in BEL.list_input_pins(n)}


def scan_input():
    """``(by_index, polls, gates)``: where a Blueprint asks for a controller
    or camera by player index; every key poll as (Blueprint, is a HUD, what
    feeds its self); and the Blueprints holding an IsLocalController."""
    by_index, polls, gates = [], [], set()
    for package in sorted({*_packages(), *ALSO}):
        bp = unreal.load_asset(package)
        if not bp or not BEL.generated_class(bp) or package.startswith(STOCK):
            continue
        name = package.rsplit("/", 1)[-1]
        hud = _is_a(bp, ("HUD",))
        for graph in sorted(str(g) for g in BEL.list_graph_names(bp)):
            ed = BGE.get_graph_editor_by_name(bp, graph)
            if not ed:
                continue
            for n in ed.list_all_nodes():
                title = _bare(n)
                if title in BY_INDEX and _by_index(n):
                    by_index.append(f"{name}.{graph}")
                elif title in POLLS:
                    polls.append((name, hud, _source(n)))
                elif title == IS_LOCAL:
                    gates.add(name)
    return by_index, polls, gates


def check_local_input(check):
    by_index, polls, gates = scan_input()
    check("no graph asks for a controller or a camera by player index (no "
          "GetPlayerController, GetPlayerCameraManager or GetPlayerCharacter "
          "in any Blueprint of the game), and the node catalog no longer has them",
          not by_index and not any(hasattr(system, g) for g in GONE),
          ", ".join(sorted(set(by_index))))
    stray = sorted({f"{name} (on {src or 'nothing'})" for name, hud, src in polls
                    if not ((hud and src == HUD_PC)
                            or (name == COMPONENT and src == LOCAL_PC))})
    on_hud = sum(1 for _n, hud, _s in polls if hud)
    on_comp = sum(1 for name, _h, _s in polls if name == COMPONENT)
    check("every key poll is the local player's: a HUD's on its owning "
          "controller, the weapon component's on LocalPC, and no other "
          "Blueprint polls a key",
          not stray and on_hud >= 20 and on_comp >= 15,
          ", ".join(stray) or f"{on_hud} on the HUD, {on_comp} on the component")
    check("the weapon component's Tick asks whether its owner's controller "
          "is this machine's (the local gate, IsLocalController)",
          COMPONENT in gates, f"asked in {sorted(gates)}")
