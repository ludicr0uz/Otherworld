"""The weapon component's Tick: polls every key and calls into the
aim/fire/inventory/sprint/recoil/ammo fragments in order.

The keys are the local player's alone (local.py). Of the Tick's four parts
the view and the stance keys (``_author_wc_tick``'s first half) and the
trigger and the action keys (``_author_actions``) run only where the owner is
locally controlled; the pose (the second half) and the slots and the equip
(``_author_upkeep``) run on every machine's copy.
"""

from uebp.graph import _connect, _node, _pin, _set, else_, out, then
from combat.weapon_component.accuracy import _author_accuracy
from combat.tuning import BIND_VARS
from combat.weapon_component.ads import _author_ads
from combat.weapon_component.aim import _author_resolve_aim
from combat.weapon_component.ammo import _author_dry_fire, _author_reload
from combat.weapon_component.block import _author_block
from combat.weapon_component.breath import _author_hold_breath
from combat.weapon_component.carry import _author_carry
from combat.weapon_component.common import _prop
from combat.weapon_component.consume import (
    _author_trigger_latch, _author_use_gate,
)
from combat.weapon_component.dead import _author_dead_gate
from combat.weapon_component.firing import _author_fire
from combat.weapon_component.light import _author_light_press
from combat.weapon_component.look import _author_local_carry, _author_look_mirror
from combat.weapon_component.local import (
    _author_local_gate, _author_local_only, local_pc)
from combat.weapon_component.knife import (
    _author_knife_press, _author_knife_swing,
)
from combat.weapon_component.inventory import (
    _author_drop, _author_equip,
)
from combat.weapon_component.interact import _author_interact
from combat.weapon_component.pose_weights import _author_pose_weights
from combat.weapon_component.punch import _author_punch
from combat.weapon_component.ready_pose import (
    _author_lowered_pose_edge, _author_ready_pose_keepalive,
)
from combat.weapon_component.recoil import (
    _author_recoil_kick, _author_recoil_recovery,
)
from combat.weapon_component.shot_noise import _author_shot_noise
from combat.weapon_component.slot_moves import _author_slot_keys, _author_slot_serve
from combat.weapon_component.slot_sync import _author_slot_sync
from combat.weapon_component.head_hide import _author_head_hide
from combat.weapon_component.sight_pitch import _author_sight_pitch
from combat.weapon_component.sights import _author_sight_camera
from combat.weapon_component.sprint import _author_sprint
from Sound.sound_world import _author_breath
from combat.weapon_component.support_hand import _author_support_hand
from combat.weapon_component.sway import _author_sight_sway
from combat.weapon_component.stance import _author_stance
from combat.weapon_component.steady import _author_steady
from combat.weapon_component.use import _author_use
from combat.weapon_component.wear import _author_take_off, _author_wear_gate
from combat.weapon_component.wear_drag import _author_wear_request
from combat.weapon_component.drop_request import _author_drop_request
from combat.weapon_component.save_exit import _author_save_exit
from combat.weapon_component.throw import _author_throw, _author_throw_key
from uebp.nodes.actor import FN_GET_OWNER, FN_IS_KEY_DOWN, FN_WAS_PRESSED
from uebp.nodes.math import FN_AND, FN_GE_FF, FN_GREATER_II, FN_NOT, FN_OR
from uebp.nodes.system import FN_IS_VALID, FN_TIME_SECONDS
from combat import item_vars as IV
from combat.weapon_component import vars as WV

# A probe's stand-in for the fire key's press: no key can be injected into a
# headless game (probes/probe_dead_no_actions.py). False in every real game.
FIRE_FORCED_VAR = "FireForced"


def _author_wc_tick(ed, tick):
    """Five polled keys and a refresh, chained so each block rejoins the next.

    There is no Sequence node here: an exec *input* accepts any number of links,
    so every block's exit and its guard branch's False pin both run into the
    next guard. That keeps the chain flat and means a block can be inserted or
    removed without re-fanning a Sequence's pins.

    Refresh runs last, after the slot sync, so a slot key, drop or pick-up
    earlier in the same frame is already applied when it does.
    """
    # This machine's controller of the owner: read only behind the local gate.
    pc_out = local_pc(ed)

    owner = _node(ed, FN_GET_OWNER)
    owner_out = out(owner)

    held_get = ed.add_get_member_variable_node(WV.Held)
    held = out(held_get, WV.Held)
    armed = _node(ed, FN_IS_VALID)
    _connect(held, _pin(armed, "Object"))
    armed_out = out(armed)

    # One Get per bind, reused by every poll below -- an output pin takes any
    # number of links. The Key pins are DRIVEN rather than set to a literal,
    # which is the whole of rebinding: the HUD writes these variables each
    # frame from the player's save, and a literal cannot be written to.
    key_pins = {}
    for name, _default in BIND_VARS:
        getter = ed.add_get_member_variable_node(name)
        key_pins[name] = out(getter, name)

    def pressed(var):
        n = _node(ed, FN_WAS_PRESSED)
        _connect(pc_out, _pin(n, "self"))
        _connect(key_pins[var], _pin(n, "Key"))
        return out(n)

    def both(a, b):
        n = _node(ed, FN_AND)
        _connect(a, _pin(n, "A"))
        _connect(b, _pin(n, "B"))
        return out(n)

    # --- dead? ---------------------------------------------------------------
    # Before everything, the passive fragments included: a dead owner gets
    # none of this Tick (dead.py).
    alive = _author_dead_gate(ed, owner_out, held, armed_out, then(tick))

    # --- whose keys? (local.py) ----------------------------------------------
    # Everything down to the body's pose is the local player's: the view, the
    # keys held. On any other machine's copy the Tick goes straight there.
    alive, remote = _author_local_gate(ed, owner_out, alive)

    # --- aim -----------------------------------------------------------------
    # First, and unconditionally: the reticle has to be right on the frames
    # where nothing is fired, which is nearly all of them. It also leaves
    # AimPoint and the muzzle position sitting there for the fire block to use.
    # --- recoil recovery -----------------------------------------------------
    # First of all, because it moves the view: the aim trace below has to be
    # taken after this frame's give-back rather than one frame behind it.
    recoil_exits = _author_recoil_recovery(ed, tick, pc_out, alive)

    aim_exits, muzzle = _author_resolve_aim(ed, held, pc_out, recoil_exits)

    # --- sprint --------------------------------------------------------------
    # Before the trigger, because the trigger reads Sprinting: polled in the
    # other order, a shot would be allowed on the frame the sprint started.
    sprint_exits = _author_sprint(ed, pc_out, owner_out, key_pins["KeySprint"], aim_exits)
    # The run key held with no stamina left is heard (Sound/sound_world.py).
    sprint_exits = _author_breath(ed, owner_out, sprint_exits)

    # --- block ---------------------------------------------------------------
    # After sprint (it reads Sprinting), before the trigger (which refuses
    # while Blocking). block.py says why the hit itself is resolved elsewhere.
    sprint_exits = (_author_block(ed, pc_out, key_pins["KeyBlock"], sprint_exits),)

    # --- crouch and prone ----------------------------------------------------
    # After sprint too, which stands the player up. stance.py owns the rest.
    sprint_exits = _author_stance(ed, pc_out, owner_out, key_pins, sprint_exits)

    # --- the use key (use.py) --------------------------------------------------
    # After the sprint, which it reads; before the aim, which reads Using to
    # know the sights key is not aiming this frame.
    sprint_exits, sights_key = _author_use(
        ed, pc_out, owner_out, held, armed_out, key_pins["KeySights"],
        sprint_exits)

    # --- aim down the sights -------------------------------------------------
    # After the sprint block, which writes Sprinting, and before the trigger,
    # which the cone width now depends on: polled in any other order the zoom
    # and the spread would disagree by a frame.
    ads_exits = _author_ads(ed, tick, pc_out, owner_out, held, armed_out,
                            key_pins, sights_key, sprint_exits)

    # --- and where the camera is, down the sights ----------------------------
    # After the aim state it reads (SightAiming). The camera trace at the top
    # of the next frame then starts from wherever this puts the camera.
    ads_exits = _author_sight_camera(ed, tick, owner_out, held, armed_out, ads_exits)

    # --- and the player's own head leaves the sight picture (head_hide.py) ----
    # After SightSeat is written, which it reads.
    ads_exits = _author_head_hide(ed, ads_exits)

    # --- and the aim sways, down the sights ----------------------------------
    # After SightBlend is written, which scales it; before the pitch below,
    # which reads the view the sway has just turned.
    # The held gun's sway rate and the held breath first (breath.py), which
    # the sway reads; after SightAiming is written, which the breath reads.
    ads_exits = (_author_hold_breath(ed, tick, pc_out, held, armed_out,
                                     key_pins["KeyHoldBreath"], ads_exits),)
    ads_exits = _author_sight_sway(ed, tick, pc_out, ads_exits)

    # --- and the body pitches with the view, down the sights -----------------
    # After SightBlend is written, which scales it.
    ads_exits = _author_sight_pitch(ed, pc_out, ads_exits)

    # --- from here on every machine's copy runs: the pose follows state -------
    # A copy that is not its player's own writes that state first, from what
    # was replicated (look.py).
    ads_exits = tuple(ads_exits) + tuple(_author_look_mirror(ed, tick, owner_out, remote))

    # --- and the body takes the stance and the guard -------------------------
    # After both are written (Stance, Blocking), which set its weights.
    ads_exits = _author_pose_weights(ed, tick, held, armed_out, ads_exits)

    # --- and the left hand holds the gun, down the sights (support_hand.py) ---
    # After SightBlend and HeldTwoHanded are written, which it copies.
    ads_exits = _author_support_hand(ed, ads_exits)

    # --- and how true the gun shoots from here -------------------------------
    # After the stance and the aim state it reads, before the trigger and the
    # kick that use it. accuracy.py owns the formula.
    ads_exits = _author_accuracy(ed, held, armed_out, ads_exits)

    # --- the gun is lowered or raised (carry.py) ------------------------------
    # After Sprinting, Aiming and Blocking are written, which it reads.
    # Where the keys are; and there the look is reported (look.py).
    ads_exits = _author_local_carry(
        ed, ads_exits, lambda execs: _author_carry(ed, held, armed_out, execs))

    # --- and the pose follows it (ready_pose.py) ------------------------------
    pose_exits = _author_lowered_pose_edge(ed, ads_exits)

    # --- and down the sights a hit plays no flinch (steady.py) ----------------
    # After SightBlend is written; before the equip, which it can ask for.
    pose_exits = _author_steady(ed, owner_out, pose_exits)

    # --- and the pose survives being shot ------------------------------------
    # After the pose edge, because that block is what starts and stops the
    # pose deliberately, and this one only restores what something else took
    # away. See _author_ready_pose_keepalive: a hit reaction stops the ready
    # pose as a side effect of the montage group, and without this the player
    # fights the rest of the session with the gun in the locomotion pose.
    pose_exits = _author_ready_pose_keepalive(ed, pose_exits)

    # --- the trigger and the action keys: the local player's (local.py) -------
    local, remote = _author_local_only(ed, pose_exits)
    flight_exits = _author_actions(
        ed, pc_out, owner_out, held, armed_out, key_pins, muzzle, pressed, both, (local,))
    _author_upkeep(ed, tuple(flight_exits) + (remote,))


def _author_actions(ed, pc_out, owner_out, held, armed_out, key_pins, muzzle,
                    pressed, both, pose_exits):
    """The trigger and every action key: fire, eat, slash, strike, punch,
    reload, the slot keys, drop, interact, throw, and the HUD's requests.
    Local input only. Returns the execs the upkeep carries on from."""
    # --- fire ----------------------------------------------------------------
    # Three conditions, and "not sprinting" is the new one: the weapon is being
    # used to run with, not to aim with. Note this AND is safe to fold together
    # -- every input is a plain bool read, with no chain behind it that could be
    # pulled by the half that should not have run (unlike the NPC melee gate).
    #
    # The trigger is polled BOTH ways, and the two are OR'd here rather than
    # chosen between. Which one a given weapon honours is settled further in,
    # behind this gate, because the answer is a property of Held -- and this
    # condition is evaluated on every frame, including the frames where nothing
    # is equipped. Reading Automatic here would be an Accessed None per frame
    # for as long as the player's hands are empty.
    #
    # So the outer gate asks the question that is answerable without a weapon:
    # is the player touching the trigger at all? A tap is also a hold on the
    # frame it happens, so the OR is not strictly necessary for the automatics
    # -- it is there so that a semi-automatic still opens the gate on the tap
    # frame even if IsInputKeyDown were ever to disagree, and so that the two
    # reads that actually decide are the same two pins the weapon is asked
    # about below.
    steady = _node(ed, FN_NOT)
    _connect(out(ed.add_get_member_variable_node(WV.Sprinting), WV.Sprinting), _pin(steady, "A"))

    # Guarding is not shooting: a separate NOT, so the Sprinting read the
    # verifier walks keeps its own NOT.
    guarded = _node(ed, FN_NOT)
    _connect(out(ed.add_get_member_variable_node(WV.Blocking), WV.Blocking), _pin(guarded, "A"))

    tapped = _node(ed, FN_OR)
    _connect(pressed("KeyFire"), _pin(tapped, "A"))
    _connect(out(ed.add_get_member_variable_node(FIRE_FORCED_VAR), FIRE_FORCED_VAR), _pin(tapped, "B"))
    tap = out(tapped)
    holding = _node(ed, FN_IS_KEY_DOWN)
    _connect(pc_out, _pin(holding, "self"))
    _connect(key_pins["KeyFire"], _pin(holding, "Key"))
    holding_out = out(holding)
    touching = _node(ed, FN_OR)
    _connect(tap, _pin(touching, "A"))
    _connect(holding_out, _pin(touching, "B"))

    # A press that ate an item is spent until the key comes up: without this
    # the weapon equipped in the item's place fires on the same press.
    armed_exit, unspent = _author_trigger_latch(ed, holding_out, pose_exits)

    # With the throw key down the click is the throw's (throw.py), not a shot.
    throw_wants, no_throw = _author_throw_key(ed, pc_out, key_pins["KeyThrow"])
    fire_gate = ed.add_branch_node()
    _connect(both(both(both(out(touching),
                            armed_out),
                       both(out(steady),
                            out(guarded))),
                  both(unspent, no_throw)),
             _pin(fire_gate, "Condition"))
    _connect(armed_exit, _pin(fire_gate, "execute"))

    # Ammunition and the cooldown are a SECOND branch inside the first, not two
    # more terms folded into its condition, and that nesting is the whole
    # reason this reads the way it does. Both tests have to read properties off
    # Held, and the condition of the outer gate is pulled on every frame --
    # including the frames where nothing is equipped at all. A pure Get with a
    # null self is an "Accessed None" per frame forever. Behind the gate, Held
    # has already been checked valid.
    loaded, loaded_n = _prop(ed, IV.Loaded, held)
    rounds = _node(ed, FN_GREATER_II)
    _connect(loaded, _pin(rounds, "A"))
    _set(rounds, "B", 0)
    limited, limited_n = _prop(ed, IV.UsesAmmo, held)
    unlimited = _node(ed, FN_NOT)
    _connect(limited, _pin(unlimited, "A"))
    # OR, so an item without ammunition never consults a magazine it does not have.
    has_ammo = _node(ed, FN_OR)
    _connect(out(unlimited), _pin(has_ammo, "A"))
    _connect(out(rounds), _pin(has_ammo, "B"))

    when, when_n = _prop(ed, IV.NextFireTime, held)
    right_now = _node(ed, FN_TIME_SECONDS)
    cooled = _node(ed, FN_GE_FF)
    _connect(out(right_now), _pin(cooled, "A"))
    _connect(when, _pin(cooled, "B"))

    # Held trigger, or tapped trigger? Now that Held is known valid, the
    # weapon can be asked. An automatic accepts either; everything else
    # accepts only the tap, which is what makes one click one shot on the
    # shotgun even though the button is still down on the following frame.
    auto_pin, auto_n = _prop(ed, IV.Automatic, held)
    spraying = _node(ed, FN_AND)
    _connect(holding_out, _pin(spraying, "A"))
    _connect(auto_pin, _pin(spraying, "B"))
    trigger = _node(ed, FN_OR)
    _connect(tap, _pin(trigger, "A"))
    _connect(out(spraying), _pin(trigger, "B"))
    trigger_out = out(trigger)

    ready = _node(ed, FN_AND)
    _connect(out(has_ammo), _pin(ready, "A"))
    _connect(out(cooled), _pin(ready, "B"))
    allowed = _node(ed, FN_AND)
    _connect(out(ready), _pin(allowed, "A"))
    _connect(trigger_out, _pin(allowed, "B"))
    ready_gate = ed.add_branch_node()
    _connect(out(allowed), _pin(ready_gate, "Condition"))

    # --- or is it something to eat (consume.py), to swing (knife.py), or to
    # strike (light.py)? ---------------------------------------------------------
    light_in, struck = _author_light_press(ed, held, owner_out, tap, _pin(ready_gate, "execute"))
    knife_in, slash_pressed = _author_knife_press(ed, held, tap, light_in)
    used, untapped = _author_use_gate(
        ed, held, owner_out, tap, then(fire_gate),
        knife_in, _author_wear_gate)

    ed.add_comment_to_nodes(
        "The trigger is being touched, the weapon is out and the player is not "
        "sprinting -- now, can it actually fire? A weapon with no ammunition "
        "rule passes on the first half; every weapon waits out its own "
        "FireInterval on the second; and an automatic is the only kind that "
        "counts a held button as a pull. Nested inside the first gate rather "
        "than folded into it, because every one of these reads a property off "
        "Held.",
        [loaded_n, rounds, limited_n, unlimited, has_ammo, when_n, right_now,
         cooled, auto_n, spraying, trigger, ready, allowed, ready_gate])

    # The kick lands before the round is spent, which costs nothing and reads
    # in the right order. It cannot bend the shot that caused it: the pellets
    # fly down the AimPoint resolved at the top of this frame.
    kicked = _author_recoil_kick(ed, held, pc_out, then(ready_gate))
    fired, flew = _author_fire(ed, held, muzzle, kicked)
    # ...and the wanderers hear it. After the pellets, so a shot is heard
    # whether or not it hit anything.
    after_fire = _author_shot_noise(ed, held, muzzle, flew, fired)

    # --- the click, when the gate said no ------------------------------------
    dry_exits = _author_dry_fire(
        ed, held, muzzle,
        out(has_ammo),
        out(cooled), tap,
        else_(ready_gate))

    # --- or, with empty hands, a punch (punch.py) ------------------------------
    # Off the fire gate's False arm, which is where every empty-handed frame
    # goes: the gate needs IsValid(Held), and the punch needs it false.
    punch_exits = _author_punch(
        ed, tap, armed_out, out(steady),
        out(guarded), unspent,
        (else_(fire_gate),))

    # --- reload --------------------------------------------------------------
    # Shares its key with the death menu's "try again", and that is safe rather
    # than lucky: Event Tick does not run while the game is paused, so this
    # graph is not listening on any frame the menu is on screen. (The HUD's
    # DrawHUD is; it is renderer-driven, which is why the menu can poll a key at
    # all.)
    # --- the knife's slash, once queued (knife.py) ----------------------------
    # Every frame, whatever is held: the swing and the blow run on after the
    # press, and the blow lands even if the knife was put away in between.
    slash_exits = _author_knife_swing(
        ed, (after_fire, *used, untapped) + slash_pressed + struck + dry_exits
        + punch_exits)

    reload_gate = ed.add_branch_node()
    _connect(both(pressed("KeyReload"), armed_out), _pin(reload_gate, "Condition"))
    for exit_pin in slash_exits:
        _connect(exit_pin, _pin(reload_gate, "execute"))
    reload_exits = _author_reload(ed, held, then(reload_gate))

    # --- the slots' keys (slot_moves.py): 1-9 and Q ask for a slot ---------
    slot_exits = _author_slot_keys(ed, pc_out, pressed("KeySwitch"),
                                   reload_exits + (else_(reload_gate),))

    # --- drop ----------------------------------------------------------------
    drop_gate = ed.add_branch_node()
    _connect(both(pressed("KeyDrop"), armed_out), _pin(drop_gate, "Condition"))
    for exit_pin in slot_exits:
        _connect(exit_pin, _pin(drop_gate, "execute"))
    after_drop = _author_drop(ed, held, owner_out, then(drop_gate))
    drop_dirty = ed.add_set_member_variable_node(WV.NeedsRefresh)
    _set(drop_dirty, WV.NeedsRefresh, True)
    _connect(after_drop, _pin(drop_dirty, "execute"))

    # --- interact (interact.py): an item in reach is picked up ---------------
    picked, not_picked = _author_interact(
        ed, owner_out, pressed("KeyInteract"),
        (then(drop_dirty), else_(drop_gate)))
    pick_dirty = ed.add_set_member_variable_node(WV.NeedsRefresh)
    _set(pick_dirty, WV.NeedsRefresh, True)
    for exit_pin in picked:
        _connect(exit_pin, _pin(pick_dirty, "execute"))

    # --- throw (throw.py) ------------------------------------------------------
    # After interact and before the refresh, which re-equips the emptied hand
    # on the frame of the throw, as it does after a drop.
    flight_exits = _author_throw(
        ed, pc_out, owner_out, held, armed_out, throw_wants, tap,
        (then(pick_dirty),) + not_picked)

    # --- take a garment off (wear.py): the I panel's request ---------------
    flight_exits = _author_take_off(ed, flight_exits)
    # --- and a slot's garment dragged onto the worn grid (wear_drag.py) -----
    flight_exits = _author_wear_request(ed, flight_exits)
    # --- and an item dragged out of the inventory (drop_request.py) ---------
    flight_exits = _author_drop_request(ed, flight_exits)

    return flight_exits


def _author_upkeep(ed, flight_exits):
    """What follows from state on every copy: the slots served and placed,
    then the equip, if anything asked for one."""
    # --- save and exit's countdown (save_exit.py) ----------------------------
    flight_exits = _author_save_exit(ed, flight_exits)

    # --- the slots: requests and drags served, then every item placed --------
    # (slot_moves.py, slot_sync.py): last, so the equip below follows them.
    flight_exits = _author_slot_serve(ed, flight_exits)
    flight_exits = _author_slot_sync(ed, flight_exits)

    # --- refresh -------------------------------------------------------------
    dirty_get = ed.add_get_member_variable_node(WV.NeedsRefresh)
    refresh_gate = ed.add_branch_node()
    _connect(out(dirty_get, WV.NeedsRefresh), _pin(refresh_gate, "Condition"))
    for exit_pin in flight_exits:
        _connect(exit_pin, _pin(refresh_gate, "execute"))
    settle = ed.add_set_member_variable_node(WV.NeedsRefresh)
    _set(settle, WV.NeedsRefresh, False)
    _connect(then(refresh_gate), _pin(settle, "execute"))
    _author_equip(ed, then(settle))
