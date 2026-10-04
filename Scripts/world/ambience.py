"""The forest's own sound: three beds on BP_DayNightCycle, and the Tick step
that hands the day's over to the night's.

    BedDay     the day's birds          volume = DayAmount
    BedNight   crickets and owls        volume = 1 - DayAmount
    BedWind    the wind, always         volume 1

Three AudioComponents on the cycle actor, each playing one looping stereo
wave (combat/audio.py, BED_NAMES) from the moment the level starts. They are
on the cycle because it is the one actor every level has and the one that
knows DayAmount: the same number that fades the sun into the moon fades the
birds into the crickets, so dusk sounds like dusk for as long as it looks
like it.

A bed has no attenuation and is not at a place: where the actor stands does
not matter. Its loudness is its SoundClass's row on the SOUND SETTINGS tab,
which the component's volume multiplies.

A bed at volume zero goes on playing (the wave's virtualization mode, set
at import), so the night's is in the same place in its two minutes when dusk
comes round as it would have been had it been heard all day.
"""

import unreal

from combat.audio import BED_DAY, BED_DIR, BED_NIGHT, BED_WIND
from uebp.graph import _add_component, _component_object, _drop_components, _must_load, _root_handle
from uebp.nodes.system import FN_SET_VOLUME
from world.day_night_graph import _call, _get, _map
from world import day_night_vars as DV

BED_DAY_COMP, BED_NIGHT_COMP, BED_WIND_COMP = "BedDay", "BedNight", "BedWind"
BEDS = ((BED_DAY_COMP, BED_DAY), (BED_NIGHT_COMP, BED_NIGHT), (BED_WIND_COMP, BED_WIND))


def build_beds(bp):
    """Drop and re-add the three bed components, each with its wave."""
    _drop_components(bp, {name for name, _wave in BEDS})
    root = _root_handle(bp)
    for name, wave in BEDS:
        bed = _component_object(_add_component(bp, root, unreal.AudioComponent, name))
        bed.set_editor_property("sound", _must_load(f"{BED_DIR}/{wave}"))
        bed.set_editor_property("auto_activate", True)
        # All round the player, not at the actor: a bed is not a place.
        bed.set_editor_property("allow_spatialization", False)
        bed.set_editor_property("is_ui_sound", False)


def author_ambience(ed, chain):
    """Extend the Tick chain: the day's bed by DayAmount, the night's by the rest."""
    day = _get(ed, DV.DayAmount)
    night = _map(ed, _get(ed, DV.DayAmount), 0.0, 1.0, 1.0, 0.0)
    birds = chain.step(_call(ed, FN_SET_VOLUME, self=_get(ed, BED_DAY_COMP),
                             NewVolumeMultiplier=day))
    crickets = chain.step(_call(ed, FN_SET_VOLUME, self=_get(ed, BED_NIGHT_COMP),
                                NewVolumeMultiplier=night))
    ed.add_comment_to_nodes(
        "The forest's sound follows the light: the day's bed is as loud as "
        "DayAmount, the night's as 1 - DayAmount. The wind plays on.",
        [birds, crickets])
