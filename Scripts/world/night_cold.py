"""BP_DayNightCycle's last Tick step: the night is cold. Every living
player's Temperature (BP_SurvivalComponent) falls while the sun is down.

    [Tick ...] --> for each living player's pawn (net/players.py)
               --> its SurvivalComponent (GetComponentByClass, cast)
               --> Temperature = max(Temperature
                       - NightTemperatureDropPerSecond * (1 - DayAmount) * dt, 0)

The rate is the cycle's NightTemperatureDropPerSecond (Instance Editable;
world_config.NIGHT_TEMPERATURE_DROP_PER_S, a WORLD SETTINGS row saved to
world_tuning.csv). It scales by how much night there is, 1 - DayAmount, so
the cold comes in through dusk and eases through dawn rather than switching
at sunset: world_config.sun_state()'s night_cold_per_s is the same sum.

The cycle writes the survival component, not the other way round, because
the cold is the world's and build_survival.py runs before build_day_night.py
(the cast node exists only for a loaded class). A level without a cycle, or a
pawn without the component, simply has no cold.

The loop's body is the end of the Tick chain: nothing is authored after it.
"""

import unreal

from net.players import each_living_player
from uebp.graph import BEL, _connect, _loose_pin, _palette, _pin, out
from survival.paths import SURVIVAL_BP_PATH, SURVIVAL_CLASS_PATH
from world.day_night_blueprint import NIGHT_COLD_VAR
from world.day_night_graph import _call, _get, _map
from uebp.nodes.actor import FN_GET_COMP
from uebp.nodes.math import FN_MAX_FF, FN_MUL_FF, FN_SUB_FF
from uebp.nodes.palette import NODE_CAST_SURVIVAL
from world import day_night_vars as DV

TEMPERATURE_VAR = "Temperature"


def author_night_cold(ed, tick, chain):
    """Extend the Tick chain with the cold (see the module docstring)."""
    pawn, each, _done, everyone = each_living_player(ed, [chain.then])
    chain.then = each

    comp = _call(ed, FN_GET_COMP, self=pawn)
    _pin(comp, "ComponentClass").set_pin_value(SURVIVAL_CLASS_PATH)
    if not unreal.load_asset(SURVIVAL_BP_PATH):   # the cast exists only for a loaded class
        raise RuntimeError(f"{SURVIVAL_BP_PATH} is missing -- run build_survival.py first")
    cast = chain.step(_palette(ed, NODE_CAST_SURVIVAL))
    if not BEL.list_input_pins(cast):
        raise RuntimeError("no cast node for BP_SurvivalComponent")
    _connect(out(comp), _pin(cast, "Object"))
    survival = _loose_pin(cast, "AsBPSurvivalComponent", is_input=False)

    night = _map(ed, _get(ed, DV.DayAmount), 0.0, 1.0, 1.0, 0.0)
    rate = out(_call(ed, FN_MUL_FF, A=_get(ed, NIGHT_COLD_VAR), B=night))
    step = out(_call(ed, FN_MUL_FF, A=rate, B=out(tick, "DeltaSeconds")))
    now = ed.add_get_member_variable_node(TEMPERATURE_VAR, SURVIVAL_CLASS_PATH)
    _connect(survival, _pin(now, "self"))
    less = out(_call(ed, FN_SUB_FF, A=out(now, TEMPERATURE_VAR), B=step))
    floor = out(_call(ed, FN_MAX_FF, A=less, B=0.0))
    write = chain.step(ed.add_set_member_variable_node(TEMPERATURE_VAR, SURVIVAL_CLASS_PATH))
    _connect(survival, _pin(write, "self"))
    _connect(floor, _pin(write, TEMPERATURE_VAR))
    ed.add_comment_to_nodes(
        "The night is cold: every living player's Temperature falls by "
        "NightTemperatureDropPerSecond x (1 - DayAmount), down to 0.",
        everyone + [cast, write])
