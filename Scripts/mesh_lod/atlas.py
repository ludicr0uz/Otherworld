"""Outside the editor: the planes' captures made into the impostor's two
textures. Needs Pillow and numpy, which the editor's Python has not got.

    T_<name>_Impostor_BC   sRGB colour, and in alpha the mask the cards are
                           cut out with
    T_<name>_Impostor_N    tangent-space normals

A pass is raw float32 RGB (capture.py). Where nothing was drawn the colour
is black and the normal pass holds an empty G-buffer decoded, (-1, -1, -1)
normalised; the mesh is every pixel that is not both. The colour pass is
linear and is stored sRGB. The
colour around the mesh is spread outwards from its edge, so a mip that
averages across the mask's edge does not pull in black. The normals are in
world space with the mesh unrotated; each is turned into its card's tangent
space (planes.tangent_basis), which is what lets a planted, rotated tree
light its card correctly.
"""

import os

import numpy as np
from PIL import Image

from mesh_lod import paths, planes

EMPTY_NORMAL = -0.57735          # each component of the normal where nothing is
EMPTY_SLACK = 0.02
SPREAD_STEPS = 24


def _srgb(linear):
    linear = np.clip(linear, 0.0, 1.0)
    return np.where(linear <= 0.0031308, linear * 12.92,
                    1.055 * np.power(linear, 1.0 / 2.4) - 0.055)


def spread(rgb, mask, steps=SPREAD_STEPS):
    """``rgb`` with every unmasked pixel within ``steps`` of the mask given
    the average of its masked neighbours, a ring at a time."""
    rgb, known = rgb.copy(), mask > 0.5
    for _ in range(steps):
        total = np.zeros_like(rgb)
        count = np.zeros(known.shape, dtype=np.float32)
        for axis, shift in ((0, 1), (0, -1), (1, 1), (1, -1)):
            near = np.roll(known, shift, axis=axis)
            # np.roll wraps: the far edge is no neighbour.
            edge = [slice(None), slice(None)]
            edge[axis] = 0 if shift == 1 else -1
            near[tuple(edge)] = False
            total += np.roll(rgb, shift, axis=axis) * near[..., None]
            count += near
        fresh = ~known & (count > 0)
        if not fresh.any():
            break
        rgb[fresh] = total[fresh] / count[fresh][:, None]
        known |= fresh
    return rgb


def read_pass(file, size):
    """A pass as a (height, width, 3) float array; ``size`` is (width, height)."""
    data = np.fromfile(file, dtype=np.float32)
    if data.size != size[0] * size[1] * 3:
        raise ValueError(f"{file}: {data.size} values, not {size[0]}x{size[1]}x3")
    return data.reshape(size[1], size[0], 3)


def mesh_mask(colour, world):
    """1.0 where the mesh was drawn, 0.0 elsewhere."""
    empty = (np.abs(world - EMPTY_NORMAL).max(axis=2) < EMPTY_SLACK) & (colour.max(axis=2) <= 0.0)
    return (~empty).astype(np.float32)


def plane_pictures(colour, world, plane, count, brightness=1.0):
    """One plane's (colour RGBA, normal RGB) as float arrays in 0..1, from its
    linear colour pass and its world-normal pass."""
    mask = mesh_mask(colour, world)
    basis = np.array(planes.tangent_basis(plane, count), dtype=np.float32)
    tangent = world @ basis.T
    length = np.linalg.norm(tangent, axis=2, keepdims=True)
    tangent = np.where(length > 1e-4, tangent / np.maximum(length, 1e-4), [0.0, 0.0, 1.0])
    # A leaf seen from behind has its normal pointing away; the card is lit
    # from the side it is seen from.
    tangent[..., 2] = np.abs(tangent[..., 2])
    flat = np.array([0.0, 0.0, 1.0], dtype=np.float32)
    tangent = np.where(mask[..., None] > 0.5, tangent, flat)
    rgb = spread(_srgb(colour * brightness) * mask[..., None], mask)
    return np.dstack([rgb, mask]), tangent * 0.5 + 0.5


def _image(array, mode):
    return Image.fromarray((np.clip(array, 0.0, 1.0) * 255.0 + 0.5).astype(np.uint8), mode)


def build(name, spec, capture_size):
    """Write the job's two atlases from its passes, each ``capture_size``
    (width, height). Returns their paths and the share of the atlas the mesh
    covers."""
    size, count = spec.atlas_px, spec.impostor_planes
    colour = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    normal = Image.new("RGB", (size, size), (128, 128, 255))
    for plane in range(count):
        files = [paths.pass_file(name, plane, kind) for kind in paths.PASSES]
        missing = [f for f in files if not os.path.isfile(f)]
        if missing:
            raise FileNotFoundError(f"{name}: no capture at {missing[0]}")
        rgba, tangent = plane_pictures(
            read_pass(files[0], capture_size), read_pass(files[1], capture_size),
            plane, count, spec.impostor_brightness)
        left, top, w, h = planes.cell_px(plane, count, size)
        colour.paste(_image(rgba, "RGBA").resize((w, h), Image.LANCZOS), (left, top))
        normal.paste(_image(tangent, "RGB").resize((w, h), Image.LANCZOS), (left, top))
    out = {"BC": paths.atlas_png(name, "BC"), "N": paths.atlas_png(name, "N")}
    colour.save(out["BC"])
    normal.save(out["N"])
    covered = float((np.asarray(colour.getchannel("A")) > 127).mean())
    return out, covered
