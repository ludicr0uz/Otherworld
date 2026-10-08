"""BP_Campfire (survival/campfire.py): the model on the ground, the glow, the
burn time, and the Tick that warms a player near it; and the weapon
component's CampfireClass, which build_survival.py points at it. The strike
that spawns it is verify_weapons' (combat/verify/light.py)."""

import unreal

from combat.light_tuning import CAMPFIRE_CLASS_VAR
from combat.paths import WEAPON_COMP_BP_PATH
from combat.verify.common import (
    BEL, PIN, by_pins, cdo, check, component_template, graph, load, num_pin,
)
from net import relevancy
from net.players_consts import LIVING_TITLE
from net.relevancy_consts import CAMPFIRE as CAMPFIRE_ROW
from uebp import net
from Sound.sound_items import CAMPFIRE, CRACKLE_COMP
from survival.campfire import (
    CAMPFIRE_MESH, CAMPFIRE_SCALE, MAX_TEMPERATURE_VAR, TEMPERATURE_VAR, WARM_RADIUS_VAR,
    WARM_RATE_VAR,
)
from survival.paths import CAMPFIRE_BP_PATH
from survival.tuning import (
    CAMPFIRE_BURN_S, CAMPFIRE_WARM_PER_S, CAMPFIRE_WARM_RADIUS_CM,
)

# A campfire, across (cm).
CAMPFIRE_WIDTH_CM = (60.0, 120.0)


def _title(n):
    return str(BEL.get_node_title(n)).replace("\n", " ")


LIVING = LIVING_TITLE.lower()


def _squash(n):
    return _title(n).replace(" ", "").lower()


def _feeders(node, pin):
    p = BEL.find_input_pin(node, pin)
    return [PIN.get_owning_node(q) for q in PIN.list_connected_pins(p)] if p else []


def _feeds(node, pin):
    """Every node feeding this pin through data links, as titles."""
    seen, stack = [], _feeders(node, pin)
    while stack:
        n = stack.pop()
        if n in seen:
            continue
        seen.append(n)
        for p in BEL.list_input_pins(n):
            if str(PIN.get_pin_name(p)) != "execute":
                stack.extend(PIN.get_owning_node(q) for q in PIN.list_connected_pins(p))
    return {_squash(n) for n in seen}


def check_model(bp):
    fire = component_template(bp, "Fire")
    mesh = fire.get_editor_property("static_mesh") if fire else None
    check("...drawn by Quaternius's Survival Pack bonfire (SM_Bonfire_Fire)",
          mesh is not None and mesh == load(CAMPFIRE_MESH), str(mesh))
    if mesh is None:
        return
    box = mesh.get_bounding_box()
    scale = fire.get_editor_property("relative_scale3d")
    at = fire.get_editor_property("relative_location")
    width = (box.max.x - box.min.x) * scale.x
    check(f"...at {CAMPFIRE_SCALE}, a fire {CAMPFIRE_WIDTH_CM[0]:.0f}-"
          f"{CAMPFIRE_WIDTH_CM[1]:.0f} cm across",
          abs(scale.x - CAMPFIRE_SCALE) < 1e-4 and scale.x == scale.y == scale.z
          and CAMPFIRE_WIDTH_CM[0] < width < CAMPFIRE_WIDTH_CM[1], f"{width:.1f} cm")
    middle = [(getattr(box.min, a) + getattr(box.max, a)) / 2.0 * getattr(scale, a)
              + getattr(at, a) for a in "xy"]
    bottom = box.min.z * scale.z + at.z
    check("...standing on the ground where it is spawned, centred on that point",
          abs(bottom) < 0.1 and all(abs(m) < 0.5 for m in middle),
          f"bottom {bottom:.2f}, middle {[round(m, 2) for m in middle]}")
    check("...and blocking nothing: the player walks through it",
          str(fire.get_collision_profile_name()) == "NoCollision",
          str(fire.get_collision_profile_name()))
    glow = component_template(bp, "Glow")
    check("...with a point light in the flames, casting no shadows",
          isinstance(glow, unreal.PointLightComponent)
          and glow.get_editor_property("intensity") > 0.0
          and glow.get_editor_property("relative_location").z > 0.0
          and not glow.get_editor_property("cast_shadows"), str(glow))
    # The fire's sound is a component of the fire, so it ends with it: a
    # looping wave played at a location instead would crackle on over the ash.
    crackle = component_template(bp, CRACKLE_COMP)
    sound = crackle.get_editor_property("sound") if crackle else None
    check("...and its own sound: a looping, placed wave on an audio component "
          "that starts with the fire",
          isinstance(crackle, unreal.AudioComponent) and sound is not None
          and sound.get_path_name().split(".")[0] == CAMPFIRE.paths[0]
          and sound.get_editor_property("looping")
          and sound.get_editor_property("attenuation_settings") is not None
          and crackle.get_editor_property("auto_activate"), str(sound))


def _owned(node, event):
    """``node`` runs off the true arm of a Branch on HasAuthority that the
    ``event`` runs: the server's copy alone (and single player's)."""
    gates = _feeders(node, "execute")
    return (len(gates) == 1 and _title(gates[0]) == "Branch"
            and node in [PIN.get_owning_node(q) for q in
                         PIN.list_connected_pins(BEL.find_then_pin(gates[0]))]
            and any("hasauthority" in _squash(f) for f in _feeders(gates[0], "Condition"))
            and any(event in _squash(f) for f in _feeders(gates[0], "execute")))


def check_replicates(bp):
    check("it replicates: the fire the server lit is sent to every client (M25)",
          net.replicates(bp), str(net.replicates(bp)))
    check(f"...within {CAMPFIRE_ROW.cull_m:g} m of them, at {CAMPFIRE_ROW.update_hz:g}/"
          f"{CAMPFIRE_ROW.min_hz:g} Hz (net/relevancy_consts.py, A2)",
          relevancy.matches(bp, CAMPFIRE_ROW), str(relevancy.read(bp)))
    dormancy = cdo(bp).get_editor_property("net_dormancy")
    check("...and dormant from its spawn: sent once, its channel closed, its destroy "
          "told", dormancy == unreal.NetDormancy.DORM_DORMANT_ALL, str(dormancy))


def check_warmth(bp):
    d = cdo(bp)
    radius, rate = d.get_editor_property(WARM_RADIUS_VAR), d.get_editor_property(WARM_RATE_VAR)
    check(f"it warms {CAMPFIRE_WARM_PER_S:g} a second within "
          f"{CAMPFIRE_WARM_RADIUS_CM:.0f} cm (floats, as tuned)",
          isinstance(radius, float) and isinstance(rate, float)
          and abs(radius - CAMPFIRE_WARM_RADIUS_CM) < 1e-6
          and abs(rate - CAMPFIRE_WARM_PER_S) < 1e-6 and rate > 0.0 and radius > 0.0,
          f"{rate} within {radius}")
    nodes = graph(bp).list_all_nodes()
    lives = by_pins(nodes, "InLifespan")
    check(f"one piece of wood burns {CAMPFIRE_BURN_S:.0f} s: BeginPlay sets the life "
          "span, with authority (the server's clock; its destroy reaches every copy)",
          len(lives) == 1 and num_pin(lives[0], "InLifespan") == CAMPFIRE_BURN_S
          and _owned(lives[0], "beginplay"),
          str([num_pin(n, "InLifespan") for n in lives]))
    writes = [n for n in nodes if _title(n) == f"Set {TEMPERATURE_VAR}"]
    check("Tick writes the Temperature in one place", len(writes) == 1, str(len(writes)))
    if len(writes) != 1:
        return
    write = writes[0]
    value = _feeds(write, TEMPERATURE_VAR)
    check("...Temperature + WarmPerSecond x DeltaSeconds, no higher than MaxTemperature",
          {f"get{TEMPERATURE_VAR.lower()}", f"get{WARM_RATE_VAR.lower()}",
           f"get{MAX_TEMPERATURE_VAR.lower()}", "min(float)"} <= value
          and any("tick" in v for v in value), str(sorted(value)))
    casts = _feeders(write, "execute")
    check("...on a living player's survival component (a cast: a pawn without "
          "one is not warmed)",
          len(casts) == 1 and "survivalcomponent" in _squash(casts[0])
          and {"foreachloop", LIVING} <= _feeds(casts[0], "Object"),
          str([_title(c) for c in casts]))
    nears = _feeders(casts[0], "execute") if len(casts) == 1 else []
    near = _feeds(nears[0], "Condition") if len(nears) == 1 else set()
    check("...only while that player is within WarmRadius of the fire",
          len(nears) == 1 and _title(nears[0]) == "Branch"
          and PIN.get_owning_node(PIN.list_connected_pins(
              BEL.find_then_pin(nears[0]))[0]) == casts[0]
          and {f"get{WARM_RADIUS_VAR.lower()}", "foreachloop"} <= near
          and any("distance" in v for v in near), str(sorted(near)))
    loops = _feeders(nears[0], "execute") if len(nears) == 1 else []
    asks = _feeders(loops[0], "Exec") if len(loops) == 1 else []
    check("...and that is every living player in turn, never player 0: the "
          "Branch is the body of a loop over LivingPlayers, asked once a Tick "
          "(net/players.py), with authority: Temperature is the server's",
          len(loops) == 1 and _squash(loops[0]) == "foreachloop"
          and len(asks) == 1 and _squash(asks[0]) == LIVING
          and _owned(asks[0], "tick")
          and not by_pins(nodes, "PlayerIndex"),
          str([_title(n) for n in loops + asks]))


def run():
    bp = load(CAMPFIRE_BP_PATH)
    check("BP_Campfire exists, an Actor", bp is not None
          and bp.get_blueprint_parent_class() == unreal.Actor.static_class())
    if bp is None:
        return
    check_model(bp)
    check_replicates(bp)
    check_warmth(bp)
    got = cdo(load(WEAPON_COMP_BP_PATH)).get_editor_property(CAMPFIRE_CLASS_VAR)
    check(f"BP_WeaponComponent.{CAMPFIRE_CLASS_VAR} points at BP_Campfire_C, so a "
          "strike of the matches lights one",
          got is not None and got.get_name() == "BP_Campfire_C", str(got))
