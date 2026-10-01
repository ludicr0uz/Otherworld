"""The night sky in a game: at midnight the dome draws the real stars, from
T_NightSkyStars, and the star map's frame agrees with the game's own sky --
the Pole Star stands in the north, opposite where the moon culminates.

Run with --windowed and OW_SKY_SHOTS=1 to save pictures of the sky to
Saved/Screenshots/MacEditor: towards the moon, the Pole Star and Orion.
"""

import math
import os

import unreal

from world import world_config as cfg
from world.paths import DAY_NIGHT_BP_PATH, DAY_NIGHT_CLASS_PATH, STARS_TEXTURE_PATH
from world.sky_material import STARS_PARAM
from world.star_catalogue import load_stars
from world.star_map import elevation_deg, star_direction

WRITABLE = [(DAY_NIGHT_BP_PATH, "Clock")]

SHOTS = bool(os.environ.get("OW_SKY_SHOTS"))
MIDNIGHT_S = cfg.DAY_LENGTH_S + cfg.NIGHT_LENGTH_S / 2
POLE_STAR, ORION = "Alp UMi", "Alp Ori"


def _look(p, cycle, toward):
    """Turn the view to a world direction at midnight, and picture it."""
    p.set(cycle, "Clock", float(MIDNIGHT_S))
    pc = unreal.GameplayStatics.get_player_controller(p.pawn(), 0)
    pc.set_control_rotation(unreal.Vector(*toward).rotator())
    yield 1.0
    if SHOTS:
        unreal.SystemLibrary.execute_console_command(p.pawn(), "shot")
        yield 1.0


def probe(p):
    cycle = p.actor_of(DAY_NIGHT_CLASS_PATH)
    p.set(cycle, "Clock", float(MIDNIGHT_S))
    yield 0.3
    sky = p.get(cycle, "SkyMaterial")
    p.check("midnight: the stars are out",
            sky is not None and sky.get_scalar_parameter_value("StarBrightness") > 0.0)
    tex = sky.get_texture_parameter_value(STARS_PARAM) if sky else None
    p.check("the dome draws the star map",
            tex is not None and tex.get_path_name().split(".")[0] == STARS_TEXTURE_PATH,
            str(tex.get_path_name() if tex else None))

    by_name = {s.name: s for s in reversed(load_stars())}
    pole = star_direction(by_name[POLE_STAR].ra_deg, by_name[POLE_STAR].dec_deg)
    orion = star_direction(by_name[ORION].ra_deg, by_name[ORION].dec_deg)
    moon = p.get(cycle, "Moon").get_forward_vector() * -1.0
    flat = math.hypot(pole[0], pole[1]) * math.hypot(moon.x, moon.y)
    across = (pole[0] * moon.x + pole[1] * moon.y) / flat
    p.check("the Pole Star stands in the north, opposite the midnight moon, as high as "
            "the latitude",
            across < -0.999 and abs(elevation_deg(pole) - cfg.STAR_LATITUDE_DEG) < 1.0,
            f"cos {across:.4f}, {elevation_deg(pole):.1f} deg up")

    for toward in ((moon.x, moon.y, moon.z), pole, orion):
        yield from _look(p, cycle, toward)
