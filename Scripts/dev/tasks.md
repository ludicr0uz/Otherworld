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
- [x] Re-work how inventory is organized. There will be item in hands (center slot on the scren)
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
- [x] There seems to be a bug introduced in recent commits where monster textures were lost.
      player character and monsters are gray. Fix that, and update the character model to the new
      one that was generated in the recent commit (5c6c53b).
- [x] Wind was implement recently but it is in random direction. Wind motion across objects
      should be realistic rather than all items blowing in the same direciton.
- [x] Improve the Menu options to appear more professional, rather than "tuning" call it
      "Settings", I.E Monster Settings, Gun Settings. Capitalize first letters.
- [x] Players default movement should be a jog rather than a walk. Right now the character walks.
- [x] Pressing I should have a hover image of the character facing forward as part of the
      character menu screen.
- [x] Update the worn clothing inventory to show clothing icons rather than text. Should be the same icon format as the inventory. Remove text labels for primary / secondary / gun / knife weapon slots. Create translucent icons for the weapon categories (AR / AR / Gun / Knife) if there are no items in those slots. Always show clothing and inventory (should not be hidden until "i" is pressed). If I is pressed, allow mouse drag to move items around, including putting them into inventory slots or hands. 
- [x] Add item highlighting when items are on the ground (configurable in the world menu as
      on/off). Implement a glimmer if there is an item on the floor.
- [x] Improve the item icon generation processor to make the items look more realistic, and add
      a thin black contour around the item models.
- [x] If the player runs too far away from his original location, the wendigo should go
      directly into the "charge at the player" state.
- [x] Disable the scroll wheel in menus. Allow vertical drag for the vertical scrollbar.
- [x] Remove the Food / H2O / Temperature labels (we already have icons). Update the food icon
      to a chicken leg rather than a mushroom.
- [x] When I (inventory) is selected, dragging an item should hold the item attached to the
      mouse cursor as it is moved to the destination. Dropping it outside of the inventory area
      should result in dropping the item on the floor. While the mouse is moving in the
      drag-item state, it should not rotate the screen.
- [x] Instead of "NPCs killed", update the label to "Monster Kills".
- [x] Wendigos should not make sound when they are patrolling.
- [x] When looting a weapon, if there is an open weapon slot for it, it should prioritize going
      there before the inventory. When retrieving a melee weapon from a stuck state (e.g. an NPC
      or a tree), if the hands are empty, the weapon should go into the hand slot.
- [x] Reduce footsteps volume. Add a sounds menu where the volume for each sound is tunable.
- [x] In the published build, when the game launches, the menu is not clickable until
      alt-tabbing out and back into the game, or first pressing a keyboard button. Fix this so
      the menu is clickable immediately on launch.
- [x] In the menus, the Escape button should navigate backwards (equivalent to Back). Rename
      "Settings" in the main menu to "Controls". If there is a saved state, the main menu should
      say "Continue Game" rather than "New Game".
- [x] The reticle turns red sometimes. Always keep the reticle white. If there is a headshot,
      show an X around the reticle.
- [x] The Q button should navigate through inventory items, not through guns.
- [x] The item shine is too bright. Make it appear subtly, and only when the character is near
      the items: a slight glimmer that appears and disappears.
- [x] The wendigo should roar when transitioning from the hunting state to the charging state.
      Just the sound, no animation, to avoid a delay in attacking.
- [x] Pistol ADS is too close to the pistol. It should partially show the hands with the pistol.
- [x] The mouse bug at game start is not resolved. It seems that when the game starts, the mouse
      is not within the game window. After alt-tabbing out and alt-tabbing back in, the mouse
      issue gets resolved. Fix it so the mouse works in the game window from launch.
- [x] The transparent weapon slot icons on the items UI use actual weapon images, which is not
      intended. Update them to be drawn icons of those weapon types rather than based on the
      actual weapon appearance, i.e. similar to how the food / water / temperature icons are
      generated.
- [x] Update the headshot multiplier to be 1.75 across the board.
- [x] Sounds refactor: refactor sound so that sound mappings can be tuned without needing to
      rebuild other modules (unless new sound areas are added). All sound definitions and logic
      should be in one place, with a module for each area of sound it is responsible for: i.e. a
      top-level sound module, with sound_weapons, sound_monsters, sound_items and sound_world
      modules where the mappings and the implementations of the sound logic are defined.
- [x] Monster sounds:
      a. Zombie growls 1, 2 and 4 can be used during an attack. Zombie growl 10 can be used when
         a zombie aggros. All other zombie growls should be played intermittently while the
         zombie is patrolling.
      b. Just like the wendigo, allow zombie sounds to be heard from farther away, especially
         the aggro sound. Right now zombies often aggro but you can't hear them aggro.
      c. Add footstep sounds for zombies and the wendigo that are audible close by; right now
         you don't hear them running up. Make the footstep sound concept generic so it can be
         used for all NPCs and players.
- [x] World / player sounds:
      a. Wire moving-through-tall-grass sounds when a player or NPC walks through a bush (in
         the world sound module).
      b. Wire breath_fast_01 to play when energy is at 0 but the player presses the run button.
         Wire heartbeat_panic to play when on low life.
      c. Wire Jo-mungus as the food eating sound.
      d. Axe / knife impact sounds are too gory and need different slicing ones: use the stab
         sound for now. For headshot kills with a thrown axe, use the gore_weapon sound, the
         1.9 second version.
      e. The AKM is still too quiet even at a volume setting of 2. Improve the volume settings
         to allow going beyond 2.
      f. Play the sound associated with the item's type when moving items in the inventory,
         moving them into the hand slot, or switching weapons (i.e. play the appropriate sound
         when pulling out a weapon or moving items within the inventory).
- [x] Mouse sensitivity seems to be different when walking compared with standing and running.
      It should be the same standing, walking and running.
- [x] My prod and dev version of the game seems not responsive to mouse and keyboard clicks to start a new game. I adjusted the vertical recoil for AKM. I also hit save and exit (but I am not sure if i pressed that before the issue started in the prod version of the game). Understand the root cause and fix it
- [x] Zombie patrol sounds now starts too far away. Add a config for minimal range to hear patrol level sounds. 
- [x] When zombies going through bushes they don't make bush sounds, update bush sounds to be audible for everyone
- [x] In menus, update the back button to be the top option. Update up/down cotrols to allow overflow. I.E when in bottom most position, going down, brings the cursor to the top of the menu. At the top of the menu, going up brings the selection cursor to the bottom of the menu. 
- [x] When operating in prod full screen mode, the bottom part of the health bars and icons is cut off
## Multiplayer, phase 0: foundations (strategy: serversupportsysdesign.md; the rest of the
## queue, phases 6-8, waits in Scripts/dev/plans/multiplayer_tasks.md)
- [x] M1. Add a real C++ module to the project. Create `Source/` from the generated files in
      `Intermediate/Source` (Otherworld runtime module, Editor, Client and Server targets),
      add the module to `Otherworld.uproject`, and compile the editor target on this Mac
      against the installed UE 5.8. The module holds no gameplay yet. Done when: the editor
      opens the project with the compiled module, the full verifier sweep is unchanged, and
      a `--game` smoke run of `Lvl_Forest_200m` is clean. Record the compile command, the
      time it takes and the Xcode version in a new `Source/CLAUDE.md`, and add `Source/` to
      the package table in the root `CLAUDE.md`. If the installed Xcode cannot compile for
      UE 5.8, stop and report exactly what version is needed; do not upgrade Xcode.
      Design goal: Give the project a place for C++, which predicted movement, lag compensation
      and the RPC helper all need and Blueprints cannot do. It should add no behaviour: its value
      is that every later C++ task has a module that already compiles.
      Big picture: this is task M1 of 36 in the multiplayer project, phase 0 of 0-8 (foundations).
      The project turns this single-player survival game into one that also runs as a PvP game on
      a dedicated server (32-64 players, teams or solo, characters that persist), with single
      player still shipping from the same code. Phases 0-7 are built and proved on this Mac;
      hosting on GCP comes after and is not part of any task here. This phase is done when the
      tools to build and test networked gameplay exist, and two players can see each other. The
      strategy is `serversupportsysdesign.md`: section 1 the target, 4.1 authority, 4.2 where
      state lives, 4.8 the two modes, 7 the whole task list; read it before designing, and build
      for the later phases rather than for this task alone. Do not do later tasks' work here.
      Both modes: single player and multiplayer both ship. Follow the standing requirement
      at the top of `Scripts/dev/plans/multiplayer_tasks.md` and `serversupportsysdesign.md` 4.8.
      Local only: use no GCP or other cloud resource. Never run gcloud, gsutil or anything in
      `Scripts/server/gcp`; if the task seems to need one, stop and report instead.
      effort: high
- [x] M2. Make RPCs and replicated variables authorable from Python. `K2Node_Event`'s
      `FunctionFlags` is a bare `UPROPERTY()` that Python cannot set, so add an editor-only
      C++ module (`OtherworldEditor`) with a BlueprintCallable library that sets a custom
      event's net flags (Server, Client, NetMulticast, Reliable) and reads them back. Wrap it
      in `Scripts/uebp` with helpers to: add a Server / Client / Multicast custom event; mark
      a variable Replicated or RepNotify (creating the OnRep function); mark a component or
      actor as replicating. Add the nodes the mode questions need to the node catalog:
      HasAuthority / SwitchHasAuthority, IsLocallyControlled, IsStandalone, IsDedicatedServer,
      GetOwningPlayerPawn. Done when: a throwaway test Blueprint built by a script has one
      event of each kind and one RepNotify variable, a verifier reads the flags back, and
      `check_node_catalog.py` passes. Document the helpers in `Scripts/uebp`'s CLAUDE.md.
      Design goal: Keep the project's way of working (Blueprints authored by Python builders)
      valid for networked code. Without this every RPC would have to be clicked together by hand
      in the editor and could not be rebuilt or verified.
      Big picture: this is task M2 of 36 in the multiplayer project, phase 0 of 0-8 (foundations).
      The project turns this single-player survival game into one that also runs as a PvP game on
      a dedicated server (32-64 players, teams or solo, characters that persist), with single
      player still shipping from the same code. Phases 0-7 are built and proved on this Mac;
      hosting on GCP comes after and is not part of any task here. This phase is done when the
      tools to build and test networked gameplay exist, and two players can see each other. The
      strategy is `serversupportsysdesign.md`: section 1 the target, 4.1 authority, 4.2 where
      state lives, 4.8 the two modes, 7 the whole task list; read it before designing, and build
      for the later phases rather than for this task alone. The tasks before this one are done or
      in the same queue; this run's progress file and the git log say what they built. Do not do
      later tasks' work here.
      Both modes: single player and multiplayer both ship. Follow the standing requirement
      at the top of `Scripts/dev/plans/multiplayer_tasks.md` and `serversupportsysdesign.md` 4.8.
      Local only: use no GCP or other cloud resource. Never run gcloud, gsutil or anything in
      `Scripts/server/gcp`; if the task seems to need one, stop and report instead.
      effort: high
- [x] M3. Extend `Scripts/dev/uepy.py` and `uepylib` with a network run:
      `uepy.py --net --clients N [--windowed] [--probe <probe>] [--seconds S]` starts one
      editor-binary `-server` process on a level (default `Lvl_Forest_200m`) and N clients
      that connect to `127.0.0.1`, keeps one log per process, kills them all at the end and
      prints one summary (joins, errors, "Accessed None" counts per process). A probe must be
      able to say where it runs (server, client 1, client 2) and the run collects every
      process's results into one report. Clients are `-nullrhi` unless `--windowed`. Refuse
      to start while a PIE session runs, like the rest of uepy. Add
      `Scripts/probes/probe_net_join.py`: the server reports N joined players, each with a
      possessed pawn; each client reports it controls a pawn. Unit-test the argument and
      report code in `Scripts/dev/tests`. Document `--net` in the root `CLAUDE.md` run section.
      Design goal: Make a multiplayer check as cheap and repeatable as a single-player one. Every
      later task proves itself with a `--net` probe, so this harness is the measuring instrument
      for the whole project.
      Big picture: this is task M3 of 36 in the multiplayer project, phase 0 of 0-8 (foundations).
      The project turns this single-player survival game into one that also runs as a PvP game on
      a dedicated server (32-64 players, teams or solo, characters that persist), with single
      player still shipping from the same code. Phases 0-7 are built and proved on this Mac;
      hosting on GCP comes after and is not part of any task here. This phase is done when the
      tools to build and test networked gameplay exist, and two players can see each other. The
      strategy is `serversupportsysdesign.md`: section 1 the target, 4.1 authority, 4.2 where
      state lives, 4.8 the two modes, 7 the whole task list; read it before designing, and build
      for the later phases rather than for this task alone. The tasks before this one are done or
      in the same queue; this run's progress file and the git log say what they built. Do not do
      later tasks' work here.
      Both modes: single player and multiplayer both ship. Follow the standing requirement
      at the top of `Scripts/dev/plans/multiplayer_tasks.md` and `serversupportsysdesign.md` 4.8.
      Local only: use no GCP or other cloud resource. Never run gcloud, gsutil or anything in
      `Scripts/server/gcp`; if the task seems to need one, stop and report instead.
      effort: high
- [x] M4. Spike and conventions. Run `uepy.py --net --clients 2` on `Lvl_Forest_200m` and make
      the minimum changes for each client to see the other's character walk and jump (default
      CharacterMovement replication; nothing custom). Write `Scripts/net/CLAUDE.md`: the
      authority pattern, the three mode questions and the mode table from
      `serversupportsysdesign.md` 4.8, how to write a `--net` probe, and a "what broke in the
      spike" list with one line per system that misbehaved (this list feeds the later tasks:
      correct their wording in this file if the spike contradicts it). Add
      `probe_net_see_each_other.py`: client 1 moves, client 2 sees client 1's pawn at the new
      place. Record the memory each process used, replacing the estimates in section 5 of the
      design doc.
      Design goal: Replace guesses with facts before the real work starts: prove the engine's
      stock replication carries two players, measure memory, and record what breaks so the later
      tasks aim at real problems.
      Big picture: this is task M4 of 36 in the multiplayer project, phase 0 of 0-8 (foundations).
      The project turns this single-player survival game into one that also runs as a PvP game on
      a dedicated server (32-64 players, teams or solo, characters that persist), with single
      player still shipping from the same code. Phases 0-7 are built and proved on this Mac;
      hosting on GCP comes after and is not part of any task here. This phase is done when the
      tools to build and test networked gameplay exist, and two players can see each other. The
      strategy is `serversupportsysdesign.md`: section 1 the target, 4.1 authority, 4.2 where
      state lives, 4.8 the two modes, 7 the whole task list; read it before designing, and build
      for the later phases rather than for this task alone. The tasks before this one are done or
      in the same queue; this run's progress file and the git log say what they built. Do not do
      later tasks' work here.
      Both modes: single player and multiplayer both ship. Follow the standing requirement
      at the top of `Scripts/dev/plans/multiplayer_tasks.md` and `serversupportsysdesign.md` 4.8.
      Local only: use no GCP or other cloud resource. Never run gcloud, gsutil or anything in
      `Scripts/server/gcp`; if the task seems to need one, stop and report instead.
## Multiplayer, phase 1: the framework for more than one player
- [x] M5. Pause is a single-player feature. Every `SetGamePaused` path (title menu, M menu,
      loot window, any other the grep for `FN_SET_PAUSED` finds) pauses only in standalone;
      as a client the same UI opens as an overlay over a running world, and the character
      takes no movement or fire input while a menu owns the keyboard. Done when: the existing
      pause verifiers and `--game` probes pass unchanged, and a `--net` probe shows a client
      opening M while the server's world time keeps advancing.
      Design goal: A shared world cannot stop for one player. Pause becomes a property of single
      player only, without changing what a solo player experiences.
      Big picture: this is task M5 of 36 in the multiplayer project, phase 1 of 0-8 (the framework
      for more than one player). The project turns this single-player survival game into one that
      also runs as a PvP game on a dedicated server (32-64 players, teams or solo, characters that
      persist), with single player still shipping from the same code. Phases 0-7 are built and
      proved on this Mac; hosting on GCP comes after and is not part of any task here. This phase
      is done when no system assumes there is exactly one player, one HUD or a pausable world. The
      strategy is `serversupportsysdesign.md`: section 1 the target, 4.1 authority, 4.2 where
      state lives, 4.8 the two modes, 7 the whole task list; read it before designing, and build
      for the later phases rather than for this task alone. The tasks before this one are done or
      in the same queue; this run's progress file and the git log say what they built. Do not do
      later tasks' work here.
      Both modes: single player and multiplayer both ship. Follow the standing requirement
      at the top of `Scripts/dev/plans/multiplayer_tasks.md` and `serversupportsysdesign.md` 4.8.
      Local only: use no GCP or other cloud resource. Never run gcloud, gsutil or anything in
      `Scripts/server/gcp`; if the task seems to need one, stop and report instead.
- [x] M6. The title menu offers both modes. Its top level becomes "Single Player",
      "Multiplayer", "Controls" and "Exit Game" (plus whatever else it holds today, unchanged).
      a. "Single Player" opens a page holding today's entry exactly: "Continue Game" when a
         saved profile exists, otherwise "New Game", starting the standalone game as now.
      b. "Multiplayer" opens a page with a server address field (default `127.0.0.1:7777`,
         remembered between runs in the local settings, not in the character profile) and a
         "Join Server" row that travels to that server. While connecting it says so; when
         the connection fails or later drops, the player is returned to the title with the
         reason shown on this page.
      c. Both pages follow the menu's existing rules: Back is the top row, Escape goes back,
         a page hides the top-level rows, mouse and keyboard both work, up/down wrap.
      d. The M menu in play shows which mode the session is in. In multiplayer its exit row
         reads "Leave Server" and returns to the title without touching the single-player
         profile; in single player "Save and Exit" is as today.
      e. A client started with an address on the command line skips the title and joins.
         The title menu must not pause or block a client that is already connected.
      Done when: the menu verifiers cover both pages and their rows; a `--game` probe enters
      through "Single Player" and plays as before; a `--net --windowed` probe joins through
      "Multiplayer", leaves with "Leave Server", and then starts a single-player game from
      the same title without restarting the process; and a join to a dead address returns
      to the title with a reason.
      Design goal: Make the two modes a visible, equal choice for the player, and make moving
      between them safe: one title menu, two entries, two separate characters.
      Big picture: this is task M6 of 36 in the multiplayer project, phase 1 of 0-8 (the framework
      for more than one player). The project turns this single-player survival game into one that
      also runs as a PvP game on a dedicated server (32-64 players, teams or solo, characters that
      persist), with single player still shipping from the same code. Phases 0-7 are built and
      proved on this Mac; hosting on GCP comes after and is not part of any task here. This phase
      is done when no system assumes there is exactly one player, one HUD or a pausable world. The
      strategy is `serversupportsysdesign.md`: section 1 the target, 4.1 authority, 4.2 where
      state lives, 4.8 the two modes, 7 the whole task list; read it before designing, and build
      for the later phases rather than for this task alone. The tasks before this one are done or
      in the same queue; this run's progress file and the git log say what they built. Do not do
      later tasks' work here.
      Both modes: single player and multiplayer both ship. Follow the standing requirement
      at the top of `Scripts/dev/plans/multiplayer_tasks.md` and `serversupportsysdesign.md` 4.8.
      Local only: use no GCP or other cloud resource. Never run gcloud, gsutil or anything in
      `Scripts/server/gcp`; if the task seems to need one, stop and report instead.
      effort: high
- [x] M7. Move per-player and shared state off the GameMode, which clients never have. Per
      `serversupportsysdesign.md` 4.2: the kill count and "is dead" become per-player on a
      new `BP_OtherworldPlayerState`; shared read-by-clients state (debug mode, anything the
      HUD reads) moves to a new `BP_OtherworldGameState`, replicated; the noise record,
      gun-drop streams and spawn bookkeeping stay on the GameMode because only the server
      reads them. Replace every client-side GameMode read (the `NODE_CAST_GAME_MODE` /
      `FN_GET_GAME_MODE` hits) with the new home. Done when: no graph that can run on a client
      reads the GameMode (add a verifier check for it), single-player behaviour is unchanged,
      and a `--net` probe shows each client's HUD reading its own kill count.
      Design goal: Put each piece of state where every machine that needs it can read it: per-
      player facts on the PlayerState, shared facts on the GameState, server-only bookkeeping on
      the GameMode.
      Big picture: this is task M7 of 36 in the multiplayer project, phase 1 of 0-8 (the framework
      for more than one player). The project turns this single-player survival game into one that
      also runs as a PvP game on a dedicated server (32-64 players, teams or solo, characters that
      persist), with single player still shipping from the same code. Phases 0-7 are built and
      proved on this Mac; hosting on GCP comes after and is not part of any task here. This phase
      is done when no system assumes there is exactly one player, one HUD or a pausable world. The
      strategy is `serversupportsysdesign.md`: section 1 the target, 4.1 authority, 4.2 where
      state lives, 4.8 the two modes, 7 the whole task list; read it before designing, and build
      for the later phases rather than for this task alone. The tasks before this one are done or
      in the same queue; this run's progress file and the git log say what they built. Do not do
      later tasks' work here.
      Both modes: single player and multiplayer both ship. Follow the standing requirement
      at the top of `Scripts/dev/plans/multiplayer_tasks.md` and `serversupportsysdesign.md` 4.8.
      Local only: use no GCP or other cloud resource. Never run gcloud, gsutil or anything in
      `Scripts/server/gcp`; if the task seems to need one, stop and report instead.
      effort: high
- [x] M8. Replace `GetPlayerPawn(0)` in everything a player owns: the HUD and every widget use
      the owning player's pawn, components use their owner, the animation graphs use their
      own pawn. (World actors and NPCs are M9.) Add a verifier check that fails on a new
      `FN_GET_PLAYER_PAWN` use in those packages. Done when: the sweep passes and a `--net
      --clients 2` probe shows each client's HUD bars following its own character, not
      player 0's.
      Design goal: End the assumption that the player is player 0 in everything a player owns, so
      each client's screen is about its own character.
      Big picture: this is task M8 of 36 in the multiplayer project, phase 1 of 0-8 (the framework
      for more than one player). The project turns this single-player survival game into one that
      also runs as a PvP game on a dedicated server (32-64 players, teams or solo, characters that
      persist), with single player still shipping from the same code. Phases 0-7 are built and
      proved on this Mac; hosting on GCP comes after and is not part of any task here. This phase
      is done when no system assumes there is exactly one player, one HUD or a pausable world. The
      strategy is `serversupportsysdesign.md`: section 1 the target, 4.1 authority, 4.2 where
      state lives, 4.8 the two modes, 7 the whole task list; read it before designing, and build
      for the later phases rather than for this task alone. The tasks before this one are done or
      in the same queue; this run's progress file and the git log say what they built. Do not do
      later tasks' work here.
      Both modes: single player and multiplayer both ship. Follow the standing requirement
      at the top of `Scripts/dev/plans/multiplayer_tasks.md` and `serversupportsysdesign.md` 4.8.
      Local only: use no GCP or other cloud resource. Never run gcloud, gsutil or anything in
      `Scripts/server/gcp`; if the task seems to need one, stop and report instead.
      effort: high
- [x] M9. Replace `GetPlayerPawn(0)` in world actors and NPC code with an explicit choice:
      a shared helper (in `Scripts/net`) for "nearest living player to this point" and "all
      living players", used by item glimmer, campfires, spawners, senses and anything else
      the grep finds outside the packages M8 covered. Target choice stays simple here (nearest
      player); the full NPC work is M27. Done when: no `FN_GET_PLAYER_PAWN` is left in the
      builders, the sweep passes, and single-player probes are unchanged.
      Design goal: End the assumption that there is one player in the world's own actors, with one
      shared way to ask who is nearby that later tasks can refine.
      Big picture: this is task M9 of 36 in the multiplayer project, phase 1 of 0-8 (the framework
      for more than one player). The project turns this single-player survival game into one that
      also runs as a PvP game on a dedicated server (32-64 players, teams or solo, characters that
      persist), with single player still shipping from the same code. Phases 0-7 are built and
      proved on this Mac; hosting on GCP comes after and is not part of any task here. This phase
      is done when no system assumes there is exactly one player, one HUD or a pausable world. The
      strategy is `serversupportsysdesign.md`: section 1 the target, 4.1 authority, 4.2 where
      state lives, 4.8 the two modes, 7 the whole task list; read it before designing, and build
      for the later phases rather than for this task alone. The tasks before this one are done or
      in the same queue; this run's progress file and the git log say what they built. Do not do
      later tasks' work here.
      Both modes: single player and multiplayer both ship. Follow the standing requirement
      at the top of `Scripts/dev/plans/multiplayer_tasks.md` and `serversupportsysdesign.md` 4.8.
      Local only: use no GCP or other cloud resource. Never run gcloud, gsutil or anything in
      `Scripts/server/gcp`; if the task seems to need one, stop and report instead.
      effort: high
- [x] M10. Input belongs to the locally controlled pawn. Every key poll (`FN_WAS_PRESSED`,
      `FN_IS_KEY_DOWN`) and every input-driven Tick branch runs only where the pawn is
      locally controlled, so a server never polls keys and a client never drives another
      player's character. The HUD and its widgets are created only for the local controller,
      never on a dedicated server. Done when: a dedicated-server log has no widget creation
      and no input-poll errors, the sweep passes, and in a 2-client run pressing fire on
      client 1 does nothing to client 2's character.
      Design goal: Separate the machine that reads a player's keys from the machines that only
      watch that player, so input never leaks between characters and a server has no HUD.
      Big picture: this is task M10 of 36 in the multiplayer project, phase 1 of 0-8 (the
      framework for more than one player). The project turns this single-player survival game into
      one that also runs as a PvP game on a dedicated server (32-64 players, teams or solo,
      characters that persist), with single player still shipping from the same code. Phases 0-7
      are built and proved on this Mac; hosting on GCP comes after and is not part of any task
      here. This phase is done when no system assumes there is exactly one player, one HUD or a
      pausable world. The strategy is `serversupportsysdesign.md`: section 1 the target, 4.1
      authority, 4.2 where state lives, 4.8 the two modes, 7 the whole task list; read it before
      designing, and build for the later phases rather than for this task alone. The tasks before
      this one are done or in the same queue; this run's progress file and the git log say what
      they built. Do not do later tasks' work here.
      Both modes: single player and multiplayer both ship. Follow the standing requirement
      at the top of `Scripts/dev/plans/multiplayer_tasks.md` and `serversupportsysdesign.md` 4.8.
      Local only: use no GCP or other cloud resource. Never run gcloud, gsutil or anything in
      `Scripts/server/gcp`; if the task seems to need one, stop and report instead.
      effort: high
- [x] M11. Move gameplay decisions out of the HUD graphs. The loot take, inventory drags and
      drops, wear and take off, and "Save and Exit" currently change game state from widget
      graphs. Give each a function on the pawn or its component that the widget calls, with
      the widget left doing display only. Do not make them RPCs yet (M18, M23 and M24 do);
      this task only moves the logic so those tasks have one place to change. Done when: the
      sweep and all existing probes pass with no behaviour change.
      Design goal: Make widgets display-only, so each player action has exactly one place in the
      character's code that later tasks turn into a server request.
      Big picture: this is task M11 of 36 in the multiplayer project, phase 1 of 0-8 (the
      framework for more than one player). The project turns this single-player survival game into
      one that also runs as a PvP game on a dedicated server (32-64 players, teams or solo,
      characters that persist), with single player still shipping from the same code. Phases 0-7
      are built and proved on this Mac; hosting on GCP comes after and is not part of any task
      here. This phase is done when no system assumes there is exactly one player, one HUD or a
      pausable world. The strategy is `serversupportsysdesign.md`: section 1 the target, 4.1
      authority, 4.2 where state lives, 4.8 the two modes, 7 the whole task list; read it before
      designing, and build for the later phases rather than for this task alone. The tasks before
      this one are done or in the same queue; this run's progress file and the git log say what
      they built. Do not do later tasks' work here.
      Both modes: single player and multiplayer both ship. Follow the standing requirement
      at the top of `Scripts/dev/plans/multiplayer_tasks.md` and `serversupportsysdesign.md` 4.8.
      Local only: use no GCP or other cloud resource. Never run gcloud, gsutil or anything in
      `Scripts/server/gcp`; if the task seems to need one, stop and report instead.
## Multiplayer, phase 2: movement
- [x] M12. Predicted movement states in C++. Subclass `UCharacterMovementComponent` in the
      `Otherworld` module with sprint, prone and aim-walk as saved-move flags, so the owning
      client predicts them and the server agrees; the 60-degree forward sprint rule and the
      jog and sprint speeds keep their tuning-table values. Stamina drain and recharge move
      to the server with the client predicting. Reparent the player character onto it by
      builder script. Done when: single-player feel is unchanged (the player-tuning probes
      pass), and a `--net` run with simulated lag (`Net PktLag=120`) shows no rubber-banding
      on sprint start, sprint stop, going prone and aiming, checked from the correction
      count in the client log.
      Design goal: Movement states must be predicted by the owning client and confirmed by the
      server, or they feel laggy or can be cheated. The engine only supports that through its C++
      movement component.
      Big picture: this is task M12 of 36 in the multiplayer project, phase 2 of 0-8 (movement).
      The project turns this single-player survival game into one that also runs as a PvP game on
      a dedicated server (32-64 players, teams or solo, characters that persist), with single
      player still shipping from the same code. Phases 0-7 are built and proved on this Mac;
      hosting on GCP comes after and is not part of any task here. This phase is done when moving
      feels instant for the player, is decided by the server, and looks right to everyone else.
      The strategy is `serversupportsysdesign.md`: section 1 the target, 4.1 authority, 4.2 where
      state lives, 4.8 the two modes, 7 the whole task list; read it before designing, and build
      for the later phases rather than for this task alone. The tasks before this one are done or
      in the same queue; this run's progress file and the git log say what they built. Do not do
      later tasks' work here.
      Both modes: single player and multiplayer both ship. Follow the standing requirement
      at the top of `Scripts/dev/plans/multiplayer_tasks.md` and `serversupportsysdesign.md` 4.8.
      Local only: use no GCP or other cloud resource. Never run gcloud, gsutil or anything in
      `Scripts/server/gcp`; if the task seems to need one, stop and report instead.
      effort: high
- [x] M13. Other players animate correctly. Replicate what the animation graph needs from
      other players' characters: stance (stand, crouch, prone), aim pitch, the aim mode
      (hip, shoulder, ADS), the held item's pose class and the "raising to fire" state.
      Done when: a `--net --windowed --clients 2` capture shows client 2 seeing client 1
      crouch, go prone, aim up and down and hold a rifle, a pistol, a knife and an item with
      the right pose.
      Design goal: A player reads other players by their animation. Replicate the small set of
      facts the animation graph needs, and nothing more.
      Big picture: this is task M13 of 36 in the multiplayer project, phase 2 of 0-8 (movement).
      The project turns this single-player survival game into one that also runs as a PvP game on
      a dedicated server (32-64 players, teams or solo, characters that persist), with single
      player still shipping from the same code. Phases 0-7 are built and proved on this Mac;
      hosting on GCP comes after and is not part of any task here. This phase is done when moving
      feels instant for the player, is decided by the server, and looks right to everyone else.
      The strategy is `serversupportsysdesign.md`: section 1 the target, 4.1 authority, 4.2 where
      state lives, 4.8 the two modes, 7 the whole task list; read it before designing, and build
      for the later phases rather than for this task alone. The tasks before this one are done or
      in the same queue; this run's progress file and the git log say what they built. Do not do
      later tasks' work here.
      Both modes: single player and multiplayer both ship. Follow the standing requirement
      at the top of `Scripts/dev/plans/multiplayer_tasks.md` and `serversupportsysdesign.md` 4.8.
      Local only: use no GCP or other cloud resource. Never run gcloud, gsutil or anything in
      `Scripts/server/gcp`; if the task seems to need one, stop and report instead.
## Multiplayer, phase 3: health, damage, death
- [x] M14. `BP_HealthComponent` is owned by the server. Health and "is dead" replicate; damage
      is applied only with authority and always carries an instigator (the damaging
      controller) and a cause; clients learn of a change by RepNotify and play the hit
      reaction, the HUD bar and the low-health heartbeat from it. Wanderers use the same
      component unchanged. Done when: the sweep passes, single-player damage probes are
      unchanged, and in a `--net` run a wanderer hitting client 1 lowers the bar on client 1
      only.
      Design goal: Health is the value cheaters most want to control, so only the server may
      change it, and every change must say who caused it so kills can be credited.
      Big picture: this is task M14 of 36 in the multiplayer project, phase 3 of 0-8 (health,
      damage, death). The project turns this single-player survival game into one that also runs
      as a PvP game on a dedicated server (32-64 players, teams or solo, characters that persist),
      with single player still shipping from the same code. Phases 0-7 are built and proved on
      this Mac; hosting on GCP comes after and is not part of any task here. This phase is done
      when the server decides who is hurt and who dies, and players can fight each other. The
      strategy is `serversupportsysdesign.md`: section 1 the target, 4.1 authority, 4.2 where
      state lives, 4.8 the two modes, 7 the whole task list; read it before designing, and build
      for the later phases rather than for this task alone. The tasks before this one are done or
      in the same queue; this run's progress file and the git log say what they built. Do not do
      later tasks' work here.
      Both modes: single player and multiplayer both ship. Follow the standing requirement
      at the top of `Scripts/dev/plans/multiplayer_tasks.md` and `serversupportsysdesign.md` 4.8.
      Local only: use no GCP or other cloud resource. Never run gcloud, gsutil or anything in
      `Scripts/server/gcp`; if the task seems to need one, stop and report instead.
      effort: high
- [x] M16. Death in each mode. Standalone keeps today's path exactly (the profile is deleted,
      back to the title). As a client of a server: the dying animation and ragdoll play on
      every client, no action is possible once dying starts, everything carried and worn
      goes onto a lootable corpse (reuse the wanderer corpse-loot window), and after 10
      seconds the player respawns at a random player start with the starting inventory. The
      character itself survives: this is the default from the design doc, section 1. Done
      when: both paths are probed.
      Design goal: Death is where the two modes legitimately differ. Give multiplayer a death that
      keeps the player in the session, without disturbing single player's permanent one.
      Big picture: this is task M16 of 36 in the multiplayer project, phase 3 of 0-8 (health,
      damage, death). The project turns this single-player survival game into one that also runs
      as a PvP game on a dedicated server (32-64 players, teams or solo, characters that persist),
      with single player still shipping from the same code. Phases 0-7 are built and proved on
      this Mac; hosting on GCP comes after and is not part of any task here. This phase is done
      when the server decides who is hurt and who dies, and players can fight each other. The
      strategy is `serversupportsysdesign.md`: section 1 the target, 4.1 authority, 4.2 where
      state lives, 4.8 the two modes, 7 the whole task list; read it before designing, and build
      for the later phases rather than for this task alone. The tasks before this one are done or
      in the same queue; this run's progress file and the git log say what they built. Do not do
      later tasks' work here.
      Both modes: single player and multiplayer both ship. Follow the standing requirement
      at the top of `Scripts/dev/plans/multiplayer_tasks.md` and `serversupportsysdesign.md` 4.8.
      Local only: use no GCP or other cloud resource. Never run gcloud, gsutil or anything in
      `Scripts/server/gcp`; if the task seems to need one, stop and report instead.
      effort: high
- [x] M17. Random rolls happen once, on the server. Loot-table rolls, gun drops, the on-hit
      bleed chance and any other `Random*` that changes game state run only with authority
      and replicate their result; rolls that are purely cosmetic (sound variation, sway) stay
      local. Audit the Random hits in the builders and list each in `Scripts/net/CLAUDE.md`
      as "state" or "cosmetic". Done when: a 2-client probe looting one corpse shows both
      clients the same contents.
      Design goal: Chance that affects the game must be rolled once, by the server, or two players
      will see two different worlds.
      Big picture: this is task M17 of 36 in the multiplayer project, phase 3 of 0-8 (health,
      damage, death). The project turns this single-player survival game into one that also runs
      as a PvP game on a dedicated server (32-64 players, teams or solo, characters that persist),
      with single player still shipping from the same code. Phases 0-7 are built and proved on
      this Mac; hosting on GCP comes after and is not part of any task here. This phase is done
      when the server decides who is hurt and who dies, and players can fight each other. The
      strategy is `serversupportsysdesign.md`: section 1 the target, 4.1 authority, 4.2 where
      state lives, 4.8 the two modes, 7 the whole task list; read it before designing, and build
      for the later phases rather than for this task alone. The tasks before this one are done or
      in the same queue; this run's progress file and the git log say what they built. Do not do
      later tasks' work here.
      Both modes: single player and multiplayer both ship. Follow the standing requirement
      at the top of `Scripts/dev/plans/multiplayer_tasks.md` and `serversupportsysdesign.md` 4.8.
      Local only: use no GCP or other cloud resource. Never run gcloud, gsutil or anything in
      `Scripts/server/gcp`; if the task seems to need one, stop and report instead.
## Multiplayer, phase 4: weapons and inventory
- [x] M18. Replicate the inventory. The hand slot, the four weapon slots, the backpack, ammo
      (loaded and reserve) and `BP_WeaponItem` state are owned by the server and replicated to
      the owning client; what other players need (the item in hand) replicates to everyone.
      Design the replicated form as plain data that can be saved as it stands (M34 reuses
      it). Slot moves, drags, the 1-9 and Q selections, equip and holster become Server
      requests that the server validates. Done when: the inventory verifiers pass, single
      player is unchanged, and a `--net` probe moves an item between slots on client 1 with
      the server's copy agreeing.
      Design goal: The inventory is the foundation of the weapon, loot, clothing and save tasks.
      Its replicated form should be plain data that can be saved as it stands.
      Big picture: this is task M18 of 36 in the multiplayer project, phase 4 of 0-8 (weapons and
      inventory). The project turns this single-player survival game into one that also runs as a
      PvP game on a dedicated server (32-64 players, teams or solo, characters that persist), with
      single player still shipping from the same code. Phases 0-7 are built and proved on this
      Mac; hosting on GCP comes after and is not part of any task here. This phase is done when
      everything a player carries and does with it is owned and checked by the server, so it
      cannot be cheated and everyone sees it. The strategy is `serversupportsysdesign.md`: section
      1 the target, 4.1 authority, 4.2 where state lives, 4.8 the two modes, 7 the whole task
      list; read it before designing, and build for the later phases rather than for this task
      alone. The tasks before this one are done or in the same queue; this run's progress file and
      the git log say what they built. Do not do later tasks' work here.
      Both modes: single player and multiplayer both ship. Follow the standing requirement
      at the top of `Scripts/dev/plans/multiplayer_tasks.md` and `serversupportsysdesign.md` 4.8.
      Local only: use no GCP or other cloud resource. Never run gcloud, gsutil or anything in
      `Scripts/server/gcp`; if the task seems to need one, stop and report instead.
      effort: high
- [x] M19. Fire and reload as server requests. The client asks, the server checks ammo, fire
      rate and state, runs the trace from the muzzle with the client's aim, applies damage
      and spends ammo; the owning client predicts recoil, the muzzle flash and the ammo
      counter. No lag compensation yet (M22). Covers every gun, the hold-breath sway and ADS.
      Prefer a GAS ability per action where it fits the existing `GA_ConsumeItem` pattern;
      say in `Scripts/combat/CLAUDE.md` which was chosen and why. Done when: gun probes pass
      in single player and a `--net` probe has client 1 kill a wanderer with the server's
      ammo count matching the client's.
      Design goal: Shooting is the core loop: it has to feel immediate to the shooter while the
      server stays the judge of ammo, timing and hits.
      Big picture: this is task M19 of 36 in the multiplayer project, phase 4 of 0-8 (weapons and
      inventory). The project turns this single-player survival game into one that also runs as a
      PvP game on a dedicated server (32-64 players, teams or solo, characters that persist), with
      single player still shipping from the same code. Phases 0-7 are built and proved on this
      Mac; hosting on GCP comes after and is not part of any task here. This phase is done when
      everything a player carries and does with it is owned and checked by the server, so it
      cannot be cheated and everyone sees it. The strategy is `serversupportsysdesign.md`: section
      1 the target, 4.1 authority, 4.2 where state lives, 4.8 the two modes, 7 the whole task
      list; read it before designing, and build for the later phases rather than for this task
      alone. The tasks before this one are done or in the same queue; this run's progress file and
      the git log say what they built. Do not do later tasks' work here.
      Both modes: single player and multiplayer both ship. Follow the standing requirement
      at the top of `Scripts/dev/plans/multiplayer_tasks.md` and `serversupportsysdesign.md` 4.8.
      Local only: use no GCP or other cloud resource. Never run gcloud, gsutil or anything in
      `Scripts/server/gcp`; if the task seems to need one, stop and report instead.
      effort: high
- [x] M20. Melee, throw and block as server requests, on the same pattern as M19: the swing
      and its hit, the throw (arc, spin, sticking in trees and bodies, retrieval), the heated
      blade's double damage, and the torch ward. The server spawns and owns thrown items.
      Done when: the melee and throw probes pass in single player and a `--net` probe has a
      thrown axe stick in a tree and be retrieved by the other client.
      Design goal: Bring the remaining ways of hurting something onto the same server-request
      pattern as guns, so there is one model of combat.
      Big picture: this is task M20 of 36 in the multiplayer project, phase 4 of 0-8 (weapons and
      inventory). The project turns this single-player survival game into one that also runs as a
      PvP game on a dedicated server (32-64 players, teams or solo, characters that persist), with
      single player still shipping from the same code. Phases 0-7 are built and proved on this
      Mac; hosting on GCP comes after and is not part of any task here. This phase is done when
      everything a player carries and does with it is owned and checked by the server, so it
      cannot be cheated and everyone sees it. The strategy is `serversupportsysdesign.md`: section
      1 the target, 4.1 authority, 4.2 where state lives, 4.8 the two modes, 7 the whole task
      list; read it before designing, and build for the later phases rather than for this task
      alone. The tasks before this one are done or in the same queue; this run's progress file and
      the git log say what they built. Do not do later tasks' work here.
      Both modes: single player and multiplayer both ship. Follow the standing requirement
      at the top of `Scripts/dev/plans/multiplayer_tasks.md` and `serversupportsysdesign.md` 4.8.
      Local only: use no GCP or other cloud resource. Never run gcloud, gsutil or anything in
      `Scripts/server/gcp`; if the task seems to need one, stop and report instead.
      effort: high
- [x] M15. Players can hurt players. Shots, melee and thrown weapons damage other players'
      characters with the same hit-box multipliers as wanderers; the kill is credited to the
      instigator's PlayerState (a separate "player kills" count beside "Monster Kills").
      Friendly fire stays on until teams exist (M33). Done when: a 2-client probe has client 1 shoot client 2 and both
      clients and the server agree on client 2's health and client 1's count.
      Design goal: This is the feature that makes the game PvP. It should reuse the wanderer
      damage path rather than add a second one.
      Big picture: this is task M15 of 36 in the multiplayer project, phase 3 of 0-8 (health,
      damage, death). The project turns this single-player survival game into one that also runs
      as a PvP game on a dedicated server (32-64 players, teams or solo, characters that persist),
      with single player still shipping from the same code. Phases 0-7 are built and proved on
      this Mac; hosting on GCP comes after and is not part of any task here. This phase is done
      when the server decides who is hurt and who dies, and players can fight each other. The
      strategy is `serversupportsysdesign.md`: section 1 the target, 4.1 authority, 4.2 where
      state lives, 4.8 the two modes, 7 the whole task list; read it before designing, and build
      for the later phases rather than for this task alone. The tasks before this one are done or
      in the same queue; this run's progress file and the git log say what they built. Do not do
      later tasks' work here.
      Both modes: single player and multiplayer both ship. Follow the standing requirement
      at the top of `Scripts/dev/plans/multiplayer_tasks.md` and `serversupportsysdesign.md` 4.8.
      Local only: use no GCP or other cloud resource. Never run gcloud, gsutil or anything in
      `Scripts/server/gcp`; if the task seems to need one, stop and report instead.
- [x] M21. Everyone sees and hears the fight. Shot sounds, muzzle flashes, tracers, impact
      effects, blood, hit reactions, fire and reload and melee and throw montages, and
      footsteps play on every client through Multicast events or RepNotify, unreliable
      where a lost one does not matter. The noise the wanderers hear is recorded on the
      server from the same events. Done when: a `--net --windowed --clients 2` capture
      shows client 2 seeing and hearing client 1 fire, reload, swing and throw.
      Design goal: A fight must look and sound the same to everyone near it. Cosmetics travel
      separately from state so losing one never changes the outcome.
      Big picture: this is task M21 of 36 in the multiplayer project, phase 4 of 0-8 (weapons and
      inventory). The project turns this single-player survival game into one that also runs as a
      PvP game on a dedicated server (32-64 players, teams or solo, characters that persist), with
      single player still shipping from the same code. Phases 0-7 are built and proved on this
      Mac; hosting on GCP comes after and is not part of any task here. This phase is done when
      everything a player carries and does with it is owned and checked by the server, so it
      cannot be cheated and everyone sees it. The strategy is `serversupportsysdesign.md`: section
      1 the target, 4.1 authority, 4.2 where state lives, 4.8 the two modes, 7 the whole task
      list; read it before designing, and build for the later phases rather than for this task
      alone. The tasks before this one are done or in the same queue; this run's progress file and
      the git log say what they built. Do not do later tasks' work here.
      Both modes: single player and multiplayer both ship. Follow the standing requirement
      at the top of `Scripts/dev/plans/multiplayer_tasks.md` and `serversupportsysdesign.md` 4.8.
      Local only: use no GCP or other cloud resource. Never run gcloud, gsutil or anything in
      `Scripts/server/gcp`; if the task seems to need one, stop and report instead.
- [x] M22. Lag compensation for shots, in C++. The server keeps a short history of each
      character's hit-box transforms and rewinds them to the shooter's view time before
      tracing, with a cap on how far back it will go. Done when: with `Net PktLag=150` a
      probe that fires at a strafing target registers hits at a rate close to the no-lag
      run, and single player is unchanged.
      Design goal: Make hits fair under real network delay: the server judges a shot against where
      the target was when the shooter fired.
      Big picture: this is task M22 of 36 in the multiplayer project, phase 4 of 0-8 (weapons and
      inventory). The project turns this single-player survival game into one that also runs as a
      PvP game on a dedicated server (32-64 players, teams or solo, characters that persist), with
      single player still shipping from the same code. Phases 0-7 are built and proved on this
      Mac; hosting on GCP comes after and is not part of any task here. This phase is done when
      everything a player carries and does with it is owned and checked by the server, so it
      cannot be cheated and everyone sees it. The strategy is `serversupportsysdesign.md`: section
      1 the target, 4.1 authority, 4.2 where state lives, 4.8 the two modes, 7 the whole task
      list; read it before designing, and build for the later phases rather than for this task
      alone. The tasks before this one are done or in the same queue; this run's progress file and
      the git log say what they built. Do not do later tasks' work here.
      Both modes: single player and multiplayer both ship. Follow the standing requirement
      at the top of `Scripts/dev/plans/multiplayer_tasks.md` and `serversupportsysdesign.md` 4.8.
      Local only: use no GCP or other cloud resource. Never run gcloud, gsutil or anything in
      `Scripts/server/gcp`; if the task seems to need one, stop and report instead.
      effort: high
- [x] M23. Picking things up and looting, as server actions. Interact pick-up (closest to the
      reticle, the vertical range rule), drop, drag out of the inventory to drop, and the
      corpse loot window's take: the server decides who gets an item when two players reach
      for it, and the loser's UI corrects itself. Dropped and placed items are replicated
      actors. Done when: a 2-client probe has both clients take the same item on the same
      frame and exactly one receives it.
      Design goal: Two players reaching for one item is the commonest conflict in a looting game.
      The server settles it, and nothing is ever duplicated.
      Big picture: this is task M23 of 36 in the multiplayer project, phase 4 of 0-8 (weapons and
      inventory). The project turns this single-player survival game into one that also runs as a
      PvP game on a dedicated server (32-64 players, teams or solo, characters that persist), with
      single player still shipping from the same code. Phases 0-7 are built and proved on this
      Mac; hosting on GCP comes after and is not part of any task here. This phase is done when
      everything a player carries and does with it is owned and checked by the server, so it
      cannot be cheated and everyone sees it. The strategy is `serversupportsysdesign.md`: section
      1 the target, 4.1 authority, 4.2 where state lives, 4.8 the two modes, 7 the whole task
      list; read it before designing, and build for the later phases rather than for this task
      alone. The tasks before this one are done or in the same queue; this run's progress file and
      the git log say what they built. Do not do later tasks' work here.
      Both modes: single player and multiplayer both ship. Follow the standing requirement
      at the top of `Scripts/dev/plans/multiplayer_tasks.md` and `serversupportsysdesign.md` 4.8.
      Local only: use no GCP or other cloud resource. Never run gcloud, gsutil or anything in
      `Scripts/server/gcp`; if the task seems to need one, stop and report instead.
      effort: high
- [x] M24. Clothing over the network. Wear and take off are server requests, the eight worn
      slots replicate to the owner, and the garment visuals (where they exist) to everyone.
      Done when: the clothing verifier and probe pass and a `--net` probe agrees on worn
      slots between client and server.
      Design goal: Carry the clothing system across unchanged in behaviour, on the inventory's
      replication pattern.
      Big picture: this is task M24 of 36 in the multiplayer project, phase 4 of 0-8 (weapons and
      inventory). The project turns this single-player survival game into one that also runs as a
      PvP game on a dedicated server (32-64 players, teams or solo, characters that persist), with
      single player still shipping from the same code. Phases 0-7 are built and proved on this
      Mac; hosting on GCP comes after and is not part of any task here. This phase is done when
      everything a player carries and does with it is owned and checked by the server, so it
      cannot be cheated and everyone sees it. The strategy is `serversupportsysdesign.md`: section
      1 the target, 4.1 authority, 4.2 where state lives, 4.8 the two modes, 7 the whole task
      list; read it before designing, and build for the later phases rather than for this task
      alone. The tasks before this one are done or in the same queue; this run's progress file and
      the git log say what they built. Do not do later tasks' work here.
      Both modes: single player and multiplayer both ship. Follow the standing requirement
      at the top of `Scripts/dev/plans/multiplayer_tasks.md` and `serversupportsysdesign.md` 4.8.
      Local only: use no GCP or other cloud resource. Never run gcloud, gsutil or anything in
      `Scripts/server/gcp`; if the task seems to need one, stop and report instead.
- [x] M25. World interactions as server actions: chopping a tree for wood, matches making a
      campfire, lighting a stick at a fire, heating a blade, cauterising. The tree's state,
      the campfire, the lit stick and the heated blade's timer replicate. Done when: the
      existing probes for each pass in single player and a `--net` probe has client 2 see
      client 1's campfire and warm at it.
      Design goal: The world-changing actions (trees, fires, heat) must happen once, on the
      server, and be visible to everyone.
      Big picture: this is task M25 of 36 in the multiplayer project, phase 4 of 0-8 (weapons and
      inventory). The project turns this single-player survival game into one that also runs as a
      PvP game on a dedicated server (32-64 players, teams or solo, characters that persist), with
      single player still shipping from the same code. Phases 0-7 are built and proved on this
      Mac; hosting on GCP comes after and is not part of any task here. This phase is done when
      everything a player carries and does with it is owned and checked by the server, so it
      cannot be cheated and everyone sees it. The strategy is `serversupportsysdesign.md`: section
      1 the target, 4.1 authority, 4.2 where state lives, 4.8 the two modes, 7 the whole task
      list; read it before designing, and build for the later phases rather than for this task
      alone. The tasks before this one are done or in the same queue; this run's progress file and
      the git log say what they built. Do not do later tasks' work here.
      Both modes: single player and multiplayer both ship. Follow the standing requirement
      at the top of `Scripts/dev/plans/multiplayer_tasks.md` and `serversupportsysdesign.md` 4.8.
      Local only: use no GCP or other cloud resource. Never run gcloud, gsutil or anything in
      `Scripts/server/gcp`; if the task seems to need one, stop and report instead.
- [x] M26. Survival on the server. The ability system component and its attributes (health
      is M14's; hunger, thirst, temperature, stamina) are server-owned and replicated to the
      owner; the debuffs, bleeding, on-hit effects, night cold, campfire warmth and
      `GA_ConsumeItem` are applied by the server; the HUD reads replicated attributes. Decide
      where the component lives (pawn or PlayerState) from what M16's respawn needs and
      record why in `Scripts/survival/CLAUDE.md`. Done when: the survival verifier and
      probes pass and a `--net` probe has client 1 eat and see its own hunger rise while
      client 2's does not.
      Design goal: Survival values drive health and death, so the server must own them. This also
      settles where the ability system lives, which the respawn and the save both rely on.
      Big picture: this is task M26 of 36 in the multiplayer project, phase 4 of 0-8 (weapons and
      inventory). The project turns this single-player survival game into one that also runs as a
      PvP game on a dedicated server (32-64 players, teams or solo, characters that persist), with
      single player still shipping from the same code. Phases 0-7 are built and proved on this
      Mac; hosting on GCP comes after and is not part of any task here. This phase is done when
      everything a player carries and does with it is owned and checked by the server, so it
      cannot be cheated and everyone sees it. The strategy is `serversupportsysdesign.md`: section
      1 the target, 4.1 authority, 4.2 where state lives, 4.8 the two modes, 7 the whole task
      list; read it before designing, and build for the later phases rather than for this task
      alone. The tasks before this one are done or in the same queue; this run's progress file and
      the git log say what they built. Do not do later tasks' work here.
      Both modes: single player and multiplayer both ship. Follow the standing requirement
      at the top of `Scripts/dev/plans/multiplayer_tasks.md` and `serversupportsysdesign.md` 4.8.
      Local only: use no GCP or other cloud resource. Never run gcloud, gsutil or anything in
      `Scripts/server/gcp`; if the task seems to need one, stop and report instead.
      effort: high

## Multiplayer, architecture pass (A1-A5): scale and hardening, before phase 5

- [x] A1. A load test that runs on this Mac, and the numbers it gives. Add `uepy.py --net --bots N` : the dedicated server (the editor binary with `-server`) spawns N extra `BP_ThirdPersonCharacter` bodies possessed by a simple AI controller that walks, crouches and fires at the nearest other body on a timer, so they exercise the weapon component's Tick, the hit history, the record and the health path as players would. Run it with 2 real `-nullrhi` clients and N = 8, 16, 32 and 62, each for 90 s, and write `Scripts/probes/probe_net_load.py`, which records per process: server frame time (mean and 99th percentile), `stat net` bytes in/out per connection, replicated actors per connection, and the hit history's sample count. Put the results in a table in `Scripts/net/CLAUDE.md` under "Measured at scale" with the date, and name the three largest costs you can attribute (Unreal Insights trace with `-trace=net,cpu` on the server run at N = 32; one `.utrace` kept under `Saved/`). Do not fix anything in this task: it is the baseline every later task is measured against. Mac memory is the limit: if N = 62 does not fit in 16 GB, record the largest N that does and why. Design goal: every performance decision from here on is made against a number from this harness, not from reading the code. Big picture: this is task A1 of 5 in the multiplayer architecture pass, which sits between phase 4 and phase 5 of the multiplayer project. The project turns this single-player survival game into one that also runs as a PvP game on a dedicated server (32–64 players, teams or solo, characters that persist), with single player still shipping from the same code. Phases 0–4 (M1–M26) proved the authority pattern with two clients; this pass makes it hold at 64. The strategy is `serversupportsysdesign.md`: section 1 the target, 4.1 authority, 4.2 where state lives, 4.8 the two modes, 7 the whole task list. Both modes: the `--game` probes and the verifier sweep stay green; `--bots 0` is today's `--net`. Local only: use no GCP or other cloud resource. Never run gcloud, gsutil or anything in `Scripts/server/gcp`; if the task seems to need one, stop and report instead. effort: high

- [x] A2. Relevancy, update rates and dormancy, and a late joiner who sees the world as it is. Today nothing is configured: every replicated actor is considered for every connection every frame at the engine's defaults, and an item taken from the level is hidden rather than destroyed, so a player who joins later still has their own copy of it. In `combat/install.py`, `combat/item_world.py`, `combat/health_component.py`, `survival/campfire.py` and `npc/character.py` set, from one table in a new `net/relevancy_consts.py`: `NetCullDistanceSquared` (players and wanderers 150 m, items and campfires 60 m), `NetUpdateFrequency` and `MinNetUpdateFrequency` (characters 30/5 Hz, items 10/1 Hz, the GameState and PlayerStates at the defaults), and `NetDormancy = DORM_DormantAll` on an item once it lies still, woken with `FlushNetDormancy` by the graphs that change its replicated state (`item_world.py` owns the one call). A take destroys the server's actor when the item was a level actor (the engine tells late joiners of destroyed startup actors), and spawns the item into the inventory as the loot take already does; a dropped item stays one actor as today. Enable the `ReplicationGraph` plugin and add `UOtherworldReplicationGraph` to the `Otherworld` C++ module with the grid-spatialisation node for characters and items, always-relevant for the GameState and PlayerStates, and the owner-only node for each player's own pawn and its components; name it in `DefaultEngine.ini` for the IpNetDriver. Measure with A1 at N = 32 before and after and write both numbers in `Scripts/net/CLAUDE.md`. Proof: `probe_net_late_join.py` (client 2 joins 20 s after client 1 took the level's hat and lit a campfire: it sees no hat and the fire), `probe_net_see_each_other.py` and the M20–M25 probes still clean. Design goal: the server sends each client only what it can see or owns, at the rate each thing needs, and a late joiner's world is the server's world; this is what the engine expects a 64-player game to configure, and nothing in it is game logic. Big picture: this is task A2 of 5 in the multiplayer architecture pass, between phase 4 and phase 5 of the multiplayer project (the aim and the strategy are as A1 states: `serversupportsysdesign.md` 1, 4.1, 4.2, 4.8, 7). M31 (late joiners) is reduced to whatever this leaves. Both modes: in standalone a dormant actor still ticks and nothing is culled (one connection, none); the `--game` probes stay green. Local only: use no GCP or other cloud resource. Never run gcloud, gsutil or anything in `Scripts/server/gcp`; if the task seems to need one, stop and report instead. effort: high

- [x] A4. What the dedicated server spends on bodies it never draws. `combat/server_pose.py` makes every body on a dedicated server evaluate its full animation and refresh its bones every frame, so that hit bodies and muzzles are where clients see them; at 64 players and the wanderers this is likely the server's largest single cost (A1 says). Measure it first with A1 at N = 32 (`stat anim`, the Insights trace), then: enable Update Rate Optimization for skeletal meshes on the dedicated server (`bEnableUpdateRateOptimizations`, with `AnimUpdateRateParams` tuned so a body more than 30 m from every player is posed at 10 Hz and interpolated, and a body nobody is near at 2 Hz) while the hit history interpolates between samples, which it already does; move `UOtherworldHitHistory` to a ring buffer of fixed capacity per character (no allocation per frame), a `TMap` from character to history, and a capsule test from the sample before any body transform is blended (`SampleAt` currently blends every body first); batch `Multicast_PelletHit` into one `Multicast_ShotHits` per shot carrying an array of impacts; and on a dedicated server the player's and the wanderers' animation Blueprints evaluate only what moves a hit-box bone (locomotion, stance, aim pitch): the sight blend, the hand pose, the support hand and every montage that is not a gameplay timer are skipped there, behind one `IsDedicatedServer` branch in `combat/anim_blueprint.py` and the wanderers' anim builder (the server never plays a clip for its own sake; the moment a blow lands or a reload completes is already a timestamp). `combat/verify/server_anim.py` fails on a player or wanderer anim graph without that branch, or with a montage or blend that is not a hit-box bone's on its server arm: the later animation tasks (G3, G4) rebuild these graphs and are told to keep it green. Write the N = 62 world tick in `serversupportsysdesign.md` section 8 beside the Tier 2 decision. Write the before/after numbers in `Scripts/net/CLAUDE.md`. Proof: `probe_net_lag_hits.py` with and without `--lag 150` still lands 6/8 and 7/8 or better; `probe_net_fx.py` counts the same impacts on client 2; `probe_headshot` and `probe_ads_hit` in `--game`. Design goal: the server poses and remembers bodies at the rate the game needs to judge a shot, not at the rate a screen needs to draw one; the per-pellet and per-frame costs become per-shot and per-sample costs. Big picture: this is task A4 of 6 in the multiplayer architecture pass, run first because it is the cheapest and its number decides a section 8 question, between phase 4 and phase 5 of the multiplayer project (the aim and the strategy are as A1 states: `serversupportsysdesign.md` 1, 4.1, 4.3, 4.8, 7). Both modes: single player renders its bodies and records no history, so nothing here runs there; the `--game` probes stay green. Local only: use no GCP or other cloud resource. Never run gcloud, gsutil or anything in `Scripts/server/gcp`; if the task seems to need one, stop and report instead. effort: high

- [x] A3a. The inventory as one replicated structure, written when it changes: the server's half. The record is six parallel arrays plus `WornClass`, rewritten every Tick and replicated independently, so a client can receive a torn set and the view has to check their lengths agree (`view.py`). Replace them with one C++ `USTRUCT` `FOtherworldInventoryRecord` in the `Otherworld` module: a `TArray<FOtherworldItemRow>` (class, slot, loaded, reserve, lit, hot) and a `TArray<TSubclassOf<AActor>> Worn`, held in a `UOtherworldInventoryRecordComponent` (replicated, `COND_OWNER_ONLY`, one RepNotify, Push Model enabled) that `combat/install.py` adds to the player beside the weapon component, with `HandClass`/`HandLit`/`HandHot` as its three `COND_SKIP_OWNER` properties. The weapon component's graphs call `MarkDirty()` on it at each site that changes what is carried (`uebp/nodes/inventory.py`: the serve, the take, the drop, the throw, the shed, the wear, the reload, the shot, the chop, the consume), and the component writes the record once at the end of that frame on the server; the per-Tick rewrite in `record.py` goes. The client's view keeps reading the `Inv*` arrays for this task: the component ALSO writes the six arrays and `WornClass` from the struct in the same frame, so `view.py` is untouched and the game stays whole between A3a and A3b. `combat/verify/record.py` checks the new wiring: every change site marks dirty, and `record.py`'s per-Tick rewrite is gone. Proof: `probe_net_inventory.py` clean, with `--lag 120`; no load run here (A3b measures). Design goal: one atomic record of what a player carries, written by the server once per frame that changed it instead of every Tick; A3b makes the clients and the save read it. Big picture: this is task A3a of 6 in the multiplayer architecture pass; A3b finishes it, between phase 4 and phase 5 of the multiplayer project (the aim and the strategy are as A1 states: `serversupportsysdesign.md` 1, 4.1, 4.2, 4.6, 4.8, 7). Both modes: in standalone the component holds the record and nothing travels; the single-player profile keeps writing `BP_Profile` until M35, through the same `ToBytes`. Local only: use no GCP or other cloud resource. Never run gcloud, gsutil or anything in `Scripts/server/gcp`; if the task seems to need one, stop and report instead. effort: high

- [x] A3b. The inventory as one replicated structure: the client's half, and the bytes the save will write. A3a's `UOtherworldInventoryRecordComponent` holds the record and still mirrors it into the six `Inv*` arrays for the old view. Now `view.py` reads rows from the struct through a Blueprint library in the same module (`ViewRow`/`ViewTrim` keep their shape), the mirror into the arrays and the arrays themselves go (`record_vars.py` keeps only `ViewDirty`, `ViewItem` and the probes' `*Forced`), and the struct's one RepNotify raises `ViewDirty`. The struct serialises to and from a `USaveGame` byte array (`ToBytes`/`FromBytes`, a version field first), with a unit probe that round-trips a loaded pistol, a lit stick and a worn hat: M35 saves it as it stands. `combat/verify/record.py` fails on any builder that still names an `Inv*` array. Proof: `probe_net_fire.py`, `probe_net_clothing.py`, `probe_net_death.py` clean, with `--lag 120`; A1 at N = 32 shows fewer bytes per connection than before, written in `Scripts/net/CLAUDE.md`. Design goal: one atomic, versioned, serialisable record of what a player carries, sent only when it changes; the save in phase 8 and the loot in phase 7 read the same structure, and no client can ever see half an inventory. Big picture: this is task A3b of 6 in the multiplayer architecture pass, finishing A3a, between phase 4 and phase 5 of the multiplayer project (the aim and the strategy are as A1 states: `serversupportsysdesign.md` 1, 4.1, 4.2, 4.6, 4.8, 7). Both modes: in standalone the component holds the record and nothing travels; the single-player profile keeps writing `BP_Profile` until M35, through the same `ToBytes`. Local only: use no GCP or other cloud resource. Never run gcloud, gsutil or anything in `Scripts/server/gcp`; if the task seems to need one, stop and report instead. effort: high

- [x] A5. Every Server event checks what it is told and how often. The server traces `Server_Fire` from its own muzzle to whatever `AimPoint` the client sends, so a client can fire behind itself; no Server event is rate-limited, so a client can flood the reliable channel; and Blueprint RPCs cannot use the engine's `_Validate` hook. Add `UOtherworldRpcGuard` to the `Otherworld` C++ module, a component on the player (added by `combat/install.py`) with two Blueprint-callable checks every Server event on the weapon component calls first, through a shared fragment `net/guard.py` (`author_guard(g, name, execs)`): `Allow(name)`, a token bucket per event name per connection (`net/guard_consts.py`: fire at the fastest gun's rate plus 20 %, the asks at 10/s, the look report at 30/s, everything else at 5/s) that logs `RPC-REFUSED <name>` and, past a threshold in 10 s, kicks the connection with `ClosedByRpcGuard`; and `AimAllowed(AimPoint)`, which refuses an `AimPoint` more than `AIM_CONE_DEG` (20°) off the server's copy's control rotation (`GetBaseAimRotation`) or more than the gun's range away. `Server_Throw`'s start and speed and `Server_Take`'s reach already check themselves; keep those and add the bucket. In standalone both checks pass without counting. `combat/verify/guard.py` fails on a Server event without the fragment, and `random_checks`' pattern is the model for keeping the table and the events in step. Proof: `probe_net_guard.py` (client 1 sends an `AimPoint` behind itself and the round goes nowhere; `FireForced` held at 50/s sends the SMG's rate and no more; 200 `AskSlot` in a second get client 1 kicked, logged on the server) and `probe_net_fire.py`, `probe_net_melee.py` and `probe_net_take.py` clean with `--lag 120` (one probe per kind of Server event: the shot, the swing and the take; the rest of M14–M26's are not re-run here). Design goal: the server trusts a client's request no further than physics allows and never lets one client's traffic cost the others; this is the validation layer the engine's C++ RPCs get for free and Blueprint ones do not. Big picture: this is task A5 of 6 in the multiplayer architecture pass, between phase 4 and phase 5 of the multiplayer project (the aim and the strategy are as A1 states: `serversupportsysdesign.md` 1, 4.1, 4.3, 4.7, 4.8, 7). Anti-cheat proper (EAC, phase 8) sits on top of this, not in place of it. Both modes: a standalone game has one connection and the guard counts nothing; the `--game` probes stay green. Local only: use no GCP or other cloud resource. Never run gcloud, gsutil or anything in `Scripts/server/gcp`; if the task seems to need one, stop and report instead. effort: high

## Player animation: Game Animation Sample locomotion, then the clips it lacks
## (plan: metahumanAnimationPlan.md Tasks 2 and 3; Task 1, Taro as the body, is done).
## Each item ends with the game playable, its probe clean and a commit; the next item
## starts from that commit. Local only: both sample projects are on this Mac.

- [x] G1. Import the Game Animation Sample (GAS) into the project, no game change. Write
      `Scripts/asset_pipeline/import_gas.py` (host side, the shape of `import_metahuman.py`
      with a manifest) copying from `~/Documents/Unreal Projects/GameAnimationSample` the
      UEFN mannequin (`Content/Characters/UEFN_Mannequin`: Meshes, Rigs, Animations, with
      MotionMatchingData, the PoseSearch databases and their `CHT_PoseSearchDatabases*`
      choosers), `Content/Blueprints/SandboxCharacter_CMC_ABP` and whatever that AnimBP's
      dependency closure needs (the `AC_*` components, `BPI_SandboxCharacter_ABP`,
      `Blueprints/Data`, AnimNotifies, AnimModifiers; find the closure with a cold run against
      the sample as `import_metahuman.py` did, results to a file, not `print`). Leave out the
      Mover variant, SmartObjects, IsolatedExamples, Echo, Paragon, Kellan and the
      UE5_Mannequins. Register it in `Scripts/forest_generator/asset_sources.py` as a FAB-kind
      entry with dest `Content/GAS`, untracked like `Content/MetaHumans`. Enable in
      `Otherworld.uproject` the plugins GAS has and we lack: PoseSearch, Chooser,
      AnimationWarping, MotionWarping, AnimationLocomotionLibrary, AnimationLayering (check the
      sample's uproject for any other the closure loads). Done when a cold run loads
      `SandboxCharacter_CMC_ABP` and every PoseSearch database without a missing-asset warning,
      the size and package count are in `Scripts/asset_pipeline/CLAUDE.md` next to the
      MetaHuman's, and the full verifier sweep is unchanged. Design goal: the clips and the
      motion-matching graph are in the project before anything uses them, so the later items
      are about wiring, not about copying. Big picture: this is item G1 of 5 (G1–G5) giving
      the player GAS motion matching, after which C1–C5 replace the combat clips GAS lacks.
      effort: medium

- [x] G2. The skeleton bridge: decide how GAS clips reach the player's hidden mannequin, and
      prove one idle. The GAS clips are on `SK_UEFN_Mannequin`'s skeleton; the player's hidden
      mesh is SK_Mannequin running ABP_Unarmed, and Taro follows it through
      `/Game/Sourced/MetaHuman/ABP_MetaHuman_Retarget` (IK retargeter RTG_MetaHuman_from_Mannequin,
      built by `Scripts/asset_pipeline/build_metahuman_retarget.py`). Two candidate bridges:
      (a) the hidden mesh becomes SK_UEFN_Mannequin, and the MetaHuman retargeter's source is
      rebuilt from the UEFN skeleton; (b) the hidden mesh stays SK_Mannequin and the GAS
      databases are retargeted to it. Try (a) first: it keeps GAS's graph and databases as
      shipped. Measure what each breaks: the weapon hand sockets and the bone names that
      `combat/` scripts set by name (grep for `hand_r`, `head`, `spine_05`, `pelvis` and the
      socket names in `combat/grip.py`, `hit_zones.py`, `hit_bodies.py`); ragdoll and hit
      bodies are the mannequin's physics asset today. Pick, record the choice and its costs
      in `Scripts/asset_pipeline/CLAUDE.md`, and implement only enough to prove it: the
      hidden mesh plays one GAS idle (`M_Neutral_Idle_Loop` or the sample's equivalent) through
      a minimal anim blueprint, and Taro follows it. Proof: `probe_metahuman_body.py` standing
      checks still within their tolerances; a new `probe_gas_idle.py` reads the hidden mesh's
      current animation name and the body's follow gap. Do not wire motion matching yet and do
      not touch the weapon layers. Design goal: the one open question of the whole GAS move is
      settled on its own, with a probe, before locomotion work depends on it. Big picture:
      item G2 of 5 (G1–G5) giving the player GAS motion matching.
      effort: high

- [x] G3. Unarmed locomotion from GAS, weapons off. Replace the locomotion half of the player's
      base AnimBP (authored by `Scripts/combat/anim_blueprint.py`, with
      `body_pose.py`/`aim_pitch.py` on top) with GAS's `SandboxCharacter_CMC_ABP` graph and
      its `CHT_PoseSearchDatabases` chooser on the bridge from G2, driven by our
      CharacterMovementComponent: idle and idle breaks, turn in place, walk/jog/run/sprint in
      all directions with starts, stops and pivots, jump start/apex/land. Keep crouch, slide
      and traversal out (G5). Our movement speeds, the stamina-gated sprint and the walk
      toggle stay the game's; GAS's `AC_PreCMCTick`/`AC_PostABPTick` come across only where the
      graph needs them, as components `combat/install.py` adds. The weapon, hold, aim and
      hit-reaction layers are disconnected for this item (feature-flag them off in the
      builder, not deleted). Done when `probe_metahuman_look.py`'s empty-hands pictures show
      GAS walking, running and sidestepping, the right-strafe picture is a strafe and not a
      turned walk (the complaint that started this), `probe_metahuman_body.py` passes
      standing, falling, landed and dead, `probe_npc_strafe.py` is unchanged (NPCs keep
      ABP_Unarmed), and footstep notifies still fire (`combat/verify/footsteps` or the probe
      that covers them). Keep A4's server branch: `anim_blueprint.py` now puts an
      `IsDedicatedServer` branch at the head of the graph so a dedicated server evaluates only
      what moves a hit-box bone (locomotion, stance, aim pitch) and skips the rest; the new
      locomotion goes under that branch's client arm as the old did, the server arm keeps
      driving the hit-box bones, and `combat/verify` has A4's check of it, which must stay
      green. Design goal: the player's base movement is Epic's shipped motion
      matching, authored by our builder from the imported graph, with nothing hand-animated
      left in locomotion. Big picture: item G3 of 5 (G1–G5) giving the player GAS motion
      matching.
      effort: high

- [x] G4. The weapon layers back on top of GAS. Re-attach, as linked anim layers over the G3
      base, everything the flag in G3 turned off: hold poses (`combat/hold_pose.py`,
      `knife_anim.py`), the aim offsets (`aim_pitch.py`; GAS ships stand and crouch aim
      offsets, use them where they fit), ADS and shoulder aim, the shotgun pose, hit reactions
      (`hit_reaction.py`), the throw, the search kneel and the prone crawl (the last three keep
      their Quaternius clips, as the plan's table says). Upper-body layering goes through
      GAS's AnimationLayering where it has a slot for it, otherwise a layered-blend-per-bone
      from `spine_01` as today. Done when the full combat verifier suite
      (`Scripts/combat/verify`) is green, `probe_metahuman_look.py` with the axe and down the
      rifle's sights looks as it did before G3, the first-person head hide and the scope hide
      (`combat/weapon_component/body_parts.py`) still hide the MetaHuman's parts, and the
      `--game` smoke run of `Lvl_Forest_200m` is clean. Remove the G3 flag. Every layer
      re-attached here is cosmetic and goes on the client arm of A4's `IsDedicatedServer`
      branch (G3 kept it); the server arm gains nothing, and A4's verifier check stays green.
      Design goal: every
      combat animation the game already had sits on the new base unchanged, so G3's locomotion
      gain costs no combat behaviour. Big picture: item G4 of 5 (G1–G5) giving the player
      GAS motion matching; C1–C5 then replace the clips one at a time.
      effort: high

- [x] G5. Crouch, slide and traversal from GAS (optional; skip if G4 ran late). Wire GAS's
      crouch set to our crouch input and `CharacterMovementComponent` crouch, the slide to
      sprint+crouch, and `AC_TraversalLogic` (mantle, vault, hurdle) to jump against an
      obstacle, each behind its own constant in `combat/` tuning so one can be off. Done when
      a new `probe_gas_traversal.py` crouches, slides and mantles a 1 m block in
      `Lvl_Forest_200m`, `probe_metahuman_body.py` passes, and the verifier suite is green.
      Design goal: the movement set GAS ships for free is in the game where our inputs already
      exist, nothing more. Big picture: item G5 of 5 (G1–G5), the last of the GAS move.
      effort: medium

- [x] C1. Unarmed punch from Lyra. Replace `MM_Attack_01` (the unarmed attack montage) with
      Lyra's unarmed melee clip on the mannequin skeleton, through the import script and an
      asset_sources entry (`Content/Sourced/Lyra`, FAB kind, untracked), retargeted onto the
      G2 bridge's skeleton if it is not SK_Mannequin. Hit timing notify and damage window as
      the montage has today. Done when the melee verifier (`combat/verify/knife.py` and
      whichever covers the unarmed attack) is green and a `--game` punch at a zombie lands.
      Design goal: one hand-rolled or placeholder clip replaced by a shipped one, in the same
      shape every C item follows: one source, one import entry, one builder change, one
      verifier. Big picture: item C1 of 5 (C1–C5) replacing the combat clips GAS lacks, after
      G1–G5.
      fab: Lyra Starter Game | url: https://www.fab.com/listings/lyra-starter-game | at: /Game/Sourced/Lyra | why: unarmed punch, rifle and pistol hold sets, hit reacts
      effort: medium

- [x] C2. Melee swings: axe, knife and stick. Today they are built from poses
      (`combat/hold_pose.py`, `knife_anim.py`, `axe.py`). Replace them with clips from a
      Mixamo melee set imported through the existing Mixamo import script (the one the zombie
      packs used), one swing and one ready pose per weapon class. If the clips are not in
      `~/Downloads`, stop before any editor work and end the report asking for them by name.
      Done when `combat/verify/axe.py`, `knife.py`, `chop.py` and `hold_pose.py` are green and
      `probe_metahuman_look.py` with the axe shows the clip, not the pose. Design goal: no
      pose-built swing remains. Big picture: item C2 of 5 (C1–C5) replacing the combat clips
      GAS lacks.
      effort: medium

- [x] C3. Rifle, pistol and shotgun holds and ADS from Lyra. Replace `MF_*_Idle_ADS` and the
      hand-built `shotgun_pose.py` with Lyra's rifle and pistol hold, aim and ADS sets (the
      shotgun uses the rifle set with the grip offset the shotgun verifier expects), through
      the C1 import entry. GAS's aim offsets stay for pitch. Done when `combat/verify/aiming.py`,
      `aim_pitch.py`, `grip_fit.py`, `shotgun_pose` (its verifier) and `head_hide.py` are
      green, `probe_ads_hit` and `probe_headshot` in `--game` land as before, and the sights
      picture in `probe_metahuman_look.py` is on the barrel. Design goal: every gun pose is a
      shipped clip. Big picture: item C3 of 5 (C1–C5) replacing the combat clips GAS lacks.
      effort: high

- [x] C4. Hit reactions. The six `MM_HitReact` montages (`combat/hit_reaction.py`) stay unless
      Lyra's or GAS's shove-receive set gives a better front/back/left/right spread on the
      new base: compare on the bridge skeleton, pick one set, and delete the other's import.
      Done when `combat/verify/hit_reactions.py` is green and `probe_hit_react` (or the
      verifier's `--game` partner) shows a reaction from each side. Design goal: a decision,
      recorded in `combat/CLAUDE.md`, not a rewrite. Big picture: item C4 of 5 (C1–C5).
      effort: low

- [x] C5. Prone crawl from Mixamo. Replace the Quaternius `Swim_Fwd_Loop` stand-in with a
      Mixamo crawl loop through the Mixamo import script; same `~/Downloads` rule as C2.
      Done when the prone verifier and `probe_metahuman_body.py` are green and a prone
      `--game` move shows the crawl. Design goal: the last placeholder clip gone. Big
      picture: item C5 of 5 (C1–C5), the end of the player animation move.
      effort: low

- [x] T1. A known-failures file, so no session spends turns on a failure that predates it. 34 of 77 sessions did, and 12 used stash or checkout to prove it. Add `Scripts/dev/known_failures.md`: one line per standing failure (`<verifier or probe> | <check label> | since <date> | <why, one line>`). `devteam/gate.py` reads it: a listed check that fails is reported as "known" and never counts as a regression; a listed check that passes is reported as "fixed, remove the line". `devteam/session.py` names the file in the prompt with the rule: never rebuild or check out HEAD to prove a baseline; report against the recorded one. Seed it with today's six `verify_weapons_and_combat.py` pose checks and the flaky `probe_headshot.py` and `probe_gas_traversal.py`. Done when `python3 -m unittest discover -s Scripts/dev/tests` passes with new tests for the parse and for `gate.regressions` ignoring a listed check, and a dry `dev-team` prompt shows the rule. Touch only `Scripts/dev`. effort: low

- [x] T2. Fix the six standing `verify_weapons_and_combat.py` failures. They have failed in every sweep for days (the pose checks; `Scripts/dev/known_failures.md` lists them after T1, else read the last sweep log in `Saved/DevTeam/`). For each: decide whether the game or the check is wrong, fix that one, and say which in the commit. A check may be loosened only with the reason in its docstring; a check that tests something the G3–G5 motion-matching move made meaningless is deleted, named in the commit. Done when a cold `uepy.py --cold --summary Scripts/verify_weapons_and_combat.py` reports zero failures, `probe_hold_poses.py` and `probe_stance_clips.py` pass, and the six lines leave `known_failures.md`. effort: medium

- [x] T3. `probe_headshot.py` is flaky: 11 failing runs in the window, and it fails when launched with `probe_ads_hit.py` in the same run. Find the cause (shared state between the two probes through `probes/boot.py`'s WRITABLE recompiles, a timing race on the shot's registration, or the sway) and fix the probe or the game, not the batching. Done when `uepy.py --game --probe Scripts/probes/probe_headshot.py Scripts/probes/probe_ads_hit.py` passes five runs in a row and its line leaves `known_failures.md`. effort: low

- [x] T4. `probe_gas_traversal.py` had 11 failing runs in G5. Traversal has nothing to climb in either map (the root `CLAUDE.md` "Known gaps"). Make the probe self-contained: spawn its own traversable block in front of the player at boot (a static mesh actor with the sample's traversable tag or interface, whatever `AC_TraversalLogic` reads), then mantle, vault and hurdle it. Nothing is added to a level. Done when the probe passes five runs in a row and its line leaves `known_failures.md`. effort: medium

- [x] T5. Every probe declares the systems it checks, so T6 can pick probes by change. Add `SYSTEMS = ("weapons", ...)` to each of the 118 files in `Scripts/probes/probe_*.py`, drawn from one list in `Scripts/probes/systems.py` (`weapons`, `inventory`, `health`, `melee`, `throw`, `survival`, `clothing`, `loot`, `npc`, `hud`, `menu`, `sound`, `world`, `animation`, `movement`, `net`, `load`, `title`). Write a one-off script in `Scripts/dev/codemods/probe_systems.py` that proposes the tags from the file name and its imports (`probe_net_*` gets `net`; an import of `combat.*` gets `weapons`; and so on), prints the table, and writes them; read the table once and correct by hand only where a name misleads. A dev test asserts every probe has a non-empty `SYSTEMS` drawn from the list. Done when the test passes and `uepy.py --list-probes` (new, host side, no editor) prints probe and systems. effort: low

- [x] T6. `uepy.py --probes-for <paths...>`: run the probes a change can affect. 63 % of probe time was repeats, 2.2 runs per probe per task. `Scripts/dev/uepylib/probe_map.py` maps a path to systems (`Scripts/combat/weapon_component/*` to `weapons`, `Scripts/npc/*` to `npc`, `Source/Otherworld/*Shot*` to `weapons` and `net`, ...), with `git diff --name-only` as the default input, and launches the matching single-player probes in one `--game` run and the matching `--net` probes in one `--net` run (probes `probe_headshot`/`probe_ads_hit` may share a launch after T3). The prompt in `devteam/session.py` gets the rule: during a task run `--probes-for`; the full regression is the gate's (T7), not yours. Done when dev tests cover the mapping and the command, and one real run of `--probes-for Scripts/combat/weapon_component/fire.py` launches exactly the weapons probes. effort: medium

- [x] T7. The gate runs a named probe set before and after each task, batched per boot, so sessions stop at their last change. The closeout tail was 22 % of session time, mostly a final regression run; 32 sessions ran probes one boot each. Add `Scripts/probes/sets.py` (`SMOKE`: one single-player launch of the ~12 probes that cover each system once, one `--net --clients 2` launch of the ~8 net probes that do the same; `FULL`: every probe) and have `devteam/gate.py` run `SMOKE` beside the verifier sweep, recording per-probe pass/fail in the baseline table the session is given, and comparing after. A probe that newly fails fails the task, as a verifier does. The session prompt says: do not run the regression yourself; end when your change is proven by its own probe. Done when dev tests cover the set parsing and the comparison, and one dev-team run of a trivial task shows the probe rows in its gate table. effort: medium

- [x] T8. A cheaper gate: cache the before-sweep and run it warm. The gate cold-boots the whole verifier suite twice per task, 52 s on Oct 6 growing to 274 s by Oct 8. `devteam/work.py` already keys a cached baseline on `tree_fingerprint()`; make the cache survive across runs (a JSON file under `Saved/DevTeam/`), and run the before-sweep in the session's warm serve editor (`UEPY_SERVE`) while the after-sweep stays cold (a literal equal to its pin default reads back differently across editors: root `CLAUDE.md`, "Finding and identifying nodes"; the cold after-sweep is what catches that). Report the sweep's duration in the gate table. Done when dev tests cover the cache and two consecutive runs on an unchanged tree skip the before-sweep. effort: low

- [x] T9. `build_weapons_and_combat.py` builds one Blueprint or one step on request. It ran 80 times at 105 s in the window, always in full. Turn `main()`'s ordered calls into a table of steps (`name`, `function`, `needs`: the steps it must follow) in `Scripts/combat/build_steps.py`, and honour `UEPY_BUILD_ONLY=<step[,step]>` (uepy passes no arguments to a script, so the environment carries it; add `uepy.py --only <steps>` that sets it). `--only` runs the named steps and nothing else; a step whose `needs` were not run is a hard error, not a silent skip. Proof: `Scripts/dev/graph_fingerprint.py full` after a full build, then `--only weapon_component` on top, then `graph_fingerprint.py only`; `graph_fingerprint_diff.py full only` is empty. Record the time of the two runs in `Scripts/combat/CLAUDE.md`. Done when that diff is empty for `weapon_component`, `health` and `hud_defaults` (or whatever the three largest steps are named) and the entry point is still under 250 lines. effort: medium

- [x] T10. A small level for probes. A single-player probe launch has a fixed cost of about 25 s and a `--net` one about 50 s, most of it the 200 m level's trees, its navmesh build and the motion-matching databases. Generate `Lvl_Probe_50m` with `generate_forest_level.py` at 50 m: at most 20 trees, grass off, the same spawn, the same forage, clothing and campfire placements as `Lvl_Forest_200m` (they are what probes use), wanderer count as the 200 m map's, and its navmesh saved with the level (`Scripts/dev/check_saved_navmesh.py` is the check). Commit the level through LFS as the other generated levels are, with its `generated_levels/Lvl_Probe_50m/` import and verify scripts. Change nothing in `uepy.py` yet (T11). Done when `verify_Lvl_Probe_50m.py` passes and `uepy.py --game --map /Game/Maps/Lvl_Probe_50m --probe Scripts/probes/probe_consume_heal.py` passes, with the boot time of both maps in the commit message. effort: medium

- [x] T12. Detached runs: `uepy.py --detach` and `uepy.py --wait`. 99.9 % of tool time blocked the session, and a headless session never hears a background command finish, so sessions are told never to use `run_in_background`. Instead `--detach` starts a `--game` or `--net` run, prints its run directory and returns at once; `--wait <run dir> [--timeout S]` blocks until the run's result file exists and prints the usual report, failing on timeout; `--status` lists detached runs. One detached run at a time (a server and two `-nullrhi` clients are 12.9 of 16 GB); a second `--detach` refuses while one runs. The session prompt gets the pattern: detach the probe, read or edit meanwhile, then `--wait`. Done when dev tests cover both commands with a fake run and one real detach-then-wait of `probe_net_join.py` reports as a foreground run does. effort: medium

- [x] T13. `uepy.py --compile`: the C++ cycle as one command. Sessions lose turns to the dylib trap in `Source/CLAUDE.md` (a build while an editor exits writes a numbered copy and `UnrealEditor.modules` is not updated). `--compile` closes this project's editors and waits for them to be gone, runs the `Build.sh` line from `Source/CLAUDE.md`, checks `Binaries/Mac/UnrealEditor.modules` names the newest `libUnrealEditor-Otherworld*.dylib` (rewriting it if not, and saying so), then boots the warm serve editor if `UEPY_SERVE` is set and proves `hasattr(unreal, "OtherworldMovementLibrary")`. Non-zero on a compile error with the first error lines printed. Done when dev tests cover the modules-file check with fixture files and a real `--compile` after touching one `.cpp` ends in a serving editor. effort: low

- [x] T14. A symbol index and a batching rule, for fewer turns. Sessions spent 2.2 h composing searches and 2.85 h reading their output, one command per turn. Add `Scripts/dev/symbols.py` that writes `Scripts/dev/symbols.txt`: one line per `def`, class and `UPPER_CASE =` constant under `Scripts/` and per `UCLASS`/`UFUNCTION` under `Source/`, with path and line, and have the `pre-commit` hook in `Scripts/dev/hooks` refresh it (the file is committed). The root `CLAUDE.md`'s "Working in it" names it in place of the grep, and the dev-team prompt says: grep `symbols.txt` first; batch independent reads into one command. Done when the hook refreshes the file, a dev test checks it is current against the tree, and the file is under 400 KB. effort: low

- [x] T15. A linter in the hook. 145 k lines of Python have none. Add `ruff` (pyflakes rules plus unused imports, line length off) to `Scripts/dev/hooks/pre-commit` for staged `.py` files, with `Scripts/ruff.toml`, and fix what it finds in `Scripts/dev`, `Scripts/uebp` and `Scripts/probes` first; the builder packages get a `# noqa` budget listed in the commit and are cleaned package by package in later tasks. Done when the hook refuses a file with an undefined name, `ruff check Scripts/dev Scripts/uebp Scripts/probes` is clean, and the unit tests pass. effort: low

- [x] The animation speed seems to be unrealistic for the run. Running animation plays too fast. Jumping animation seems similar. Same with crouching. Review and fix the root cause. There was a task attempting to fix this that was interrupted and did not compelte. Review if there are active changes to address this issue already, if so validate them. If not - fix the issue. 

- [x] X1. Split `Scripts/net/CLAUDE.md` into rules and history. It is 1,633 lines and is read before every multiplayer task; most of it is the narrative of M7 to A5. Keep in `CLAUDE.md` only the rules a graph follows, the traps, the mode table and the pointers; move each task's narrative verbatim to `docs/history/multiplayer.md` under its heading, with a one-line pointer left behind (`M22 lag compensation: docs/history/multiplayer.md#m22`). Nothing is reworded. Done when `net/CLAUDE.md` is under 500 lines, every heading that left has a pointer, and `git diff --stat` shows the lines moved, not lost (count the lines in both files before and after in the commit message). effort: low

- [x] X2. The same split for `Scripts/combat/CLAUDE.md` (1,243 lines) and `Scripts/graphics_menu/CLAUDE.md` (988) into `docs/history/combat.md` and `docs/history/menu.md`, and for the root `CLAUDE.md`'s "Current state" section, which is a 90-line narrative, into `docs/current_state.md` with a five-line summary left in place. Same rule: move verbatim, leave pointers, count lines. Done when each `CLAUDE.md` is under 500 lines and the root under 450. effort: low

- [x] X3. Package maps that cannot go stale. Each package's `__init__.py` docstring lists its modules by hand. Add `Scripts/dev/tests/test_package_maps.py`: every `.py` in a package appears in its `__init__` docstring, and every name in the docstring exists; and `Scripts/dev/package_map.py --fix <package>` appends a missing module's first docstring line. Fix every package it finds wrong. Done when the test passes for every package under `Scripts/` and the root `CLAUDE.md`'s routing table lists every package that has a `CLAUDE.md`. effort: low

- [x] V1. Finish the typed variable tables for the weapon component and the weapon item. Phase 4 of `Scripts/dev/plans/remove_graph_literals.md` typed only variables that were bare strings (weapon component 29 of 35 rows typed, weapon item 21 of 36; the report lists them). Type the rest in their `*_vars.py` tables and delete the builders' own `_declare` calls and default dicts for them; a `*_VAR` constant that other modules import becomes `NAME_VAR = WV.Name`. Proof: `Scripts/dev/plans/sweep.sh v1` against a fresh baseline fingerprint is identical, verifier counts unchanged. Done when `grep -rn '_declare(' Scripts/combat` finds no call that names a variable by a string. effort: medium

- [x] V2. The same for survival (3 of 9 typed), day and night (0 of 10), the NPC controllers and the HUD's remaining per-item default dicts. After V1, same proof. Done when no builder under `Scripts/` declares a variable outside a `uebp.vars` table and the fingerprint diff is empty. effort: medium

- [x] V3. Verifiers read the variable tables. Today each verifier re-states the variables it expects by hand. Add `Scripts/uebp/verify_vars.py`: `check_table(bp, TABLE, check)` asserts every row is declared with the row's type, default and (through `uebp.net.compiled_replication`) replication, and nothing undeclared sits beside them. Call it once per Blueprint from the owning verifier and delete the hand-written variable checks it makes redundant, naming each in the commit. Done when the verifier sweep's counts change only by the deletions named, and the dev tests cover `check_table` with a fake table. effort: medium

- [x] V4. Count checks become anchored checks, in the two verifiers that churn most. Every task reworded 5 to 15 "X is written exactly once" checks that broke on legitimate new nodes; `Scripts/combat/verify` has about 149 of them. In `combat/verify/weapon_inputs.py` and `combat/verify/throw_strike.py`, replace each whole-graph count with a check anchored to a named node or fragment (the fixture approach of `combat/verify/fixtures.py`: find the fragment's entry, assert what it wires), keeping the same intent. Write the rule into `Scripts/combat/CLAUDE.md` ("Verifiers mirror builders": anchor, never count the graph). Done when both verifiers pass with the same number of checks or fewer, each deletion named, and no `== 1` count remains in them. effort: medium

- [x] W0. Measure where the server's tick goes before porting anything. The world tick is 43 ms at 62 bots against the 25 ms line (`Scripts/net/CLAUDE.md`, "Measured at scale"); the design doc guesses the weapon component's Tick. Run `uepy.py --net --clients 2 --bots 32 --trace --probe Scripts/probes/probe_net_load.py`, open `server.utrace` with `UnrealInsights` from the command line (or `-statnamedevents` plus `stat dumpframe` if Insights cannot be driven headless), and record the top ten costs by inclusive time with the Blueprint VM's share split out per class (`BP_WeaponComponent`, `BP_HealthComponent`, the NPC controllers, the record component). Write the table into `Scripts/net/CLAUDE.md` under "Measured at scale" and name the first port in the commit. No game change. Done when the table exists with numbers from one run. effort: low

- [x] W1. The shot's server half in C++: slice 1 of the weapon component port. Add `UOtherworldWeaponComponentBase : UActorComponent` to the `Otherworld` module and reparent `BP_WeaponComponent` onto it (`combat/install.py`; the reparent keeps variables, as `player_move.reparent_player` does for the character). Move into C++ only: the fire deadline (`NextFireTime`), `Loaded`/`Reserve` as replicated `UPROPERTY`s with the record marked dirty as `Scripts/combat/dirty.py` requires, and `Server_Fire`'s validation and spend (the guard's `Allow` and `AimAllowed`, the `ShotTrace` call, the damage hand-off to the health event) as a `UFUNCTION(Server, Reliable, WithValidation)`; the graph's `Server_Fire` event becomes a call to it. Cosmetics, the HUD and the reload stay in the graph. `combat/verify/shot.py` (or the existing section) asserts the C++ function exists and the graph calls it; the variable rows for `Loaded`/`Reserve` move from `shot_vars.py` to a note that C++ owns them. Proof: `probe_net_fire.py` and `probe_net_guard.py` with `--lag 120`, `probe_gun_tuning.py`, `probe_slots.py`, and `probes/sets.py` `SMOKE`. Record the server tick at 32 bots before and after (W0's method) in `Scripts/net/CLAUDE.md`. effort: high

- [x] W2. The reload and the ammo in C++: slice 2, from W1's commit. `Server_Reload`, `ReloadTake` (the pure node whose re-evaluation gave free ammo: root `CLAUDE.md`, "Evaluation order") and the pistol's endless reserve move onto `UOtherworldWeaponComponentBase`; the graph keeps the key, the montage and the sound. Proof as W1 plus `probe_net_fire.py`'s reload checks and `probe_dev_all_guns.py`. Done when the graph has no `ReloadTake` node and the fingerprint of every other Blueprint is unchanged. effort: medium

- [x] W3. The health component in C++. `BP_HealthComponent` is 263 nodes with one `TakeHit` Server path, replicated `Health` and `Dead` and the kill credit (M14). Add `UOtherworldHealthComponent` with `TakeHit(Damage, Instigator, Bone)` as a server-only function, `Health` and `Dead` as RepNotify properties firing Blueprint-implementable `OnHealthChanged`/`OnDied` events the existing graph fragments connect to (death's corpse and respawn stay in the graph: `combat/player_respawn.py`). Reparent through `combat/install.py`; `combat/verify/health.py` asserts the class and the two events. Proof: `probe_net_health.py`, `probe_net_death.py`, `probe_net_pvp.py`, `probe_kill_credit.py`, `probe_consume_heal.py`, `probe_dead_no_actions.py`. effort: high

- [x] T16. The gate's probe half is opt-in, and one probe sweep runs at the end of a run. In run 20261009-081727 the gate took 6h02m of 14h35m (41%); each after-sweep was 1,340-1,660 s, of which 126 s was the nine verifier suites and ~1,260 s the SMOKE set, because batch interference made `rerun_alone` turn 2 launches into 12. Two of 12 tasks failed the gate on probe rows while changing only Markdown (task 2, the CLAUDE.md split; task 9, W0), each costing a second full sweep and a fix session. Make `--gate-probes` default to `none` (`Scripts/dev/dev-team`, line 163). Add `--final-probes SET` (default `SMOKE`): after the last task of a run, one sweep of that set against the run's first baseline, written to `progress.md` as its own section with the commit range, counting against the run's exit code but failing no individual task. `devteam/gate.regressions` must stop reporting a label that is in the baseline but missing from the after-sweep (`gate.py:120`) when the two sweeps ran different probe sets: compare only the labels both hold, and say in the table which rows were not re-run. `devteam/baseline_cache.key` takes the probe set as well as the tree state, so a baseline cached under one set is never reused under another (`Saved/DevTeam/baseline_cache.json` currently holds 29 rows, 20 of them `probe:*`). Done when dev tests cover the narrowed comparison and the new cache key, `./dev-team --dry-run` shows `none` as the default, and a run of two trivial tasks shows no probe rows per task and one final probe section. Touch only `Scripts/dev`. effort: medium

- [x] K1. The MetaHuman starts in boxers. Read `Scripts/clothing/CLAUDE.md` and `Scripts/asset_pipeline/CLAUDE.md` ("The MetaHuman") first. `combat/metahuman_body.install()` always puts the hoodie, jeans and shoes on `Torso`, `Legs`, `Feet`. Keep the three components (same names, still in the LOD sync) but give them no mesh and hide them; `metahuman_paths.CLOTHING` stays as the table of meshes. The body's material already paints underwear. Take one front picture with `probe_metahuman_look.py`: if skin is pulled inward where the clothes were (`BodyHideScale` is -3 on `MI_BodySynthesized`), wear a copy of that material under `/Game/Sourced/MetaHuman` with it at 0; never edit `/Game/MetaHumans`. Update `probe_metahuman_body.py` and the verifier checks that expect three dressed garments. Done when the weapons verifier and `probe_metahuman_body.py` pass and the picture shows a whole body in underwear. effort: low

- [x] K2. A garment names the mesh it is drawn as. From K1's commit. In `clothing/specs.py` add to `Garment` an optional `worn` pair (the body component it fills, the skeletal mesh), read from `metahuman_paths.CLOTHING`: Jacket fills `Torso` with the hoodie, Pants `Legs` with the jeans, Boots `Feet` with the running shoes; the other five have none. `clothing/items.py` writes it onto each `BP_<Garment>` as two new item variables (`WornPart` name, `WornMesh` skeletal mesh; empty on every non-garment), declared where `ClothingSlot` is. Data only: nothing draws yet. Done when `verify_clothing.py` passes with new checks for the three rows and for an empty `WornMesh` on the other five, and the unit tests pass. effort: low

- [x] K3. Wearing draws the garment, single player. From K2's commit. In `combat/weapon_component/wear.py` (split a `wear_draw.py` out if it nears 500 lines), after a wear, set the worn garment's `WornMesh` on the component named by its `WornPart` under the body and show it; after a take-off or a drop of a worn garment, clear it and hide it. A garment with no `WornMesh` draws nothing. The mesh must follow the body: leader pose when it is on `metahuman_base_skel` (the jeans), else the `ABP_Clothing_PostProcess` copy pose (hoodie, shoes), set when the mesh is set, because `MetaHumanComponentUE` only does it at BeginPlay. Done when `probe_clothing.py` gains and passes: wear the jacket, `Torso` has the hoodie, is visible and its spine is within 1 cm of the body's after a walk; take it off, `Torso` is empty and hidden; wearing the hat changes no component. effort: medium

- [x] K4. The scope, the sights and death with a garment on. From K3's commit. The per-view hides loop over the mannequin's children (`weapon_component/body_parts.py`), so a worn garment should follow; prove it rather than assume. Extend `probe_scope_hide.py` and `probe_head_hide.py` to run once more with the jacket worn, and `probe_net_death.py`'s standalone arm (or the ragdoll probe) to die with the pants worn: the garment is owner-no-see behind the scope, back on death, and stays on the body through the ragdoll. Fix whichever fails. Done when those probes pass both bare and dressed. effort: low

- [x] K5. Everyone sees what a player wears. From K4's commit. Read `Scripts/net/CLAUDE.md`, "Clothing": the record's `Worn` replicates to the owner only, and the note there says how to widen it. Add a replicated, skip-owner array of worn classes on the record component beside `HandClass` (C++; `uepy.py --compile`), written where the record's `Worn` is written; its RepNotify, and the owner's own view (`view_worn.py`), call K3's draw. A dedicated server sets no mesh. Done when `probe_net_clothing.py` gains and passes: client 1 wears the jacket and client 2 sees the hoodie on client 1's `Torso`; client 1 takes it off and client 2 sees it gone; a client joining late sees it; clean with `--lag 120`. effort: medium

- [x] K6. The profile saves what is worn. From K5's commit. The single-player profile stores the bag and not `Worn` (`Scripts/graphics_menu/CLAUDE.md`, "Save and exit"), so clothes are lost on save and exit. Save the worn slots' classes with the bag's rows and, on load, spawn each into `Worn[slot]` hidden, as a wear leaves it, and draw it through K3's path. The death wipe clears them with the bag. Done when a new `probe_clothing_save.py` passes: wear the jacket and the hat, save and exit, continue, and both are worn, the jacket drawn, the bag otherwise as it was. effort: low

- [x] K7. The I panel's portrait is the MetaHuman. From K6's commit. `item_icons/portrait.py` still pictures `SKM_<PLAYER_NAME>`, the retired Meshy body. Picture the MetaHuman instead: the body and the face (grooms if the capture takes them, else say so in `Scripts/item_icons/CLAUDE.md`) in boxers, in the idle's first frame, through the same passes. Rebuild with `build_item_icons.py Character`. The portrait does not change with what is worn; that is not this task. Done when the portrait check in `graphics_menu/wear_checks.py` passes against the new mesh and the texture is looked at once and shows Taro, facing forward, whole. effort: medium

- [x] K8. Retire the old base body. From K7's commit. `CLOTHING_BASE_BODY` and `CLOTHING_BASE_NAME` (`asset_pipeline/player_body.py`), `BASE_BODY_*` (`clothing/specs.py`) and `clothing/verify/base_body.py` describe a Meshy body in shorts the garments were once to be drawn on. Delete them and their checks, keep `swap_player_body.py` working for the non-MetaHuman rigs, and correct `Scripts/clothing/CLAUDE.md` ("Not done yet", the owner table), the root `CLAUDE.md` clothing paragraph and `Scripts/asset_pipeline/CLAUDE.md` to say what K1 to K7 made true. No behaviour changes. Done when the full verifier sweep and the unit tests pass and `grep -r CLOTHING_BASE Scripts` finds nothing. effort: low

- [x] K9. The three real garments look like themselves on the ground. From K8's commit. The jacket, pants and boots lie as cubes (`clothing/specs.py` `parts`). Give a garment with a `WornMesh` that mesh as its ground model instead: one skeletal mesh component in its reference pose, laid flat and centred on the item's origin, with the item's collision and glimmer unchanged; held in hand it keeps the stand-in's grip point. Rebuild their three icons (`build_item_icons.py Jacket Pants Boots`). The other five keep their cubes. Done when `verify_clothing.py` and `probe_clothing.py` pass and one windowed picture of the test row shows a hoodie, jeans and shoes on the ground. effort: medium

- [x] K10. Wanderers carry clothing. From K9's commit. Add the jacket, the pants and the boots to `WANDERER_LOOT` (`Scripts/loot/tables.py`) at 0.10 each; `clothing` may not be imported by `loot` or `combat`, so name the paths the way `survival.paths` is named there. Run `build_survival.py` after `build_clothing.py` (the table is installed once every item exists; say so in `Scripts/loot/CLAUDE.md`). Done when `survival/verify/loot.py` passes with the new rows and `probe_corpse_loot.py` gains and passes a case that forces a jacket into a body's loot, takes it into the bag and wears it. effort: low

- [x] K11. Clothing is found in the forest. From K10's commit. Scatter the three real garments through the generated levels the way forage is (`survival/forage_placement.py`, `forage_level.py`, `place_forage.py`): a new `clothing/scatter.py` (where, pure Python, seeded, about one garment per hectare, never inside a trunk) and an entry in `build_clothing.py` that places them with the tag `OW_Clothing`, idempotently. The test row on `Lvl_Forest_200m` stays: the probes use it. Done when unit tests cover the placement's count, seed and spacing, `verify_clothing.py` checks the tagged actors exist on each level, and `probe_clothing.py` still passes. effort: low

- [x] I1. Enhanced Input, one action: the fire key. `DefaultInput.ini` already names the Enhanced Input classes and nothing uses them; ten modules poll `WasInputKeyJustPressed` on a post-physics Tick with bindings pushed from the SaveGame each frame. Add `combat/input_assets.py` authoring `IA_Fire` and `IMC_Default` (the key from `player_tuning`'s binding table), add the context in `AOtherworldCharacter::SetupPlayerInputComponent` and bind `IA_Fire` to a `BlueprintImplementableEvent OnFirePressed` the weapon component's existing fire fragment connects to in place of its poll. The other keys stay polled. The settings page's rebinding writes the mapping context's key for `IA_Fire` (one row) instead of the SaveGame key. Proof: `probe_net_fire.py`, `probe_asks.py`, `probe_look_sensitivity.py`, the menu's rebinding probe if one exists. Done when `grep` finds no poll of the fire key in `Scripts/combat` and the fingerprint of untouched Blueprints is unchanged. effort: medium

- [x] In the main menu, consolidate exit game and save and exit buttons. When in game, the option shoudl be save and exit. When in the menu it should be exit game. Bottom option in both cases. In multiplayer instead of leave server should trigger the 15 minute delay same as in single player. 

- [x] H1. Make an item's place in the hand editable in the editor. Today a held item's grip
      is solved in code and baked at build, so every correction is edit, build, launch, look.
      Give each held item (the guns, axe, knife, stick, wood, matches, consumables) a grip
      the editor can move by eye, which the game then uses to seat the item in the hand.
      Because content is generated from Python, a hand-placed grip must survive a rebuild:
      the build seeds it from today's solved values only when it is missing, and never
      overwrites one that exists. A fresh checkout must look the same as it does now. Done
      when moving an item's grip in the editor changes how it sits in the hand with no build,
      a rebuild of the weapons step leaves a moved grip alone, and the existing grip-fit
      verifier still passes. Document the "place a grip by eye" steps beside the grip docs.
      Design goal: a handle that sits 2 cm off is fixed by whoever sees it, with no engineer.
      Big picture: item H1 of 3 (H1-H3), hand placement and clip swaps. effort: medium

- [x] H2. Grip nudges as a tuning table, so a number is a restart and not a build. From H1
      and D1 (follow D1's table pattern). Add a table of per-item position and rotation
      nudges, all zero by default, applied on top of whatever H1 gives, so a rebuild or a
      new ready pose keeps the nudge. Every machine reads the same rows so the server,
      client and menu agree. The dev GUN SETTINGS tab gets a grip section for the held item:
      changing a value moves the item that frame and writes the table, as the tab already
      does for gun tuning. Done when editing a row and relaunching with no build moves the
      item, a slider in play moves it at once and persists, and all-zero rows change
      nothing. Cover the table's parse and write-back with tests and add a probe that a row
      changes the attach offset by exactly that row. Design goal: tune the last centimetre
      of a handle from inside the game. Big picture: item H2 of 3. effort: medium

- [x] U0. Unit tests for what the probes checked by arithmetic. The probes cost 21 hours
      over 8-10 Oct and found three defects; two of the three were plain Python wrong
      (a per-hectare forage count rounding to zero on the 50 m level; a tuning product).
      Pin that ground with tests under Scripts/dev/tests, no engine launch, two files:
      (1) test_weapon_tuning.py: for every row of combat/gun_tuning.csv, the number the
      builders bake equals the row -- melee_tuning.throw_damage and melee_specs against
      the Knife and Axe rows, weapon_specs._weapon_specs against each gun's row for every
      TUNE_STATS column, and a head hit's worth is the row's throw damage times
      COMBAT.head_multiplier, which is greater than one; a row under its stat's minimum,
      a missing column and a weapon with no row each fail or fall back the way
      gun_tuning.read_table says. (2) test_placement.py: survival/forage_placement's
      forage_counts gives at least one mushroom and one canteen on the 50 m probe level
      (50 m by 50 m, 0.25 ha) as on the 200 m one; scatter_forage keeps every item
      TRUNK_CLEAR_CM from a trunk, inside the margin, and off the start; and the zombie
      and clothing placements (world/level_placement.py, clothing/scatter.py) hold the
      same three rules on both sizes -- follow test_clothing_scatter.py's fake forest.
      Any module that needs `unreal` to import gets its table or rule moved into a
      plain-Python helper first, as grip_nudges.py is; do not stub the engine. Done when
      the tests pass, each failure message names the weapon or item and the rule, and
      a deliberate edit (a zero forage count, a halved throw damage) fails exactly one
      named test. No probe, no verifier, no builder: Scripts/dev changes only, plus any
      helper split out. Design goal: a wrong number in a CSV or a placement rule fails
      in 28 seconds at pre-commit, not in a 3-minute launch at night.
      effort: low

- [x] H3. One command to swap a player clip. A new Mixamo clip today means dropping the FBX
      in the cache, adding a row, running the whole player import, then the weapons build.
      Provide a single dev command that takes the role being replaced (knife or axe ready or
      swing, prone crawl) and an FBX, and does the rest: registers it, imports and retargets
      only that clip, and rebuilds only the steps that bake it. It rejects an unknown role
      and says which exist, supports a dry run, and prints the strike moment it detected for
      a swing so a bad one is noticed. Done when swapping the axe swing takes about two
      minutes, the diff shows one changed row and no unrelated regenerated content, and
      swapping back restores it. Cover the row edit and role list with tests and use the
      existing melee verifier and look probe as proof. Document the flow beside the clips.
      Design goal: choosing between three candidate swings takes minutes, not an afternoon.
      Big picture: item H3 of 3, closing the "which clip" loop the animation library opens.
      effort: medium


- [x] Set Debug to be disabled by default in the main menu

- [x] Update the ADS animation to right away go into the ADS mode rather than gliding the camera zooming in gradually. Once the camera is in ADS mode, the gun should get quickly raised from the bottom right area into the ADS marker such that it looks natural. 

- [x] Moving or shooting during save an exit should cancel the save and exit process

- [x] Right click in inventory to use (for equippable items that is equip - guns into an available slot if available, if not replace primary slot, clothes to equip. If a clothing article is already equipped for that slot, quipt the new one from inventory in its place. I, left hand to bring to hands. The use button should be available when in the inventory screen.

- [x] ADS animation slightly jittery after ADS zooms in. Implement the following ADS sequence (Center of screen firmly stays on reticle the whole time):
            -Camera very briefly starts zooming in, in a smooth motion (like it did before - just not as long)
            -snap to ADS view and gun raising animation
            -brief animation of gun gets raised (as it is now) into the reticle so that the crossairs of the gun firmly match the reticle target (as they do now - that works great). Just need to make sure the camera does not jitter here and the gun gets raised into the reticle. 
            -Coming of ADS works great now, there is a brief zoom out phase which works well. (Essentially we will want something similar on the zoom in phase only inverse)
            -Implement camera zoom in / zoom out speed, zoom in duration, gun raise animation duration to be configurable per gun in the guns settings menus. Default should be the same for all.

- [x] Picking up an item from the floor should play a pick up item animation from the floor. 

- [x] In the menu screen, don't load the game yet. Just show the menu and render the current character in the gear that is saved for him. If no character is saved, show the basic character with no gear. 

- [x] Update the character to have pants as an equipped starting item when the game starts (already in the equiptment slot). This also means on loading screen a fresh character should already have pants. (low effort)

- [x] In the inventory mode, the front facing image of the character should represent the current equiptment. Remove the [i] Inventory text. Allow right clicking on a usable item in hand to use it (or use the "Use" key while in inventory mode.). 

## Multiplayer, phase 5: wanderers and the world (moved from
## Scripts/dev/plans/multiplayer_tasks.md; phases 6-8 wait there)

- [x] M27. Wanderers in a world with several players. Senses, aggro, the wendigo's stalk,
      charge, torch ward and "ran too far" rule, zombie attacks and the "Drawn" state each
      choose and keep a target among all living players, switch when the target dies or
      leaves, and never read player 0. All AI runs only on the server; clients get movement
      and animation by replication, and the roar and growl sounds by Multicast. Done when:
      the NPC verifier and probes pass and a 2-client probe has a wanderer aggro on the
      nearer client and switch when that client dies.
      Design goal: Monsters built to hunt one player must choose among many and stay coherent when
      a target dies or leaves, with all AI on the server.
      Big picture: this is task M27 of 36 in the multiplayer project, phase 5 of 0-8 (wanderers
      and the world). The project turns this single-player survival game into one that also runs
      as a PvP game on a dedicated server (32-64 players, teams or solo, characters that persist),
      with single player still shipping from the same code. Phases 0-7 are built and proved on
      this Mac; hosting on GCP comes after and is not part of any task here. This phase is done
      when the monsters and the world behave sensibly with many players spread over the map. The
      strategy is `serversupportsysdesign.md`: section 1 the target, 4.1 authority, 4.2 where
      state lives, 4.8 the two modes, 7 the whole task list; read it before designing, and build
      for the later phases rather than for this task alone. The tasks before this one are done or
      in the same queue; this run's progress file and the git log say what they built. Do not do
      later tasks' work here.
      Both modes: single player and multiplayer both ship. Follow the standing requirement
      at the top of `Scripts/dev/plans/multiplayer_tasks.md` and `serversupportsysdesign.md` 4.8.
      effort: high
- [x] M28. Noise for several players. The GameMode's single last-noise record becomes a short
      list of recent noises (place, loudness, time, who made it), written only on the
      server and queried by the senses. Done when: two clients firing far apart each draw
      the wanderers near them.
      Design goal: Sound-driven AI must work when several players make noise in different places
      at once.
      Big picture: this is task M28 of 36 in the multiplayer project, phase 5 of 0-8 (wanderers
      and the world). The project turns this single-player survival game into one that also runs
      as a PvP game on a dedicated server (32-64 players, teams or solo, characters that persist),
      with single player still shipping from the same code. Phases 0-7 are built and proved on
      this Mac; hosting on GCP comes after and is not part of any task here. This phase is done
      when the monsters and the world behave sensibly with many players spread over the map. The
      strategy is `serversupportsysdesign.md`: section 1 the target, 4.1 authority, 4.2 where
      state lives, 4.8 the two modes, 7 the whole task list; read it before designing, and build
      for the later phases rather than for this task alone. The tasks before this one are done or
      in the same queue; this run's progress file and the git log say what they built. Do not do
      later tasks' work here.
      Both modes: single player and multiplayer both ship. Follow the standing requirement
      at the top of `Scripts/dev/plans/multiplayer_tasks.md` and `serversupportsysdesign.md` 4.8.
- [x] M29. Wanderer population by mode. Standalone keeps the level's fixed count and the
      10-second respawn. On a server the count is a budget: wanderers spawn out of sight
      near players and are removed when no player is within a configurable range, with a
      cap per player and for the server. The settings join the monster tuning table. Done
      when: single-player spawn probes are unchanged and a `--net` probe shows the count
      following two clients standing far apart.
      Design goal: A fixed monster count cannot serve both one player and sixty-four. Make
      population follow the players on a server and leave single player as designed.
      Big picture: this is task M29 of 36 in the multiplayer project, phase 5 of 0-8 (wanderers
      and the world). The project turns this single-player survival game into one that also runs
      as a PvP game on a dedicated server (32-64 players, teams or solo, characters that persist),
      with single player still shipping from the same code. Phases 0-7 are built and proved on
      this Mac; hosting on GCP comes after and is not part of any task here. This phase is done
      when the monsters and the world behave sensibly with many players spread over the map. The
      strategy is `serversupportsysdesign.md`: section 1 the target, 4.1 authority, 4.2 where
      state lives, 4.8 the two modes, 7 the whole task list; read it before designing, and build
      for the later phases rather than for this task alone. The tasks before this one are done or
      in the same queue; this run's progress file and the git log say what they built. Do not do
      later tasks' work here.
      Both modes: single player and multiplayer both ship. Follow the standing requirement
      at the top of `Scripts/dev/plans/multiplayer_tasks.md` and `serversupportsysdesign.md` 4.8.
- [x] M30. One world clock. The time of day, the random start time, wind and the night cold
      are driven by the server and replicated through the GameState, so every client sees
      the same sun and moon. Done when: two clients report the same time of day within a
      second after a minute, and the day-night verifier passes.
      Design goal: Everyone on a server shares one sky, so the clock has a single owner.
      Big picture: this is task M30 of 36 in the multiplayer project, phase 5 of 0-8 (wanderers
      and the world). The project turns this single-player survival game into one that also runs
      as a PvP game on a dedicated server (32-64 players, teams or solo, characters that persist),
      with single player still shipping from the same code. Phases 0-7 are built and proved on
      this Mac; hosting on GCP comes after and is not part of any task here. This phase is done
      when the monsters and the world behave sensibly with many players spread over the map. The
      strategy is `serversupportsysdesign.md`: section 1 the target, 4.1 authority, 4.2 where
      state lives, 4.8 the two modes, 7 the whole task list; read it before designing, and build
      for the later phases rather than for this task alone. The tasks before this one are done or
      in the same queue; this run's progress file and the git log say what they built. Do not do
      later tasks' work here.
      Both modes: single player and multiplayer both ship. Follow the standing requirement
      at the top of `Scripts/dev/plans/multiplayer_tasks.md` and `serversupportsysdesign.md` 4.8.
- [x] M31. Things left in the world. (Reduced by A2, which gave every item and campfire a
      cull distance, dormancy and a late joiner who sees a placed item taken and a fire lit:
      `probe_net_late_join.py`.) What remains: corpses, stuck weapons and chopped trees are
      replicated to players who arrive later, and each thing left in the world has a cleanup
      rule on a server (a lifetime, and a cap on how many exist) so a long-running world does
      not fill up. Standalone keeps today's behaviour. Done when: client 2 joining after
      client 1 dropped an item, lodged a blade in a tree and killed a wanderer sees all three.
      Design goal: A server runs for days and players arrive at any time: what was left in the
      world must be there for latecomers, and must not pile up without limit.
      Big picture: this is task M31 of 36 in the multiplayer project, phase 5 of 0-8 (wanderers
      and the world). The project turns this single-player survival game into one that also runs
      as a PvP game on a dedicated server (32-64 players, teams or solo, characters that persist),
      with single player still shipping from the same code. Phases 0-7 are built and proved on
      this Mac; hosting on GCP comes after and is not part of any task here. This phase is done
      when the monsters and the world behave sensibly with many players spread over the map. The
      strategy is `serversupportsysdesign.md`: section 1 the target, 4.1 authority, 4.2 where
      state lives, 4.8 the two modes, 7 the whole task list; read it before designing, and build
      for the later phases rather than for this task alone. The tasks before this one are done or
      in the same queue; this run's progress file and the git log say what they built. Do not do
      later tasks' work here.
      Both modes: single player and multiplayer both ship. Follow the standing requirement
      at the top of `Scripts/dev/plans/multiplayer_tasks.md` and `serversupportsysdesign.md` 4.8.
- [x] M32. Dev settings and cheats by mode. Standalone keeps every dev tab and cheat as today.
      A client of a server can open the tabs but changes to gameplay tables (guns, monsters,
      player, world) are sent to the server and applied only when the server was started
      with a `-AllowDevTuning` switch; otherwise the rows are read-only and say why.
      Graphics and sound settings stay local in both modes. Done when: both cases are probed.
      Design goal: The tuning tools were built for a solo developer. Keep them for single player
      and stop them being a cheat menu on a shared server.
      Big picture: this is task M32 of 36 in the multiplayer project, phase 5 of 0-8 (wanderers
      and the world). The project turns this single-player survival game into one that also runs
      as a PvP game on a dedicated server (32-64 players, teams or solo, characters that persist),
      with single player still shipping from the same code. Phases 0-7 are built and proved on
      this Mac; hosting on GCP comes after and is not part of any task here. This phase is done
      when the monsters and the world behave sensibly with many players spread over the map. The
      strategy is `serversupportsysdesign.md`: section 1 the target, 4.1 authority, 4.2 where
      state lives, 4.8 the two modes, 7 the whole task list; read it before designing, and build
      for the later phases rather than for this task alone. The tasks before this one are done or
      in the same queue; this run's progress file and the git log say what they built. Do not do
      later tasks' work here.
      Both modes: single player and multiplayer both ship. Follow the standing requirement
      at the top of `Scripts/dev/plans/multiplayer_tasks.md` and `serversupportsysdesign.md` 4.8.


- [x] Add Axe and Knife to the loot table for monsters. 15% change to drop either of the time. 

- [x] Increase the glimemer distance for items by 30%. Delay the initial glimmer of the item by 5 seconds. 

- [x] R1. A thrown item reaches the other clients for the whole of its flight (the small fix, ahead of R2). In online play another player's thrown axe shows once in mid-air and then at rest, not flying start to finish; single player is fine. The suspect, not confirmed: a carried item is `DORM_DormantAll` (`combat/item_world.py` `_author_rest`), the release (`author_into_world`) calls `SetReplicates(true)` on it in that state, and only its own next Tick sets `DORM_Awake`, so the replication graph (`AddActor_Dormancy`) takes it in as a still actor, sends it once and closes its channel; the landing's sleep then sends it once more, which is why `probe_net_throw.py` passes. The other candidates: the client's hide until `InWorld` arrives, and the item's rate alone (`net/relevancy_consts.py` `ITEM`, 10 Hz). First find which: one throw under `uepy.py --net --clients 2`, logging on the server the item's `NetDormancy` at the release and each frame of the flight, and on client 2 the frames its copy exists, is visible and moves. Write the finding in `Scripts/net/docs/history/multiplayer.md`. Then the fix where the finding points, and no further: for dormancy, the release wakes the item (`DORM_Awake`, `Dormant` false) before it is made a replicated actor; check whether any other way into the world starts replicating a dormant item and say so. Not here: smoothing, prediction, the rate (R2 replaces the position stream; a flight that hops at 10 Hz is this task's done). Proof: `probe_net_throw.py` with one new check (client 2's copy is visible and at five or more different places between the release and the rest), clean with `--lag 120`; `probe_net_late_join.py` and `probe_net_pvp.py` unchanged. If the finding is none of the three, stop with the finding. effort: low

- [x] R2. A thrown item flies on every machine from the release, not from replicated movement. Today the flight (`combat/weapon_component/throw_flight.py`) runs only behind HasAuthority and the clients see the server's positions (`SetReplicateMovement(true)`, 10 Hz, no smoothing), and the thrower sees its own throw a round trip late. The standard design instead: the release is sent once and every machine runs the same kinematic curve, and **no client's flight depends on the item's replicated actor**, so whatever delays or closes that actor's channel cannot touch what is seen in the air. (1) The launch goes out on the thrower's weapon component, which every client already has: `Fx_Throw` carries the item's class, `Start`, `Velocity` and the server's time at the release. (2) Each client flies a stand-in: a local, unreplicated actor of the item's class, carried along `start + v t + g t^2/2` under `THROW_GRAVITY_Z` with the same square-up and tumble, from the server's clock (`GetServerWorldTimeSeconds`), so it starts where the server's is now and a late message shortens the flight, not shifts it. One authoring of the curve for the server's item and the stand-in, not two. (3) The thrower predicts: its stand-in leaves the hand on the click, and the server's launch names that one (no second axe, no pop); a refused throw (`Server_Throw`'s checks) takes it back. (4) The server alone judges the strike, once (`throw_strike.py`), and the end is told reliably: where it lies or lodged, and the body and bone it is in. The stand-in stops there, blended over a few frames if its own curve ended elsewhere, and is destroyed on the frame the replicated item is visible in its place; the replicated item is hidden on clients while it flies, and its movement is not replicated until it rests. (5) The lit stick and the hot blade look the same on the stand-in as on the item. Single player stays one plain call on one machine: no stand-in, the item itself flies (`serversupportsysdesign.md` 4.8). Not here: lag compensation of a throw. Proof: `probe_net_throw.py` extended (on client 2 a thrown axe is visible within 100 ms of the release, sampled every frame it is never more than 30 cm off the curve and never stands still in the air, exactly one axe is visible on every frame from the release to a second after the rest, and it rests where the server's does; the same on client 1, from the frame of the click; a refused throw leaves the axe in the hand), clean with `--lag 120` and under packet loss if the harness can make it (say if it cannot); `probe_net_pvp.py`, `probe_net_fx.py`, `probe_net_late_join.py` and the `--game` `probe_throw*` set unchanged. Update "Melee, the guard, the throw and the take" in `Scripts/net/CLAUDE.md` and its history. effort: high

- [x] when in multiplayer game, and menu is opened, the single player button should not be present in the menu. Should only be visible when not in game. (very low effort)


- [x]	(polish - UI) Update the title level to be with night light with trees, matching thick tree density from the middle of 1000m level. effort: low

- [x] (polish - UI) Instead of exit called off, update the wording to "exit interrupted".  effort: low

- [x] (polish - UI) Dev all guns option - make it not available title screen (visible in game only) effort: low

- [x] (bug - UI) -Dragging items does not work from weapon slot to main hand. I should be able to drag from weapon slots to main hand. effort: low

- [x] (bug - graphics) in save and exit state character legs shake and twitch

- [x] (feature - graphics) Make what "engine quality" hides tunable in game. Today the GRAPHICS SETTINGS tab has one row, engine quality (0-3), which `BP_GraphicsTuner` applies with `SetOverallScalabilityLevel` (`graphics_menu/gfx_tuner.py` `_author_level`): every engine quality group moves together, at the stock `BaseScalability.ini` values (the project has no `Config/DefaultScalability.ini`). So Lumen's cost, the shadow atlas and cascades, post-processing, effects, textures and shading cannot be tuned apart, and High can only choose between level 1 and Epic. `graphisOptimizationStrategy.md` measured why that matters (200 m map, High, 43 ms): Lumen one level down saves 8 ms, and Epic's 4096x2048 shadow atlas is most of the 14 ms shadows cost. Build: (1) one row per quality group in place of the one engine quality row, each 0-3: Lumen GI quality, reflection quality, shadow detail, post-processing, effects, textures, shading, foliage. Leave out the groups whose every cvar already has a row (view distance, anti-aliasing) and say which you left out and why. (2) Two direct rows for the shadow numbers the strategy names: shadow resolution (`r.Shadow.MaxResolution`) and shadow cascades (`r.Shadow.CSM.MaxCascades`); confirm in the engine's `BaseScalability.ini` that those are the cvars that differ between the tiers on this engine version, and use the ones that do. (3) How a group row is applied is yours to find: per-group setters on GameUserSettings then `ApplyNonResolutionSettings`, or the `sg.*` console variables. Whichever it is, the existing cvar rows must still win over the group they sit in (shadow quality, shadow and view distance, volumetric fog, the GI, reflection and AA methods), a group that did not move is not re-applied (as `TUNER_LEVEL_APPLIED_VAR` does today), and never `ApplySettings` (the Mac hang, `graphics_menu/CLAUDE.md`). A console command outranks scalability, so check that a row which has once set a cvar by console does not leave a group row unable to move it afterwards, and say what you found. (4) No change to what any preset looks like or costs: every new column's default is what that preset's engine quality gives today (0, 1, 3, 3), `graphics_tuning.csv` is rewritten with the new columns, and a saved Custom row from before the change (`gfx_save.py`) loads with its old engine quality spread over the new rows, not reset. Redefining High is not this task. (5) For each cvar a new row drives, read its flags in the engine source and list any that are cheat or read-only, which will not move in a shipping build (as the brightness row already notes for `r.ExposureOffset`). Proof: `verify_graphics_menu.py` and `gfx_tuner_checks.py` extended (the rows exist with their limits, one apply per group and only when it moved, no `ApplySettings`); one `--game` run that picks High, nudges Lumen GI quality 3 to 2 and shadow resolution down one step, and reads back from the engine that those cvars and no others changed, then picks Low and reads back today's Low values; the frame time before and after the Lumen nudge at the strategy's forest spot, reported beside its 8 ms. Update `graphics_menu/CLAUDE.md`, its history and `systemDesign.md` section 0. effort: medium


- [x] P1. (feature - animation) Lying down is a real prone, in place of the zombie crawl: the idle and the forward crawl (P2 adds the other directions). Today the player's prone is Mixamo's `ZombieCrawl` (the `prone_crawl` role), played at 1.5x, and lying still is that clip held on one frame. Measured in the animation library (`Scripts/dev/anim_library/README.md`), each clip on its own rig: the zombie crawl's head goes 25 to 62 cm against a 40 cm prone capsule, its hands reach 59 cm, its hips bob 8 to 23 cm and its knees dip under the ground. The pack's `anim_Prone_Idle` (1.0 s loop, propped on the elbows) and `anim_Prone_Fwd_Loop_R` (1.0 s, 63 cm/s), in `/Game/FreeAnimationLibrary/Animations/UnarmedProne`: head 38 to 41 cm, hands 4 to 8 cm, hips steady at 13 cm, knees never under 5 cm. Wanted: on the motion-matching player, lying still plays the idle loop and crawling plays the forward loop, with the hips on the ground and nothing under it, empty-handed and with each gun. What is known: the clips are on the pack's own UE5 mannequin, so they need retargeting onto the player's skeleton; `import_lyra.py` does that for Lyra's clips, which are on the same rig (a row per clip, the plain retargeter), and `swap_clip.py` cannot do it (it takes a Mixamo FBX). The forward loop carries its travel on the root bone (the root ends 63 cm on) with root motion off, so the travel has to come out of the copy the game plays: a crawl that slides forward and snaps back each loop is the failure to look for. Constraints: the stance line's nodes are `combat/stance_clips.py`'s alone; no clip in it may have root motion; the older skins keep what they play; the crawl's speed (about 120 cm/s) does not change, so pick the play rate as the crouch walk's was picked and write down the slide left; bring in the clips so that P2 can add four more without a second import path. Expected, confirm on the worn MetaHuman rather than take from here: the retargeted clips keep those heights, the still hip lift in `body_pose` shrinks to a few cm, and the extra lift while crawling is no longer needed. With a gun the new chest is propped where the zombie's was face down, so look at the rifle, the pistol and the shotgun and correct only what is wrong. Not here: any direction but forward (a sideways crawl plays the forward loop, as today), the pack's stand-to-prone, prone-to-stand and run-to-prone clips (about 2 s each: a design question), the Animation Starter Pack's prone clips, the capsule, the C++ movement. Proof: the stance and body-pose verifiers updated to the new clips; `probe_stance_clips.py` showing that prone and still the head stays under the capsule's top and holds steady, that crawling forward no foot, knee or hand goes under the ground, and that with each gun the hands are off the ground; `probe_net_move_states.py` and `probe_gas_locomotion.py` unchanged; a windowed look lying still and crawling, empty-handed and with the rifle, with the pictures in the report. Rebuild the animation library afterwards so it shows what is in game. effort: low

- [x] P2. (feature - animation) The crawl goes the way the player moves. Needs P1 done (the prone idle and forward crawl from the Free Animation Library): if P1 is not ticked above and in the git log, stop and say so. After P1 a player crawling sideways or backward still plays the forward loop. Wanted: crawling in any of the eight directions plays that direction's motion, on the owning client, on another machine's copy of the player and on a dedicated server. **The two things that decide this task:** (a) where the direction of travel relative to the body comes from. Look first for what the weapon-layers graph can already read and for state that already replicates; a new RPC or replicated property only if nothing else can say it, and then say why (`Scripts/net/CLAUDE.md`, "what a dedicated server poses"). (b) The side clips are slow: `anim_Prone_Left_loop` and `anim_Prone_Right_Loop` cover 38 cm in 2.27 s (17 cm/s), `anim_Prone_Fwd_Left_Loop` and `anim_Prone_Fwd_Right_Loop` 52 cm in 2.0 s (26 cm/s), against a crawl of about 120 cm/s. Write down the slide left in each direction, and if the side crawl cannot be made to read right at that speed, say so rather than hide it: slowing the crawl by direction is a decision for the user, not this task. What is known: those four are in `/Game/FreeAnimationLibrary/Animations/UnarmedProne`; the pack's three backward clips are the forward ones with the asset's rate scale at -1, not other motion, so backward is the forward clips played in reverse and they are not worth importing; the side loop's hips rise to 19 cm at one point (measured on the pack's rig). Constraints: the clips come in the way P1's did; the stance line's nodes are `combat/stance_clips.py`'s alone; no clip in it has root motion; a change of direction does not pop (a strafe reversed or a crawl turned backward must not snap the pose). Not here: the stand-to-prone and prone-to-stand clips, turning in place while prone, the crawl's speed, the capsule, the C++ movement, the older skins. Proof: the stance verifier knows every direction's clip; `probe_stance_clips.py` showing that each of the eight directions plays its own motion and not the forward one's, that nothing goes under the ground, and that a left-to-right reversal does not snap; one `--net --clients 2` check that client 2 sees client 1 crawl sideways and backward as client 1 does, clean with `--lag 120`; `probe_gas_locomotion.py` unchanged; a windowed look crawling to the side and backward, with the pictures in the report. Rebuild the animation library afterwards. effort: medium

- [x] Add the leaf sound that bushes make when a player passes near trees that have low leaves that can be walked through. 

- [x] Replace pistol with SM_1911_02

- [x] Replace shotgun with SM_Shotgun_02

- [x] G1. (polish - graphics) The grass fills the ground and is dark enough for a spooky forest, on `Lvl_Forest_200m` only, at no extra instances or triangles. Today the levels plant one library clump, `grass_02_09_mesh` (`forest_generator/undergrowth_meshes.py`, spec `HISM_Grass_02_09` in `grass_placement.py`), with the pack's own material: 54 cm across at about 1.1 clumps per m², so roughly 15% of the ground is under grass and it reads as light green tufts on bare terrain (pictures: `assets/generated/undergrowth/undergrowth_*.png`). Three changes, one re-import: (1) **Colour.** A material instance of our own under `/Game/Forest/Materials`, child of the pack's `grass_02_09_Mat`, set to a dark, desaturated olive through the parameters the parent already exposes (`Tint`, `Brightness`, `Saturation`, `ColorVariation`), and the grass cells draw with it (a spec's `material_paths` is the cells' override; it is empty today). `Tint` ships with alpha 0, which may be its strength and not unused: find out what the alpha does in `MA_Grass` before choosing values, and say what you found. Write to no pack asset. (2) **Ground.** The terrain under the grass (`M_Forest_Ground_PBR`, authored in `generate_forest_level.py`) is brought to the grass's hue and darkness, so a gap between clumps stops reading as bare ground. The colours for both live in one small constants place, each with a one-line reason. This material is shared, so the 1 km and probe levels' ground changes with it: expected, say so in the report. (3) **Width.** Each clump is planted about 1.8x wider at the same height (the spec's `width_jitter`, about 1.55-2.1 in place of 0.85-1.20; the importer's XY scale is already separate from Z). That is about 3.2x the area per clump, roughly 40% of the ground covered. If blades look oversized at 1.8x, come down and write the value you settled on and why. Constraints: counts, tiers, cull distances, density and the bushes do not change; `forest_import/undergrowth_assets.py` today checks that cells have no override material and that a mesh depends on nothing outside its listed packages, so update both checks to expect the new instance, not delete them; the new instance is committed content (not under an ignored pack folder), and `dev/tests/test_undergrowth_meshes.py` must still pass; a new `Scripts/` module needs its package map line. Not here: `Lvl_Forest_1000m` (not regenerated or re-imported; its grass keeps the pack material until the user has seen the pictures), any density raise, runtime-scattered grass, the pack's wind, deleting the unused generated meshes (`foliage_meshes.py`, `/Game/Forest/Procedural`). After the import run what a re-import needs: `place_forage.py`, `build_clothing.py`, `build_day_night.py`, `build_sound.py` (the footstep step is not needed, the bush mesh does not change). Proof: unit tests and `ruff check --config Scripts/ruff.toml` clean on every changed file; `verify_Lvl_Forest_200m.py` passing with the updated checks; frame time on the 200 m map at Medium and High, same spot and time of day, before and after, with the grass hidden and shown, reported as numbers (wider masked clumps cost overdraw: if grass at Medium costs over 7 ms, say so and stop short of tuning); windowed pictures at noon and at night, at Low, Medium and High, from standing height looking across the ground and looking down, saved beside the old ones under `assets/generated/undergrowth/` with a `g1_` prefix and named in the report. Update the grass paragraphs in `Scripts/forest_generator/CLAUDE.md` and `systemDesign.md`, and add the result to "Library grass and bushes" in `graphisOptimizationStrategy.md`. effort: medium 

- [x] Implement a carry animation when a character is standing, walking, jogging or sprinting with a rifle or a shotgun. Crouching / prone will be a separate task.

- [x] Implement a carry animation when a character is crouching with rifle or a shotgun. prone will be a separate task.

- [x] For ADS animation implement both hands to be fitted to the gun models. Add a verifier for this logic - checking that he hands are fitted to the guns in the ADS holds. (fingers will be a separate task). Implement this as automation that will be used in future gun integrations.

- [x] Implement finger bending such that character fingers are fitted to the weapons when holding them for rifles. this will be used as automation for future gun integrations. (shotguns / pistols will be a separate task)

- [x] Implement finger bending such that character fingers are fitted to the weapons when holding them for shotguns. this will be used as automation for future gun integrations. (pistols will be a separate task)

- [x] Implement finger bending such that character fingers are fitted to the weapons when holding them for pistols. this will be used as automation for future gun integrations.

- [x] Implement a reload animation for AKM and sniper rifle. Should be the same one. 

- [x] Implement a reload animation for Pistols.

- [x] Implement a reload animation for Shotgun.
- [x] ADS: the player's own hair floats in front of the sight camera. `weapon_component/head_hide.py` hides the head bone with HideBoneByName on skinned meshes only; the six MetaHuman grooms (`metahuman_paths.GROOMS`: Hair, Eyebrows, Eyelashes, Mustache, Beard, Fuzz) are GroomComponents and are never hidden. While on the sights (the existing `SightSeat > HEAD_HIDE_SEAT` branch), also SetOwnerNoSee(true) on the Face mesh and on every groom, and false again on the else arm and in `dead.py`. Per view only: other players must still see the full character. Add a variant of `body_parts.author_parts_no_see` filtered to those components; do not hide the body, the arms or the gun, and leave HEAD_HIDE_SEAT as it is. Set bCastHiddenShadow on them so the shadow keeps its head. Extend `verify/head_hide.py` and `probes/probe_head_hide.py` to cover the grooms. Confirm in a windowed run that strand hair honours OwnerNoSee and save a sight picture per gun (`OW_SIGHT_SHOTS=1`) for review; if it does not, say so and hide the grooms another way for the owner only. Report whether the Hat and Glasses garments need the same.
      effort: medium

- [x] Standing still with a gun, turning the view should make the character shuffle-step to follow, as the motion-matching sample's turn-in-place does. Today the legs stay planted and the upper body winds round over them, up to a full circle. Requirements: use the sample's own turn-in-place rather than a new step animation; the body must still face the camera at once, so the gun stays on the crosshair; the feet must not slide; it must work on other players' copies in multiplayer, and unarmed, carrying, and down the sights. Lead (read off the graph, not confirmed in game): `ShouldTurnInPlace` needs an input flag that `gas_locomotion._author_properties` never fills. Confirm the cause in a running game before fixing, and prove the fix with a probe that turns the view 180 and 360 degrees and checks the legs caught up.
      effort: medium

- [x] G2. (polish - graphics) Medium runs engine level 2, the grass is drawn out to 300 m and the trees to 400 m, the grass is twice as dense, and the 1 km map's grass is the 200 m map's colour. Four changes. (1) **Medium's engine levels.** In the Medium row of `graphics_menu/graphics_tuning.csv` the ten engine quality group columns (`gi_quality` … `character_lod`, `gfx_stats.GROUP_STATS`) go from 1 to 2, and the three shadow rows read off a level take their level 2 values (`gfx_stats.SHADOW_BY_LEVEL`: 2048, 1024, 4 cascades). `gfx_stats._LEVELS` (the default a missing CSV falls back to) says the same for Medium. Low, High and Custom do not change. (2) **Draw distance.** Medium's `grass_distance` is 300 m and its `tree_distance` 400 m (today 180 and 180; 300 is already the grass row's upper limit, and the tree row's is 1200). `view_distance` stays a percentage and is not touched: the tuner divides it out, so 300 m is 300 m on the ground (`gfx_tuner_foliage.py`). Confirm in a running game that a grass clump past 250 m is really drawn at Medium, and a tree past 350 m (the 200 m map is 283 m corner to corner, so the tree needs the 1 km map): the cells' own max draw distance (`grass_cells.cell_max_draw_cm`, and the trees' in `tree_cells.py`) and the mesh's last LOD may cut it shorter than the row says, and if so fix that, not the row's label. (3) **Density.** Every grass density setting (layers 1 to 4) draws twice the clumps it does today: `grass_placement.DEFAULT_DENSITY_PER_SQM` 1.1 to 2.2 with the tier shares in `grass_cells.GRASS_TIERS` unchanged, so each layer doubles (about 81,000 clumps on the 200 m map where 40,521 were). Regenerate and re-import `Lvl_Forest_200m` only, then run what a re-import needs (`place_forage.py`, `build_clothing.py`, `build_day_night.py`, `build_sound.py`). The doubling does not reach `Lvl_Forest_1000m` here (about 2 million clumps and a larger `.umap` than today's 185 MB: say in the report what it would be; another task does it); the probe level is regenerated only if its verifier needs it. (4) **The 1 km map's colour.** `Lvl_Forest_1000m`'s grass still draws the pack's spring-green material; it draws `MI_Grass_02_09_Dark`, the same instance and numbers as the 200 m map (its ground is already dark: the ground material is shared). Colour only: its clumps keep their count (about 1.0 M, at 1.1/m², not G2's 2.2), their places and their narrow width, so `grass_look.py` has to tell which levels have the colour apart from which have the wide clump (today `DARK_GRASS_LEVELS` means both). How it gets there is yours to choose (a re-import with the density held at today's value, or the override set on the existing cells), but the generated import and verify scripts must agree with the level: `verify_Lvl_Forest_1000m.py` passes and holds the cells to the instance, as the 200 m one does. If the level is re-imported, run what a re-import needs on it too, and `dev/check_saved_navmesh.py` after. The title level is not changed. Constraints: the clump, the 200 m map's width, the colours' numbers and the bushes do not change; follow `Scripts/graphics_menu/CLAUDE.md` for rebuilding the menu after the CSV changes (one build per warm headless editor); a player's saved Custom row is not rewritten. Proof: unit tests and `ruff check --config Scripts/ruff.toml` clean on every changed file; `verify_Lvl_Forest_200m.py`, `verify_Lvl_Forest_1000m.py` and the graphics menu's verifier passing; `probes/probe_grass_look.py` windowed, before and after, grass shown and hidden at Medium and High, as numbers, plus the whole frame at Medium before and after (level 2 and the longer draw distances cost frame time apart from the grass: report each change's share if it can be told apart, and if Medium goes over 33 ms say so and stop short of tuning it back); the twelve pictures saved beside the old ones with a `g2_` prefix (`OW_GRASS_PREFIX`), and from the 1 km map a noon and a night picture at Medium looking across the ground (`g2_1km_…`), with the frame time there at Medium before and after. Update the grass and preset paragraphs in `Scripts/forest_generator/CLAUDE.md`, `Scripts/graphics_menu/CLAUDE.md`, `systemDesign.md` and "Library grass and bushes" in `graphisOptimizationStrategy.md`.
      effort: medium

- [x] G3. (polish - graphics) A grass instance is a wide patch, not one small clump, on `Lvl_Forest_200m`. Needs G2 done (the doubled density stays, as a setting the player can lower): if G2 is not ticked above and in the git log, stop and say so. Today an instance is `grass_02_09_mesh`, 54 cm across, stretched 1.55-2.10x sideways by G1 (`grass_look.WIDE_WIDTH_JITTER`): the same blades spread thinner, so it reads as flat spiky stars on bare ground. The generated patches it replaced were 1.1 m across and overlapped into a field. Wanted: one instance covers about 1.1-1.5 m of ground with blades as thick as the clump's own, at the same knee height, at the same instance count as after G2. **Find out first, then choose:** (a) measure every mesh in the grass pack in the editor (`/Game/PN_GrassLibrary/Meshes/grassMesh`, 83 meshes in 12 families; we use one): bounds, triangles per LOD, material. Write the table into the report. If one is already a wide, knee-high patch of the same kind of grass at a sane triangle count, plant it: no build step. (b) Otherwise build our own patch under `/Game/Forest` (never write to a pack asset): several copies of the clump, turned and offset, merged into one static mesh with its own LOD chain, built from the clump's lower LODs so LOD0 stays near the clump's 2,152 triangles and no more than about twice it; say which LODs and how many copies you settled on and why. Either way: the stretch goes back to about the default (`width_jitter` near 0.85-1.20; the patch is wide, the blades are not stretched); the patch draws with the dark look (`MI_Grass_02_09_Dark`, or an instance of the chosen mesh's own material set from the same numbers in `grass_look.py` if its parent differs); it still sways by the pack's wind and still has no collision; `undergrowth_meshes.py` holds the new mesh's record and packages, `.gitignore` lets through exactly what it needs and `dev/tests/test_undergrowth_meshes.py` passes; if a second 8k atlas would be committed for (a), say so and prefer (b). Constraints: counts, tiers, cull distances, G2's density and draw distances, the bushes and the colours do not change; `Lvl_Forest_1000m` is not regenerated; a new `Scripts/` module needs its package map line (`package_map.py --fix`); keep new modules small. After the import run what a re-import needs (`place_forage.py`, `build_clothing.py`, `build_day_night.py`, `build_sound.py`). Proof: unit tests and `ruff check --config Scripts/ruff.toml` clean on every changed file; `verify_Lvl_Forest_200m.py` passing with the mesh checks updated to the new mesh, not deleted; `probes/probe_grass_look.py` windowed, before and after, grass shown and hidden at Medium and High, as numbers (if grass at Medium costs over 7 ms, say so and stop short of tuning); the twelve pictures with a `g3_` prefix beside the `g2_` ones, and one sentence on whether the ground now reads as filled when looking down at Medium. Update the grass paragraphs in `Scripts/forest_generator/CLAUDE.md`, `systemDesign.md` and "Library grass and bushes" in `graphisOptimizationStrategy.md`.
      effort: medium

- [x] If a player dies, rather then giving him the option to retry and start again, the option should be to go back to main menu. And then from the menu if the player wants they will be able to start a new game. 

- [x] Unarmed sprint: swap the forward loop for the sample's relaxed one. Sprinting straight ahead without a gun should play `M_Relaxed_Sprint_Loop_F` (`/Game/GAS/Characters/UEFN_Mannequin/Animations/Sprint`) where it plays `M_Neutral_Sprint_Loop_F` today. Only that one clip changes: the diagonal loops (`M_Neutral_Sprint_Loop_FL`, `_FR`) look good and stay, as do the Neutral starts, stops, pivots and the run/walk-to-sprint transitions. The sprint with a long gun (the `CarrySprint` overlay, `combat/carry_pose.py`) is fine and must look the same after. Lead (read off the assets' strings, not confirmed in the editor): the forward loop sits in `PSD_Dense_Stand_Sprint_Loops` and `PSD_Sparse_Stand_Sprint_Loops` under `MotionMatchingData/Databases`, and maybe the extreme-sparse set; find every sprint loops database the `CHT_PoseSearchDatabases` chooser can offer and swap it in each, by a build script and not by hand, keeping the entry's settings (mirroring, sampling range). Check the relaxed clip's travel speed against the neutral one's and say what it is: the feet must not slide at the sprint speed and the play rate must not visibly scale (`probes/probe_gas_anim_speed.py` measures this). Veering from forward to a diagonal and back must blend without a pop in posture; if the two styles seam visibly, report it with a capture rather than swapping the diagonals too. Must hold on other players' copies in multiplayer.

- [x] Update the melee weaponless attack animation to a punching animation

- [x] Some of the character model peeks through the current jeans and jacket clothing when it's equipped as the character moves around

- [x] Improve foliage to be thicker in an efficient way. Right now there is a still a fair bit of ground seen through the grass. Allow for more foliage to exist such that it largely covers the ground tunable through the menu. Increase the max setting to 8 (I.E current max is 4)

- [x] Improve foliage to be a variety of types of grass throughout the forest. Some areas may have more of one grass type, other areas more of another grass type. Some areas may have mixed grass types. Use 7 differnt grass types.

- [x] Implement another level that is 400x400 called "Horde Survival". The level should be surrounded by a dense forest (same density as center in the 1000x1000). Center should only have scarse trees. In the center there should be a defensible area surrounded by chest high rocks. There should be 3 entrances / opennings into the defensible section.

- [x] In single player main menu there should be an option to do "Horde Mode" - new horde level and "Survival" - the current 1000x1000 level. Not accessible in multiplayer for now.

- [x] On the horde level there is a permanent campfire in the center of the level. (Create a new object for this). This campfire like a regular campfire pulls in zombies on the map. 

- [x] On the horde level implement difficulty levels that gradually increase every 3 minutes. Difficulty levels increase the number of total NPC monsters that exist on the level. Level 1 - 4 monsters, Level 2 - 6 monsters, Level 3- 8x etc. For every 9 zombies spawned there should be one wendiego. I.E no wendiegos until level 4 - where there is one, then level 8 there is 2 etc.

- [x] On the horde level update the permanent campfire to have an attraction range that is indefinite (I.E applies to the whole level)

- [x] Instead of debug on / off in the main menu, create a debug settings tab (in the same format that we have other settings subsections in the menu). In this tab monster vision and agro lines and shot trajectory are 2 separate settings. (Currently debug on / off enables both) Reduce the thickens of the monster agro vision lines (right now they are way too thick). Add a cheat to get full stats when used. 

- [x] Make the GUN SETTINGS tab's save (Enter) work in a packaged build: today it runs through Python, which only the editor has, so tuned values are stuck in the game's .sav file. Have it write a CSV the project can take back as the new gun defaults (gun_tuning.csv), keeping the editor's save as it is. Prove it in a real packaged build by tuning a value, saving, and showing it land in gun_tuning.csv.
      effort: medium

- [x] When firing without ADS, every shot should gradually increase the spread range for automatic weapons (and come back relatively quickly when firing stopped). I.E the more you fire continuously the more random the shots become as the hands start shaking. Stopping briefly should bring this spread range down in a smooth motion.

- [x] When switching from hipfire or over the shoudler aim to ADS, the target aim location jumps which is incorrect. It should stay consistent with where the player was aiming prior. State machine flow shoudl be 1. Brief gradual zoom in 2. Switch to FPS view. 3. Bring gun into frame from the side over a few frames. 4. Gun from the side aligns with reticle target.

- [x] Add refresh command to dev-team that can be called mid run, to re-read tasks.md and update the queue based on its content. (I.E if tasks were removed then remove them from queue, and if tasks were added, add them to queeue). Essentially re-read incomplete tasks and set the queue to that. Complete current task regardless and do not update it even if it changed. I.E if mid run, do not read the first incomplete task into the refreshed queue. 

- [x] For shotgun, add pellet spread width as a configurable parameter in the guns tuning menu for shotgun

- [x] Implement flipbook sprites for blood splatter in the points of contact. Smaller for limb contact. Largest for head contact. Medium for chest contact.

- [x] (QOL - small) polish - QOL. If a weapon gets picked up but there is no weapon in hand, it should go to hand. (melee or ranged)

- [x] (polish) Crawl animation legs are too wide, fix them to be natural

- [x] (implement) zombie combat - use scratch animation for attack

- [x] Punch animation for attack, alternate between A_UAL1_Punch_Cross and cross at random on each hit. 

- [x] Use A_UAL2_TreeChopping_Loop if the character is hitting a tree with the swing.

- [x] The blood splatter pop up animation has a few frames where it appears and a few frames where it disappears. Remove those, just keeep the maximal shape frame, and slightly reduce the time that it stays up. (otherwise hanging blood drops stay in the air after the monster dies)

- [x] Measure how the drawn hands hold the guns. The grip is fitted on the hidden UEFN mannequin and the gun is attached to it, but the MetaHuman is what's drawn, retargeted rotation-only, and every grip check (verify/gun_hold, verify/finger_pose, probe_gun_hands) measures the mannequin. Make the grip probe measure the drawn Body's hands and fingers against each gun's real mesh, for every gun standing, walking, crouched, sprinting and down the sights at pitch up/level/down, with close-up screenshots per gun and state. Report: wrist offset drawn vs mannequin, and per finger, penetration and gap.
      effort: medium

- [x] Pin the drawn MetaHuman's wrists to the mannequin's with hand IK goals in the retarget, so the gun sits in the drawn hand. Keep the mannequin the gameplay truth (gun socket, hits, server); nothing may change for the server, which draws no MetaHuman. Prove it with the drawn-hand grip probe: wrist offset near zero in every gun state, and no regression in the body's look elsewhere.
      effort: medium

- [x] Make the fingers hold every gun, using the drawn-hand grip probe's results with the wrists pinned. Fit each gun's finger pose on the MetaHuman's own hand against the gun's real mesh (not the outline boxes), and hold it over the fingers in every gun state, carry included; the trigger finger at the trigger. Goal: no visible penetration, finger pads on the surface, in the probe and the screenshots. Retire or fix the old mannequin fit (finger_fit.close() and swing() fall back to the clip's pose even inside the gun; riding() skips the first finger bone). Add runtime fingertip IK only if the wrist-pinned results still drift.
      effort: high

- [x] Stop the cook's ~300 `LogBlueprint: Warning: Node '...EdGraphNode_Comment_N' missing NodeGuid` lines at the source. Cause: in UE 5.8, `UBlueprintGraphEditor::AddCommentNode` (`Engine/Source/Editor/BlueprintEditorLibrary/Private/BlueprintEditorLibrary/BlueprintGraphEditor.cpp:1292`) never calls `CreateNewGuid()`; the engine's normal add-node path does (line 1032). Every `ed.add_comment_to_nodes(...)` in `Scripts/` therefore saves a comment with no GUID. Python can't set `NodeGuid`, and the build scripts save in about 119 places (`save_loaded_asset`), so fix it once in C++: in `Source/OtherworldEditor`, register an `FCoreUObjectDelegates::OnObjectPreSave` handler at module startup (unregister on shutdown). Before a `UBlueprint` saves, it walks `FBlueprintEditorUtils::GetAllGraphs` and calls `CreateNewGuid()` on any node whose `NodeGuid` is invalid, so every save path is covered, scripted or by hand. Add a GUID check to `dev/graph_fingerprint.py` too if it would otherwise flag the new GUIDs as changes. After the editor rebuild, resave the Blueprints that already have the problem so the fix sticks (`-run=ResavePackages -PackageFolder=/Game -OnlySaveDirtyPackages`, or re-run their build scripts). Assets seen in the cook log: `BP_WeaponComponent`, `BP_ForestWandererAI_Zombie`, `ABP_WeaponLayers`, `SandboxCharacter_CMC_ABP`, `AC_TraversalLogic`, the Zombie01/Wendigo01 unarmed ABPs, `BP_Axe`/`BP_Knife`/`BP_Stick`/`BP_WeaponItem`, `BP_AmmoPickup`, `BP_BloodSplash`, `BP_BulletImpact`, `BP_BloodSprite`, `BP_FootstepComponent`, `BP_DayNightCycle`, `BP_GraphicsTuner`, `BP_OtherworldGameInstance`. Never resave or modify files under the engine or pack folders. Proof: re-run one build script that adds comments (e.g. `combat/weapon_component`'s), then cook Mac and show zero `missing NodeGuid` lines in the log (grep count before vs after); unit tests and `ruff check --config Scripts/ruff.toml` clean on any changed Python file.
      effort: low

- [x] Add a debug option to enable a trace log for shots that are fired, origin, end, source manequin position, target manequin position and contact point(s). Whatever information would be necessary to help troubleshoot shot issues.

- [ ] In ADS view for pistol, the thumb placement covers the ironsights. Fix the thumb gripping logic for pistols so that it holds correctly around the grip rather than the thumb pointing upwards.

- [ ] For uzi and pistol, the ADS is too close up. set the camera farther back such that the gun is held farther out in front of it. More hands will be seen in the shot

- [ ] The recent wrist pinning improvements we a good improvement in the gun holding animations. There are some remaining issues with the gun holding. Shotgun left hand carry does not hold the gun correctly. Right hand is good. Left hand fingers rest on the outside of the gun rather than holding around it.

- [ ]  The recent wrist pinning improvements we a good improvement in the gun holding animations. There are some remaining issues with the gun holding. For ADS, make the frame duration of the zoom in motion from TPP to ADS configurable in player settings, down to 0 seconds in which case it's effectively skipped, and the view goes straight into FPP from tpp on button press. The gun raise duration should also be configurable - how long it takes to pull out the gun from the side to the crosshairs. 

- [ ] ADS wepapon hover motion (that happens without holding breath) should move in a randomized slow gliding path rather than jitter. 

- [ ] The inventory screen model of the character should also show the weapon that is being currently held in hand. It seems it is shown with lower quality at the moment. It should effectively be a front facing view of the character as you would see him in the world. Move the location of the character image on the right side above the clothing items list.

- [ ] When in game, the multiplayer choice menu should just not be present in the menu. (Right now it's there, but says "from the title"). Remove the logic that has the "from the title" text concept. The menu options should either be present (and visible) or not present (at all) depending on the state of the game.

- [ ] Create a new 4km by 4km map that has a "C" shaped landscape, with water in the middle of the C. Do not worry about implementing swimming or character movement in water. Prevent the ability to walk in the area that has water. One end of the landscape should have a mountain on it. The mountain should have a semi relistic landscape (I.E not just one portrusion). The peak of the mountain should reach 400m. The gameplay on this map should be the same as on the 1k by 1k map. (I.E just the map changes). Add a new option in the game menu for this map "Survival Large" both single player and multiplayer. Vary tree densities throughout the landscape, some areas treeated as forests with density same as we have in the center of the 1km map, areas with less trees around forestes, and field areas with no trees. 

- [ ] There were recent changes made to improve prone position as the legs were too wide. The legs are still too wide in the prone position, like a frog. Make the prone legs more narrow, more aligned with the laying down upper body.