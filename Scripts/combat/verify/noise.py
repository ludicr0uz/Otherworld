"""verify.noise -- the world's noise list (the native library the graphs
call), each gun's ShotVolume, and the two things that add a noise to it: the
shot and the player's footsteps. The list itself (one entry a maker, the
stale-or-louder guard, the server alone) is C++ and is proved in a running
game: probes/probe_net_noise.py.
"""

import math

import unreal

from combat.footsteps import FOOTSTEP_BP_PATH
from combat import game_mode_vars as GV
from combat.tuning import COMBAT, SHOT_VOLUME_CM
from combat.weapon_specs import _weapon_specs
from combat.verify.common import (
    BEL, PIN, cdo, check, graph, load, num_pin, pin_value, titled,
)
from combat.verify.fixtures import gm, wg
from forest_generator.npc_placement import NPC_REPATH_SECONDS

MAKE_TITLE = "MakeNoise"


def _feeders(node, pin_name):
    """Titles of the nodes wired into ``node``'s input pin ``pin_name``."""
    pin = BEL.find_input_pin(node, pin_name)
    return {str(BEL.get_node_title(PIN.get_owning_node(q))).replace("\n", " ")
            for q in PIN.list_connected_pins(pin)}


def check_noise_record():
    check("the noise list's library is compiled in (Source/Otherworld: OtherworldNoise.h)",
          all(hasattr(getattr(unreal, "OtherworldNoiseLibrary", None), f)
              for f in ("make_noise", "hear_noise", "noises_held")))
    # The one record the list replaced (M28): a GameMode built before it loses it.
    names = {str(v) for v in BEL.list_member_variable_names(gm, False)}
    check("the GameMode no longer holds a noise record: the noises are the world's list",
          not names & set(GV.REMOVED), f"{sorted(names & set(GV.REMOVED))}")
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
              abs(got - spec["shot_volume"]) < 1e-3, f"{got}")
    # The ordering holds the built volumes: gun_tuning.csv's over SHOT_VOLUME_CM.
    v = {s["display"]: s["shot_volume"] for s in specs}
    check("the sniper is the loudest gun",
          v["Sniper"] > max(x for k, x in v.items() if k != "Sniper"))
    check("the rifle and shotgun sit between the sniper and the SMG",
          v["Sniper"] > v["Rifle"] > v["SMG"] and v["Sniper"] > v["Shotgun"] > v["SMG"])
    check("the SMG is quieter than both, and the pistol is the quietest",
          v["SMG"] > v["Pistol"] and v["Pistol"] == min(v.values()))


def _check_writer(label, nodes, maker):
    """What every noise write shares: one MakeNoise, its maker and the hold.
    Returns the node, or None."""
    makes = titled(nodes, MAKE_TITLE)
    check(f"{label}: one noise added to the world's list", len(makes) == 1, f"{len(makes)}")
    if len(makes) != 1:
        return None
    make = makes[0]
    check(f"{label}: only its maker's stale or quieter noise is replaced "
          f"(held {COMBAT.noise_hold_s} s)",
          num_pin(make, "HoldSeconds") == COMBAT.noise_hold_s, pin_value(make, "HoldSeconds"))
    check(f"{label}: the noise is its maker's ({maker})",
          _feeders(make, "Maker") == {maker}, f"{_feeders(make, 'Maker')}")
    check(f"{label}: it has a place", len(_feeders(make, "Location")) == 1,
          f"{_feeders(make, 'Location')}")
    return make


def check_shot_noise():
    make = _check_writer("the shot", wg, "GetOwner")
    if make is None:
        return
    check("the shot's reach is the held weapon's ShotVolume",
          _feeders(make, "Reach") == {"Get ShotVolume"}, f"{_feeders(make, 'Reach')}")
    scale = [n for n in titled(wg, "float * float")
             if num_pin(n, "B") == COMBAT.shot_noise_cone_range_scale
             and _feeders(n, "A") == {"Get ShotVolume"}]
    check(f"down the barrel it carries {COMBAT.shot_noise_cone_range_scale}x further",
          len(scale) == 1 and _feeders(make, "ConeReach") == {"float * float"},
          f"{len(scale)} scale node(s)")
    want = math.cos(math.radians(COMBAT.shot_noise_cone_half_angle_deg))
    got = num_pin(make, "ConeCos")
    check(f"the cone is {COMBAT.shot_noise_cone_half_angle_deg:.0f} degrees either side",
          got is not None and abs(got - want) < 1e-4, pin_value(make, "ConeCos"))
    # The same Normalize the pellet cone is built around, not a second copy of
    # the muzzle -> AimPoint line that could drift from it.
    pellet_dirs = {PIN.get_owning_node(q) for n in titled(wg, "RandomUnitVectorInConeInRadians")
                   for q in PIN.list_connected_pins(BEL.find_input_pin(n, "ConeDir"))}
    shot_dirs = {PIN.get_owning_node(q)
                 for q in PIN.list_connected_pins(BEL.find_input_pin(make, "Direction"))}
    # The pellets now fly around ShotDirection, which the shot's cloud draw
    # centres on that same Normalize.
    check("the cone points down the line the shot was drawn around",
          bool(shot_dirs) and shot_dirs <= pellet_dirs,
          f"{len(shot_dirs)} source(s), shared with the shot's cone: "
          f"{shot_dirs <= pellet_dirs}")


def check_footstep_noise():
    fg = graph(load(FOOTSTEP_BP_PATH)).list_all_nodes()
    make = _check_writer("a footstep", fg, "Cast To Character")
    gate = [n for n in titled(fg, "Branch")
            if _feeders(n, "Condition") == {"IsPlayerControlled"}]
    check("only the player's footsteps are a noise -- the wanderers share the component",
          len(gate) == 1, f"{len(gate)} IsPlayerControlled gate(s)")
    if make is None:
        return
    per_speed = COMBAT.footstep_noise_range_cm / COMBAT.footstep_noise_reference_speed_cms
    reach = [n for n in titled(fg, "float * float") if num_pin(n, "B") == per_speed]
    check(f"a step carries {COMBAT.footstep_noise_range_cm / 100:.0f} m at "
          f"{COMBAT.footstep_noise_reference_speed_cms:.0f} cm/s, in proportion to speed",
          len(reach) == 1 and _feeders(make, "Reach") == {"float * float"},
          f"{len(reach)} x{per_speed} node(s)")
    # A literal equal to its pin's default is not saved: "" once loaded from disk.
    check("a footstep has no cone -- it is heard the same all round",
          not _feeders(make, "ConeReach") and (num_pin(make, "ConeReach") or 0.0) == 0.0,
          pin_value(make, "ConeReach"))


def run():
    check_noise_record()
    check_shot_volumes()
    check_shot_noise()
    check_footstep_noise()
