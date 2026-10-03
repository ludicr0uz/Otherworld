"""uebp.nodes.system -- the other static libraries: system, string, text,
input, material, GameplayStatics, user settings.
"""

FN_APPLY = "/Script/Engine.GameUserSettings.ApplyNonResolutionSettings"
FN_GET_GUS = "/Script/Engine.GameUserSettings.GetGameUserSettings"
FN_SET_OVERALL = "/Script/Engine.GameUserSettings.SetOverallScalabilityLevel"

FN_ACTOR_OF_CLASS = "/Script/Engine.GameplayStatics.GetActorOfClass"
# Drawn to a fire (npc/drawn.py). FindNearestActor is pure: its actor is read
# once, into a variable.
FN_ALL_ACTORS = "/Script/Engine.GameplayStatics.GetAllActorsOfClass"
FN_CREATE_SAVE = "/Script/Engine.GameplayStatics.CreateSaveGameObject"
FN_DELETE_SAVE = "/Script/Engine.GameplayStatics.DeleteGameInSlot"
FN_DELTA_SECONDS = "/Script/Engine.GameplayStatics.GetWorldDeltaSeconds"
FN_GET_CAM = "/Script/Engine.GameplayStatics.GetPlayerCameraManager"
FN_GET_GAME_MODE = "/Script/Engine.GameplayStatics.GetGameMode"
FN_GET_PC = "/Script/Engine.GameplayStatics.GetPlayerController"
FN_GET_PLAYER_PAWN = "/Script/Engine.GameplayStatics.GetPlayerPawn"
FN_LEVEL_NAME = "/Script/Engine.GameplayStatics.GetCurrentLevelName"
FN_LOAD_SAVE = "/Script/Engine.GameplayStatics.LoadGameFromSlot"
FN_NEAREST_ACTOR = "/Script/Engine.GameplayStatics.FindNearestActor"
FN_OBJECT_CLASS = "/Script/Engine.GameplayStatics.GetObjectClass"
FN_OPEN_LEVEL = "/Script/Engine.GameplayStatics.OpenLevel"
FN_PLAY_SOUND = "/Script/Engine.GameplayStatics.PlaySoundAtLocation"
FN_REAL_TIME = "/Script/Engine.GameplayStatics.GetRealTimeSeconds"
FN_SAVE_EXISTS = "/Script/Engine.GameplayStatics.DoesSaveGameExist"
FN_SET_PAUSED = "/Script/Engine.GameplayStatics.SetGamePaused"
FN_TIME_SECONDS = "/Script/Engine.GameplayStatics.GetTimeSeconds"
FN_WITH_TAG = "/Script/Engine.GameplayStatics.GetAllActorsWithTag"
FN_WRITE_SAVE = "/Script/Engine.GameplayStatics.SaveGameToSlot"

FN_KEY_DISPLAY = "/Script/Engine.KismetInputLibrary.Key_GetDisplayName"

FN_SET_MPC_SCALAR = "/Script/Engine.KismetMaterialLibrary.SetScalarParameterValue"

FN_BOOL_TO_STR = "/Script/Engine.KismetStringLibrary.Conv_BoolToString"
FN_BUILD_FLOAT = "/Script/Engine.KismetStringLibrary.BuildString_Double"
FN_BUILD_INT = "/Script/Engine.KismetStringLibrary.BuildString_Int"
FN_CONCAT = "/Script/Engine.KismetStringLibrary.Concat_StrStr"
FN_CONTAINS = "/Script/Engine.KismetStringLibrary.Contains"
FN_EQ_SS = "/Script/Engine.KismetStringLibrary.EqualEqual_StrStr"
FN_FLOAT_TO_STR = "/Script/Engine.KismetStringLibrary.Conv_DoubleToString"
FN_INT_TO_STR = "/Script/Engine.KismetStringLibrary.Conv_IntToString"
FN_VEC_TO_STR = "/Script/Engine.KismetStringLibrary.Conv_VectorToString"

FN_COMMAND_LINE = "/Script/Engine.KismetSystemLibrary.GetCommandLine"
FN_CONSOLE = "/Script/Engine.KismetSystemLibrary.ExecuteConsoleCommand"
FN_DELAY = "/Script/Engine.KismetSystemLibrary.Delay"
# Only the temporary hit-reaction probe uses this; see HIT_REACT_PROBE.
FN_DISPLAY_NAME = "/Script/Engine.KismetSystemLibrary.GetDisplayName"
FN_DRAW_CONE = "/Script/Engine.KismetSystemLibrary.DrawDebugConeInDegrees"
FN_DRAW_LINE = "/Script/Engine.KismetSystemLibrary.DrawDebugLine"
FN_DRAW_POINT = "/Script/Engine.KismetSystemLibrary.DrawDebugPoint"
FN_DRAW_STRING = "/Script/Engine.KismetSystemLibrary.DrawDebugString"
FN_IS_VALID = "/Script/Engine.KismetSystemLibrary.IsValid"
# A class reference is a different pin category from an object reference, so
# IsValid refuses to connect to one; IsValidClass is the class-pin twin.
FN_IS_VALID_CLASS = "/Script/Engine.KismetSystemLibrary.IsValidClass"
# A Name pin passed by reference (the Blackboard's KeyName) takes no literal,
# and EqualEqual_NameName is a wildcard until wired: both are fed from this.
FN_LITERAL_NAME = "/Script/Engine.KismetSystemLibrary.MakeLiteralName"
# An object pin of EqualEqual_ObjectObject takes no asset literal, so a mesh
# is told by its name (npc/stalk_cover.py).
FN_OBJECT_NAME = "/Script/Engine.KismetSystemLibrary.GetObjectName"
# The combat trace (npc/combat_trace.py) and the corpse state (npc/corpse.py).
FN_PRINT = "/Script/Engine.KismetSystemLibrary.PrintString"
FN_QUIT = "/Script/Engine.KismetSystemLibrary.QuitGame"
# The wendigo's hunt (npc/stalk.py, stalk_cover.py).
FN_SPHERE_TRACE = "/Script/Engine.KismetSystemLibrary.SphereTraceSingle"
FN_TRACE = "/Script/Engine.KismetSystemLibrary.LineTraceSingle"
FN_WARN = "/Script/Engine.KismetSystemLibrary.PrintWarning"

FN_STR_TO_TEXT = "/Script/Engine.KismetTextLibrary.Conv_StringToText"
FN_TEXT_TO_STR = "/Script/Engine.KismetTextLibrary.Conv_TextToString"
FN_TO_TEXT = "/Script/Engine.KismetTextLibrary.Conv_DoubleToText"

FN_EXEC_PYTHON = "/Script/PythonScriptPlugin.PythonScriptLibrary.ExecutePythonCommand"
