"""verify.noise -- the GameMode's noise record, each gun's ShotVolume, and the
two things that write the record: the shot and the player's footsteps.
"""

import math

import unreal

from combat.footsteps import FOOTSTEP_BP_PATH
from combat.game_state import (
    NOISE_CONE_COS_VAR, NOISE_CONE_RANGE_VAR, NOISE_DIRECTION_VAR,
    NOISE_FLOAT_VARS, NOISE_LOCATION_VAR, NOISE_RANGE_VAR, NOISE_TIME_VAR,
    NOISE_VECTOR_VARS,
)
from combat.tuning import COMBAT, SHOT_VOLUME_CM
from combat.weapon_specs import _weapon_specs
from combat.verify.common import (
    BEL, PIN, cdo, check, graph, load, num_pin, pin_value, titled,
)
from combat.verify.fixtures import gm, wg
from forest_generator.npc_placement import NPC_REPATH_SECONDS


def _feeders(node, pin_name):
    """Titles of the nodes wired into ``node``'s input pin ``pin_name``."""
    pin = BEL.find_input_pin(node, pin_name)
    return {str(BEL.get_node_title(PIN.get_owning_node(q))).replace("\n", " ")
            for q in PIN.list_connected_pins(pin)}


def _sets(nodes, var):
    """Set nodes for ``var`` (on any class)."""
    return [n for n in nodes if str(BEL.get_node_title(n)) == f"Set {var}"]


def check_noise_record():
    mode = cdo(gm)
    for name in NOISE_FLOAT_VARS:
        value = mode.get_editor_property(name)
        check(f"the GameMode's {name} is a float", isinstance(value, float),
              type(value).__name__)
    for name in NOISE_VECTOR_VARS:
        value = mode.get_editor_property(name)
        check(f"the GameMode's {name} is a vector", isinstance(value, unreal.Vector),
              type(value).__name__)
    # A noise has to survive one NPC heartbeat, or a footstep right after a
    # gunshot erases the shot before half the pack has checked for it.
    check("a noise is held longer than one NPC heartbeat",
          COMBAT.noise_hold_s > NPC_REPATH_SECONDS,
          f"{COMBAT.noise_hold_s} s held vs a {NPC_REPATH_SECONDS} s heartbeat")


def check_shot_volumes():
    specs = _weapon_specs()
    check("every weapon has a shot volume in the combat config",
          {s["display"] for s in specs} == set(SHOT_VOLUME_CM),
          f"{sorted(SHOT_VOLUME_CM)}")
    for spec in specs:
        got = cdo(load(spec["path"])).get_editor_property("ShotVolume")
        check(f"{spec['display']} is heard out to {spec['shot_volume'] / 100:.0f} m",
              abs(got - SHOT_VOLUME_CM[spec["display"]]) < 1e-3, f"{got}")
    v = SHOT_VOLUME_CM
    check("the sniper is the loudest gun",
          v["Sniper"] > max(x for k, x in v.items() if k != "Sniper"))
    check("the rifle and shotgun sit between the sniper and the SMG",
          v["Sniper"] > v["Rifle"] > v["SMG"] and v["Sniper"] > v["Shotgun"] > v["SMG"])
    check("the SMG is quieter than both, and the pistol is the quietest",
          v["SMG"] > v["Pistol"] and v["Pistol"] == min(v.values()))


def _check_writer(label, nodes):
    """What every noise write shares: the stale-or-louder guard, all six fields."""
    holds = [n for n in titled(nodes, "float >= float")
             if num_pin(n, "B") == COMBAT.noise_hold_s]
    guards = [n for n in titled(nodes, "Branch")
              if _feeders(n, "Condition") == {"OR Boolean"}
              and any(str(BEL.get_node_title(PIN.get_owning_node(q))) == f"Set {NOISE_TIME_VAR}"
                      for q in BEL.find_then_pin(n).list_connected_pins())]
    check(f"{label}: only a stale or quieter noise is replaced",
          len(holds) == 1 and len(guards) == 1,
          f"{len(holds)} hold comparison(s), {len(guards)} stale-or-louder branch(es)")
    for var in (NOISE_TIME_VAR, NOISE_LOCATION_VAR, NOISE_RANGE_VAR,
                NOISE_CONE_RANGE_VAR, NOISE_CONE_COS_VAR):
        check(f"{label}: writes {var}", len(_sets(nodes, var)) == 1,
              f"{len(_sets(nodes, var))}")


def check_shot_noise():
    _check_writer("the shot", wg)
    ranges = _sets(wg, NOISE_RANGE_VAR)
    check("the shot's reach is the held weapon's ShotVolume",
          bool(ranges) and _feeders(ranges[0], NOISE_RANGE_VAR) == {"Get ShotVolume"},
          f"{_feeders(ranges[0], NOISE_RANGE_VAR) if ranges else None}")
    cone = _sets(wg, NOISE_CONE_RANGE_VAR)
    scale = [n for n in titled(wg, "float * float")
             if num_pin(n, "B") == COMBAT.shot_noise_cone_range_scale
             and _feeders(n, "A") == {"Get ShotVolume"}]
    check(f"down the barrel it carries {COMBAT.shot_noise_cone_range_scale}x further",
          len(scale) == 1 and bool(cone)
          and _feeders(cone[0], NOISE_CONE_RANGE_VAR) == {"float * float"},
          f"{len(scale)} scale node(s)")
    cos = _sets(wg, NOISE_CONE_COS_VAR)
    want = math.cos(math.radians(COMBAT.shot_noise_cone_half_angle_deg))
    check(f"the cone is {COMBAT.shot_noise_cone_half_angle_deg:.0f} degrees either side",
          bool(cos) and abs(float(pin_value(cos[0], NOISE_CONE_COS_VAR)) - want) < 1e-4,
          pin_value(cos[0], NOISE_CONE_COS_VAR) if cos else "missing")
    # The same Normalize the pellet cone is built around, not a second copy of
    # the muzzle -> AimPoint line that could drift from it.
    heading = _sets(wg, NOISE_DIRECTION_VAR)
    pellet_dirs = {PIN.get_owning_node(q) for n in titled(wg, "RandomUnitVectorInConeInRadians")
                   for q in PIN.list_connected_pins(BEL.find_input_pin(n, "ConeDir"))}
    shot_dirs = {PIN.get_owning_node(q) for n in heading
                 for q in PIN.list_connected_pins(BEL.find_input_pin(n, NOISE_DIRECTION_VAR))}
    check("the cone points down the line the pellets flew",
          len(heading) == 1 and bool(shot_dirs) and shot_dirs == pellet_dirs,
          f"{len(shot_dirs)} source(s), shared with the pellets: {shot_dirs == pellet_dirs}")


def check_footstep_noise():
    fg = graph(load(FOOTSTEP_BP_PATH)).list_all_nodes()
    _check_writer("a footstep", fg)
    gate = [n for n in titled(fg, "Branch")
            if _feeders(n, "Condition") == {"IsPlayerControlled"}]
    check("only the player's footsteps are a noise -- the wanderers share the component",
          len(gate) == 1, f"{len(gate)} IsPlayerControlled gate(s)")
    per_speed = COMBAT.footstep_noise_range_cm / COMBAT.footstep_noise_reference_speed_cms
    reach = [n for n in titled(fg, "float * float") if num_pin(n, "B") == per_speed]
    ranges = _sets(fg, NOISE_RANGE_VAR)
    check(f"a step carries {COMBAT.footstep_noise_range_cm / 100:.0f} m at "
          f"{COMBAT.footstep_noise_reference_speed_cms:.0f} cm/s, in proportion to speed",
          len(reach) == 1 and bool(ranges)
          and _feeders(ranges[0], NOISE_RANGE_VAR) == {"float * float"},
          f"{len(reach)} x{per_speed} node(s)")
    cone = _sets(fg, NOISE_CONE_RANGE_VAR)
    check("a footstep has no cone -- it is heard the same all round",
          bool(cone) and num_pin(cone[0], NOISE_CONE_RANGE_VAR) == 0.0,
          pin_value(cone[0], NOISE_CONE_RANGE_VAR) if cone else "missing")


def run():
    check_noise_record()
    check_shot_volumes()
    check_shot_noise()
    check_footstep_noise()
