"""catalog.py -- the monsters we want, as intent rather than artifacts.

This file is tracked.  It says *what* to make and with which parameters; it
never holds a task id, a result URL or an API key.  Those are artifacts of a
particular run and live in assets/cache/meshy/<id>/task.json, which is
git-ignored -- the same split ``asset_sources.py`` draws between the thing
described and the thing restored.

── Two parameters carry most of the outcome ────────────────────────────────

``pose_mode`` is "a-pose" for every humanoid, always.  SK_Mannequin -- the
skeleton ABP_Unarmed drives -- is authored in A-pose, and a source mesh
generated in T-pose retargets onto it with the shoulders wrong.  The API
parameter is authoritative, so the prompt text must not argue with it: the
zombie description as first written asked for a T-pose and has been
normalised to match.

``enable_pbr`` (set in providers/meshy.py, not here) defaults to FALSE at the
API.  Without it a refine returns base colour only -- no normal, roughness or
metallic -- which reads as flat plastic.  Every realism claim in these prompts
depends on it being on.

Textures are generated at 4k because that is the cheap direction to be wrong
in: Unreal can clamp a 4k source down at import with a max-texture-size or LOD
bias, but it cannot invent detail that was never generated.  Ship-time value
is likely 2k; generation-time value is 4k.
"""

from dataclasses import dataclass

# Measured from SKM_Quinn_Simple on 2026-09-27: box_extent.z 90.084 * 2 =
# 180.17 uu = 1.802 m.  The zombie matches it so that retargeted locomotion
# needs no scale compensation at all.
QUINN_HEIGHT_M = 1.80


@dataclass(frozen=True)
class MonsterSpec:
    """One creature: what to generate, how big, and where it lands."""

    id: str
    prompt: str
    height_meters: float
    dest: str
    target_polycount: int = 30000
    texture_resolution: str = "4k"
    pose_mode: str = "a-pose"
    ai_model: str = "meshy-7.1"
    provider: str = "meshy"
    license: str = "meshy-commercial"
    note: str = ""


MONSTERS = (
    MonsterSpec(
        id="zombie_01",
        prompt=(
            "Realistic horror game zombie, modern era humanoid male, decaying "
            "flesh, torn and bloody hospital gown, exposed bone visible on the "
            "jawline and ribcage, pallid grey mottled skin, sunken glowing "
            "eyes, A-pose, highly detailed, PBR textures, dark survival horror "
            "aesthetic, Unreal Engine 5 style, photorealistic, 4k resolution, "
            "symmetrical posture for rigging"
        ),
        height_meters=QUINN_HEIGHT_M,
        dest="/Game/Sourced/Characters/SKM_Zombie01",
        note="The easy case: human proportions, human silhouette. If the "
             "shared-skeleton idea fails here it fails everywhere.",
    ),
    MonsterSpec(
        id="wendigo_01",
        prompt=(
            "Realistic horror game wendigo, terrifying humanoid creature with "
            "abnormally prolonged emaciated arms, rotting deer skull for a head "
            "with large jagged antlers, tight leathery grey skin stretched "
            "tightly over visible ribs and spine, elongated sharp bone-like "
            "claws on hands, A-pose, highly detailed, PBR textures, dark "
            "fantasy horror, Unreal Engine 5 style, photorealistic, 4k "
            "resolution, symmetrical posture for rigging"
        ),
        height_meters=2.40,
        dest="/Game/Sourced/Characters/SKM_Wendigo01",
        note="The stress test. Antlers are not limbs and the arms are "
             "deliberately out of human proportion, both of which push at what "
             "Meshy's pose estimation says it supports. A failure here is a "
             "result, not a waste: it marks the boundary of the humanoid path.",
    ),
)


def by_id(spec_id: str):
    for spec in MONSTERS:
        if spec.id == spec_id:
            return spec
    raise KeyError(f"no monster spec with id {spec_id!r}")
