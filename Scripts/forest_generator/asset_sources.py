"""
asset_sources.py -- where every non-code byte in Content/ comes from.

Imports no ``unreal``: the host-side sync tool, the offline checks and anything
running inside the editor all read the same table, so the thing that is
restored is the thing that is described.

── Why this file exists ────────────────────────────────────────────────────────

The repository is code only.  Nothing under ``Content/`` is committed except
``Content/Python`` (which is Python), so a fresh clone has a .uproject, a pile
of scripts and an empty Content tree.  This table is what turns that back into
a project: for every directory the clone is missing, it names the one thing
that produces it -- an engine install, a builder script, or a download.

Three kinds, and the distinction is the whole point:

  STOCK       bytes that ship with Unreal.  Restored by copying from the engine
              install.  Verified by checksum, because they are supposed to be
              identical and a mismatch means the engine version moved.

  GENERATED   bytes a script in Scripts/ writes.  Restored by running that
              script.  NOT verified by checksum -- a Blueprint recompile is not
              byte-deterministic, so two correct builds of the same graph
              differ in the tens to low thousands of bytes.  The verifiers are
              the check that matters.

  CACHE       bytes fetched off the internet.  Restored by re-running the
              fetcher.  Lives in assets/, which is git-ignored.

── The one subtlety: stock assets that a builder then patches ─────────────────

Three stock files are edited in place by builders.  They are STOCK for the
purposes of *getting* them and GENERATED for the purposes of *verifying* them:
copy the engine's copy, then run the builder, then trust the verifier rather
than a hash.  ``PATCHED_STOCK`` lists them so that a checksum mismatch on one
of those three is reported as expected rather than as engine drift.

Proved end to end on 2026-09-27: the four stock directories were deleted,
re-copied from UE 5.8.3 and rebuilt, and the suite came back 356/356 weapons,
60/60 HUD and 148/148 level -- 564 checks, zero failures.
"""

from dataclasses import dataclass, field

# ── Engine layout ────────────────────────────────────────────────────────────
#
# Template assets live in a shared pool beside the templates that use them, not
# inside any one template, which is why the paths below are not all under
# TP_ThirdPersonBP.  ENGINE_ROOT is the UE_x.y directory -- the parent of the
# Engine/ directory that uepy.py resolves.
ENGINE_VERSION = "5.8"
ENGINE_ROOT_GLOB = "/Users/Shared/Epic Games/UE_*"
TEMPLATE_RESOURCES = "Templates/TemplateResources/High"
THIRD_PERSON_TEMPLATE = "Templates/TP_ThirdPersonBP"


@dataclass(frozen=True)
class AssetSource:
    """One directory under Content/, and the single thing that produces it."""
    dest: str                       # project-relative, e.g. "Content/Characters"
    kind: str                       # "stock" | "generated" | "cache"
    engine_subpath: str = ""        # stock: source dir relative to ENGINE_ROOT
    builders: tuple = ()            # generated: scripts, in the order they run
    note: str = ""

    @property
    def is_stock(self) -> bool:
        return self.kind == "stock"


# ── Stock: copied from the engine install, byte for byte ─────────────────────
#
# Verified 2026-09-27 against UE 5.8.3: 171 files, of which 168 are identical to
# the engine's own copies and 3 are the patched ones below. Copying these four
# directories in produces exactly the project's file set -- no extras, nothing
# missing -- so the engine directory *is* the file list and this table does not
# need to carry one.
STOCK = (
    AssetSource(
        dest="Content/Characters/Mannequins",
        kind="stock",
        engine_subpath=f"{TEMPLATE_RESOURCES}/Characters/Content/Mannequins",
        note="Manny and Quinn: meshes, rigs, textures, and the full animation set "
             "(Unarmed, Pistol, Rifle, Death, HitReact). 126 MB, 128 assets.",
    ),
    AssetSource(
        dest="Content/Input",
        kind="stock",
        engine_subpath=f"{TEMPLATE_RESOURCES}/Input/Content",
        note="Enhanced Input actions and mapping contexts, untouched.",
    ),
    AssetSource(
        dest="Content/LevelPrototyping",
        kind="stock",
        engine_subpath=f"{TEMPLATE_RESOURCES}/LevelPrototyping/Content",
        note="Grid materials and blockout meshes, untouched.",
    ),
    AssetSource(
        dest="Content/ThirdPerson",
        kind="stock",
        engine_subpath=f"{THIRD_PERSON_TEMPLATE}/Content/ThirdPerson",
        note="Template character, game mode and Lvl_ThirdPerson. The map is "
             "byte-identical to the engine's; the two Blueprints are patched.",
    ),
)

# Stock files that a builder rewrites in place. Restoring them is still a copy
# from the engine -- the builder supplies the difference afterwards.
PATCHED_STOCK = {
    "Content/Characters/Mannequins/Anims/Unarmed/ABP_Unarmed.uasset":
        ("build_weapons_and_combat.py",
         "patch_anim_blueprint() inserts the LayeredBoneBlend that keeps "
         "DefaultSlot on the upper body; stock 385911 B, patched ~423800 B"),
    "Content/ThirdPerson/Blueprints/BP_ThirdPersonCharacter.uasset":
        ("build_weapons_and_combat.py",
         "capsule blocks Visibility, camera boom, HealthComponent and "
         "WeaponComponent installed"),
    "Content/ThirdPerson/Blueprints/BP_ThirdPersonGameMode.uasset":
        ("build_weapons_and_combat.py, build_graphics_menu.py",
         "NpcSpawnCount / NpcKillCount / PlayerDead / DebugMode, and HUDClass"),
}

# ── Generated: a script in Scripts/ writes every byte ────────────────────────
#
# Order matters. build_weapons_and_combat.py patches the stock character and
# game mode, so it runs before build_graphics_menu.py points HUDClass at the
# menu it builds. The level generator runs last because it spawns the NPCs the
# NPC builder defines.
GENERATED = (
    AssetSource(
        dest="Content/Weapons",
        kind="generated",
        builders=("Scripts/build_weapons_and_combat.py",),
        note="Five weapons, ammunition, inventory, health, blood, drops. The "
             "Audio/ subfolder is imported by make_weapon_sounds.py from the "
             "sound cache -- see CACHE below.",
    ),
    AssetSource(
        dest="Content/UI",
        kind="generated",
        builders=("Scripts/build_graphics_menu.py",),
        note="BP_GraphicsMenuHUD: the settings menu, HP and stamina bars.",
    ),
    AssetSource(
        dest="Content/Forest/NPC",
        kind="generated",
        builders=("Scripts/build_npc_blueprints.py",),
        note="BP_ForestWanderer and its AI controller.",
    ),
    AssetSource(
        dest="Content/Forest",
        kind="generated",
        builders=("Scripts/generate_forest_level.py",),
        note="Materials, foliage, scanned-asset imports, terrain. ~920 MB, and "
             "the reason the repository is code only.",
    ),
    AssetSource(
        dest="Content/Maps",
        kind="generated",
        builders=("Scripts/generate_forest_level.py",),
        note="Lvl_Forest_200m.umap and its World Partition sidecars.",
    ),
)

# ── Cache: fetched off the internet into assets/, which is git-ignored ───────
ASSETS_DIR = "assets"
CACHE = (
    AssetSource(
        dest="assets/cache/sounds",
        kind="cache",
        builders=("Scripts/fetch_weapon_sounds.py",),
        note="~300 MB of CC0 firearm recordings from opengameart.org, including "
             "a 185 MB .7z. fetch_weapon_sounds.py both downloads them and cuts "
             "the nine A_* wavs into assets/generated/sounds, which "
             "build_weapons_and_combat.py imports. Never committed: GitHub "
             "rejects files over 100 MB, and the fetcher reproduces them "
             "exactly. make_weapon_sounds.py synthesised the earlier set and "
             "is history -- running it AFTER the fetcher overwrites real "
             "recordings with synthesised ones.",
    ),
)

ALL_SOURCES = STOCK + GENERATED + CACHE

# Where the stock checksums live, relative to the project root. Written by
# Scripts/sync_assets.py --record; compared by --verify. Text, a few tens of KB,
# and tracked: it is how an engine upgrade announces itself instead of being
# absorbed silently.
STOCK_CHECKSUM_FILE = "Scripts/forest_generator/stock_checksums.json"

# The order a fresh clone runs things in.
RESTORE_ORDER = (
    "Scripts/sync_assets.py --restore-stock",
    "Scripts/fetch_weapon_sounds.py",
    "Scripts/dev/uepy.py --cold Scripts/build_weapons_and_combat.py",
    "Scripts/dev/uepy.py --cold Scripts/build_graphics_menu.py",
    "Scripts/dev/uepy.py --cold Scripts/build_npc_blueprints.py",
    "Scripts/generate_forest_level.py",
)


def stock_sources() -> tuple:
    return STOCK


def source_for(dest: str):
    """The table entry covering a project-relative path, longest match first."""
    best = None
    for src in ALL_SOURCES:
        if dest == src.dest or dest.startswith(src.dest.rstrip("/") + "/"):
            if best is None or len(src.dest) > len(best.dest):
                best = src
    return best
