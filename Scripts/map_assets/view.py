"""How a mesh is looked at for its picture: the numbers the capture and the
shading share. No `unreal` import.
"""

PASS_SIZE = 512                  # the passes; the picture is half, which smooths its edges
THUMB_SIZE = 256
FOV = 30.0
MARGIN = 1.1                     # of the mesh's bounding sphere
YAW, PITCH = 215.0, -18.0        # the camera looks back and a little down
