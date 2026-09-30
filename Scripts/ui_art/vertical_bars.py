"""The vertical bars' art: T_UI_Bar and T_UI_BarTrack turned upright.

A vertical ProgressBar clips its fill from the bottom. Drawn with the
horizontal texture stretched upright, the bar's lit-from-above shading ran
down its length, so a nearly empty bar showed only the dark foot of the
gradient and read as a different colour. Turned 90 degrees, the shading runs
across the bar, the same at every height, so a tinted fill keeps its colour
however low it is.

Made from build_ui_art.py's horizontal PNGs, so there is one drawing of a bar.
"""

import os

VERTICAL = {"T_UI_Bar": "T_UI_BarV", "T_UI_BarTrack": "T_UI_BarTrackV"}


def write_vertical_bars(out_dir):
    """Rotate the horizontal bars in ``out_dir``; returns the names written."""
    from PIL import Image
    made = []
    for flat, upright in VERTICAL.items():
        with Image.open(os.path.join(out_dir, f"{flat}.png")) as img:
            img.transpose(Image.Transpose.ROTATE_90).save(
                os.path.join(out_dir, f"{upright}.png"))
        made.append(upright)
    return made
