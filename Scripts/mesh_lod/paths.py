"""Where a build's working files live: under git-ignored assets/generated.
No ``unreal`` import. The assets themselves go where the job says.
"""

import os

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
WORK_DIR = os.path.join(PROJECT_DIR, "assets", "generated", "mesh_lod")
# build_game_ready_mesh.py writes it, editor_build.py reads it: the stage to
# run and the jobs.
REQUEST_JSON = os.path.join(WORK_DIR, "request.json")
PASSES = ("base", "normal")


def job_dir(name):
    return os.path.join(WORK_DIR, name)


def pass_file(name, plane, kind):
    """One plane's capture, raw float32 RGB: ``kind`` is "base" or "normal"."""
    return os.path.join(job_dir(name), f"plane{plane}_{kind}.f32")


def atlas_png(name, kind):
    """The atlas the editor imports: "BC" (colour and mask) or "N"."""
    return os.path.join(job_dir(name), f"T_{name}_Impostor_{kind}.png")


def report_json(name, stage):
    """What a stage found and built, for the next stage and the summary."""
    return os.path.join(job_dir(name), f"{stage}.json")


def preview_file(name, lod, kind):
    """One LOD's preview pass, raw float32 RGB like a plane's."""
    return os.path.join(job_dir(name), f"preview_lod{lod}_{kind}.f32")


def preview_png(name):
    """The picture of every LOD side by side, for a person to look at."""
    return os.path.join(job_dir(name), f"{name}_lods.png")
