"""How a mesh is looked at for its picture: the numbers the capture and the
shading share. No `unreal` import.
"""

PASS_SIZE = 512                  # the passes; the picture is half, which smooths its edges
THUMB_SIZE = 256
FOV = 30.0
MARGIN = 1.1                     # of the mesh's bounding sphere
YAW, PITCH = 215.0, -18.0        # the camera looks back and a little down
# The turn: the camera walks once round the mesh, and the page's large view
# flips through what it saw. Frame 0 is the picture's own view.
SPIN_FRAMES = 16
SPIN_SIZE = 384


def spin_yaw(frame):
    return (YAW + frame * 360.0 / SPIN_FRAMES) % 360.0
