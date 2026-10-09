"""The systems a probe may declare in its SYSTEMS tuple.

Each probe_*.py names the systems it checks, drawn from SYSTEMS here, so a
change can be mapped to the probes worth running (`uepy.py --list-probes`).
"""

SYSTEMS = ("weapons", "inventory", "health", "melee", "throw", "survival", "clothing",
           "loot", "npc", "hud", "menu", "sound", "world", "animation", "movement",
           "net", "load", "title")
