"""Build the game's sound: the assets, where each sound is played from, and
how loud each is. Run with:

    python3 Scripts/dev/uepy.py Scripts/build_sound.py

Everything it writes is defined in the Sound package (Scripts/Sound/__init__.py
maps it): one module per area -- sound_weapons, sound_monsters, sound_items,
sound_world -- each a table of sounds and of the Blueprint variables that play
them. After changing a mapping, a take (selection.py, then
install_selected_sounds.py), an attenuation profile or a volume
(sound_tuning.csv), this is the only build to run. A new variable, component
or play site in a Blueprint's graph is that Blueprint's builder's.
"""

import os
import sys

_SCRIPTS = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _SCRIPTS)
for _name in [m for m in sys.modules
              if m.split(".")[0] in ("uebp", "combat", "npc", "world", "survival",
                                     "graphics_menu", "forest_generator", "Sound")]:
    del sys.modules[_name]

from Sound.build import (                                         # noqa: E402
    apply_sound_bindings, apply_sound_volumes, build_sound_assets)


def main():
    build_sound_assets()
    apply_sound_bindings()
    apply_sound_volumes()


if __name__ == "__main__":
    main()
