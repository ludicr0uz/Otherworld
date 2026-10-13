"""rules.py -- which files of a raw download are taken, and what a texture's name says.

Constants only. A raw download is copied by allowlist: a mesh or a texture is
taken, everything else stays where it is and is listed. Nothing is unpacked,
so an archive in the download is never opened.
"""

import re

# glTF's .gltf is not here: it names a .bin beside it, which is not content.
# A USD file is a mesh that may name other files (a layer per variant, one for
# the shared foliage), so a download's folders are kept as they are when staged
# and the editor half checks that every file one names is inside the item.
USD_EXT = (".usd", ".usda", ".usdc")
MESH_EXT = (".fbx", ".obj", ".glb") + USD_EXT
TEXTURE_EXT = (".png", ".jpg", ".jpeg", ".tga", ".tif", ".tiff", ".exr")
# .usdz is a zip of a stage and whatever it names: an archive like any other.
ARCHIVE_EXT = (".zip", ".rar", ".7z", ".tar", ".gz", ".usdz")

# What the launcher writes beside a download: read by listing.py, never taken.
LAUNCHER_METADATA = "metadata"
LAUNCHER_THUMBNAIL = "thumbnail"
# Sketchfab's viewer ground shadow, exported with every model that came from it.
JUNK_TEXTURE_STEMS = frozenset(("internal_ground_ao_texture",))

# How a file starts when it is what its extension says. A type not listed
# (TGA has no signature, OBJ is text) is not checked.
SIGNATURES = {
    ".png": (b"\x89PNG\r\n\x1a\n",),
    ".jpg": (b"\xff\xd8\xff",),
    ".jpeg": (b"\xff\xd8\xff",),
    ".tif": (b"II*\0", b"MM\0*"),
    ".tiff": (b"II*\0", b"MM\0*"),
    ".exr": (b"\x76\x2f\x31\x01",),
    ".fbx": (b"Kaydara FBX Binary", b"; FBX"),
    ".glb": (b"glTF",),
    ".usd": (b"PXR-USDC", b"#usda"),
    ".usdc": (b"PXR-USDC",),
    ".usda": (b"#usda",),
}

SEPARATORS = " _-."

# (role, the words a file name ends with). The longest word that fits wins, so
# "bcolor" is not read as "color" and "mixedao" not as "ao". Separators inside
# a name are ignored ("Base_color" is "basecolor"). A one-letter word needs a
# separator before it. "matal" is a seller's spelling, kept because it is real.
ROLE_WORDS = (
    ("basecolor", ("basecolor", "basecolour", "bcolor", "albedo", "diffuse", "diff",
                   "color", "colour", "col", "c", "d")),
    ("normal", ("normal", "norm", "nrm", "nor", "n")),
    ("roughness", ("roughness", "rough", "rgh", "r")),
    ("metallic", ("metallic", "metalness", "metal", "matal", "m")),
    ("ao", ("ambientocclusion", "mixedao", "occlusion", "ao")),
    ("opacity", ("opacity", "alpha")),
)
ROLES = tuple(role for role, _words in ROLE_WORDS)

# Project prefixes (CLAUDE.md, hard rule 3).
MESH_PREFIX = "SM_"
TEXTURE_PREFIX = "T_"
MATERIAL_PREFIX = "M_"

NOT_A_NAME = re.compile(r"[^A-Za-z0-9]+")
