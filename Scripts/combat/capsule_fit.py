"""Capsules fitted to a cloud of vertices: the geometry behind hit_bodies.py.

Pure (no ``unreal``): points are (x, y, z) tuples in any one space, and what
comes back is in that space. Tests: dev/tests/test_capsule_fit.py.

One body used to be one capsule down one of the importer's three axes. That
held while every body was a clothed limb, and broke on two things a generated
body can have:

  * axes that are not the limb's. A physics asset copied from another body
    (asset_pipeline/physics_template.py) brings capsule axes written in that
    body's bone frames, and Meshy gives each rig its own. So the axes are the
    cloud's own principal axes, and no importer's.
  * a shape one capsule cannot follow: a bare thigh that tapers to the knee, a
    forearm whose body also carries an open hand. One capsule round the widest
    part stood out past the rest, and a round beside a bare knee was a hit. So
    a body is cut across its long axis wherever two capsules cover markedly
    less of the picture than one (SPLIT_GAIN), each half fitted by itself.
"""

import math

# The share of a cloud's vertices, from each end of an axis, left outside the
# fit: a few stray vertices (a tooth, a torn sleeve) must not set the size.
FIT_TRIM = 0.02
# A capsule is round and a head or a chest is not, so its radius sits between
# the body's two half-widths: 0 is the narrower one, 1 the wider.
FIT_ROUNDNESS = 0.5
# How far a capsule's rounded end reaches past its vertices, as a share of its
# radius. Neighbouring bodies meet where the skin's weights change hands, and
# two hemispheres meeting there leave a notch all round the joint.
FIT_END_OVERLAP = 0.25
# Two capsules replace one when their silhouettes together are this much
# smaller than the one's. Measured on the four Meshy bodies (overhang as
# hit_bodies.body_coverage counts it, one capsule a body -> cut at 0.05): the
# man in boxers 0.204 -> 0.168, the zombie 0.146 -> 0.119, the dressed
# adventurer 0.132 -> 0.130, with the uncovered share unchanged to 0.004. At
# 0.12 only the wendigo's limbs were cut and the bare legs stayed whole...
SPLIT_GAIN = 0.05
# ...at most this many times over (2 cuts: up to 4 capsules a body)...
SPLIT_DEPTH = 2
# ...and never into a half with fewer vertices than this.
SPLIT_MIN_POINTS = 24


def _dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2],
            a[0] * b[1] - a[1] * b[0])


def _unit(v):
    n = math.sqrt(_dot(v, v))
    return (v[0] / n, v[1] / n, v[2] / n)


def _signed(v):
    """``v`` or its opposite: the one whose largest component is positive, so
    the same cloud always gives the same axis."""
    big = max(v, key=abs)
    return v if big >= 0 else (-v[0], -v[1], -v[2])


def principal_axes(points):
    """(long, middle, short) unit axes of the cloud, by Jacobi rotations of
    its covariance. Right-handed: short = long x middle."""
    n = float(len(points))
    mean = tuple(sum(p[i] for p in points) / n for i in range(3))
    a = [[sum((p[i] - mean[i]) * (p[j] - mean[j]) for p in points) / n
          for j in range(3)] for i in range(3)]
    v = [[1.0 if i == j else 0.0 for j in range(3)] for i in range(3)]
    for _sweep in range(32):
        off = abs(a[0][1]) + abs(a[0][2]) + abs(a[1][2])
        if off < 1e-12:
            break
        for p, q in ((0, 1), (0, 2), (1, 2)):
            if abs(a[p][q]) < 1e-15:
                continue
            theta = 0.5 * math.atan2(2.0 * a[p][q], a[q][q] - a[p][p])
            c, s = math.cos(theta), math.sin(theta)
            for k in range(3):
                akp, akq = a[k][p], a[k][q]
                a[k][p], a[k][q] = c * akp - s * akq, s * akp + c * akq
            for k in range(3):
                apk, aqk = a[p][k], a[q][k]
                a[p][k], a[q][k] = c * apk - s * aqk, s * apk + c * aqk
            for k in range(3):
                vkp, vkq = v[k][p], v[k][q]
                v[k][p], v[k][q] = c * vkp - s * vkq, s * vkp + c * vkq
    order = sorted(range(3), key=lambda i: -a[i][i])
    long_axis = _signed(_unit(tuple(v[k][order[0]] for k in range(3))))
    middle = tuple(v[k][order[1]] for k in range(3))
    middle = _signed(_unit(tuple(
        m - l * _dot(middle, long_axis) for m, l in zip(middle, long_axis))))
    return long_axis, middle, _cross(long_axis, middle)


def _span(values):
    """(middle, half-extent) of ``values`` with FIT_TRIM dropped off each end."""
    values = sorted(values)
    lo = values[int(FIT_TRIM * (len(values) - 1))]
    hi = values[int((1.0 - FIT_TRIM) * (len(values) - 1))]
    return (lo + hi) * 0.5, (hi - lo) * 0.5


def _one(points, axes):
    """One capsule along axes[0] round ``points``: {center, radius, length}."""
    long_axis, u_axis, v_axis = axes
    (mt, ht), (mu, hu), (mv, hv) = (
        _span([_dot(p, a) for p in points]) for a in (long_axis, u_axis, v_axis))
    narrow, wide = sorted((hu, hv))
    radius = narrow + (wide - narrow) * FIT_ROUNDNESS
    # Never rounder than it is long: a capsule's ends are its radius.
    squat = ht > 0 and radius > ht / (1.0 - FIT_END_OVERLAP)
    if squat:
        radius = ht / (1.0 - FIT_END_OVERLAP)
    length = max(0.0, 2.0 * (ht - radius * (1.0 - FIT_END_OVERLAP)))
    center = tuple(long_axis[i] * mt + u_axis[i] * mu + v_axis[i] * mv
                   for i in range(3))
    return {"center": center, "radius": radius, "length": length, "middle": mt,
            "squat": squat}


def _silhouette(capsule):
    """The capsule's area seen from the side: what a pellet meets."""
    r = capsule["radius"]
    return 2.0 * r * capsule["length"] + math.pi * r * r


def _fit(points, axes, depth):
    whole = _one(points, axes)
    if depth <= 0 or len(points) < 2 * SPLIT_MIN_POINTS:
        return [whole]
    along = axes[0]
    low = [p for p in points if _dot(p, along) < whole["middle"]]
    high = [p for p in points if _dot(p, along) >= whole["middle"]]
    if min(len(low), len(high)) < SPLIT_MIN_POINTS:
        return [whole]
    halves = [_one(low, axes), _one(high, axes)]
    # A half wider than it is long is a ball, smaller than what it stands for:
    # cut that way a chest or a head loses its sides.
    if any(c["squat"] for c in halves):
        return [whole]
    if sum(_silhouette(c) for c in halves) > (1.0 - SPLIT_GAIN) * _silhouette(whole):
        return [whole]
    return _fit(low, axes, depth - 1) + _fit(high, axes, depth - 1)


def fit_capsules(points):
    """(axes, [capsule]): the cloud's (long, middle, short) axes, and the
    capsules along the long one that cover it, in order along it. Each capsule
    is {center, radius, length}; a cloud that one capsule follows gets one."""
    axes = principal_axes(points)
    capsules = _fit(points, axes, SPLIT_DEPTH)
    return axes, [{k: c[k] for k in ("center", "radius", "length")}
                  for c in capsules]
