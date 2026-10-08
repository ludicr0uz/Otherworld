"""The moves the Game Animation Sample ships beyond the walk and the run
(task G5): the crouch set, the slide and traversal (mantle, vault, hurdle),
each behind a switch of its own. Constants only; gas_locomotion.py,
stance_clips.py, weapon_component/stance.py, player_move.py and
gas_traversal.py read them, verify/gas_moves.py checks them.

Each switch needs GAS_LOCOMOTION (gas_locomotion_consts.py): on the mannequin
fallback none of these exist, whatever the switch says. Change one, then run
the weapons build.

    GAS_CROUCH      crouched, the legs are the sample's crouch set (its idles,
                    walks, starts, stops and pivots, picked by its chooser on
                    Stance = Crouch) instead of the two Quaternius clips the
                    weapon layers blended in. Off: those two clips, as G4 left it.
    GAS_SLIDE       the crouch key in a sprint slides: a predicted state of the
                    C++ movement component (the sample's CMC character has no
                    slide: its slide is the Mover variant's movement mode,
                    which did not come across), posed by the sample's slide
                    loop. Off: the crouch key in a sprint does nothing, as before.
    GAS_TRAVERSAL   the jump key in front of a traversable block mantles,
                    vaults or hurdles it (the sample's AC_TraversalLogic and
                    its montage chooser). Off: the jump key jumps.
"""

from asset_pipeline.gas_paths import GAME_ROOT

GAS_CROUCH = True
GAS_SLIDE = True
GAS_TRAVERSAL = True

# ─── The slide ───────────────────────────────────────────────────────────────
# How long it coasts, from the speed it began at down to the crouch's pace.
SLIDE_SECONDS = 1.0
# It starts only from a sprint going at least this share of the sprint's speed.
SLIDE_MIN_START_SCALE = 0.75
# The sample's loop: 10 s of sliding on one hip, root locked (the clip's own
# force_root_lock), so a sequence player holds it in place.
SLIDE_CLIP = f"{GAME_ROOT}/Characters/UEFN_Mannequin/Animations/Slide/M_Neutral_Slide_FootOut_Loop"
# The weapon layers' weight for it (stance_clips.py), and how fast it eases:
# faster than a stance (12), the slide is a second long.
POSE_SLIDE = "PoseSlide"
SLIDE_BLEND_SPEED = 18.0

# ─── Traversal ───────────────────────────────────────────────────────────────
TRAVERSAL_BP = f"{GAME_ROOT}/Blueprints/AC_TraversalLogic"
TRAVERSAL_COMPONENT = "GasTraversal"
WARP_CLASS = "/Script/MotionWarping.MotionWarpingComponent"
WARP_COMPONENT = "MotionWarping"
# The only thing the sample's check takes for an obstacle: an actor of this
# class (it reads the ledges off the block's own splines). The forest has
# none placed; probes/probe_gas_traversal.py spawns one.
BLOCK_BP = f"{GAME_ROOT}/Levels/LevelPrototyping/LevelBlock_Traversable"
MONTAGE_CHOOSER = (f"{GAME_ROOT}/Characters/UEFN_Mannequin/Animations/Traversal/"
                   "CHT_TraversalMontages_CMC")
# Its graphs, and the nodes the patch looks for in them.
TRY_GRAPH = "TryTraversalAction"
PROPERTIES_MESSAGE = "Get_PropertiesForTraversal"
PROPERTIES_VAR = "CharacterProperties"
SERVER_EVENT = "PerformTraversalAction_Server"
DOING_VAR = "DoingTraversalAction"
# The character's custom event the jump key calls: the key's whole logic, so
# a probe's call of it is a press of the key.
JUMP_EVENT = "JumpPressed"
# The struct's fields (S_CharacterPropertiesForTraversal) the patch fills.
TRAVERSAL_FIELDS = ("Capsule", "Mesh", "MotionWarping", "MovementMode", "Gait", "Speed")
# The sweep the jump key asks for (S_TraversalCheckInputs), as the sample's
# character asks on the ground: ahead of the body, further the faster it goes.
TRACE_NEAR_CM = 75.0
TRACE_FAR_CM = 350.0
TRACE_FAR_AT_CMS = 500.0
TRACE_RADIUS_CM = 30.0
TRACE_HALF_HEIGHT_CM = 60.0
