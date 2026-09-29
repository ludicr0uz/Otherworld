"""BP_ConsumableItem and the two consumables."""

import unreal

from combat.paths import ITEM_BP_PATH
from combat.verify.common import BEL, cdo, check, component_template, components, load
from survival.consumable_specs import consumable_specs
from survival.paths import CONSUMABLE_BP_PATH


def run():
    item = load(ITEM_BP_PATH)
    base = load(CONSUMABLE_BP_PATH)
    check("BP_ConsumableItem exists", base is not None)
    if not base:
        return
    check("BP_ConsumableItem is a BP_WeaponItem, so the inventory takes it",
          base.get_blueprint_parent_class() == BEL.generated_class(item))
    check("BP_WeaponItem itself is not Consumable",
          cdo(item).get_editor_property("Consumable") is False)
    for spec in consumable_specs():
        bp = load(spec["path"])
        name = spec["display"]
        check(f"{name} exists", bp is not None)
        if not bp:
            continue
        d = cdo(bp)
        check(f"{name} is Consumable", d.get_editor_property("Consumable") is True)
        check(f"{name} starts Dropped, so a placed one can be picked up",
              d.get_editor_property("Dropped") is True)
        for var, want in (("HungerRestore", spec["hunger"]),
                          ("ThirstRestore", spec["thirst"])):
            got = d.get_editor_property(var)
            check(f"{name}.{var} is the float {want}",
                  isinstance(got, float) and abs(got - want) < 1e-6, repr(got))
        check(f"{name} restores something",
              spec["hunger"] + spec["thirst"] > 0)
        check(f"{name} is named {name!r}", d.get_editor_property("DisplayName") == name)
        # (AdsZoom - 1) is a divisor in the ADS speed and the scope fade.
        check(f"{name}'s AdsZoom is above 1", d.get_editor_property("AdsZoom") > 1.0)
        check(f"{name} has an inventory icon", d.get_editor_property("Icon") is not None)
        check(f"{name} has a ready pose", d.get_editor_property("AimPose") is not None)
        check(f"{name} uses no ammunition", d.get_editor_property("UsesAmmo") is False)
        parts = [p[0] for p in spec["parts"]]
        present = set(components(bp))
        check(f"{name} has its parts {parts}", set(parts) <= present,
              str(sorted(present)))
        blocking = [p for p in parts
                    if (t := component_template(bp, p)) is not None
                    and t.get_collision_enabled() != unreal.CollisionEnabled.NO_COLLISION]
        check(f"{name}'s parts collide with nothing", not blocking, str(blocking))
