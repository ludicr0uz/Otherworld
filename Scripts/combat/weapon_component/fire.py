"""Fire and heat as server requests (task M25, combat/fire_vars.py): the four
Server events, authored in one call for build.py. Each event is its owner's:

    Server_Light       light.py      the matches' strike: wood into a campfire
    Server_Kindle      torch.py      a stick lit at a campfire
    Server_Heat        heat.py       a blade heated at one
    Server_Cauterize   cauterize.py  a hot blade on a bleed

Before the Tick, whose fragments call them by name; the match's cosmetic pair
before the event that tells it.
"""

from combat.weapon_component.cauterize import author_cauterize_event
from combat.weapon_component.heat import author_heat_event
from combat.weapon_component.light import author_light_event, author_light_fx
from combat.weapon_component.torch import author_kindle_event


def author_fire_events(ed):
    author_light_fx(ed)
    author_light_event(ed)
    author_kindle_event(ed)
    author_heat_event(ed)
    author_cauterize_event(ed)
