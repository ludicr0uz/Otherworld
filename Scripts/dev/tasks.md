# dev-team queue
Run: `Scripts/dev/dev-team` (this file is its default queue)

- [x] The monsters currently spawn in a non-patrolling state; they seem to be standing in one place.
      Review whether there was an unintended change around this (check the git history of
      `Scripts/npc/`, `forest_generator/npc_agro.py`, `npc_placement.py` and the wanderer
      Blueprints), and fix the issue. Verify NPCs spawn patrolling and stroll around their spawn
      point.
- [x] The gun drop rates seem to have increased. Implement a gun loot drop table, and make the drop
      probability PRNG-based with two rolls: one PRNG for the probability of dropping an item at
      all, and a second for which gun is dropped when a gun is dropped. Starting points:
      `Scripts/combat/death.py`, `combat/tuning.py`, `combat/verify/drops.py`.
- [x] Implement finger bone mapping when integrating humanoid models from Meshy, and apply it to
      the zombies and the player. Starting points: `Scripts/asset_pipeline/build_retarget.py`,
      `import_characters.py`, `skeleton_probe.py`, `providers/meshy.py`, and `Scripts/combat/skin.py`
      / `grip.py`. Verify the finger chains are mapped in the retargeter and the hands no longer
      stay in the bind pose.
- [x] Fix a bug: when a mushroom is eaten and a weapon is in the next inventory slot, that weapon
      fires once after the mushroom is consumed. Starting point:
      `Scripts/combat/weapon_component/consume.py` (and `firing.py` / `inventory.py`). The fire
      press that eats the item must not also fire the weapon that becomes active; add a verifier
      check for it.
