"""The impostor's geometry: where its cards stand, how each is photographed
and where its picture sits in the atlas. Pure Python (no ``unreal``); the
capture, the atlas and the card mesh all read the same numbers from here.

Plane k of K stands upright through the mesh's middle at 180/K * k degrees.
Its picture is taken from straight on by an orthographic camera, so a point
of the mesh lands on the card where the card passes in front of it. Seen from
the other side the card shows the same picture mirrored.
"""

import math
from dataclasses import dataclass

MARGIN = 1.03        # the card over the mesh's own extent
PIVOT_SHARE = 0.35   # a pivot this far off the middle, of the half-width, is not a trunk
PAD_PX = 4           # empty border of an atlas cell, so mips do not bleed across


@dataclass(frozen=True)
class Frame:
    """The box every plane's card covers, in the mesh's own space (cm)."""
    centre_x: float
    centre_y: float
    bottom: float
    width: float
    height: float


def frame_of(origin, extent):
    """From a mesh's bounds (centre and half-size, each x, y, z). The cards
    cross on the mesh's pivot when that is near the middle, as a tree's is:
    the trunk is then in the same place on every card, where cards crossing
    on the middle of a lopsided crown show a trunk each. The width fits the
    crown from any side: a box seen corner-on is wider than its longer side,
    a round crown is not, so it is the smaller of the two."""
    ex, ey, ez = extent
    cx, cy = origin[0], origin[1]
    if max(abs(cx), abs(cy)) <= PIVOT_SHARE * max(ex, ey):
        ex, ey, cx, cy = ex + abs(cx), ey + abs(cy), 0.0, 0.0
    half = min(math.hypot(ex, ey), 1.15 * max(ex, ey))
    return Frame(cx, cy, origin[2] - ez * MARGIN, 2.0 * half * MARGIN, 2.0 * ez * MARGIN)


def plane_angle(k, planes):
    return 180.0 * k / planes


def camera_yaw(k, planes):
    """The yaw of the camera that photographs plane k: square on to it."""
    return plane_angle(k, planes) + 90.0


def capture_size(frame, longer_px):
    """(width, height) in pixels of one plane's capture: the frame's shape."""
    if frame.width >= frame.height:
        return longer_px, max(8, round(longer_px * frame.height / frame.width))
    return max(8, round(longer_px * frame.width / frame.height)), longer_px


def grid(planes):
    """(columns, rows) of the atlas."""
    columns = math.ceil(math.sqrt(planes))
    return columns, math.ceil(planes / columns)


def cell_px(k, planes, atlas_px):
    """(left, top, width, height) of plane k's picture in the atlas, inside
    its cell's border."""
    columns, rows = grid(planes)
    w, h = atlas_px // columns, atlas_px // rows
    return ((k % columns) * w + PAD_PX, (k // columns) * h + PAD_PX,
            w - 2 * PAD_PX, h - 2 * PAD_PX)


def cell_uv(k, planes, atlas_px):
    """(u0, v0, u1, v1) of the same rectangle."""
    left, top, w, h = cell_px(k, planes, atlas_px)
    return (left / atlas_px, top / atlas_px, (left + w) / atlas_px, (top + h) / atlas_px)


def quad(k, planes, frame, atlas_px):
    """Plane k's card: four (position, uv) corners -- bottom left, bottom
    right, top right, top left as the camera sees them. The camera's right is
    the opposite of the plane's own direction, so u runs against it."""
    a = math.radians(plane_angle(k, planes))
    ux, uy = math.cos(a), math.sin(a)
    u0, v0, u1, v1 = cell_uv(k, planes, atlas_px)
    half, top = frame.width / 2.0, frame.bottom + frame.height

    def corner(s, z, u, v):
        return ((frame.centre_x + s * ux, frame.centre_y + s * uy, z), (u, v))

    return [corner(half, frame.bottom, u0, v1), corner(-half, frame.bottom, u1, v1),
            corner(-half, top, u1, v0), corner(half, top, u0, v0)]


def tangent_basis(k, planes):
    """The card's tangent, bitangent and normal in the mesh's space, as rows:
    along u, along v (down the picture) and towards the camera. A world
    normal dotted with each is the tangent-space normal the atlas stores."""
    a = math.radians(plane_angle(k, planes))
    ux, uy = math.cos(a), math.sin(a)
    return ((-ux, -uy, 0.0), (0.0, 0.0, -1.0), (uy, -ux, 0.0))
