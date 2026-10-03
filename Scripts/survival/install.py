"""Installing on the characters: an AbilitySystemComponent on the player and
on the wanderer, and BP_SurvivalComponent on the player.

Both characters get an ability system because a debuff is something any
character can carry: GE_Starving and GE_Dehydrated are applied to an
AbilitySystemComponent, and BP_HealthComponent drains any owner whose ASC has
the drain tag. Only the player gets hungry, so only the player gets the
survival component that applies them.

This drops and re-adds only its own two component names, so it neither fights
nor depends on combat.install -- either builder can be re-run alone.
"""

import unreal

from combat.log import _log
from uebp.graph import BEL, _add_component, _assets, _drop_components, _root_handle
from combat.paths import CHARACTER_BP_PATH, NPC_BP_PATH
from forest_generator.npc_placement import NPC_VARIANTS
from survival.paths import ASC_COMPONENT, SURVIVAL_COMPONENT


def _install(path, parts, required=True):
    eas = _assets()
    bp = eas.load_asset(path)
    if not bp:
        if required:
            raise RuntimeError(f"could not load {path}")
        # The same tolerance combat.install.install_on_npc has: on a fresh
        # clone the wanderer is built after this (see RESTORE_ORDER), so re-run
        # this builder once build_npc_blueprints.py has made it.
        _log(f"note: {path} not found -- skipping; re-run after it exists")
        return
    _drop_components(bp, {name for name, _cls in parts})
    for name, cls in parts:
        _add_component(bp, _root_handle(bp), cls, name)
    if not BEL.compile_blueprint(bp):
        raise RuntimeError(f"{path} failed to compile")
    eas.save_loaded_asset(bp)
    _log(f"{path.rsplit('/', 1)[1]}: {', '.join(n for n, _c in parts)} installed")


def install_survival(survival_bp):
    asc = unreal.AbilitySystemComponent.static_class()
    _install(CHARACTER_BP_PATH, ((ASC_COMPONENT, asc),
                                 (SURVIVAL_COMPONENT, BEL.generated_class(survival_bp))))
    _install(NPC_BP_PATH, ((ASC_COMPONENT, asc),), required=False)
    _resave_variants()


def _resave_variants():
    """Recompile and save each wanderer variant (BP_Wanderer_<Creature>).

    They are children of BP_ForestWanderer, so changing the parent's components
    recompiles them in memory and leaves them dirty -- the editor then asks to
    save them, and a cold build would leave them stale on disk. Saving here is
    what makes the inherited AbilitySystem part of the saved variant.
    """
    eas = _assets()
    for variant in NPC_VARIANTS:
        bp = eas.load_asset(variant.blueprint)
        if not bp:
            continue
        if not BEL.compile_blueprint(bp):
            raise RuntimeError(f"{variant.blueprint} failed to compile")
        eas.save_loaded_asset(bp, False)
        _log(f"{variant.blueprint.rsplit('/', 1)[1]}: recompiled and saved")
