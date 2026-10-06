"""verify.movement -- the player's movement component (combat/player_move.py):
the character is a child of the native class that has the C++ component, the
component holds the tuning tables' numbers, and the graph hands it the aim.

What the component does with a key (the sprint's latch and cone, the speeds,
the stamina) is C++ and is checked in the running game, on a client and the
server at once, with lag: probes/probe_net_move_states.py.
"""

import unreal

from combat.paths import MOVE_CHARACTER_CLASS_PATH
from combat.player_move import MOVE_NUMBERS
from combat.verify.common import BEL, PIN, cdo, check, has_in_pin
from combat.verify.fixtures import char, w, wg
from combat.weapon_component.ads import AIM_FORCED_VAR


def _title(n):
    return str(BEL.get_node_title(n)).replace("\n", " ")


def _feeders(node, pin):
    return [PIN.get_owning_node(q)
            for q in PIN.list_connected_pins(BEL.find_input_pin(node, pin))]


def check_player_parent():
    parent = BEL.get_blueprint_parent_class(char)
    check("the player's Blueprint is a child of OtherworldCharacter, the native "
          "class that chooses the movement component",
          parent is not None and parent.get_path_name() == MOVE_CHARACTER_CLASS_PATH,
          parent.get_path_name() if parent else "none")
    movement = cdo(char).get_editor_property("character_movement")
    check("...so its movement component is the C++ one that predicts sprint, "
          "prone and the aim-walk",
          isinstance(movement, unreal.OtherworldCharacterMovement),
          type(movement).__name__)
    return movement


def check_move_numbers(movement):
    for name, want in MOVE_NUMBERS.items():
        got = movement.get_editor_property(name)
        check(f"the movement component's {name} is the tuning table's {want:g}",
              isinstance(got, float) and abs(got - want) < 1e-4, repr(got))


def check_aim_walk():
    tells = [n for n in wg if _title(n).replace(" ", "") == "SetAimWalk"]
    fed = [_title(f) for n in tells for f in _feeders(n, "bAiming")]
    runs = [bool(PIN.list_connected_pins(BEL.find_input_pin(n, "execute")))
            for n in tells]
    check("the aim is handed to the movement component once a frame, on the "
          "exec chain: Aiming, which is already false sprinting or unarmed",
          len(tells) == 1 and fed == ["Get Aiming"] and all(runs), f"{fed}, {runs}")
    forced = w.get_editor_property(AIM_FORCED_VAR)
    check(f"{AIM_FORCED_VAR}, a probe's hand on the shoulder key, starts False",
          forced is False, repr(forced))
    aims = [n for n in wg if has_in_pin(n, "Aiming") and _title(n) == "Set Aiming"]
    check("...and Aiming is still written in one place", len(aims) == 1, str(len(aims)))


def run():
    movement = check_player_parent()
    if isinstance(movement, unreal.OtherworldCharacterMovement):
        check_move_numbers(movement)
    check_aim_walk()
