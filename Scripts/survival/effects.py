"""GE_Starving and GE_Dehydrated: the debuffs, as Gameplay Ability System
GameplayEffects.

A debuff is an INFINITE GameplayEffect. BP_SurvivalComponent applies it to
its owner's AbilitySystemComponent when a bar reaches zero and removes it
(RemoveActiveGameplayEffectBySourceEffect) when the bar comes back up. Being a
real active effect is what makes it a debuff in the engine's own terms rather
than a bool on a component: any actor with an AbilitySystemComponent -- the
wanderers carry one too -- can have it applied, the ability system's debugger
(`showdebug abilitysystem`) lists it, and its granted tags are what the health
component and the HUD query.

WHY THE TAGS ARE NOT ON THE ASSET
---------------------------------
Since UE 5.3 a GameplayEffect grants tags through a
TargetTagsGameplayEffectComponent, and that component's tag container is a
PRIVATE property, which Unreal Python cannot read or write (probed: "Failed to
find property"). The deprecated InheritableOwnedTagsContainer is still
writable, but the engine only upgrades it into the component for assets saved
before the Modular53 version, which a freshly built asset never is -- probed
four ways, none took. So the tags are attached to the SPEC at application
time with AbilitySystemBlueprintLibrary.AddGrantedTag (survival/debuffs.py).
That is a supported GAS route -- FGameplayEffectSpec::DynamicGrantedTags --
and the tags are granted and revoked with the effect exactly as asset tags
would be. The price is that the GE asset alone does not say which tags it
grants; survival.tuning.DEBUFFS is where that is written down.
"""

import unreal

from combat.graph import BEL, _assets, _create_blueprint, _log
from survival.paths import DEHYDRATED_GE_PATH, STARVING_GE_PATH

DEBUFF_EFFECT_PATHS = {
    "StarvingEffect": STARVING_GE_PATH,
    "DehydratedEffect": DEHYDRATED_GE_PATH,
}


def build_debuff_effects():
    """Both debuffs, INFINITE, with nothing else configured.

    Returns {component variable name: GE blueprint}, the shape
    build_survival_component's defaults are written from.
    """
    built = {}
    for var, path in DEBUFF_EFFECT_PATHS.items():
        bp = _create_blueprint(path, unreal.GameplayEffect)
        cdo = unreal.get_default_object(BEL.generated_class(bp))
        cdo.set_editor_property("duration_policy",
                                unreal.GameplayEffectDurationType.INFINITE)
        if not BEL.compile_blueprint(bp):
            raise RuntimeError(f"{path} failed to compile")
        _assets().save_loaded_asset(bp)
        got = unreal.get_default_object(BEL.generated_class(bp)).get_editor_property(
            "duration_policy")
        if got != unreal.GameplayEffectDurationType.INFINITE:
            raise RuntimeError(f"{path}: duration policy did not stick ({got})")
        built[var] = bp
        _log(f"built {path} (infinite)")
    return built
