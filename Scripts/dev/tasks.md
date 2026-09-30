# dev-team queue
Run: `Scripts/dev/dev-team` (this file is its default queue)
- [x] When holding a knife or mushroom or water bottle in hand, the character holds them like a pistol which is not correct. Update the character to hold them in hand like they are carrying a normal item. Note that the holding animation should be differnt for knife (melee weapon ready to fight) vs regular consumable items. 
- [x] The SMG hold animation for the UZI that we are using should be the same as for the pistol
- [ ] During exit, the character should not be able to move.
- [ ] When aiming down sights with a scoped weapon (sniper rifle), the weapon animation gets
      in the way. For scoped aim, the weapon should not be visible to the player. This applies
      to sniper rifles and scopes only; regular ADS is fine.
- [ ] When aiming down sights, the sound of footsteps is much louder than in third-person
      perspective. Sound volume should not change based on perspective—actions should always
      be played as if the viewer is at the character's location.
- [ ] Implement lootable corpses from monsters with a UI to loot them. For now, add a 50%
      chance for monsters to drop water when killed. Implement loot tables for managing drops.
- [ ] Implement a developer tab in the menu for gun tuning. Allow in-game tuning of the gun
      config table for all weapons, with changes applied immediately. Save tuned values to a
      CSV file for version control.
- [ ] Implement a developer tab in the menu for monster tuning. Allow in-game tuning of monster
      specs (aggro range, aggro cone distance, patrol area, damage per hit, run speed, and
      other specs), with changes applied immediately. Save tuned values to a CSV file for
      version control.
- [ ] Implement a developer tab in the menu for world tuning. Add the ability to set the
      current time of day. When the game starts, it should begin at a random time of day.
- [ ] Implement a throw button. Any item in hand should be throwable. When holding the throw
      button, display the target arc. Throw the item on release.