"""The SMG, the rifle and the sniper as real models: the FPS Weapon Bundle's
SMG11, AK 47 and AS Val (Deadghost Interactive, a Fab pack under
/Game/FPS_Weapon_Bundle), how
each is placed in the weapon's frame, and the measured outline every grip and
sight check reads.

WHY AN OUTLINE AS WELL AS A MODEL
---------------------------------
Everything that places a gun in the hand or the eye behind it measures boxes:
grip._grip_location seats the "Grip" box in the fist, verify.grip_fit puts the
index finger on the "TriggerGuard", and verify.sights walks the sight line
over every box. A primitive gun IS its boxes. A model gun is not, so its row
carries the model (what is built and drawn) and an outline in the same box
form (what is measured). The outline is not built: each box is the model's
own geometry, measured off its vertices (min/max per 2 cm slice along the
barrel, in the model's frame), and the numbers below are those measurements.

THE FRAME
---------
The pack's _X meshes already point down +X with +Z up, which is the weapon's
own frame (weapon_specs.py), so the model sits at the origin unrotated and
unscaled: the pack is modelled at real size (the AK is 88 cm, the Val 95 cm,
the SMG11 32 cm)
and the adventurer is a real-size person. Muzzles are the meshes' own
b_gun_muzzleflash sockets.

The pack's _X/_Y are not texture variants but axis variants: SK_KA47 (_Y) and
SK_KA47_X are the same gun lying along +Y and +X. The _X is used so no
rotation has to be carried.

Nothing here acquires the pack. A clone without it fails the build at
_must_load with the pack's name; fab_library.json is the restore recipe.
"""

from combat.graph import _rot
from combat.grip import _barrel_rotation
from combat.paths import CUBE, CYLINDER, MAT_METAL


FAB_WEAPONS = "/Game/FPS_Weapon_Bundle/Weapons/Meshes"

SMG11_MESH = f"{FAB_WEAPONS}/SMG11/SK_SMG11_X"
AK47_MESH = f"{FAB_WEAPONS}/Ka47/SK_KA47_X"
VAL_MESH = f"{FAB_WEAPONS}/KA_Val/SK_KA_Val_X"
SCOPE_MESH = f"{FAB_WEAPONS}/Accessories/SM_Scope_25x56_X"


def _box(name, lo, hi):
    """An outline box from its min and max corners (cm), as a part tuple."""
    centre = tuple((a + b) / 2.0 for a, b in zip(lo, hi))
    scale = tuple((b - a) / 100.0 for a, b in zip(lo, hi))
    return (name, CUBE, centre, _rot(), scale, MAT_METAL)


# Each model component: (name, mesh, location, rotation, scale). The mesh's
# class (skeletal or static) decides the component's.

# ─── SMG11: the SMG ─────────────────────────────────────────────────────────

# The pack's SMG11, a MAC-11: a box receiver with the magazine up through the
# pistol grip (it hangs 13 cm under it), the wire stock folded over the top,
# and a sling strap hanging under the muzzle.
SMG_MODEL = (
    ("Model", SMG11_MESH, (0.0, 0.0, 0.0), _rot(), (1.0, 1.0, 1.0)),
)

# b_gun_muzzleflash on SK_SMG11_X.
SMG_MUZZLE = (19.5, 0.0, 8.0)

# Over the folded stock: its wire lies on the receiver's back half and tops
# out at 12.8, the highest thing on the gun, so the eye is a centimetre over
# it. The stock's butt is the part nearest the eye, and the eye must be a near
# plane (10 cm) behind it: that puts it 23 cm behind the grip, a little
# further back than the shotgun's 20.
SMG_SIGHT = (-24.0, 0.0, 13.8)


def smg_outline():
    return (
        _box("Receiver",     (-11.0, -2.8, 4.2),   (16.0, 2.5, 10.6)),
        # The folded wire stock: the butt behind the receiver, the wire over it.
        _box("Stock",        (-13.0, -2.4, 1.9),   (-1.0, 2.4, 12.8)),
        _box("CockingKnob",  (7.0, -1.0, 10.6),    (10.0, 1.0, 12.0)),
        _box("FrontSight",   (12.8, -1.5, 10.6),   (14.3, 1.5, 12.3)),
        _box("Barrel",       (16.0, -1.0, 7.1),    (19.5, 1.0, 9.0)),
        _box("Sling",        (13.5, -1.4, -12.4),  (15.6, 1.4, 4.5)),
        # The grip is deep front to back because the magazine runs up it.
        _box("Magazine",     (-1.6, -1.1, -18.8),  (1.9, 1.1, -6.0)),
        _box("Grip",         (-4.6, -1.6, -6.0),   (2.2, 1.6, 1.0)),
        _box("TriggerGuard", (2.2, -0.8, 0.6),     (8.0, 0.8, 1.6)),
    )


# ─── AK 47: the assault rifle ────────────────────────────────────────────────

RIFLE_MODEL = (
    ("Model", AK47_MESH, (0.0, 0.0, 0.0), _rot(), (1.0, 1.0, 1.0)),
)

# b_gun_muzzleflash on SK_KA47_X.
RIFLE_MUZZLE = (61.9, 0.0, 8.2)

# Over the irons: the rear sight's leaf (x 19-25) tops out at 13.8 and the
# front post at 13.7, so the sight line is ~13.8 and the eye a centimetre over
# it. 17 cm back: the dust cover's rear is at x -6, and the eye must be a near
# plane (10 cm) behind anything that close to the line; that also keeps the
# eye 15.5 cm behind the grip, where the old rifle's was 14 (further back
# and the camera is in the adventurer's head).
RIFLE_SIGHT = (-17.0, 0.0, 14.8)


def rifle_outline():
    return (
        _box("Stock",        (-28.0, -1.9, -2.5), (-10.0, 1.9, 8.3)),
        _box("Receiver",     (-6.0, -2.2, 1.5),   (26.0, 2.2, 12.4)),
        _box("RearSight",    (19.0, -1.1, 9.0),   (25.0, 1.1, 13.8)),
        _box("Handguard",    (26.0, -1.9, 5.9),   (40.0, 1.9, 13.4)),
        _box("Barrel",       (40.0, -1.2, 6.4),   (62.0, 1.2, 13.7)),
        _box("Magazine",     (12.0, -2.2, -12.7), (26.0, 2.2, 1.0)),
        # The pistol grip below the receiver, and the loop in front of it.
        _box("Grip",         (-3.75, -1.4, -6.0), (0.75, 1.4, 1.0)),
        _box("TriggerGuard", (2.0, -0.8, 1.1),    (11.0, 0.8, 2.5)),
    )


# ─── AS Val with a 25x56 scope: the sniper ──────────────────────────────────

# The scope's own frame: its tube runs x -20.8..22.8 (the eyepiece at -X, the
# 56 mm objective at +X) on an axis 3.6 cm over the rings' feet, which are at
# z -0.5. It sits on the Val's receiver top (z 12.5, x -4..28) with the rings
# at x 4 and 16, which puts the eyepiece 12 cm ahead of the grip.
SCOPE_AT = (12.0, 0.0, 13.0)
SCOPE_AXIS_Z = SCOPE_AT[2] + 3.6
SCOPE_EYEPIECE_X = SCOPE_AT[0] - 20.8

SNIPER_MODEL = (
    ("Model", VAL_MESH, (0.0, 0.0, 0.0), _rot(), (1.0, 1.0, 1.0)),
    ("Scope", SCOPE_MESH, SCOPE_AT, _rot(), (1.0, 1.0, 1.0)),
)

# b_gun_muzzleflash on SK_KA_Val_X: the end of the integral suppressor.
SNIPER_MUZZLE = (64.9, 0.0, 9.1)

# On the scope's axis, a near plane behind the eyepiece: the HUD's glass is
# what is seen, and the rifle hides itself before the camera gets there.
SNIPER_SIGHT = (SCOPE_EYEPIECE_X - 10.0, 0.0, SCOPE_AXIS_Z)


def sniper_outline():
    tube = SCOPE_AT[0] + 1.0
    return (
        _box("Stock",        (-32.0, -1.1, -1.8), (-18.0, 1.5, 8.7)),
        _box("Receiver",     (-6.0, -2.2, 3.0),   (36.0, 2.3, 13.1)),
        _box("Suppressor",   (36.0, -2.0, 7.1),   (65.0, 2.0, 12.8)),
        _box("Magazine",     (12.0, -2.2, -9.4),  (22.0, 2.2, 3.0)),
        _box("Grip",         (-3.0, -1.3, -5.5),  (2.0, 1.3, 1.0)),
        _box("TriggerGuard", (2.0, -0.8, 1.7),    (10.0, 0.8, 3.5)),
        # The rings' bases, from the receiver up to the underside of the tube.
        _box("ScopeMountR",  (SCOPE_AT[0] - 9.0, -1.5, 12.5),
             (SCOPE_AT[0] - 7.0, 1.5, SCOPE_AXIS_Z - 2.2)),
        _box("ScopeMountF",  (SCOPE_AT[0] + 3.0, -1.5, 12.5),
             (SCOPE_AT[0] + 5.0, 1.5, SCOPE_AXIS_Z - 2.2)),
        # A cylinder, the form verify.sights knows a scope by: 43.6 cm long,
        # 3.2 cm round at the objective bell.
        ("Scope", CYLINDER, (tube, 0.0, SCOPE_AXIS_Z), _barrel_rotation(),
         (0.064, 0.064, 0.436), MAT_METAL),
    )
