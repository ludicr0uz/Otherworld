"""verify.near_clip -- the camera's near plane (seat_tuning.NEAR_CLIP_CM) is
set where the engine reads it: Config/DefaultEngine.ini, in the engine's own
section, once.

An unknown key or a wrong section is ignored without a word, so that the game
took it, and that no hand is cut open down any gun's sights, is
probes/probe_sight_near_clip.py.
"""

import os

import unreal

from combat.seat_tuning import (
    NEAR_CLIP_CM, NEAR_CLIP_DEFAULT_CM, NEAR_CLIP_INI, NEAR_CLIP_KEY, NEAR_CLIP_SECTION,
)
from combat.verify.common import check


def _ini_values(path, section, key):
    """Every value `key` is given in `section` of the ini at `path`, as text.
    Not configparser: an engine ini repeats keys (+Key=...)."""
    found, inside = [], False
    with open(path, encoding="utf-8") as ini:
        for line in ini:
            line = line.strip()
            if line.startswith("["):
                inside = line == f"[{section}]"
            elif inside and "=" in line and not line.startswith(";"):
                name, value = line.split("=", 1)
                if name.strip().lstrip("+-.!") == key:
                    found.append(value.strip())
    return found


def check_near_clip():
    path = os.path.join(unreal.Paths.project_dir(), NEAR_CLIP_INI)
    got = _ini_values(path, NEAR_CLIP_SECTION, NEAR_CLIP_KEY)
    check(f"{NEAR_CLIP_INI} sets the camera's near plane to {NEAR_CLIP_CM:g} cm, "
          f"once ([{NEAR_CLIP_SECTION}] {NEAR_CLIP_KEY}): the hands down the "
          "pistol's sights are not cut open",
          len(got) == 1 and abs(float(got[0]) - NEAR_CLIP_CM) < 1e-6, str(got))
    check(f"...nearer the eye than the engine's default {NEAR_CLIP_DEFAULT_CM:g} cm, "
          "and not so near that depth is wasted on it",
          1.0 <= NEAR_CLIP_CM < NEAR_CLIP_DEFAULT_CM, f"{NEAR_CLIP_CM:g}")


def run():
    check_near_clip()
