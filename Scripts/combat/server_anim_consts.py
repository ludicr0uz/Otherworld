"""The server arm of an anim graph (task A4): its names and what it may hold.
Constants only; server_anim.py authors the branch, verify/server_anim.py
checks it.

A dedicated server evaluates an anim graph for one reason: the bones carry
the hit bodies a shot is judged against and the gun a shot leaves. So each
graph, the player's and every wanderer's, has ONE branch on ServerPose (set
once from IsDedicatedServer), and its server arm holds only what moves a
hit-box bone a shooter is aiming at:

    locomotion   the state machines
    stance       the crouch, the crawl and the kneel (clips and their blends,
                 the hips' lift)
    the aim      the ready pose, or a wanderer's swing, in DefaultSlot (upper
                 body: where the arms' hit bodies and the muzzle are) and the
                 spine's pitch
    the flinch   HitSlot: a body that is hit flinches on every client, and
                 the next round is aimed at the chest where it flinched to
    the guard    the arms and the chest brought up in front of the head

and none of what is for the eye:

    the feet     the player's foot IK (the Control Rig), which traces the
                 ground under both feet every frame. Measured at 32 players
                 (probes/probe_net_load.py): 5.5 ms of a 31.4 ms world tick.
                 What it costs a shot: it lowers the hips onto the ground,
                 so without it the server's chest stands 3-5 cm off the one
                 a client aims at, against 1-3 cm with it
                 (probes/probe_net_lag_hits.py prints it per shot)
    FullBodySlot nothing plays in it today
    the support hand's IK
                 in the shared tail, held at weight 0 on a server
                 (weapon_component/support_hand.py writes it on none)

WHY THE TWO SLOTS STAY. The flinch was skipped at first too. It is back for
a reason the hit probe cannot put a number on (its own spread, 4 to 8 rounds
of 8 from run to run, on the build before this task as well, is wider than a
flinch could show in it), and for one of wiring: a blend's output in these
graphs feeds the next blend's base AND that blend's slot, the engine updates
a node once per link that reaches it, so an arm that left a blend out would
update the locomotion under it fewer times a frame than a client's does
(server_anim.py, "The branch").

The player's graph is two since G4: the motion-matching base, whose own
branch skips the feet's ground traces (gas_locomotion.py), and the weapon
layers linked into it on both of that branch's arms (weapon_layers.py),
which is the graph this file's rule is checked on. Its locomotion is the pose
it is handed.

A montage still runs its clock on a server (the anim instance advances it,
slot or no slot), so one that times something keeps timing it.
"""

# The anim Blueprint's own flag: this machine is a dedicated server. Written
# once, by the event graph's BlueprintInitializeAnimation.
SERVER_POSE_VAR = "ServerPose"

BRANCH_CLASS = "AnimGraphNode_BlendListByBool"
# The branch's pins: the pose taken while ServerPose is true, and while false.
SERVER_PIN, CLIENT_PIN, FLAG_PIN = "BlendPose_0", "BlendPose_1", "bActiveValue"

SLOT_CLASS = "AnimGraphNode_Slot"
LAYER_CLASS = "AnimGraphNode_LayeredBoneBlend"
RIG_CLASS = "AnimGraphNode_ControlRig"
IK_CLASS = "AnimGraphNode_TwoBoneIK"
# The local-space nodes between the aim blend and the component-space tail:
# the walk that finds the two ends of the branch follows these down the chain.
COSMETIC_CLASSES = (LAYER_CLASS, SLOT_CLASS, RIG_CLASS)

PLAYER, WANDERER = "player", "wanderer"
# The slots a server arm may play, by whose graph it is. (The names are
# anim_blueprint.py's AIM_SLOT and HIT_SLOT; FULL_BODY_SLOT is in neither.)
SERVER_SLOTS = {PLAYER: ("DefaultSlot", "HitSlot"), WANDERER: ("DefaultSlot", "HitSlot")}

# Every pose node a server arm may hold, by class. A slot must also be one of
# SERVER_SLOTS, a layered blend the one that slot feeds, and the IK held at 0.
SERVER_ARM_CLASSES = (
    "AnimGraphNode_Root", BRANCH_CLASS,
    # The pose the motion-matching base hands the weapon layers' graph
    # (weapon_layers.py): the locomotion, as that graph sees it.
    "AnimGraphNode_LinkedInputPose",
    "AnimGraphNode_StateMachine", "AnimGraphNode_SequencePlayer",
    "AnimGraphNode_SequenceEvaluator", "AnimGraphNode_TwoWayBlend",
    "AnimGraphNode_LocalToComponentSpace", "AnimGraphNode_ComponentToLocalSpace",
    "AnimGraphNode_ModifyBone", SLOT_CLASS, LAYER_CLASS, IK_CLASS,
)
