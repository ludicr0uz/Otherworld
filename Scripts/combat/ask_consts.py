"""The asks: what a screen asks of the player's weapon component, by name.

A widget graph changes no game state. Each thing the player does through one
is a custom event on BP_WeaponComponent (combat/weapon_component/asks.py,
loot_take.py, save_exit.py), which the HUD calls with what was picked and
nothing else; the component decides whether it happens. One event per action,
so the multiplayer tasks that make these server requests (M18, M23, M24,
M35) have one node each to turn into a Server event. Constants only.
"""

# (event, its int parameters). The slot codes are combat/slot_tuning.py's; a
# worn slot is wear_tuning.WEAR_SLOTS' index.
ASK_SLOT = "AskSlot"            # bring a slot's item to hand (a click, Enter)
ASK_MOVE = "AskMove"            # a drag from one slot onto another
ASK_TAKE_OFF = "AskTakeOff"     # a worn garment off: into the bag, or onto a slot
ASK_WEAR = "AskWear"            # a slot's garment dragged onto the worn grid
ASK_DROP = "AskDrop"            # a slot's item or a worn garment set down
SLOT_PARAM, FROM_PARAM, TO_PARAM = "Slot", "From", "To"
INT_ASKS = (
    (ASK_SLOT, (SLOT_PARAM,)),
    (ASK_MOVE, (FROM_PARAM, TO_PARAM)),
    (ASK_TAKE_OFF, (SLOT_PARAM, TO_PARAM)),
    (ASK_WEAR, (FROM_PARAM,)),
    (ASK_DROP, (FROM_PARAM,)),
)

# The loot window's take: the body searched (its BP_HealthComponent) and
# which of the things it carries.
ASK_LOOT_TAKE = "AskLootTake"
BODY_PARAM, INDEX_PARAM = "Body", "Index"

# Save and exit: the M panel's row starts the countdown.
ASK_SAVE_EXIT = "AskSaveExit"
EXIT_SECONDS = 15.0
NEVER = -1000.0
# On the component. ExitStartedAt is compared with the owner's
# BP_HealthComponent.LastDamageTime, which a wanderer's swing stamps
# (npc/melee.py): a hit after the start calls the exit off.
EXIT_PENDING_VAR = "ExitPending"
EXIT_AT_VAR = "ExitAt"
EXIT_STARTED_VAR = "ExitStartedAt"
EXIT_CALLED_OFF_VAR = "ExitCalledOffAt"
# The countdown ran out: the character may be saved and the player leave.
EXIT_DUE_VAR = "ExitDue"

ALL_ASKS = tuple(name for name, _ in INT_ASKS) + (ASK_LOOT_TAKE, ASK_SAVE_EXIT)
