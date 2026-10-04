"""The small CC0 packs: Kenney's and OpenGameArt's, fetched whole.

These are a few megabytes each and need no account, so they are simply
downloaded and unpacked into `assets/cache/sounds/kenney/<pack>/` and
`assets/cache/sounds/opengameart/<pack>/`, where `manifest.py` reads them.

The two big ones are not here because nothing can fetch them: Nox Sound's
Essentials Series (itch.io, a name-your-price button) and the Sonniss GDC
2026 bundle (a server that refuses scripts) are downloaded by hand and
unpacked into `assets/cache/sounds/nox/` and `assets/cache/sounds/sonniss/`.
"""

import os
import re
import subprocess
import urllib.parse
import urllib.request

_PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))
CACHE_DIR = os.path.join(_PROJECT_DIR, "assets", "cache", "sounds")
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 Safari/605.1.15"

KENNEY_PAGE = "https://kenney.nl/assets/{pack}"
KENNEY_PACKS = ("impact-sounds", "interface-sounds", "ui-audio", "rpg-audio")
OGA_PAGE = "https://opengameart.org/content/{pack}"
# (folder, the page's name). One page's address is misspelt on the site.
OGA_PACKS = (
    ("monster-sound-pack-volume-1", "monster-sound-pack-volume-1"),
    ("80-cc0-creature-sfx", "80-cc0-creature-sfx"),
    ("80-cc0-creature-sfx-2", "80-cc0-creture-sfx-2"),
    ("swishes-sound-pack", "swishes-sound-pack"),
    ("cc0-deep-monster-roar", "cc0-deep-monster-roar"),
    ("big-scary-troll-sounds", "big-scary-troll-sounds"),
)
OGA_FILE = re.compile(r'https://opengameart\.org/sites/default/files/[^"]+\.(?:zip|wav|ogg|flac)')
# A page lists each sound twice: the file, and an MP3 preview of it.
OGA_PREVIEW = re.compile(r"prev|\.(?:wav|ogg)\.mp3$")


def _get(url):
    request = urllib.request.Request(url, headers={"User-Agent": UA})
    return urllib.request.urlopen(request, timeout=120).read()


def _save(url, folder):
    """Download `url` into `folder`, unpacking a zip. Returns the file's name."""
    os.makedirs(folder, exist_ok=True)
    name = urllib.parse.unquote(url.rsplit("/", 1)[-1])
    path = os.path.join(folder, name)
    if not os.path.isfile(path):
        with open(path, "wb") as out:
            out.write(_get(url))
        if name.endswith(".zip"):
            subprocess.run(["bsdtar", "-xf", name], cwd=folder, check=True)
    return name


def fetch(log=print):
    for pack in KENNEY_PACKS:
        page = _get(KENNEY_PAGE.format(pack=pack)).decode("utf-8", "replace")
        found = re.search(r"https://kenney\.nl/media/pages/assets/[^\"' ]+\.zip", page)
        if not found:
            raise RuntimeError(f"no download on Kenney's page for {pack}")
        log(f"kenney/{pack}: {_save(found.group(0), os.path.join(CACHE_DIR, 'kenney', pack))}")
    for folder, pack in OGA_PACKS:
        page = _get(OGA_PAGE.format(pack=pack)).decode("utf-8", "replace")
        if "CC0" not in page:
            raise RuntimeError(f"OpenGameArt's page for {pack} does not say CC0")
        for url in sorted(set(OGA_FILE.findall(page))):
            if not OGA_PREVIEW.search(url):
                log(f"opengameart/{folder}: {_save(url, os.path.join(CACHE_DIR, 'opengameart', folder))}")
