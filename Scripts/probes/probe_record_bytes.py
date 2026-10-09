"""The inventory's record as a save holds it: bytes, a version first, and back.

    python3 Scripts/dev/uepy.py --game --probe Scripts/probes/probe_record_bytes.py

The record (combat/record_vars.py; C++, FOtherworldInventoryRecord) is what a
player carries as plain data, and task M35 saves it as it stands: ToBytes
into a USaveGame's byte array, FromBytes out of it. This is the unit check of
those two, on a record a running game wrote:

    the player  a pistol with five rounds in it, a stick that burns, a hat worn
    its record  --> ToBytes: the version in the first four bytes
                --> a USaveGame (UOtherworldRecordSave), saved to a slot and
                    loaded back: the same bytes
                --> FromBytes: the same record, row for row (the pistol's
                    rounds, the stick lit, the hat in its slot), and the same
                    bytes written again
    refused     another version, bytes cut short, bytes with more after them
    outlived    a row whose class no longer exists is dropped, not a failure

Single player only: the bytes are the same on any machine, and the record a
server holds is the same struct.
"""

SYSTEMS = ('inventory',)

import struct
import time

import unreal

from combat import item_vars as IV
from combat.paths import ITEM_BP_PATH, WEAPON_COMP_BP_PATH, WEAPON_COMP_CLASS_PATH
from combat.record_vars import FORCED
from combat.slot_tuning import SLOT_VAR
from combat.strike_vars import SERVER_TAKE
from combat.torch_tuning import BURN_OUT_VAR, LIT_VAR
from combat.wear_tuning import WEAR_SLOTS
from combat.weapon_component import vars as WV
from probes.probe_chop_tree import _items

RUNS_ON = ("standalone",)
WRITABLE = ([(WEAPON_COMP_BP_PATH, str(v)) for v in FORCED]
            + [(ITEM_BP_PATH, str(v)) for v in (IV.Loaded, LIT_VAR, BURN_OUT_VAR)])
LIB = unreal.OtherworldInventoryLibrary
SLOT_NAME = "probe_record_bytes"
ROUNDS = 5
HAT = WEAR_SLOTS.index("hat")
WAIT_S = 15.0


def _await(cond, seconds=WAIT_S):
    end = time.time() + seconds
    return lambda: cond() or time.time() > end


def _name(cls):
    return cls.get_name().replace("BP_", "").replace("_C", "") if cls else None


def _rows(record):
    """{item name: (slot, loaded, reserve, lit, hot)} off a record struct."""
    return {_name(r.get_editor_property("class")): tuple(
        r.get_editor_property(f) for f in ("slot", "loaded", "reserve", "lit", "hot"))
        for r in record.get_editor_property("items")}


def _worn(record):
    return [_name(c) for c in record.get_editor_property("worn")]


def _item(p, wc, name):
    for item in p.get(wc, WV.Inventory):
        if item and _name(item.get_class()) == name:
            return item
    return None


def probe(p):
    pawn = p.pawn()
    wc = p.component(pawn, WEAPON_COMP_CLASS_PATH)
    yield _await(lambda: _item(p, wc, "Pistol") and _item(p, wc, "Stick"))
    pistol, stick = _item(p, wc, "Pistol"), _item(p, wc, "Stick")
    if not p.check("the player carries a pistol and a stick", bool(pistol and stick)):
        return

    # --- what the task names: a loaded pistol, a lit stick, a worn hat -----------
    p.set(pistol, IV.Loaded, ROUNDS)
    p.set(stick, BURN_OUT_VAR, unreal.GameplayStatics.get_time_seconds(p.world()) + 600.0)
    p.set(stick, LIT_VAR, True)
    hats = [a for a in _items(p, "BP_Hat_C") if p.get(a, IV.Dropped)]
    if not p.check("the level has a hat lying", bool(hats)):
        return
    hats[0].set_actor_location(pawn.get_actor_location(), False, True)
    wc.call_method(SERVER_TAKE, (hats[0],))
    yield _await(lambda: bool(_item(p, wc, "Hat")))
    p.ask_wear(wc, p.get(_item(p, wc, "Hat"), SLOT_VAR))

    def ready():
        record = LIB.inventory_record_of(pawn)
        rows, worn = _rows(record), _worn(record)
        return (rows.get("Pistol", (0, 0))[1] == ROUNDS and rows.get("Stick", (0,) * 5)[3]
                and len(worn) > HAT and worn[HAT] == "Hat")
    yield _await(ready)
    record = LIB.inventory_record_of(pawn)
    text = LIB.describe_record(record)
    p.check(f"the record has the pistol with {ROUNDS} rounds, the stick burning and the "
            "hat worn", bool(ready()), text)

    # --- to bytes, through a save, and back --------------------------------------
    data = bytes(LIB.inventory_record_to_bytes(record))
    version = LIB.inventory_record_save_version()
    p.check("ToBytes writes the version first (four bytes, little-endian)",
            len(data) > 4 and struct.unpack_from("<I", data)[0] == version >= 1,
            f"{len(data)} bytes, starting {data[:4].hex()}; version {version}")

    stats = unreal.GameplayStatics
    save = stats.create_save_game_object(unreal.OtherworldRecordSave)
    save.set_editor_property("record", list(data))
    wrote = stats.save_game_to_slot(save, SLOT_NAME, 0)
    back = stats.load_game_from_slot(SLOT_NAME, 0)
    kept = bytes(back.get_editor_property("record")) if back else b""
    stats.delete_game_in_slot(SLOT_NAME, 0)
    p.check("a USaveGame holds them: saved to a slot and loaded back, the same bytes",
            bool(wrote) and isinstance(back, unreal.OtherworldRecordSave) and kept == data,
            f"saved {wrote}, {len(kept)} of {len(data)} bytes back")

    read = LIB.inventory_record_from_bytes(list(kept))
    p.check("FromBytes reads them", read is not None)
    if read is None:
        return
    p.check("...into the same record, row for row and slot for slot",
            _rows(read) == _rows(record) and _worn(read) == _worn(record)
            and LIB.describe_record(read) == text, LIB.describe_record(read))
    rows = _rows(read)
    p.check(f"...the pistol's {ROUNDS} rounds, the stick lit, the hat in its slot",
            rows["Pistol"][1] == ROUNDS and rows["Pistol"][2] == _rows(record)["Pistol"][2]
            and rows["Stick"][3] is True and rows["Pistol"][3] is False
            and _worn(read)[HAT] == "Hat",
            f"pistol {rows['Pistol']}, stick {rows['Stick']}, worn {_worn(read)}")
    p.check("...and written again it is the same bytes",
            bytes(LIB.inventory_record_to_bytes(read)) == data)

    # --- what it refuses ---------------------------------------------------------
    newer = struct.pack("<I", version + 1) + data[4:]
    refused = {
        "a newer version": newer,
        "no bytes": b"",
        "half a version": data[:3],
        "the last byte missing": data[:-1],
        "cut inside the first row": data[:12],
        "a byte after the end": data + b"\x00",
    }
    got = {label: LIB.inventory_record_from_bytes(list(raw)) is None
           for label, raw in refused.items()}
    p.check("FromBytes refuses bytes it does not read: another version, bytes cut "
            "short, bytes with more after them", all(got.values()), str(got))

    # --- a save outlives an item -------------------------------------------------
    gone = b"/Game/Otherworld/Nowhere/BP_Gone.BP_Gone_C"
    pistol_path = pistol.get_class().get_path_name().encode()
    def row(path, slot, loaded, reserve, flags):
        return (struct.pack("<H", len(path)) + path
                + struct.pack("<iiiB", slot, loaded, reserve, flags))
    old = (struct.pack("<IH", version, 2) + row(gone, 3, 1, 2, 0)
           + row(pistol_path, -1, 7, 9, 2) + struct.pack("<H", 1) + struct.pack("<H", 0))
    kept = LIB.inventory_record_from_bytes(list(old))
    p.check("bytes written by hand in the documented layout read back, and a row whose "
            "class no longer exists is dropped: the pistol's row (slot -1, 7/9, hot) "
            "and an empty worn slot are what is left",
            kept is not None and _rows(kept) == {"Pistol": (-1, 7, 9, False, True)}
            and _worn(kept) == [None],
            LIB.describe_record(kept) if kept is not None else "refused")
