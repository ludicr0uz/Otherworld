"""The earlier Sonniss GDC bundles: which of their files this game wants.

2016 to 2019 are on a public mirror that answers range requests, so the
wanted files are pulled out of the remote zips one at a time
(`remote_zip.py`) into `assets/cache/sounds/sonniss_archive/<year>/`. The
2020 and later bundles are only on Sonniss's own server, which refuses
scripted downloads: those are fetched by hand.

Licence: the Sonniss GDC bundle licence, as the 2026 bundle. Royalty-free,
no attribution, not CC0, and the files may not be passed on as sounds.
"""

import os
import re
import urllib.parse
import urllib.request

from sound_candidates import remote_zip

_PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))
OUT_DIR = os.path.join(_PROJECT_DIR, "assets", "cache", "sounds", "sonniss_archive")

MIRROR = "https://ftpmirror.your.org/pub/misc/sonniss{year}/"
YEARS = (2016, 2017, 2018, 2019)
AUDIO = (".wav", ".flac", ".aif", ".aiff")

# Regexes over a member's path inside its zip (library folder / file name),
# grouped by the gap each fills. A year's bundle is a sampler, three or four
# files a library, so a library named here gives a handful of takes.
WANTED = {
    "creature voices": (
        r"INFECTED ZONE/(Zombie|Bite)", r"Screams & Shouts 2 - Monsters/",
        r"Troll Monster Vocalizations/", r"CREATURES ZONE/Creature_Monster",
        r"Yeti Monster/", r"6Monsters/", r"Girardot - Monsters/Monster (Growls|Bite)",
        r"Monster Within/", r"Glitchedtones - Zombie/", r"Mouthy,growl",
        r"Dino - Roars & Growls/", r"black soul growl energy entity drone - quad LR",
    ),
    "player voice": (
        r"Screams & Shouts 2 - Humans/Male_", r"Human Vocalizations/voice_male",
        r"Fight Vocalizations/EMOTE (David|Joshua)", r"Breathing In Hell/scared breath",
        r"voice_male_breathing_mask_loop",
    ),
    "gun handling": (
        r"Various Gun Foley & Handling/",
        r"12 Gauge Shotgun/(Shell Load|Shotgun_Quick Pump)",
    ),
    "tension": (
        r"Cinematic Tension Sound Effects/", r"Drone Collection/Drone_(Dungeon|Evolving|Horror)",
        r"SoundMorph - TENSION/Tension - (low|warbley)", r"Subtext Drone Library Vol. 1/Drone, Dark",
        r"Bedlam Stingers", r"Glitchedtones - Paranormal/(Drone|Eerie)",
        r"Dare Small Pack/Atmospheric", r"DP-Atmospheric element_Tension",
        r"Granular Texture Tension",
    ),
    "heartbeat": (r"Heartbeat,Sound Design", r"Stethoscope_Chest_Heart"),
    "blade and gore": (
        r"Dark Materials/.*(stab|Hammer Impact)", r"Just Gore _ Add On/",
        r"Bones & Blood.*stab dagger", r"SoundMorph - Gore/GORE - WEAP",
        r"BLOODBATH/PM_BB_(CLEAN_STABS|DESIGNED_CINEMATIC_CHOPS)", r"Sound Spark LLC . Gore/",
        r"Punch and Combat Sounds/(punch|whoosh|foley)",
    ),
    "eating and drinking": (
        r"EatingApple", r"CHIP GRAB AND EAT", r"drink,sipping", r"TheWorkRoom - Eating/",
    ),
    "matches": (r"Meridian,ASMR,loop,scratching,matches",),
    "wood": (
        r"Wood Impacts and Debris/", r"BlueZone - Wood Sound Effects/",
        r"BROKEN - DESIGNED - WOOD Break Small",
    ),
    "forest": (
        r"Winter Forest Ambience/", r"Pacific Northwest- Ambiences/Amb, Forest, Birds, Wind",
        r"Wilderness Crickets/", r"Natural ambiences vol.1/(05|43|38)", r"Owls 201",
        r"31 Wind_squeaking_tree", r"Hzandbits - Wind In Trees/",
        r"Footsteps on Leaves/", r"Footsteps_Grass_Sneaker", r"RUSTLE Studio performed green leaves",
    ),
    "bullet impacts": (r"Bullet Impact", r"Rock Hit and Bounce Dirt", r"Hit Rock into Gravel"),
    "menu": (
        r"InspectorJ - UI - Mechanical/", r"Dark Sci-Fi UI Sounds/", r"/Menu Confirm",
        r"3maze - Buttons and Switches/",
    ),
}

_PATTERN = re.compile("|".join(p for group in WANTED.values() for p in group), re.I)
_PART_PREFIX = re.compile(r"^Sonniss\.com - GDC \d+ - Game Audio Bundle Part \d+of\d+/")


def _zip_urls(year):
    base = MIRROR.format(year=year)
    page = urllib.request.urlopen(base, timeout=remote_zip.TIMEOUT_S).read().decode()
    names = re.findall(r'href="([^"]+\.zip)"', page)
    # 2016 is mirrored twice, as three parts and as six.
    return [base + n for n in names if not (year == 2016 and "of3" in n)]


def _local_path(year, member):
    inner = _PART_PREFIX.sub("", member)
    safe = re.sub(r'[*?"<>|:]', "", inner)
    return os.path.join(OUT_DIR, str(year), *safe.split("/"))


def fetch(log=print):
    """Pull every wanted file not already in the cache. Returns `(new, held)`."""
    new = held = 0
    for year in YEARS:
        for url in _zip_urls(year):
            archive = remote_zip.open_zip(url)
            part = urllib.parse.unquote(url.rsplit("%20", 1)[-1])
            for info in archive.infolist():
                name = info.filename
                if info.is_dir() or not name.lower().endswith(AUDIO):
                    continue
                if not _PATTERN.search("/" + _PART_PREFIX.sub("", name)):
                    continue
                path = _local_path(year, name)
                if os.path.exists(path) and os.path.getsize(path) == info.file_size:
                    held += 1
                    continue
                os.makedirs(os.path.dirname(path), exist_ok=True)
                with archive.open(info) as src, open(path + ".part", "wb") as out:
                    while True:
                        chunk = src.read(1 << 20)
                        if not chunk:
                            break
                        out.write(chunk)
                os.replace(path + ".part", path)
                new += 1
                log(f"{year} {part} {info.file_size / 1e6:6.1f} MB  {os.path.relpath(path, OUT_DIR)}")
    return new, held
