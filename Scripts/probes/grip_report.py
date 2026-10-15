"""grip_report -- the arithmetic of probe_drawn_grip.py: a finger's signed
distances to a gun's mesh made into its penetration and its gap, the wrist
of the drawn body against the mannequin's, and the report's lines. Pure: no
unreal, so the dev unit tests hold it (Scripts/dev/tests/test_grip_report.py).

A distance is a bone's axis to the gun's surface (cm), negative inside the
mesh. A finger's skin stands SKIN_CM off its axis (finger_fit.SKIN_CM, the
seat's own figure), so the finger's surface is in the gun by SKIN_CM less the
nearest axis distance (its penetration), and off it by the nearest axis
distance less SKIN_CM (its gap). One of the two is always nought.
"""

# The finger's skin off its bone's axis (cm): hand_seat.SEAT_OFF_CM, which the
# fit lays every finger at. Repeated, not imported: this module stays pure.
SKIN_CM = 0.75


def finger(signed, skin_cm=SKIN_CM):
    """(nearest axis distance, penetration, gap) of one finger, from the
    signed distances of its riding points (cm)."""
    near = min(signed)
    return near, max(0.0, skin_cm - near), max(0.0, near - skin_cm)


def offset(a, b):
    """How far apart two points are (cm)."""
    return sum((x - y) ** 2 for x, y in zip(a, b)) ** 0.5


def finger_cell(signed, skin_cm=SKIN_CM):
    """A finger as the report writes it: "in 0.42" (its skin that deep in
    the gun), "off 1.10" (that far off it) or "on" (touching, within 0.05)."""
    _near, pen, gap = finger(signed, skin_cm)
    if pen > 0.05:
        return f"in {pen:.2f}"
    if gap > 0.05:
        return f"off {gap:.2f}"
    return "on"


def table(names, rows):
    """Markdown lines of a table: ``names`` the header, ``rows`` lists of
    cells (str or number, a number to two places)."""
    def cell(v):
        return f"{v:.2f}" if isinstance(v, float) else str(v)
    out = ["| " + " | ".join(names) + " |", "|" + "---|" * len(names)]
    out += ["| " + " | ".join(cell(v) for v in row) + " |" for row in rows]
    return out


def worst(cells):
    """The deepest penetration and the widest gap among ``cells`` ({label:
    signed distances}): ((label, cm) or None, (label, cm) or None)."""
    pens = [(k, finger(v)[1]) for k, v in cells.items()]
    gaps = [(k, finger(v)[2]) for k, v in cells.items()]
    pen = max(pens, key=lambda kv: kv[1], default=None)
    gap = max(gaps, key=lambda kv: kv[1], default=None)
    return (pen if pen and pen[1] > 0 else None), (gap if gap and gap[1] > 0 else None)
