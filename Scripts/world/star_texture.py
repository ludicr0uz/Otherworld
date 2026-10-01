"""T_NightSkyStars: the star map as a texture, drawn from the catalogue.

Every build rasterises star_catalogue.csv (star_map.rasterise) into a PNG
under Saved/World and imports it. The texture is uncompressed, has no mips and
is never streamed: a star is a texel or two across, and block compression or
a lower mip would wipe it out. It is sRGB, which spends the 8 bits where the
faint stars are.
"""

import os
import struct
import zlib

import unreal

from combat.graph import _log
from world import world_config as cfg
from world.paths import STARS_TEXTURE_PATH
from world.star_catalogue import load_stars
from world.star_map import rasterise


def _srgb_byte(linear):
    c = min(1.0, max(0.0, linear))
    c = c * 12.92 if c <= 0.0031308 else 1.055 * c ** (1.0 / 2.4) - 0.055
    return int(round(c * 255.0))


def _chunk(kind, data):
    body = kind + data
    return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body))


def png_bytes(texels, width, height):
    """An 8-bit RGB PNG: black but for `texels` ({(x, y): [r, g, b]}, linear)."""
    stride = 1 + width * 3                  # each row starts with its filter byte
    raw = bytearray(stride * height)
    for (x, y), rgb in texels.items():
        at = y * stride + 1 + x * 3
        raw[at:at + 3] = bytes(_srgb_byte(c) for c in rgb)
    return (b"\x89PNG\r\n\x1a\n"
            + _chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
            + _chunk(b"IDAT", zlib.compress(bytes(raw), 6))
            + _chunk(b"IEND", b""))


def build_star_texture():
    """Draw, import and save T_NightSkyStars (every run)."""
    width, height = cfg.STAR_MAP_SIZE
    stars = load_stars()
    texels = rasterise(stars, width, height)
    png = os.path.join(unreal.Paths.convert_relative_path_to_full(
        unreal.Paths.project_saved_dir()), "World", "T_NightSkyStars.png")
    os.makedirs(os.path.dirname(png), exist_ok=True)
    with open(png, "wb") as f:
        f.write(png_bytes(texels, width, height))

    dest_dir, name = STARS_TEXTURE_PATH.rsplit("/", 1)
    task = unreal.AssetImportTask()
    task.set_editor_property("filename", png)
    task.set_editor_property("destination_path", dest_dir)
    task.set_editor_property("destination_name", name)
    task.set_editor_property("automated", True)
    task.set_editor_property("replace_existing", True)
    task.set_editor_property("save", True)
    unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
    tex = unreal.EditorAssetLibrary.load_asset(STARS_TEXTURE_PATH)
    if not tex:
        raise RuntimeError(f"could not import {png} as {STARS_TEXTURE_PATH}")
    tex.set_editor_property("srgb", True)
    tex.set_editor_property("compression_settings",
                            unreal.TextureCompressionSettings.TC_EDITOR_ICON)
    tex.set_editor_property("lod_group", unreal.TextureGroup.TEXTUREGROUP_SKYBOX)
    tex.set_editor_property("mip_gen_settings", unreal.TextureMipGenSettings.TMGS_NO_MIPMAPS)
    tex.set_editor_property("never_stream", True)
    tex.set_editor_property("address_x", unreal.TextureAddress.TA_WRAP)
    tex.set_editor_property("address_y", unreal.TextureAddress.TA_CLAMP)
    unreal.EditorAssetLibrary.save_asset(STARS_TEXTURE_PATH)
    drawn = sum(1 for s in stars if s.vmag <= cfg.STAR_MAX_MAG)
    _log(f"{STARS_TEXTURE_PATH}: {drawn} stars on {width}x{height}")
    return tex
