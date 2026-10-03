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

``unreal`` is imported lazily so the ledger half stays importable off-engine.
"""


class Probe(object):

    def __init__(self, ledger, map_path, game_time):
        self._ledger = ledger
        self.map_path = map_path
        self.time = game_time

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

    def hud(self):
        pc = self.controller()
        return pc.get_hud() if pc else None

    def game_mode(self):
        import unreal
        return unreal.GameplayStatics.get_game_mode(self.world())

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

    def hold(self, wc, index):
        """Bring Inventory[index] to hand, as a number key or a click on its
        slot does: its slot goes into the component's SlotRequest, and the
        next Tick it is held (the hand's item goes home first). Already in
        hand, or past the end of the bag: nothing. boot.py makes SlotRequest
        writable for any probe that writes EquippedIndex."""
        import unreal
        from combat.slot_tuning import HAND, SLOT_REQUEST_VAR, SLOT_VAR
        bag = list(wc.get_editor_property("Inventory"))
        if not 0 <= index < len(bag):
            return
        slot = bag[index].get_editor_property(SLOT_VAR)
        if slot > HAND:
            wc.set_editor_property(SLOT_REQUEST_VAR, slot,
                                   unreal.PropertyAccessChangeNotifyMode.NEVER)

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
