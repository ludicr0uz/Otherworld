"""UseHeld: use what is in hand, asked by a screen (the I panel's right click
on the hand's slot, and the use key with the panel open:
graphics_menu/inv_drag.py). With the cursor up a click is not the fire key,
so the tap that eats, drinks or strikes a match never comes; this is that
tap's use, by name.

    UseHeld(), on the machine the screen is on:
        Held is there ->
            Consumable and not a garment   one of its UseSounds, then
                                           Server_Consume, the press spent:
                                           the fire key's own arm (consume.py)
            it Lights (the matches)        Server_Light (light.py)
            anything else                  nothing

Not a Server event itself: like the key's arm it only asks, and the server's
events refuse what its own Held does not allow. A garment is not its
business: the screen asks that worn as it always did (AskUseSlot, AskWear),
so a wear goes one way only.
"""

from combat import item_vars as IV
from combat.ask_consts import USE_HELD
from combat.fire_vars import SERVER_LIGHT
from combat.light_tuning import LIGHTS_VAR
from combat.paths import ITEM_CLASS_PATH
from combat.wear_tuning import CLOTHING_SLOT_VAR
from combat.weapon_component import vars as WV
from combat.weapon_component.consume import _author_consume
from uebp.g import _G
from uebp.graph import out, then
from uebp.net import custom_event
from uebp.nodes.actor import FN_GET_OWNER
from uebp.nodes.math import FN_GE_II
from uebp.nodes.system import FN_IS_VALID


def author_use_held_event(ed):
    """The event (see the module docstring). After Server_Consume and
    Server_Light, which it calls by name."""
    g = _G(ed, ITEM_CLASS_PATH)
    event = g.keep(custom_event(ed, USE_HELD, []))
    held = g.get(WV.Held)
    there, _empty = g.branch(out(g.call(FN_IS_VALID, Object=held)), [then(event)])
    edible, other = g.branch(g.iget(held, IV.Consumable), [there])
    garment = g.call(FN_GE_II, A=g.iget(held, CLOTHING_SLOT_VAR), B=0)
    _worn, food = g.branch(out(garment), [edible])
    _author_consume(ed, held, out(g.call(FN_GET_OWNER)), food)
    lights, _plain = g.branch(g.iget(held, LIGHTS_VAR), [other])
    g.call(SERVER_LIGHT, [lights])
    ed.add_comment_to_nodes(
        f"{USE_HELD}: a screen's use of what is in hand, the fire key's tap by name. "
        "Food and drink are used (the sound, Server_Consume), the matches struck "
        "(Server_Light); a garment is the screen's own ask (use_held.py).", g.made)
