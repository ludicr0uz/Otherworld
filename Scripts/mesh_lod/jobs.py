"""The jobs: which mesh is built into what. Pure Python (no ``unreal``).

A job names a source mesh, where the game-ready copy goes and the settings it
changes from spec.LodSpec's defaults. The source is read and never written.

TREES is the forest's five. Their sources are the cut-down trees under
/Game/Forest/Trees rather than the scans: those carry the game's materials
and stand on their trunks (forest_generator/tree_meshes.py), and are a twentieth
of the scan to read. ``planted_scale`` is the middle of what
forest_generator/tree_placement.py plants each at, which is what turns the
distances into screen sizes.
"""

from dataclasses import dataclass, field

from mesh_lod.spec import LodSpec, with_overrides

DEFAULT_DEST = "/Game/GameReady"
TREE_DEST = "/Game/Forest/TreesLOD"


@dataclass(frozen=True)
class Job:
    source: str                      # /Game path of the mesh to build from
    dest: str = DEFAULT_DEST         # the folder the built mesh goes in
    name: str = ""                   # the built mesh's name; "": the source's
    overrides: dict = field(default_factory=dict)

    @property
    def asset_name(self):
        return self.name or self.source.rsplit("/", 1)[-1]

    @property
    def path(self):
        return f"{self.dest}/{self.asset_name}"

    @property
    def spec(self):
        return with_overrides(LodSpec(), self.overrides)

    # The impostor's own assets, beside the mesh.
    @property
    def impostor_dir(self):
        return f"{self.dest}/Impostors"

    def texture_path(self, kind):
        return f"{self.impostor_dir}/T_{self.asset_name}_Impostor_{kind}"

    @property
    def material_path(self):
        return f"{self.impostor_dir}/MI_{self.asset_name}_Impostor"

    @property
    def master_path(self):
        return f"{self.impostor_dir}/M_Impostor"

    def to_dict(self):
        return {"source": self.source, "dest": self.dest, "name": self.name,
                "overrides": dict(self.overrides)}


def from_dict(data):
    return Job(data["source"], data.get("dest") or DEFAULT_DEST, data.get("name", ""),
               dict(data.get("overrides") or {}))


def _tree(name, scale_min, scale_max):
    return Job(f"/Game/Forest/Trees/{name}", TREE_DEST,
               overrides={"planted_scale": round((scale_min + scale_max) / 2.0, 2)})


TREES = (
    _tree("SM_Fir_A", 1.8, 3.8),
    _tree("SM_IslandTree_01", 2.0, 3.6),
    _tree("SM_IslandTree_02", 2.0, 3.6),
    _tree("SM_PineSapling_A", 3.0, 5.5),
    _tree("SM_TreeSmall_02", 2.5, 4.2),
)

SETS = {"trees": TREES}
