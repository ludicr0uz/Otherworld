"""The fire key is an Enhanced Input action (I1), and pressing it fires.

The other probes stand in for the trigger with FireForced; this one goes
through the input itself. The local player's Enhanced Input subsystem is
handed IA_Fire's value, as a key mapped to it would hand it, and the round
has to leave the gun: the mapping context is on the player, the native
character bound the action, the weapon component's OnFirePressed stamped the
press and its Tick took it (combat/weapon_component/trigger.py).

Held, the action is the component's FireHeld, and a gun that is not
automatic fires once for it. Pressed while the game is paused, it fires
nothing, then or when the pause ends with the button still down.

Rebinding: the HUD pushes the settings' first bind into the mapping context
(SetFireKey). The bind is written on the live settings object, never saved,
and the context's key for the action has to follow it there and back. A
headless game draws no HUD, so the probe calls its draw, where the push is.
"""

SYSTEMS = ('weapons', 'menu')

import unreal

from combat import settings_vars as SV
from combat.input_consts import IA_FIRE, IMC_DEFAULT
from combat.paths import SETTINGS_BP_PATH, WEAPON_COMP_CLASS_PATH
from combat.tuning import FIRE_KEY
from combat.weapon_component import vars as WV
from uebp.nodes.weapon import FIRE_HELD

WRITABLE = [(SETTINGS_BP_PATH, SV.Binds)]
OTHER_KEY = "K"
DOWN = unreal.Vector(1.0, 0.0, 0.0)


def _keys(context, action):
    return [m.key.export_text() for m in context.get_editor_property("default_key_mappings").mappings
            if m.action == action]


def _subsystem():
    """The local player's Enhanced Input subsystem. Python has no node that
    hands a local player's subsystem over, so it is found among the objects:
    a headless game has one local player."""
    found = [o for o in unreal.ObjectIterator(unreal.EnhancedInputLocalPlayerSubsystem)
             if not o.get_name().startswith("Default__")]
    return found[0] if len(found) == 1 else None


def _hold(inputs, action, frames):
    """The action down for ``frames`` frames running: its value handed over
    before each, as a held key's is."""
    for _ in range(frames):
        inputs.inject_input_vector_for_action(action, DOWN, [], [])
        yield 0.0


def probe(p):
    yield 0.5
    world = p.world()
    wc = p.component(p.pawn(), WEAPON_COMP_CLASS_PATH)
    action, context = unreal.load_asset(IA_FIRE), unreal.load_asset(IMC_DEFAULT)
    inputs = _subsystem()
    now = lambda: unreal.GameplayStatics.get_time_seconds(world)
    cooled = lambda: now() > p.get(held, "NextFireTime") + 0.05

    p.check("the local player has the game's mapping context, IA_Fire on its default key",
            # The priority it was added at; None when it is not there.
            inputs is not None and inputs.has_mapping_context(context) is not None
            and _keys(context, action) == [FIRE_KEY], str(_keys(context, action)))
    held = p.get(wc, "Held")
    p.check("the player holds a loaded gun that is not automatic",
            held is not None and p.get(held, "Loaded") > 3 and not p.get(held, "Automatic"),
            held.get_class().get_name() if held else "nothing")
    if inputs is None or held is None:
        return

    # --- a press ---------------------------------------------------------------
    loaded = p.get(held, "Loaded")
    p.check("at rest nothing was pressed and nothing is held",
            p.get(wc, WV.FirePressedAt) < 0.0 and not p.get(wc, FIRE_HELD),
            f"{p.get(wc, WV.FirePressedAt):.3f}")
    inputs.inject_input_vector_for_action(action, DOWN, [], [])
    yield lambda: p.get(held, "Loaded") < loaded
    p.check("the action pressed for a frame fires one round",
            p.get(held, "Loaded") == loaded - 1 and p.get(wc, WV.FirePressedAt) > 0.0,
            f"{loaded} -> {p.get(held, 'Loaded')}")
    yield 0.2
    p.check("...and let go, it is not held", not p.get(wc, FIRE_HELD))

    # --- held ------------------------------------------------------------------
    yield cooled
    loaded = p.get(held, "Loaded")
    yield from _hold(inputs, action, 5)
    # Long enough for a second shot, were the hold a press each frame.
    while now() < p.get(held, "NextFireTime") + 0.3:
        yield from _hold(inputs, action, 1)
    p.check("held down it is FireHeld, and the gun fires once for the one press",
            p.get(wc, FIRE_HELD) and p.get(held, "Loaded") == loaded - 1,
            f"{loaded} -> {p.get(held, 'Loaded')}")
    yield 0.2
    p.check("...and released, FireHeld drops", not p.get(wc, FIRE_HELD))

    # --- paused ----------------------------------------------------------------
    yield cooled
    loaded, stamp = p.get(held, "Loaded"), p.get(wc, WV.FirePressedAt)
    unreal.GameplayStatics.set_game_paused(world, True)
    yield from _hold(inputs, action, 10)
    p.check("pressed in a pause, the press is not told (the button is held all the same)",
            p.get(wc, WV.FirePressedAt) == stamp and p.get(wc, FIRE_HELD),
            f"held {p.get(wc, FIRE_HELD)}")
    unreal.GameplayStatics.set_game_paused(world, False)
    until = now() + 0.4
    while now() < until:
        yield from _hold(inputs, action, 1)
    p.check("...and the pause ending with it still down fires nothing",
            p.get(held, "Loaded") == loaded and p.get(wc, WV.FirePressedAt) == stamp,
            f"{loaded} -> {p.get(held, 'Loaded')}")
    yield 0.2

    # --- rebound ---------------------------------------------------------------
    settings = p.get(p.hud(), "Settings")
    binds = list(p.get(settings, SV.Binds))
    other = unreal.Key()
    other.import_text(OTHER_KEY)
    p.set(settings, SV.Binds, [other] + binds[1:])
    p.hud().call_method("ReceiveDrawHUD", (1920, 1080))
    p.check(f"the settings' first bind written to {OTHER_KEY}, the context maps IA_Fire to it alone",
            _keys(context, action) == [OTHER_KEY], str(_keys(context, action)))
    yield 0.2
    loaded = p.get(held, "Loaded")
    yield cooled
    inputs.inject_input_vector_for_action(action, DOWN, [], [])
    yield lambda: p.get(held, "Loaded") < loaded
    p.check("...and the action still fires", p.get(held, "Loaded") == loaded - 1)
    p.set(settings, SV.Binds, binds)
    p.hud().call_method("ReceiveDrawHUD", (1920, 1080))
    p.check(f"...and written back, to {FIRE_KEY} again",
            _keys(context, action) == [FIRE_KEY], str(_keys(context, action)))
