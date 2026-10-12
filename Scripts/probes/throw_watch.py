"""What a client shows of one thrown item, frame by frame (task R2).

Owns: the sampling (``Watch``: every frame, which pictures of the item this
machine shows and where) and the sums over those frames, which are plain
Python and unit-tested (Scripts/dev/tests/test_throw_watch.py): how far a
point is from the throw's curve, how many frames showed some other number of
items than one, how many frames an item in the air did not move.

Used by probe_net_throw.py. A frame is ``(wall, world, shown, flying)``:
the wall clock (one machine runs every process, so the processes share it),
the world's time, ``shown`` a list of ``(kind, (x, y, z))`` and ``flying``
whether the stand-in was still on its curve. The kinds:

    hand     the picture in the thrower's hand (its Held, not hidden)
    standin  the local actor this client flies (the thrower's ThrowFlyer)
    world    the server's replicated item, of the world's and not hidden
"""

import time

HAND, STANDIN, WORLD = "hand", "standin", "world"


# ─── the sums (no engine) ────────────────────────────────────────────────────

def on_curve(start, velocity, gravity_z, t):
    """start + v t + g t^2 / 2."""
    return (start[0] + velocity[0] * t, start[1] + velocity[1] * t,
            start[2] + velocity[2] * t + 0.5 * gravity_z * t * t)


def _gap(a, b):
    return sum((x - y) ** 2 for x, y in zip(a, b)) ** 0.5


def off_curve(point, start, velocity, gravity_z, t_max, steps=400):
    """How far ``point`` is from the nearest point of the curve flown from
    ``start`` at ``velocity`` in its first ``t_max`` seconds: a coarse sweep,
    then the bracket around its best step halved down."""
    def gap(t):
        return _gap(point, on_curve(start, velocity, gravity_z, t))
    step = t_max / steps
    best = min(range(steps + 1), key=lambda i: gap(i * step))
    lo, hi = max(0.0, (best - 1) * step), min(t_max, (best + 1) * step)
    for _ in range(40):
        a, b = lo + (hi - lo) / 3.0, hi - (hi - lo) / 3.0
        if gap(a) < gap(b):
            hi = b
        else:
            lo = a
    return gap((lo + hi) / 2.0)


def worst_off(frames, start, velocity, gravity_z, t_max, rest=None):
    """The furthest any stand-in was shown from the curve (or, once the throw
    has ended, from where the server says it rests, if that is nearer)."""
    worst = 0.0
    for _wall, _world, shown, flying in frames:
        for kind, at in shown:
            if kind != STANDIN:
                continue
            off = off_curve(at, start, velocity, gravity_z, t_max)
            if rest is not None and not flying:
                off = min(off, _gap(at, rest))
            worst = max(worst, off)
    return worst


def first_wall(frames, kind):
    """The wall clock of the first frame that showed a ``kind``, or None."""
    for wall, _world, shown, _flying in frames:
        if any(k == kind for k, _at in shown):
            return wall
    return None


def miscounts(frames, since=None, until=None):
    """The frames between two wall clocks that showed some other number of
    items than one, as (seconds after ``since``, kinds shown)."""
    base = since if since is not None else (frames[0][0] if frames else 0.0)
    return [(round(wall - base, 3), [k for k, _at in shown])
            for wall, _world, shown, _flying in frames
            if (since is None or wall >= since) and (until is None or wall <= until)
            and len(shown) != 1]


def stalls(frames, moved_cm=0.01):
    """How many frames a stand-in still on its curve was shown where the frame
    before showed it, though the world's time had moved on."""
    count, last = 0, None
    for _wall, world, shown, flying in frames:
        at = next((a for k, a in shown if k == STANDIN), None)
        if at is None or not flying:
            last = None
            continue
        if last is not None and world > last[0] and _gap(at, last[1]) < moved_cm:
            count += 1
        last = (world, at)
    return count


def places(frames, kind=STANDIN, apart_cm=1.0):
    """How many different places a ``kind`` was shown at."""
    seen = []
    for _wall, _world, shown, _flying in frames:
        for k, at in shown:
            if k == kind and (not seen or _gap(at, seen[-1]) > apart_cm):
                seen.append(at)
    return len(seen)


# ─── the sampling (in the game) ──────────────────────────────────────────────

def _xyz(actor):
    v = actor.get_actor_location()
    return (v.x, v.y, v.z)


def _hidden(actor):
    return bool(actor.get_editor_property("hidden"))


class Watch:
    """Every frame's pictures of the item ``name`` (any, if None) that
    ``wc``'s owner holds and throws, on this machine. ``world_items()`` lists this machine's item
    actors of that name and ``clock()`` reads the world's time; the rest name
    the weapon component's variables and the item's InWorld."""

    def __init__(self, p, wc, name, world_items, clock, flyer_var, stopped_var,
                 ended_var, in_world_var):
        self.p, self.wc, self.name = p, wc, name
        self.world_items, self.clock = world_items, clock
        self.flyer_var, self.stopped_var, self.ended_var = flyer_var, stopped_var, ended_var
        self.in_world_var = in_world_var
        self.frames = []

    def _is(self, actor):
        return actor is not None and (
            self.name is None or actor.get_class().get_name() == self.name)

    def shown(self):
        p, wc = self.p, self.wc
        flyer = p.get(wc, self.flyer_var)
        out = []
        held = p.get(wc, "Held")
        if self._is(held) and held != flyer and not _hidden(held):
            out.append((HAND, _xyz(held)))
        if self._is(flyer) and not _hidden(flyer):
            out.append((STANDIN, _xyz(flyer)))
        for item in self.world_items():
            if (item != flyer and not item.has_authority() and not _hidden(item)
                    and p.get(item, self.in_world_var)):
                out.append((WORLD, _xyz(item)))
        return out

    def sample(self):
        p, wc = self.p, self.wc
        flying = (p.get(wc, self.flyer_var) is not None
                  and not p.get(wc, self.stopped_var) and not p.get(wc, self.ended_var))
        self.frames.append((time.time(), self.clock(), self.shown(), flying))
