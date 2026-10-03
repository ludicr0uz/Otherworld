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
from combat.graph import BEL, _connect, _loose_pin, _node, _palette, _pin, _set, _vec
from combat.nodes import (
    FN_ADD_VV, FN_AND, FN_ARR_GET, FN_ARR_LEN, FN_GREATER_II, FN_LESS_FF,
    FN_MAKE_TRANSFORM, FN_SEED_STREAM, FN_SET_STREAM_SEED, FN_STREAM_FLOAT,
    FN_STREAM_INT, NODE_CAST_ITEM, NODE_SPAWN,
)
from combat.paths import GAME_MODE_CLASS_PATH, ITEM_CLASS_PATH
from combat.tuning import (
    GUN_DROP_CHANCE, GUN_DROP_FORWARD, GUN_DROP_SEED, GUN_LOOT_TABLE,
)


def _mode_var(ed, mode_out, name, setter=False):
    """A get (or set) of one of the GameMode's gun-drop variables."""
    make = (ed.add_set_member_variable_node if setter
            else ed.add_get_member_variable_node)
    node = make(name, GAME_MODE_CLASS_PATH)
    _connect(mode_out, _pin(node, "self"))
    return node


def _author_seed_streams(ed, mode_out, exec_in, keep):
    """Seed both streams once per session, on the first counted kill.

    Lazily, here, rather than at the GameMode's BeginPlay, because
    combat_trace.py owns (and wipes) the GameMode's EventGraph. A fresh
    FRandomStream has seed 0, so without this every session would draw the
    same sequence. GUN_DROP_SEED != 0 is that on purpose: fixed seeds, for a
    probe or a bug report. Decided here in Python, so the graph holds one arm.

    Returns the exec pins that carry on to the roll -- seeded before, or now.
    """
    seeded = keep(_mode_var(ed, mode_out, GUN_STREAMS_SEEDED_VAR))
    first = keep(ed.add_branch_node())
    _connect(_pin(seeded, GUN_STREAMS_SEEDED_VAR, is_input=False),
             _pin(first, "Condition"))
    _connect(exec_in, _pin(first, "execute"))

    step = BEL.find_else_pin(first)
    for i, name in enumerate((GUN_ROLL_STREAM_VAR, GUN_PICK_STREAM_VAR)):
        stream = keep(_mode_var(ed, mode_out, name))
        seed = keep(_node(ed, FN_SET_STREAM_SEED if GUN_DROP_SEED else FN_SEED_STREAM))
        _connect(_pin(stream, name, is_input=False), _pin(seed, "Stream"))
        if GUN_DROP_SEED:
            _set(seed, "NewSeed", GUN_DROP_SEED + i)
        _connect(step, _pin(seed, "execute"))
        step = BEL.find_then_pin(seed)
    done = keep(_mode_var(ed, mode_out, GUN_STREAMS_SEEDED_VAR, setter=True))
    _set(done, GUN_STREAMS_SEEDED_VAR, "true")
    _connect(step, _pin(done, "execute"))
    return BEL.find_then_pin(first), BEL.find_then_pin(done)


def _author_gun_drop(ed, mode_out, at, exec_in):
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

    ready = _author_seed_streams(ed, mode_out, exec_in, keep)

    rolls = keep(_mode_var(ed, mode_out, GUN_ROLL_STREAM_VAR))
    roll = keep(_node(ed, FN_STREAM_FLOAT))
    _connect(_pin(rolls, GUN_ROLL_STREAM_VAR, is_input=False), _pin(roll, "Stream"))
    lucky = keep(_node(ed, FN_LESS_FF))
    _connect(_pin(roll, "ReturnValue", is_input=False), _pin(lucky, "A"))
    _set(lucky, "B", GUN_DROP_CHANCE)

    table = keep(ed.add_get_member_variable_node("DropClasses"))
    table_out = _pin(table, "DropClasses", is_input=False)
    how_many = keep(_node(ed, FN_ARR_LEN))
    _connect(table_out, _pin(how_many, "TargetArray"))
    stocked = keep(_node(ed, FN_GREATER_II))
    _connect(_pin(how_many, "ReturnValue", is_input=False), _pin(stocked, "A"))
    _set(stocked, "B", 0)

    worth = keep(_node(ed, FN_AND))
    _connect(_pin(lucky, "ReturnValue", is_input=False), _pin(worth, "A"))
    _connect(_pin(stocked, "ReturnValue", is_input=False), _pin(worth, "B"))
    rare = keep(ed.add_branch_node())
    _connect(_pin(worth, "ReturnValue", is_input=False), _pin(rare, "Condition"))
    for pin in ready:
        _connect(pin, _pin(rare, "execute"))

    # RandomIntegerFromStream is [0, Max), so the length is the top as it is.
    picks = keep(_mode_var(ed, mode_out, GUN_PICK_STREAM_VAR))
    which = keep(_node(ed, FN_STREAM_INT))
    _connect(_pin(picks, GUN_PICK_STREAM_VAR, is_input=False), _pin(which, "Stream"))
    _connect(_pin(how_many, "ReturnValue", is_input=False), _pin(which, "Max"))
    pick = keep(_node(ed, FN_ARR_GET))
    _connect(table_out, _pin(pick, "TargetArray"))
    _connect(_pin(which, "ReturnValue", is_input=False), _pin(pick, "Index"))

    # Clear of the shells, which are already sitting on the corpse: two pickups
    # at the same point read as one object and the player collects the ammo
    # without ever seeing the gun.
    beside = keep(_node(ed, FN_ADD_VV))
    _connect(at, _pin(beside, "A"))
    _connect(_vec(ed, GUN_DROP_FORWARD, 0.0, 0.0), _pin(beside, "B"))
    where = keep(_node(ed, FN_MAKE_TRANSFORM))
    _connect(_pin(beside, "ReturnValue", is_input=False), _pin(where, "Location"))
    _connect(_vec(ed, 1.0, 1.0, 1.0), _pin(where, "Scale"))

    spawn = keep(_palette(ed, NODE_SPAWN))
    _connect(_pin(pick, "Item", is_input=False), _pin(spawn, "Class"))
    _connect(_pin(where, "ReturnValue", is_input=False), _pin(spawn, "SpawnTransform"))
    _set(spawn, "CollisionHandlingOverride", "AlwaysSpawn")
    _connect(BEL.find_then_pin(rare), _pin(spawn, "execute"))

    # DropClasses is typed as class-of-Actor, for the same reason AmmoClass is:
    # this component has to compile in a pass where BP_WeaponItem's generated
    # class is not available to type a pin against. The cost is this cast.
    as_item = keep(_palette(ed, NODE_CAST_ITEM))
    _connect(_pin(spawn, "ReturnValue", is_input=False), _pin(as_item, "Object"))
    _connect(BEL.find_then_pin(spawn), _pin(as_item, "execute"))
    loose = keep(ed.add_set_member_variable_node("Dropped", ITEM_CLASS_PATH))
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
