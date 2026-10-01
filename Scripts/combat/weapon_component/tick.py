"""The weapon component's Tick: polls every key and calls into the
aim/fire/inventory/sprint/recoil/ammo fragments in order.
"""

from combat.graph import BEL, _at, _connect, _node, _pin, _set
from combat.weapon_component.accuracy import _author_accuracy
from combat.nodes import (
    FN_ADD_II, FN_AND, FN_ARR_LEN, FN_GET_OWNER, FN_GET_PC, FN_GE_FF,
    FN_GREATER_II, FN_IS_KEY_DOWN, FN_IS_VALID, FN_LESS_II, FN_MOD_II,
    FN_NOT, FN_OR, FN_TIME_SECONDS, FN_WAS_PRESSED,
)
from combat.tuning import BIND_VARS, SWITCH_KEY
from combat.weapon_component.ads import _author_ads
from combat.weapon_component.aim import _author_resolve_aim
from combat.weapon_component.ammo import _author_dry_fire, _author_reload
from combat.weapon_component.block import _author_block
from combat.weapon_component.carry import _author_carry
from combat.weapon_component.common import _prop
from combat.weapon_component.consume import (
    _author_trigger_latch, _author_use_gate,
)
from combat.weapon_component.dead import _author_dead_gate
from combat.weapon_component.firing import _author_fire
from combat.weapon_component.light import _author_light_press
from combat.weapon_component.knife import (
    _author_knife_press, _author_knife_swing,
)
from combat.weapon_component.inventory import (
    _author_drop, _author_equip,
)
from combat.weapon_component.pickup import _author_pickup
from combat.weapon_component.pose_weights import _author_pose_weights
from combat.weapon_component.punch import _author_punch
from combat.weapon_component.ready_pose import (
    _author_lowered_pose_edge, _author_ready_pose_keepalive,
)
from combat.weapon_component.recoil import (
    _author_recoil_kick, _author_recoil_recovery,
)
from combat.weapon_component.shot_noise import _author_shot_noise
from combat.weapon_component.head_hide import _author_head_hide
from combat.weapon_component.sight_pitch import _author_sight_pitch
from combat.weapon_component.sights import _author_sight_camera
from combat.weapon_component.sprint import _author_sprint
from combat.weapon_component.sway import _author_sight_sway
from combat.weapon_component.stance import _author_stance
from combat.weapon_component.steady import _author_steady
from combat.weapon_component.throw import _author_throw, _author_throw_key

# A probe's stand-in for the fire key's press: no key can be injected into a
# headless game (probes/probe_dead_no_actions.py). False in every real game.
FIRE_FORCED_VAR = "FireForced"


def _author_wc_tick(ed, tick):
    """Five polled keys and a refresh, chained so each block rejoins the next.

    There is no Sequence node here: an exec *input* accepts any number of links,
    so every block's exit and its guard branch's False pin both run into the
    next guard. That keeps the chain flat and means a block can be inserted or
    removed without re-fanning a Sequence's pins.

    Refresh runs last so a switch, drop or pick-up earlier in the same frame is
    already applied when it does.
    """
    pc = _at(_node(ed, FN_GET_PC), 240, 260)
    _set(pc, "PlayerIndex", 0)
    pc_out = _pin(pc, "ReturnValue", is_input=False)

    owner = _at(_node(ed, FN_GET_OWNER), 240, 400)
    owner_out = _pin(owner, "ReturnValue", is_input=False)

    held_get = _at(ed.add_get_member_variable_node("Held"), 240, 520)
    held = _pin(held_get, "Held", is_input=False)
    armed = _at(_node(ed, FN_IS_VALID), 480, 520)
    _connect(held, _pin(armed, "Object"))
    armed_out = _pin(armed, "ReturnValue", is_input=False)

    # One Get per bind, reused by every poll below -- an output pin takes any
    # number of links. The Key pins are DRIVEN rather than set to a literal,
    # which is the whole of rebinding: the HUD writes these variables each
    # frame from the player's save, and a literal cannot be written to.
    key_pins = {}
    for i, (name, _default) in enumerate(BIND_VARS):
        getter = _at(ed.add_get_member_variable_node(name), -40, 260 + i * 120)
        key_pins[name] = _pin(getter, name, is_input=False)

    def pressed(var, y):
        n = _at(_node(ed, FN_WAS_PRESSED), 480, y)
        _connect(pc_out, _pin(n, "self"))
        _connect(key_pins[var], _pin(n, "Key"))
        return _pin(n, "ReturnValue", is_input=False)

    def both(a, b, y):
        n = _at(_node(ed, FN_AND), 760, y)
        _connect(a, _pin(n, "A"))
        _connect(b, _pin(n, "B"))
        return _pin(n, "ReturnValue", is_input=False)

    # --- dead? ---------------------------------------------------------------
    # Before everything, the passive fragments included: a dead owner gets
    # none of this Tick (dead.py).
    alive = _author_dead_gate(ed, owner_out, held, armed_out,
                              BEL.find_then_pin(tick), 1040, -5200)

    # --- aim -----------------------------------------------------------------
    # First, and unconditionally: the reticle has to be right on the frames
    # where nothing is fired, which is nearly all of them. It also leaves
    # AimPoint and the muzzle position sitting there for the fire block to use.
    # --- recoil recovery -----------------------------------------------------
    # First of all, because it moves the view: the aim trace below has to be
    # taken after this frame's give-back rather than one frame behind it.
    recoil_exits = _author_recoil_recovery(ed, tick, pc_out, alive, 1040, -3600)

    aim_exits, muzzle = _author_resolve_aim(ed, held, recoil_exits,
                                            1040, -2400)

    # --- sprint --------------------------------------------------------------
    # Before the trigger, because the trigger reads Sprinting: polled in the
    # other order, a shot would be allowed on the frame the sprint started.
    sprint_exits = _author_sprint(ed, tick, pc_out, owner_out,
                                  key_pins["KeySprint"], aim_exits,
                                  1040, -1400)

    # --- block ---------------------------------------------------------------
    # After sprint (it reads Sprinting), before the trigger (which refuses
    # while Blocking). block.py says why the hit itself is resolved elsewhere.
    sprint_exits = (_author_block(ed, pc_out, key_pins["KeyBlock"],
                                  sprint_exits, 3700, -1400),)

    # --- crouch and prone ----------------------------------------------------
    # After sprint too, which stands the player up. stance.py owns the rest.
    sprint_exits = _author_stance(ed, pc_out, owner_out, key_pins,
                                  sprint_exits, 1040, -9000)

    # --- aim down the sights -------------------------------------------------
    # After the sprint block, which writes Sprinting, and before the trigger,
    # which the cone width now depends on: polled in any other order the zoom
    # and the spread would disagree by a frame.
    ads_exits = _author_ads(ed, tick, pc_out, owner_out, held, armed_out,
                            key_pins, sprint_exits, 1040, -700)

    # --- and where the camera is, down the sights ----------------------------
    # After the aim state it reads (SightAiming). The camera trace at the top
    # of the next frame then starts from wherever this puts the camera.
    ads_exits = _author_sight_camera(ed, tick, owner_out, held, armed_out,
                                     ads_exits, 8400, -700)

    # --- and the player's own head leaves the sight picture (head_hide.py) ----
    # After SightSeat is written, which it reads.
    ads_exits = _author_head_hide(ed, ads_exits, 11200, 2600)

    # --- and the aim sways, down the sights ----------------------------------
    # After SightBlend is written, which scales it; before the pitch below,
    # which reads the view the sway has just turned.
    ads_exits = _author_sight_sway(ed, tick, pc_out, ads_exits, 8400, 1200)

    # --- and the body pitches with the view, down the sights -----------------
    # After SightBlend is written, which scales it.
    ads_exits = _author_sight_pitch(ed, pc_out, ads_exits, 11200, -700)

    # --- and the body takes the stance and the guard -------------------------
    # After both are written (Stance, Blocking), which set its weights.
    ads_exits = _author_pose_weights(ed, tick, held, armed_out, ads_exits,
                                     12600, -700)

    # --- and how true the gun shoots from here -------------------------------
    # After the stance and the aim state it reads, before the trigger and the
    # kick that use it. accuracy.py owns the formula.
    ads_exits = _author_accuracy(ed, held, armed_out, ads_exits, 16800, -700)

    # --- the gun is lowered or raised (carry.py) ------------------------------
    # After Sprinting, Aiming and Blocking are written, which it reads.
    ads_exits = _author_carry(ed, held, armed_out, ads_exits, 19600, -700)

    # --- and the pose follows it (ready_pose.py) ------------------------------
    pose_exits = _author_lowered_pose_edge(ed, ads_exits)

    # --- and down the sights a hit plays no flinch (steady.py) ----------------
    # After SightBlend is written; before the equip, which it can ask for.
    pose_exits = _author_steady(ed, owner_out, pose_exits, 3200, 1600)

    # --- and the pose survives being shot ------------------------------------
    # After the pose edge, because that block is what starts and stops the
    # pose deliberately, and this one only restores what something else took
    # away. See _author_ready_pose_keepalive: a hit reaction stops the ready
    # pose as a side effect of the montage group, and without this the player
    # fights the rest of the session with the gun in the locomotion pose.
    pose_exits = _author_ready_pose_keepalive(ed, held, pose_exits, 240, 1400)

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
    steady = _at(_node(ed, FN_NOT), 760, 760)
    _connect(_pin(_at(ed.add_get_member_variable_node("Sprinting"), 480, 760),
                  "Sprinting", is_input=False), _pin(steady, "A"))

    # Guarding is not shooting: a separate NOT, so the Sprinting read the
    # verifier walks keeps its own NOT.
    guarded = _at(_node(ed, FN_NOT), 760, 680)
    _connect(_pin(_at(ed.add_get_member_variable_node("Blocking"), 480, 680),
                  "Blocking", is_input=False), _pin(guarded, "A"))

    tapped = _at(_node(ed, FN_OR), 760, 500)
    _connect(pressed("KeyFire", 600), _pin(tapped, "A"))
    _connect(_pin(_at(ed.add_get_member_variable_node(FIRE_FORCED_VAR), 480, 500),
                  FIRE_FORCED_VAR, is_input=False), _pin(tapped, "B"))
    tap = _pin(tapped, "ReturnValue", is_input=False)
    holding = _at(_node(ed, FN_IS_KEY_DOWN), 480, 860)
    _connect(pc_out, _pin(holding, "self"))
    _connect(key_pins["KeyFire"], _pin(holding, "Key"))
    holding_out = _pin(holding, "ReturnValue", is_input=False)
    touching = _at(_node(ed, FN_OR), 760, 580)
    _connect(tap, _pin(touching, "A"))
    _connect(holding_out, _pin(touching, "B"))

    # A press that ate an item is spent until the key comes up: without this
    # the weapon equipped in the item's place fires on the same press.
    armed_exit, unspent = _author_trigger_latch(ed, holding_out, pose_exits,
                                                240, -200)

    # With the throw key down the click is the throw's (throw.py), not a shot.
    throw_wants, no_throw = _author_throw_key(ed, pc_out, key_pins["KeyThrow"],
                                              240, 13000)
    fire_gate = _at(ed.add_branch_node(), 1040, 0)
    _connect(both(both(both(_pin(touching, "ReturnValue", is_input=False),
                            armed_out, 640),
                       both(_pin(steady, "ReturnValue", is_input=False),
                            _pin(guarded, "ReturnValue", is_input=False), 680),
                       700),
                  both(unspent, no_throw, 820), 760),
             _pin(fire_gate, "Condition"))
    _connect(armed_exit, _pin(fire_gate, "execute"))

    # Ammunition and the cooldown are a SECOND branch inside the first, not two
    # more terms folded into its condition, and that nesting is the whole
    # reason this reads the way it does. Both tests have to read properties off
    # Held, and the condition of the outer gate is pulled on every frame --
    # including the frames where nothing is equipped at all. A pure Get with a
    # null self is an "Accessed None" per frame forever. Behind the gate, Held
    # has already been checked valid.
    loaded, loaded_n = _prop(ed, "Loaded", held, 1240, 300)
    rounds = _at(_node(ed, FN_GREATER_II), 1480, 300)
    _connect(loaded, _pin(rounds, "A"))
    _set(rounds, "B", 0)
    limited, limited_n = _prop(ed, "UsesAmmo", held, 1240, 420)
    unlimited = _at(_node(ed, FN_NOT), 1480, 420)
    _connect(limited, _pin(unlimited, "A"))
    # OR, so an item without ammunition never consults a magazine it does not have.
    has_ammo = _at(_node(ed, FN_OR), 1720, 360)
    _connect(_pin(unlimited, "ReturnValue", is_input=False), _pin(has_ammo, "A"))
    _connect(_pin(rounds, "ReturnValue", is_input=False), _pin(has_ammo, "B"))

    when, when_n = _prop(ed, "NextFireTime", held, 1240, 560)
    right_now = _at(_node(ed, FN_TIME_SECONDS), 1240, 680)
    cooled = _at(_node(ed, FN_GE_FF), 1480, 560)
    _connect(_pin(right_now, "ReturnValue", is_input=False), _pin(cooled, "A"))
    _connect(when, _pin(cooled, "B"))

    # Held trigger, or tapped trigger? Now that Held is known valid, the
    # weapon can be asked. An automatic accepts either; everything else
    # accepts only the tap, which is what makes one click one shot on the
    # shotgun even though the button is still down on the following frame.
    auto_pin, auto_n = _prop(ed, "Automatic", held, 1240, 820)
    spraying = _at(_node(ed, FN_AND), 1480, 820)
    _connect(holding_out, _pin(spraying, "A"))
    _connect(auto_pin, _pin(spraying, "B"))
    trigger = _at(_node(ed, FN_OR), 1720, 760)
    _connect(tap, _pin(trigger, "A"))
    _connect(_pin(spraying, "ReturnValue", is_input=False), _pin(trigger, "B"))
    trigger_out = _pin(trigger, "ReturnValue", is_input=False)

    ready = _at(_node(ed, FN_AND), 1960, 420)
    _connect(_pin(has_ammo, "ReturnValue", is_input=False), _pin(ready, "A"))
    _connect(_pin(cooled, "ReturnValue", is_input=False), _pin(ready, "B"))
    allowed = _at(_node(ed, FN_AND), 1960, 600)
    _connect(_pin(ready, "ReturnValue", is_input=False), _pin(allowed, "A"))
    _connect(trigger_out, _pin(allowed, "B"))
    ready_gate = _at(ed.add_branch_node(), 2200, 0)
    _connect(_pin(allowed, "ReturnValue", is_input=False),
             _pin(ready_gate, "Condition"))

    # --- or is it something to eat (consume.py), to swing (knife.py), or to
    # strike (light.py)? ---------------------------------------------------------
    light_in, struck = _author_light_press(
        ed, held, owner_out, tap, _pin(ready_gate, "execute"), 1240, -1300)
    knife_in, slash_pressed = _author_knife_press(
        ed, held, tap, light_in, 1240, -800)
    consumed, untapped = _author_use_gate(
        ed, held, owner_out, tap, BEL.find_then_pin(fire_gate),
        knife_in, 1240, -300)

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
    kicked = _author_recoil_kick(ed, held, pc_out,
                                 BEL.find_then_pin(ready_gate), 6800, -1400)
    fired, flew = _author_fire(ed, held, muzzle, kicked, 2700, 0)
    # ...and the wanderers hear it. After the pellets, so a shot is heard
    # whether or not it hit anything.
    after_fire = _author_shot_noise(ed, held, muzzle, flew, fired, 6800, -2600)

    # --- the click, when the gate said no ------------------------------------
    dry_exits = _author_dry_fire(
        ed, held, muzzle,
        _pin(has_ammo, "ReturnValue", is_input=False),
        _pin(cooled, "ReturnValue", is_input=False), tap,
        BEL.find_else_pin(ready_gate), 2200, 1100)

    # --- or, with empty hands, a punch (punch.py) ------------------------------
    # Off the fire gate's False arm, which is where every empty-handed frame
    # goes: the gate needs IsValid(Held), and the punch needs it false.
    punch_exits = _author_punch(
        ed, tap, armed_out, _pin(steady, "ReturnValue", is_input=False),
        _pin(guarded, "ReturnValue", is_input=False), unspent,
        (BEL.find_else_pin(fire_gate),), 1040, 9800)

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
        ed, (after_fire, consumed, untapped) + slash_pressed + struck + dry_exits
        + punch_exits,
        1040, 11000)

    reload_gate = _at(ed.add_branch_node(), 1040, 7200)
    _connect(both(pressed("KeyReload", 7360), armed_out, 7300),
             _pin(reload_gate, "Condition"))
    for exit_pin in slash_exits:
        _connect(exit_pin, _pin(reload_gate, "execute"))
    reload_exits = _author_reload(ed, held, BEL.find_then_pin(reload_gate),
                                  1400, 7200)

    # --- switch --------------------------------------------------------------
    switch_gate = _at(ed.add_branch_node(), 1040, 1400)
    inv = _at(ed.add_get_member_variable_node("Inventory"), 240, 1560)
    count = _at(_node(ed, FN_ARR_LEN), 480, 1560)
    _connect(_pin(inv, "Inventory", is_input=False), _pin(count, "TargetArray"))
    count_out = _pin(count, "ReturnValue", is_input=False)
    any_held = _at(_node(ed, FN_LESS_II), 760, 1680)
    _set(any_held, "A", 0)
    _connect(count_out, _pin(any_held, "B"))
    _connect(both(pressed("KeySwitch", 1560), _pin(any_held, "ReturnValue", is_input=False),
                  1620), _pin(switch_gate, "Condition"))
    for exit_pin in reload_exits + (BEL.find_else_pin(reload_gate),):
        _connect(exit_pin, _pin(switch_gate, "execute"))

    idx = _at(ed.add_get_member_variable_node("EquippedIndex"), 1300, 1600)
    step = _at(_node(ed, FN_ADD_II), 1540, 1600)
    _connect(_pin(idx, "EquippedIndex", is_input=False), _pin(step, "A"))
    _set(step, "B", 1)
    wrap = _at(_node(ed, FN_MOD_II), 1780, 1600)
    _connect(_pin(step, "ReturnValue", is_input=False), _pin(wrap, "A"))
    _connect(count_out, _pin(wrap, "B"))
    to = _at(ed.add_set_member_variable_node("EquippedIndex"), 2020, 1400)
    _connect(_pin(wrap, "ReturnValue", is_input=False), _pin(to, "EquippedIndex"))
    _connect(BEL.find_then_pin(switch_gate), _pin(to, "execute"))
    switch_dirty = _at(ed.add_set_member_variable_node("NeedsRefresh"), 2280, 1400)
    _set(switch_dirty, "NeedsRefresh", "true")
    _connect(BEL.find_then_pin(to), _pin(switch_dirty, "execute"))

    ed.add_comment_to_nodes(
        f"{SWITCH_KEY} cycles: (index + 1) mod count, so it wraps and works for "
        "any number of carried weapons. 1/2/3 and M would have been the obvious "
        "keys but they already belong to the graphics menu.",
        [inv, count, any_held, idx, step, wrap, to, switch_dirty, switch_gate])

    # --- drop ----------------------------------------------------------------
    drop_gate = _at(ed.add_branch_node(), 1040, 2200)
    _connect(both(pressed("KeyDrop", 2360), armed_out, 2300), _pin(drop_gate, "Condition"))
    _connect(BEL.find_then_pin(switch_dirty), _pin(drop_gate, "execute"))
    _connect(BEL.find_else_pin(switch_gate), _pin(drop_gate, "execute"))
    after_drop = _author_drop(ed, held, owner_out, BEL.find_then_pin(drop_gate),
                              1400, 2200)
    drop_dirty = _at(ed.add_set_member_variable_node("NeedsRefresh"), 4700, 2200)
    _set(drop_dirty, "NeedsRefresh", "true")
    _connect(after_drop, _pin(drop_dirty, "execute"))

    # --- pick up (pickup.py) -------------------------------------------------
    picked, not_picked = _author_pickup(
        ed, owner_out, pressed("KeyPickup", 3560),
        (BEL.find_then_pin(drop_dirty), BEL.find_else_pin(drop_gate)),
        1040, 3400)
    pick_dirty = _at(ed.add_set_member_variable_node("NeedsRefresh"), 4900, 3400)
    _set(pick_dirty, "NeedsRefresh", "true")
    for exit_pin in picked:
        _connect(exit_pin, _pin(pick_dirty, "execute"))

    # --- throw (throw.py) ------------------------------------------------------
    # After pick-up and before the refresh, which re-equips the emptied hand
    # on the frame of the throw, as it does after a drop.
    flight_exits = _author_throw(
        ed, pc_out, owner_out, held, armed_out, throw_wants, tap,
        (BEL.find_then_pin(pick_dirty),) + not_picked, 1040, 12800)

    # --- refresh -------------------------------------------------------------
    dirty_get = _at(ed.add_get_member_variable_node("NeedsRefresh"), 1040, 4760)
    refresh_gate = _at(ed.add_branch_node(), 1300, 4600)
    _connect(_pin(dirty_get, "NeedsRefresh", is_input=False),
             _pin(refresh_gate, "Condition"))
    for exit_pin in flight_exits:
        _connect(exit_pin, _pin(refresh_gate, "execute"))
    settle = _at(ed.add_set_member_variable_node("NeedsRefresh"), 1560, 4600)
    _set(settle, "NeedsRefresh", "false")
    _connect(BEL.find_then_pin(refresh_gate), _pin(settle, "execute"))
    _author_equip(ed, BEL.find_then_pin(settle), 1900, 4600)
