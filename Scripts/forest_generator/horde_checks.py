"""
horde_checks.py — Offline checks for a Horde Survival level
(horde_layout.py): the ring is as dense as asked, the clearing scarce, the
fort clear of trees and bushes, its wall closed but for three openings each
wide enough, and its rocks chest high. Run by verification.run_all_checks on
a level in horde_layout.HORDE_LEVELS.
"""

import math

from .horde_layout import neighbour_overlap, opening_widths_cm, stretches
from .verification import CheckResult


def check_ring_density(layout, placed_trees, world_size_cm):
    """The dense ring (past the clearing's feather, inside the trees' box)
    holds dense_trees_per_ha, within 10 %."""
    half = world_size_cm / 2.0 * layout.edge_fraction
    inner = layout.clearing_radius_cm + layout.clearing_feather_cm
    count = sum(1 for t in placed_trees if math.hypot(t.x, t.y) >= inner)
    area_ha = ((2.0 * half) ** 2 - math.pi * inner ** 2) / 1e8
    density = count / area_ha
    ok = abs(density - layout.dense_trees_per_ha) <= 0.1 * layout.dense_trees_per_ha
    return CheckResult("Horde Ring Density", ok,
                       f"{count} trees on {area_ha:.1f} ha = {density:.1f}/ha "
                       f"(asked {layout.dense_trees_per_ha:g})")


def check_clearing_scarce(layout, placed_trees):
    """The clearing has a few trees, no more than twice what it asks, and
    none in the fort or the ground kept clear round it."""
    inside = [t for t in placed_trees if math.hypot(t.x, t.y) < layout.clearing_radius_cm]
    fort = [t for t in inside if math.hypot(t.x, t.y) < layout.keep_out_cm]
    area_ha = math.pi * (layout.clearing_radius_cm ** 2 - layout.keep_out_cm ** 2) / 1e8
    density = len(inside) / area_ha
    ok = 0 < len(inside) and density <= 2.0 * layout.sparse_trees_per_ha and not fort
    return CheckResult("Horde Clearing Scarce", ok,
                       f"{len(inside)} trees in the clearing ({density:.1f}/ha, "
                       f"asked {layout.sparse_trees_per_ha:g}), {len(fort)} inside "
                       f"{layout.keep_out_cm / 100.0:.0f} m",
                       [f"{t.spec_name} at ({t.x:.0f},{t.y:.0f})" for t in fort])


def check_fort_clear_of_bushes(layout, placed_bushes):
    near = [b for b in placed_bushes or [] if math.hypot(b.x, b.y) < layout.keep_out_cm]
    return CheckResult("Horde Fort Clear of Bushes", not near,
                       f"{len(near)} bushes inside {layout.keep_out_cm / 100.0:.0f} m",
                       [f"{b.spec_name} at ({b.x:.0f},{b.y:.0f})" for b in near])


def check_fort_openings(layout, rocks):
    """As many openings as the layout names, each at least its box width
    clear between the two rocks' footprint boxes (the rocks are rounder than
    their boxes: the verifier measures the walked width in the editor)."""
    widths = opening_widths_cm(rocks)
    ok = (len(widths) == len(layout.opening_yaws_deg)
          and min(widths) >= layout.opening_box_cm)
    return CheckResult("Horde Fort Openings", ok,
                       f"{len(widths)} openings, "
                       f"{', '.join(f'{w:.0f}' for w in widths)} cm clear "
                       f"(at least {layout.opening_box_cm:.0f})")


def check_fort_wall_closed(layout, rocks):
    """Every pair of neighbours in a stretch overlaps by at least 30 % of
    the shorter: the boxes' overlap, which the rounded rocks need to touch."""
    worst, bad = 1.0, []
    for arc in stretches(rocks):
        for a, b in zip(arc, arc[1:]):
            share = neighbour_overlap(a, b)
            worst = min(worst, share)
            if share < 0.3:
                bad.append(f"stretch {a.arc}: ({a.cx:.0f},{a.cy:.0f})-({b.cx:.0f},"
                           f"{b.cy:.0f}) overlap {share:.2f}")
    return CheckResult("Horde Fort Wall Closed", bool(rocks) and not bad,
                       f"{len(rocks)} rocks, the least overlap {worst:.2f}", bad)


def check_fort_chest_high(layout, rocks):
    lo, hi = layout.rock_visible_cm
    heights = [r.top_z - r.terrain_z for r in rocks]
    bad = [f"{r.mesh_path.rsplit('/', 1)[1]} at ({r.cx:.0f},{r.cy:.0f}): {h:.0f} cm"
           for r, h in zip(rocks, heights) if not lo - 1.0 <= h <= hi + 1.0]
    return CheckResult("Horde Fort Chest High", bool(rocks) and not bad,
                       f"tops {min(heights or [0]):.0f}-{max(heights or [0]):.0f} cm "
                       f"above the ground (asked {lo:.0f}-{hi:.0f})", bad)


def run_horde_checks(layout, placed_trees, rocks, placed_bushes, world_size_cm):
    return [
        check_ring_density(layout, placed_trees, world_size_cm),
        check_clearing_scarce(layout, placed_trees),
        check_fort_clear_of_bushes(layout, placed_bushes),
        check_fort_openings(layout, rocks),
        check_fort_wall_closed(layout, rocks),
        check_fort_chest_high(layout, rocks),
    ]
