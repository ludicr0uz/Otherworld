"""Probe: the object every probe function is handed.

Checks and notes go to the probe's Ledger (runner.py). The rest are the few
game lookups every probe needs, written once so no probe has to rediscover
them -- each of these cost a session a turn or three to find:

- The world comes from ``find_object`` on the map's path. A -game process has
  no editor world context, and ``EditorLevelLibrary.get_game_world`` SIGSEGVs.
- ``AbilitySystemLibrary`` is the Python name of the GAS blueprint library
  (not ``AbilitySystemBlueprintLibrary``).
- A tag is built with ``import_text('(TagName="...")')``.
- A Blueprint variable is written with ``set_editor_property``, which refuses a
  live instance unless the variable is Instance Editable -- list it in the
  probe's ``WRITABLE`` and boot.py makes it so for this run -- and which, by
  default, re-runs the owner's construction script (``set`` below says why
  it must not).

In a network run (``uepy.py --net``) every process runs the probe: ``where``
and its neighbours say which one this is, and ``post``/``posted`` carry a
step from one process to another (net.py).

``unreal`` is imported lazily so the ledger half stays importable off-engine.
"""

from combat.weapon_layers_consts import LAYERS_TAG
from probes.net import Where


class Probe(object):

    def __init__(self, ledger, map_path, game_time, where=None):
        self._ledger = ledger
        self.map_path = map_path
        self.time = game_time
        self.net = where or Where()

    @staticmethod
    def pose_instance(mesh):
        """The anim instance the pose variables are on (AimPitch, the stance
        and guard weights, the support hand): the mesh's own, or with the
        motion matching worn the weapon layers' instance linked into it
        (combat/weapon_layers.py). Montages and slots are asked of the mesh's
        own instance, whichever body it is."""
        return (mesh.get_linked_anim_graph_instance_by_tag(LAYERS_TAG)
                or mesh.get_anim_instance())

    # ─── which process this is ──────────────────────────────────────────────

    @property
    def where(self):
        """"server", "client 1", ..., or "standalone" in a --game run."""
        return self.net.name

    @property
    def is_server(self):
        return self.net.role == "server"

    @property
    def is_client(self):
        return self.net.role == "client"

    @property
    def client(self):
        """This client's number, 1..N; 0 on the server and standalone."""
        return self.net.index

    @property
    def clients(self):
        """How many clients the run started; 0 standalone."""
        return self.net.clients

    def post(self, key, value=True):
        self.net.post(key, value)

    def posted(self, where, key):
        return self.net.posted(where, key)

    # ─── results ────────────────────────────────────────────────────────────

    def check(self, label, ok, detail=""):
        return self._ledger.check(label, ok, detail)

    def note(self, text):
        self._ledger.note(text)

    # ─── the game ───────────────────────────────────────────────────────────

    def world(self):
        import unreal
        name = self.map_path.rsplit("/", 1)[-1]
        return unreal.find_object(None, f"{self.map_path}.{name}")

    def pawn(self, index=0):
        import unreal
        return unreal.GameplayStatics.get_player_pawn(self.world(), index)

    def controller(self, index=0):
        import unreal
        return unreal.GameplayStatics.get_player_controller(self.world(), index)

    def players(self):
        """Every player's controller. On the server that is one per client;
        a client (or a single-player game) has only its own."""
        import unreal
        world = self.world()
        return [unreal.GameplayStatics.get_player_controller(world, i)
                for i in range(unreal.GameplayStatics.get_num_player_controllers(world))]

    def hud(self):
        pc = self.controller()
        return pc.get_hud() if pc else None

    def game_mode(self):
        """The GameMode: the server's (and single player's). None on a client."""
        import unreal
        return unreal.GameplayStatics.get_game_mode(self.world())

    def game_state(self):
        """The world's shared state (net/state_consts.py), on any machine."""
        import unreal
        return unreal.GameplayStatics.get_game_state(self.world())

    def player_state(self, index=0):
        """A local player's own state: the kills, "is dead". On a server use
        ``controller.player_state`` of each of ``players()``."""
        pc = self.controller(index)
        return pc.player_state if pc else None

    def load_class(self, class_path):
        """A Blueprint class by its ``/Game/.../BP_X.BP_X_C`` path. Raises if missing."""
        import unreal
        cls = unreal.load_object(None, class_path)
        if cls is None:
            raise LookupError(f"no class at {class_path}")
        return cls

    def component(self, actor, class_path):
        """The first component of ``actor`` whose class is at ``class_path``."""
        comp = actor.get_component_by_class(self.load_class(class_path))
        if comp is None:
            raise LookupError(f"{actor.get_name()} has no {class_path}")
        return comp

    def actor_of(self, class_path):
        """Any one placed or spawned actor of the class, or raises."""
        import unreal
        actor = unreal.GameplayStatics.get_actor_of_class(
            self.world(), self.load_class(class_path))
        if actor is None:
            raise LookupError(f"no {class_path} in the level")
        return actor

    def get(self, obj, name):
        return obj.get_editor_property(name)

    def set(self, obj, name, value):
        """Write a variable on a live object (declare it in WRITABLE).

        Without edit notifications: the default fires PostEditChange, which on
        a live component re-runs its owner's construction script -- the actor
        gets fresh components and the one just written is a dead copy.

        The weapon component's EquippedIndex is the slot sync's to write
        (combat/weapon_component/slot_sync.py): a probe that writes it is
        asking for Inventory[value] in hand, which is hold()'s.
        """
        import unreal
        if name == EQUIPPED_INDEX and _is_weapon_component(obj):
            self.hold(obj, value)
            return
        obj.set_editor_property(name, value,
                                unreal.PropertyAccessChangeNotifyMode.NEVER)
        # A carried item's state written from here is a change no graph made,
        # so nothing marked its carrier's record (combat/dirty.py): the
        # probe's write marks it, as a graph's Set would.
        from combat.record_vars import ITEM_STATE
        if str(name) in ITEM_STATE and isinstance(obj, unreal.Actor):
            unreal.OtherworldInventoryLibrary.mark_carried_item_dirty(obj)

    def hold(self, wc, index):
        """Bring Inventory[index] to hand, as a number key or a click on its
        slot does: the component is asked for its slot (AskSlot), and
        the next Tick it is held (the hand's item goes home first); on a
        client, once the server has served it and its record is back. Already
        in hand, or past the end of the bag: nothing."""
        from combat.slot_tuning import HAND, SLOT_VAR
        bag = list(wc.get_editor_property("Inventory"))
        if not 0 <= index < len(bag):
            return
        slot = bag[index].get_editor_property(SLOT_VAR)
        if slot > HAND:
            self.ask_slot(wc, slot)

    def ask_slot(self, wc, slot):
        """AskSlot(slot) of a weapon component, from whichever machine this
        is. With authority (the server, single player) the event is called;
        a client cannot send a Blueprint Server event from Python, so it
        writes SlotForced and the component's own Tick asks (the probe lists
        SlotForced, or EquippedIndex, in WRITABLE)."""
        import unreal
        from combat.ask_consts import ASK_SLOT
        from combat.record_vars import SlotForced
        if wc.get_owner().has_authority():
            wc.call_method(ASK_SLOT, (slot,))
        else:
            wc.set_editor_property(str(SlotForced), slot,
                                   unreal.PropertyAccessChangeNotifyMode.NEVER)

    def ask_drop(self, wc, slot):
        """AskDrop(slot), the same way (DropForced in WRITABLE): the slot's
        item set down on the ground, by the server."""
        import unreal
        from combat.ask_consts import ASK_DROP
        from combat.record_vars import DropForced
        if wc.get_owner().has_authority():
            wc.call_method(ASK_DROP, (slot,))
        else:
            wc.set_editor_property(str(DropForced), slot,
                                   unreal.PropertyAccessChangeNotifyMode.NEVER)

    def ask_take_off(self, wc, slot, to=-1):
        """AskTakeOff(slot, to), the same way (TakeOffForced and
        TakeOffForcedTo in WRITABLE): the garment worn in ``slot`` into the
        bag, or onto the slot code ``to``."""
        import unreal
        from combat.ask_consts import ASK_TAKE_OFF
        from combat.record_vars import TakeOffForced, TakeOffForcedTo
        if wc.get_owner().has_authority():
            wc.call_method(ASK_TAKE_OFF, (slot, to))
            return
        never = unreal.PropertyAccessChangeNotifyMode.NEVER
        wc.set_editor_property(str(TakeOffForcedTo), to, never)
        wc.set_editor_property(str(TakeOffForced), slot, never)

    def ask_wear(self, wc, slot):
        """AskWear(slot), the same way (WearForced in WRITABLE): the garment
        in the slot code ``slot`` onto the worn slot it belongs in."""
        import unreal
        from combat.ask_consts import ASK_WEAR
        from combat.record_vars import WearForced
        if wc.get_owner().has_authority():
            wc.call_method(ASK_WEAR, (slot,))
        else:
            wc.set_editor_property(str(WearForced), slot,
                                   unreal.PropertyAccessChangeNotifyMode.NEVER)

    def ask_move(self, wc, src, dst):
        """AskMove(src, dst), the same way (MoveForcedFrom and MoveForcedTo
        in WRITABLE)."""
        import unreal
        from combat.ask_consts import ASK_MOVE
        from combat.record_vars import MoveForcedFrom, MoveForcedTo
        if wc.get_owner().has_authority():
            wc.call_method(ASK_MOVE, (src, dst))
            return
        never = unreal.PropertyAccessChangeNotifyMode.NEVER
        wc.set_editor_property(str(MoveForcedTo), dst, never)
        wc.set_editor_property(str(MoveForcedFrom), src, never)

    def tag(self, name):
        import unreal
        tag = unreal.GameplayTag()
        if not tag.import_text(f'(TagName="{name}")'):
            raise LookupError(f"gameplay tag {name} is not registered")
        return tag

    def send_event(self, actor, tag_name, optional_object=None, instigator=None):
        """Send a gameplay event to ``actor``'s ability system, as Blueprints do."""
        import unreal
        tag = self.tag(tag_name)
        data = unreal.GameplayEventData()
        data.set_editor_property("event_tag", tag)
        if optional_object is not None:
            data.set_editor_property("optional_object", optional_object)
        if instigator is not None:
            data.set_editor_property("instigator", instigator)
        unreal.AbilitySystemLibrary.send_gameplay_event_to_actor(actor, tag, data)


EQUIPPED_INDEX = "EquippedIndex"


def _is_weapon_component(obj):
    return obj.get_class().get_name() == "BP_WeaponComponent_C"
