"""A blade heated in a fire: the numbers and the names (the item's side is
heat.py, the component's weapon_component/heat.py, cauterize.py and
hot_blow.py).

With an item that Heats in hand (the knife, the axe), the interact key on a
campfire in reach makes it Hot for HEAT_S: it glows red, and cools wherever
it then is. While it is Hot the use key cauterises a wound (it takes the
bleeding off the player), and its blow does HOT_BLOW_SCALE times the damage
to a creature afraid of fire (FIRE_FEAR_TAG on the actor: the wendigo).
"""

# On BP_WeaponItem.
HEATS_VAR = "Heats"                   # the interact key heats it at a fire
HOT_VAR = "Hot"                       # it is hot, and glows
COOL_VAR = "CoolTime"                 # the world time it is cold again
HEAT_MATERIAL_VAR = "HeatMaterial"    # the overlay its model wears while Hot

# How long a blade stays hot once heated. Heating a hot one starts it again.
HEAT_S = 20.0

# What a hot blade's blow does to a creature afraid of fire, times the
# strike's own damage.
HOT_BLOW_SCALE = 2.0
# The actor tag such a creature carries. npc/character.py puts it on the
# variants of forest_generator/npc_ward.NPC_WARD_FEARS; combat only reads it.
FIRE_FEAR_TAG = "FearsFire"

# The component's variable: what this blow takes, written before the health
# is (weapon_component/hot_blow.py).
BLOW_DAMAGE_VAR = "BlowDamage"

# --- the glow -----------------------------------------------------------------
# M_HotMetal is an additive overlay: it adds HOT_COLOUR x HOT_EMISSIVE over the
# part of the model past `Start` along `Axis` (the model component's own
# space, which for a scaled static mesh is the mesh's units), fading in over
# `Fade`. One instance per item, since each model lies its own way.
# Red, and no brighter than lit metal: at 6, and still at 2, the bloom washed
# it out to a white-yellow bar.
HOT_COLOUR = (1.0, 0.03, 0.005)
HOT_EMISSIVE = 1.0
HOT_AXIS_PARAM = "Axis"
HOT_START_PARAM = "Start"
HOT_FADE_PARAM = "Fade"

# The item's components: the model that wears the overlay (weapon_items.
# build_model's name for a one-mesh item) and the light the hot metal throws.
MODEL = "Model"
HEAT_GLOW = "HeatGlow"
HEAT_GLOW_COLOUR = (255, 50, 15)      # sRGB bytes
# Dim: hot metal, not a flame. At 250 it lit a trunk at arm's length by day.
HEAT_GLOW_INTENSITY = 60.0
HEAT_GLOW_RADIUS_CM = 120.0
