"""player_body -- which generated body the player is.  THE one setting.

Constants only (no ``unreal``).  To put the player in another body, change
PLAYER_BODY to that body's catalog id and run the swap (below); nothing else
names the player's body.  What reads it:

    combat/skin.py                 SKIN_ADVENTURER: mesh, anim BP, clips
    quaternius_paths.py            UAL_CHARACTERS: who gets the stance clips
    combat/verify/player_body.py   checks every one of those agrees

The body must be a catalog spec that is already imported and rigged.  One that
names ``compatible_with`` is normalised to that body on the way in
(physics_template.py, clavicle_align.py, two_hands.py), which is what lets it
stand in with no numbers of its own.

── The swap ────────────────────────────────────────────────────────────────

    python3 Scripts/asset_pipeline/swap_player_body.py adventurer_03

writes the setting, imports the body if it never was, retargets the stance
clips onto it, rebuilds and runs the verifiers (--plan prints the commands
instead; --check runs the verifiers alone). By hand it is: edit PLAYER_BODY,
then those commands in that order, with the editor closed.
"""

import os

from asset_pipeline import catalog

# The catalog id (asset_pipeline/catalog.py) of the body the player wears.
PLAYER_BODY = "adventurer_03"

# How that body is rigged.  One line, like the one above:
#
#   "own"        its own Meshy skeleton, every clip retargeted onto it
#                (import_characters.py, build_retarget.py).  What is built and
#                verified today.
#   "mannequin"  bound to SK_Mannequin (bind_to_mannequin.py, import_bound.py):
#                the mannequin's anim blueprint and clips play on it as they
#                are.  Where the project is going; see mannequin_bind/.  Until
#                import_bound.py has put the body in Content/, combat/skin.py
#                says so and wears the "own" body.
PLAYER_RIG = "mannequin"

# The catalog id of the body the garments are drawn on (Scripts/clothing): the
# player with every clothing slot empty.
CLOTHING_BASE_BODY = "adventurer_03"


def name_of(spec_id):
    """A spec's short asset name: adventurer_01 -> Adventurer01 (its mesh is
    SKM_Adventurer01, its skeleton SK_Adventurer01, its clips A_Adventurer01_*)."""
    return os.path.basename(catalog.by_id(spec_id).dest).replace("SKM_", "")


def reference_of(name):
    """The short name of the body ``name`` must be able to replace, or None:
    its spec's compatible_with."""
    for spec in catalog.CHARACTERS:
        if name_of(spec.id) == name:
            return name_of(spec.compatible_with) if spec.compatible_with else None
    return None


PLAYER_NAME = name_of(PLAYER_BODY)
CLOTHING_BASE_NAME = name_of(CLOTHING_BASE_BODY)
