"""probe_clothing's drag half: what the I panel's mouse asks of the weapon
component (graphics_menu/inv_drag.py), written straight onto it, since no
headless probe can aim a cursor at a cell. Not a probe of its own:
probe_clothing.py runs it at its end, with the shirt worn and the hat and the
jacket in the bag.

    WearRequest := a slot's code        that slot's garment is worn (a drag
                                        onto the worn grid), from the bag or
                                        from the hand; a gun is not
    TakeOffTo, TakeOffSlot              a worn garment dragged onto a bag
                                        slot or the hand lands there; onto a
                                        weapon slot, or a filled one, in the
                                        bag's first free slot
"""

SYSTEMS = ('inventory', 'clothing')

from combat.slot_tuning import BAG_FIRST, BAG_LAST, HAND, PISTOL_SLOT, SLOT_VAR
from combat.wear_tuning import NOT_CLOTHING, TAKE_OFF_TO_VAR, TAKE_OFF_VAR, WEAR_REQUEST_VAR


def _wear(p, wc, code):
    p.set(wc, WEAR_REQUEST_VAR, code)
    yield lambda: p.get(wc, WEAR_REQUEST_VAR) == NOT_CLOTHING
    yield 0.1


def _take_off(p, wc, slot, to):
    p.set(wc, TAKE_OFF_TO_VAR, to)
    p.set(wc, TAKE_OFF_VAR, slot)
    yield lambda: p.get(wc, TAKE_OFF_VAR) == NOT_CLOTHING
    yield 0.1


def drag_checks(p, wc, hat, jacket, shirt, _slot, _worn_at, _bag, _hold):
    # A bag slot's garment onto the worn grid, with the jacket in hand.
    yield from _hold(p, wc, jacket)
    yield from _wear(p, wc, p.get(hat, SLOT_VAR))
    p.check("dragged onto the worn grid, the hat in a bag slot is worn: out of the bag, "
            "hidden, and what is in hand stays there",
            _worn_at(p, wc, _slot("Hat")) == hat and hat not in _bag(p, wc)
            and hat.get_editor_property("hidden") and p.get(wc, "Held") == jacket,
            str(p.get(wc, "Held")))
    worn_before = list(p.get(wc, "Worn"))
    yield from _wear(p, wc, PISTOL_SLOT)
    p.check("...a gun dragged there is not: nothing changes and the request is lowered",
            list(p.get(wc, "Worn")) == worn_before
            and p.get(wc, WEAR_REQUEST_VAR) == NOT_CLOTHING)

    # A worn garment onto a bag slot, a filled slot, a weapon slot, the hand.
    yield from _take_off(p, wc, _slot("Hat"), BAG_LAST)
    p.check("a worn hat dragged onto the bag's last slot is taken off into that slot",
            hat in _bag(p, wc) and p.get(hat, SLOT_VAR) == BAG_LAST
            and _worn_at(p, wc, _slot("Hat")) is None
            and p.get(wc, TAKE_OFF_TO_VAR) == NOT_CLOTHING, str(p.get(hat, SLOT_VAR)))
    yield from _take_off(p, wc, _slot("Shirt"), BAG_LAST)
    at = p.get(shirt, SLOT_VAR)
    p.check("...onto a slot that is filled, into the bag's first free one instead",
            shirt in _bag(p, wc) and BAG_FIRST <= at < BAG_LAST
            and p.get(hat, SLOT_VAR) == BAG_LAST, str(at))
    yield from _wear(p, wc, at)
    yield from _take_off(p, wc, _slot("Shirt"), PISTOL_SLOT)
    at = p.get(shirt, SLOT_VAR)
    p.check("...and onto a weapon slot, into the bag too: a garment fits none",
            shirt in _bag(p, wc) and BAG_FIRST <= at <= BAG_LAST, str(at))

    # The held garment onto the worn grid: out of the hand.
    yield from _hold(p, wc, jacket)
    yield from _wear(p, wc, HAND)
    yield lambda: p.get(wc, "Held") != jacket
    p.check("the jacket in hand, dragged onto the worn grid, is worn and leaves the hand",
            _worn_at(p, wc, _slot("Jacket")) == jacket and jacket not in _bag(p, wc)
            and p.get(wc, "Held") != jacket and jacket.get_editor_property("hidden"),
            str(p.get(wc, "Held")))
    # ...and back into empty hands.
    yield from _take_off(p, wc, _slot("Jacket"), HAND)
    yield lambda: p.get(wc, "Held") == jacket
    p.check("...and dragged from its worn slot onto the empty hand, is held again",
            p.get(jacket, SLOT_VAR) == HAND and p.get(wc, "Held") == jacket
            and not jacket.get_editor_property("hidden"), str(p.get(jacket, SLOT_VAR)))

    # A swap: the garment worn there takes the slot the new one left.
    yield from _wear(p, wc, HAND)
    worn = list(p.get(wc, "Worn"))
    worn[_slot("Shirt")], worn[_slot("Jacket")] = jacket, None
    p.set(wc, "Worn", worn)
    left = p.get(shirt, SLOT_VAR)
    yield from _wear(p, wc, left)
    p.check("a shirt dragged onto a filled worn slot swaps: it is worn, and the one "
            "that was there is in the bag slot it left",
            _worn_at(p, wc, _slot("Shirt")) == shirt and jacket in _bag(p, wc)
            and p.get(jacket, SLOT_VAR) == left and shirt not in _bag(p, wc),
            f"{p.get(jacket, SLOT_VAR)} vs {left}")
