"""Where Lyra's content lies and which of its clips the game plays.  Pure
names, importable outside the editor.

The user adds the Lyra Starter Game's ``Content/Characters`` under
``Content/Sourced/Lyra`` (a Fab pack: fab_library.json has the entry, nothing
of it is committed).  The files are byte copies that still name each other by
Lyra's own /Game paths, so, as with the Game Animation Sample (gas_paths.py),
one [CoreRedirects] line in Config/DefaultEngine.ini per row of REDIRECTED
points those names here.  **Name a Lyra asset by its /Game/Sourced/Lyra
path** (``lyra()``).

A clip belongs to one skeleton, and Lyra's are on its own SK_Mannequin, so
import_lyra.py retargets each row of CLIPS onto the player's
(SK_UEFN_Mannequin) into UEFN_DIR, where combat/skin.SKIN_GAS looks.
"""

from asset_pipeline.gas_bridge_paths import PLAYER_FAMILY

GAME_ROOT = "/Game/Sourced/Lyra"
CONTENT_DIR = "Content/Sourced/Lyra"

# Lyra's folders the copy has something in.  Never a folder this project has
# content of its own in: /Game/Characters/Mannequins is the game's.
REDIRECTED = (
    "/Game/Characters/Heroes/",
)


def lyra(lyra_path):
    """This project's path for one of Lyra's /Game paths."""
    assert lyra_path.startswith("/Game/"), lyra_path
    return GAME_ROOT + lyra_path[len("/Game"):]


def redirect_lines():
    """REDIRECTED as [CoreRedirects] lines: a folder matches as a prefix."""
    return ['+PackageRedirects=(OldName="%s...",NewName="%s",MatchWildcard=true)'
            % (old, lyra(old)) for old in REDIRECTED]


MANNEQUIN = lyra("/Game/Characters/Heroes/Mannequin")
SKELETON = f"{MANNEQUIN}/Meshes/SK_Mannequin"
# The mesh the clips are read off: a clip is retargeted as shown on a mesh,
# and a mesh's reference pose is not its skeleton's.
SOURCE_MESH = f"{MANNEQUIN}/Meshes/SKM_Manny"
ACTIONS = f"{MANNEQUIN}/Animations/Actions"
LOCOMOTION = f"{MANNEQUIN}/Animations/Locomotion"

# Written by import_lyra.py, beside the pack and as little committed as it.
RIG_DIR = f"{GAME_ROOT}/Rig"
IK_LYRA = f"{RIG_DIR}/IK_Lyra_Mannequin_Source"
RTG_UEFN_FROM_LYRA = f"{RIG_DIR}/RTG_UEFN_from_Lyra"
UEFN_DIR = f"{GAME_ROOT}/{PLAYER_FAMILY}"
UEFN_PREFIX = f"A_{PLAYER_FAMILY}_"

# The empty-handed punch.  Lyra has no clip by that name: its melee is one
# clip per weapon, and the pistol's is the one a bare fist reads as (a
# straight right, the other hand off the gun).
PUNCH = f"{ACTIONS}/MM_Pistol_Melee"

# A gun's ready pose (C3): what it is held in for an aim, down the sights, a
# shot, a reload and the guard.  Lyra's own ADS idles, one per kind of gun: a
# breathing loop with the gun at the shoulder and the eye behind its sights.
# The rifle's is the sniper's and the shotgun's too, the pistol's the SMG's (a
# machine pistol).  Lyra has an MM_Shotgun_Idle_ADS, and it is the rifle's
# with the left hand 2 cm further back: further from our shotgun's pump, so
# it is not taken (combat/shotgun_hold.py seats the hand).
AIM_RIFLE = f"{LOCOMOTION}/Rifle/MM_Rifle_Idle_ADS"
AIM_PISTOL = f"{LOCOMOTION}/Pistol/MM_Pistol_Idle_ADS"

# Every Lyra clip the game plays.  A later one is a row here and a re-run.
CLIPS = (PUNCH, AIM_RIFLE, AIM_PISTOL)


def uefn_clip(source):
    """Where a Lyra clip's copy on the UEFN skeleton lands."""
    return f"{UEFN_DIR}/{UEFN_PREFIX}{source.rsplit('/', 1)[1]}"
