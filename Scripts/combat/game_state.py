"""The GameMode's shared variables (spawn/kill counters, PlayerDead, debug
mode) and the per-health-component variable names every graph agrees on,
plus ensure_game_mode_vars() which declares them.
"""

import unreal

from combat.graph import (
    BEL, BGE, _assets, _declare, _float_type, _log, _struct_type,
)
from combat.difficulty import DIFFICULTY_VAR
from combat.paths import GAME_MODE_BP_PATH


# --- debug mode --------------------------------------------------------------
# One flag on the GameMode, toggled from the graphics menu, that turns the
# developer overlays on and off: the pellet tracers drawn from the muzzle, the
# wanderer's number beside its health bar and its sight cone
# (npc/sight_cone.py). Off by default -- they are all instrumentation, and
# instrumentation is not what the game looks like.
DEBUG_MODE_VAR = "DebugMode"

# --- combat trace ------------------------------------------------------------
# A second developer switch on the GameMode, and a log rather than an overlay:
# with it on, every wanderer's swing that lands writes one COMBAT_TRACE_PREFIX
# line naming the attacker by number, where it stood, and where its target
# stood. Off by default (COMBAT_TRACE_DEFAULT in tuning.py); flipped at runtime
# from the console with `ke * CombatTraceOn` / `ke * CombatTraceOff`, which
# call the two custom events combat/combat_trace.py authors on the GameMode.
COMBAT_TRACE_VAR = "CombatTrace"
COMBAT_TRACE_ON_EVENT = "CombatTraceOn"
COMBAT_TRACE_OFF_EVENT = "CombatTraceOff"
COMBAT_TRACE_PREFIX = "[COMBAT-TRACE] "

# Pellet tracers drawn in the world for this many seconds, in debug mode only.
# They are the only way to see *where* a shot went -- sound and blood tell you a
# shot happened and that it connected, but not that it missed high -- which is
# exactly why they are instrumentation and not part of the game.
#
# Drawn with an explicit DrawDebugLine rather than with the trace node's own
# DrawDebugType: that pin is an enum literal, and an enum pin cannot be driven
# by a variable, so "sometimes" is not expressible there at all.
#
# Long enough to walk up to a line and look along it. The tracer
# (weapon_component/tracer.py) stops where the pellet did, with a point there:
# TRACER_HIT_COLOR when it connected with anything, TRACER_MISS_COLOR when it
# ran out the weapon's range.
TRACE_DEBUG_SECONDS = 3.0
TRACER_THICKNESS = 2.0
TRACER_POINT_SIZE = 12.0
TRACER_HIT_COLOR = "(R=1.000000,G=0.150000,B=0.050000,A=1.000000)"
TRACER_MISS_COLOR = "(R=0.300000,G=0.800000,B=1.000000,A=1.000000)"

# Every wanderer gets a number, handed out in spawn order and shown beside its
# health bar, so a fall-through seen on screen can be matched to the exact
# spawn location in the log. The counter has to live somewhere world-scoped and
# Blueprints have no statics -- the GameMode is the project's existing wiring
# point (it already carries HUDClass), one instance per session, and it outlives
# every wanderer.
SPAWN_COUNT_VAR = "NpcSpawnCount"
NPC_ID_VAR = "NpcId"
# Two more numbers on the same GameMode, for the same reason: they have to
# outlive every wanderer and every one of the player's own components.
# NpcKillCount is what the HUD counts in the corner and what the death menu
# quotes; PlayerDead is the one flag the menu is drawn from.
KILL_COUNT_VAR = "NpcKillCount"
PLAYER_DEAD_VAR = "PlayerDead"
# The gun drop's two random streams (combat/gun_drop.py) and whether they have
# been seeded this session. On the GameMode because a stream only means
# anything if it outlives the draws: kept on each wanderer's own health
# component, every kill would be the first draw of a fresh stream.
GUN_ROLL_STREAM_VAR = "GunDropRollStream"
GUN_PICK_STREAM_VAR = "GunDropPickStream"
GUN_STREAMS_SEEDED_VAR = "GunDropSeeded"
# Set on a health component by whatever hurt it. The HUD shows a wanderer's bar
# only for a few seconds after LastDamageTime, and only a death with
# DamagedByPlayer true counts as a kill -- the safety net writes Health to 0 for
# a wanderer that fell through the world, and that is not something anyone shot.
LAST_DAMAGE_VAR = "LastDamageTime"
DAMAGED_BY_PLAYER_VAR = "DamagedByPlayer"
# Far enough in the past that nothing is "recently damaged" at level start.
NEVER_DAMAGED = -1000.0
SPAWN_LOG_PREFIX = "[NPC-SPAWN] #"
# Flagged ERROR in the text because Blueprint cannot emit an Error-severity log
# line at all: PrintWarning is the highest the Kismet library offers (there is
# no PrintStringWithSeverity / LogError node), and a real UE_LOG(Error) would
# need a C++ module, which this project does not have. Warning severity at
# least colours it in the Output Log and trips the editor's warning filter; the
# token makes it greppable as an error regardless.
FELL_LOG_PREFIX = "[NPC-FELL] ERROR #"
# The player's own death, written once. Without it a headless -game run has no
# way to say whether the death path ran at all: the menu it opens is on a canvas
# nobody is looking at, and a paused game and a quiet game look identical in a
# log. The score goes in the line because it is the one number worth having
# afterwards.
DEAD_LOG_PREFIX = "[PLAYER-DEAD] killed with "
SPAWNED_AT_VAR = "SpawnedAt"
# The last noise the player made, for the wanderers to hear. One record,
# world-scoped for the same reason as the counters above: the emitters (the
# weapon component, the footstep component) and the listeners (every
# wanderer's AI controller) share nothing else. Written by combat/noise.py,
# read by Scripts/npc/senses.py. Where, when, how far it carries all round,
# and -- for a gunshot -- the direction and reach of the louder cone down the
# barrel, with the cosine of its half-angle. An all-round noise leaves the
# cone reach at 0, which no listener can be inside.
NOISE_TIME_VAR = "NoiseTime"
NOISE_LOCATION_VAR = "NoiseLocation"
NOISE_RANGE_VAR = "NoiseRange"
NOISE_DIRECTION_VAR = "NoiseDirection"
NOISE_CONE_RANGE_VAR = "NoiseConeRange"
NOISE_CONE_COS_VAR = "NoiseConeCos"
NOISE_FLOAT_VARS = (NOISE_TIME_VAR, NOISE_RANGE_VAR, NOISE_CONE_RANGE_VAR,
                    NOISE_CONE_COS_VAR)
NOISE_VECTOR_VARS = (NOISE_LOCATION_VAR, NOISE_DIRECTION_VAR)
# Debug mode's damage readout, drawn at each impact for as long as the tracer.
DAMAGE_TEXT_COLOR = "(R=1.000000,G=0.850000,B=0.100000,A=1.000000)"


# ─── BP_HealthComponent ──────────────────────────────────────────────────────

def ensure_game_mode_vars():
    """Put the world-scoped counters and the death flag on the GameMode.

    Variables only -- no graph. The GameMode is chosen because Blueprints have
    no statics and each of these has to be one value per session, shared by
    every wanderer's health component and read by the HUD:

        NpcSpawnCount  the next number to hand a wanderer, so the log and the
                       floating bars agree on who is who;
        NpcKillCount   what the corner of the HUD shows and what the death menu
                       quotes as the final score;
        PlayerDead     the one flag the death menu is drawn from;
        DebugMode      whether the developer overlays are on. Here rather than
                       on the HUD that toggles it because the *weapon
                       component* is the other thing that reads it, and a HUD
                       variable is not reachable from a component.
        CombatTrace    whether wanderers log each landed swing (see
                       COMBAT_TRACE_VAR). Its default is written by
                       combat_trace.build_combat_trace_switch().
        Noise*         the last noise the player made (see NOISE_TIME_VAR),
                       written by whatever made it, heard by every wanderer.
        GunDrop*       the gun drop's roll and pick streams and their
                       seeded-this-session flag (see GUN_ROLL_STREAM_VAR).
        Difficulty     the settings screen's difficulty, copied here by the
                       HUD every DrawHUD so gameplay (GA_ConsumeItem) reads it
                       without loading the save. Its int default, 0, is EASY.

    All three outlive every actor that touches them -- the player's own health
    component is destroyed with the player, so the score cannot live there.

    Declared here rather than in build_graphics_menu.py (which owns the other
    edit to this asset, HUDClass) because they are part of the NPC and player
    life cycle, and this file is what writes them.
    """
    eas = _assets()
    bp = eas.load_asset(GAME_MODE_BP_PATH)
    if not bp:
        raise RuntimeError(f"could not load {GAME_MODE_BP_PATH}")
    ed = BGE.get_graph_editor_by_name(bp, "EventGraph")
    if not ed:
        raise RuntimeError(f"{GAME_MODE_BP_PATH} has no EventGraph")
    for name in (SPAWN_COUNT_VAR, KILL_COUNT_VAR, DIFFICULTY_VAR):
        _declare(ed, name, BEL.get_basic_type_by_name("int"))
    for name in (PLAYER_DEAD_VAR, DEBUG_MODE_VAR, COMBAT_TRACE_VAR,
                 GUN_STREAMS_SEEDED_VAR):
        _declare(ed, name, BEL.get_basic_type_by_name("bool"))
    for name in NOISE_FLOAT_VARS:
        _declare(ed, name, _float_type())
    for name in NOISE_VECTOR_VARS:
        _declare(ed, name, _struct_type(unreal.Vector.static_struct()))
    for name in (GUN_ROLL_STREAM_VAR, GUN_PICK_STREAM_VAR):
        _declare(ed, name, _struct_type(unreal.RandomStream.static_struct()))
    if not BEL.compile_blueprint(bp):
        raise RuntimeError("BP_ThirdPersonGameMode failed to compile")
    eas.save_loaded_asset(bp)
    _log(f"{GAME_MODE_BP_PATH}: {SPAWN_COUNT_VAR}, {KILL_COUNT_VAR}, "
         f"{PLAYER_DEAD_VAR}, {DEBUG_MODE_VAR}, {COMBAT_TRACE_VAR}, "
         f"{DIFFICULTY_VAR}, the noise record and the gun-drop streams ready")
    return bp
