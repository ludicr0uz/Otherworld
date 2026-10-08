"""rules.py -- what a content pack may contain, and what earns a second look.

Constants only. A content pack is data: Unreal packages plus, at most, the raw
files they were imported from. Anything that can run on its own (a script, a
binary, a plugin, a config file the editor reads at startup) has no business in
one, so the allowlist is short and everything else blocks.
"""

# Finding levels. BLOCK refuses the promote; REVIEW needs --accept-review after
# a human has looked; NOTE is only listed.
BLOCK = "BLOCK"
REVIEW = "REVIEW"
NOTE = "NOTE"

# The tag every Unreal package starts with (0x9E2A83C1, little-endian).
PACKAGE_TAG = b"\xc1\x83\x2a\x9e"
PACKAGE_EXT = (".uasset", ".umap")

ALLOWED_EXT = frozenset(PACKAGE_EXT + (
    ".uexp", ".ubulk", ".uptnl",                               # package payloads
    ".fbx", ".obj", ".glb", ".gltf", ".abc", ".usd", ".usda", ".usdc", ".usdz",
    ".png", ".jpg", ".jpeg", ".tga", ".exr", ".hdr", ".tif", ".tiff", ".psd",
    ".wav", ".ogg", ".flac",
    ".txt", ".md", ".pdf",                                     # a readme, a licence
))

# Finder litter: skipped, neither reported nor copied.
IGNORED_NAMES = frozenset((".DS_Store", "Thumbs.db", "desktop.ini"))

# A top-level Content folder a pack may never write. Content/Python is
# auto-loaded by the editor (init_unreal.py runs at startup).
RESERVED_TOP = frozenset(("python",))

# How a file starts when it is a program, whatever its extension says.
EXECUTABLE_MAGIC = (
    (b"\xfe\xed\xfa\xce", "Mach-O binary"), (b"\xfe\xed\xfa\xcf", "Mach-O binary"),
    (b"\xce\xfa\xed\xfe", "Mach-O binary"), (b"\xcf\xfa\xed\xfe", "Mach-O binary"),
    (b"\xca\xfe\xba\xbe", "Mach-O universal binary or Java class"),
    (b"\x7fELF", "ELF binary"),
    (b"#!", "script with a shebang line"),
)

# Names inside a package (the name table is plain ASCII) that mean it can do
# more than be looked at. Matched case-insensitively, as FNames are.
# /Script/UnrealEd is not here: ordinary meshes and materials name it (109 of the
# FPS Weapon Bundle's 220 packages do), so it says nothing.
REVIEW_NAMES = (
    (b"/script/pythonscriptplugin", "references the Python plugin"),
    (b"executepythoncommand", "runs a Python command"),
    (b"/script/blutility", "is an editor utility (runs inside the editor)"),
    (b"editorutilitywidgetblueprint", "is an editor utility widget"),
    (b"editorutilityblueprint", "is an editor utility Blueprint"),
    (b"/script/editorscriptingutilities", "calls the editor scripting library"),
    (b"executeconsolecommand", "runs a console command"),
    (b"/script/http", "references the HTTP module"),
    (b"/script/sockets", "references the sockets module"),
    (b"/script/websockets", "references the WebSockets module"),
    (b"launchurl", "opens a URL"),
    (b"blueprintfileutils", "reads or writes files"),
    (b"createproc", "starts a process"),
)

# Ordinary in a pack, but logic all the same: listed so the user knows where it is.
NOTE_NAMES = (
    (b"animblueprintgeneratedclass", "animation Blueprint"),
    (b"widgetblueprintgeneratedclass", "widget Blueprint"),
    (b"blueprintgeneratedclass", "Blueprint"),
)
