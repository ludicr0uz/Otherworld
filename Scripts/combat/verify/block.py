"""verify.block -- the player's guard (weapon_component/block.py): its key,
the Blocking stance it writes, and the fire gate refusing while it is up.
Also the other thing a wanderer reads off the player: FireWard, fire held out.

What a block does to a swing is authored into the wanderers' controllers
(npc/block.py) and checked by verify_npc_blueprints.py.
"""

from combat.paths import FIRE_WARD_VAR
from combat.tuning import BIND_VARS, BLOCK_KEY, COMBAT
from combat.weapon_component.vars import FirePressedAt as FIRE_PRESSED_AT
from combat.verify.fixtures import w, wg
from combat.verify.common import BEL, PIN, check, in_pins, pin_value
from combat.verify.knife import is_melee_gate


def _title(n):
    return str(BEL.get_node_title(n)).replace("\n", " ")


def _feeds(pin, limit=250):
    """Every node feeding this pin through DATA links only."""
    seen, stack = set(), [pin]
    while stack and len(seen) < limit:
        for q in PIN.list_connected_pins(stack.pop()):
            node = PIN.get_owning_node(q)
            if node in seen:
                continue
            seen.add(node)
            stack.extend(x for x in BEL.list_input_pins(node)
                         if str(PIN.get_pin_name(x)) != "execute")
    return seen


def check_block_key():
    check(f"blocking is its own bind, {BLOCK_KEY} by default, appended after "
          f"the eight older binds so no saved bind changes meaning",
          [v for v, _k in BIND_VARS][8] == "KeyBlock"
          and w.get_editor_property("KeyBlock").export_text() == BLOCK_KEY,
          str([v for v, _k in BIND_VARS]))
    check("Blocking is a bool that starts false",
          w.get_editor_property("Blocking") is False,
          repr(w.get_editor_property("Blocking")))
    check("the guard's numbers make sense: a block takes some damage off, "
          "costs some stamina, and covers the front only",
          0.0 < COMBAT.block_damage_scale < 1.0
          and 0.0 < COMBAT.block_stamina_per_hit < COMBAT.max_stamina
          and 0.0 < COMBAT.block_half_angle_deg < 90.0)


def check_blocking_stance():
    every = [n for n in wg if "Blocking" in in_pins(n) and _title(n) == "Set Blocking"]
    # Two writes: the owning machine's, off its key, and the server's for a
    # client's character, off what that client asked (holds.py: verify/strike.py).
    sets = [n for n in every
            if "Get KeyBlock" in {_title(x) for x in _feeds(BEL.find_input_pin(n, "Blocking"))}]
    check("Blocking is written once a frame off the key, in one place (and once by "
          "the server, for a client's character)", len(sets) == 1 and len(every) == 2,
          f"{len(sets)} of {len(every)}")
    if len(sets) != 1:
        return
    src = {_title(n) for n in _feeds(BEL.find_input_pin(sets[0], "Blocking"))}
    check("...held on the block key, while there is stamina and the player is "
          "not sprinting",
          {"Get KeyBlock", "Get Stamina", "Get Sprinting"} <= src
          and any("IsInputKeyDown" in t for t in src)
          and any(t.upper().startswith("NOT") for t in src), str(sorted(src)))
    check("...and without asking what is in hand, so it works unarmed",
          "Get Held" not in src and not any("IsValid" in t for t in src),
          str(sorted(src)))
    zero = [n for n in _feeds(BEL.find_input_pin(sets[0], "Blocking"))
            if _title(n) == "Get Stamina"]
    gt = [PIN.get_owning_node(q) for z in zero
          for q in BEL.find_output_pin(z, "Stamina").list_connected_pins()]
    check("...a guard with no stamina left is no guard (Stamina > 0)",
          len(gt) == 1 and pin_value(gt[0], "B") in ("", "0.0", "0", "0.000000"),
          str([pin_value(g, "B") for g in gt]))


def check_fire_refused_while_blocking():
    reads = [n for n in wg if _title(n) == "Get Blocking"]
    negated = [PIN.get_owning_node(q) for n in reads
               for q in BEL.find_output_pin(n, "Blocking").list_connected_pins()
               if _title(PIN.get_owning_node(q)).upper().startswith("NOT")
               # (Not the report's NotEqual against what was last sent: holds.py.)
               and "EQUAL" not in _title(PIN.get_owning_node(q)).upper()]
    # Three: the trigger's, and the two swings' Server events (verify/strike.py).
    check("the trigger reads Blocking through a NOT, as the two swings' Server "
          "events do", len(negated) == 3, f"{len(negated)} of {len(reads)} read(s)")
    # The fire gate is the one Branch whose condition reads the fire key AND
    # Sprinting; it must read the guard's NOT too.
    # (The punch's press gate reads both too; verify/punch.py checks it.)
    gates = [n for n in wg if _title(n) == "Branch" and not is_melee_gate(n)
             and {f"Get {FIRE_PRESSED_AT}", "Get Sprinting"}
             <= {_title(x) for x in _feeds(BEL.find_input_pin(n, "Condition"))}]
    check("...and the fire gate refuses while the guard is up",
          len(gates) == 1 and any(
              n in _feeds(BEL.find_input_pin(gates[0], "Condition")) for n in negated),
          str(len(gates)))


def check_fire_ward():
    check(f"{FIRE_WARD_VAR} is a bool that starts false: no fire is held out "
          f"until something lights one (the wendigo reads it, npc/ward.py)",
          w.get_editor_property(FIRE_WARD_VAR) is False,
          repr(w.get_editor_property(FIRE_WARD_VAR)))


def run():
    check_block_key()
    check_fire_ward()
    check_blocking_stance()
    check_fire_refused_while_blocking()
