"""The stars: the catalogue, the sky's frame, the dots' size, T_NightSkyStars."""

import math

import unreal

from combat.verify.common import check, load
from world import world_config as cfg
from world.paths import STARS_TEXTURE_PATH
from world.star_catalogue import load_stars
from world.star_map import (
    compass, direction_uv, elevation_deg, moon_width_deg, rasterise, star_amplitude,
    star_direction, star_texel, star_width_deg,
)

SIRIUS, POLE_STAR, BETELGEUSE, RIGEL, VEGA = "Alp CMa", "Alp UMi", "Alp Ori", "Bet Ori", "Alp Lyr"


def _dot(a, b):
    return sum(x * y for x, y in zip(a, b))


def _check_catalogue(stars, named):
    sirius = stars[0]
    check("the catalogue is the real sky: the naked eye's nine thousand stars, Sirius "
          "the brightest, where Sirius is",
          len(stars) > 9000 and sirius.name == SIRIUS
          and abs(sirius.ra_deg - 101.287) < 0.01 and abs(sirius.dec_deg + 16.716) < 0.01,
          f"{len(stars)} stars, first {sirius}")
    check("the catalogue has the stars the checks stand on",
          all(n in named for n in (POLE_STAR, BETELGEUSE, RIGEL, VEGA)),
          str(sorted(named)[:5]))


def _check_frame(named):
    east, south, _up = compass()
    noon = math.radians(cfg.SUNRISE_YAW_DEG + 90.0 + 180.0)   # the light's yaw, turned round
    check("south is where the sun stands at noon",
          _dot(south, (math.cos(noon), math.sin(noon), 0.0)) > 0.9999, str(south))
    pole = star_direction(named[POLE_STAR].ra_deg, named[POLE_STAR].dec_deg)
    check("the Pole Star stands due north, as high as the latitude",
          _dot(pole, south) < 0.0 and abs(_dot(pole, east)) < 0.02
          and abs(elevation_deg(pole) - cfg.STAR_LATITUDE_DEG) < 1.0,
          f"{pole}, {elevation_deg(pole):.1f} deg up")
    bet = star_direction(named[BETELGEUSE].ra_deg, named[BETELGEUSE].dec_deg)
    rig = star_direction(named[RIGEL].ra_deg, named[RIGEL].dec_deg)
    check("Orion is up in the south, upright: Betelgeuse above Rigel and to its east",
          _dot(bet, south) > 0.0 and elevation_deg(rig) > 10.0
          and elevation_deg(bet) > elevation_deg(rig) and _dot(bet, east) > _dot(rig, east),
          f"Betelgeuse {elevation_deg(bet):.1f}, Rigel {elevation_deg(rig):.1f} deg up")
    worst = 0.0
    for name in (SIRIUS, POLE_STAR, BETELGEUSE, RIGEL, VEGA):
        s = named[name]
        u, v = direction_uv(star_direction(s.ra_deg, s.dec_deg))
        worst = max(worst, abs(u - s.ra_deg / 360.0), abs(v - (90.0 - s.dec_deg) / 180.0))
    check("the shader's coordinate for a star's direction is the star's place on the map",
          worst < 1e-9, f"worst error {worst:.2e}")


def _check_size(stars):
    moon = moon_width_deg()
    widest = max(star_width_deg(s.vmag) for s in stars)
    faint = star_width_deg(cfg.STAR_MAX_MAG)
    check("a star is small beside the moon: the brightest under a sixth of its width, "
          "a faint one under a twelfth",
          widest == star_width_deg(stars[0].vmag) and widest < moon / 6.0
          and faint < moon / 12.0,
          f"moon {moon:.2f}, brightest star {widest:.2f}, faint star {faint:.2f} deg")
    check("the faintest star drawn still shows in 8 bits",
          star_amplitude(cfg.STAR_MAX_MAG) > 2.0 / 1024.0
          and star_amplitude(stars[0].vmag) == 1.0,
          f"{star_amplitude(cfg.STAR_MAX_MAG):.4f}")


def _check_drawing(stars, named):
    width, height = cfg.STAR_MAP_SIZE
    texels = rasterise(stars, width, height)
    drawn = sum(1 for s in stars if s.vmag <= cfg.STAR_MAX_MAG)
    lit = len(texels) / float(width * height)
    check("the map is dark but for the stars: each a few texels, under 2% of it lit",
          drawn > 8000 and len(texels) > drawn and lit < 0.02,
          f"{drawn} stars on {len(texels)} texels ({lit:.2%})")
    at = [max(texels.get(star_texel(named[n], width, height), [0.0])) for n in (SIRIUS, VEGA)]
    check("a bright star is drawn where the catalogue puts it", min(at) > 0.5, str(at))


def _check_texture():
    tex = load(STARS_TEXTURE_PATH)
    check("T_NightSkyStars exists", tex is not None, STARS_TEXTURE_PATH)
    if tex is None:
        return
    size = (tex.blueprint_get_size_x(), tex.blueprint_get_size_y())
    check("T_NightSkyStars is the whole map", size == tuple(cfg.STAR_MAP_SIZE), str(size))
    got = {k: tex.get_editor_property(k) for k in
           ("srgb", "never_stream", "mip_gen_settings", "compression_settings")}
    check("T_NightSkyStars keeps every texel: uncompressed, no mips, never streamed",
          got["srgb"] and got["never_stream"]
          and got["mip_gen_settings"] == unreal.TextureMipGenSettings.TMGS_NO_MIPMAPS
          and got["compression_settings"] == unreal.TextureCompressionSettings.TC_EDITOR_ICON,
          str(got))


def run():
    stars = load_stars()
    named = {s.name: s for s in reversed(stars)}       # the brightest of a name wins
    _check_catalogue(stars, named)
    _check_frame(named)
    _check_size(stars)
    _check_drawing(stars, named)
    _check_texture()
