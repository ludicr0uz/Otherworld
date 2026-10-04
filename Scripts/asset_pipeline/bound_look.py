"""bound_look.py -- photograph bodies in a clip's pose, for looking at.

Editor-side tooling: nothing in the game reads what it writes.

    python3 Scripts/dev/uepy.py --cold Scripts/asset_pipeline/bound_look.py

For each body in SUBJECTS -- the bound one, the same body on its own skeleton,
and Quinn -- and each clip in CLIPS, one PNG per moment and view under
Saved/Renders/bound_look/.  The bound body and Quinn play the mannequin's own
clip; the per-body one plays its retargeted copy.  What to look at is in
import_bound.py's docstring: shoulders under lifted arms, forearms, fingers.

A SceneCapture2D into a render target, as dev/render_character.py does it and
for its reasons; the pose is a SingleAnimationPlayData set before the mesh, as
item_icons/capture.py does it (nothing ticks an animation in this harness).
"""

import os
import sys

import unreal

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

for _name in [m for m in sys.modules if m.startswith("asset_pipeline")]:
    del sys.modules[_name]

from asset_pipeline import player_body                              # noqa: E402
from asset_pipeline.mannequin_bind import paths                     # noqa: E402

EAL = unreal.EditorAssetLibrary
_log = unreal.log_warning
NAME = player_body.PLAYER_NAME
OUT_DIR = os.path.join(unreal.Paths.project_dir(), "Saved", "Renders", "bound_look")
SIZE = (700, 1000)
STAGE = unreal.Vector(0.0, 0.0, 500000.0)
FOV = 30.0
MANNEQUIN_ANIMS = "/Game/Characters/Mannequins/Anims"
OWN_ANIMS = f"/Game/Sourced/Characters/Anims/{NAME}"

# label -> (mesh, clip path for a mannequin clip's short path)
SUBJECTS = (
    ("bound", f"{paths.bound_asset_dir(NAME)}/{paths.bound_asset_name(NAME)}",
     lambda clip: f"{MANNEQUIN_ANIMS}/{clip}"),
    ("own", f"/Game/Sourced/Characters/SKM_{NAME}/SKM_{NAME}",
     lambda clip: f"{OWN_ANIMS}/A_{NAME}_{clip.rsplit('/', 1)[1]}"),
    ("quinn", "/Game/Characters/Mannequins/Meshes/SKM_Quinn_Simple",
     lambda clip: f"{MANNEQUIN_ANIMS}/{clip}"),
)
# (clip under the mannequin's Anims/, shares of its length to photograph)
CLIPS = (
    ("Unarmed/MM_Idle", (0.0,)),
    ("Unarmed/Jump/MM_Jump", (0.25, 0.6)),
    ("Unarmed/Jump/MM_Fall_Loop", (0.5,)),
    ("Unarmed/Attack/MM_Attack_01", (0.3, 0.45)),
    ("Rifle/MF_Rifle_Idle_ADS", (0.0,)),
)
# name -> (height of the point looked at, where the camera stands from it);
# the body faces +Y.  "front" and "back" take the whole body in a jump;
# "chest" is the shoulders, arms and hands from in front and a little above.
VIEWS = {"front": (105.0, unreal.Vector(0.0, 400.0, 10.0)),
         "back": (105.0, unreal.Vector(0.0, -400.0, 10.0)),
         "chest": (130.0, unreal.Vector(70.0, 210.0, 25.0))}


def _spawn(cls, location, rotation=None):
    return unreal.EditorLevelLibrary.spawn_actor_from_class(
        cls, location, rotation or unreal.Rotator())


def _lights(spawned):
    for yaw in (250.0, 70.0):           # one from the front, one from behind
        key = _spawn(unreal.DirectionalLight, STAGE, unreal.Rotator(0.0, -35.0, yaw))
        spawned.append(key)
        key.get_component_by_class(unreal.DirectionalLightComponent).set_intensity(5.0)
    sky = _spawn(unreal.SkyLight, STAGE)
    spawned.append(sky)
    comp = sky.get_component_by_class(unreal.SkyLightComponent)
    comp.set_editor_property("intensity", 2.2)
    comp.recapture_sky()


def shoot(mesh, clip, seconds, view, out_path):
    world = unreal.EditorLevelLibrary.get_editor_world()
    target = unreal.RenderingLibrary.create_render_target2d(
        world, SIZE[0], SIZE[1], unreal.TextureRenderTargetFormat.RTF_RGBA8_SRGB)
    spawned = []
    try:
        actor = _spawn(unreal.SkeletalMeshActor, STAGE)
        spawned.append(actor)
        body = actor.skeletal_mesh_component
        play = unreal.SingleAnimationPlayData()
        play.set_editor_property("anim_to_play", clip)
        play.set_editor_property("saved_position", seconds)
        play.set_editor_property("saved_playing", False)
        body.set_editor_property("animation_mode", unreal.AnimationMode.ANIMATION_SINGLE_NODE)
        body.set_editor_property("animation_data", play)
        body.set_skinned_asset_and_update(mesh)
        body.set_forced_lod(1)
        _lights(spawned)

        height, offset = VIEWS[view]
        centre = unreal.Vector(STAGE.x, STAGE.y, STAGE.z + height)
        eye = centre + offset
        cam = _spawn(unreal.SceneCapture2D, eye,
                     unreal.MathLibrary.find_look_at_rotation(eye, centre))
        spawned.append(cam)
        cap = cam.get_component_by_class(unreal.SceneCaptureComponent2D)
        cap.set_editor_property("texture_target", target)
        cap.set_editor_property("fov_angle", FOV)
        cap.set_editor_property("capture_source", unreal.SceneCaptureSource.SCS_FINAL_COLOR_LDR)
        cap.set_editor_property(
            "primitive_render_mode", unreal.SceneCapturePrimitiveRenderMode.PRM_USE_SHOW_ONLY_LIST)
        cap.show_only_actor_components(actor, True)
        cap.set_editor_property("capture_every_frame", True)
        for _ in range(8):
            cap.capture_scene()
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        unreal.RenderingLibrary.export_render_target(
            world, target, os.path.dirname(out_path), os.path.basename(out_path))
    finally:
        for a in spawned:
            unreal.EditorLevelLibrary.destroy_actor(a)


def main():
    made = 0
    for label, mesh_path, clip_of in SUBJECTS:
        mesh = EAL.load_asset(mesh_path) if EAL.does_asset_exist(mesh_path) else None
        if not mesh:
            _log(f"[LOOK] {label}: {mesh_path} is not imported, skipped")
            continue
        for short, shares in CLIPS:
            path = clip_of(short)
            clip = EAL.load_asset(path) if EAL.does_asset_exist(path) else None
            if not clip:
                _log(f"[LOOK] {label}: no {path}, skipped")
                continue
            for share in shares:
                seconds = share * clip.get_play_length()
                for view in VIEWS:
                    name = f"{short.rsplit('/', 1)[1]}_{int(share * 100):02d}_{view}_{label}.png"
                    shoot(mesh, clip, seconds, view, os.path.join(OUT_DIR, name))
                    made += 1
    _log(f"[LOOK] {made} pictures -> {OUT_DIR}")


if __name__ == "__main__":
    main()
