"""The title's stage is a night forest: the play level's middle trees round
the figure, under the forest's night.

    python3 Scripts/dev/uepy.py --game --title --probe Scripts/probes/probe_title_forest.py
    python3 Scripts/dev/uepy.py --game --title --windowed --probe Scripts/probes/probe_title_forest.py

  the trees    the running title holds every tree title/forest.py picks, in
               their cells, and the nearest stands outside the clearing
  the figure   stands on the forest floor, where the stage put it, in front
               of the stage's camera: nothing planted took its place or its
               footing
  the night    the moon and the sky light are the forest night's, and no
               day/night clock runs

With a window (--windowed) it also saves a picture of the title to
Saved/Screenshots/MacEditor, the only way to see how the night reads.
"""

SYSTEMS = ('title',)
LEVEL = "/Game/Maps/Lvl_Title"

import unreal

from forest_generator.lighting import get_preset
from probes import title as T
from title import forest
from title import paths as P

GS = unreal.GameplayStatics
HISM = unreal.HierarchicalInstancedStaticMeshComponent
# The exposure settles on the dark before the picture is taken.
SETTLE_S = 6.0
STAND_TOLERANCE_CM = 150.0


def _tree_cells(p):
    cells = []
    for a in GS.get_all_actors_of_class(p.world(), unreal.Actor):
        root = a.get_editor_property("root_component")
        if isinstance(root, HISM) and "Forest/Trees" in root.get_editor_property(
                "static_mesh").get_path_name():
            cells.append(root)
    return cells


def probe(p):
    yield from T.wait(lambda: T.on_title(p) and p.pawn() is not None)
    if not T.on_title(p):
        p.check("the game opens on the title level (run with uepy.py --game --title)", False,
                f"level {T.level_name(p) if p.world() else None}")
        return
    yield from T.wait(lambda: False, 1.0)

    placements = forest.trees()
    cells = _tree_cells(p)
    planted = sum(c.get_instance_count() for c in cells)
    p.check(f"the title holds the play level's {len(placements)} middle trees",
            planted == len(placements), f"{planted} in {len(cells)} cells")

    at = p.pawn().get_actor_location()
    p.check("the figure stands on the forest floor where the stage put it",
            (at - unreal.Vector(*P.PLAYER_START)).length() < STAND_TOLERANCE_CM,
            f"{at}")

    night = get_preset(P.NIGHT_PRESET)
    moons = GS.get_all_actors_of_class(p.world(), unreal.DirectionalLight)
    lux = [m.get_component_by_class(unreal.DirectionalLightComponent)
           .get_editor_property("intensity") for m in moons]
    skies = GS.get_all_actors_of_class(p.world(), unreal.SkyLight)
    p.check("one directional light, the night's moon, and one sky light",
            len(lux) == 1 and abs(lux[0] - night["sun"]["intensity"]) < 1e-3
            and len(skies) == 1, f"lux {lux}, {len(skies)} sky lights")
    clocks = [a.get_name() for a in GS.get_all_actors_of_class(p.world(), unreal.Actor)
              if "DayNight" in a.get_class().get_name()]
    p.check("no day/night clock runs on the title: the night stays", not clocks, str(clocks))

    if "-nullrhi" not in str(unreal.SystemLibrary.get_command_line()).lower():
        yield from T.wait(lambda: False, SETTLE_S)
        unreal.SystemLibrary.execute_console_command(p.world(), "shot showui")
        p.note("shot showui: the title in the night forest")
        yield from T.wait(lambda: False, 1.0)
