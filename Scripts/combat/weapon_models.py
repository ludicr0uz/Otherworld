"""Every gun as a real model: the SMG, the rifle and the sniper are the FPS
Weapon Bundle's SMG11, AK 47 and AS Val (Deadghost Interactive, a Fab pack
under /Game/FPS_Weapon_Bundle), the shotgun and the pistol are Stein Games'
pump-action shotgun with a wooden stock and 1911 (Fab listings taken raw,
under /Game/Fab/Shotgun_Pump_Action_Wooden_Stock_Hish_Poly and
/Game/Fab/1911_Pistol_High_Poly). How each is placed in the weapon's frame,
and the measured outline every grip and sight check reads.

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

The Stein Games guns lie along +Y with +Z up, a little over real size, so
each carries a quarter turn onto +X and a scale. The outlines below are
measured on the mesh as it is placed.

Nothing here acquires any of the packs. A clone without them fails the build
at _must_load with the pack's name; fab_library.json is the Fab packs' restore
recipe.
"""

from uebp.graph import _rot
from combat.grip import _barrel_rotation
from combat.paths import CUBE, CYLINDER, MAT_METAL


FAB_WEAPONS = "/Game/FPS_Weapon_Bundle/Weapons/Meshes"

SMG11_MESH = f"{FAB_WEAPONS}/SMG11/SK_SMG11_X"
AK47_MESH = f"{FAB_WEAPONS}/Ka47/SK_KA47_X"
VAL_MESH = f"{FAB_WEAPONS}/KA_Val/SK_KA_Val_X"
SCOPE_MESH = f"{FAB_WEAPONS}/Accessories/SM_Scope_25x56_X"

# "Shotgun - Pump Action - Wooden Stock - Hish Poly" and "1911 Pistol - High
# Poly" in fab_library.json (asset_pipeline/fab_raw_import.py).
SHOTGUN_MESH = "/Game/Fab/Shotgun_Pump_Action_Wooden_Stock_Hish_Poly/SM_Shotgun_02"
PISTOL_MESH = "/Game/Fab/1911_Pistol_High_Poly/SM_1911_02"


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


# ─── Pump shotgun with a wooden stock: the shotgun ──────────────────────────

# Stein Games' pump-action shotgun (a Fab listing taken raw, fab_library.json):
# a wooden stock with a semi pistol grip (the wrist swells down behind the
# trigger guard, its front face raked back from under the receiver), a
# receiver with a notched rear sight block, a ribbed barrel over a tube
# magazine, the wooden pump round the tube, and a clamp with the bead behind
# the muzzle. The mesh lies along +Y at about 107% of a real pump gun, as the
# same maker's 1911 does (its trigger is 38.5 cm from the butt and its
# receiver 23.1 long, against a Remington 870's 35.6 and 21.6), so the model
# is turned a quarter turn onto +X and scaled to 95.6 cm, butt to muzzle. Its
# origin is where the stock meets the receiver, on the gun's middle plane.
SHOTGUN_SCALE = 0.93
SHOTGUN_MODEL = (
    ("Model", SHOTGUN_MESH, (0.0, 0.0, 0.0), _rot(yaw=-90.0), (SHOTGUN_SCALE,) * 3),
)

# The end of the barrel, on its axis.
SHOTGUN_MUZZLE = (67.76, 0.0, 3.44)

# How far the index's outer joints may rest off the trigger guard (cm).
TRIGGER_REACH_CM = 2.5
# How far the shotgun's may (verify/grip_fit). The ready pose is a pistol
# grip's: its index lies 4 cm above the fist's centre, the other fingers
# stacked upright under it. This gun's guard hangs level with the fist, behind
# a raked swell of the stock: the fist is seated with its middle finger behind
# the guard, under the receiver's tail, and the index lies along the receiver
# 3.3 cm above the guard. Putting it in the guard would hang the fist 4 cm
# under the wood.
SHOTGUN_TRIGGER_REACH_CM = 4.5
# Lyra's pistol ready pose lays the index straight along the frame, above
# the guard, not on the trigger: 3.8 cm from the pistol's guard, 3.5 from the
# SMG's (verify/grip_fit.py; the pose until C3 had it 1.7 off).
PISTOL_POSE_TRIGGER_REACH_CM = 4.5

# The sight line: the top of the rear block's two blades (6.40 high at their
# back edge, x 7.85, a notch 2 mm deep between them) and the top of the bead
# (5.88, a bar from x 64.9 to 66.8, 3 mm wide): the bead stands half a
# centimetre lower than the blades, so the line falls a little to the muzzle,
# over the rib (4.98). The eye is 12.4 cm behind the fist's middle, as it was
# on the gun before this one: 15 cm behind the receiver's back.
SHOTGUN_SIGHT_REAR = (7.85, 0.0, 6.397)
SHOTGUN_SIGHT_FRONT = (65.88, 0.0, 5.878)
SHOTGUN_SIGHT = _eye_behind(SHOTGUN_SIGHT_REAR, SHOTGUN_SIGHT_FRONT, -12.8)


# The stock's wrist: its min and max corners, measured. Its underside falls
# from the receiver's tail to (-0.9, -2.4), then the swell's face runs back
# and down to (-4.2, -6.9); the wood is 3 cm thick.
SHOTGUN_WRIST = ((-7.4, -1.5, -7.1), (2.2, 1.5, 0.9))

# The pump, where the left hand closes: the wood round the magazine tube,
# reaching half a centimetre up the sides of the barrel (which runs
# y -1.1..1.1, z 2.3..4.6, a rib on it to 5.0), measured.
SHOTGUN_PUMP = ((29.1, -2.1, -2.0), (47.7, 2.1, 2.8))


def shotgun_outline():
    return (
        # The butt and the comb, back from the wrist.
        _box("Stock",        (-27.9, -2.05, -13.2), (-3.6, 2.05, 0.9)),
        # Where the right hand closes: the wrist under the receiver's tail,
        # from the top of the swell to the back of the guard. The fist's
        # middle is just under the wood there, the middle finger a finger's
        # width behind the guard and the thumb along the wrist's top. The
        # fingers of a pistol grip's pose stand upright, so the ring and the
        # little finger close on air 5 cm ahead of the swell's raked face:
        # seated on that face, the hand is 4 cm further from the trigger and
        # from the pump, which the left arm then cannot reach at all.
        _box("Grip",         (-3.6, -1.5, -5.4),    (2.8, 1.5, 0.2)),
        _box("Receiver",     (2.2, -1.9, -1.86),    (23.7, 1.9, 5.65)),
        # The rear block up to its blades' tops.
        _box("RearSight",    (7.5, -0.7, 5.65),     (9.7, 0.7, 6.397)),
        # The guard's loop under the receiver.
        _box("TriggerGuard", (5.0, -0.47, -3.8),    (11.07, 0.47, -1.86)),
        # The barrel (a tube 2.2 cm across, its top at 4.56) with the rib
        # along its top: what the left thumb stays under
        # (shotgun_hold.barrel_top).
        _box("Barrel",       (23.7, -1.1, 2.3),     (67.76, 1.1, 4.98)),
        _box("MagTube",      (23.7, -1.4, -1.0),    (66.1, 1.4, 1.8)),
        _box("Pump",         (29.1, -2.1, -2.0),    (47.7, 2.1, 2.8)),
        # The clamp round barrel and tube, and the bead on the barrel.
        _box("BarrelClamp",  (62.4, -1.4, -2.25),   (64.9, 1.4, 4.98)),
        _box("Bead",         (64.9, -0.25, 4.98),   (67.0, 0.25, 5.878)),
    )


# ─── 1911: the pistol ────────────────────────────────────────────────────────

# Stein Games' 1911 (a Fab listing taken raw, fab_library.json): a Government
# model with its hammer down, the slide over a frame with a short dust cover,
# the grip raked back. The mesh lies along +Y at 108% of the real gun (23.4 cm
# from the beavertail to the muzzle), so the model is turned a quarter turn
# onto +X and scaled to 21.1 cm. Its origin is already where the weapon's
# belongs: inside the top of the grip, behind the trigger guard.
PISTOL_SCALE = 0.9
PISTOL_MODEL = (
    ("Model", PISTOL_MESH, (0.0, 0.0, 0.0), _rot(yaw=-90.0), (PISTOL_SCALE,) * 3),
)

# The middle of the bore at the barrel's face, flush with the slide's front.
PISTOL_MUZZLE = (16.3, 0.0, 6.48)

# The sight line: the top of the rear blades (8.06 high at their front edge,
# x -0.58, a notch 4.9 mm wide between them) and the tip of the front post
# (7.90 at x 15.0, 2.6 mm wide): the post stands 1.6 mm lower than the
# blades, so the line falls a little to the front. The eye is 21 cm behind
# the hammer: far enough that both hands stand partly in the view, round the
# gun (at 10 cm the slide's back alone filled a quarter of it).
PISTOL_SIGHT_REAR = (-0.58, 0.0, 8.064)
PISTOL_SIGHT_FRONT = (15.01, 0.0, 7.902)
PISTOL_SIGHT = _eye_behind(PISTOL_SIGHT_REAR, PISTOL_SIGHT_FRONT, -25.0)


def pistol_outline():
    return (
        _box("Slide",        (-3.1, -1.0, 3.9),   (16.3, 1.0, 7.47)),
        # The blades up to their highest edge, and the post from its tip on.
        _box("RearSight",    (-1.55, -0.5, 7.47), (-0.58, 0.5, 8.064)),
        _box("FrontSight",   (14.9, -0.13, 7.47), (16.0, 0.13, 7.902)),
        _box("Hammer",       (-4.8, -0.35, 4.15), (-3.1, 0.35, 5.6)),
        # The frame over the trigger, between the grip and the dust cover.
        _box("Frame",        (1.7, -0.75, 3.15),  (7.6, 0.75, 3.9)),
        # The grip between its straps at mid height (it is raked: the back
        # strap runs from x -3.1 under the slide to -4.5 at the butt), the
        # panels' 3.1 cm across, down to the magazine's floor.
        _box("Grip",         (-3.9, -1.55, -6.3), (1.5, 1.55, 0.9)),
        # The guard's bar under the trigger.
        _box("TriggerGuard", (1.8, -0.5, 0.9),    (7.4, 0.5, 1.45)),
    )
