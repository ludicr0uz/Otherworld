"""listing.py -- what the launcher wrote beside a download: which listing it is.

The Fab plugin's library keeps one folder per listing and format
(FabLibrary/<Title>-<id8>/<format>/), and in it a ``metadata`` file: JSON,
UTF-16 from some launcher versions and UTF-8 from others. It names the
listing; it does not name its licence. A folder with no metadata is still an
item: its name is its title and it has no URL.
"""

import json
import os

from asset_pipeline.fab_raw import rules

LIBRARY = "/Users/Shared/UnrealEngine/Launcher/VaultCache/FabLibrary"
LISTING_URL = "https://www.fab.com/listings/"


def _decode(raw):
    if raw[:2] in (b"\xff\xfe", b"\xfe\xff"):
        return raw.decode("utf-16")
    return raw.decode("utf-8-sig")


def _metadata_paths(folder):
    yield os.path.join(folder, rules.LAUNCHER_METADATA)
    for name in sorted(os.listdir(folder)):
        yield os.path.join(folder, name, rules.LAUNCHER_METADATA)


def read(folder):
    """{"title", "url", "seller"} for the download at ``folder``."""
    out = {"title": os.path.basename(os.path.normpath(folder)), "url": "", "seller": ""}
    for path in _metadata_paths(folder):
        if not os.path.isfile(path):
            continue
        try:
            with open(path, "rb") as fh:
                listing = json.loads(_decode(fh.read())).get("listing", {})
        except (ValueError, OSError, AttributeError):
            continue
        if not isinstance(listing, dict):
            continue
        if listing.get("title"):
            out["title"] = str(listing["title"])
        if listing.get("uid"):
            out["url"] = LISTING_URL + str(listing["uid"])
        user = listing.get("user")
        if isinstance(user, dict):
            out["seller"] = str(user.get("sellerName") or "")
        break
    return out


def slug(title):
    """A listing's title as a folder name: "CC0 - Axe" -> "CC0_Axe"."""
    return rules.NOT_A_NAME.sub("_", title).strip("_") or "Item"


def find(name, library=LIBRARY):
    """The library folders whose name contains ``name`` (case ignored)."""
    if not os.path.isdir(library):
        return []
    return [os.path.join(library, d) for d in sorted(os.listdir(library))
            if name.lower() in d.lower() and os.path.isdir(os.path.join(library, d))]


def raw_items(library=LIBRARY):
    """Every library folder that holds a raw download (not an unreal-engine one)."""
    out = []
    for folder in find("", library):
        formats = [d for d in sorted(os.listdir(folder))
                   if os.path.isdir(os.path.join(folder, d))]
        if formats and formats != ["unreal-engine"]:
            out.append(folder)
    return out
