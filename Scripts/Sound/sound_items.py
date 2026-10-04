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

Two more are arrays on the ITEM (BP_WeaponItem's, so every item's), bound by
the item's type:

    HandleSounds  the item handled: brought to hand or put away by a slot's
                  key, or moved from slot to slot in the I panel
                  (ITEM_HANDLING: a gun's, a blade's, a garment's, anything
                  else's; author_handled, called by slot_moves.py)
    UseSounds     the item used up (ITEM_USE: food eaten; consume.py)

To give an item, or a kind of item, another sound: its row of ITEM_HANDLING
or ITEM_USE, then Scripts/build_sound.py.
"""

import unreal

from clothing.specs import GARMENTS
from combat import item_vars as IV
from combat.paths import (
    AXE_BP_PATH, ITEM_BP_PATH, ITEM_CLASS_PATH, KNIFE_BP_PATH, PISTOL_BP_PATH, RIFLE_BP_PATH,
    SHOTGUN_BP_PATH, SMG_BP_PATH, SNIPER_BP_PATH, WEAPON_COMP_BP_PATH)
from combat.weapon_component import vars as WV
from combat.weapon_component.slot_nodes import valid
from Sound.play import _author_random_sound
from Sound.sound_def import ATT_CREATURE, ATT_FOLEY, Binding, Sound, takes
from survival.paths import CAMPFIRE_BP_PATH, MUSHROOM_BP_PATH
from uebp.graph import _add_component, _component_object, _must_load, out
from uebp.nodes.actor import FN_ACTOR_LOC, FN_GET_OWNER

THROW = Sound("throw", "throw", takes("throw"), ATT_FOLEY)
# The axe on a trunk carries as a creature's voice does: it is the loudest
# thing a player does without a gun, and the wanderers' hearing of it is the
# chop's own noise event, not this.
AXE_CHOP = Sound("axe_chop", "axe chop", takes("axe_chop"), ATT_CREATURE)
MATCH = Sound("match", "match", takes("match"), ATT_FOLEY)
# A fire does not end: its wave loops.
CAMPFIRE = Sound("campfire", "campfire", takes("campfire"), ATT_FOLEY, looping=True)
# An item handled, by its type, and food eaten. Small sounds at the player.
HANDLE_ITEM = Sound("handle_item", "item handling", takes("handle_item"), ATT_FOLEY)
HANDLE_GUN = Sound("handle_gun", "gun handling", takes("handle_gun"), ATT_FOLEY)
HANDLE_BLADE = Sound("handle_blade", "blade handling", takes("handle_blade"), ATT_FOLEY)
HANDLE_CLOTH = Sound("handle_cloth", "garment handling", takes("handle_cloth"), ATT_FOLEY)
EATING = Sound("eating", "eating", takes("eating"), ATT_FOLEY)
SOUNDS = (THROW, AXE_CHOP, MATCH, CAMPFIRE, HANDLE_ITEM, HANDLE_GUN, HANDLE_BLADE, HANDLE_CLOTH,
          EATING)

# Which item sounds like what when handled. The base class's is every item's
# that has no row of its own (the matches, the stick, wood, food, water): a
# child Blueprint inherits the default it does not override.
ITEM_HANDLING = {
    ITEM_BP_PATH: HANDLE_ITEM,
    **{gun: HANDLE_GUN for gun in (SHOTGUN_BP_PATH, PISTOL_BP_PATH, SMG_BP_PATH, RIFLE_BP_PATH,
                                   SNIPER_BP_PATH)},
    KNIFE_BP_PATH: HANDLE_BLADE,
    AXE_BP_PATH: HANDLE_BLADE,
    **{garment.path: HANDLE_CLOTH for garment in GARMENTS},
}
# ...and when used up. The canteen has none: the one drinking take is a preview
# rated ok (docs/missing_sounds.md).
ITEM_USE = {MUSHROOM_BP_PATH: EATING}

CRACKLE_COMP = "Crackle"

BINDINGS = (
    Binding(WEAPON_COMP_BP_PATH, WV.ThrowSounds, THROW),
    Binding(WEAPON_COMP_BP_PATH, WV.ChopSounds, AXE_CHOP),
    Binding(WEAPON_COMP_BP_PATH, WV.MatchSounds, MATCH),
    Binding(CAMPFIRE_BP_PATH, "sound", CAMPFIRE, single=True, component=CRACKLE_COMP),
) + tuple(Binding(item, IV.HandleSounds, sound) for item, sound in ITEM_HANDLING.items()
) + tuple(Binding(item, IV.UseSounds, sound) for item, sound in ITEM_USE.items())


def author_handled(g, execs):
    """The item a slot move handled this frame is heard: one of HandledItem's
    HandleSounds at the player, and HandledItem is let go. ``g`` is the slot
    fragments' _G on the weapon component. Returns the exec tails.

    One play for every move (slot_moves.py sets HandledItem where an item
    goes to hand, goes back, or changes slot), so a new kind of move is a
    write of the variable and not another play node.
    """
    item = g.get(WV.HandledItem)
    moved, idle = g.branch(valid(g, item), execs)
    here = g.call(FN_ACTOR_LOC, self=out(g.call(FN_GET_OWNER)))
    made, heard = _author_random_sound(g.ed, IV.HandleSounds, out(here), moved,
                                       source=g.iget(item, IV.HandleSounds, ITEM_CLASS_PATH))
    g.made.extend(made)
    return [g.put(WV.HandledItem, None, [heard]), idle]


def add_crackle(bp, root, height_cm):
    """The fire's own sound: a looping wave on a component of the fire, so it
    starts with the fire and ends with it. How far it carries and how loud
    it is are the wave's (its attenuation, the SOUND SETTINGS tab)."""
    crackle = _component_object(_add_component(bp, root, unreal.AudioComponent, CRACKLE_COMP))
    crackle.set_editor_property("sound", _must_load(CAMPFIRE.paths[0]))
    crackle.set_editor_property("relative_location", unreal.Vector(0.0, 0.0, height_cm))
    crackle.set_editor_property("auto_activate", True)
