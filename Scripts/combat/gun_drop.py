"""The gun drop on a counted kill: two seeded rolls and a weighted loot table.

Owns the BP_HealthComponent graph fragment that decides whether a kill leaves
a weapon and which one, and the lazy per-session seeding of the two
FRandomStreams it draws from. The streams themselves are GameMode variables
(game_state.GUN_*_VAR); the numbers are GUN_* in tuning.py; the table is
DropClasses, filled with one entry per ticket by build_weapons_and_combat.main().
"""

from combat.game_state import (
    GUN_PICK_STREAM_VAR, GUN_ROLL_STREAM_VAR, GUN_STREAMS_SEEDED_VAR,
)
from combat.graph import (
    BEL, _at, _connect, _loose_pin, _node, _palette, _pin, _set, _vec,
)
from combat.nodes import (
    FN_ADD_VV, FN_AND, FN_ARR_GET, FN_ARR_LEN, FN_GREATER_II, FN_LESS_FF,
    FN_MAKE_TRANSFORM, FN_SEED_STREAM, FN_SET_STREAM_SEED, FN_STREAM_FLOAT,
    FN_STREAM_INT, NODE_CAST_ITEM, NODE_SPAWN,
)
from combat.paths import GAME_MODE_CLASS_PATH, ITEM_CLASS_PATH
from combat.tuning import (
    GUN_DROP_CHANCE, GUN_DROP_FORWARD, GUN_DROP_SEED, GUN_LOOT_TABLE,
)


def _mode_var(ed, mode_out, name, x, y, setter=False):
    """A get (or set) of one of the GameMode's gun-drop variables."""
    make = (ed.add_set_member_variable_node if setter
            else ed.add_get_member_variable_node)
    node = _at(make(name, GAME_MODE_CLASS_PATH), x, y)
    _connect(mode_out, _pin(node, "self"))
    return node


def _author_seed_streams(ed, mode_out, exec_in, keep, x0, y0):
    """Seed both streams once per session, on the first counted kill.

    Lazily, here, rather than at the GameMode's BeginPlay, because
    combat_trace.py owns (and wipes) the GameMode's EventGraph. A fresh
    FRandomStream has seed 0, so without this every session would draw the
    same sequence. GUN_DROP_SEED != 0 is that on purpose: fixed seeds, for a
    probe or a bug report. Decided here in Python, so the graph holds one arm.

    Returns the exec pins that carry on to the roll -- seeded before, or now.
    """
    seeded = keep(_mode_var(ed, mode_out, GUN_STREAMS_SEEDED_VAR, x0, y0 + 240))
    first = keep(_at(ed.add_branch_node(), x0 + 240, y0))
    _connect(_pin(seeded, GUN_STREAMS_SEEDED_VAR, is_input=False),
             _pin(first, "Condition"))
    _connect(exec_in, _pin(first, "execute"))

    step = BEL.find_else_pin(first)
    for i, name in enumerate((GUN_ROLL_STREAM_VAR, GUN_PICK_STREAM_VAR)):
        stream = keep(_mode_var(ed, mode_out, name, x0 + 480 + 480 * i, y0 + 240))
        seed = keep(_at(_node(ed, FN_SET_STREAM_SEED if GUN_DROP_SEED
                              else FN_SEED_STREAM), x0 + 720 + 480 * i, y0))
        _connect(_pin(stream, name, is_input=False), _pin(seed, "Stream"))
        if GUN_DROP_SEED:
            _set(seed, "NewSeed", GUN_DROP_SEED + i)
        _connect(step, _pin(seed, "execute"))
        step = BEL.find_then_pin(seed)
    done = keep(_mode_var(ed, mode_out, GUN_STREAMS_SEEDED_VAR,
                          x0 + 1680, y0, setter=True))
    _set(done, GUN_STREAMS_SEEDED_VAR, "true")
    _connect(step, _pin(done, "execute"))
    return BEL.find_then_pin(first), BEL.find_then_pin(done)


def _author_gun_drop(ed, mode_out, at, exec_in, x0, y0):
    """One kill in ten also leaves a weapon: which one is a second, separate roll.

    Two decisions, each on its own FRandomStream on the GameMode:

        drop roll  RandomFloatFromStream(GunDropRollStream) < GUN_DROP_CHANCE;
        pick roll  RandomIntegerFromStream(GunDropPickStream, Length) into
                   DropClasses, the loot table with one entry per ticket.

    Keeping them apart means the rate and the table are tuned independently --
    re-weighting the table changes what a drop is worth and not how often one
    happens, and because the pick stream is drawn only by kills that drop, the
    drop sequence of a seeded session does not move either.

    Both draws are pure and advance their stream, so each has exactly one
    consumer: the Branch pulls the drop roll once, the spawn pulls the pick once.

    Two guards on the roll, folded into one condition because both are plain
    reads with nothing behind them:

        lucky    the 10%.
        stocked  the table is not empty. RandomIntegerFromStream(0) is 0, and
                 Array_Get at 0 of an empty array is an access-none per kill on
                 any build where main() has not filled the table.

    The spawned actor is cast to BP_WeaponItem so Dropped can be set on it, and
    Dropped is the entire interface: from that moment it is an ordinary weapon
    lying in the forest, and the E key that picks up a gun the player threw
    away is the same code that picks this one up. Nothing in _author_pickup
    knows these exist.
    """
    made = []

    def keep(n):
        made.append(n)
        return n

    ready = _author_seed_streams(ed, mode_out, exec_in, keep, x0 + 400, y0 - 400)

    rolls = keep(_mode_var(ed, mode_out, GUN_ROLL_STREAM_VAR, x0 + 2160, y0 + 300))
    roll = keep(_at(_node(ed, FN_STREAM_FLOAT), x0 + 2400, y0 + 300))
    _connect(_pin(rolls, GUN_ROLL_STREAM_VAR, is_input=False), _pin(roll, "Stream"))
    lucky = keep(_at(_node(ed, FN_LESS_FF), x0 + 2640, y0 + 300))
    _connect(_pin(roll, "ReturnValue", is_input=False), _pin(lucky, "A"))
    _set(lucky, "B", GUN_DROP_CHANCE)

    table = keep(_at(ed.add_get_member_variable_node("DropClasses"),
                     x0 + 2400, y0 + 440))
    table_out = _pin(table, "DropClasses", is_input=False)
    how_many = keep(_at(_node(ed, FN_ARR_LEN), x0 + 2640, y0 + 440))
    _connect(table_out, _pin(how_many, "TargetArray"))
    stocked = keep(_at(_node(ed, FN_GREATER_II), x0 + 2880, y0 + 440))
    _connect(_pin(how_many, "ReturnValue", is_input=False), _pin(stocked, "A"))
    _set(stocked, "B", 0)

    worth = keep(_at(_node(ed, FN_AND), x0 + 3120, y0 + 360))
    _connect(_pin(lucky, "ReturnValue", is_input=False), _pin(worth, "A"))
    _connect(_pin(stocked, "ReturnValue", is_input=False), _pin(worth, "B"))
    rare = keep(_at(ed.add_branch_node(), x0 + 3360, y0))
    _connect(_pin(worth, "ReturnValue", is_input=False), _pin(rare, "Condition"))
    for pin in ready:
        _connect(pin, _pin(rare, "execute"))

    # RandomIntegerFromStream is [0, Max), so the length is the top as it is.
    picks = keep(_mode_var(ed, mode_out, GUN_PICK_STREAM_VAR, x0 + 2880, y0 + 720))
    which = keep(_at(_node(ed, FN_STREAM_INT), x0 + 3120, y0 + 580))
    _connect(_pin(picks, GUN_PICK_STREAM_VAR, is_input=False), _pin(which, "Stream"))
    _connect(_pin(how_many, "ReturnValue", is_input=False), _pin(which, "Max"))
    pick = keep(_at(_node(ed, FN_ARR_GET), x0 + 3360, y0 + 580))
    _connect(table_out, _pin(pick, "TargetArray"))
    _connect(_pin(which, "ReturnValue", is_input=False), _pin(pick, "Index"))

    # Clear of the shells, which are already sitting on the corpse: two pickups
    # at the same point read as one object and the player collects the ammo
    # without ever seeing the gun.
    beside = keep(_at(_node(ed, FN_ADD_VV), x0 + 3620, y0 + 300))
    _connect(at, _pin(beside, "A"))
    _connect(_vec(ed, GUN_DROP_FORWARD, 0.0, 0.0, x0 + 3360, y0 + 440),
             _pin(beside, "B"))
    where = keep(_at(_node(ed, FN_MAKE_TRANSFORM), x0 + 3880, y0 + 300))
    _connect(_pin(beside, "ReturnValue", is_input=False), _pin(where, "Location"))
    _connect(_vec(ed, 1.0, 1.0, 1.0, x0 + 3620, y0 + 480), _pin(where, "Scale"))

    spawn = keep(_at(_palette(ed, NODE_SPAWN), x0 + 4140, y0))
    _connect(_pin(pick, "Item", is_input=False), _pin(spawn, "Class"))
    _connect(_pin(where, "ReturnValue", is_input=False), _pin(spawn, "SpawnTransform"))
    _set(spawn, "CollisionHandlingOverride", "AlwaysSpawn")
    _connect(BEL.find_then_pin(rare), _pin(spawn, "execute"))

    # DropClasses is typed as class-of-Actor, for the same reason AmmoClass is:
    # this component has to compile in a pass where BP_WeaponItem's generated
    # class is not available to type a pin against. The cost is this cast.
    as_item = keep(_at(_palette(ed, NODE_CAST_ITEM), x0 + 4400, y0))
    _connect(_pin(spawn, "ReturnValue", is_input=False), _pin(as_item, "Object"))
    _connect(BEL.find_then_pin(spawn), _pin(as_item, "execute"))
    loose = keep(_at(ed.add_set_member_variable_node("Dropped", ITEM_CLASS_PATH),
                     x0 + 4680, y0))
    _connect(_loose_pin(as_item, "AsBPWeaponItem", is_input=False),
             _pin(loose, "self"))
    _set(loose, "Dropped", "true")
    _connect(BEL.find_then_pin(as_item), _pin(loose, "execute"))

    total = sum(w for _, w in GUN_LOOT_TABLE)
    shares = ", ".join(f"{name} {GUN_DROP_CHANCE * w / total * 100:.0f}%"
                       for name, w in GUN_LOOT_TABLE)
    ed.add_comment_to_nodes(
        f"Gun drop: roll stream < {GUN_DROP_CHANCE:.2f} decides whether, pick "
        f"stream into the DropClasses tickets decides which ({shares} per "
        "kill). Both streams live on the GameMode and are seeded on the first "
        "counted kill. Dropped=true is the whole handover: from here it is an "
        "ordinary weapon on the ground and E picks it up with no new code.",
        made)
    return (BEL.find_then_pin(loose),
            _pin(as_item, "CastFailed", is_input=False),
            BEL.find_else_pin(rare))
