"""The use key's names (the graph is weapon_component/use.py). Constants only,
apart from that graph, so a kind of use (weapon_component/torch.py) and the
aim (weapon_component/ads.py) can read them without importing it.
"""

USING_VAR = "Using"               # the use key is held on an item with no sights
USE_PRESSED_VAR = "UsePressed"    # ...and went down this frame
USE_WAS_VAR = "UseWas"            # last frame's Using
