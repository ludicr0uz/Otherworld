# dev-team queue
Run: `Scripts/dev/dev-team` (this file is its default queue)
- [x] When holding a knife or mushroom or water bottle in hand, the character holds them like a pistol which is not correct. Update the character to hold them in hand like they are carrying a normal item. Note that the holding animation should be differnt for knife (melee weapon ready to fight) vs regular consumable items. 
- [x] The SMG hold animation for the UZI that we are using should be the same as for the pistol
- [x] During exit, the character should not be able to move.
- [x] When aiming down sights with a scoped weapon (sniper rifle), the weapon animation gets
      in the way. For scoped aim, the weapon should not be visible to the player. This applies
      to sniper rifles and scopes only; regular ADS is fine.
- [x] When aiming down sights, the sound of footsteps is much louder than in third-person
      perspective. Sound volume should not change based on perspective—actions should always
      be played as if the viewer is at the character's location.
- [x] Implement lootable corpses from monsters with a UI to loot them. For now, add a 50%
      chance for monsters to drop water when killed. Implement loot tables for managing drops.
- [x] Implement a developer tab in the menu for gun tuning. Allow in-game tuning of the gun
      config table for all weapons, with changes applied immediately. Save tuned values to a
      CSV file for version control.
- [x] Implement a developer tab in the menu for monster tuning. Allow in-game tuning of monster
      specs (aggro range, aggro cone distance, patrol area, damage per hit, run speed, and
      other specs), with changes applied immediately. Save tuned values to a CSV file for
      version control.
- [x] Implement a developer tab in the menu for world tuning. Add the ability to set the
      current time of day. When the game starts, it should begin at a random time of day.
- [x] Implement a throw button. Any item in hand should be throwable. When holding the throw
      button, display the target arc. Throw the item on release.
- [x] Implement an import script for maximo downloads to be compatible with our project. Integrate the imported zombie animations into our project. '/Users/alexeysukhov/Downloads/Scary Zombie Pack.zip' '/Users/alexeysukhov/Downloads/Not So Scary Zombie Pack.zip'
- [x] Integrate the following downloaded animation packs so they are usable in the project:
      '/Users/alexeysukhov/Downloads/Universal Animation Library[Standard].zip'
      '/Users/alexeysukhov/Downloads/drive-download-20260930T225601Z-1-001.zip'
      '/Users/alexeysukhov/Downloads/drive-download-20260930T225405Z-1-001.zip'
      '/Users/alexeysukhov/Downloads/drive-download-20260930T225320Z-1-001.zip'
      '/Users/alexeysukhov/Downloads/Universal Animation Library 2[Standard].zip'
      Update the prone crawl animation, crouch animation, shotgun model, and pistol model using
      the new assets from this list.
- [x] Implement mouse cursor usage in the in-game menus.
- [x] Show bullet trajectories and aggro cones in debug mode.
- [x] When using the pick-up button, don't pick everything up. Pick up one item at a time — the
      one closest to the reticle target.
- [x] Add a kneel animation for searching bodies. Every body should be searchable, whether it has
      items or not. In the loot menu, show item icons rather than text.
- [x] Sprinting while holding ADS or shoulder aim at the same time makes the screen twitch. Fix
      the twitch.
- [x] Throwing: make the default arc higher. Expose the throw arc as a tunable parameter in the
      weapon stats dev tab. Change controls: hold the throw button to show the arc, mouse click
      to throw.
- [x] The player can fire a shot during the dying animation after they have already died. Check
      whether the same is true for NPCs. Once the dying animation starts, no further actions
      should be possible (enforce at the state machine level).
- [x] Proprietary notices (the game is the property of Ellivian Inc.; see LICENSE.txt). Static
      designer text only, no graph logic:
      a. Title screen (WBP_MainMenu, outside both panels so it shows on the title and settings
         pages), anchored bottom centre, small and dim: "© 2026 Ellivian Inc. All rights
         reserved." and under it "Confidential pre-release build. Do not distribute, stream or
         share." 
      b. Watermark on WBP_HUD's Root (outside Body, like Fps, so it shows on every screen),
         anchored bottom right, small and low-opacity: "ELLIVIAN INC. · CONFIDENTIAL" plus a
         recipient line read from a constant (e.g. WATERMARK_RECIPIENT, empty = line omitted)
         so each shared build can be stamped with who it was given to. It must not overlap the
         loot window or the inventory strip.
      Keep the strings in a small constants module (e.g. graphics_menu/legal_consts.py), add
      verifier checks (texts present, anchors, watermark outside Body, HitTestInvisible), and
      check the look with a windowed `shot showui`.
- [x] Implement a bullet impact animation on the environment.
- [x] The hitbox for bullet impacts on zombies seems forgiving (around head contact). Ensure the
      hitbox aligns with the zombie model.
- [x] Add a close-menu button to the menus that is usable with the mouse.
- [x] When zombies are attacking, they should back off slightly and sidestep between attacks in
      a natural way, so they don't stand still.
- [x] In ADS there should be weapon sway that is strictly aligned with the target. The ADS
      weapon model view should strictly align with the iron sights.
- [x] Implement a 10 second respawn delay for monsters rather than spawning right away (when
      there are fewer than 10 existing).
- [x] The character currently runs with the weapon pointing forward. Change it to a jogging
      animation without the weapon pointing forward. During shots the character should raise
      the gun. In over-the-shoulder aim, the gun should also be raised.
- [x] Implement temperature slowly going down at night (magnitude configurable in world
      tuning).
- [x] Add an axe item, include in starting inventory.
- [x] Implement attacking a tree, resulting in wood spawning beside the tree.
- [x] Add a "matches" item, include in starting inventory. Using matches with wood in the inventory should create a campfire.
      Standing near the campfire should increase the player's temperature.
- [x] Bug: when the player is in ADS and takes a hit from a monster, the ADS view jumps to a
      location that seems to be at crouch level. If the player gets hit in ADS, the target
      should stay unchanged.
- [x] ADS issue: right now the camera first goes to the ADS sight (i.e. looking down at the
      hand), then moves with the gun towards the target, so every time you ADS there is a
      quick, shaky up-to-down movement. The camera should stay on the target and the ADS gun
      image should move up to the reticle: the user keeps looking forward and the iron sights
      come into view, meeting the reticle. The ADS reticle should only be visible in dev mode
      now that the iron sights are aligned with it. Over-the-shoulder aim should still have a
      reticle.
- [x] M should not be titled graphics menu; it should be "Game Settings". Within it, implement
      a graphics tab in the dev menu. Low / medium / high / ultra should be top-level
      preconfigured options. The tab should have detailed developer-level controls for tuning:
      make all major settings that contribute to FPS and overall image appearance tunable
      (grass draw distance, tree draw distance, grass density, fog on/off and density, any
      others that can be identified, including anything to do with leaves), lighting settings,
      brightness, settings that affect the appearance of the sun (brightness or anything
      else), and settings that affect appearance during the night (stars, moon if present,
      etc.).
- [x] In the main menu options remove the graphics high / low / medium options as they are now already present in the graphics menu. When navigating into the submenu from main menu, hide the main menu options (to avoid multiple menus displayed). Submenu (such as graphics) should have a back button to take you to the main menu. Remove the hotkey buttons from the menu now that mouse control is available. When in a menu, the navigation buttons should not move the character - should only navigate the menu. For the graphics menu, put the menu location in the bottom right corner of the screen to maximize screen visibility, and reduce it's vertical height to 5 entries at a time with a scroll bar. Reduce the font size for the title to help optimize visible screen size. The units in the configs for the graphics menu should be more intuitive (I.E draw distance should be in meters)
- [x] ADS for the AKM currently shows part of the character's head. Solve this in the
      implementation for all current and future weapons, not just the AKM.
- [x] ADS is currently available for the axe and the knife. ADS should be removed for items
      and melee weapons; only guns should have it.
- [x] Thrown items should have some rotation in the air. Add a throwing animation for the
      character if one is available in our current library (if not, skip for now).
- [x] Star size is currently too large: each individual star is too large relative to the
      moon. The moon's size is good. Stars should also be laid out like a real night sky
      rather than randomly.
- [ ] Update FPS metric to be always shown regardless of whether debug mode is enabled or not. Add another custom FPS setting that persists. (So Low / Med / High / Custom as 4 options). Add a save default button for the graphics setting that should modify the csv that defines the default (that I can commit later). Defaults should be driven by the CSV.

