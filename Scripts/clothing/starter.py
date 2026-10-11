"""The garment a player starts in: the pants, written onto the weapon
component as the class its BeginPlay wears
(combat/weapon_component/starter_worn.py).

The component is built before the garments are (build_weapons_and_combat.py,
then build_clothing.py), so its build leaves the class as it found it and
this fills it in, as build_survival.py fills in the campfire's.
"""

from combat.log import _log
from combat.paths import WEAPON_COMP_BP_PATH
from combat.wear_tuning import STARTER_PANTS_CLASS_VAR
from clothing.specs import GARMENTS
from uebp.graph import BEL, _apply_defaults, _must_load

STARTER = "Pants"       # a Garment's display name


def starter_garment():
    return next(g for g in GARMENTS if g.display == STARTER)


def install_starter():
    """BP_WeaponComponent.StarterPantsClass = BP_Pants."""
    garment = starter_garment()
    _apply_defaults(_must_load(WEAPON_COMP_BP_PATH),
                    {STARTER_PANTS_CLASS_VAR: BEL.generated_class(_must_load(garment.path))})
    _log(f"{WEAPON_COMP_BP_PATH}.{STARTER_PANTS_CLASS_VAR} -> {garment.path}")
