"""Outside the editor: light each mesh's passes into its picture. Needs Pillow
and numpy.

The passes are linear base colour and world normals with no alpha. The mesh
is where the normal pass is not black (a normal is stored as n * 0.5 + 0.5,
never zero); the picture is the base colour under one light from over the
camera's left shoulder plus an ambient floor, in sRGB, cut out along that
mask. A leaf card lit from behind is lit as from the front: BACK_SHARE of
the light reaches a face turned away.

A picture is kept while it is newer than its passes.
"""

import math
import os

import numpy as np
from PIL import Image

from map_assets.paths import PASSES_DIR, THUMB_DIR, pass_file, thumb_file
from map_assets.view import PITCH, THUMB_SIZE, YAW

AMBIENT = 0.42
KEY = 0.85
BACK_SHARE = 0.45
GAIN = 1.25                      # scanned base colours are dark on their own
MASK_FLOOR = 8                   # of 255: under this in every channel is no mesh


def _light():
    """The unit vector from the mesh towards the light, in world space."""
    yaw, pitch = math.radians(YAW), math.radians(PITCH)
    forward = np.array([math.cos(pitch) * math.cos(yaw), math.cos(pitch) * math.sin(yaw),
                        math.sin(pitch)])
    right = np.array([-math.sin(yaw), math.cos(yaw), 0.0])
    light = -forward * 0.6 - right * 0.5 + np.array([0.0, 0.0, 0.7])
    return light / np.linalg.norm(light)


def _srgb(linear):
    linear = np.clip(linear, 0.0, 1.0)
    return np.where(linear <= 0.0031308, linear * 12.92,
                    1.055 * np.power(linear, 1.0 / 2.4) - 0.055)


def shade(base, normal):
    """The picture (RGBA, THUMB_SIZE square) of two pass images."""
    base = np.asarray(base.convert("RGB"), dtype=np.float32) / 255.0
    raw = np.asarray(normal.convert("RGB"), dtype=np.float32)
    mask = (raw.max(axis=2) > MASK_FLOOR).astype(np.float32)
    facing = (raw / 255.0 * 2.0 - 1.0) @ _light().astype(np.float32)
    lit = AMBIENT + KEY * np.where(facing > 0.0, facing, -facing * BACK_SHARE)
    rgb = _srgb(base * lit[..., None] * GAIN)
    rgba = np.dstack([rgb, mask]) * 255.0
    picture = Image.fromarray(rgba.astype(np.uint8), "RGBA")
    return picture.resize((THUMB_SIZE, THUMB_SIZE), Image.LANCZOS)


def shade_all(paths):
    """Write the picture of every mesh of ``paths`` that has passes. Returns
    {path: file name} for the meshes with a picture."""
    os.makedirs(THUMB_DIR, exist_ok=True)
    done = {}
    for path in paths:
        passes = [os.path.join(PASSES_DIR, pass_file(path, n)) for n in ("base", "normal")]
        if not all(os.path.isfile(p) for p in passes):
            continue
        out = os.path.join(THUMB_DIR, thumb_file(path))
        if not os.path.isfile(out) or os.path.getmtime(out) < max(map(os.path.getmtime, passes)):
            with Image.open(passes[0]) as base, Image.open(passes[1]) as normal:
                shade(base, normal).save(out)
        # A translucent mesh is in neither pass: no picture, not a blank one.
        with Image.open(out) as picture:
            if picture.getchannel("A").getextrema()[1] == 0:
                continue
        done[path] = thumb_file(path)
    return done
