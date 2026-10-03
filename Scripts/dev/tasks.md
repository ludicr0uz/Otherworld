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
- [x] Update FPS metric to be always shown regardless of whether debug mode is enabled or not. Add another custom FPS setting that persists. (So Low / Med / High / Custom as 4 options). Add a save default button for the graphics setting that should modify the csv that defines the default (that I can commit later). Defaults should be driven by the CSV.
- [x] During ADS there is unnecessary jerky movement as the camera first goes into shoulder
      aim, then transitions to ADS in two steps. Simplify this to be one smooth motion from
      the current camera location into the ADS view.
- [x] For AKM ADS hover movement, the hand holding the weapon is not synchronized with the
      weapon movement. The hand and weapon should move in sync.
- [x] For shotgun holding ADS animation, the thumb sticks out upwards which is unnatural.
      Implement different thumb placement for shotgun compared to rifles.
- [x] Fix pistol ADS where the user can see through the hand holding the pistol.
- [x] Implement a new hunting state for wendigos. When they aggro on you, they should first roar
      (using the zombie roar animation and roaring sound). They should run towards you in a
      semicircle, stopping behind nearby obstacles (e.g., trees) and coming closer to you tree
      after tree while hiding behind them. When they are at close range, they should charge
      directly at you.
- [x] Refactor the E button from a "Pick Up Items" button to a generic "Interact" button. If
      interact is pointed at an item, the item gets picked up. No functional change, just
      refactor the usage to a generic interact system for future expansion.
- [x] Create a process to generate item icons based on 3D models and create 2D images for use
      in the UI. Update existing 2D cartoony item icons with icons generated from the 3D models.
- [x] When holding a lit stick in front of a wendigo, it should prevent the wendigo from
      attacking. The wendigo should try to go around the fire to attack from the side or back.
      If it successfully moves at least 90 degrees around the torch, it should attack. After
      being held off for 30 seconds, the wendigo should run away.
- [x] When a stick is used near a campfire, it should light and become a lit stick that can be
      carried in hand like a torch until it burns out. Repurpose the scope/ADS button as a
      generic "use item" button when a non-weapon is selected. With a burning stick selected,
      pressing this button should raise the stick forward for warding away fire-afraid creatures.
- [x] Add a bleeding debuff that players have a 33% chance of getting when hit by a wendigo.
      Implement generic on-hit chance logic that can be extended to other attacks in the future.
      The bleeding debuff drains 50 health total over 3 minutes.
- [x] When a knife or axe is equipped, using it on a fire (interact button) should heat it up,
      making it glow red and keeping it hot for 20 seconds. If the player has a bleeding debuff,
      using the heated knife stops the bleeding (cauterizing the wound). Hitting a wendigo with
      a burning knife should deal double damage.
- [x] For wendigos, increase their movement speed when running in the semicircle. Alternate the
      semicircle direction at varying intervals. If a wendigo is shot, it should enter "enraged"
      mode and charge directly at the player to attack.
- [x] Sprinting should only be allowed in forward-facing directions. Disable sprinting sideways
      or backwards; allow sprinting only within 60 degrees left or right of forward.
- [x] Fix the shotgun grip hand alignment. The hand grip does not properly align with the
      shotgun; the curled fingers on the right side stick out unnaturally.
- [x] When throwing a melee weapon, it should fly in a more direct trajectory with less curve
      than other items. Axes and swords should fly in a forward spinning trajectory, like a
      throwing axe or throwing knife.
- [x] Thrown melee weapons should do damage when hitting an enemy. When hitting a tree, the
      item should get stuck in the tree and be retrievable.
- [x] When a thrown melee weapon hits an enemy, it should stick to the enemy at the impact
      area and should be retrievable in the vicinity, whether the enemy is dead or alive.
- [x] Increase the wendigo's roar audible distance to be 1.75 times its aggro range so that
      it's always heard.
- [x] Refine wendigo hunting behavior: run directly towards player if over 150m away (catch-up
      state at same hunting speed), don't use small trees to hide behind, don't pause without
      trees (keep running or charge), change strafe direction at random intervals (at least 1s)
      roughly twice as often when warded by torch, increase hunting movement speed by 30%, don't
      hide behind transparent/thin trees, increase tree search range by 50% when hunting.
- [x] In the monster tuning tab, add various tunable parameters around wendiego behavior so they
      can be adjusted through the developer menu.
- [x] When being warded away by a torch, the wendigo should roar periodically: once after 15
      seconds (with +/-2 second variance) and once at 30 seconds right before it runs away. If
      the wendigo hits the player, the 30-second timer resets.
- [x] When a fire is started, zombies in a 200 meter radius should be slowly drawn to it. Add
      a new "Drawn" state for zombies that slowly moves them towards the target (fire).
- [x] Implement dev team script to check for additional tasks after completing a task. After
      each task completion, reload the tasks.md file to detect newly added items so the script
      automatically picks up new work in subsequent sessions.
- [x] Implement a generic "taking hit" animation system for models when they take damage. When
      a thrown weapon hits a model and deals damage, it should trigger an impact animation.
      This should be generic so that any damage taken results in a "taking hit" animation. This may be implemented already, looking to confirm that this is extended to damage inflicted from thrown weapons. 
- [x] Implement the thrown trajectory to be aligned vertically with the reticle. For thrown weapons, the weapon should fly where the reticle is aimed. While holding the throw button, character should be in a "getting ready to throw" animation. 
- [x] Headshots from thrown weapons should also apply a headshot multiplier. Thrown damage should also be tunable for melee weapons in the weapon tuning menu.
- [x] Implement an exit game button in the main menu. Consolidate the menu that appears when
      pressing 'm' with the main menu into one unified menu. When pressing 'm' during gameplay,
      the same consolidated menu appears. Keep the menu placement the same as the current 'm'
      menu location.
- [x] Update player jog speed to 4m/s and sprint speed to 6m/s. Double the sprint duration available at full bar. The current recharge time should stay enough to fully recharge the sprint bar. This should be configurable in the player tuning options.
- [x] Implement a clothing system for the main character. Shirt, jacket, hat, glasses, boots, pants, gloves, backpack. Looted clothing items be stored in the current inventory slots until equipped. Using them should equip them. Do not implement drawings/models for the equipped clothing yet. Just implement the state - in inventory, vs equipped in the proper slot. Implement the "i" button to show what's currently equipped - inventory screen. Implement test clothing items to be spawned in front of the character at start on the 200 x 200 map.
- [x] Reduce the rate at which the ADS aimer hovers around target. Right now it moves around too fast making it difficult to shoot. Make this rate configurable in weapon tuning. Implement a hold breath button 
- [x] Implement wind for trees and grass, configurable in the graphics menu if its enabled or disabled. And settings around it. 
- [x] When the knife is held for the throw animation, character should hold it by the blade rather than by the handle. 
- [x] Items should not be lootable if they are vertically too far away from the character. It seems right now only the horizontal distnace is checked. 
- [x] Generate a new adventurer model with meshy API in boxers as default. This will be a preparation for implementing clothing.
- [ ] Re-work how inventory is organized. There will be item in hands (center slot on the scren)
      + 4 weapon slots (storage slots) - shown underneat it + 10 backpack slots (backpack visible
      when I is pressed). Hand slot always visible, and 4 weapon slots always visible underneath
      it. The selected weapon is in the hand slot. If no weapon is selected, pressing one moves
      primary weapon to hand slot and the weapon is now active. Pressing 1 again will put the
      weapon back into the weapon slot and the weapon is inactive. Character then becomes
      unarmed. Picking up items puts them straight into the backpack slot if available. In hands
      if no backpack slot is available. Items can be moved from the backpack slot to hands to be
      used. Buttons 5,6,7,8,9 can be mapped to 5 backpack slots to be able to quickly bring those
      to hands. Backpack items and clothing items should be visible bottom right of the screen.
      Clothing slots should be above the backpack slots bottom right. Always visible, do not need
      to press I to show them. There is now going to be a primary weapon slot, secondary weapon
      slot, pistol slot, melee weapon slot. When inventory is selected, user can drag items from
      backpack into either weapon slots or hand slot or vice versa. New button mapping - 1 Will be
      to select primary weapon. 2 - select secondary weapon, 3 select pistol, 4 select melee.
      Backpack slots are not visible by default, but are shown when the I button is pressed for
      inventory. Hand slot & active items: All items (weapons, consumables, tools, torches) can
      be in the hand slot. When navigating through the backpack, selecting an item brings it to
      the hand slot. When a weapon is in the hand slot and a quick-slot button (5-9) is pressed
      for a backpack item, the weapon goes to a slot if one is available (primary or secondary).
      Weapon slot organization: Primary/secondary slots hold SMGs/Rifles/ARs. Pistol slot holds
      all pistols. Melee slot holds all melee weapons. Weapon slots can be empty. Quick slots
      (5-9): The top 5 backpack slots are mapped to buttons 5-9 (slots 1-5). Picking up items:
      If the backpack is full and you already have a weapon active in the hand slot, you cannot
      pick up the item. Drag-and-drop constraints: Only weapons can be dragged into weapon slots.
      Consumables cannot be dragged into weapon slots; hotkeyed backpack slots will be used for
      consumables. Clothing system: Use existing clothing slot system.
- [ ] There seems to be a bug introduced in recent commits where monster textures were lost.
      player character and monsters are gray. Fix that, and update the character model to the new
      one that was generated in the recent commit (5c6c53b).
- [ ] Wind was implement recently but it is in random direction. Wind motion across objects
      should be realistic rather than all items blowing in the same direciton.
- [ ] Improve the Menu options to appear more professional, rather than "tuning" call it
      "Settings", I.E Monster Settings, Gun Settings. Capitalize first letters.
- [ ] Players default movement should be a jog rather than a walk. Right now the character walks.
- [ ] Pressing I should have a hover image of the character facing forward as part of the
      character menu screen.