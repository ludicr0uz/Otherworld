"""What the lighting mends in a picture of several parts, from the masks the
capture wrote of each part alone (`part_<name>.png`; only the portrait has
any). Outside the editor: numpy, no `unreal`.

    seam   where two parts meet and do not quite touch, the capture sees
           between them. The MetaHuman's face ends at the shoulders and the
           whole body (a generic one, not Taro's own) begins a few pixels
           off: a hairline of nothing, which the contour then drew in black.
           Those pixels are filled from the skin on either side.
    hair   a groom writes its strands' direction where a surface writes its
           normal, so lit as a surface it is chrome at every angle. There the
           normal is taken from the depth instead, and the hair takes no gloss.
"""

import os

import numpy as np
from PIL import Image

from item_icons.paths import part_file

SEAM_PX = 3                      # of the capture: the widest gap that is one
HAIR_SMOOTH_PX = 3               # the depth is blurred this much for a normal


def part(folder, name):
    """Where the part is, as the capture saw it alone; None if it wrote none."""
    path = os.path.join(folder, part_file(name))
    if not os.path.isfile(path):
        return None
    return np.asarray(Image.open(path).convert("RGBA"))[..., 3] < 128


def _grown(mask, px):
    for _ in range(px):
        pad = np.pad(mask, 1)
        mask = np.logical_or.reduce([pad[1 + dy:pad.shape[0] - 1 + dy, 1 + dx:pad.shape[1] - 1 + dx]
                                     for dy in (-1, 0, 1) for dx in (-1, 0, 1)])
    return mask


def seam(on, rim):
    """The pixels off the model that lie in a gap between the ``rim`` part
    and the rest of it."""
    closed = ~_grown(~_grown(on, SEAM_PX), SEAM_PX)
    return closed & ~on & _grown(rim & on, SEAM_PX) & _grown(on & ~rim, SEAM_PX)


def filled(a, on, hole):
    """``a`` with its ``hole`` pixels given the mean of the model round them."""
    a, known = a.copy(), on.copy()
    flat = a.reshape(a.shape[0], a.shape[1], -1)
    for _ in range(2 * SEAM_PX):
        todo = hole & ~known
        if not todo.any():
            break
        weight = np.pad(known, 1).astype(np.float32)
        value = np.pad(flat * known[..., None], ((1, 1), (1, 1), (0, 0)))
        h, w = known.shape
        n = sum(weight[1 + dy:h + 1 + dy, 1 + dx:w + 1 + dx]
                for dy in (-1, 0, 1) for dx in (-1, 0, 1))
        s = sum(value[1 + dy:h + 1 + dy, 1 + dx:w + 1 + dx]
                for dy in (-1, 0, 1) for dx in (-1, 0, 1))
        got = todo & (n > 0)
        flat[got] = s[got] / n[got][:, None]
        known = known | got
    return a


def height_normal(height, px_cm, blur):
    """The surface's normal in the camera's space (x right, y up, z towards
    the viewer), from the height field."""
    smooth = blur(height, HAIR_SMOOTH_PX)
    d_row, d_col = np.gradient(smooth)
    n = np.dstack([-d_col, d_row, np.full_like(smooth, px_cm)])
    return n / np.linalg.norm(n, axis=-1, keepdims=True)
