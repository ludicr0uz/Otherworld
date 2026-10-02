"""GE_Starving, GE_Dehydrated and GE_Bleeding: the debuffs, as Gameplay
Ability System GameplayEffects.

A debuff is an INFINITE GameplayEffect. BP_SurvivalComponent applies it to
its owner's AbilitySystemComponent when a bar reaches zero and removes it
(RemoveActiveGameplayEffectBySourceEffect) when the bar comes back up. Being a
real active effect is what makes it a debuff in the engine's own terms rather
than a bool on a component: any actor with an AbilitySystemComponent -- the
wanderers carry one too -- can have it applied, the ability system's debugger
(`showdebug abilitysystem`) lists it, and its granted tags are what the health
component and the HUD query.

A debuff that ends by itself is the same thing with a DURATION: GE_Bleeding
lasts combat.tuning.BLEED_DURATION_S and the ability system takes it off, and
its tag with it. Nothing syncs it to a bar; a hit applies it
(survival/on_hit_graph.py).

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
from combat.tuning import BLEED_DURATION_S
from survival.paths import BLEEDING_GE_PATH, DEHYDRATED_GE_PATH, STARVING_GE_PATH

DEBUFF_EFFECT_PATHS = {
    "StarvingEffect": STARVING_GE_PATH,
    "DehydratedEffect": DEHYDRATED_GE_PATH,
}


# The debuffs that wear off: {GameplayEffect path: seconds it lasts}.
TIMED_EFFECT_PATHS = {
    BLEEDING_GE_PATH: BLEED_DURATION_S,
}


def effect_duration_s(cdo):
    """The seconds a GameplayEffect CDO lasts, read off its duration magnitude.
    The struct's fields are not Python properties, so it is read as text."""
    text = cdo.get_editor_property("duration_magnitude").export_text()
    return float(text.split("ScalableFloatMagnitude=(Value=")[1].split(",")[0])


def build_timed_effects():
    """Each timed debuff: HAS_DURATION, lasting its row's seconds."""
    for path, seconds in TIMED_EFFECT_PATHS.items():
        bp = _create_blueprint(path, unreal.GameplayEffect)
        cdo = unreal.get_default_object(BEL.generated_class(bp))
        cdo.set_editor_property("duration_policy",
                                unreal.GameplayEffectDurationType.HAS_DURATION)
        # The magnitude's fields refuse set_editor_property; import_text takes.
        lasts = unreal.GameplayEffectModifierMagnitude()
        if not lasts.import_text("(MagnitudeCalculationType=ScalableFloat,"
                                 f"ScalableFloatMagnitude=(Value={seconds:.6f}))"):
            raise RuntimeError(f"{path}: could not make a {seconds} s duration")
        cdo.set_editor_property("duration_magnitude", lasts)
        if not BEL.compile_blueprint(bp):
            raise RuntimeError(f"{path} failed to compile")
        _assets().save_loaded_asset(bp)
        cdo = unreal.get_default_object(BEL.generated_class(bp))
        policy = cdo.get_editor_property("duration_policy")
        if (policy != unreal.GameplayEffectDurationType.HAS_DURATION
                or abs(effect_duration_s(cdo) - seconds) > 1e-3):
            raise RuntimeError(f"{path}: the duration did not stick "
                               f"({policy}, {effect_duration_s(cdo)} s)")
        _log(f"built {path} (lasts {seconds:g} s)")


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
