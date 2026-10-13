"""In the editor: the two stages of a build, run from the request the host
script left (paths.REQUEST_JSON).

    mesh      each job's source cut into its mesh LODs and written to the
              copy; with an impostor, the copy photographed plane by plane
    impostor  the atlases the host made in between imported, the cards added
              as the last LOD

Whichever stage is a job's last sets the screen sizes and collision, stamps
the mesh, saves it and photographs every LOD for the host's preview sheet
(preview.py). Each stage leaves <stage>.json in the job's working
folder: the next stage and the host's summary read it.
"""

import json
import os

import unreal

from mesh_lod import asset, capture, geometry, impostor, jobs, paths, planes, preview


def _log(msg):
    unreal.log_warning(f"[LOD] {msg}")


def _write(name, stage, data):
    os.makedirs(paths.job_dir(name), exist_ok=True)
    with open(paths.report_json(name, stage), "w") as fh:
        json.dump(data, fh, indent=1)


def _summary(mesh, job, sizes):
    return {"path": job.path, "triangles": asset.lod_triangles(mesh), "screen_sizes": sizes,
            "materials": [s.material_interface.get_name() if s.material_interface else None
                          for s in mesh.static_materials]}


def _bounds(mesh):
    bounds = mesh.get_bounds()
    origin, extent = bounds.origin, bounds.box_extent
    return ((origin.x, origin.y, origin.z), (extent.x, extent.y, extent.z),
            bounds.sphere_radius)


def mesh_stage(job, force):
    name, spec = job.asset_name, job.spec
    if not force and asset.is_built(job):
        _log(f"{name}: already built from this spec, kept")
        _write(name, "mesh", {"kept": True})
        return
    source = asset.load(job.source)
    foliage = geometry.foliage_slots(source, spec)
    _log(f"{name}: from {job.source}, foliage slots {sorted(foliage) or 'none'}")
    parts = geometry.read_source(source)
    lods, table = geometry.build_lods(parts, foliage, spec, _log)
    mesh = asset.open_copy(job)
    asset.write_mesh_lods(mesh, lods)
    origin, extent, radius = _bounds(mesh)
    frame = planes.frame_of(origin, extent)
    report = {"kept": False, "source": job.source,
              "source_triangles": sum(p.get_triangle_count() for p in parts.values()),
              "foliage": sorted(foliage), "slots": table, "radius_cm": radius,
              "frame": frame.__dict__}
    if spec.impostor:
        report["capture_px"] = list(capture.shoot(mesh, name, spec, frame))
        unreal.EditorAssetLibrary.save_loaded_asset(mesh, only_if_is_dirty=False)
    else:
        report["built"] = _summary(mesh, job, asset.finish(mesh, job, foliage, radius))
        preview.shoot(mesh, name)
    _write(name, "mesh", report)


def impostor_stage(job):
    name, spec = job.asset_name, job.spec
    with open(paths.report_json(name, "mesh")) as fh:
        before = json.load(fh)
    if before.get("kept") or not spec.impostor:
        return
    mesh = asset.load(job.path)
    frame = planes.Frame(**before["frame"])
    impostor.build(mesh, job, frame)
    sizes = asset.finish(mesh, job, set(before["foliage"]), before["radius_cm"])
    preview.shoot(mesh, name)
    _write(name, "impostor", {"built": _summary(mesh, job, sizes)})
    _log(f"{name}: LODs {asset.lod_triangles(mesh)} at screen sizes {sizes}")


def main():
    with open(paths.REQUEST_JSON) as fh:
        request = json.load(fh)
    failed = []
    for data in request["jobs"]:
        job = jobs.from_dict(data)
        try:
            if request["stage"] == "mesh":
                mesh_stage(job, request.get("force", False))
            else:
                impostor_stage(job)
        except Exception as error:                         # one bad mesh, not the run
            failed.append(job.asset_name)
            _write(job.asset_name, request["stage"], {"error": str(error)})
            unreal.log_error(f"[LOD] {job.asset_name}: {error}")
    _log(f"stage {request['stage']}: {len(request['jobs']) - len(failed)} done, "
         f"{len(failed)} failed {failed or ''}")
    if failed:
        raise RuntimeError(f"mesh_lod {request['stage']} failed for {failed}")
