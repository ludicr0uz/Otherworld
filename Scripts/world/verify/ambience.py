"""The forest's sound: the three beds on BP_DayNightCycle (Sound/sound_world.py)."""

import unreal

from combat.verify.common import by_pins, check, component_template, graph, load
from Sound.sound_def import BED_DIR
from Sound.sound_world import BEDS, BED_DAY_COMP, BED_NIGHT_COMP
from world.paths import DAY_NIGHT_BP_PATH


def check_beds(bp):
    for name, wave in BEDS:
        comp = component_template(bp, name)
        sound = comp.get_editor_property("sound") if comp else None
        check(f"{name} is an AudioComponent playing {wave} from the level's start",
              isinstance(comp, unreal.AudioComponent) and sound is not None
              and sound.get_path_name().split(".")[0] == f"{BED_DIR}/{wave}"
              and comp.get_editor_property("auto_activate"), str(sound))
        check(f"{name} is not placed: it is heard all round, wherever the actor stands",
              comp is not None and not comp.get_editor_property("allow_spatialization"))
        asset = load(f"{BED_DIR}/{wave}")
        # A bed is the one kind of wave with no attenuation, and the one kind
        # that is stereo: both on purpose, and neither true of any other.
        check(f"{wave} loops, plays on when silent, and carries no attenuation",
              asset is not None and asset.get_editor_property("looping")
              and asset.get_editor_property("virtualization_mode")
              == unreal.VirtualizationMode.PLAY_WHEN_SILENT
              and asset.get_editor_property("attenuation_settings") is None,
              str(asset))
        check(f"{wave} is stereo", asset is not None
              and asset.get_editor_property("num_channels") == 2,
              str(asset.get_editor_property("num_channels") if asset else None))
    fades = by_pins(graph(bp).list_all_nodes(), "NewVolumeMultiplier")
    check("Tick sets two volumes: the day's bed and the night's (the wind plays on)",
          len(fades) == 2, f"{len(fades)} SetVolumeMultiplier node(s)")


def run():
    bp = load(DAY_NIGHT_BP_PATH)
    if bp is not None:
        check_beds(bp)
