"""xform -- the vector, quaternion and matrix helpers the bind is written in.

Plain tuples, as quat_math.py's (which this builds on): a point or direction
is (x, y, z), a quaternion (x, y, z, w), a rotation matrix three rows. Pure:
no unreal, no numpy -- a body is 25,000 vertices and this runs in seconds.
"""

import math

from asset_pipeline.quat_math import add, conj, dot, length, mul, scale, sub, turn

IDENTITY = (0.0, 0.0, 0.0, 1.0)
EYE = ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0))


def cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2],
            a[0] * b[1] - a[1] * b[0])


def unit(v):
    n = length(v)
    if n < 1e-12:
        raise ValueError("a zero-length vector has no direction")
    return tuple(c / n for c in v)


def qnorm(q):
    n = math.sqrt(sum(c * c for c in q))
    return tuple(c / n for c in q)


def axis_angle(axis, degrees):
    half = math.radians(degrees) / 2.0
    s = math.sin(half)
    ax = unit(axis)
    return (ax[0] * s, ax[1] * s, ax[2] * s, math.cos(half))


def angle_deg(q):
    """How far a rotation turns, 0-180."""
    return math.degrees(2.0 * math.acos(min(1.0, abs(q[3]))))


def angle_between(a, b):
    return math.degrees(math.acos(max(-1.0, min(1.0, dot(unit(a), unit(b))))))


def swing(a, b):
    """The shortest turn taking direction ``a`` onto direction ``b``.
    quat_math.between divides by zero on opposite directions; this turns
    half way round about any axis across them."""
    a, b = unit(a), unit(b)
    w = 1.0 + dot(a, b)
    if w < 1e-9:
        side = cross(a, (1.0, 0.0, 0.0))
        if length(side) < 1e-6:
            side = cross(a, (0.0, 1.0, 0.0))
        side = unit(side)
        return (side[0], side[1], side[2], 0.0)
    c = cross(a, b)
    return qnorm((c[0], c[1], c[2], w))


def q_to_mat(q):
    x, y, z, w = q
    return ((1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)),
            (2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)),
            (2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)))


def mat_to_q(m):
    """A rotation matrix (three rows) as a quaternion."""
    t = m[0][0] + m[1][1] + m[2][2]
    if t > 0.0:
        s = math.sqrt(t + 1.0) * 2.0
        q = ((m[2][1] - m[1][2]) / s, (m[0][2] - m[2][0]) / s,
             (m[1][0] - m[0][1]) / s, 0.25 * s)
    elif m[0][0] > m[1][1] and m[0][0] > m[2][2]:
        s = math.sqrt(1.0 + m[0][0] - m[1][1] - m[2][2]) * 2.0
        q = (0.25 * s, (m[0][1] + m[1][0]) / s, (m[0][2] + m[2][0]) / s,
             (m[2][1] - m[1][2]) / s)
    elif m[1][1] > m[2][2]:
        s = math.sqrt(1.0 + m[1][1] - m[0][0] - m[2][2]) * 2.0
        q = ((m[0][1] + m[1][0]) / s, 0.25 * s, (m[1][2] + m[2][1]) / s,
             (m[0][2] - m[2][0]) / s)
    else:
        s = math.sqrt(1.0 + m[2][2] - m[0][0] - m[1][1]) * 2.0
        q = ((m[0][2] + m[2][0]) / s, (m[1][2] + m[2][1]) / s, 0.25 * s,
             (m[1][0] - m[0][1]) / s)
    return qnorm(q)


def mat_vec(m, v):
    return (m[0][0] * v[0] + m[0][1] * v[1] + m[0][2] * v[2],
            m[1][0] * v[0] + m[1][1] * v[1] + m[1][2] * v[2],
            m[2][0] * v[0] + m[2][1] * v[1] + m[2][2] * v[2])


def mat_mul(a, b):
    return tuple(tuple(sum(a[i][k] * b[k][j] for k in range(3)) for j in range(3))
                 for i in range(3))


def transpose(m):
    return tuple(tuple(m[j][i] for j in range(3)) for i in range(3))


def frame(forward, normal):
    """An orthonormal frame as a matrix whose COLUMNS are: ``forward``, the
    axis across it, and ``normal`` with whatever lay along forward removed."""
    f = unit(forward)
    n = unit(sub(normal, scale(f, dot(normal, f))))
    a = cross(n, f)
    return transpose((f, a, n))


def frame_turn(src_forward, src_normal, dst_forward, dst_normal):
    """The rotation carrying one (forward, normal) frame onto another."""
    return mat_to_q(mat_mul(frame(dst_forward, dst_normal),
                            transpose(frame(src_forward, src_normal))))


def lerp(a, b, t):
    return tuple(p + (q - p) * t for p, q in zip(a, b))


def smoothstep(lo, hi, x):
    if hi <= lo:
        return 0.0 if x < lo else 1.0
    t = max(0.0, min(1.0, (x - lo) / (hi - lo)))
    return t * t * (3.0 - 2.0 * t)


__all__ = ["IDENTITY", "EYE", "add", "angle_between", "angle_deg", "axis_angle",
           "conj", "cross", "dot", "frame", "frame_turn", "length", "lerp",
           "mat_mul", "mat_to_q", "mat_vec", "mul", "q_to_mat", "qnorm", "scale",
           "smoothstep", "sub", "swing", "transpose", "turn", "unit"]
