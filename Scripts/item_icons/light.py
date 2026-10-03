"""Light an item's passes: the picture compose.py fits to the icon.

A studio shot, worked out per pixel from what the capture wrote:

    shape    the depth pass is a height field (cm towards the viewer), which
             the key light casts shadows across and which closes the model's
             creases to the ambient light (the occlusion)
    diffuse  base colour x (ambient x occlusion + a warm key, shadowed + a
             cool fill from the other side)
    gloss    the key's highlight, and a reflection of the studio (a soft box
             overhead, a dark floor), strongest at grazing angles
    tone     levelled, so a black gun still reads on the HUD's dark slot,
             then rolled off at the top so a highlight never clips flat

The lights are fixed in the camera's space (x right, y up, z towards the
viewer), so every icon is lit from the same side whatever view its item is
shot from. Every number that decides the look is a constant below.
"""

import json
import os

import numpy as np
from PIL import Image

from item_icons.exr import read_channel

KEY_LIGHT = (-0.50, 0.62, 0.60)   # upper left, towards the viewer
KEY = 1.05
KEY_COLOUR = (1.00, 0.96, 0.90)   # warm
FILL_LIGHT = (0.70, -0.25, 0.67)  # lower right
FILL = 0.22
FILL_COLOUR = (0.80, 0.88, 1.00)  # cool
AMBIENT = 0.20
SKY = 0.22                        # extra on faces that look up
HIGHLIGHT = 0.22                  # the key's, Blinn-Phong
HIGHLIGHT_POWER = 36.0
REFLECTION = 0.15                 # of the studio, at a grazing angle
REFLECTION_FACING = 0.10          # of that, on a face square to the viewer
RIM = 0.03                        # on faces turning away from the viewer
EDGE_PX = 2.0                     # of the capture: the outline that takes no gloss

# The shadow the key light casts across the model itself.
SHADOW = 0.62                     # how much of the key a shadowed pixel loses
SHADOW_REACH = 0.16               # of the capture's width: how far one falls
SHADOW_STEPS = 40
SHADOW_BIAS_CM = 0.20             # over the depth's own step (a half float)
SHADOW_SOFT_CM = 0.60             # the height over which it comes on
SHADOW_BLUR = 0.003               # of the capture's width
# The occlusion: how far a pixel lies below its neighbourhood, at each of
# these radii (of the capture's width).
OCCLUSION = 0.75
OCCLUSION_RADII = (0.004, 0.012, 0.035)
OCCLUSION_FLOOR = 0.35            # the ambient a crease keeps

# Levelling: the brightest tenth of the model is brought up to this (never
# down), the hue kept. The FPS bundle's guns are near-black steel, and the
# slot behind an icon is near-black too.
LEVEL_PERCENTILE = 90.0
LEVEL_TO = 0.46
LEVEL_MAX_GAIN = 6.0
SHOULDER = 0.55                   # linear below this, rolled off above it

# What the capture must show before it is lit: a real model, not an empty frame.
MIN_COVERAGE = 0.02               # of the capture, on the model


def _load(folder, name):
    return np.asarray(Image.open(os.path.join(folder, f"{name}.png")).convert("RGBA"),
                      dtype=np.float32) / 255.0


def _unit(v):
    v = np.array(v, dtype=np.float32)
    return v / np.linalg.norm(v)


def _to_srgb(x):
    x = np.clip(x, 0.0, 1.0)
    return np.where(x <= 0.0031308, x * 12.92, 1.055 * np.power(x, 1 / 2.4) - 0.055)


def _shifted(a, dx, dy):
    """``a`` sampled at (x + dx, y + dy), zero where that is off the picture."""
    out = np.zeros_like(a)
    h, w = a.shape
    xs, xd = (slice(dx, w), slice(0, w - dx)) if dx >= 0 else (slice(0, w + dx), slice(-dx, w))
    ys, yd = (slice(dy, h), slice(0, h - dy)) if dy >= 0 else (slice(0, h + dy), slice(-dy, h))
    out[yd, xd] = a[ys, xs]
    return out


def _blur(a, radius):
    """A Gaussian-like blur: three box blurs of ``radius`` pixels, edges held."""
    r = max(1, int(round(radius)))
    for axis in (0, 1):
        for _ in range(3):
            pad = [(r + 1, r) if i == axis else (0, 0) for i in range(2)]
            c = np.cumsum(np.pad(a, pad, mode="edge"), axis=axis, dtype=np.float64)
            n = a.shape[axis]
            hi = np.take(c, range(2 * r + 1, 2 * r + 1 + n), axis=axis)
            lo = np.take(c, range(0, n), axis=axis)
            a = ((hi - lo) / (2 * r + 1)).astype(np.float32)
    return a


def _height(folder, on, width_cm):
    """The model's height field: cm towards the viewer above its furthest
    point, 0 off the model."""
    depth = read_channel(os.path.join(folder, "depth.exr"), "A")
    if depth.shape != on.shape:
        raise RuntimeError(f"{folder}: the depth pass is {depth.shape}, the mask {on.shape}")
    # Off the model the depth is the far plane; a pixel half on it is no
    # depth of the model's either.
    on = on & (depth < 4.0 * width_cm + 1000.0)
    return np.where(on, depth[on].max() - depth, 0.0).astype(np.float32)


def _shadow(height, px_cm, light):
    """0..1 per pixel: how far the key light is blocked on its way there, by
    marching the height field towards the light."""
    size = height.shape[1]
    flat = float(np.hypot(light[0], light[1]))
    step_x, step_y = light[0] / flat, -light[1] / flat      # the picture's y is down
    rise = light[2] / flat * px_cm                          # cm the ray climbs per pixel
    shade = np.zeros_like(height)
    for i in range(1, SHADOW_STEPS + 1):
        t = SHADOW_REACH * size * (i / SHADOW_STEPS) ** 1.5 + 1.0
        over = (_shifted(height, int(round(step_x * t)), int(round(step_y * t)))
                - height - rise * t - SHADOW_BIAS_CM)
        shade = np.maximum(shade, np.clip(over / SHADOW_SOFT_CM, 0.0, 1.0))
    return np.clip(_blur(shade, SHADOW_BLUR * size), 0.0, 1.0)


def _occlusion(height, px_cm):
    """0..1 per pixel: how closed in it is by the model round it."""
    size = height.shape[1]
    closed = np.zeros_like(height)
    for radius in OCCLUSION_RADII:
        r = max(1.0, radius * size)
        closed += np.clip((_blur(height, r) - height) / (r * px_cm), 0.0, 1.0)
    return np.clip(closed / len(OCCLUSION_RADII) * 2.0, 0.0, 1.0)


def _studio(reflected):
    """What a mirror would show along each reflected ray: a soft box overhead
    and to the key's side, a paler wall behind the viewer, a dark floor."""
    up = reflected[..., 1]
    box = np.clip((reflected @ _unit(KEY_LIGHT) - 0.45) / 0.35, 0.0, 1.0)
    wall = 0.25 + 0.35 * np.clip(up * 0.5 + 0.5, 0.0, 1.0)
    return wall * np.clip(up * 4.0 + 1.0, 0.15, 1.0) + box ** 2


def lit(folder, level_to=LEVEL_TO):
    """The model lit and levelled, as straight-alpha float RGBA at the
    capture's size."""
    base = _load(folder, "base")[..., :3]
    world_normal = _load(folder, "normal")[..., :3] * 2.0 - 1.0
    alpha = 1.0 - _load(folder, "mask")[..., 3]
    with open(os.path.join(folder, "view.json")) as fh:
        view = json.load(fh)
    on = alpha > 0.5
    if on.mean() < MIN_COVERAGE:
        raise RuntimeError(f"{folder}: the model covers {on.mean():.1%} of its capture")
    axes = np.array([view["right"], view["up"], [-c for c in view["forward"]]],
                    dtype=np.float32)
    n = world_normal @ axes.T
    n /= np.maximum(np.linalg.norm(n, axis=-1, keepdims=True), 1e-4)
    facing = np.clip(n[..., 2], 0.0, 1.0)

    px_cm = view["width_cm"] / alpha.shape[1]
    height = _height(folder, on, view["width_cm"])
    key, fill = _unit(KEY_LIGHT), _unit(FILL_LIGHT)
    unshadowed = 1.0 - SHADOW * _shadow(height, px_cm, key)
    open_ = 1.0 - OCCLUSION * _occlusion(height, px_cm)

    ambient = (AMBIENT + SKY * (n[..., 1] * 0.5 + 0.5)) * (
        OCCLUSION_FLOOR + (1.0 - OCCLUSION_FLOOR) * open_)
    light = (ambient[..., None]
             + (KEY * np.clip(n @ key, 0.0, 1.0) * unshadowed)[..., None]
             * np.array(KEY_COLOUR, dtype=np.float32)
             + (FILL * np.clip(n @ fill, 0.0, 1.0) * open_)[..., None]
             * np.array(FILL_COLOUR, dtype=np.float32))

    half = _unit(key + np.array([0.0, 0.0, 1.0], dtype=np.float32))
    shine = HIGHLIGHT * np.power(np.clip(n @ half, 0.0, 1.0), HIGHLIGHT_POWER) * unshadowed
    # The viewer is along +z, so the reflected ray is 2 (n.z) n - z.
    reflected = 2.0 * n[..., 2:3] * n - np.array([0.0, 0.0, 1.0], dtype=np.float32)
    fresnel = REFLECTION_FACING + (1.0 - REFLECTION_FACING) * np.power(1.0 - facing, 5.0)
    mirror = REFLECTION * fresnel * _studio(reflected) * open_
    rim = RIM * np.power(1.0 - facing, 3.0)
    # Not on the outline itself: a pixel half on the model has a normal mixed
    # with the background's, which reads as grazing, and the gloss there drew
    # a pale halo round the portrait.
    inside = np.clip((_blur(on.astype(np.float32), EDGE_PX) - 0.5) * 2.0, 0.0, 1.0)
    mirror, rim = mirror * inside, rim * inside
    # Levelled before the gloss goes on: the gain a near-black model needs
    # would turn its faint reflections into chrome.
    colour = base * light
    luma = colour @ np.array([0.2126, 0.7152, 0.0722], dtype=np.float32)
    bright = float(np.percentile(luma[on], LEVEL_PERCENTILE))
    colour = colour * min(LEVEL_MAX_GAIN, max(1.0, level_to / max(bright, 1e-4)))
    colour = colour + (shine + mirror + rim)[..., None]
    over = np.maximum(colour - SHOULDER, 0.0) / (1.0 - SHOULDER)
    colour = np.where(colour > SHOULDER, SHOULDER + (1.0 - SHOULDER) * np.tanh(over), colour)
    return np.dstack([_to_srgb(colour), alpha])
