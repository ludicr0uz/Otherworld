"""verify.drops -- BP_AmmoPickup and the gun drop (two seeded rolls, loot table).
"""

import unreal

from combat.game_state import (
    DAMAGED_BY_PLAYER_VAR, GUN_PICK_STREAM_VAR, GUN_ROLL_STREAM_VAR,
    GUN_STREAMS_SEEDED_VAR,
)
from combat.paths import AMMO_BP_PATH, GAME_MODE_BP_PATH, HEALTH_BP_PATH
from combat.tuning import (
    AMMO_DROP_SHELLS, AMMO_PICKUP_LIFETIME, AMMO_PICKUP_RADIUS,
    GUN_DROP_CHANCE, GUN_DROP_SEED, GUN_LOOT_TABLE,
)
from combat.weapon_specs import DROP_TICKETS, _weapon_specs
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
    # The pistol has a magazine now, but its reserve never ends: shells paid
    # into it would vanish. Both paths (held weapon and loop) ask.
    endless = [n for n in ag if "InfiniteReserve" in out_pins(n)]
    check("the shells never go to an InfiniteReserve weapon (the pistol), on "
          "either path", len(endless) == 2, f"{len(endless)} InfiniteReserve reads")
    check("...with the inventory loop kept as the fallback for an unarmed player "
          "or one holding the pistol",
          bool(by_pins(ag, "Array")) or any("Inventory" in out_pins(n) for n in ag),
          "the ForEachLoop over Inventory is gone")


# ─── The gun drop ────────────────────────────────────────────────────────────

class _Stream:
    """FRandomStream, bit for bit (Core/Public/Math/RandomStream.h), so the
    table's shares can be measured here with the engine's own generator."""

    def __init__(self, seed):
        self.seed = seed & 0xFFFFFFFF

    def fraction(self):
        self.seed = (self.seed * 196314165 + 907633515) & 0xFFFFFFFF
        # 1.0f with the top 23 bits of the seed as its mantissa, minus 1.
        return (self.seed >> 9) / float(1 << 23)

    def below(self, top):
        return int(self.fraction() * top) if top > 0 else 0


def simulate_gun_drops(roll_seed, pick_seed, kills, tickets=DROP_TICKETS,
                       chance=GUN_DROP_CHANCE):
    """What the death path drops over ``kills`` counted kills: one name or None
    per kill. The same two draws the graph makes, in the same order."""
    roll, pick = _Stream(roll_seed), _Stream(pick_seed)
    return [tickets[pick.below(len(tickets))]
            if roll.fraction() < chance and tickets else None
            for _ in range(kills)]


def _feeders(node, pin):
    p = BEL.find_input_pin(node, pin)
    if not (p and p.is_valid()):
        return []
    return [PIN.get_owning_node(q) for q in PIN.list_connected_pins(p)]


def _reads(node, var):
    return var in out_pins(node)


def check_weapon_drop():
    drop_classes = list(cdo(health_bp).get_editor_property("DropClasses"))
    want = [f"{sp['path'].rsplit('/', 1)[-1]}_C"
            for name in DROP_TICKETS
            for sp in _weapon_specs() if sp["display"] == name]
    check(f"the loot table holds one DropClasses entry per ticket "
          f"({', '.join(f'{n} x{w}' for n, w in GUN_LOOT_TABLE)})",
          [c.get_name() for c in drop_classes] == want,
          str([c.get_name() for c in drop_classes]))
    issued = {sp["display"] for sp in _weapon_specs()} - {n for n, _ in GUN_LOOT_TABLE}
    check("...every weight is positive and nothing in the starting loadout is in it",
          all(w > 0 for _, w in GUN_LOOT_TABLE) and issued == {"Shotgun", "Pistol"},
          str(GUN_LOOT_TABLE))

    mode = cdo(load(GAME_MODE_BP_PATH))
    streams = [mode.get_editor_property(v)
               for v in (GUN_ROLL_STREAM_VAR, GUN_PICK_STREAM_VAR)]
    check("the GameMode carries the two gun-drop random streams",
          all(isinstance(x, unreal.RandomStream) for x in streams),
          str([type(x).__name__ for x in streams]))

    # The two rolls, told apart by which stream feeds them.
    draws = [n for n in hg if "Stream" in in_pins(n) and "execute" not in in_pins(n)]
    rolls = [n for n in draws if "Max" not in in_pins(n)
             and any(_reads(f, GUN_ROLL_STREAM_VAR) for f in _feeders(n, "Stream"))]
    picks = [n for n in draws if "Max" in in_pins(n)
             and any(_reads(f, GUN_PICK_STREAM_VAR) for f in _feeders(n, "Stream"))]
    check("the drop roll is RandomFloatFromStream on GunDropRollStream",
          len(rolls) == 1, f"{len(rolls)} roll(s), {len(draws)} stream draw(s)")
    check("the pick roll is RandomIntegerFromStream on GunDropPickStream",
          len(picks) == 1, f"{len(picks)} pick(s)")
    check("...and nothing else in the health graph draws from a stream",
          len(draws) == 2, f"{len(draws)} stream draws")
    check("no unseeded RandomIntegerInRange is left in the death path -- the "
          "only one is the flinch clip pick",
          len([n for n in by_pins(hg, "Min", "Max")
               if "RandomInteger" in str(BEL.get_node_title(n))]) <= 1)
    # Pure draws advance their stream: a second reader would be a second roll.
    for label, nodes in (("drop", rolls), ("pick", picks)):
        if nodes:
            outs = [p for p in BEL.list_output_pins(nodes[0])]
            links = sum(len(PIN.list_connected_pins(p)) for p in outs)
            check(f"the {label} roll has exactly one reader", links == 1,
                  f"{links} link(s)")
    if rolls:
        lucky = [n for n in hg if rolls[0] in _feeders(n, "A")]
        check(f"the drop rate is {GUN_DROP_CHANCE * 100:.0f}%, compared against "
              "the drop roll",
              len(lucky) == 1
              and abs((num_pin(lucky[0], "B") or -1.0) - GUN_DROP_CHANCE) < 1e-6,
              f"expected roll < {GUN_DROP_CHANCE}")
    if picks:
        top = _feeders(picks[0], "Max")
        check("the pick draws over the whole table: Max is Length(DropClasses), "
              "as RandomIntegerFromStream is already [0, Max)",
              len(top) == 1 and "TargetArray" in in_pins(top[0])
              and "Length" in str(BEL.get_node_title(top[0])),
              str([str(BEL.get_node_title(t)) for t in top]))
        check("the weapon is picked by index into the array, not by a Switch that "
              "would need a pin per weapon",
              any(picks[0] in _feeders(n, "Index")
                  for n in by_pins(hg, "TargetArray", "Index")),
              f"{len(by_pins(hg, 'TargetArray', 'Index'))} Array_Get node(s)")

    # Seeded once per session, on the first counted kill.
    seeders = [n for n in hg if "Stream" in in_pins(n) and "execute" in in_pins(n)]
    seeded = {v for n in seeders for f in _feeders(n, "Stream")
              for v in (GUN_ROLL_STREAM_VAR, GUN_PICK_STREAM_VAR) if _reads(f, v)}
    fixed = [n for n in seeders if "NewSeed" in in_pins(n)]
    check("both streams are seeded"
          + (f" (fixed: {GUN_DROP_SEED}, {GUN_DROP_SEED + 1})" if GUN_DROP_SEED
             else " from the engine RNG, so each session draws differently"),
          len(seeders) == 2 and seeded == {GUN_ROLL_STREAM_VAR, GUN_PICK_STREAM_VAR}
          and len(fixed) == (2 if GUN_DROP_SEED else 0),
          f"{len(seeders)} seeder(s) on {sorted(seeded)}")
    gate = [n for n in hg if "Branch" in str(BEL.get_node_title(n))
            and any(_reads(f, GUN_STREAMS_SEEDED_VAR) for f in _feeders(n, "Condition"))]
    check("...once, behind a Branch on GunDropSeeded that the seeding sets",
          len(gate) == 1 and any(
              str(BEL.get_node_title(n)).replace("\n", " ")
              == f"Set {GUN_STREAMS_SEEDED_VAR}" for n in hg),
          f"{len(gate)} gate(s)")

    # The engine's own generator over the table: the rate is the chance and the
    # shares are the weights. 20k kills keeps sampling noise under ~0.5 points.
    sim = simulate_gun_drops(1, 2, 20000)
    got = [d for d in sim if d]
    rate = len(got) / len(sim)
    total = sum(w for _, w in GUN_LOOT_TABLE)
    worst = max(abs(got.count(n) / max(len(got), 1) - w / total)
                for n, w in GUN_LOOT_TABLE)
    check(f"FRandomStream replayed over 20000 kills drops at {GUN_DROP_CHANCE:.0%}"
          f" with the table's shares",
          abs(rate - GUN_DROP_CHANCE) < 0.01 and worst < 0.03,
          f"rate {rate:.3f}, worst share error {worst:.3f}")

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
