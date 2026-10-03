# Skeleton Compatibility Guide for Meshy Generation

## Problem

When Meshy generates humanoid characters, the resulting skeleton may have different proportions than a reference skeleton (e.g., Adventurer01). This causes cascading re-tuning work:

- Hold poses (how weapons are held) need re-authoring
- Hit zones (head, chest, limbs) need re-measuring
- Weapon animations need re-fitting to hand positions
- Grip points for items need recalibration
- Movement speeds and animation clips may need adjustments

The Adventurer02 model swap (2026-10-02/10-03) demonstrated this: a single model change cascaded into ~25 minutes of weapon build + 13 verifier failures + extensive re-tuning across body_pose, hold_pose, hit_bodies, physics assets, and grip locations.

## Solution: Skeleton Templates

When generating a new male humanoid model, specify `skeleton_template="adventurer01_humanoid"` in the spec. This tells the pipeline to:

1. **Include prompt guidance** — the Meshy prompt explicitly requests skeleton compatibility
2. **Record the constraint** — task.json logs that the model should be drop-in compatible
3. **Enable future validation** — downstream verifiers can check Adventurer01 compatibility

## How to Generate a Compatible Male Humanoid

### 1. Add a spec to `catalog.py`

```python
MonsterSpec(
    id="my_character",
    prompt=(
        # Include this in the prompt for Meshy:
        "... humanoid male character with standard humanoid skeleton "
        "compatible with Adventurer01 rig ..."
    ),
    height_meters=1.80,  # Match Adventurer01: QUINN_HEIGHT_M
    dest="/Game/Sourced/Characters/SKM_MyCharacter",
    skeleton_template="adventurer01_humanoid",
)
```

### 2. What the Prompt Should Include

- **"humanoid male"** — explicit gender and form
- **"standard humanoid skeleton"** — no unusual limb counts or proportions
- **"compatible with Adventurer01 rig"** — direct reference to the target
- **Height: ~1.80 m** — QUINN_HEIGHT_M, matching Adventurer01
- **A-pose** — required for retargeting (not T-pose)
- **Standard limbs** — no unusually long arms, no extra joints

### 3. Prompt Anti-Patterns (Things That Break Compatibility)

❌ "humanoid creature with abnormally prolonged emaciated arms" → broke Adventurer02  
❌ "creature with a deer skull for a head with large jagged antlers" → non-human spine count  
❌ "T-pose" → breaks animation retargeting  
❌ Height far from 1.80 m → stride length mismatch  
❌ "wearing a backpack" → loose geometry, wrong rigging  

## Expected Outcome

If skeleton_template is set and the prompt includes compatibility guidance:

- ✓ Physics asset should have Head, Spine01, Spine02 bodies (matching Adventurer01)
- ✓ Bone names and hierarchy match (pelvis, spine_01..03, clavicle_l, etc.)
- ✓ Limb proportions are close enough that hold poses need minimal adjustment
- ✓ Animation retargeting from UAL1/UAL2 works without re-measuring
- ✓ Weapons and items fit in hand positions without extensive tuning
- ✓ Weapons build takes ~4 minutes, not 25+

## Verification

After generation, the import process should verify:

1. **Bone count and names** — check against Adventurer01's skeleton
2. **Physics bodies** — ensure Head and Spine01 exist and are positioned correctly
3. **Height scale** — verify arrival height matches spec.height_meters
4. **Bone proportions** — spot-check key bones (clavicle, thigh, forearm lengths)

If verification fails, the model may not be compatible despite the prompt guidance. In that case, add issues to the next Meshy request or escalate to manual retargeting (the old path).

## Future Work

- Add bone measurement comparison to the verifier suite
- Create a `verify_skeleton_compatibility.py` check
- Track which specs successfully used `skeleton_template="adventurer01_humanoid"`
- Build a Meshy prompt library of successful humanoid prompts
- Consider requesting a Meshy API parameter for explicit skeleton constraints (when they expose it)
