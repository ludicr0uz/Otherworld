"""What a player starts out wearing: the weapon component's StarterPantsClass
is BP_Pants, a garment drawn when worn. That its BeginPlay spawns it into
Worn and draws it is the combat verifier's (combat/verify/wear.py,
wear_draw.py): the graph is that package's."""

from combat.paths import WEAPON_COMP_BP_PATH
from combat.verify.common import cdo, check, load
from combat.wear_tuning import STARTER_PANTS_CLASS_VAR
from clothing.starter import starter_garment


def run():
    garment = starter_garment()
    got = cdo(load(WEAPON_COMP_BP_PATH)).get_editor_property(STARTER_PANTS_CLASS_VAR)
    check(f"{STARTER_PANTS_CLASS_VAR} points at {garment.asset}_C",
          got is not None and got.get_path_name() == garment.class_path, str(got))
    check("the garment a player starts in is drawn on the body, in the pants' slot",
          garment.worn is not None and garment.slot == "pants", str(garment))
