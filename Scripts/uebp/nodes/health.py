"""uebp.nodes.health -- the health component's native parent (C++, the
Otherworld module: Source/Otherworld/Public/OtherworldHealthComponent.h),
which BP_HealthComponent is a child of (task W3): the blow, the death and
the two events the graph hangs what a client shows, and what dying is, on
(combat/damage.py, combat/health_component.py).
"""

HEALTH_BASE_CLASS = "/Script/Otherworld.OtherworldHealthComponent"

# self, Amount, From, InstigatedBy, Cause: a blow, the one way health is
# taken off a body. Nothing without authority.
FN_TAKE_HIT = HEALTH_BASE_CLASS + ".TakeHit"
# self: the body has died. Dead, which replicates, and OnDied. Once, and
# nothing without authority.
FN_DIE = HEALTH_BASE_CLASS + ".Die"
# On a client, a Health that arrived.
NODE_EVENT_HEALTH_CHANGED = "AddEvent|Otherworld|Health|EventOnHealthChanged"
# Once on each machine: the server's from Die, a client's when Dead arrives.
NODE_EVENT_DIED = "AddEvent|Otherworld|Health|EventOnDied"
