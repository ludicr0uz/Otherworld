"""The garments on the ground: the jacket, the pants and the boots lie as the
mesh they are worn as (clothing/ground_model.py), the other five as cubes.

    python3 Scripts/dev/uepy.py --game --probe Scripts/probes/probe_clothing_ground.py
    python3 Scripts/dev/uepy.py --game --windowed --probe Scripts/probes/probe_clothing_ground.py

1. Each of the three test garments on the 200 m map shows one skeletal mesh,
   its WornMesh, with no anim instance and its post-process Blueprint off, lying over the item's origin and
   no higher than the garment is thick; it glimmers as any item on the ground.
2. The other five show no skeletal mesh.
3. One picture of the row, from above the player with the player hidden, to
   Saved/Screenshots/MacEditor (a picture only when --windowed).
"""

SYSTEMS = ('clothing',)

import os

import unreal

from clothing.ground_model import MODEL
from clothing.placement import TEST_TAG
from clothing.specs import GARMENTS
from combat.glimmer_tuning import GLIMMER
from combat.wear_tuning import WORN_MESH_VAR

# The test garments are placed on it.
LEVEL = "/Game/Maps/Lvl_Forest_200m"
SHOTS_DIR = os.path.join(unreal.Paths.project_saved_dir(), "Screenshots", "MacEditor")
# The bounds of a skinned mesh are its physics asset's or a padded box: near
# enough to tell a garment lying on its item from one standing beside it.
OVER_CM = 15.0
EYE_UP_CM, EYE_FOV = 260.0, 45.0
SETTLE = 0.5


def _named(actor, cls, name):
    return next((c for c in actor.get_components_by_class(cls) if c.get_name() == name),
                None)


def _lies_as_mesh(p, garment, item):
    name = garment.display
    skinned = item.get_components_by_class(unreal.SkeletalMeshComponent)
    model = _named(item, unreal.SkeletalMeshComponent, MODEL)
    worn = p.get(item, WORN_MESH_VAR)
    p.check(f"the {name} on the ground shows one skeletal mesh, its WornMesh",
            model is not None and len(skinned) == 1 and worn is not None
            and model.get_editor_property("skeletal_mesh_asset") == worn
            and model.is_visible(), f"{[c.get_name() for c in skinned]} {worn}")
    if model is None:
        return
    # The engine still makes the mesh asset's post-process instance (the
    # hoodie's, the shoes'); the component's flag is what keeps it from running.
    p.check("...in its reference pose: nothing animates it",
            model.get_anim_instance() is None
            and (model.get_post_process_instance() is None
                 or model.get_editor_property("disable_post_process_blueprint")),
            f"{model.get_anim_instance()} {model.get_post_process_instance()}")
    origin, extent, _r = unreal.SystemLibrary.get_component_bounds(model)
    at = item.get_actor_location()
    p.check("...lying over the item's origin, flat",
            abs(origin.x - at.x) < OVER_CM and abs(origin.y - at.y) < OVER_CM
            and at.z - OVER_CM < origin.z - extent.z and extent.z < min(extent.x, extent.y),
            f"centre {(origin - at).to_tuple()} half {extent.to_tuple()}")
    glimmer = _named(item, unreal.MaterialBillboardComponent, GLIMMER)
    p.check("...and glimmering, as any item on the ground",
            glimmer is not None and glimmer.is_visible())


def probe(p):
    yield lambda: p.pawn() is not None
    yield SETTLE
    world, player, pc = p.world(), p.pawn(), p.controller()
    placed = {a.get_class().get_path_name(): a for a in
              unreal.GameplayStatics.get_all_actors_with_tag(world, TEST_TAG)}
    p.check("the test garments are on the ground", len(placed) == len(GARMENTS),
            str(sorted(placed)))
    plain = []
    for garment in GARMENTS:
        item = placed.get(garment.class_path)
        if item is None:
            continue
        if garment.worn:
            _lies_as_mesh(p, garment, item)
        elif item.get_components_by_class(unreal.SkeletalMeshComponent):
            plain.append(garment.display)
    p.check("the garments with no mesh to be worn as keep their stand-ins",
            not plain, str(plain))
    if not placed:
        return

    # The picture: from over the player's head, down at the middle of the row.
    mid = unreal.Vector()
    for item in placed.values():
        mid += item.get_actor_location() / len(placed)
    eye = player.get_actor_location() + unreal.Vector(0.0, 0.0, EYE_UP_CM)
    player.set_actor_hidden_in_game(True)
    player.set_actor_location(eye, False, False)
    player.get_editor_property("character_movement").set_movement_mode(
        unreal.MovementMode.MOVE_NONE)
    pc.set_control_rotation(unreal.MathLibrary.find_look_at_rotation(eye, mid))
    unreal.SystemLibrary.execute_console_command(world, f"FOV {EYE_FOV:g}", pc)
    yield 2.0       # the camera's boom and the exposure settle
    before = len(os.listdir(SHOTS_DIR)) if os.path.isdir(SHOTS_DIR) else 0
    unreal.SystemLibrary.execute_console_command(world, "shot")
    yield 1.0
    after = len(os.listdir(SHOTS_DIR)) if os.path.isdir(SHOTS_DIR) else 0
    p.note(f"the row of test garments: {after - before} picture(s) in {SHOTS_DIR}")
    unreal.SystemLibrary.execute_console_command(world, "FOV 0", pc)
