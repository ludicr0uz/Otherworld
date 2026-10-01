"""Every gun as a real model: the SMG, the rifle and the sniper are the FPS
Weapon Bundle's SMG11, AK 47 and AS Val (Deadghost Interactive, a Fab pack
under /Game/FPS_Weapon_Bundle), the shotgun and the pistol are Quaternius's
Ultimate Gun Pack's Shotgun_3 and Pistol_1 (CC0, imported by
asset_pipeline/import_quaternius.py). How each is placed in the weapon's
frame, and the measured outline every grip and sight check reads.

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

The Quaternius guns also point down +X with +Z up, but at no one size (the
pistol is 1.8 m long as imported, the shotgun 5.8 m), so each carries its own
scale to real size: the shotgun 104 cm, the pistol 20. The outlines below are
measured on the scaled mesh.

Nothing here acquires either pack. A clone without them fails the build at
_must_load with the pack's name; fab_library.json is the Fab pack's restore
recipe, and the Quaternius zips go in assets/cache/quaternius/.
"""

from combat.graph import _rot
from combat.grip import _barrel_rotation
from combat.paths import CUBE, CYLINDER, MAT_METAL


FAB_WEAPONS = "/Game/FPS_Weapon_Bundle/Weapons/Meshes"

SMG11_MESH = f"{FAB_WEAPONS}/SMG11/SK_SMG11_X"
AK47_MESH = f"{FAB_WEAPONS}/Ka47/SK_KA47_X"
VAL_MESH = f"{FAB_WEAPONS}/KA_Val/SK_KA_Val_X"
SCOPE_MESH = f"{FAB_WEAPONS}/Accessories/SM_Scope_25x56_X"

# asset_pipeline/quaternius_paths.SHOTGUN_MODEL and PISTOL_MODEL.
QUATERNIUS_GUNS = "/Game/Sourced/Quaternius/Guns"
SHOTGUN_MESH = f"{QUATERNIUS_GUNS}/SM_Shotgun_3"
PISTOL_MESH = f"{QUATERNIUS_GUNS}/SM_Pistol_1"


def _eye_behind(rear, front, eye_x):
    """The point of the sight line (rear sight -> front sight) at `eye_x`:
    where the eye goes, so the two sights and the eye are on one line."""
    t = (eye_x - rear[0]) / (front[0] - rear[0])
    return tuple(r + (f - r) * t for r, f in zip(rear, front))


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

# The sight line: the rear peep (a 3.2 mm hole in a plate behind the receiver,
# at x -9.1) and the tip of the front post between its ears, both 11.7 up, so
# the line runs level. It passes between the folded stock's two wires (they
# lie at |y| 1.4-2.2, up to 12.8), through the cocking knob's U (11.3 deep,
# the line clear of it inside |y| 0.45) and under the stock's hinge bar. The
# stock's butt is the part nearest the eye, and the eye must be a near plane
# (10 cm) behind it: that puts it 23 cm behind the grip.
SMG_SIGHT_REAR = (-9.1, 0.0, 11.7)
SMG_SIGHT_FRONT = (14.1, 0.0, 11.7)
SMG_SIGHT = _eye_behind(SMG_SIGHT_REAR, SMG_SIGHT_FRONT, -24.0)


def smg_outline():
    return (
        _box("Receiver",     (-11.0, -2.8, 4.2),   (16.0, 2.5, 10.6)),
        # The folded wire stock: the butt behind the receiver, the wire over it.
        # ...as its two wires, either side of the sight line, and the butt.
        _box("Stock",        (-13.0, -2.4, 1.9),   (-10.0, 2.4, 11.0)),
        _box("StockWireL",   (-13.0, -2.4, 11.0),  (-1.0, -1.2, 12.8)),
        _box("StockWireR",   (-13.0, 1.2, 11.0),   (-1.0, 2.4, 12.8)),
        # The peep's plate under its hole, the knob under its U, and the
        # front sight's base under the post: each stops at the sight line.
        _box("RearSight",    (-9.2, -0.7, 10.6),   (-9.0, 0.7, 11.38)),
        _box("CockingKnob",  (7.0, -1.0, 10.6),    (10.0, 1.0, 11.4)),
        _box("FrontSight",   (12.8, -1.5, 10.6),   (14.3, 1.5, 11.7)),
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

# The sight line: the top of the rear leaf's notch (2.6 mm wide, 1.7 deep, at
# x 20.35, 13.77 up) and the tip of the front post (13.30, x 59.3, between
# ears that stand to 13.67), so the line falls 0.7 degrees to the muzzle and
# the post's tip stands level with the notch's shoulders. The eye is 17 cm
# back: the dust cover's rear is at x -6, and the eye must be a near plane
# (10 cm) behind anything that close to the line; that also keeps the eye
# 15.5 cm behind the grip (further back and the camera is in the adventurer's
# head).
RIFLE_SIGHT_REAR = (20.35, 0.0, 13.77)
RIFLE_SIGHT_FRONT = (59.3, 0.0, 13.30)
RIFLE_SIGHT = _eye_behind(RIFLE_SIGHT_REAR, RIFLE_SIGHT_FRONT, -17.0)


def rifle_outline():
    return (
        _box("Stock",        (-28.0, -1.9, -2.5), (-10.0, 1.9, 8.3)),
        _box("Receiver",     (-6.0, -2.2, 1.5),   (26.0, 2.2, 12.4)),
        # The rear leaf up to its notch's shoulders, and the gas block and
        # barrel up to the front post's tip: the sight line touches both.
        _box("RearSight",    (19.0, -1.1, 9.0),   (25.0, 1.1, 13.77)),
        _box("Handguard",    (26.0, -1.9, 5.9),   (40.0, 1.9, 13.4)),
        _box("Barrel",       (40.0, -1.2, 6.4),   (62.0, 1.2, 13.3)),
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

# The sight line is the scope's axis, eyepiece to objective, and the eye is on
# it a near plane behind the eyepiece: the HUD's glass is what is seen, and
# the rifle hides itself before the camera gets there.
SNIPER_SIGHT_REAR = (SCOPE_EYEPIECE_X, 0.0, SCOPE_AXIS_Z)
SNIPER_SIGHT_FRONT = (SCOPE_AT[0] + 22.8, 0.0, SCOPE_AXIS_Z)
SNIPER_SIGHT = _eye_behind(SNIPER_SIGHT_REAR, SNIPER_SIGHT_FRONT,
                           SCOPE_EYEPIECE_X - 10.0)


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


# ─── Quaternius Shotgun_3: the shotgun ──────────────────────────────────────

# A pump gun with a straight wooden stock (no pistol grip: the hand holds the
# stock's wrist behind the trigger guard), a tube magazine under the barrel,
# the wooden pump round both, and a band with the bead near the muzzle.
SHOTGUN_SCALE = 0.18
SHOTGUN_MODEL = (
    ("Model", SHOTGUN_MESH, (0.0, 0.0, 0.0), _rot(), (SHOTGUN_SCALE,) * 3),
)

# The end of the barrel, on its axis.
SHOTGUN_MUZZLE = (77.5, 0.0, 3.9)

# How far the index may rest off the TriggerGuard (verify/grip_fit; the other
# guns are held to 2.5). The ready pose is a pistol grip's: its index lies
# 4.5 cm above the fist's centre. This gun has a straight stock and its guard
# hangs under the wrist, so the index lies along the receiver, 4.1 cm above
# the guard; putting it in the guard would hang the fist 3 cm under the wood.
SHOTGUN_TRIGGER_REACH_CM = 4.5

# The sight line: a shotgun has no rear sight, so the line skims the
# receiver's hump (a fin 6.83 high at x 3.7) a millimetre over it and ends on
# the bead's tip (6.42, x 69): the bead stands half a centimetre clear of the
# hump, and its tip is the point of aim. The eye is a near plane behind the
# receiver's back, 12 cm behind the grip.
SHOTGUN_SIGHT_REAR = (3.7, 0.0, 6.93)
SHOTGUN_SIGHT_FRONT = (69.0, 0.0, 6.42)
SHOTGUN_SIGHT = _eye_behind(SHOTGUN_SIGHT_REAR, SHOTGUN_SIGHT_FRONT, -12.0)


def shotgun_outline():
    return (
        _box("Stock",        (-26.6, -1.5, -10.1), (-4.6, 1.5, 3.9)),
        # Where the right hand closes: the stock's wrist (x -4.6..1.4, z -5.4..2.4)
        # and the back of the receiver's belly, the fist as far forward and
        # down as the index needs to reach into the guard.
        _box("Grip",         (-2.6, -1.4, -6.0),   (3.4, 1.4, 0.8)),
        _box("Receiver",     (1.4, -2.2, -2.5),    (22.4, 2.2, 6.8)),
        _box("TriggerGuard", (3.4, -0.8, -5.6),    (11.4, 0.8, -2.3)),
        _box("Barrel",       (22.4, -1.4, 2.5),    (77.5, 1.4, 5.3)),
        _box("MagTube",      (22.4, -1.4, -1.2),   (62.4, 1.4, 1.6)),
        _box("Pump",         (28.4, -2.1, -2.5),   (44.4, 2.1, 5.3)),
        # The band round barrel and tube, with the bead on top.
        _box("MuzzleBand",   (62.4, -1.8, -1.7),   (70.4, 1.8, 6.4)),
    )


# ─── Quaternius Pistol_1: the pistol ────────────────────────────────────────

# A service automatic: the slide over a short frame, the grip raked back with
# the weapon's origin inside it, a rear notch and a front post on the slide.
PISTOL_SCALE = 0.11
PISTOL_MODEL = (
    ("Model", PISTOL_MESH, (0.0, 0.0, 0.0), _rot(), (PISTOL_SCALE,) * 3),
)

# The barrel's end, standing a centimetre proud of the slide.
PISTOL_MUZZLE = (16.4, 0.0, 6.35)

# The sight line: the top of the rear notch (two blades 8.125 high at x -1.2,
# 4.4 mm apart) and the tip of the front post (8.29 at x 13.9, 4.4 mm wide),
# the post's tip level with the blades. The eye is a near plane behind the
# slide's back.
PISTOL_SIGHT_REAR = (-1.2, 0.0, 8.125)
PISTOL_SIGHT_FRONT = (13.9, 0.0, 8.29)
PISTOL_SIGHT = _eye_behind(PISTOL_SIGHT_REAR, PISTOL_SIGHT_FRONT, -14.0)


def pistol_outline():
    return (
        _box("Slide",        (-3.7, -1.6, 3.3),  (16.3, 1.6, 7.7)),
        _box("RearSight",    (-1.7, -1.8, 7.7),  (-0.7, 1.8, 8.125)),
        _box("FrontSight",   (13.3, -0.8, 7.7),  (15.3, 0.8, 8.29)),
        _box("Frame",        (2.3, -1.6, 2.3),   (8.3, 1.6, 3.3)),
        _box("Grip",         (-3.7, -1.8, -4.5), (2.3, 1.8, 3.3)),
        _box("TriggerGuard", (3.3, -0.8, 0.9),   (8.3, 0.8, 2.3)),
    )
