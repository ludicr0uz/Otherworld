"""The reload clips' numbers (weapon_component/reload_clip.py): Lyra's rifle
reload, the magazine change the AKM and the sniper share, and its pistol
reload, the pistol's and the SMG's. Constants only.

A clip is played whole, at the rate that fits it to its gun's reload (the
rifle's 2.2 s over the AKM's 2.1 s and the sniper's 2.6 s; the pistol's
2.0 s over the pistol's 1.2 s and the SMG's 1.9 s): the builder works the
rate out from the clip's length and the gun's row (gun_rows.gun_row, so a
reload time changed in gun_tuning.csv is followed at the next build). The
reload is still a deadline and not a state (tuning.py): the clip follows
nothing and nothing waits for it.
"""

# The guns whose reload plays a clip, by Blueprint: the row of gun_rows.py
# its reload time is read from (its DisplayName), and the PlayerSkin field
# its clip is. A magazine fed from below into a gun held in the rifle's
# pose, or into the grip of one held in the pistol's.
RELOAD_CLIP_GUNS = {
    "BP_AssaultRifle": ("Rifle", "reload_rifle"),
    "BP_SniperRifle": ("Sniper", "reload_rifle"),
    "BP_Pistol": ("Pistol", "reload_pistol"),
    "BP_SMG": ("SMG", "reload_pistol"),
}

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


def reload_rate(clip_seconds, reload_seconds):
    """The play rate that ends a clip of ``clip_seconds`` with a reload of
    ``reload_seconds``."""
    return clip_seconds / reload_seconds
