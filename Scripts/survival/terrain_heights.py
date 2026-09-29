"""Terrain height at a point, from the terrain mesh's own triangles.

Pure Python: give it world-space vertices and the triangle index list, ask for
height(x, y). place_forage uses this rather than a physics trace, because a
level loaded in the same Python call as the trace has not finished cooking its
terrain collision yet -- the 1 km map's complex collision cooks
asynchronously, the cook completes on a later editor tick, and a Python job
never yields one. Measured: 380 of 380 traces missed straight after
load_level, and 15 of 15 hit once the editor had ticked. The mesh is the same
geometry the collision is cooked from, so the answer is the same.

Triangles are bucketed on a uniform XY grid, so a query tests only the
handful of triangles over its cell.
"""

import math


class TriangleHeights:
    def __init__(self, verts, tris, cell=None):
        """verts: [(x, y, z)] in world space; tris: flat index list, 3 per face."""
        self.v = verts
        self.t = [tuple(tris[i:i + 3]) for i in range(0, len(tris) - len(tris) % 3, 3)]
        if not self.t:
            raise ValueError("no triangles")
        if cell is None:
            # About one triangle's footprint per cell.
            xs = [p[0] for p in verts]
            ys = [p[1] for p in verts]
            area = (max(xs) - min(xs)) * (max(ys) - min(ys))
            cell = max(1.0, math.sqrt(2.0 * area / len(self.t)))
        self.cell = cell
        self.grid = {}
        for idx, (a, b, c) in enumerate(self.t):
            pa, pb, pc = verts[a], verts[b], verts[c]
            for ix in range(self._k(min(pa[0], pb[0], pc[0])),
                            self._k(max(pa[0], pb[0], pc[0])) + 1):
                for iy in range(self._k(min(pa[1], pb[1], pc[1])),
                                self._k(max(pa[1], pb[1], pc[1])) + 1):
                    self.grid.setdefault((ix, iy), []).append(idx)

    def _k(self, u):
        return int(math.floor(u / self.cell))

    def height(self, x, y):
        """The highest surface over (x, y), or None off the mesh."""
        best = None
        for idx in self.grid.get((self._k(x), self._k(y)), ()):
            a, b, c = self.t[idx]
            (x1, y1, z1), (x2, y2, z2), (x3, y3, z3) = self.v[a], self.v[b], self.v[c]
            den = (y2 - y3) * (x1 - x3) + (x3 - x2) * (y1 - y3)
            if abs(den) < 1e-9:
                continue
            l1 = ((y2 - y3) * (x - x3) + (x3 - x2) * (y - y3)) / den
            l2 = ((y3 - y1) * (x - x3) + (x1 - x3) * (y - y3)) / den
            l3 = 1.0 - l1 - l2
            if min(l1, l2, l3) < -1e-6:
                continue
            z = l1 * z1 + l2 * z2 + l3 * z3
            best = z if best is None else max(best, z)
        return best
