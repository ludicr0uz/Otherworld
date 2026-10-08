"""gas_paths.py -- where the Game Animation Sample's content lies in this
project, and what of the sample comes across.  Constants only; no ``unreal``,
so the host-side import_gas.py and the editor-side scripts both read it.

The sample's /Game/<Folder>/... is this project's /Game/GAS/<Folder>/...:
``gas(path)`` turns one into the other, and REDIRECTED is the same rule as the
engine reads it (Config/DefaultEngine.ini, [CoreRedirects]), which is how the
copied packages, saved by the sample, still find each other.
"""

# The folder the copy lands in, and its mount path.
DEST = "Content/GAS"
GAME_ROOT = "/Game/GAS"

# What import_gas.py --manifest starts the closure from: these packages, and
# every asset under these folders (the UEFN mannequin: meshes, rigs, and every
# clip with the PoseSearch databases and their choosers).
# The anim blueprint reaches none of the sample's AC_ components (the
# character blueprint adds them).  Two are roots because the later wiring
# needs them: AC_PostABPTick stands alone, and AC_TraversalLogic brings the
# traversal choosers and LevelBlock_Traversable, the block it looks for.  The
# other two stay behind: AC_PreCMCTick casts to SandboxCharacter_CMC and
# AC_VisualOverrideManager to GM_Sandbox, and those bring the sample's
# character, cameras, game mode and /Game/Input.
ROOT_PACKAGES = (
    "/Game/Blueprints/SandboxCharacter_CMC_ABP",
    "/Game/Blueprints/AC_PostABPTick",
    "/Game/Blueprints/AC_TraversalLogic",
)
ROOT_FOLDERS = (
    "/Game/Characters/UEFN_Mannequin/Meshes",
    "/Game/Characters/UEFN_Mannequin/Rigs",
    "/Game/Characters/UEFN_Mannequin/Animations",
)

# What stays in the sample.  A name ending in "/" is a folder; one that does
# not is a package-name prefix (the Mover variant's three blueprints, and the
# Mover's three choosers under the mannequin: two have the Mover's anim
# blueprint as their context and cannot load without that class, and the
# third, CHT_PoseSearchDatabases_Mover, nests one of them).
EXCLUDED = (
    "/Game/Blueprints/SandboxCharacter_Mover",
    "/Game/Characters/UEFN_Mannequin/Animations/ExperimentalStateMachineData/"
    "CHT_MoverCharacterAnimations_PoseMatch",
    "/Game/Characters/UEFN_Mannequin/Animations/MotionMatchingData/"
    "CHT_PoseSearchDatabases_Relaxed",
    "/Game/Characters/UEFN_Mannequin/Animations/MotionMatchingData/"
    "CHT_PoseSearchDatabases_Mover",
    "/Game/Blueprints/MovementModes/",
    "/Game/Blueprints/SmartObjects/",
    "/Game/Blueprints/RetargetedCharacters/",
    "/Game/IsolatedExamples/",
    "/Game/Characters/Echo/",
    "/Game/Characters/Paragon/",
    "/Game/Characters/UE4_Mannequin/",
    "/Game/Characters/UE5_Mannequins/",
    "/Game/MetaHumans/",
)

# The sample's folders (a name ending in "/") and single packages the manifest
# has something in.  Each is one redirect; import_gas.py refuses a manifest
# package no row covers.  Never a folder this project has content of its own
# in: /Game/Audio is the game's, so the sample's audio is named piece by piece.
REDIRECTED = (
    "/Game/Characters/UEFN_Mannequin/",
    "/Game/Blueprints/",
    "/Game/Audio/Foley/",
    "/Game/Audio/Mix/",
    "/Game/Audio/DefaultAttenuation",
    "/Game/Misc/",
    "/Game/Levels/LevelPrototyping/",
)

# Copied, then changed in this project by patch_gas_notifies.py: the notifies
# only the Mover character answers.
PATCHED_NOTIFIES = (
    "/Game/Blueprints/AnimNotifies/BP_AnimNotify_TriggerRagdoll",
    "/Game/Blueprints/AnimNotifies/BP_NotifyState_OverrideMovementMode",
)
# Every package changed here after the copy.  import_gas.py copies one only
# while it is not here, so a re-run does not put the sample's back over the
# patch.  The anim blueprint is the weapons build's to patch
# (combat/gas_locomotion.py: what it reads of its character, its montage slot,
# the server branch); it is patched where it lies because the sample's
# choosers take an object of its class and no other.
PATCHED = PATCHED_NOTIFIES + (
    "/Game/Blueprints/SandboxCharacter_CMC_ABP",
)

ABP = GAME_ROOT + "/Blueprints/SandboxCharacter_CMC_ABP"
UEFN = GAME_ROOT + "/Characters/UEFN_Mannequin"
DATABASES = UEFN + "/Animations/MotionMatchingData/Databases"


def gas(sample_path):
    """This project's path for one of the sample's /Game paths."""
    assert sample_path.startswith("/Game/"), sample_path
    return GAME_ROOT + sample_path[len("/Game"):]


def redirected(pkg):
    """Whether a row of REDIRECTED covers this sample package."""
    return any(pkg.startswith(old) if old.endswith("/") else pkg == old
               for old in REDIRECTED)


def redirect_lines():
    """REDIRECTED as [CoreRedirects] lines: a folder matches as a prefix."""
    return ['+PackageRedirects=(OldName="%s",NewName="%s"%s)' % (
                old + "..." if old.endswith("/") else old, gas(old),
                ",MatchWildcard=true" if old.endswith("/") else "")
            for old in REDIRECTED]
