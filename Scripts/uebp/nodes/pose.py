"""uebp.nodes.pose -- the game's own pose library (C++, the Otherworld
module: Source/Otherworld/Public/OtherworldServerPose.h). How often a
dedicated server poses a body it never draws (task A4).
"""

POSE_LIBRARY = "/Script/Otherworld.OtherworldPoseLibrary"

# Body, FullWithinCm, FarHz, NobodyBeyondCm, NobodyHz. On a dedicated server
# alone: the body's mesh is posed by how near a player is, and every other
# skinned mesh on it stops ticking.
FN_THROTTLE_SERVER_POSE = POSE_LIBRARY + ".ThrottleServerPose"
# For the probes: the frames between two poses of a body, and how many
# skinned meshes on an actor still tick.
FN_SERVER_POSE_EVERY_FRAMES = POSE_LIBRARY + ".ServerPoseEveryFrames"
FN_TICKING_SKINNED_MESHES = POSE_LIBRARY + ".TickingSkinnedMeshes"
