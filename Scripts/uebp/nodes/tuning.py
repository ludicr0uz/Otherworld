"""uebp.nodes.tuning -- the game's own tuning library (C++, the Otherworld
module: Source/Otherworld/Public/OtherworldTuningLibrary.h): a tuning tab's
save where there is no Python plugin, which is a packaged build.
"""

TUNING_LIBRARY = "/Script/Otherworld.OtherworldTuningLibrary"

# -> is the Python plugin loaded here (the editor binary)?
FN_CAN_RUN_PYTHON = TUNING_LIBRARY + ".CanRunPython"
# FileName, Header, Subjects, Values, Live, Stride -> the table as a CSV in
# the build's Saved/Tuning/; true when it was written.
FN_SAVE_TUNING_CSV = TUNING_LIBRARY + ".SaveTuningCsv"
