"""The night sky's star map: where each real star stands, and how it is drawn.

Two things, both plain Python (no `unreal`), so the verifier and the probe can
ask the same questions the shader and the texture answer:

  where   The stars are fixed to the celestial sphere, and the sphere to the
          world: its pole stands STAR_LATITUDE_DEG above the northern horizon
          and the stars on the southern meridian are those of right ascension
          STAR_SIDEREAL_HOUR. North is the side the sun never crosses: it
          culminates in the south (day_night_graph turns its LIGHT to
          SUNRISE_YAW_DEG + angle, so the body is opposite that). sky_basis()
          is that frame, star_direction() a star's world direction, and
          direction_uv() the texture coordinate M_DayNightSky's StarUV node
          computes for a view ray (sky_material.STAR_UV_HLSL does these sums).

  how     T_NightSkyStars is an equirectangular map of the whole sphere: u is
          right ascension, v runs from the north pole down. rasterise() draws
          each star as a small Gaussian dot whose brightness follows its
          magnitude and whose tint follows its B-V colour. A dot is widened
          along u by 1/cos(declination), so it is round on the sky.
"""

import math

from world import world_config as cfg


def _yaw(deg):
    r = math.radians(deg)
    return (math.cos(r), math.sin(r), 0.0)


def _mix(a, ka, b, kb):
    return tuple(x * ka + y * kb for x, y in zip(a, b))


def compass():
    """World unit vectors (east, south, up). The sun rises in the east."""
    east = cfg.SUNRISE_YAW_DEG + 180.0
    return _yaw(east), _yaw(east + 90.0), (0.0, 0.0, 1.0)


def sky_basis():
    """World unit vectors (ex, ey, ez) of the equatorial frame: ex towards
    right ascension 0 on the equator, ey towards 6 h, ez the north pole."""
    east, south, up = compass()
    lat = math.radians(cfg.STAR_LATITUDE_DEG)
    lst = math.radians(cfg.STAR_SIDEREAL_HOUR * 15.0)
    pole = _mix(south, -math.cos(lat), up, math.sin(lat))
    meridian = _mix(south, math.sin(lat), up, math.cos(lat))
    ex = _mix(meridian, math.cos(lst), east, -math.sin(lst))
    ey = _mix(meridian, math.sin(lst), east, math.cos(lst))
    return ex, ey, pole


def star_direction(ra_deg, dec_deg):
    """The world direction (viewer -> star) of a point of the sphere."""
    ex, ey, ez = sky_basis()
    ra, dec = math.radians(ra_deg), math.radians(dec_deg)
    return tuple(math.cos(dec) * (math.cos(ra) * x + math.sin(ra) * y) + math.sin(dec) * z
                 for x, y, z in zip(ex, ey, ez))


def direction_uv(v):
    """The star map's (u, v) for a world view direction: the StarUV node's sums."""
    d = [sum(a * b for a, b in zip(v, axis)) for axis in sky_basis()]
    u = (math.atan2(d[1], d[0]) / (2.0 * math.pi)) % 1.0
    return u, math.acos(max(-1.0, min(1.0, d[2]))) / math.pi


def elevation_deg(v):
    return math.degrees(math.asin(max(-1.0, min(1.0, v[2]))))


# ─── How a star is drawn ─────────────────────────────────────────────────────

def star_amplitude(vmag):
    """A star's peak brightness, 0-1: 1 at STAR_FULL_MAG and brighter, falling
    with magnitude (a real star's light falls 2.512x a magnitude; STAR_CONTRAST
    under 1 flattens that so the faint ones still show)."""
    return min(1.0, 10.0 ** (-0.4 * cfg.STAR_CONTRAST * (vmag - cfg.STAR_FULL_MAG)))


def star_sigma_deg(vmag):
    """A star's Gaussian radius in degrees: STAR_SIZE_DEG, and more the
    brighter it is than STAR_SIZE_MAG, up to STAR_SIZE_MAX times."""
    over = max(0.0, cfg.STAR_SIZE_MAG - vmag)
    return cfg.STAR_SIZE_DEG * min(cfg.STAR_SIZE_MAX, 1.0 + cfg.STAR_SIZE_GROWTH * over)


def star_width_deg(vmag):
    """How wide a star reads on the sky: 4 sigma, the dot down to 13% of its peak."""
    return 4.0 * star_sigma_deg(vmag)


def moon_width_deg():
    """The moon's disc across, from the shader's edge (world_config.MOON_DISC_COS)."""
    return 2.0 * math.degrees(math.acos(sum(cfg.MOON_DISC_COS) / 2.0))


def star_color(bv):
    """A linear RGB tint for a B-V index: blue-white, white, orange."""
    t = max(-0.3, min(1.9, bv))
    if t < 0.6:
        k = (t + 0.3) / 0.9
        return _mix(cfg.STAR_COLOR_BLUE, 1.0 - k, cfg.STAR_COLOR_WHITE, k)
    k = (t - 0.6) / 1.3
    return _mix(cfg.STAR_COLOR_WHITE, 1.0 - k, cfg.STAR_COLOR_ORANGE, k)


def star_texel(star, width, height):
    """The (x, y) texel a star's centre falls in."""
    return (int(star.ra_deg / 360.0 * width) % width,
            min(height - 1, int((90.0 - star.dec_deg) / 180.0 * height)))


def rasterise(stars, width, height):
    """Draw the stars no fainter than STAR_MAX_MAG. Returns {(x, y): [r, g, b]},
    linear and unclamped, for the texels any star touches."""
    texels = {}
    deg_per_texel = 180.0 / height
    for star in stars:
        if star.vmag > cfg.STAR_MAX_MAG:
            continue
        amp = star_amplitude(star.vmag)
        rgb = star_color(star.bv)
        sy = star_sigma_deg(star.vmag) / deg_per_texel
        sx = sy / max(0.05, math.cos(math.radians(star.dec_deg)))
        cx = star.ra_deg / 360.0 * width - 0.5          # in texel-centre units
        cy = (90.0 - star.dec_deg) / 180.0 * height - 0.5
        rx, ry = int(math.ceil(3.0 * sx)), int(math.ceil(3.0 * sy))
        for y in range(max(0, int(round(cy)) - ry), min(height, int(round(cy)) + ry + 1)):
            for x in range(int(round(cx)) - rx, int(round(cx)) + rx + 1):
                g = amp * math.exp(-0.5 * (((x - cx) / sx) ** 2 + ((y - cy) / sy) ** 2))
                if g < 1.0 / 1024.0:
                    continue
                px = texels.setdefault((x % width, y), [0.0, 0.0, 0.0])
                for i in range(3):
                    px[i] += g * rgb[i]
    return texels
