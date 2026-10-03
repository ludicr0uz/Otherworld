"""The melee weapons' rows of the gun tuning table (gun_tuning.csv): what the
GUN SETTINGS tab can change of the knife and the axe, which is their throw.

    throw_arc       the tip over the view of a throw at nothing in reach
    throw_damage    what a thrown one takes off a body it strikes

The defaults are throw_tuning's; a cell of the CSV wins, as it does for a gun
(weapon_specs._weapon_specs). knife.py and axe.py lay melee_throw() over
their defaults, and the tab's table (graphics_menu/tune_tick.py) lists
melee_specs() under the guns.
"""

from combat.gun_tuning import MELEE_COLUMNS, MELEE_WEAPONS, TUNE_STATS, read_table
from combat.throw_tuning import (
    THROW_AXE_DAMAGE, THROW_DAMAGE_COLUMN, THROW_KNIFE_DAMAGE,
    THROW_MELEE_PITCH_UP_DEG, THROW_PITCH_COLUMN,
)

MELEE_DEFAULTS = {
    "Knife": {THROW_PITCH_COLUMN: THROW_MELEE_PITCH_UP_DEG,
              THROW_DAMAGE_COLUMN: THROW_KNIFE_DAMAGE},
    "Axe": {THROW_PITCH_COLUMN: THROW_MELEE_PITCH_UP_DEG,
            THROW_DAMAGE_COLUMN: THROW_AXE_DAMAGE},
}
assert tuple(MELEE_DEFAULTS) == MELEE_WEAPONS
assert all(tuple(d) == MELEE_COLUMNS for d in MELEE_DEFAULTS.values())


def melee_specs():
    """[(DisplayName, {column: value})] in MELEE_WEAPONS order: the defaults
    with the CSV's cells over them."""
    tuned = read_table()
    return [(name, {c: float(tuned.get(name, {}).get(c, default))
                    for c, default in MELEE_DEFAULTS[name].items()})
            for name in MELEE_WEAPONS]


def melee_throw(display):
    """{BP_WeaponItem variable: value}: what ``display``'s builder adds to
    its defaults, after throw_tuning.MELEE_THROW."""
    spec = dict(melee_specs())[display]
    return {var: spec[col] for col, var, *_rest in TUNE_STATS if col in spec}


def throw_damage(display):
    """What a thrown ``display`` is built to take off a body."""
    return dict(melee_specs())[display][THROW_DAMAGE_COLUMN]
