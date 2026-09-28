"""
build_npc_blueprints.py — Creates the forest NPC Blueprints from Python.

Run inside the editor:
    UnrealEditor-Cmd <uproject> -ExecutePythonScript="<abs>/Scripts/build_npc_blueprints.py" -NoUI -stdout

or import it from a generated level script and call ``ensure_npc_blueprints()``.

Two assets are produced under /Game/Forest/NPC:

  BP_ForestWandererAI  (parent AIController)  — the brain.  Event graph:

      [Event BeginPlay] --> [both ends on the navmesh?]
                                 ^     |            |
                                 |  yes|            |no
                                 |     v            v
                                 | [MoveToActor] [MoveToLocation,
                                 |  (pathfound)   no pathfinding]
                                 |     |            |
                                 |     '-----.------'
                                 |           v
                                 |   [in reach and off cooldown?]
                                 |           |            |
                                 |       yes |            | no
                                 |           v            |
                                 |  [arm next swing]      |
                                 |  [play MM_Attack_01]   |
                                 |  [player Health -= 12] |
                                 |           |            |
                                 '--- [Delay 0.5s] <------'

      [Get Player Pawn 0] --ReturnValue--> [MoveToActor.Goal]

      MoveToActor does the pathfinding, so the NPC runs *around* trees rather
      than into them.  Re-issuing it on a timer (instead of once) means the NPC
      keeps following a player who moves, and recovers on its own if the first
      request fires before the navmesh or the player pawn exist -- and that same
      loop is where the melee check lives, so there is one heartbeat rather than
      two that can disagree.

      The branch in front of it is the answer to a navigation DEAD ZONE: the
      navmesh covers a disc of radius 85 m inside a 200 m square of terrain, so
      a player who walks into the ring outside it cannot be pathed to at all.
      With bAllowPartialPath the request did not even fail -- it succeeded, at
      the island edge, and the pack stood there.  See NAV_REACHABLE_EXTENT_CM
      in npc_placement.py.

  BP_ForestWanderer    (parent Character)     — the body: mannequin mesh,
      running movement speed, and the controller above auto-possessing it.

The numbers (run speed, melee range/damage/interval, spawn band) all live in
forest_generator/npc_placement.py, which imports no `unreal`, so the host-side
generator and its offline checks read exactly what the editor builds.

These assets are level-independent — nothing here depends on map size, seed or
time of day — which is why they live in their own script instead of the
generated per-level one.
"""

import os
import sys

import unreal

# The tuning constants live in the pure-Python placement module so the host-side
# generator can read them without importing `unreal`.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from forest_generator.npc_placement import (
    NPC_RUN_SPEED_CMS,
    NPC_ACCEPTANCE_RADIUS_CM,
    NPC_REPATH_SECONDS,
    NPC_MELEE_RANGE_CM,
    NPC_MELEE_DAMAGE,
    NPC_MELEE_INTERVAL_S,
    NPC_MELEE_MONTAGE,
    NPC_MELEE_MONTAGE_FALLBACK,
    NPC_MELEE_BLEND_S,
    NAV_REACHABLE_EXTENT_CM,
    NPC_VARIANTS,
    NPC_BASE_MESH,
    NPC_BASE_MESH_FALLBACK,
    NPC_ANIM_BP,
    NPC_ANIM_BP_FALLBACK,
    NPC_BASE_HEALTH,
    NPC_RUN_SPEED_CMS as _NPC_RUN_SPEED_CMS,
    NPC_VOICE_MIN_S,
    NPC_VOICE_MAX_S,
)

# ─── Configuration ───────────────────────────────────────────────────────────

NPC_DIR = "/Game/Forest/NPC"
AI_BP_PATH = f"{NPC_DIR}/BP_ForestWandererAI"
NPC_BP_PATH = f"{NPC_DIR}/BP_ForestWanderer"

# ── Body and animation ───────────────────────────────────────────────────────
#
# The wanderers wear Meshy creatures, each on its OWN skeleton, animated by
# its own A_<Creature>_ABP_Unarmed -- ABP_Unarmed retargeted onto that
# skeleton, state machine and blend space included, by
# Scripts/asset_pipeline/build_retarget.py.
# An anim BP is bound to one skeleton, so the mannequin's cannot drive a
# creature; retargeting the BLUEPRINT rather than a folder of clips is what
# makes the monsters usable by a Character at all.
#
# Every one of these lives under /Game/Sourced, which is git-ignored and
# rebuilt from assets/cache/meshy.  A checkout that has not run the asset
# pipeline therefore has none of them, and the mannequin pair it falls back to
# is the combination that shipped before the creatures existed -- a wanderer
# that looks wrong is a far better failure than a build that stops, and the log
# says loudly which one happened.
def _resolve(preferred, fallback, what):
    """First of the two that exists on disk, as an OBJECT path."""
    eas = _asset_sub()
    for pkg in (preferred, fallback):
        if eas.does_asset_exist(pkg):
            if pkg is fallback:
                unreal.log_warning(
                    f"[NPC] {what}: {preferred} is missing -- falling back to "
                    f"{pkg}. Run Scripts/asset_pipeline to build the creatures.")
            return f"{pkg}.{pkg.rsplit('/', 1)[-1]}"
    raise RuntimeError(f"[NPC] neither {preferred} nor {fallback} exists ({what})")


def _mesh_object(pkg):
    return f"{pkg}.{pkg.rsplit('/', 1)[-1]}"

MESH_RELATIVE_Z_CM = -89.0
MESH_RELATIVE_YAW_DEG = 270.0

# Where the player's health lives.  Built by build_weapons_and_combat.py; if it
# is absent (a project where the weapons have never been built) the melee half
# of the chase loop is skipped and the NPC just runs at the player.
HEALTH_BP_PATH = "/Game/Weapons/BP_HealthComponent"
HEALTH_CLASS_PATH = f"{HEALTH_BP_PATH}.BP_HealthComponent_C"

# The slot the attack animation is played into.  build_weapons_and_combat.py
# splices a layered blend per bone (spine_01) into ABP_Unarmed, which makes
# DefaultSlot upper-body only -- so the NPC swings its arms while the legs keep
# running.  Without that patch the montage is full body and the swing also stops
# the legs; it still reads as an attack, so this is not a hard dependency.
MELEE_SLOT = "DefaultSlot"

# An object pin holds the full object path (package + object name), and it
# normalises whatever is written into that form -- so write it that way, or the
# read-back guard in _set() reports a mismatch that is not one.
#
# Resolved when the graph is authored rather than at import, because which of
# the two montages exists depends on whether the asset pipeline has run, and
# _resolve needs the editor's asset subsystem.
def _melee_montage_object():
    return _resolve(NPC_MELEE_MONTAGE, NPC_MELEE_MONTAGE_FALLBACK, "melee montage")

INF = 1.0e9

# Function paths for the graph nodes
FN_MOVE_TO_ACTOR = "/Script/AIModule.AIController.MoveToActor"
# The same move order with pathfinding switched off: path following still runs,
# it just follows a straight line to the point instead of a Recast path. This
# is what lets a wanderer chase a player who is standing on ground the navmesh
# does not cover.
FN_MOVE_TO_LOCATION = "/Script/AIModule.AIController.MoveToLocation"
FN_PROJECT_NAV = ("/Script/NavigationSystem.NavigationSystemV1"
                  ".K2_ProjectPointToNavigation")
FN_MAKE_VECTOR = "/Script/Engine.KismetMathLibrary.MakeVector"
FN_AND_B = "/Script/Engine.KismetMathLibrary.BooleanAND"
FN_GET_PLAYER_PAWN = "/Script/Engine.GameplayStatics.GetPlayerPawn"
FN_DELAY = "/Script/Engine.KismetSystemLibrary.Delay"
FN_GET_PAWN = "/Script/Engine.Controller.K2_GetPawn"
FN_IS_VALID = "/Script/Engine.KismetSystemLibrary.IsValid"
FN_ACTOR_LOC = "/Script/Engine.Actor.K2_GetActorLocation"
FN_DISTANCE = "/Script/Engine.KismetMathLibrary.Vector_Distance"
FN_LE_FF = "/Script/Engine.KismetMathLibrary.LessEqual_DoubleDouble"
FN_GE_FF = "/Script/Engine.KismetMathLibrary.GreaterEqual_DoubleDouble"
FN_AND = "/Script/Engine.KismetMathLibrary.BooleanAND"
FN_ADD_FF = "/Script/Engine.KismetMathLibrary.Add_DoubleDouble"
FN_SUB_FF = "/Script/Engine.KismetMathLibrary.Subtract_DoubleDouble"
FN_CLAMP = "/Script/Engine.KismetMathLibrary.FClamp"
FN_TIME_SECONDS = "/Script/Engine.GameplayStatics.GetTimeSeconds"
FN_GET_COMP = "/Script/Engine.Actor.GetComponentByClass"
FN_ANIM_INSTANCE = "/Script/Engine.SkeletalMeshComponent.GetAnimInstance"
FN_PLAY_SLOT = "/Script/Engine.AnimInstance.PlaySlotAnimationAsDynamicMontage"
FN_PLAY_SOUND = "/Script/Engine.GameplayStatics.PlaySoundAtLocation"
FN_ARR_LEN = "/Script/Engine.KismetArrayLibrary.Array_Length"
FN_ARR_GET = "/Script/Engine.KismetArrayLibrary.Array_Get"
FN_RAND_INT = "/Script/Engine.KismetMathLibrary.RandomIntegerInRange"
FN_RANDOM_FLOAT = "/Script/Engine.KismetMathLibrary.RandomFloatInRange"
FN_SUB_II = "/Script/Engine.KismetMathLibrary.Subtract_IntInt"
FN_GREATER_II = "/Script/Engine.KismetMathLibrary.Greater_IntInt"
FN_NOT = "/Script/Engine.KismetMathLibrary.Not_PreBool"
FN_SUB_VV = "/Script/Engine.KismetMathLibrary.Subtract_VectorVector"
FN_NORMAL = "/Script/Engine.KismetMathLibrary.Normal"

# Where the creature voices and the impact sounds are imported to, by
# build_weapons_and_combat.import_sounds().
VOICES_VAR = "Voices"
HIT_SOUNDS_VAR = "HitSounds"
STATS_APPLIED_VAR = "StatsApplied"
NEXT_VOICE_VAR = "NextVoiceTime"
HIT_SOUNDS = tuple(f"/Game/Audio/A_MeleeHit_{i:02d}" for i in (1, 2, 3))

# This creature's six flinches, carried on the CONTROLLER and copied onto the
# pawn's health component at possession -- the same route, and for the same
# reason, as its health: an AnimSequence belongs to one skeleton, the variants
# are three different skeletons, and a child Blueprint's override of an
# inherited component's defaults lives in an InheritableComponentHandler the
# Python API cannot reach.  Without this every wanderer would flinch with
# BP_ForestWanderer's mesh's clips, i.e. the wendigos would not flinch at all.
REACTIONS_VAR = "HitReactions"
# On BP_HealthComponent, written by whoever did the damage: a unit vector from
# the victim toward the source.  The wanderers' punch is the only melee in the
# game and this is the only place it is written; build_weapons_and_combat.py
# writes it off the impact normal for a bullet.  See _author_hit_reaction there
# for what reads it.
LAST_HIT_FROM_VAR = "LastHitFrom"

NODE_CAST_CHARACTER = "Utilities|Casting|CastToCharacter"
NODE_CAST_HEALTH = "Utilities|Casting|CastToBP_HealthComponent"

BGE = unreal.BlueprintGraphEditor
BEL = unreal.BlueprintEditorLibrary
PIN = unreal.BlueprintGraphPinLibrary


def _log(msg):
    unreal.log_warning(f"[NPC] {msg}")


def _try_set(obj, prop, value):
    """Set a property, logging instead of raising if the name moved."""
    try:
        obj.set_editor_property(prop, value)
    except Exception as exc:
        unreal.log_warning(f"[NPC] could not set {prop}: {exc}")


def _asset_sub():
    return unreal.get_editor_subsystem(unreal.EditorAssetSubsystem)


def _create_blueprint(path, parent_class):
    """
    Load the Blueprint at ``path``, creating it if absent.

    Deliberately does NOT delete-and-recreate: an existing asset is usually
    still referenced (by the level's NPC actor, or by the other blueprint's
    ai_controller_class), the delete then silently fails, and asset creation
    errors out. Updating in place is both more robust and idempotent.
    """
    eas = _asset_sub()
    if eas.does_asset_exist(path):
        existing = eas.load_asset(path)
        if existing:
            return existing
    package_path, asset_name = path.rsplit("/", 1)
    factory = unreal.BlueprintFactory()
    factory.set_editor_property("parent_class", parent_class)
    bp = unreal.AssetToolsHelpers.get_asset_tools().create_asset(
        asset_name, package_path, unreal.Blueprint, factory)
    if not bp:
        raise RuntimeError(f"Could not create Blueprint {path}")
    return bp


def _pin(node, name, is_input=True):
    """Find a pin by name, raising with a useful message if it is missing."""
    p = (BEL.find_input_pin(node, name) if is_input
         else BEL.find_output_pin(node, name))
    if not p or not p.is_valid():
        raise RuntimeError(
            f"pin {name!r} ({'in' if is_input else 'out'}) not found on "
            f"{type(node).__name__}")
    return p


def _connect(a, b):
    if not a.try_create_connection(b):
        raise RuntimeError("could not connect pins")


def _at(node, x, y):
    BEL.set_node_pos(node, unreal.IntPoint(int(x), int(y)))
    return node


def _node(ed, function_path):
    """add_call_function_node, but loud when the path does not resolve.

    An unresolvable path yields a *pinless* node rather than None, which
    surfaces much later as a baffling "pin 'self' not found on ''".
    """
    n = ed.add_call_function_node(function_path)
    if not n or not BEL.list_all_pins(n):
        raise RuntimeError(f"{function_path} is not a Blueprint-callable function")
    return n


def _palette(ed, name, x=0.0, y=0.0):
    n = ed.create_node_from_name(name, unreal.Vector2D(float(x), float(y)), [])
    if not n:
        raise RuntimeError(f"palette node {name!r} could not be created")
    return n


def _loose_pin(node, wanted, is_input=True):
    """Find a pin ignoring spaces and case -- cast nodes name their output after
    the class with spaces inserted ("AsBP Health Component")."""
    key = wanted.replace(" ", "").lower()
    for p in (BEL.list_input_pins(node) if is_input else BEL.list_output_pins(node)):
        if str(PIN.get_pin_name(p)).replace(" ", "").lower() == key:
            return p
    raise RuntimeError(f"no pin like {wanted!r} on {BEL.get_node_title(node)}")


def _set(node, name, value):
    """Set a pin's literal and prove it landed.

    set_pin_value's return is not a usable signal (False means both "rejected"
    and "already equal to the default"), and a pin that quietly stays empty
    compiles as **zero** -- a melee attack for 0 damage at a range of 0, which
    looks perfect in the graph.
    """
    pin = _pin(node, name)
    pin.set_pin_value(str(value))
    got = str(PIN.get_pin_value(pin))
    if got == str(value):
        return
    try:
        if abs(float(got or 0.0) - float(value)) < 1e-6:
            return
    except ValueError:
        pass
    if got.lower() == str(value).lower() or got.endswith(f"::{value}"):
        return
    raise RuntimeError(f"pin {name!r} would not take {value!r} — reads back {got!r}")


# ─── The AI controller ──────────────────────────────────────────────────────

# ─── Playing one of several sounds ──────────────────────────────────────────

def _author_random_sound(ed, var_name, at_pin, exec_in, x0, y0):
    """Play a random element of the ``var_name`` sound array at ``at_pin``.

    Returns ``(nodes, then_pin)``.  The array is guarded on its own length:
    RandomIntegerInRange(0, -1) against an empty array feeds Array_Get an index
    into nothing, which is an access-none at runtime rather than silence.  That
    matters here because the arrays are filled from /Game/Audio, which a
    checkout that has never run Scripts/make_creature_sounds.py does not have
    -- an unvoiced monster is a fine outcome, a spammed error log is not.

    One sound is drawn per call rather than cycling, and there are three of
    each: a pack of ten retriggering a single buffer on a shared timer reads
    as one machine, which is the same lockstep problem gait_scale_for_index
    solves for the legs.
    """
    made = []

    def keep(n):
        made.append(n)
        return n

    table = keep(_at(ed.add_get_member_variable_node(var_name), x0, y0 + 240))
    table_out = _pin(table, var_name, is_input=False)

    count = keep(_at(_node(ed, FN_ARR_LEN), x0 + 240, y0 + 240))
    _connect(table_out, _pin(count, "TargetArray"))
    stocked = keep(_at(_node(ed, FN_GREATER_II), x0 + 480, y0 + 240))
    _connect(_pin(count, "ReturnValue", is_input=False), _pin(stocked, "A"))
    _set(stocked, "B", 0)

    have = keep(_at(ed.add_branch_node(), x0 + 720, y0))
    _connect(_pin(stocked, "ReturnValue", is_input=False), _pin(have, "Condition"))
    _connect(exec_in, _pin(have, "execute"))

    # RandomIntegerInRange is inclusive at both ends, so the top is length - 1.
    top = keep(_at(_node(ed, FN_SUB_II), x0 + 720, y0 + 240))
    _connect(_pin(count, "ReturnValue", is_input=False), _pin(top, "A"))
    _set(top, "B", 1)
    which = keep(_at(_node(ed, FN_RAND_INT), x0 + 960, y0 + 240))
    _set(which, "Min", 0)
    _connect(_pin(top, "ReturnValue", is_input=False), _pin(which, "Max"))
    pick = keep(_at(_node(ed, FN_ARR_GET), x0 + 1200, y0 + 240))
    _connect(table_out, _pin(pick, "TargetArray"))
    _connect(_pin(which, "ReturnValue", is_input=False), _pin(pick, "Index"))

    play = keep(_at(_node(ed, FN_PLAY_SOUND), x0 + 1440, y0))
    _connect(_pin(pick, "Item", is_input=False), _pin(play, "Sound"))
    _connect(at_pin, _pin(play, "Location"))
    _connect(BEL.find_then_pin(have), _pin(play, "execute"))

    # A join node so the caller has ONE exec to carry on from whether or not
    # there was a sound to play. Without it the empty-array path dangles and
    # the chase loop ends the first time a wanderer tries to speak.
    join = keep(_at(ed.add_branch_node(), x0 + 1700, y0))
    _set(join, "Condition", "true")
    _connect(BEL.find_then_pin(play), _pin(join, "execute"))
    _connect(BEL.find_else_pin(have), _pin(join, "execute"))
    return made, BEL.find_then_pin(join)


def _author_stats_and_voice(ed, gate, x0, y0, health, voice_min, voice_max):
    """Apply this creature's health once, then growl on a timer.

    Both hang off the chase loop's existing heartbeat rather than getting a
    Tick of their own, for the reason _author_melee gives: the loop is already
    the NPC's clock and a second one is only a way for the two to disagree.

        gate(possessed) --> [stats applied yet?]
                              no  --> MaxHealth = Health = <this creature's>
                              yes ----------------------------.
                                                              v
                                            [time to make a noise?]
                                              yes --> play one of Voices
                                              no  ----------------------> on

    Health is applied HERE, from a literal baked into this controller, rather
    than set on the pawn Blueprint. It has to be: MaxHealth lives on an
    inherited BP_HealthComponent, and Unreal stores a child Blueprint's
    override of an inherited component's defaults in an InheritableComponentHandler
    that the Python API does not expose -- ``get_component_by_class`` on a CDO
    returns None (measured). The controller is already per creature for the
    attack clip, so it is the one place that both knows which creature this is
    and can reach the component at runtime.

    Applying it on the first heartbeat AFTER possession, rather than at
    BeginPlay, is what makes it reliable: a controller's BeginPlay runs before
    it possesses anything, so there is no pawn to find the component on.

    Returns the nodes it made and the exec to carry on with.
    """
    made = []

    def keep(n):
        made.append(n)
        return n

    for name, kind in ((STATS_APPLIED_VAR, "bool"), (NEXT_VOICE_VAR, "real")):
        ed.remove_member_variable(name)
        if not ed.add_member_variable(name, BEL.get_basic_type_by_name(kind)):
            raise RuntimeError(f"could not declare {name}")
    sound_array = BEL.get_array_type(
        BEL.get_object_reference_type(unreal.SoundBase.static_class()))
    for name in (VOICES_VAR, HIT_SOUNDS_VAR):
        ed.remove_member_variable(name)
        if not ed.add_member_variable(name, sound_array):
            raise RuntimeError(f"could not declare {name}")
    ed.remove_member_variable(REACTIONS_VAR)
    if not ed.add_member_variable(REACTIONS_VAR, BEL.get_array_type(
            BEL.get_object_reference_type(unreal.AnimSequenceBase.static_class()))):
        raise RuntimeError(f"could not declare {REACTIONS_VAR}")

    pawn = keep(_at(_node(ed, FN_GET_PAWN), x0, y0 + 620))
    pawn_out = _pin(pawn, "ReturnValue", is_input=False)
    where = keep(_at(_node(ed, FN_ACTOR_LOC), x0 + 240, y0 + 620))
    _connect(pawn_out, _pin(where, "self"))
    where_out = _pin(where, "ReturnValue", is_input=False)

    # --- once: this creature's health ---------------------------------------
    done = keep(_at(ed.add_get_member_variable_node(STATS_APPLIED_VAR), x0, y0 + 240))
    fresh = keep(_at(_node(ed, FN_NOT), x0 + 240, y0 + 240))
    _connect(_pin(done, STATS_APPLIED_VAR, is_input=False), _pin(fresh, "A"))
    first = keep(_at(ed.add_branch_node(), x0 + 480, y0))
    _connect(_pin(fresh, "ReturnValue", is_input=False), _pin(first, "Condition"))
    _connect(BEL.find_then_pin(gate), _pin(first, "execute"))

    comp = keep(_at(_node(ed, FN_GET_COMP), x0 + 480, y0 + 380))
    _connect(pawn_out, _pin(comp, "self"))
    _pin(comp, "ComponentClass").set_pin_value(HEALTH_CLASS_PATH)
    as_health = keep(_at(_palette(ed, NODE_CAST_HEALTH), x0 + 720, y0))
    _connect(_pin(comp, "ReturnValue", is_input=False), _pin(as_health, "Object"))
    _connect(BEL.find_then_pin(first), _pin(as_health, "execute"))
    health_out = _loose_pin(as_health, "AsBPHealthComponent", is_input=False)

    set_max = keep(_at(ed.add_set_member_variable_node("MaxHealth", HEALTH_CLASS_PATH),
                       x0 + 980, y0))
    _connect(health_out, _pin(set_max, "self"))
    _set(set_max, "MaxHealth", health)
    _connect(BEL.find_then_pin(as_health), _pin(set_max, "execute"))

    set_now = keep(_at(ed.add_set_member_variable_node("Health", HEALTH_CLASS_PATH),
                       x0 + 1240, y0))
    _connect(health_out, _pin(set_now, "self"))
    _set(set_now, "Health", health)
    _connect(BEL.find_then_pin(set_max), _pin(set_now, "execute"))

    # ...and this creature's own hit reactions, onto the same component, in the
    # same breath and for the same reason.  A plain array-to-array copy: the
    # health component's graph does the picking, all this has to do is put the
    # right skeleton's clips where it can see them.
    set_reacts = keep(_at(ed.add_set_member_variable_node(REACTIONS_VAR,
                                                          HEALTH_CLASS_PATH),
                          x0 + 1500, y0))
    _connect(health_out, _pin(set_reacts, "self"))
    mine = keep(_at(ed.add_get_member_variable_node(REACTIONS_VAR),
                    x0 + 1500, y0 + 380))
    _connect(_pin(mine, REACTIONS_VAR, is_input=False),
             _pin(set_reacts, REACTIONS_VAR))
    _connect(BEL.find_then_pin(set_now), _pin(set_reacts, "execute"))

    mark = keep(_at(ed.add_set_member_variable_node(STATS_APPLIED_VAR), x0 + 1760, y0))
    _set(mark, STATS_APPLIED_VAR, "true")
    _connect(BEL.find_then_pin(set_reacts), _pin(mark, "execute"))

    # --- every few seconds: a noise -----------------------------------------
    now = keep(_at(_node(ed, FN_TIME_SECONDS), x0 + 1760, y0 + 380))
    now_out = _pin(now, "ReturnValue", is_input=False)
    due_at = keep(_at(ed.add_get_member_variable_node(NEXT_VOICE_VAR), x0 + 1760, y0 + 500))
    due = keep(_at(_node(ed, FN_GE_FF), x0 + 2000, y0 + 380))
    _connect(now_out, _pin(due, "A"))
    _connect(_pin(due_at, NEXT_VOICE_VAR, is_input=False), _pin(due, "B"))
    speak = keep(_at(ed.add_branch_node(), x0 + 2240, y0))
    _connect(_pin(due, "ReturnValue", is_input=False), _pin(speak, "Condition"))
    # Every way into the voice check: stats just applied, stats already
    # applied, or the component was not there to apply them to.
    for tail in (BEL.find_then_pin(mark),
                 BEL.find_else_pin(first),
                 _pin(as_health, "CastFailed", is_input=False)):
        _connect(tail, _pin(speak, "execute"))

    voiced, after_voice = _author_random_sound(
        ed, VOICES_VAR, where_out, BEL.find_then_pin(speak), x0 + 2500, y0)
    made.extend(voiced)

    gap = keep(_at(_node(ed, FN_RANDOM_FLOAT), x0 + 4300, y0 + 380))
    _set(gap, "Min", voice_min)
    _set(gap, "Max", voice_max)
    again = keep(_at(_node(ed, FN_ADD_FF), x0 + 4540, y0 + 380))
    _connect(now_out, _pin(again, "A"))
    _connect(_pin(gap, "ReturnValue", is_input=False), _pin(again, "B"))
    rearm = keep(_at(ed.add_set_member_variable_node(NEXT_VOICE_VAR), x0 + 4800, y0))
    _connect(_pin(again, "ReturnValue", is_input=False), _pin(rearm, NEXT_VOICE_VAR))
    _connect(after_voice, _pin(rearm, "execute"))

    # One exec out, whether or not it spoke this pass.
    out = keep(_at(ed.add_branch_node(), x0 + 5060, y0))
    _set(out, "Condition", "true")
    _connect(BEL.find_then_pin(rearm), _pin(out, "execute"))
    _connect(BEL.find_else_pin(speak), _pin(out, "execute"))
    return made, BEL.find_then_pin(out)



def _author_melee(ed, after_move, delay, x0, y0, melee_anim=None):
    """Swing at the player when the chase has closed the distance.

    ``after_move`` is every exec pin that has just issued a move order -- there
    are two of them now, the pathfinding one and the straight-line one -- and
    all of them run into the same range check. The melee half does not care
    which kind of move got the NPC here.

    Spliced between the move order and the re-path delay, so the check runs
    every NPC_REPATH_SECONDS with no Tick event of its own: the loop is already
    the NPC's heartbeat, and a second one would only add a way for the two to
    disagree about whether the chase is still running.

        MoveToActor --> [in range AND off cooldown?]
                          true  --> NextAttackTime = now + interval
                                --> play MM_Attack_01 on the upper body
                                --> player Health -= NPC_MELEE_DAMAGE
                          false -------------------------------------> Delay

    Range is centre-to-centre between the two capsules, which is why
    NPC_MELEE_RANGE_CM (200) has to exceed NPC_ACCEPTANCE_RADIUS_CM (120): the
    move order stops the NPC at the acceptance radius, and an NPC that parks
    itself outside its own reach never lands a hit.

    The cooldown is wall-clock rather than a counter of loop iterations so the
    swing rate is independent of NPC_REPATH_SECONDS -- and it lives on the
    *controller*, so five wanderers each keep their own, rather than sharing one
    and machine-gunning the player in lockstep.

    Damage is applied by writing Health on the player's BP_HealthComponent,
    which is exactly what the pellets do (see _author_impact in
    build_weapons_and_combat.py). Routing through ApplyDamage/AnyDamage instead
    would need a graph on BP_ThirdPersonCharacter, whose Enhanced Input template
    graph the Python API cannot partially rebuild.

    Returns the nodes it made (for the comment box), or None when
    BP_HealthComponent is absent -- a project where the weapons have never been
    built still gets a chasing NPC, just not a damaging one.
    """
    eas = _asset_sub()
    if not eas.does_asset_exist(HEALTH_BP_PATH):
        _log(f"note: {HEALTH_BP_PATH} not found — melee skipped, the NPC will "
             f"chase but not attack (run build_weapons_and_combat.py first)")
        return None
    # A cast node only appears in the palette for a class that is already
    # loaded; without this the node name reads like a typo rather than a
    # missing asset.
    if not eas.load_asset(HEALTH_BP_PATH):
        raise RuntimeError(f"could not load {HEALTH_BP_PATH} for its cast node")

    made = []

    def keep(n):
        made.append(n)
        return n

    # --- is the player within reach? ----------------------------------------
    self_pawn = keep(_at(_node(ed, FN_GET_PAWN), x0, y0 + 260))
    self_loc = keep(_at(_node(ed, FN_ACTOR_LOC), x0 + 240, y0 + 260))
    _connect(_pin(self_pawn, "ReturnValue", is_input=False), _pin(self_loc, "self"))

    player = keep(_at(_node(ed, FN_GET_PLAYER_PAWN), x0, y0 + 420))
    _set(player, "PlayerIndex", 0)
    player_out = _pin(player, "ReturnValue", is_input=False)
    player_loc = keep(_at(_node(ed, FN_ACTOR_LOC), x0 + 240, y0 + 420))
    _connect(player_out, _pin(player_loc, "self"))

    gap = keep(_at(_node(ed, FN_DISTANCE), x0 + 480, y0 + 340))
    _connect(_pin(self_loc, "ReturnValue", is_input=False), _pin(gap, "V1"))
    _connect(_pin(player_loc, "ReturnValue", is_input=False), _pin(gap, "V2"))

    in_range = keep(_at(_node(ed, FN_LE_FF), x0 + 720, y0 + 340))
    _connect(_pin(gap, "ReturnValue", is_input=False), _pin(in_range, "A"))
    _set(in_range, "B", NPC_MELEE_RANGE_CM)

    # --- has this NPC's cooldown expired? ------------------------------------
    now = keep(_at(_node(ed, FN_TIME_SECONDS), x0 + 480, y0 + 560))
    now_out = _pin(now, "ReturnValue", is_input=False)
    next_at = keep(_at(ed.add_get_member_variable_node("NextAttackTime"),
                       x0 + 480, y0 + 680))
    ready = keep(_at(_node(ed, FN_GE_FF), x0 + 720, y0 + 560))
    _connect(now_out, _pin(ready, "A"))
    _connect(_pin(next_at, "NextAttackTime", is_input=False), _pin(ready, "B"))

    both = keep(_at(_node(ed, FN_AND), x0 + 960, y0 + 400))
    _connect(_pin(in_range, "ReturnValue", is_input=False), _pin(both, "A"))
    _connect(_pin(ready, "ReturnValue", is_input=False), _pin(both, "B"))

    swing = keep(_at(ed.add_branch_node(), x0 + 1200, y0))
    _connect(_pin(both, "ReturnValue", is_input=False), _pin(swing, "Condition"))
    for tail in after_move:
        _connect(tail, _pin(swing, "execute"))
    # Not in range, or still on cooldown: straight on to the re-path delay.
    _connect(BEL.find_else_pin(swing), BEL.find_execute_pin(delay))

    # --- arm the next swing --------------------------------------------------
    when = keep(_at(_node(ed, FN_ADD_FF), x0 + 1440, y0 + 300))
    _connect(now_out, _pin(when, "A"))
    _set(when, "B", NPC_MELEE_INTERVAL_S)
    arm = keep(_at(ed.add_set_member_variable_node("NextAttackTime"),
                   x0 + 1680, y0))
    _connect(_pin(when, "ReturnValue", is_input=False), _pin(arm, "NextAttackTime"))
    _connect(BEL.find_then_pin(swing), _pin(arm, "execute"))

    # --- play the swing ------------------------------------------------------
    # The montage goes through the pawn's own AnimInstance, so it animates
    # whichever body this controller happens to possess rather than assuming
    # BP_ForestWanderer.
    as_char = keep(_at(_palette(ed, NODE_CAST_CHARACTER), x0 + 1920, y0))
    _connect(_pin(self_pawn, "ReturnValue", is_input=False), _pin(as_char, "Object"))
    _connect(BEL.find_then_pin(arm), _pin(as_char, "execute"))
    char_out = _loose_pin(as_char, "AsCharacter", is_input=False)

    mesh = keep(_at(ed.add_get_member_variable_node("Mesh", "/Script/Engine.Character"),
                    x0 + 1920, y0 + 300))
    _connect(char_out, _pin(mesh, "self"))

    anim = keep(_at(_node(ed, FN_ANIM_INSTANCE), x0 + 2160, y0 + 300))
    _connect(_pin(mesh, "Mesh", is_input=False), _pin(anim, "self"))

    montage = keep(_at(_node(ed, FN_PLAY_SLOT), x0 + 2400, y0))
    _connect(_pin(anim, "ReturnValue", is_input=False), _pin(montage, "self"))
    _set(montage, "Asset", melee_anim or _melee_montage_object())
    _set(montage, "SlotNodeName", MELEE_SLOT)
    _set(montage, "BlendInTime", NPC_MELEE_BLEND_S)
    _set(montage, "BlendOutTime", NPC_MELEE_BLEND_S)
    _connect(BEL.find_then_pin(as_char), _pin(montage, "execute"))

    # --- land the hit --------------------------------------------------------
    comp = keep(_at(_node(ed, FN_GET_COMP), x0 + 2400, y0 + 300))
    _connect(player_out, _pin(comp, "self"))
    _pin(comp, "ComponentClass").set_pin_value(HEALTH_CLASS_PATH)

    hit = keep(_at(_palette(ed, NODE_CAST_HEALTH), x0 + 2640, y0))
    _connect(_pin(comp, "ReturnValue", is_input=False), _pin(hit, "Object"))
    _connect(BEL.find_then_pin(montage), _pin(hit, "execute"))
    as_health = _loose_pin(hit, "AsBPHealthComponent", is_input=False)

    read = keep(_at(ed.add_get_member_variable_node("Health", HEALTH_CLASS_PATH),
                    x0 + 2880, y0 + 300))
    _connect(as_health, _pin(read, "self"))
    hurt = keep(_at(_node(ed, FN_SUB_FF), x0 + 3120, y0 + 300))
    _connect(_pin(read, "Health", is_input=False), _pin(hurt, "A"))
    _set(hurt, "B", NPC_MELEE_DAMAGE)
    floor = keep(_at(_node(ed, FN_CLAMP), x0 + 3360, y0 + 300))
    _connect(_pin(hurt, "ReturnValue", is_input=False), _pin(floor, "Value"))
    _set(floor, "Min", 0.0)
    _set(floor, "Max", INF)
    write = keep(_at(ed.add_set_member_variable_node("Health", HEALTH_CLASS_PATH),
                     x0 + 3600, y0))
    _connect(as_health, _pin(write, "self"))
    _connect(_pin(floor, "ReturnValue", is_input=False), _pin(write, "Health"))
    _connect(BEL.find_then_pin(hit), _pin(write, "execute"))

    # --- and which way it came from ------------------------------------------
    # The player's flinch is picked by direction, and a punch has no impact
    # normal to read it off -- so it is stated: the unit vector from the player
    # to the wanderer that swung.  Both locations are already on the graph for
    # the range check, so this is three pure nodes and a Set.  Whichever of the
    # ten lands the blow writes its own bearing, so being surrounded reads as
    # being hit from all sides rather than as one repeated stagger.
    toward = keep(_at(_node(ed, FN_SUB_VV), x0 + 3600, y0 + 300))
    _connect(_pin(self_loc, "ReturnValue", is_input=False), _pin(toward, "A"))
    _connect(_pin(player_loc, "ReturnValue", is_input=False), _pin(toward, "B"))
    bearing = keep(_at(_node(ed, FN_NORMAL), x0 + 3840, y0 + 300))
    _connect(_pin(toward, "ReturnValue", is_input=False), _pin(bearing, "A"))
    came_from = keep(_at(ed.add_set_member_variable_node(LAST_HIT_FROM_VAR,
                                                          HEALTH_CLASS_PATH),
                         x0 + 3840, y0))
    _connect(as_health, _pin(came_from, "self"))
    _connect(_pin(bearing, "ReturnValue", is_input=False),
             _pin(came_from, LAST_HIT_FROM_VAR))
    _connect(BEL.find_then_pin(write), _pin(came_from, "execute"))

    # --- and make a noise landing it ----------------------------------------
    # At the PLAYER's location rather than the wanderer's: the sound is the
    # impact, and the impact happens where the hit lands. With ten wanderers
    # around one player the difference is audible -- from the attacker it
    # smears around the listener, from the target it is one solid thump in
    # front of them.
    thud, after_thud = _author_random_sound(
        ed, HIT_SOUNDS_VAR, _pin(player_loc, "ReturnValue", is_input=False),
        BEL.find_then_pin(came_from), x0 + 4120, y0)
    made.extend(thud)

    # Every exit -- hit, missing health component, not a Character -- has to
    # reach the Delay, or the chase loop ends on the first swing and the NPC
    # stands still forever.  A cast's failure pin left dangling is exactly that
    # bug, and it only shows up in a level where the player has no health
    # component.
    for tail in (after_thud,
                 _pin(hit, "CastFailed", is_input=False),
                 _pin(as_char, "CastFailed", is_input=False)):
        _connect(tail, BEL.find_execute_pin(delay))

    return made


def build_ai_controller_blueprint(rebuild=True, path=None, melee_anim=None,
                                 health=NPC_BASE_HEALTH, voices=(),
                                 hit_sounds=HIT_SOUNDS, reactions=()):
    """Create an AI controller and author its chase-and-attack loop.

    ``rebuild`` wipes the graph first.  It defaults to True because this builder
    is the only description of the behaviour: the old "already authored,
    reusing" guard meant no edit here ever reached the asset once it existed.

    ``path``, ``melee_anim``, ``health`` and ``voices`` exist because all four
    are per creature.  The attack clip is per creature because
    each monster now has its own skeleton (see import_characters.py), and an
    AnimSequence belongs to exactly one skeleton, so a single controller cannot
    hold a literal that plays on both a zombie and a wendigo.  ``health`` is
    per creature because a wendigo has three times a zombie's, and the
    controller is the only place that can reach an inherited component's
    defaults per child (see _author_stats_and_voice).  ``voices`` because a
    zombie growls and a wendigo roars.

    A controller per variant is one way to solve that, and it is what this
    does.  Both are generated by THIS function from the same constants, so the
    melee numbers cannot drift between them the way two hand-authored graphs
    would.

    It is not the only way, and probably not the best one.  The alternative --
    an AnimSequence variable on the pawn, overridden per child Blueprint, read
    by one shared controller -- was ruled out on the false belief that Python
    cannot declare object-reference variables.  It can:
    BlueprintEditorLibrary.get_object_reference_type, which
    build_weapons_and_combat.py already uses for FireSound and AimPose.  That
    route would need the pawn Blueprint to exist before the controller graph is
    authored (they are currently built the other way round) and a cast to read
    the variable, so it is a real refactor rather than a rename -- worth doing
    when a third creature makes the duplication cost something.
    """
    path = path or AI_BP_PATH
    bp = _create_blueprint(path, unreal.AIController)
    ed = BGE.get_graph_editor_by_name(bp, "EventGraph")
    if not ed:
        raise RuntimeError(f"{path} has no EventGraph")

    begin_play = ed.find_event_node("ReceiveBeginPlay")
    authored = bool(begin_play and BEL.find_then_pin(begin_play)
                    and BEL.find_then_pin(begin_play).list_connected_pins())
    if authored and not rebuild:
        _log(f"{path} graph already authored — reusing")
        if not BEL.compile_blueprint(bp):
            raise RuntimeError(f"{path} failed to compile")
        _asset_sub().save_loaded_asset(bp)
        return bp
    if authored:
        _log("wiping the existing AI graph")
        ed.remove_nodes(ed.list_all_nodes())
        begin_play = None

    if not begin_play:
        begin_play = ed.find_event_node("ReceiveBeginPlay")
    if not begin_play:
        # A fresh Blueprint ships a disabled BeginPlay placeholder, but a wiped
        # graph has none, so put one back from the palette.
        begin_play = _palette(ed, "AddEvent|EventBeginPlay", 0.0, 0.0)
    origin = BEL.get_node_pos(begin_play)

    # Each NPC's swing timer. Zero is the right default -- it means "may attack
    # immediately" -- which is just as well, since add_member_variable's own
    # default-value argument silently does not apply (see CLAUDE.md).
    ed.remove_member_variable("NextAttackTime")
    if not ed.add_member_variable("NextAttackTime",
                                  BEL.get_basic_type_by_name("real")):
        raise RuntimeError("could not declare NextAttackTime")

    move_to = _at(_node(ed, FN_MOVE_TO_ACTOR), origin.x + 1000, origin.y - 120)
    get_pawn = _at(_node(ed, FN_GET_PLAYER_PAWN), origin.x + 40, origin.y + 220)
    delay = _at(_node(ed, FN_DELAY), origin.x + 4600, origin.y)

    # Goal = the player pawn
    _set(get_pawn, "PlayerIndex", 0)
    _connect(_pin(get_pawn, "ReturnValue", is_input=False), _pin(move_to, "Goal"))

    # Pathfinding is what makes it run around the trees rather than into them.
    _set(move_to, "AcceptanceRadius", NPC_ACCEPTANCE_RADIUS_CM)
    _set(move_to, "bUsePathfinding", "true")
    _set(move_to, "bStopOnOverlap", "true")
    # Partial paths keep the NPC advancing as far as the navmesh allows instead
    # of refusing to move at all; the retry loop then re-paths, so a temporary
    # dead end does not end the chase.
    _set(move_to, "bAllowPartialPath", "true")

    _set(delay, "Duration", NPC_REPATH_SECONDS)

    # BeginPlay -> [possessed?] -> MoveToActor -> (melee) -> Delay -> back
    #
    # The gate is not defensive padding: a controller's BeginPlay runs before it
    # has possessed anything, so the first pass through the loop has no pawn.
    # MoveToActor then quietly does nothing, and the melee chain's
    # GetActorLocation reads a None pawn -- which the VM reports as an "Accessed
    # None ... CallFunc_K2_GetPawn_ReturnValue" runtime error against the swing
    # Branch, once per spawned NPC.  Note the gate has to sit *before*
    # MoveToActor rather than joining the melee AND: pure nodes are pulled by
    # whichever node reads them and BooleanAND does not short-circuit, so an
    # IsValid in the condition would still evaluate the location chain.
    #
    # Skipping the body costs one Delay -- the loop re-enters
    # NPC_REPATH_SECONDS later, by which time possession has happened.
    own_pawn = _at(_node(ed, FN_GET_PAWN), origin.x - 220, origin.y - 320)
    possessed = _at(_node(ed, FN_IS_VALID), origin.x + 40, origin.y - 320)
    _connect(_pin(own_pawn, "ReturnValue", is_input=False),
             _pin(possessed, "Object"))
    gate = _at(ed.add_branch_node(), origin.x + 300, origin.y - 200)
    _connect(_pin(possessed, "ReturnValue", is_input=False),
             _pin(gate, "Condition"))
    _connect(BEL.find_then_pin(begin_play), _pin(gate, "execute"))
    _connect(BEL.find_then_pin(delay), _pin(gate, "execute"))
    # --- can this chase be pathfound at all? ---------------------------------
    # See NAV_REACHABLE_EXTENT_CM. Both ends are tested, and both have to be
    # on the navmesh for pathfinding to be the right tool: a player who has
    # walked into the un-navigable ring cannot be pathed TO, and a wanderer
    # already standing in it cannot be pathed FROM. Either way the answer is
    # the same -- walk at them in a straight line.
    #
    # K2_ProjectPointToNavigation is pure and re-evaluates once per output pin
    # that is read. Only ReturnValue is read from each of these, so each
    # projects exactly once per frame the loop runs, and the ProjectedLocation
    # output is deliberately left dangling: the destination is the player's
    # real position, not a snapped one. Snapping it back onto the navmesh is
    # precisely the behaviour that made the dead zone.
    reach = _at(_node(ed, FN_MAKE_VECTOR), origin.x + 40, origin.y + 900)
    for axis, value in zip(("X", "Y", "Z"), NAV_REACHABLE_EXTENT_CM):
        _set(reach, axis, value)
    reach_out = _pin(reach, "ReturnValue", is_input=False)

    goal_loc = _at(_node(ed, FN_ACTOR_LOC), origin.x + 300, origin.y + 380)
    _connect(_pin(get_pawn, "ReturnValue", is_input=False), _pin(goal_loc, "self"))
    goal_out = _pin(goal_loc, "ReturnValue", is_input=False)
    goal_on = _at(_node(ed, FN_PROJECT_NAV), origin.x + 560, origin.y + 380)
    _connect(goal_out, _pin(goal_on, "Point"))
    _connect(reach_out, _pin(goal_on, "QueryExtent"))

    here_pawn = _at(_node(ed, FN_GET_PAWN), origin.x + 40, origin.y + 620)
    here_loc = _at(_node(ed, FN_ACTOR_LOC), origin.x + 300, origin.y + 620)
    _connect(_pin(here_pawn, "ReturnValue", is_input=False), _pin(here_loc, "self"))
    here_on = _at(_node(ed, FN_PROJECT_NAV), origin.x + 560, origin.y + 620)
    _connect(_pin(here_loc, "ReturnValue", is_input=False), _pin(here_on, "Point"))
    _connect(reach_out, _pin(here_on, "QueryExtent"))

    both_on = _at(_node(ed, FN_AND_B), origin.x + 800, origin.y + 500)
    _connect(_pin(goal_on, "ReturnValue", is_input=False), _pin(both_on, "A"))
    _connect(_pin(here_on, "ReturnValue", is_input=False), _pin(both_on, "B"))

    pathable = _at(ed.add_branch_node(), origin.x + 800, origin.y + 200)
    _connect(_pin(both_on, "ReturnValue", is_input=False), _pin(pathable, "Condition"))
    _connect(BEL.find_then_pin(pathable), BEL.find_execute_pin(move_to))

    # Between "we have a pawn" and "can we path to the player": this creature's
    # health, applied once, and its voice on a timer. Both need the pawn, which
    # is why they sit after the gate and not on BeginPlay.
    extras, after_extras = _author_stats_and_voice(
        ed, gate, origin.x - 200, origin.y + 1400,
        health, NPC_VOICE_MIN_S, NPC_VOICE_MAX_S)
    _connect(after_extras, _pin(pathable, "execute"))

    # --- the straight line ---------------------------------------------------
    # Not a teleport, not AddMovementInput, and not a second Tick: this is the
    # SAME move request the pathfinding branch issues, with pathfinding off, so
    # the path-following component drives the character with the same
    # acceleration and the same stop condition and keeps doing it between loop
    # iterations. AddMovementInput would move the NPC for exactly one frame out
    # of every thirty, because this loop runs twice a second.
    #
    # bProjectDestinationToNavigation must stay FALSE. True is the dead zone,
    # written a different way: it snaps the goal back onto the navmesh island
    # and the NPC walks to the edge and stops.
    direct = _at(_node(ed, FN_MOVE_TO_LOCATION), origin.x + 1000, origin.y + 200)
    _connect(goal_out, _pin(direct, "Dest"))
    _set(direct, "AcceptanceRadius", NPC_ACCEPTANCE_RADIUS_CM)
    _set(direct, "bUsePathfinding", "false")
    _set(direct, "bProjectDestinationToNavigation", "false")
    _set(direct, "bStopOnOverlap", "true")
    _set(direct, "bCanStrafe", "false")
    _connect(BEL.find_else_pin(pathable), BEL.find_execute_pin(direct))

    after_move = (BEL.find_then_pin(move_to), BEL.find_then_pin(direct))

    _connect(BEL.find_else_pin(gate), BEL.find_execute_pin(delay))

    melee = _author_melee(ed, after_move, delay, origin.x + 1400, origin.y,
                          melee_anim=melee_anim)
    if melee is None:
        for tail in after_move:
            _connect(tail, BEL.find_execute_pin(delay))

    ed.add_comment_to_nodes(
        f"Re-issue a move order at the player every {NPC_REPATH_SECONDS} s, "
        f"once the controller has a pawn to move. Pathfinding when both ends "
        f"are on the navmesh -- which is what runs the NPC around trees -- and "
        f"a straight-line move order when either end is not, because the "
        f"navmesh only covers a disc inside the terrain and a player in the "
        f"ring outside it used to be simply unreachable.",
        [move_to, get_pawn, delay, gate, own_pawn, possessed, reach, goal_loc,
         goal_on, here_pawn, here_loc, here_on, both_on, pathable, direct])
    if melee:
        ed.add_comment_to_nodes(
            f"Melee: within {NPC_MELEE_RANGE_CM:.0f} cm and off cooldown, swing "
            f"for {NPC_MELEE_DAMAGE:.0f} damage, then arm the next swing "
            f"{NPC_MELEE_INTERVAL_S} s out. The cooldown is per controller, so "
            f"a pack does not hit in lockstep.",
            melee)

    ed.add_comment_to_nodes(
        f"This creature's own health ({health:.0f}), applied once on the first "
        f"heartbeat after possession, and its voice every "
        f"{NPC_VOICE_MIN_S:.0f}-{NPC_VOICE_MAX_S:.0f} s. Health is set from "
        f"here rather than on the pawn because MaxHealth lives on an INHERITED "
        f"component, and Unreal keeps a child Blueprint's override of one in an "
        f"InheritableComponentHandler that Python cannot reach.",
        extras)

    if not BEL.compile_blueprint(bp):
        raise RuntimeError(f"{path} failed to compile")

    # The sound arrays are defaults on the class, not pin literals -- an array
    # cannot be written into a pin. Missing files are dropped rather than
    # raising: /Game/Audio is built from assets/generated/sounds, which a
    # checkout that has not run Scripts/make_creature_sounds.py does not have,
    # and the graph already guards an empty array.
    eas = _asset_sub()
    cdo = unreal.get_default_object(BEL.generated_class(bp))
    for var, wanted in ((VOICES_VAR, voices), (HIT_SOUNDS_VAR, hit_sounds)):
        found = [eas.load_asset(a) for a in wanted if eas.does_asset_exist(a)]
        cdo.set_editor_property(var, found)
        if len(found) != len(wanted):
            _log(f"note: {path} {var}: {len(found)} of {len(wanted)} sounds "
                 f"exist -- run Scripts/make_creature_sounds.py, then "
                 f"build_weapons_and_combat.py, to import the rest")

    # The flinches, same mechanism, but ALL SIX OR NONE: the reaction graph
    # indexes this array by position (three Fronts, then Back, Left, Right), so
    # a partial set is not a shorter list, it is the wrong clip for three of the
    # four directions -- and that failure is silent, where an empty array simply
    # means this creature does not flinch.
    clips = [eas.load_asset(a) for a in reactions if eas.does_asset_exist(a)]
    if len(clips) != len(reactions):
        _log(f"note: {path}: {len(clips)} of {len(reactions)} hit reactions "
             f"exist -- run Scripts/asset_pipeline/build_retarget.py. This "
             f"creature will not flinch.")
        clips = []
    cdo.set_editor_property(REACTIONS_VAR, clips)

    eas.save_loaded_asset(bp)
    _log(f"built {path} ({len(cdo.get_editor_property(REACTIONS_VAR))} hit "
         f"reactions, health {health:.0f}"
         + (f", melee {NPC_MELEE_DAMAGE:.0f} dmg / {NPC_MELEE_INTERVAL_S} s "
            f"inside {NPC_MELEE_RANGE_CM:.0f} cm" if melee else ", no melee")
         + f", {len(cdo.get_editor_property(VOICES_VAR))} voices)")
    return bp


# ─── The character ──────────────────────────────────────────────────────────

def build_npc_blueprint(ai_bp):
    """Create BP_ForestWanderer and point it at the AI controller."""
    bp = _create_blueprint(NPC_BP_PATH, unreal.Character)
    eas = _asset_sub()

    generated = BEL.generated_class(bp)
    cdo = unreal.get_default_object(generated)

    # Possession: the controller must take over wherever the NPC comes from.
    cdo.set_editor_property("ai_controller_class", BEL.generated_class(ai_bp))
    cdo.set_editor_property(
        "auto_possess_ai", unreal.AutoPossessAI.PLACED_IN_WORLD_OR_SPAWNED)

    # Body — the default creature. Each variant child overrides just this.
    mesh_comp = cdo.get_editor_property("mesh")
    mesh_path = _resolve(NPC_BASE_MESH, NPC_BASE_MESH_FALLBACK, "base mesh")
    skel = eas.load_asset(mesh_path)
    if skel:
        mesh_comp.set_editor_property("skeletal_mesh_asset", skel)
    else:
        unreal.log_error(f"[NPC] missing skeletal mesh {mesh_path}")

    # The wanderer wears the mesh's own materials. This array is written every
    # build, empty included, because this builder edits the Blueprint in place:
    # anything it does not write survives from the previous build. An abandoned
    # re-skin experiment left two material instances here that no code
    # referenced any more, and no amount of rebuilding cleared them -- the
    # builder simply never mentioned the array. Silence is not a default.
    previous = list(mesh_comp.get_editor_property("override_materials") or [])
    mesh_comp.set_editor_property("override_materials", [])
    if previous:
        names = ", ".join(m.get_name() if m else "None" for m in previous)
        unreal.log_warning(f"[NPC] cleared {len(previous)} material override(s): {names}")
    # ── Animation ────────────────────────────────────────────────────────────
    # ABP_Unarmed's locomotion gates on
    #   ShouldMove = (GroundSpeed > threshold) AND (GetCurrentAcceleration() != 0)
    # The acceleration half of that is supplied by use_acceleration_for_paths
    # below -- see the note there; it is the load-bearing setting for whether a
    # walk cycle plays at all, not anything in this block.
    #
    # animation_mode is already ANIMATION_BLUEPRINT once anim_class is set; it
    # is pinned here only because this builder updates blueprints in place and
    # should not inherit a stale AnimationSingleNode/AnimationCustomMode value.
    # _resolve hands back an object path; a Blueprint's runtime class is that
    # plus _C, which is what a component's anim_class actually wants.
    anim_bp = _resolve(NPC_ANIM_BP, NPC_ANIM_BP_FALLBACK, "anim blueprint")
    anim_class = unreal.load_class(None, f"{anim_bp}_C")
    if anim_class:
        _try_set(mesh_comp, "animation_mode",
                 unreal.AnimationMode.ANIMATION_BLUEPRINT)
        mesh_comp.set_editor_property("anim_class", anim_class)
    else:
        unreal.log_error(f"[NPC] missing anim blueprint {anim_bp}_C")

    # Keep the pose updating even when the NPC is off-screen, so it is mid-stride
    # when the player turns to look rather than snapping into a pose.
    _try_set(mesh_comp, "visibility_based_anim_tick_option",
             unreal.VisibilityBasedAnimTickOption.ALWAYS_TICK_POSE_AND_REFRESH_BONES)

    # Stock Character capsule is 88 cm half-height; drop the mesh to its feet.
    mesh_comp.set_editor_property(
        "relative_location", unreal.Vector(0, 0, MESH_RELATIVE_Z_CM))
    mesh_comp.set_editor_property(
        "relative_rotation",
        unreal.Rotator(pitch=0.0, yaw=MESH_RELATIVE_YAW_DEG, roll=0.0))

    movement = cdo.get_editor_property("character_movement")
    movement.set_editor_property("max_walk_speed", NPC_RUN_SPEED_CMS)
    # Turn in place smoothly instead of snapping to each new path segment.
    movement.set_editor_property(
        "rotation_rate", unreal.Rotator(pitch=0.0, yaw=180.0, roll=0.0))
    movement.set_editor_property("orient_rotation_to_movement", True)

    # MUST be True, and pinned explicitly rather than left to the engine default:
    # this builder updates blueprints IN PLACE, so any property it does not set
    # keeps whatever the asset already had -- deleting a line does not revert it.
    #
    # With it False, UCharacterMovementComponent::ApplyRequestedMove takes its
    # "just set velocity directly" branch and leaves Acceleration at exactly
    # zero every frame.  ABP_Unarmed gates locomotion on
    #   ShouldMove = GroundSpeed > threshold AND GetCurrentAcceleration() != 0
    # so the state machine stays in Idle and the NPC slides along in its idle
    # pose -- which is precisely the bug this was once (wrongly) blamed for.
    # With it True the branch guard is
    #   CurrentSpeedSq < Square(RequestedSpeed * 1.01f)
    # which still holds at cruising speed, so acceleration stays non-zero.
    #
    # A note here used to claim True was measured at 0.0 m over 91 s versus
    # 51.7 m with False.  That measurement predates the navmesh fix (section 7
    # of generate_forest_level.py): the level had zero nav tiles, so every
    # MoveTo failed and the NPC covered 0 m regardless of this flag.
    nav_props = movement.get_editor_property("nav_movement_properties")
    nav_props.set_editor_property("use_acceleration_for_paths", True)
    movement.set_editor_property("nav_movement_properties", nav_props)
    # A stock Character has use_controller_rotation_yaw = True, which forces the
    # pawn's yaw to the controller's every frame and fights the line above.
    # The third-person template turns it off for the same reason.
    cdo.set_editor_property("use_controller_rotation_yaw", False)

    if not BEL.compile_blueprint(bp):
        raise RuntimeError("BP_ForestWanderer failed to compile")
    eas.save_loaded_asset(bp)
    _log(f"built {NPC_BP_PATH} (run speed {NPC_RUN_SPEED_CMS} cm/s)")
    return bp


# ─── Creature variants ──────────────────────────────────────────────────────

def build_variant_blueprint(base_bp, variant):
    """A child of BP_ForestWanderer wearing one creature.

    Child Blueprints rather than a mesh swap at spawn time, and rather than one
    builder per creature.  Inheritance is what keeps the SHARED behaviour from
    drifting: the capsule, the melee numbers, the rotation rate and the whole
    chase loop are defined once on the parent and are not repeated here.

    Two stats are now per creature -- health and run speed, see
    WENDIGO_HEALTH_MULTIPLIER in npc_placement.py -- and they are both read
    from the variant record rather than written out here, so "a wendigo has
    three times the health" is stated in one place and applied in another.
    Everything else this function sets is an asset reference.

    It sets three of them rather than one, because a creature is its own
    skeleton: the mesh, the anim Blueprint retargeted against THAT skeleton,
    and an AI controller holding THAT skeleton's attack clip.  The melee
    numbers inside those controllers still come from one place -- they are
    generated by build_ai_controller_blueprint from the same constants.

    Adding a creature is therefore an entry in NPC_VARIANTS and nothing else.
    """
    eas = _asset_sub()
    parent_class = BEL.generated_class(base_bp)
    if not parent_class:
        raise RuntimeError("base NPC blueprint has no generated class")

    bp = _create_blueprint(variant.blueprint, parent_class)
    cdo = unreal.get_default_object(BEL.generated_class(bp))
    mesh_comp = cdo.get_editor_property("mesh")

    mesh = eas.load_asset(_mesh_object(variant.mesh))
    if mesh:
        mesh_comp.set_editor_property("skeletal_mesh_asset", mesh)
    else:
        # Not fatal: the child still inherits the parent's mesh, so the NPC
        # spawns and behaves correctly, it just wears the wrong creature.
        unreal.log_warning(
            f"[NPC] {variant.key}: {variant.mesh} is missing -- this variant "
            "will wear the base mesh")

    # The creature carries its own material instance (MI_Zombie01 and friends,
    # built by build_creature_materials.py), so an override here could only
    # ever be wrong.  Written explicitly rather than left alone because this
    # builder edits in place: an override set by a previous build survives
    # until something states otherwise.
    mesh_comp.set_editor_property("override_materials", [])

    # The anim BP is skeleton-bound, so the parent's cannot drive this mesh:
    # assigning a mismatched one leaves the creature in its bind pose, still
    # sliding around on its capsule, with nothing logged.
    anim_bp = _resolve(variant.anim_bp, NPC_ANIM_BP_FALLBACK,
                       f"{variant.key} anim blueprint")
    anim_class = unreal.load_class(None, f"{anim_bp}_C")
    if not anim_class:
        raise RuntimeError(f"[NPC] {variant.key}: {anim_bp} has no generated class")
    mesh_comp.set_editor_property("animation_mode",
                                  unreal.AnimationMode.ANIMATION_BLUEPRINT)
    mesh_comp.set_editor_property("anim_class", anim_class)

    # How fast this creature runs. The one stat that IS set on the pawn,
    # because MaxWalkSpeed lives on CharacterMovement -- a native subobject,
    # which a CDO does expose -- rather than on an added component. Health
    # cannot be set here for exactly that reason; see _author_stats_and_voice.
    #
    # The animation rate is scaled by the same factor at spawn time (see
    # generate_forest_level.py), not here, because it multiplies with the
    # per-instance gait variance and there is one place that composes the two.
    speed = _NPC_RUN_SPEED_CMS * variant.speed_scale
    move = cdo.get_editor_property("character_movement")
    move.set_editor_property("max_walk_speed", speed)
    got = move.get_editor_property("max_walk_speed")
    if abs(got - speed) > 1e-3:
        raise RuntimeError(
            f"{variant.key}: MaxWalkSpeed stayed at {got}, wanted {speed}")

    # Its own controller, because the attack clip inside it belongs to this
    # creature's skeleton and will not play on any other -- and because its
    # health and its voice are per creature too.
    ai_bp = build_ai_controller_blueprint(
        rebuild=True, path=variant.ai_blueprint,
        melee_anim=_resolve(variant.melee, NPC_MELEE_MONTAGE_FALLBACK,
                            f"{variant.key} melee clip"),
        health=variant.health, voices=variant.voices,
        reactions=variant.reactions)
    cdo.set_editor_property("ai_controller_class", BEL.generated_class(ai_bp))

    if not BEL.compile_blueprint(bp):
        raise RuntimeError(f"{variant.blueprint} failed to compile")
    eas.save_loaded_asset(bp)
    _log(f"built {variant.blueprint} "
         f"({mesh.get_name() if mesh else 'inherited mesh'}, "
         f"{anim_class.get_name()}, {ai_bp.get_name()}, "
         f"{variant.health:.0f} HP, {speed:.0f} cm/s)")
    return bp


# ─── Entry point ────────────────────────────────────────────────────────────

def ensure_npc_blueprints(force=False):
    """
    Build both NPC Blueprints, returning the character Blueprint.

    Idempotent: with ``force=False`` existing assets are reused, which keeps
    re-generating a level cheap and preserves any hand edits.
    """
    eas = _asset_sub()
    if not force and eas.does_asset_exist(NPC_BP_PATH) and eas.does_asset_exist(AI_BP_PATH):
        _log("NPC blueprints already exist — reusing")
        return eas.load_asset(NPC_BP_PATH)

    ai_bp = build_ai_controller_blueprint(rebuild=force)
    return build_npc_blueprint(ai_bp)


def ensure_npc_variants(force=False):
    """Every creature Blueprint the level can spawn, keyed by variant key.

    This is what a level generator wants; ``ensure_npc_blueprints`` builds the
    shared parent and is kept because the verify scripts address it by name.
    """
    base = ensure_npc_blueprints(force=force)
    eas = _asset_sub()
    out = {}
    for variant in NPC_VARIANTS:
        if not force and eas.does_asset_exist(variant.blueprint):
            out[variant.key] = eas.load_asset(variant.blueprint)
        else:
            out[variant.key] = build_variant_blueprint(base, variant)
    return out


if __name__ == "__main__":
    ensure_npc_variants(force=True)
    _log("done")
