"""verify.drops -- BP_AmmoPickup and the 10% weapon drop.
"""

from combat.game_state import DAMAGED_BY_PLAYER_VAR
from combat.paths import AMMO_BP_PATH, HEALTH_BP_PATH
from combat.tuning import (
    AMMO_DROP_SHELLS, AMMO_PICKUP_LIFETIME, AMMO_PICKUP_RADIUS,
    GUN_DROP_CHANCE,
)
from combat.weapon_specs import DROP_DISPLAYS, _weapon_specs
from combat.verify.fixtures import ag, health_bp, hg
from combat.verify.common import (
    BEL, PIN, by_pins, cdo, check, components, graph, in_pins, load, num_pin,
    out_pins, pin_value,
)


# ─── BP_AmmoPickup ───────────────────────────────────────────────────────────

def check_ammo_pickup():
    ammo_bp = load(AMMO_BP_PATH)
    ammo = cdo(ammo_bp)

    check(f"a drop carries {AMMO_DROP_SHELLS} shells",
          ammo.get_editor_property("Shells") == AMMO_DROP_SHELLS,
          str(ammo.get_editor_property("Shells")))
    check("it starts uncollected", ammo.get_editor_property("Credited") is False)
    check("it looks like what it gives you -- one mesh per shell",
          len({n for n in components(ammo_bp) if n.startswith("Shell")})
          == AMMO_DROP_SHELLS,
          str(sorted({n for n in components(ammo_bp) if n.startswith("Shell")})))
    # Measured HERE, on at most a handful of actors, rather than by sweeping the
    # level from the weapon component's Tick every frame whether any exist or not.
    check("the pickup measures its own distance to the player",
          bool(by_pins(ag, "V1", "V2")) and bool(by_pins(ag, "PlayerIndex")),
          f"{len(by_pins(ag, 'V1', 'V2'))} distance node(s)")
    check(f"...and is taken by walking within {AMMO_PICKUP_RADIUS:.0f} cm of it",
          any(pin_value(n, "B") == str(AMMO_PICKUP_RADIUS)
              for n in ag if "B" in in_pins(n)),
          f"{AMMO_PICKUP_RADIUS:.0f} cm")
    check("no key is involved -- it is not another thing to press E on",
          not by_pins(ag, "Key"), f"{len(by_pins(ag, 'Key'))} key polls")
    check("it credits the weapon's own Reserve, not a counter on the player",
          any(str(BEL.get_node_title(n)).replace("\n", " ") == "Set Reserve"
              for n in ag))
    check("Credited is written on both paths -- the held weapon and the fallback loop",
          len([n for n in ag
               if str(BEL.get_node_title(n)).replace("\n", " ") == "Set Credited"]) == 2,
          f"{len([n for n in ag if str(BEL.get_node_title(n)).replace(chr(10), ' ') == 'Set Credited'])} writes")
    check("...and it only vanishes once something has actually taken it",
          len([n for n in ag if "Credited" in out_pins(n)]) == 2,
          f"{len([n for n in ag if 'Credited' in out_pins(n)])} reads of Credited")
    # With four of the five weapons using ammunition, "the first one in the
    # inventory" means the shotgun in slot 0 forever -- so a player clearing the
    # forest with the sniper would watch a gun they are not holding fill up.
    check("the shells go to the weapon in the player's hands first",
          any("Held" in out_pins(n) for n in ag),
          "no read of the weapon component's Held on the pickup")
    held_reads = [n for n in ag if "Held" in out_pins(n)]
    if held_reads:
        # And that read has to be behind an IsValid gate rather than beside one:
        # UsesAmmo is a pure pull off Held, and pulling it while unarmed is an
        # Accessed None -- the trap this project has now hit four times.
        valids = [n for n in ag if "Object" in in_pins(n)
                  and "IsValid" in str(BEL.get_node_title(n))]
        check("...behind an IsValid gate, because reading UsesAmmo off None is an "
              "Accessed None", bool(valids), f"{len(valids)} IsValid node(s)")
    check("...with the inventory loop kept as the fallback for an unarmed player "
          "or one holding the pistol",
          bool(by_pins(ag, "Array")) or any("Inventory" in out_pins(n) for n in ag),
          "the ForEachLoop over Inventory is gone")


# ─── The 10% weapon drop ─────────────────────────────────────────────────────

def check_weapon_drop():
    drop_classes = list(cdo(health_bp).get_editor_property("DropClasses"))
    check(f"a kill can leave one of {len(DROP_DISPLAYS)} weapons",
          len(drop_classes) == len(DROP_DISPLAYS), str(len(drop_classes)))
    check("...and they are the three that are not in the starting loadout",
          [c.get_name() for c in drop_classes]
          == [f"{sp['path'].rsplit('/', 1)[-1]}_C" for sp in _weapon_specs()
              if sp["display"] in DROP_DISPLAYS],
          str([c.get_name() for c in drop_classes]))
    check(f"the drop rate is {GUN_DROP_CHANCE * 100:.0f}%",
          any(abs((num_pin(n, "B") or -1.0) - GUN_DROP_CHANCE) < 1e-6
              for n in hg if "B" in in_pins(n)),
          f"expected a comparison against {GUN_DROP_CHANCE}")
    # Two draws, not one weighted table: the rate and the table are tuned apart.
    check("...rolled once, and which weapon drawn separately",
          bool([n for n in hg if {"Min", "Max"} <= in_pins(n)
                and "Random" in str(BEL.get_node_title(n))]),
          "no random draw in the death path")
    check("the weapon is picked by index into the array, not by a Switch that "
          "would need a pin per weapon",
          bool(by_pins(hg, "TargetArray", "Index")),
          f"{len(by_pins(hg, 'TargetArray', 'Index'))} Array_Get node(s)")
    # The empty-table guard. Without it RandomIntegerInRange(0, -1) indexes nothing.
    check("an empty drop table drops nothing rather than indexing off the end",
          any(str(BEL.get_node_title(n)).replace("\n", " ").startswith("Get DropClasses")
              for n in hg)
          and bool([n for n in hg if "TargetArray" in in_pins(n)
                    and "Length" in str(BEL.get_node_title(n))]),
          "no Array_Length on DropClasses")
    # The handover: from here it is an ordinary weapon on the ground, and the E key
    # that picks up a gun the player threw away picks this one up with no new code.
    check("a dropped weapon is flagged Dropped, which is the whole pick-up interface",
          any(str(BEL.get_node_title(n)).replace("\n", " ") == "Set Dropped"
              for n in hg),
          "nothing sets Dropped in the death path")
    # Matched by the feeder's PIN SET, not by its title: Array_Get's displayed
    # title is the bare word "Get", which is also how every variable getter in the
    # graph reads. Pins are the only unambiguous handle.
    guns = [n for n in by_pins(hg, "Class", "SpawnTransform")
            if any({"TargetArray", "Index"} <= in_pins(PIN.get_owning_node(q))
                   for q in PIN.list_connected_pins(BEL.find_input_pin(n, "Class")))]
    check("exactly one spawn in the death path drops a weapon",
          len(guns) == 1, f"{len(guns)} weapon spawns")
    # Same guard as the shells and the kill count, walked the same way: the safety
    # net kills anything that falls under the world down this very path.
    if guns:
        # BREADTH-first over every exec feeder, not a single chain.
        #
        # This used to follow feeders[0] and stop, which made it a coin flip: an
        # exec input takes any number of links and their order is not something
        # this API promises, so on a graph where the drop is reached from more than
        # one place the walk would sometimes take the arm without the guard on it
        # and report the guard missing. It failed intermittently, on a graph that
        # had not changed, which is worse than no check at all -- a flaky assertion
        # teaches you to ignore it.
        seen, frontier, guarded, hops = set(), [guns[0]], False, 0
        while frontier and hops < 400 and not guarded:
            node = frontier.pop(0)
            hops += 1
            if id(node) in seen:
                continue
            seen.add(id(node))
            if "Branch" in str(BEL.get_node_title(node)).replace("\n", " "):
                cond = BEL.find_input_pin(node, "Condition")
                if cond and cond.is_valid() and any(
                        DAMAGED_BY_PLAYER_VAR in str(BEL.get_node_title(
                            PIN.get_owning_node(q)))
                        for q in PIN.list_connected_pins(cond)):
                    guarded = True
                    break
            ins = BEL.find_input_pin(node, "execute")
            if ins and ins.is_valid():
                frontier.extend(PIN.get_owning_node(q)
                                for q in PIN.list_connected_pins(ins))
        check("only a death the player caused drops a weapon", guarded,
              "the safety net must not be a weapon dispenser")
    check("an uncollected drop tidies itself away",
          any(abs(float(pin_value(n, "InLifespan") or 0) - AMMO_PICKUP_LIFETIME) < 1e-3
              for n in ag if "InLifespan" in in_pins(n)),
          f"{AMMO_PICKUP_LIFETIME:.0f}s")


# --- and who drops it --------------------------------------------------------

def check_who_drops():
    hp = load(HEALTH_BP_PATH)
    hg = graph(hp).list_all_nodes()
    check("a killed wanderer's health component knows what to drop",
          cdo(hp).get_editor_property("AmmoClass") is not None
          and cdo(hp).get_editor_property("AmmoClass").get_name() == "BP_AmmoPickup_C",
          str(cdo(hp).get_editor_property("AmmoClass")))
    drops = [n for n in by_pins(hg, "Class", "SpawnTransform")
             if any("AmmoClass" in str(BEL.get_node_title(PIN.get_owning_node(q)))
                    for q in PIN.list_connected_pins(BEL.find_input_pin(n, "Class")))]
    check("exactly one spawn in the death path drops ammunition",
          len(drops) == 1, f"{len(drops)} ammo spawns")
    # The same guard the kill counter uses, and for the same reason: the safety net
    # writes Health to 0 for a wanderer that fell through the world, and paying the
    # player for that would turn a bug into an ammunition supply.
    if drops:
        seen, node, guarded = set(), drops[0], False
        for _ in range(40):
            ins = BEL.find_input_pin(node, "execute")
            feeders = [PIN.get_owning_node(q) for q in PIN.list_connected_pins(ins)] \
                if ins and ins.is_valid() else []
            if not feeders:
                break
            node = feeders[0]
            if id(node) in seen:
                break
            seen.add(id(node))
            title = str(BEL.get_node_title(node)).replace("\n", " ")
            if "Branch" in title:
                cond = BEL.find_input_pin(node, "Condition")
                if cond and cond.is_valid() and any(
                        DAMAGED_BY_PLAYER_VAR in str(BEL.get_node_title(
                            PIN.get_owning_node(q)))
                        for q in PIN.list_connected_pins(cond)):
                    guarded = True
                    break
        check("only a death the player caused drops shells", guarded,
              f"{DAMAGED_BY_PLAYER_VAR} branch found upstream: {guarded}")


def run():
    check_ammo_pickup()
    check_weapon_drop()
    check_who_drops()
