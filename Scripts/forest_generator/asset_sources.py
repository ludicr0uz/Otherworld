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

  FAB         bytes the user acquired from Fab (Megascans, packs, characters,
              animations).  Restored BY HAND: Fab needs the user's Epic
              sign-in, so no script can fetch them.  The tracked
              asset_pipeline/fab_library.json lists what to re-add and where
              it lands; ``fab_library.py --check`` names what is missing.

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
    kind: str                       # "stock" | "generated" | "cache" | "fab"
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
        note="Five weapons, ammunition, inventory, health, blood, drops, and "
             "BP_Settings -- the SaveGame the menu's keybinds and mouse "
             "sensitivity live in, built here so both it and the HUD can name "
             "the class. The Audio/ subfolder is imported by this builder "
             "from the sound cache -- see CACHE below. The rifle and the "
             "sniper wear the FPS Weapon Bundle's models (a Fab pack under "
             "/Game/FPS_Weapon_Bundle), so that pack must be in first. "
             "The three A_Att_* USoundAttenuation profiles every sound in the "
             "game points at are built by the same script but live in "
             "/Game/Audio, because the foley half of the sounds does.",
    ),
    AssetSource(
        dest="Content/UI/Art",
        kind="generated",
        builders=("Scripts/build_ui_art.py",
                  "Scripts/build_survival_icons.py",
                  "Scripts/asset_pipeline/import_ui_art.py"),
        note="The HUD's artwork: panels, inventory slots, bars, the sniper's "
             "scope overlay and one "
             "silhouette per weapon, plus the mushroom's and the canteen's "
             "(build_survival_icons.py). Drawn by Pillow rather than authored, so "
             "the look of the UI is a readable script and not a folder of "
             "PNGs nobody can regenerate. Two steps because the editor's "
             "embedded Python has no Pillow: build_ui_art.py writes assets/ui/ "
             "from outside, import_ui_art.py brings it in with the settings "
             "that keep it crisp (UI texture group, uncompressed, no mips).",
    ),
    AssetSource(
        dest="Content/Survival",
        kind="generated",
        builders=("Scripts/build_survival.py",),
        note="Hunger, thirst and temperature (BP_SurvivalComponent), the "
             "mushroom and the water canteen (children of BP_WeaponItem, so "
             "they live in the inventory), the two debuff GameplayEffects and "
             "GA_ConsumeItem. Also installs an AbilitySystemComponent on the "
             "player and the wanderer. Needs Content/Weapons first; the forage "
             "in the levels is placed by Scripts/place_forage.py.",
    ),
    AssetSource(
        dest="Content/UI",
        kind="generated",
        builders=("Scripts/build_graphics_menu.py",),
        note="BP_GraphicsMenuHUD and the UMG screens it drives: WBP_HUD (HP, "
             "stamina and hunger/thirst/temperature bars, the inventory grid), "
             "WBP_MainMenu (title and settings pages), WBP_PauseMenu (the M "
             "panel), WBP_DeathMenu, and their parts WBP_MenuRow and "
             "WBP_InventorySlot, all built on the artwork above. Needs Content/"
             "Survival first: the survival bars cast to its component.",
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
             "the reason the repository is code only. Procedural/ -- the "
             "grass patches, bushes and M_ProcFoliage -- is built from "
             "forest_generator/foliage_meshes.py by "
             "forest_import/foliage_assets.py, which the level import runs.",
    ),
    AssetSource(
        dest="Content/Sourced/Characters",
        kind="generated",
        builders=("Scripts/asset_pipeline/import_characters.py",
                  "Scripts/asset_pipeline/build_creature_materials.py",
                  "Scripts/asset_pipeline/build_retarget.py"),
        note="AI-generated characters (zombie, wendigo, and the player's "
             "adventurer) imported from the Meshy cache below, plus the rigs "
             "that animate them. The adventurer is generated by the same four "
             "stages as the monsters and differs only in what wears it: "
             "build_weapons_and_combat.py puts it on BP_ThirdPersonCharacter "
             "(see PlayerSkin there), and npc_placement.NPC_VARIANTS does not "
             "list it, so it never spawns as an enemy. Each character gets "
             "its OWN skeleton, IK rig, retargeter and animation set under "
             "Anims/<Creature>/. Sharing one skeleton looked right -- two "
             "independently generated creatures came back on byte-identical "
             "24-bone hierarchies -- but identical hierarchies are not "
             "identical BIND POSES, and an animation is per-bone local "
             "rotations interpreted against the bind pose. Shared, the clips "
             "put the 2.4 m wendigo's forward neck pitch on the 1.8 m zombie "
             "and its head hung off the front of its chest. Nothing is "
             "hand-authored per creature: the chain tables are keyed by bone "
             "name and those really are shared. Each monster imports into a "
             "folder of its own: Meshy names every export's material "
             "Material_1, so a shared folder makes the second monster bind to "
             "the first one's skin. The rigged FBX carries only a base colour, "
             "so build_creature_materials.py imports the normal and packed "
             "occlusion/roughness/metallic maps from the cache and wires them "
             "into M_MeshyCreature -- without it the creatures shade like "
             "plastic. build_retarget.py retargets the anim BLUEPRINT, not a "
             "list of clips, which is what gives the creatures a state machine "
             "a Character can actually be pointed at. Run the three builders "
             "in that order.",
    ),
    AssetSource(
        dest="Content/Maps",
        kind="generated",
        builders=("Scripts/generate_forest_level.py",),
        note="Lvl_Forest_200m.umap (--size 200) and Lvl_Forest_1000m.umap "
             "(--size 1000), each with its World Partition sidecars. The "
             "forage (place_forage.py) and the day/night cycle actor "
             "(build_day_night.py) are added to them afterwards.",
    ),
    AssetSource(
        dest="Content/World",
        kind="generated",
        builders=("Scripts/build_day_night.py",),
        note="The day/night cycle: BP_DayNightCycle (sun, moon, sky light, "
             "sky dome, fog and exposure, driven by a clock) and "
             "Materials/M_DayNightSky. The same script places one cycle in "
             "each generated level. Settings: Scripts/world/world_config.py.",
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
             "exactly. Scripts/make_creature_sounds.py synthesises the other "
             "sounds -- footsteps, melee impacts and the "
             "monster voices, which have no recording to be overwritten by, "
             "and writes only A_Footstep_*, A_MeleeHit_*, A_ZombieGrowl_* and "
             "A_WendigoRoar_*, never a file the fetcher writes.",
    ),
)

CACHE = CACHE + (
    AssetSource(
        dest="assets/cache/meshy",
        kind="cache",
        builders=("Scripts/asset_pipeline/fetch_monsters.py",),
        note="Meshy.ai output: ~250 MB per monster across preview, refine, "
             "remesh and rig stages. Costs 40 credits per creature and real "
             "money beyond the free tier, so the fetcher is resumable -- each "
             "completed stage is recorded in <id>/task.json and skipped on a "
             "re-run. Requires MESHY_API_KEY in assets/.env, which is "
             "git-ignored and must never be referenced from a tracked file. "
             "Scripts/asset_pipeline/catalog.py holds the prompts.",
    ),
)

# ── Fab: acquired by the user, never by a script ─────────────────────────────
#
# Only the plugin's default folder is listed here. A pack added through the
# launcher lands in its own /Game/<Pack>, and fab_library.json records each of
# those; sync_assets.py --status reports them one by one.
FAB = (
    AssetSource(
        dest="Content/Fab",
        kind="fab",
        builders=("(manual) the Fab plugin in the editor -- see "
                  "Scripts/asset_pipeline/fab_library.py --check",),
        note="Whatever the Fab plugin imported (Megascans under Megascans/, "
             "plus /Fab/Materials parents from the plugin itself). Indexed by "
             "Scripts/asset_pipeline/fab_index.py into assets/cache/fab/.",
    ),
)

ALL_SOURCES = STOCK + GENERATED + CACHE + FAB

# Where the stock checksums live, relative to the project root. Written by
# Scripts/sync_assets.py --record; compared by --verify. Text, a few tens of KB,
# and tracked: it is how an engine upgrade announces itself instead of being
# absorbed silently.
STOCK_CHECKSUM_FILE = "Scripts/forest_generator/stock_checksums.json"

# The order a fresh clone runs things in.
RESTORE_ORDER = (
    "Scripts/sync_assets.py --restore-stock",
    "Scripts/fetch_weapon_sounds.py",
    # The foley and the monster voices. A separate script from the fetcher
    # because it is synthesised rather than cut from recordings -- see its
    # docstring for why that split is the right one and not laziness. Both
    # write into assets/generated/sounds and build_weapons_and_combat.py
    # imports the lot.
    "python3 Scripts/make_creature_sounds.py",
    # The HUD's artwork comes before the weapons, because each weapon stores a
    # reference to its own inventory icon, and before the menu, which draws the
    # panels, slots and bars. Two steps, not one: the generator needs Pillow and
    # the editor's embedded Python does not have it, so it runs outside.
    "python3 Scripts/build_ui_art.py",
    "python3 Scripts/build_survival_icons.py",
    "Scripts/dev/uepy.py --cold Scripts/asset_pipeline/import_ui_art.py",
    # Fab content is re-added by hand (it needs the user's Epic sign-in):
    # --check lists what fab_library.json holds that the disk does not. Then
    # the index, which sessions read instead of booting the editor. Before the
    # weapons, whose rifle and sniper are the FPS Weapon Bundle's models.
    "Scripts/asset_pipeline/fab_library.py --check",
    "Scripts/dev/uepy.py --cold Scripts/asset_pipeline/fab_index.py",
    "Scripts/dev/uepy.py --cold Scripts/build_weapons_and_combat.py",
    # After combat (the consumables are children of BP_WeaponItem) and before
    # the HUD (whose survival bars cast to BP_SurvivalComponent).
    "Scripts/dev/uepy.py --cold Scripts/build_survival.py",
    "Scripts/dev/uepy.py --cold Scripts/build_graphics_menu.py",
    # The monsters come before the NPC blueprints, because the wanderers ARE
    # the monsters: BP_Wanderer_Zombie and BP_Wanderer_Wendigo need
    # SKM_Zombie01/SKM_Wendigo01 and the retargeted A_Meshy_ABP_Unarmed to
    # exist before they can point at them.
    #
    # A clone without a Meshy key can still stop before this block and run the
    # rest: build_npc_blueprints falls back to the mannequin and says so in the
    # log. That is a playable game with wrong-looking enemies, which is the
    # right failure for a missing optional credential -- but it is a FALLBACK,
    # not the intended build, so the order here is the full one.
    "Scripts/asset_pipeline/fetch_monsters.py",
    "Scripts/dev/uepy.py --cold Scripts/asset_pipeline/import_characters.py",
    "Scripts/dev/uepy.py --cold Scripts/asset_pipeline/build_creature_materials.py",
    "Scripts/dev/uepy.py --cold Scripts/asset_pipeline/build_retarget.py",
    "Scripts/dev/uepy.py --cold Scripts/build_npc_blueprints.py",
    "Scripts/generate_forest_level.py",
    # Once each printed import_<Level>.py has run: the import rebuilds the
    # level from nothing, forage included.
    "Scripts/dev/uepy.py --cold Scripts/place_forage.py",
    # Also after the imports: it tags each level's static sky and adds the
    # day/night cycle that replaces it at BeginPlay.
    "Scripts/dev/uepy.py --cold Scripts/build_day_night.py",
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
