"""Fire and heat as server requests (task M25): the events' names, what the
server checks, and how the lit stick and the hot blade reach the clients.
Constants only; the graphs are weapon_component/light.py, torch.py, heat.py
and cauterize.py.

    owning client                         server
    the fire key tapped, the   ------->   Server_Light()
    matches in hand                         alive, ITS item in hand Lights, a
                                            piece of wood in ITS bag: the wood
                                            is spent, a campfire (a replicated
                                            actor: survival/campfire.py) is
                                            spawned in front of ITS copy, and
                                            everyone hears the match
    the use key pressed, a     ------->   Server_Kindle()
    stick that Burns in hand                alive, ITS item Burns and is not
                                            Lit, a campfire within reach of
                                            ITS copy: Lit until BurnOutTime
    E on a campfire, a blade   ------->   Server_Heat(Fire)
    that Heats in hand                      alive, Fire a campfire within
                                            HEAT_REACH_CM of ITS copy, ITS
                                            item Heats: Hot until CoolTime
    the use key pressed, a     ------->   Server_Cauterize()
    Hot blade in hand                       alive, ITS item Hot: the bleed is
                                            taken off ITS ability system

Lit and Hot are the item's own, and so are their clocks: the server's item
burns out and cools on its own Tick (stick.py, heat.py), and no client's copy
decides either. They reach a client three ways, all of them the server's
word:

    an item in the world        Lit and Hot replicate on the actor
                                (item_world.py)
    an item its owner carries   the record's InvLit and InvHot columns
                                (record_vars.py), which the picture is made
                                from (view.py)
    the item in another         HandLit and HandHot, beside HandClass
    player's hand

The chop needed nothing new: it hangs off the server's blow (M20), its count
is the server's, its chips are a Multicast and the wood it leaves lies
Dropped, which replicates by itself (item_world.py).

In single player each Server event is a plain call on the one machine.
"""

from combat.tuning import INTERACT_RADIUS
from uebp.vars import obj

SERVER_LIGHT = "Server_Light"
SERVER_KINDLE = "Server_Kindle"
SERVER_HEAT = "Server_Heat"
SERVER_CAUTERIZE = "Server_Cauterize"

# The campfire is survival's and built after the component: an actor here,
# tested against CampfireClass by the server.
FIRE_PARAM = "Fire"
HEAT_PARAMS = ((FIRE_PARAM, obj("/Script/Engine.Actor")),)
# The interact's reach, and what a moving client is ahead of the server by
# (as the take's: strike_vars.TAKE_REACH_CM).
HEAT_REACH_CM = INTERACT_RADIUS + 150.0

SERVER_EVENTS = (SERVER_LIGHT, SERVER_KINDLE, SERVER_HEAT, SERVER_CAUTERIZE)
