#!/usr/bin/env python3
"""build_app_icons.py -- the game's launcher icon, cut once for each platform.

Run outside the editor (it needs Pillow, which the editor's Python has not):

    python3 Scripts/build_app_icons.py                # from assets/icon/otherworld-icon.jpeg
    python3 Scripts/build_app_icons.py <picture>      # from another square picture

The picture is a rounded frame on a dark backdrop. The backdrop is cut away
along the frame, and what is left is written where each platform's packaging
looks for it (all three tracked, so a clone packages with them):

    macOS    Build/Mac/Resources/Assets.xcassets/AppIcon.appiconset
             Xcode compiles the project's catalog in place of the engine's
             (XcodeProject.cs, ASSETCATALOG_COMPILER_APPICON_NAME = AppIcon).
             The art sits in Apple's 824 px of a 1024 px canvas and is cut to
             Apple's corner, rounder than the frame's own: macOS 26 draws an
             icon of any other outline small, on a grey plate.
    Windows  Build/Windows/Application.ico
             UBT compiles it into the exe, and the packaging stamps it again.
    Linux    Content/Splash/Icon.bmp
             A Linux binary holds no icon: the game sets its window's (the
             taskbar's, the dock's) from this file at start, read with
             SDL_LoadBMP, so it is a BMP and is staged loose, outside the pak
             (Config/DefaultGame.ini, DirectoriesToAlwaysStageAsNonUFS).

The picture itself stays in git-ignored assets/. Mac and Windows take the icon
at compile time, Linux at staging: each needs a re-package to show it.
"""

import json
import os
import struct
import sys

from PIL import Image, ImageDraw

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SOURCE = os.path.join(ROOT, "assets", "icon", "otherworld-icon.jpeg")

MAC_ICONSET = os.path.join(ROOT, "Build", "Mac", "Resources", "Assets.xcassets",
                           "AppIcon.appiconset")
WINDOWS_ICO = os.path.join(ROOT, "Build", "Windows", "Application.ico")
LINUX_BMP = os.path.join(ROOT, "Content", "Splash", "Icon.bmp")

# The frame inside the picture, as fractions of its side: the square it fills
# (left, top, side) and the radius of its corners.
FRAME = (0.0395, 0.0350, 0.9230)
FRAME_RADIUS = 0.105

MASTER = 1024
MAC_ART = 824                       # Apple's icon grid: the art's side in 1024
MAC_RADIUS = 0.225                  # and its corner, as a fraction of that side
MAC_POINTS = (16, 32, 128, 256, 512)
WINDOWS_SIZES = (16, 24, 32, 48, 64, 128, 256)
LINUX_SIZE = 256


def cut(source, radius=FRAME_RADIUS):
    """The frame and what is in it, MASTER px square, clear past its corners."""
    picture = Image.open(source).convert("RGB")
    if picture.width != picture.height:
        sys.exit(f"{source}: {picture.width}x{picture.height}, not square")
    left, top, side = (round(f * picture.width) for f in FRAME)
    art = picture.crop((left, top, left + side, top + side))
    art = art.resize((MASTER, MASTER), Image.LANCZOS).convert("RGBA")
    big = MASTER * 4                # drawn large and shrunk: a smooth edge
    mask = Image.new("L", (big, big), 0)
    ImageDraw.Draw(mask).rounded_rectangle(
        (0, 0, big - 1, big - 1), radius=round(radius * big), fill=255)
    art.putalpha(mask.resize((MASTER, MASTER), Image.LANCZOS))
    return art


def _sized(art, px):
    return art if px == art.width else art.resize((px, px), Image.LANCZOS)


def write_mac(art):
    canvas = Image.new("RGBA", (MASTER, MASTER), (0, 0, 0, 0))
    inset = (MASTER - MAC_ART) // 2
    canvas.paste(_sized(art, MAC_ART), (inset, inset))
    os.makedirs(MAC_ICONSET, exist_ok=True)
    images = []
    for points in MAC_POINTS:
        for scale in (1, 2):
            name = f"icon_{points}x{points}{'@2x' if scale == 2 else ''}.png"
            _sized(canvas, points * scale).save(
                os.path.join(MAC_ICONSET, name), optimize=True)
            images.append({"filename": name, "idiom": "mac",
                           "scale": f"{scale}x", "size": f"{points}x{points}"})
    info = {"author": "xcode", "version": 1}
    _json(os.path.join(MAC_ICONSET, "Contents.json"),
          {"images": images, "info": info})
    _json(os.path.join(os.path.dirname(MAC_ICONSET), "Contents.json"),
          {"info": info})


def _json(path, data):
    with open(path, "w") as handle:
        json.dump(data, handle, indent=2)
        handle.write("\n")


def write_windows(art):
    os.makedirs(os.path.dirname(WINDOWS_ICO), exist_ok=True)
    # Plain bitmaps, not PNG entries: every resource compiler reads those.
    art.save(WINDOWS_ICO, format="ICO", bitmap_format="bmp",
             sizes=[(px, px) for px in WINDOWS_SIZES])


def write_linux(art):
    """A 32-bit BMP with its alpha masks spelled out (a V4 header), bottom row
    first: the form SDL_LoadBMP keeps the transparency of."""
    icon = _sized(art, LINUX_SIZE)
    red, green, blue, alpha = icon.split()
    pixels = Image.merge("RGBA", (blue, green, red, alpha))
    rows = pixels.transpose(Image.FLIP_TOP_BOTTOM).tobytes()
    header = struct.pack(
        "<IiiHHIIiiIIIIII", 108, LINUX_SIZE, LINUX_SIZE, 1, 32, 3, len(rows),
        2835, 2835, 0, 0, 0x00FF0000, 0x0000FF00, 0x000000FF, 0xFF000000)
    header += b"sRGB"[::-1] + bytes(108 - len(header) - 4)
    offset = 14 + len(header)
    os.makedirs(os.path.dirname(LINUX_BMP), exist_ok=True)
    with open(LINUX_BMP, "wb") as handle:
        handle.write(b"BM" + struct.pack("<IHHI", offset + len(rows), 0, 0, offset))
        handle.write(header)
        handle.write(rows)


def main(argv):
    source = argv[0] if argv else SOURCE
    if not os.path.isfile(source):
        sys.exit(f"no picture at {source}")
    art = cut(source)
    write_mac(cut(source, MAC_RADIUS))
    write_windows(art)
    write_linux(art)
    for path in (MAC_ICONSET, WINDOWS_ICO, LINUX_BMP):
        print(os.path.relpath(path, ROOT))


if __name__ == "__main__":
    main(sys.argv[1:])
