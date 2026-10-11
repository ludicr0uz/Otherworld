"""verify_title_level.py's checks: the level exists and is the game's
default map, and the stage holds exactly its actors, each as title/paths.py
numbers it."""

import os
import re

import unreal

from combat.verify.common import check
from title import paths as P

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _actors():
    return unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()


def _by_label(actors):
    found = {}
    for a in actors:
        found.setdefault(a.get_actor_label(), []).append(a)
    return found


def _near(v, xyz, tol=0.5):
    return (v - unreal.Vector(*xyz)).length() < tol


def _rot(actor):
    r = actor.get_actor_rotation()
    return (round(r.pitch, 2), round(r.yaw, 2), round(r.roll, 2))


def check_config():
    with open(os.path.join(ROOT, "Config", "DefaultEngine.ini")) as f:
        ini = f.read()
    found = re.search(r"^GameDefaultMap=(.*)$", ini, re.M)
    name = P.TITLE_LEVEL.rsplit("/", 1)[1]
    check(f"the game opens on the title level: DefaultEngine.ini's GameDefaultMap is {P.TITLE_LEVEL}",
          found is not None and found.group(1).strip() == f"{P.TITLE_LEVEL}.{name}",
          found.group(1) if found else "no GameDefaultMap")


def check_level():
    les = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    check(f"{P.TITLE_LEVEL} exists and loads", les.load_level(P.TITLE_LEVEL))
    actors = _actors()
    found = _by_label(actors)
    check("the stage holds each of its actors once, and nothing else: no forest, "
          "no wanderers, no day/night",
          all(len(found.get(label, [])) == 1 for label in P.LABELS)
          and set(found) == set(P.LABELS),
          str(sorted(found)))
    return found


def check_floor(found):
    floor = found.get(P.FLOOR_LABEL, [None])[0]
    smc = floor.get_component_by_class(unreal.StaticMeshComponent) if floor else None
    mesh = smc.get_editor_property("static_mesh") if smc else None
    mat = smc.get_material(0) if smc else None
    flat = (isinstance(mat, unreal.Material)
            and unreal.MaterialEditingLibrary.get_num_material_expressions(mat) == 3)
    check("the floor: the engine's cube in the title's own near-black matte (a flat "
          "material: base colour, metallic, roughness), its top at z = 0, blocking",
          mesh is not None and mesh.get_path_name().split(".")[0] == P.FLOOR_MESH
          and mat is not None and mat.get_path_name().split(".")[0] == P.FLOOR_MATERIAL
          and _near(floor.get_actor_scale3d(), P.FLOOR_SCALE, 1e-3)
          and _near(floor.get_actor_location(), (0.0, 0.0, P.FLOOR_Z))
          and str(smc.get_collision_profile_name()) == "BlockAll"
          and flat,
          f"{mesh and mesh.get_name()}, {mat and mat.get_name()}, flat {flat}")


def check_figure_place(found):
    start = found.get(P.PLAYER_START_LABEL, [None])[0]
    check("the figure spawns on the stage: one PlayerStart, where the builder put it, "
          "facing +X",
          start is not None and _near(start.get_actor_location(), P.PLAYER_START)
          and _rot(start) == (0.0, P.PLAYER_START_YAW, 0.0),
          f"{start and start.get_actor_location()} {start and _rot(start)}")


def check_camera(found):
    cam = found.get(P.CAMERA_LABEL, [None])[0]
    cc = cam.get_component_by_class(unreal.CameraComponent) if cam else None
    auto = cam.get_editor_property("auto_activate_for_player") if cam else None
    check("the title is seen through the stage's camera: a CameraActor in front of the "
          "figure, taken by player 0 as the level comes up, at its field of view",
          isinstance(cam, unreal.CameraActor) and _near(cam.get_actor_location(), P.CAMERA)
          and _rot(cam) == tuple(round(x, 2) for x in P.CAMERA_ROTATION)
          and auto == unreal.AutoReceiveInput.PLAYER0
          and abs(cc.get_editor_property("field_of_view") - P.CAMERA_FOV) < 1e-3
          and not cc.get_editor_property("constrain_aspect_ratio"),
          f"{cam and cam.get_actor_location()} {cam and _rot(cam)} auto {auto}")


def _light(found, label, spec, shadows):
    light = found.get(label, [None])[0]
    comp = light.get_component_by_class(unreal.DirectionalLightComponent) if light else None
    colour = comp.get_editor_property("light_color") if comp else None
    want = unreal.LinearColor(*spec["color"], 1.0).to_color(True) if comp else None
    check(f"{label}: a directional light at {spec['intensity']} lux, "
          f"{'with' if shadows else 'no'} shadows, where the builder aimed it",
          comp is not None and abs(comp.get_editor_property("intensity") - spec["intensity"]) < 1e-3
          and _rot(light) == tuple(round(x, 2) for x in spec["rotation"])
          and bool(comp.get_editor_property("cast_shadows")) is shadows
          and (colour.r, colour.g, colour.b) == (want.r, want.g, want.b),
          f"{light and _rot(light)} {comp and comp.get_editor_property('intensity')} {colour}")


def check_lights(found):
    _light(found, P.KEY_LIGHT_LABEL, P.KEY_LIGHT, True)
    _light(found, P.FILL_LIGHT_LABEL, P.FILL_LIGHT, False)
    fog = found.get(P.FOG_LABEL, [None])[0]
    fc = fog.get_component_by_class(unreal.ExponentialHeightFogComponent) if fog else None
    check("the fog fades the floor into black with distance",
          fc is not None and abs(fc.get_editor_property("fog_density") - P.FOG["density"]) < 1e-6
          and abs(fc.get_editor_property("fog_height_falloff") - P.FOG["height_falloff"]) < 1e-6,
          f"{fc and fc.get_editor_property('fog_density')}")
    ppv = found.get(P.POST_PROCESS_LABEL, [None])[0]
    settings = ppv.get_editor_property("settings") if ppv else None
    lo = settings.get_editor_property("auto_exposure_min_brightness") if settings else None
    hi = settings.get_editor_property("auto_exposure_max_brightness") if settings else None
    overridden = {f: bool(settings.get_editor_property(f)) for f in P.EXPOSURE_OVERRIDES} \
        if settings else {"none": False}
    check("the exposure is fixed (min = max, each with its override flag) over the whole stage: no hunting over the dark",
          ppv is not None and ppv.get_editor_property("unbound")
          and abs(lo - P.EXPOSURE["min_brightness"]) < 1e-6 and abs(hi - lo) < 1e-6
          and abs(settings.get_editor_property("auto_exposure_bias") - P.EXPOSURE["bias"]) < 1e-6
          and all(overridden.values()),
          f"{lo}..{hi}, overrides {overridden}")


def run():
    check_config()
    found = check_level()
    check_floor(found)
    check_figure_place(found)
    check_camera(found)
    check_lights(found)
