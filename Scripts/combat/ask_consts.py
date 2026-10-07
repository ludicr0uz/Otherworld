"""The asks: what a screen asks of the player's weapon component, by name.

A widget graph changes no game state. Each thing the player does through one
is a custom event on BP_WeaponComponent (combat/weapon_component/asks.py,
loot_take.py, save_exit.py), which the HUD calls with what was picked and
nothing else; the component decides whether it happens. One event per action,
so a multiplayer task that makes one a server request (M18 did the slots',
M23 the drop and the loot window's take: SERVER_ASKS; M24, M35) has one node
to turn into a Server event. Constants only.
"""

# (event, its int parameters). The slot codes are combat/slot_tuning.py's; a
# worn slot is wear_tuning.WEAR_SLOTS' index.
ASK_SLOT = "AskSlot"            # bring a slot's item to hand (a click, Enter)
ASK_MOVE = "AskMove"            # a drag from one slot onto another
ASK_NEXT = "AskNext"            # the bag's next item to hand (the Q key)
ASK_TAKE_OFF = "AskTakeOff"     # a worn garment off: into the bag, or onto a slot
ASK_WEAR = "AskWear"            # a slot's garment dragged onto the worn grid
ASK_DROP = "AskDrop"            # a slot's item or a worn garment set down
SLOT_PARAM, FROM_PARAM, TO_PARAM = "Slot", "From", "To"
INT_ASKS = (
    (ASK_SLOT, (SLOT_PARAM,)),
    (ASK_MOVE, (FROM_PARAM, TO_PARAM)),
    (ASK_NEXT, ()),
    (ASK_TAKE_OFF, (SLOT_PARAM, TO_PARAM)),
    (ASK_WEAR, (FROM_PARAM,)),
    (ASK_DROP, (FROM_PARAM,)),
)

# The loot window's take: the body searched (its BP_HealthComponent), which
# of the things it carries, and what the window showed there (its class). The
# server takes the row only if it still holds that: a row another player took
# first has gone, and the next one has moved up into its place.
ASK_LOOT_TAKE = "AskLootTake"
BODY_PARAM, INDEX_PARAM, WANT_PARAM = "Body", "Index", "Want"

# The ones that are Server events (the slots' M18, the drop and the loot take
# M23): the owning client asks, and the server serves the request, where what
# fits where and who gets what is decided. The rest are plain calls until
# their tasks (M24, M35).
SERVER_ASKS = (ASK_SLOT, ASK_MOVE, ASK_NEXT, ASK_DROP, ASK_LOOT_TAKE)

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
