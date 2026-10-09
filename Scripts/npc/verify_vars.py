"""Every wanderer controller's variables, and its step task's, against the
tables their fragments declare from (uebp/verify_vars.py): each row declared
with its type, default and replication, and nothing beside them.

Which fragments a creature's controller has is the builder's own question
(controller.py): a stalker's, one a fire wards off, one a fire draws.
"""

import unreal

from forest_generator.npc_placement import NPC_VARIANTS
from forest_generator.npc_stalk import NPC_STALK_ROAR
from npc import controller_vars as NV
from npc.drawn import draws
from npc.paths import AI_BP_PATH, step_task_path
from npc.verify import check
from npc.ward import wards
from survival.on_hit import ON_HIT_TABLE
from uebp.verify_vars import check_table

EVERY = (NV.TABLE + NV.HIT + NV.STEPS + NV.AGRO + NV.STATS + NV.CORPSE + NV.SIGHT_CONE
         + NV.STRAFE + NV.TUNED + ON_HIT_TABLE)


def controller_table(key):
    table = EVERY
    if key in NPC_STALK_ROAR:
        table += NV.STALK + NV.STALK_COVER
    if wards(key):
        table += NV.WARD + NV.WARD_ROAR
    if draws(key):
        table += NV.DRAWN
    return table


def run():
    made = [(AI_BP_PATH, NPC_VARIANTS[0].key)]
    made += [(variant.ai_blueprint, variant.key) for variant in NPC_VARIANTS]
    for path, key in made:
        check_table(unreal.load_asset(path), controller_table(key), check)
        check_table(unreal.load_asset(step_task_path(path)), NV.STEP_TASK, check)
