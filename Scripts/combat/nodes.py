"""Engine class paths the combat graphs name. Constants only. (The node
paths, FN_* and NODE_*, are the shared catalog: uebp/nodes/.)
"""

CAMERA_CLASS_PATH = "/Script/Engine.CameraComponent"
MOVEMENT_CLASS_PATH = "/Script/Engine.CharacterMovementComponent"
# Aiming down the sights (weapon_component/sights.py): the camera leaves the
# boom's end for the weapon's eye point. USpringArmComponent names its one
# socket SpringEndpoint; the camera hangs off it with no offset of its own.
SPRING_ARM_CLASS_PATH = "/Script/Engine.SpringArmComponent"
SPRING_ARM_SOCKET = "SpringEndpoint"


