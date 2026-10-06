"""verify.health -- BP_HealthComponent: health, spawn numbering, damage stamp, kill count,
dying, the corpse and the world-floor net.
"""

from combat.death import (
    CONTROLLER_RETIRE_SECONDS, CORPSE_SECONDS, DEATH_PAUSE_SECONDS,
)
from combat.game_state import (
    DAMAGED_BY_PLAYER_VAR, FELL_LOG_PREFIX, KILL_COUNT_VAR, LAST_DAMAGE_VAR,
    NEVER_DAMAGED, NPC_ID_VAR, PLAYER_DEAD_VAR, SPAWNED_AT_VAR,
    SPAWN_COUNT_VAR, SPAWN_LOG_PREFIX,
)
from combat.ragdoll import RAGDOLL_PROFILE
from combat.respawn import (
    RESPAWN_ATTEMPTS, RESPAWN_BAND, RESPAWN_DELAY, RESPAWN_DELAY_VAR,
    RESPAWN_LIFT, WORLD_FLOOR_Z,
)
from net.players_consts import POINT_PIN
from combat.verify.fixtures import (
    _montages, drain_writes, exec_reach, gm, h, health_bp, hg, wg,
)
from net.pause_checks import check_standalone_pause
from net.state_checks import check_state
from net.state_consts import PLAYER_STATE_BP_PATH
from combat.verify.common import (
    HEALTH_SETS,
    BEL, PIN, by_pins, check, graph, in_pins, load, num_pin, out_pins, pin_value,
    titled,
)


# ─── Health, death, respawn ──────────────────────────────────────────────────

def check_health_death_respawn():
    check("health starts at 100", abs(float(h.get_editor_property("Health")) - 100.0) < 1e-6)
    check("Health is a float, not an int",
          isinstance(h.get_editor_property("Health"), float),
          type(h.get_editor_property("Health")).__name__)
    check("the player's copy does not despawn at 0 HP (default is off)",
          h.get_editor_property("DespawnOnDeath") is False)

    check("death spawns a replacement", bool(by_pins(hg, "Class", "SpawnTransform")))
    check("respawn point comes from the navmesh",
          bool(by_pins(hg, "Origin", "Radius")))

    # The respawn has to land on walkable ground. The band point is built from the
    # PLAYER's Z, so on any terrain higher than the player it is underground -- and
    # a Character spawned underground falls through the world. These four checks
    # guard the shape that fixes it, each of which compiles fine when broken:
    projections = by_pins(hg, "Point", "QueryExtent")
    check("the respawn point is projected onto the navmesh",
          len(projections) == RESPAWN_ATTEMPTS,
          f"{len(projections)} ProjectPointToNavigation node(s), "
          f"expected {RESPAWN_ATTEMPTS}")
    # An unconnected struct pin reads as the ZERO vector: a search box with no
    # volume, which finds nothing and fails every projection.
    check("every projection has a real search box, not an empty struct pin",
          all(BEL.find_input_pin(n, "QueryExtent").list_connected_pins()
              for n in projections) and bool(projections))
    # The original bug: the location output was used and the bool ignored, so a
    # failed query spawned at the raw request point, at the player's own Z.
    check("every projection's success is branched on, not ignored",
          all(BEL.find_output_pin(n, "ReturnValue").list_connected_pins()
              for n in projections) and bool(projections))
    lifts = [n for n in by_pins(hg, "X", "Y", "Z")
             if pin_value(n, "Z") == str(RESPAWN_LIFT)]
    check("the spawn is lifted from the ground to the capsule's centre",
          bool(lifts), f"expected a MakeVector with Z = {RESPAWN_LIFT}")
    check("the chosen point is stored, so the random draw is evaluated once",
          "RespawnPoint" in {str(v) for v in BEL.list_member_variable_names(
              health_bp, False)})

    # The respawn band. A replacement wanderer has to keep the "75-100 m away" rule
    # the level generator spawns the pack under, or the rule holds only until the
    # first kill -- and it is measured from the *player*, not from a stored spawn
    # point, so that it survives the player walking across the map.
    ranges = {(pin_value(n, "Min"), pin_value(n, "Max")) for n in by_pins(hg, "Min", "Max")}
    want_band = (str(RESPAWN_BAND[0]), str(RESPAWN_BAND[1]))
    check("respawns land in the 75-100 m band", want_band in ranges,
          f"{sorted(ranges)} vs {want_band}")
    check("the bearing is random over a full circle", ("0.0", "360.0") in ranges,
          str(sorted(ranges)))
    check("the respawn is measured from the living player nearest the body "
          "(net/players.py), not player 0 or a stored spawn point",
          "SpawnOrigin" not in {str(v) for v in BEL.list_member_variable_names(
              health_bp, False)}
          and bool(by_pins(hg, POINT_PIN)) and not by_pins(hg, "PlayerIndex"))
    check_respawn_delay()
    tick = graph(health_bp).find_event_node("ReceiveTick")
    check("health ticks (otherwise nothing notices 0 HP)",
          tick is not None and bool(BEL.find_then_pin(tick).list_connected_pins()))


def _fed_by(node, pin, var):
    """Is ``node``'s input ``pin`` wired to a getter of the variable ``var``?"""
    return any(var in out_pins(PIN.get_owning_node(q))
               for q in PIN.list_connected_pins(BEL.find_input_pin(node, pin)))


def check_respawn_delay():
    # The replacement comes RESPAWN_DELAY seconds after the death, not with it.
    # The wait is a variable so a probe can shorten it (probe_respawn_delay.py).
    delay = h.get_editor_property(RESPAWN_DELAY_VAR)
    check(f"the respawn delay defaults to {RESPAWN_DELAY:.0f} s, as a float",
          isinstance(delay, float) and abs(delay - RESPAWN_DELAY) < 1e-6, repr(delay))
    check("10 s, as asked for", abs(RESPAWN_DELAY - 10.0) < 1e-6, f"{RESPAWN_DELAY}")
    waits = [n for n in by_pins(hg, "Duration")
             if _fed_by(n, "Duration", RESPAWN_DELAY_VAR)]
    check("one Delay waits RespawnDelay", len(waits) == 1, f"{len(waits)} node(s)")
    after = {n.get_path_name() for w in waits
             for n in exec_reach([BEL.find_then_pin(w)])}
    spawns = [n for n in by_pins(hg, "Class", "SpawnTransform")
              if _fed_by(n, "Class", "RespawnClass")]
    check("the replacement is spawned only after that wait",
          len(spawns) == 1 and all(n.get_path_name() in after for n in spawns),
          f"{len(spawns)} spawn(s) of RespawnClass")
    # Read after the wait, or the band is round where the player was at the kill.
    asks = by_pins(hg, "Point", "QueryExtent") + by_pins(hg, "Origin", "Radius")
    check("...and so is every respawn point chosen",
          bool(asks) and all(n.get_path_name() in after
                             for n in asks if "execute" in in_pins(n))
          and all(n.get_path_name() in after for n in hg
                  if RESPAWN_POINT_SETTER <= set(in_pins(n))),
          f"{len(asks)} nav queries")
    check("the corpse and the collapse do not wait for it",
          not any("InLifespan" in in_pins(n) or "ProfileName" in in_pins(n)
                  or "NewProfileName" in in_pins(n) for n in hg
                  if n.get_path_name() in after))


RESPAWN_POINT_SETTER = {"execute", "RespawnPoint"}


# ─── Spawn numbering ─────────────────────────────────────────────────────────

def check_spawn_numbering():
    # Every wanderer takes a number as it spawns and logs where it appeared; the HUD
    # draws that number beside its health bar. The pair is what makes a fall-through
    # reportable, so both halves are guarded here.
    check("the GameMode carries the spawn counter",
          SPAWN_COUNT_VAR in {str(v) for v in BEL.list_member_variable_names(gm, False)})
    check("the health component carries the wanderer's number",
          NPC_ID_VAR in {str(v) for v in BEL.list_member_variable_names(
              health_bp, False)})
    logs = [n for n in hg if "InString" in in_pins(n)]
    # Exactly three, all deliberate: the spawn log, the safety net's, and the
    # player's death. Any more is a probe left behind -- and this graph is the one
    # that gets instrumented whenever respawns misbehave.
    check("exactly three log lines in the health graph (spawn + fell + death)",
          len(logs) == 3, f"{len(logs)} PrintString(s)")
    # PrintWarning has no screen toggle (it is log-only by construction); the spawn
    # log is a PrintString and must be told not to paint over the HUD.
    screened = [n for n in logs if "bPrintToScreen" in in_pins(n)]
    check("the spawn and death logs are written to the log, not over the HUD",
          all(pin_value(n, "bPrintToScreen") in ("false", "False") for n in screened)
          and bool(screened))
    # Blueprint cannot log at Error severity at all, so the fall is reported at the
    # highest it has: PrintWarning takes InString and nothing else.
    check("the fall is reported at warning severity, not a plain print",
          any("bPrintToScreen" not in in_pins(n) for n in logs))
    check("the wanderer remembers where it was spawned",
          SPAWNED_AT_VAR in {str(v) for v in BEL.list_member_variable_names(
              health_bp, False)})
    # Both lines quote the stored SpawnedAt, so they cannot disagree.

    reads = [n for n in hg if SPAWNED_AT_VAR in out_pins(n)]
    check("the fall report names the spawn location too", len(reads) == 2,
          f"{len(reads)} SpawnedAt read(s), expected 2 (spawn log + fall report)")
    prefixes = {pin_value(n, "A") for n in by_pins(hg, "A", "B")}
    for label, want in (("spawn", SPAWN_LOG_PREFIX), ("fall", FELL_LOG_PREFIX)):
        check(f"{label} log lines are greppable", want in prefixes,
              f"expected {want!r}")


# ─── The damage stamp ────────────────────────────────────────────────────────

def check_damage_stamp():
    health_vars = {str(v) for v in BEL.list_member_variable_names(health_bp, False)}
    check("the health component records when it was last hurt",
          LAST_DAMAGE_VAR in health_vars, str(sorted(health_vars)))
    check("nothing starts the game looking recently hurt",
          abs(float(h.get_editor_property(LAST_DAMAGE_VAR)) - NEVER_DAMAGED) < 1e-6,
          str(h.get_editor_property(LAST_DAMAGE_VAR)))
    check("LastDamageTime is a float, not an int",
          isinstance(h.get_editor_property(LAST_DAMAGE_VAR), float),
          type(h.get_editor_property(LAST_DAMAGE_VAR)).__name__)
    # Both are TakeHit's now, in the component's own graph, on the server
    # (verify/damage.py reads the event); the weapon's graph writes neither.
    check("a blow stamps the time it landed",
          len(titled(hg, f"Set {LAST_DAMAGE_VAR}")) == 1
          and not titled(wg, f"Set {LAST_DAMAGE_VAR}"),
          "the HUD floats a wanderer's bar off this")
    check("a blow also records who did it",
          len(titled(hg, f"Set {DAMAGED_BY_PLAYER_VAR}")) == 1
          and not titled(wg, f"Set {DAMAGED_BY_PLAYER_VAR}"))
    check("nothing is born blamed on the player",
          h.get_editor_property(DAMAGED_BY_PLAYER_VAR) is False)


# ─── The kill counter ────────────────────────────────────────────────────────

def check_kill_counter():
    # Where state lives (net/state_checks.py): both are one player's, on
    # their PlayerState, where their own machine's HUD can read them.
    check_state(check)
    ps_vars = {str(v) for v in BEL.list_member_variable_names(
        load(PLAYER_STATE_BP_PATH), False)}
    check("the PlayerState carries the kill counter", KILL_COUNT_VAR in ps_vars,
          str(sorted(ps_vars)))
    check("the PlayerState carries the player-death flag", PLAYER_DEAD_VAR in ps_vars)
    check("a death adds one to the kill counter",
          bool(titled(hg, f"SET {KILL_COUNT_VAR}"))
          or bool(titled(hg, f"Set {KILL_COUNT_VAR}")))
    # The guard that stops the safety net inflating the score: a wanderer that fell
    # through the world dies down this very same path, and nobody shot it.
    blamed = [n for n in hg if DAMAGED_BY_PLAYER_VAR in out_pins(n)]
    check("only a death the player caused is counted", len(blamed) == 1,
          f"{len(blamed)} reads of {DAMAGED_BY_PLAYER_VAR} in the death path")
    if blamed:
        driven = [PIN.get_owning_node(q) for q in
                  BEL.find_output_pin(blamed[0],
                                      DAMAGED_BY_PLAYER_VAR).list_connected_pins()]
        check("and a Branch is what guards on it, not an AND",
              [n.get_class().get_name() for n in driven] == ["K2Node_IfThenElse"],
              str([n.get_class().get_name() for n in driven]))


# ─── Dying: the ragdoll, the corpse, and the menu ────────────────────────────

def check_dying():
    # The player used to play MM_Death_Front_01 into FullBodySlot and the wanderers
    # were destroyed on the frame they died. Both are gone: Epic's six MM_Death_*
    # clips are one-second staggers that END STANDING (measured off the assets:
    # pelvis 83-88 cm, both feet on the floor, 1.5-2 m of backwards travel), so the
    # montage blended out and put the player back on his feet a second before the
    # pause -- which is exactly what "he gets up right away" was.

    ragdolls = titled(hg, "SetAllBodiesSimulatePhysics")
    check("dying is a ragdoll, not a clip", len(ragdolls) == 1, str(len(ragdolls)))
    if ragdolls:
        check("...simulating, not un-simulating",
              pin_value(ragdolls[0], "bNewSimulate") in ("true", "True"),
              pin_value(ragdolls[0], "bNewSimulate"))
    # SetSimulatePhysics would put the ONE root body into simulation -- a
    # creature-shaped brick toppling over. It is not even a UFunction on
    # SkeletalMeshComponent, so this is a ban on reaching for the PrimitiveComponent
    # one on the mesh pin.
    check("and every body in the physics asset, not just the root",
          not titled(hg, "SetSimulatePhysics"))
    # The montage count and its slot are checked in the flinch section above; what
    # matters here is that the death path itself plays nothing.
    profiles = titled(hg, "SetCollisionProfileName")
    check("the ragdoll gets a collision profile that lets it hit the ground",
          len(profiles) == 1, str(len(profiles)))
    if profiles:
        check(f"...the {RAGDOLL_PROFILE} profile, which also ignores Pawn",
              pin_value(profiles[0], "InCollisionProfileName") == RAGDOLL_PROFILE,
              pin_value(profiles[0], "InCollisionProfileName"))
    # The capsule -- not the mesh -- is what blocks the player and what the pellets
    # trace against (see make_shootable), so switching it off is both halves of "a
    # corpse is not in the way".
    capsules = titled(hg, "SetCollisionEnabled")
    check("the capsule stops colliding, so a corpse is neither an obstacle nor a "
          "target", len(capsules) == 1, str(len(capsules)))
    if capsules:
        check("...switched off entirely",
              pin_value(capsules[0], "NewType").endswith("NoCollision"),
              pin_value(capsules[0], "NewType"))
    check("the body stops where it fell",
          len(titled(hg, "DisableMovement")) == 1,
          "without it CharacterMovement drags the capsule and the mesh with it")

    # One collapse, reached from both arms of the death branch. Two would be two
    # places for "what dying looks like" to drift apart.
    casts = [n for n in hg if n.get_class().get_name() == "K2Node_DynamicCast"
             and "AsCharacter" in {q.replace(" ", "") for q in out_pins(n)}]
    # There are TWO of these now and they are not interchangeable: the flinch also
    # has to reach the owner's mesh to find an AnimInstance. Told apart by following
    # the montage's own self pin back up -- montage <- GetAnimInstance <- Get Mesh
    # <- cast -- rather than by position or by exec-link count, either of which
    # would quietly pick the wrong one the next time the graph moves.
    _flinch_cast = None
    if _montages:
        _walk = _montages[0]
        for _ in range(3):
            _up = PIN.list_connected_pins(BEL.find_input_pin(_walk, "self"))
            if not _up:
                break
            _walk = PIN.get_owning_node(_up[0])
        _flinch_cast = _walk if _walk in casts else None
    check("the flinch finds its body through its own CastToCharacter",
          _flinch_cast is not None)
    collapse_casts = [n for n in casts if n is not _flinch_cast]
    check("the player and the wanderers collapse through the same nodes",
          len(collapse_casts) == 1, f"{len(collapse_casts)} collapse CastToCharacter(s) "
          f"of {len(casts)} in the graph")
    if collapse_casts:
        feeders = PIN.list_connected_pins(BEL.find_input_pin(collapse_casts[0], "execute"))
        check("...and both arms really do reach it", len(feeders) == 2,
              f"{len(feeders)} exec link(s) into the collapse")


# ─── The corpse, and when it goes away ───────────────────────────────────────

def check_corpse():
    def _fed_by(node):
        return [str(BEL.get_node_title(PIN.get_owning_node(q))).replace("\n", " ")
                for q in PIN.list_connected_pins(BEL.find_input_pin(node, "self"))]

    lifespans = titled(hg, "SetLifeSpan")
    bodies = [n for n in lifespans if _fed_by(n) == ["GetOwner"]]
    brains = [n for n in lifespans if _fed_by(n) == ["GetController"]]
    check("a killed wanderer leaves a corpse instead of vanishing",
          len(bodies) == 1, str([_fed_by(n) for n in lifespans]))
    if bodies:
        check(f"the corpse despawns after {CORPSE_SECONDS:.0f} s",
              abs((num_pin(bodies[0], "InLifespan") or -1.0)
                  - CORPSE_SECONDS) < 1e-3,
              pin_value(bodies[0], "InLifespan"))
    check("60 s, as asked for", abs(CORPSE_SECONDS - 60.0) < 1e-6,
          f"{CORPSE_SECONDS}")
    # The chase, the melee and the growls are one self-re-entering loop on the AI
    # controller. The loop now stops itself for a Dead pawn (npc/corpse.py); this
    # is the cleanup. It has to be a lifespan: K2_DestroyActor on a controller is
    # an empty override in the engine, and this check used to pass on a Destroy
    # node that never destroyed anything.
    check("a corpse's AI controller is retired by lifespan (a Blueprint "
          "DestroyActor on a controller is a no-op)",
          len(brains) == 1 and not titled(hg, "Destroy Actor"),
          f"{len(brains)} controller lifespan(s), "
          f"{len(titled(hg, 'Destroy Actor'))} Destroy Actor node(s)")
    if brains:
        got = num_pin(brains[0], "InLifespan")
        check(f"...after {CONTROLLER_RETIRE_SECONDS} s, and not 0 (which means forever)",
              got is not None and got > 0.0
              and abs(got - CONTROLLER_RETIRE_SECONDS) < 1e-3,
              pin_value(brains[0], "InLifespan"))

    pauses = by_pins(hg, "bPaused")
    check("death pauses the game", len(pauses) == 1, str(len(pauses)))
    if pauses:
        check("...paused, not unpaused",
              pin_value(pauses[0], "bPaused") in ("true", "True"),
              pin_value(pauses[0], "bPaused"))
    check_standalone_pause(check, hg, "death")
    # The pause stops physics too, so this is also how long the ragdoll gets to
    # settle; pausing early freezes the player mid-topple.
    check("the pause waits for the body to land",
          any(abs((num_pin(n, "Duration") or -1.0) - DEATH_PAUSE_SECONDS) < 1e-3
              for n in by_pins(hg, "Duration")),
          f"expected a {DEATH_PAUSE_SECONDS}s Delay before the pause")
    check("the death flag is raised for the HUD to draw the menu from",
          bool(titled(hg, f"SET {PLAYER_DEAD_VAR}"))
          or bool(titled(hg, f"Set {PLAYER_DEAD_VAR}")))

    # Three writers: the safety net's, the debuff drain's (combat/debuff_drain.py)
    # and TakeHit's (combat/damage.py).
    # Anything else writing Health inside the component's own graph is a probe
    # that was left behind -- which is exactly how the 60 s corpse timer was
    # measured, on a compressed value, with a clock forcing the death.
    writes = [n for n in hg if str(BEL.get_node_title(n)).replace("\n", " ") in HEALTH_SETS]
    drains = [n for n in writes if n in drain_writes]
    check("only the world-floor net, the debuff drain and TakeHit write Health from "
          "inside the component",
          len(writes) == 3 and len(drains) == 1,
          f"{len(writes)} Set Health node(s), {len(drains)} of them the drain's")


# ─── Walking off the edge of the world ───────────────────────────────────────

def check_world_edge():
    # The navmesh is a disc of radius 85 m and the terrain a 200 m square, but the
    # terrain does eventually END -- and a Character in freefall never stops. The
    # player used to fall for the rest of the session with nothing noticing, because
    # "still falling" and "standing still" look identical to everything watching.
    #
    # The fix reuses the NPC safety net rather than adding a KillZ or a teleport:
    # below WORLD_FLOOR_Z, write Health to 0 and let the death path that already
    # exists open the restart menu. What had to change is that the net used to be
    # AND-ed with DespawnOnDeath -- NPCs only -- and that gate moved inward so it
    # guards only the log line, which quotes an NpcId the player does not have.

    floors = [n for n in hg if num_pin(n, "B") == WORLD_FLOOR_Z]
    check(f"something compares a height against {WORLD_FLOOR_Z:.0f} cm",
          len(floors) == 1, f"{len(floors)} comparisons")
    if floors:
        gates = [PIN.get_owning_node(q) for q in
                 BEL.find_output_pin(floors[0], "ReturnValue").list_connected_pins()]
        # THE REGRESSION THIS EXISTS TO CATCH: an AND here means the test is once
        # again "under the world AND is an NPC", and the player falls forever.
        check("the world floor is branched on directly, not AND-ed with a "
              "\"...and is an NPC\" term",
              [g.get_class().get_name() for g in gates] == ["K2Node_IfThenElse"],
              str([str(BEL.get_node_title(g)) for g in gates]))

    # Two writes of Health = 0 would mean two floors; one, reached from both arms
    # of the "is this worth a log line" branch, is the shape that catches both the
    # wanderer and the player.
    # A LITERAL zero: a wired pin (the debuff drain's) also reads back as 0.
    zeroes = [n for n in hg
              if str(BEL.get_node_title(n)).replace("\n", " ") in HEALTH_SETS
              and num_pin(n, "Health") == 0.0
              and not BEL.find_input_pin(n, "Health").list_connected_pins()]
    check("exactly one node writes the fall off as death", len(zeroes) == 1,
          f"{len(zeroes)} writes of Health = 0")
    if zeroes:
        feeders = [PIN.get_owning_node(q) for q in
                   PIN.list_connected_pins(BEL.find_input_pin(zeroes[0], "execute"))]
        check("...and BOTH arms of the report branch reach it -- the reported "
              "wanderer and the unreported player",
              len(feeders) == 2, f"reached from {len(feeders)} exec pin(s)")
        kinds = sorted(f.get_class().get_name() for f in feeders)
        check("...one of them straight from a Branch (the player: no log line)",
              "K2Node_IfThenElse" in kinds, str(kinds))
    # The log line stays wanderer-only: it quotes a number and a spawn point.
    check("the fall report is still gated on DespawnOnDeath",
          any("DespawnOnDeath" in out_pins(n) for n in hg))
    check("...and still names the wanderer and where it was put",
          bool(titled(hg, "PrintWarning")) or bool(titled(hg, "Print Warning")),
          "the fall report is the one line Blueprint can raise above Display")


def run():
    check_health_death_respawn()
    check_spawn_numbering()
    check_damage_stamp()
    check_kill_counter()
    check_dying()
    check_corpse()
    check_world_edge()
