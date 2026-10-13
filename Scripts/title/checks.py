"""verify_title_level.py's checks: the level exists and is the game's
default map, and the stage holds exactly its actors, each as title/paths.py
numbers it: the forest floor, the play level's middle trees, the night."""

import os
import re

import unreal

from combat.verify.common import check
from forest_generator.lighting import get_preset
from forest_import import trees as trees_import
from title import forest
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
    others = {label for label in found if not label.startswith(P.TREE_LABEL_PREFIX)}
    check("the stage holds each of its actors once, and beside them only its trees: "
          "no terrain, no wanderers, no day/night clock",
          all(len(found.get(label, [])) == 1 for label in P.LABELS)
          and others == set(P.LABELS),
          str(sorted(others)))
    return found


def check_trees():
    """The trees are the play level's middle ones, planted as that level
    plants them (forest_import/trees.py's own checks: counts, collision,
    the LOD build, draw distances)."""
    placements = forest.trees()
    nearest = min((t["x"] ** 2 + t["y"] ** 2) ** 0.5 for t in placements)
    check(f"the stage stands in a thick wood: over 150 trees within "
          f"{P.TREE_RADIUS_CM / 100:g} m, none within 7 m of the figure",
          len(placements) > 150 and nearest >= 700.0,
          f"{len(placements)} trees, the nearest at {nearest / 100:.1f} m")
    trees_import.verify_trees(lambda name, ok, detail="": check(f"title trees: {name}", ok, detail),
                              _actors(), forest.counts(placements), len(placements),
                              P.TITLE_LEVEL_NAME)


def check_floor(found):
    floor = found.get(P.FLOOR_LABEL, [None])[0]
    smc = floor.get_component_by_class(unreal.StaticMeshComponent) if floor else None
    mesh = smc.get_editor_property("static_mesh") if smc else None
    mat = smc.get_material(0) if smc else None
    check("the floor: the engine's cube in the forest's ground, wide enough to hold the "
          "trees, its top at z = 0, blocking",
          mesh is not None and mesh.get_path_name().split(".")[0] == P.FLOOR_MESH
          and mat is not None and mat.get_path_name().split(".")[0] == P.FLOOR_MATERIAL
          and _near(floor.get_actor_scale3d(), P.FLOOR_SCALE, 1e-3)
          and _near(floor.get_actor_location(), (0.0, 0.0, P.FLOOR_Z))
          and P.FLOOR_SCALE[0] * 50.0 > P.TREE_RADIUS_CM
          and str(smc.get_collision_profile_name()) == "BlockAll",
          f"{mesh and mesh.get_name()}, {mat and mat.get_name()}")


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


def check_moon(found, cfg):
    moon = found.get(P.MOON_LABEL, [None])[0]
    comp = moon.get_component_by_class(unreal.DirectionalLightComponent) if moon else None
    colour = comp.get_editor_property("light_color") if comp else None
    check(f"the moon: the forest night's directional light, {cfg['intensity']} lux, "
          "with shadows, low in the sky on the camera's side of the figure",
          comp is not None and abs(comp.get_editor_property("intensity") - cfg["intensity"]) < 1e-3
          and _rot(moon) == (cfg["pitch"], cfg["yaw"], 0.0)
          and bool(comp.get_editor_property("cast_shadows"))
          and [colour.r, colour.g, colour.b] == cfg["color"],
          f"{moon and _rot(moon)} {comp and comp.get_editor_property('intensity')} {colour}")


def check_sky(found, cfg):
    dome = found.get(P.SKY_SPHERE_LABEL, [None])[0]
    smc = dome.get_component_by_class(unreal.StaticMeshComponent) if dome else None
    mat = smc.get_material(0) if smc else None
    sky = found.get(P.SKY_LIGHT_LABEL, [None])[0]
    comp = sky.get_component_by_class(unreal.SkyLightComponent) if sky else None
    check("the sky: the forest's starfield on a dome, captured by the sky light as the "
          "stage's ambient light",
          mat is not None and mat.get_path_name().split(".")[0] == P.SKY_SPHERE_MATERIAL
          and comp is not None and bool(comp.get_editor_property("real_time_capture"))
          and abs(comp.get_editor_property("intensity") - cfg["intensity"]) < 1e-3
          and isinstance(found.get(P.SKY_ATMOSPHERE_LABEL, [None])[0], unreal.SkyAtmosphere),
          f"{mat and mat.get_name()}, sky light {comp and comp.get_editor_property('intensity')}")


def check_fog_and_exposure(found, night):
    fog = found.get(P.FOG_LABEL, [None])[0]
    fc = fog.get_component_by_class(unreal.ExponentialHeightFogComponent) if fog else None
    check("the fog is the forest night's: its density, volumetric",
          fc is not None
          and abs(fc.get_editor_property("fog_density") - night["fog"]["density"]) < 1e-6
          and bool(fc.get_editor_property("enable_volumetric_fog")),
          f"{fc and fc.get_editor_property('fog_density')}")
    ppv = found.get(P.POST_PROCESS_LABEL, [None])[0]
    settings = ppv.get_editor_property("settings") if ppv else None
    got = {k: settings.get_editor_property(k) for k in P.EXPOSURE_KEYS} if settings else {}
    overridden = {f: bool(settings.get_editor_property(f)) for f in P.EXPOSURE_OVERRIDES} \
        if settings else {"none": False}
    check("the exposure is the forest night's range (each value with its override flag) "
          "over the whole stage",
          ppv is not None and ppv.get_editor_property("unbound")
          and all(abs(got[k] - night["post_process"][k]) < 1e-6 for k in P.EXPOSURE_KEYS)
          and all(overridden.values()),
          f"{got}, overrides {overridden}")


def run():
    check_config()
    found = check_level()
    check_floor(found)
    check_figure_place(found)
    check_camera(found)
    check_trees()
    night = get_preset(P.NIGHT_PRESET)
    check_moon(found, night["sun"])
    check_sky(found, night["sky_light"])
    check_fog_and_exposure(found, night)
