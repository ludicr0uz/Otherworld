"""The reload clip's numbers (weapon_component/reload_clip.py): Lyra's rifle
reload, the magazine change the AKM and the sniper share. Constants only.

The clip is 2.2 s, played whole at its own rate over a reload of 2.1 s (the
AKM) or 2.6 s (the sniper): the reload is a deadline and not a state
(tuning.py), so the clip follows nothing and nothing waits for it.
"""

# The guns whose reload plays it, by Blueprint: a magazine fed from below
# into a gun held in the rifle's pose.
RELOAD_CLIP_GUNS = ("BP_AssaultRifle", "BP_SniperRifle")

RELOAD_BLEND_IN_S = 0.15    # over the ready pose the slot held
RELOAD_BLEND_OUT_S = 0.2    # its own, where no ready pose takes over (a gun lowered)
# How long before the clip's end the ready pose takes the slot back. A slot
# play blends itself out over the last RELOAD_BLEND_OUT_S to the pose under
# the slot, the locomotion's, and only a silent slot is given the ready pose
# again: left to that the gun went to the hip and came up again after every
# reload. Started before the clip's own blend out, the ready pose's play
# blends the clip out against itself.
RELOAD_HANDOVER_S = 0.3
# The left hand's hold on the gun down the sights (support_hand.py) lets go
# for the clip and takes hold again after, eased at this speed (FInterpTo).
RELOAD_HAND_SPEED = 12.0
