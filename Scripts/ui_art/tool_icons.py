"""The tools' inventory icons, drawn as build_ui_art.py draws the weapons':
white silhouettes on its supersampled icon canvas, which its _icon crops,
scales and centres, and the HUD tints with the item's SlotColor.

    Axe   a long haft with a flared head across one end: the only drawing
          whose bulk is a wedge at the tip, hanging below the line.
    Wood  a short thick log with the stub of a branch standing off it: the
          only drawing that is one fat bar, with nothing at either end.
    Matches  an upright open box with three match heads standing out of its
          top: the only drawing that is taller than it is wide.

The supersample is passed in, so this module imports nothing from
build_ui_art.py (which imports it).
"""

WHITE = (255, 255, 255, 255)


def icon_axe(d, s):
    """The haft lying along the slot, the head at its right end, bit down."""
    d.rounded_rectangle((8 * s, 27 * s, 114 * s, 35 * s), radius=4 * s, fill=WHITE)
    head = [(95, 15), (111, 15), (112, 34), (124, 54), (103, 62), (82, 54), (94, 34)]
    d.polygon([(x * s, y * s) for x, y in head], fill=WHITE)


def icon_wood(d, s):
    """A log lying along the slot, a cut branch stub on its upper side."""
    d.rounded_rectangle((14 * s, 24 * s, 114 * s, 50 * s), radius=11 * s, fill=WHITE)
    stub = [(70, 26), (80, 10), (92, 14), (88, 26)]
    d.polygon([(x * s, y * s) for x, y in stub], fill=WHITE)


def icon_matches(d, s):
    """A matchbox standing on end, three matches standing out of it."""
    d.rounded_rectangle((44 * s, 24 * s, 84 * s, 62 * s), radius=3 * s, fill=WHITE)
    for x in (50, 62, 74):
        d.rectangle(((x + 1) * s, 10 * s, (x + 3) * s, 24 * s), fill=WHITE)
        d.ellipse(((x - 1) * s, 3 * s, (x + 5) * s, 12 * s), fill=WHITE)
