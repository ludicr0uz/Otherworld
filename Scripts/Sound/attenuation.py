"""The USoundAttenuation assets, one per profile (sound_def.py, and the
roar's in sound_monsters.py), and every SoundWave's link to its own.
"""

import unreal

from Sound.catalog import ATTENUATIONS, SOUND_ATTENUATION
from combat.log import _log
from Sound.sound_def import (
    ATT_DB_AT_MAX, ATT_LPF_FAR_HZ, ATT_LPF_NEAR_HZ, AUDIBLE_LIMIT_CM, CREATURE_AUDIO_DIR,
    WEAPON_AUDIO_DIR)
from uebp.graph import _assets


def build_sound_attenuations():
    """Build the USoundAttenuation assets, one per AttenuationProfile.

    Re-authored in place every run rather than skipped when present: that is
    the lesson build_materials() had to learn the hard way -- a builder that
    leaves an existing asset alone can never change a recipe, and since nothing
    under Content/ is committed, the asset on disk is only ever as good as the
    last run that actually wrote it.

    Returns {name: asset} for apply_attenuation().
    """
    tools = unreal.AssetToolsHelpers.get_asset_tools()
    eas = _assets()
    built = {}
    for profile in ATTENUATIONS:
        if profile.audible_cm > AUDIBLE_LIMIT_CM:
            raise RuntimeError(
                f"{profile.name} would be audible from "
                f"{profile.audible_cm / 100.0:.0f} m, over the "
                f"{AUDIBLE_LIMIT_CM / 100.0:.0f} m ceiling")
        asset = (eas.load_asset(profile.path)
                 if eas.does_asset_exist(profile.path)
                 else tools.create_asset(profile.name, CREATURE_AUDIO_DIR,
                                         unreal.SoundAttenuation,
                                         unreal.SoundAttenuationFactory()))
        if asset is None:
            raise RuntimeError(f"could not create {profile.path}")
        # The struct read back off the asset is a COPY -- the same trap the
        # LayeredBoneBlend node's inner FAnimNode has -- so it is read,
        # changed, and written back wholesale.
        at = asset.get_editor_property("attenuation")
        at.set_editor_property("attenuate", True)
        at.set_editor_property("spatialize", True)
        at.set_editor_property(
            "distance_algorithm",
            unreal.AttenuationDistanceModel.LINEAR if profile.linear
            else unreal.AttenuationDistanceModel.NATURAL_SOUND)
        at.set_editor_property("attenuation_shape",
                               unreal.AttenuationShape.SPHERE)
        # Only X is read for a sphere; Y and Z are the box and capsule extents.
        at.set_editor_property("attenuation_shape_extents",
                               unreal.Vector(profile.radius_cm, 0.0, 0.0))
        at.set_editor_property("falloff_distance", profile.falloff_cm)
        # Spelled d_b_ and not db_: the UPROPERTY is dBAttenuationAtMax and
        # the Python name is generated one word boundary at a time.
        at.set_editor_property("d_b_attenuation_at_max", ATT_DB_AT_MAX)
        at.set_editor_property(
            "spatialization_algorithm",
            unreal.SoundSpatializationAlgorithm.SPATIALIZATION_DEFAULT)
        at.set_editor_property("attenuate_with_lpf", profile.air_absorption)
        if profile.air_absorption:
            at.set_editor_property("lpf_radius_min", profile.radius_cm)
            at.set_editor_property("lpf_radius_max", profile.audible_cm)
            at.set_editor_property("lpf_frequency_at_min", ATT_LPF_NEAR_HZ)
            at.set_editor_property("lpf_frequency_at_max", ATT_LPF_FAR_HZ)
        asset.set_editor_property("attenuation", at)
        eas.save_loaded_asset(asset)
        built[profile.name] = asset
        _log(f"built {profile.path} "
             f"(full volume to {profile.radius_cm:.0f} cm, silent past "
             f"{profile.audible_cm / 100.0:.0f} m"
             + (", air absorption on)" if profile.air_absorption else ")"))
    return built


def apply_attenuation(attenuations):
    """Point every SoundWave in the two audio folders at its profile.

    On the ASSET, not on the PlaySoundAtLocation nodes. Both would work -- the
    node carries an AttenuationSettings pin that overrides the asset -- but the
    pin has to be wired at every call site, and there are five of those across
    three Blueprints authored by two different builders, so the pin is five
    chances to miss one and the asset is one write per sound.

    It sweeps the FOLDERS rather than SOUND_NAMES + CREATURE_SOUND_NAMES, and
    raises on a wave it has no profile for. That is the check that makes "no
    world sound was left behind" true rather than merely intended: a sound
    added to either tuple, or dropped into the folder by hand, stops the build
    instead of shipping unattenuated.
    """
    eas = _assets()
    orphans, applied = [], {}
    for folder in (WEAPON_AUDIO_DIR, CREATURE_AUDIO_DIR):
        for ref in eas.list_assets(folder, recursive=False):
            asset = eas.load_asset(ref)
            if not isinstance(asset, unreal.SoundWave):
                continue
            profile = SOUND_ATTENUATION.get(asset.get_name())
            if profile is None:
                orphans.append(asset.get_name())
                continue
            asset.set_editor_property("attenuation_settings",
                                      attenuations[profile.name])
            eas.save_loaded_asset(asset)
            applied.setdefault(profile.name, []).append(asset.get_name())
    if orphans:
        raise RuntimeError(
            f"no attenuation profile for {sorted(orphans)} -- add them to "
            f"SOUND_ATTENUATION, or they ship audible from anywhere")
    for name, names in sorted(applied.items()):
        _log(f"{name} -> {len(names)} sound(s): {', '.join(sorted(names))}")
    return applied
