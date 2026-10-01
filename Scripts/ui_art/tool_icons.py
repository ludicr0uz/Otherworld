"""The tools' inventory icons, drawn as build_ui_art.py draws the weapons':
white silhouettes on its supersampled icon canvas, which its _icon crops,
scales and centres, and the HUD tints with the item's SlotColor.

    Axe   a long haft with a flared head across one end: the only drawing
          whose bulk is a wedge at the tip, hanging below the line.

The supersample is passed in, so this module imports nothing from
build_ui_art.py (which imports it).
"""

WHITE = (255, 255, 255, 255)


def icon_axe(d, s):
    """The haft lying along the slot, the head at its right end, bit down."""
    d.rounded_rectangle((8 * s, 27 * s, 114 * s, 35 * s), radius=4 * s, fill=WHITE)
    head = [(95, 15), (111, 15), (112, 34), (124, 54), (103, 62), (82, 54), (94, 34)]
    d.polygon([(x * s, y * s) for x, y in head], fill=WHITE)
