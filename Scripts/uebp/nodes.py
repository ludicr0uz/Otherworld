"""Engine function and palette paths the authoring helpers themselves use."""

FN_MAKE_VECTOR = "/Script/Engine.KismetMathLibrary.MakeVector"
# A name pin on a call node refuses a literal on some functions; a
# MakeLiteralName node feeds it instead.
FN_LITERAL_NAME = "/Script/Engine.KismetSystemLibrary.MakeLiteralName"
NODE_TICK = "AddEvent|EventTick"
NODE_BEGIN_PLAY = "AddEvent|EventBeginPlay"
