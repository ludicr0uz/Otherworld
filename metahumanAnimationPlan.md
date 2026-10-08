# MetaHuman player + Game Animation Sample plan

Written 2026-10-07. Status of the project when written: the Meshy adventurer
is bound to SK_Mannequin (Scripts/asset_pipeline/mannequin_bind, PLAYER_RIG =
"mannequin"); the remaining complaints (strafe, stretched lats, hand-built
weapon poses) are animation quality, not binding. Decision: move the player to
a sample MetaHuman body and to Epic's Game Animation Sample (GAS) clips, and
stop hand-rolling animations.

## Local inputs (all UE 5.8, all on this machine)

| Project | Path | Holds |
|---|---|---|
| MetaHumans sample | `~/Documents/Unreal Projects/MetaHumans 5.8` | Content/MetaHumans/{Ada 686 MB, Taro 513 MB, Common 1.0 GB} |
| MetaHumans sample (5.7, ignore) | `~/Documents/Unreal Projects/MetaHumans` | same, older engine |
| Game Animation Sample | `~/Documents/Unreal Projects/GameAnimationSample` | Content/Characters/UEFN_Mannequin/Animations (5.4 GB Content), MetaHumans/Kellan, MetaHumans/Common/Common/RTG_metahuman_base_skel_AnimBP |

Taro: BP_Taro, Body/m_med_nrw_body (skeleton `metahuman_base_skel` in
Common/Male/Medium/NormalWeight/Body), Face/Taro_FaceMesh on
Common/Face/Face_Archetype_Skeleton (RigLogic), five grooms. Common also
ships `Animation/Retargeting/ABP_MetaHuman_m_med_nrw_Retargeting`, which
copies the pose at runtime from a mannequin mesh component. That is the
bridge: the player keeps an invisible SK_Mannequin running the game's AnimBP,
and the MetaHuman body, face, grooms and clothing follow it.

Plugins the samples enable that Otherworld lacked: RigLogic, HairStrands,
AlembicHairImporter, MetaHumanRuntime. Added to Otherworld.uproject on
2026-10-07 (uncommitted). LiveLink/ARKit are not needed.

Because both projects mount assets at the same /Game/MetaHumans/... paths, a
file copy of Taro + Common is equivalent to the editor's Migrate. The repo is
code-only, so the copy must be an asset_sources.py entry (FAB-like: acquired
by hand through the Epic launcher, copied by a script).

## Task 1 - MetaHuman Taro as the player body (no animation changes)

Status 2026-10-07: DONE and worn (`PLAYER_RIG = "metahuman"`). What was built,
and where it departs from the steps below, is in
Scripts/asset_pipeline/CLAUDE.md ("The MetaHuman"). Departures: the sample's
retargeting ABP is MetaHuman-to-MetaHuman, so the bridge is our own IK
retargeter (build_metahuman_retarget.py); LiveLink had to be enabled too
(Face_AnimBP); there is no "Optimized" LOD settings asset in the 5.8 sample,
so step 5 is not done (the Cinematic LOD settings and strand grooms are what
the sample ships, and the LODSync is BP_Taro's). Not done either: hit zones
and ragdoll stay the mannequin's (the MetaHuman follows it within 7 cm, so a
shot that hits the mannequin hits where the MetaHuman is drawn). Left for
later: the weapon rides the hidden mannequin's hand socket, which is where the
MetaHuman's hand is only to within those centimetres; the shadow is the
MetaHuman's, headless down the sights as the mannequin's was.

1. Plugins (done, needs editor restart; editor pid may be open on the project).
2. Copy script `Scripts/asset_pipeline/import_metahuman.py` (host side):
   copy `Content/MetaHumans/Taro` and the parts of `Common` Taro depends on
   into Otherworld/Content/MetaHumans; register in asset_sources.py FAB
   section with dest `Content/MetaHumans`. Prune Common/Female, FemaleHair
   and Ada-only clothing if the dependency closure allows (~1.2 GB otherwise).
   Dependency closure: run an editor script against the sample with
   `Scripts/dev/uepy.py --cold --project "<sample>.uproject" script.py`; NOTE
   `print` is not captured in cold runs, write results to a file.
   `unreal.get_engine_subsystem(unreal.SubobjectDataSubsystem)` reads BP_Taro's
   components.
3. Player skin: third PlayerSkin in `Scripts/combat/skin.py` behind
   `PLAYER_RIG = "metahuman"` (asset_pipeline/player_body.py). The builder
   spawns the BP_Taro component set (body, face, grooms, clothing) as children
   of the existing mannequin mesh component, hides the mannequin, sets the
   body's anim class to the m_med_nrw retargeting ABP with the mannequin
   component as its source. Weapon sockets: same hand bone names, no change.
4. Hit zones and ragdoll from the MetaHuman body physics asset; first-person
   head hide becomes hiding the face mesh and grooms. Verifiers to make
   metahuman-aware: combat/verify/body_setting.py, hit_reactions.py,
   shotgun_pose.py (same treatment the bound body got).
5. Performance: switch LOD settings to the Optimized variants, grooms to cards.
6. Validate: `Scripts/asset_pipeline/bound_look.py` photographs,
   `Scripts/probes/probe_bound_body.py`, combat verifier suite.

Licensing: MetaHuman assets may only be used inside Unreal Engine projects.

## Task 2 - GAS motion matching as the player's base AnimBP

GAS 5.8 is motion matching (PoseSearch, Chooser, AnimationWarping,
MotionWarping, AnimationLocomotionLibrary plugins) inside a shipped AnimBP,
not a state machine. Our ABP_Unarmed is authored by Scripts/combat/
anim_blueprint.py. Plan: the player's base AnimBP becomes GAS's CMC variant
(CHT_CMCCharacterAnimations, CHT_PoseSearchDatabases); weapon and hold poses
become linked anim layers on top. Covers idle+breaks, turn in place,
walk/jog/run/sprint all directions with starts/stops/pivots (fixes strafe),
full crouch set, jump start/off/apex/land, slide, mantle/vault/hurdle/climb,
ragdoll poses + get-ups, stand and crouch aim offsets.

## Task 3 - replace the clips GAS lacks (no hand-rolled animations)

| Game need | Today | GAS? | Source |
|---|---|---|---|
| Unarmed punch | MM_Attack_01 | no | Lyra sample (Fab, free, mannequin) or Mixamo |
| Axe / knife / stick swings | built from poses (combat/hold_pose.py, knife_anim.py) | no | Mixamo melee or a Fab melee pack |
| Rifle / pistol / shotgun holds + ADS | MF_*_Idle_ADS + hand-built shotgun_pose.py | aim offsets only | Lyra rifle + pistol sets |
| Hit reactions x6 | MM_HitReact set (combat/hit_reaction.py) | shove-receive montages | keep Lyra hit reacts or GAS shoves |
| Throw | Quaternius UAL2 OverhandThrow | no | keep Quaternius |
| Prone crawl | Quaternius UAL1 Swim_Fwd_Loop | no | Mixamo crawl |
| Search kneel | Quaternius UAL1 Fixing_Kneeling | no (bench sit only) | keep Quaternius |
| Death | ragdoll (combat/death.py) | ragdoll poses | covered |

Order: 1 (body, no animation work is thrown away) -> 2 -> 3.
