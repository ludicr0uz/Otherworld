"""meshy.py -- Meshy.ai client: text -> mesh -> textures -> skeleton.

Standard library only, matching the existing download_*.py scripts: no
third-party HTTP dependency for a fresh clone to install.

── The chain, and why it is in this order ──────────────────────────────────

    preview   POST /openapi/v2/text-to-3d   ~20 credits   untextured geometry
    refine    POST /openapi/v2/text-to-3d   ~10 credits   PBR textures
    rig       POST /openapi/v1/rigging        5 credits   skeleton + weights

Rigging is last and cannot be reordered: the API rejects untextured meshes,
so the refine has to land first.  It also accepts GLB only, which is why every
stage requests "glb" even though the rigger hands back FBX as well.

Note the version skew -- generation is /v2, rigging is /v1.  That is Meshy's,
not a typo here.

── Credits are money, so every stage is resumable ──────────────────────────

Each spec keeps a task.json beside its downloads recording the id and status
of every stage that has completed.  Re-running picks up where it stopped
rather than re-paying for work already done.  A stage is only written to
task.json once the API has reported SUCCEEDED for it.
"""

import json
import os
import ssl
import time
import urllib.error
import urllib.request

API_ROOT = "https://api.meshy.ai"
# .../Scripts/asset_pipeline/providers/meshy.py -> four levels up is the
# project root, the directory holding Otherworld.uproject.
PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))
CACHE_ROOT = os.path.join(PROJECT_DIR, "assets", "cache", "meshy")
ENV_FILE = os.path.join(PROJECT_DIR, "assets", ".env")

POLL_SECONDS = 10
POLL_TIMEOUT = 1800  # 30 min; a 4k refine is the slow stage

_ctx = ssl.create_default_context()


class MeshyError(RuntimeError):
    pass


def api_key() -> str:
    """The key, from the environment or the git-ignored assets/.env.

    Never read from a tracked file and never logged -- the error below names
    the file, not the value.
    """
    key = os.environ.get("MESHY_API_KEY", "").strip()
    if key:
        return key
    if os.path.exists(ENV_FILE):
        with open(ENV_FILE) as fh:
            for line in fh:
                line = line.strip()
                if line.startswith("#") or "=" not in line:
                    continue
                name, _, value = line.partition("=")
                if name.strip() == "MESHY_API_KEY":
                    return value.strip()
    raise MeshyError(
        f"no MESHY_API_KEY in the environment or {ENV_FILE}"
    )


def _request(method: str, path: str, payload=None):
    url = f"{API_ROOT}{path}"
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Authorization", f"Bearer {api_key()}")
    if data:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, context=_ctx, timeout=120) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        body = exc.read().decode(errors="replace")[:600]
        raise MeshyError(f"{method} {path} -> HTTP {exc.code}: {body}") from None


def poll(path: str, task_id: str, label: str) -> dict:
    """Block until the task settles. Returns the finished task object."""
    deadline = time.time() + POLL_TIMEOUT
    last = -1
    while time.time() < deadline:
        task = _request("GET", f"{path}/{task_id}")
        status = task.get("status")
        progress = task.get("progress", 0)
        if progress != last:
            print(f"    {label}: {status} {progress}%", flush=True)
            last = progress
        if status == "SUCCEEDED":
            return task
        if status in ("FAILED", "CANCELED"):
            err = task.get("task_error") or task.get("error") or {}
            raise MeshyError(f"{label} {status}: {err}")
        time.sleep(POLL_SECONDS)
    raise MeshyError(f"{label} still {status} after {POLL_TIMEOUT}s (id {task_id})")


# ── the three stages ────────────────────────────────────────────────────────

def preview(spec) -> str:
    body = {
        "mode": "preview",
        "prompt": spec.prompt,
        "ai_model": spec.ai_model,
        "pose_mode": spec.pose_mode,
        "target_polycount": spec.target_polycount,
        "topology": "triangle",
        "target_formats": ["glb"],
    }
    return _request("POST", "/openapi/v2/text-to-3d", body)["result"]


def refine(spec, preview_task_id: str) -> str:
    body = {
        "mode": "refine",
        "preview_task_id": preview_task_id,
        # Defaults to False at the API. Everything these prompts claim about
        # realism depends on it: without PBR there is no normal, roughness or
        # metallic map and the result shades like plastic.
        "enable_pbr": True,
        "texture_resolution": spec.texture_resolution,
        "target_formats": ["glb", "fbx"],
    }
    return _request("POST", "/openapi/v2/text-to-3d", body)["result"]


def remesh(spec, input_task_id: str) -> tuple:
    """Decimate to a game-legal face count. Returns (task_id, path_used).

    Necessary, not optional.  ``target_polycount`` on the *preview* does not
    survive the refine: a 30k-triangle preview came back from refine at
    723,976 faces, which the rigger rejects outright at its 320k ceiling.
    This stage is what actually enforces the budget, and 30k is chosen for the
    game rather than for the ceiling -- several of these are on screen at once.

    The endpoint version is contested: the docs say /v1/remesh, while the
    rigger's own 400 message points at /v2/remesh. Try the documented one and
    fall back, rather than betting on either.
    """
    body = {
        "input_task_id": input_task_id,
        "target_polycount": spec.target_polycount,
        "topology": "triangle",
        "target_formats": ["glb", "fbx"],
    }
    last = None
    for path in ("/openapi/v1/remesh", "/openapi/v2/remesh"):
        try:
            return _request("POST", path, body)["result"], path
        except MeshyError as exc:
            last = exc
            if "404" not in str(exc):
                raise
    raise last


def rig(spec, refine_task_id: str) -> str:
    body = {
        "input_task_id": refine_task_id,
        "height_meters": spec.height_meters,
    }
    return _request("POST", "/openapi/v1/rigging", body)["result"]


# ── cache bookkeeping ───────────────────────────────────────────────────────

def cache_dir(spec) -> str:
    path = os.path.join(CACHE_ROOT, spec.id)
    os.makedirs(path, exist_ok=True)
    return path


def load_state(spec) -> dict:
    path = os.path.join(cache_dir(spec), "task.json")
    if os.path.exists(path):
        with open(path) as fh:
            return json.load(fh)
    return {"id": spec.id, "stages": {}}


def save_state(spec, state: dict) -> None:
    with open(os.path.join(cache_dir(spec), "task.json"), "w") as fh:
        json.dump(state, fh, indent=2, sort_keys=True)


def download(url: str, dest: str) -> str:
    if os.path.exists(dest) and os.path.getsize(dest) > 0:
        return dest
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    req = urllib.request.Request(url, headers={"User-Agent": "Otherworld/1.0"})
    with urllib.request.urlopen(req, context=_ctx, timeout=300) as resp:
        body = resp.read()
    with open(dest, "wb") as fh:
        fh.write(body)
    print(f"    saved {os.path.basename(dest)} ({len(body) / 1e6:.1f} MB)", flush=True)
    return dest
