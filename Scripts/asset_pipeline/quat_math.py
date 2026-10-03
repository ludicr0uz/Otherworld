"""quat_math.py -- quaternions and vectors as plain (x, y, z, w) / (x, y, z)
tuples, for the retarget passes that turn bones by measured directions
(clavicle_align.py, two_hands.py). Pure: no unreal."""

import math


def mul(a, b):
    ax, ay, az, aw = a
    bx, by, bz, bw = b
    return (aw * bx + ax * bw + ay * bz - az * by,
            aw * by - ax * bz + ay * bw + az * bx,
            aw * bz + ax * by - ay * bx + az * bw,
            aw * bw - ax * bx - ay * by - az * bz)


def conj(q):
    return (-q[0], -q[1], -q[2], q[3])


def norm(v):
    n = math.sqrt(sum(c * c for c in v))
    return tuple(c / n for c in v)


def turn(q, v):
    """``v`` rotated by ``q``."""
    return mul(mul(q, (v[0], v[1], v[2], 0.0)), conj(q))[:3]


def between(a, b):
    """The shortest turn taking unit ``a`` onto unit ``b``."""
    cx = (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])
    w = 1.0 + sum(p * q for p, q in zip(a, b))
    return norm((cx[0], cx[1], cx[2], w))


def sub(a, b):
    return tuple(p - q for p, q in zip(a, b))


def add(a, b):
    return tuple(p + q for p, q in zip(a, b))


def scale(v, s):
    return tuple(c * s for c in v)


def dot(a, b):
    return sum(p * q for p, q in zip(a, b))


def length(v):
    return math.sqrt(dot(v, v))
