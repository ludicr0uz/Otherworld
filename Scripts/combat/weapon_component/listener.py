"""BeginPlay: hear the world from where the character stands, not from the camera.

The engine's listener sits on the camera, for panning and for distance alike.
The camera does not stay put: over the shoulder it rides the boom about 2.6 m
behind the character, and down the sights it travels to the gun at the eye.
Every sound measured against it changed loudness with the view. The footsteps
showed it most (A_Att_Foley falls off from 1 m): they were quiet behind the
shoulder and loud down the sights.

SetAudioListenerAttenuationOverride splits the two. Distance is measured from
the character's capsule, which is the same place in every view. Direction still
comes from the camera, so a sound on the left of the screen is still heard on
the left. The override follows the component and never needs refreshing. A
restart opens the level again, and the new character's BeginPlay sets it again.
"""

from combat.graph import BEL, _connect, _node, _pin
from combat.nodes import FN_SET_LISTENER_ATTENUATION


def _author_listener_at_character(ed, as_char, pc_out, exec_in):
    """Pin the player controller's attenuation listener to the capsule.

    The offset pin stays empty, which compiles as zero: the listener is the
    capsule's centre. Returns the then pin.
    """
    capsule = ed.add_get_member_variable_node("CapsuleComponent", "/Script/Engine.Character")
    _connect(as_char, _pin(capsule, "self"))
    listen = _node(ed, FN_SET_LISTENER_ATTENUATION)
    _connect(pc_out, _pin(listen, "self"))
    _connect(_pin(capsule, "CapsuleComponent", is_input=False),
             _pin(listen, "AttachToComponent"))
    _connect(exec_in, _pin(listen, "execute"))
    ed.add_comment_to_nodes(
        "Sounds fade with the distance from the character, not from the "
        "camera, so aiming down the sights does not make the footsteps "
        "louder. Panning still follows the camera.",
        [capsule, listen])
    return BEL.find_then_pin(listen)
