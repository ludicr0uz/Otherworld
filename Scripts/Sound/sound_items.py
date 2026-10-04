"""The items' sounds: anything blunt thrown, the axe on a trunk, a match
struck, and the campfire's crackle.

SOUNDS is the area's rows of the sound table and BINDINGS where each is played
from. Three are arrays of takes on BP_WeaponComponent, one drawn per play
(Sound/play.py):

    ThrowSounds   a blunt thing thrown, as it leaves the hand (throw.py)
    ChopSounds    the axe landing on a tree, and a thrown blade lodging in
                  one: at the cut (chop.py, throw_strike.py)
    MatchSounds   the strike that lights a campfire: where the fire is laid
                  (light.py)

The fourth is the fire's own: a looping wave on a component of BP_Campfire
(add_crackle), so it starts with the fire and ends with it.
"""

import unreal

from combat.paths import WEAPON_COMP_BP_PATH
from combat.weapon_component import vars as WV
from Sound.sound_def import ATT_CREATURE, ATT_FOLEY, Binding, Sound, takes
from survival.paths import CAMPFIRE_BP_PATH
from uebp.graph import _add_component, _component_object, _must_load

THROW = Sound("throw", "throw", takes("throw"), ATT_FOLEY)
# The axe on a trunk carries as a creature's voice does: it is the loudest
# thing a player does without a gun, and the wanderers' hearing of it is the
# chop's own noise event, not this.
AXE_CHOP = Sound("axe_chop", "axe chop", takes("axe_chop"), ATT_CREATURE)
MATCH = Sound("match", "match", takes("match"), ATT_FOLEY)
# A fire does not end: its wave loops.
CAMPFIRE = Sound("campfire", "campfire", takes("campfire"), ATT_FOLEY, looping=True)
SOUNDS = (THROW, AXE_CHOP, MATCH, CAMPFIRE)

CRACKLE_COMP = "Crackle"

BINDINGS = (
    Binding(WEAPON_COMP_BP_PATH, WV.ThrowSounds, THROW),
    Binding(WEAPON_COMP_BP_PATH, WV.ChopSounds, AXE_CHOP),
    Binding(WEAPON_COMP_BP_PATH, WV.MatchSounds, MATCH),
    Binding(CAMPFIRE_BP_PATH, "sound", CAMPFIRE, single=True, component=CRACKLE_COMP),
)


def add_crackle(bp, root, height_cm):
    """The fire's own sound: a looping wave on a component of the fire, so it
    starts with the fire and ends with it. How far it carries and how loud
    it is are the wave's (its attenuation, the SOUND SETTINGS tab)."""
    crackle = _component_object(_add_component(bp, root, unreal.AudioComponent, CRACKLE_COMP))
    crackle.set_editor_property("sound", _must_load(CAMPFIRE.paths[0]))
    crackle.set_editor_property("relative_location", unreal.Vector(0.0, 0.0, height_cm))
    crackle.set_editor_property("auto_activate", True)
