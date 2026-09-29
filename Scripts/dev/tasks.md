# dev-team queue
Run: `Scripts/dev/dev-team Scripts/dev/tasks.md`

- [ ] Implement finger bone mapping when integrating humanoid models from Meshy, and apply it to
      the zombies and the player. Starting points: `Scripts/asset_pipeline/build_retarget.py`,
      `import_characters.py`, `skeleton_probe.py`, `providers/meshy.py`, and `Scripts/combat/skin.py`
      / `grip.py`. Verify the finger chains are mapped in the retargeter and the hands no longer
      stay in the bind pose.
- [ ] Fix a bug: when a mushroom is eaten and a weapon is in the next inventory slot, that weapon
      fires once after the mushroom is consumed. Starting point:
      `Scripts/combat/weapon_component/consume.py` (and `firing.py` / `inventory.py`). The fire
      press that eats the item must not also fire the weapon that becomes active; add a verifier
      check for it.
