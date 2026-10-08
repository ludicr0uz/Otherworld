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
## queue, phases 5-8, waits in Scripts/dev/plans/multiplayer_tasks.md)
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

- [ ] A3. The inventory as one replicated structure, written when it changes. The record is six parallel arrays plus `WornClass`, rewritten every Tick and replicated independently, so a client can receive a torn set and the view has to check their lengths agree (`view.py`). Replace them with one C++ `USTRUCT` `FOtherworldInventoryRecord` in the `Otherworld` module: a `TArray<FOtherworldItemRow>` (class, slot, loaded, reserve, lit, hot) and a `TArray<TSubclassOf<AActor>> Worn`, held in a `UOtherworldInventoryRecordComponent` (replicated, `COND_OWNER_ONLY`, one RepNotify, Push Model enabled) that `combat/install.py` adds to the player beside the weapon component, with `HandClass`/`HandLit`/`HandHot` as its three `COND_SKIP_OWNER` properties. The weapon component's graphs call `MarkDirty()` on it at each site that changes what is carried (`uebp/nodes/inventory.py`: the serve, the take, the drop, the throw, the shed, the wear, the reload, the shot, the chop, the consume), and the component writes the record once at the end of that frame on the server; the per-Tick rewrite in `record.py` goes. `view.py` reads rows from the struct through a Blueprint library in the same module; `ViewRow`/`ViewTrim` keep their shape. The struct serialises to and from a `USaveGame` byte array (`ToBytes`/`FromBytes`, a version field first), with a unit probe that round-trips a loaded pistol, a lit stick and a worn hat: M35 saves it as it stands. `combat/verify/record.py` checks the new wiring and that no builder still names an `Inv*` array. Proof: `probe_net_inventory.py`, `probe_net_fire.py`, `probe_net_clothing.py`, `probe_net_death.py` clean, with `--lag 120`; A1 at N = 32 shows fewer bytes per connection than before, written in `Scripts/net/CLAUDE.md`. Design goal: one atomic, versioned, serialisable record of what a player carries, sent only when it changes; the save in phase 8 and the loot in phase 7 read the same structure, and no client can ever see half an inventory. Big picture: this is task A3 of 5 in the multiplayer architecture pass, between phase 4 and phase 5 of the multiplayer project (the aim and the strategy are as A1 states: `serversupportsysdesign.md` 1, 4.1, 4.2, 4.6, 4.8, 7). Both modes: in standalone the component holds the record and nothing travels; the single-player profile keeps writing `BP_Profile` until M35, through the same `ToBytes`. Local only: use no GCP or other cloud resource. Never run gcloud, gsutil or anything in `Scripts/server/gcp`; if the task seems to need one, stop and report instead. effort: high

- [ ] A4. What the dedicated server spends on bodies it never draws. `combat/server_pose.py` makes every body on a dedicated server evaluate its full animation and refresh its bones every frame, so that hit bodies and muzzles are where clients see them; at 64 players and the wanderers this is likely the server's largest single cost (A1 says). Measure it first with A1 at N = 32 (`stat anim`, the Insights trace), then: enable Update Rate Optimization for skeletal meshes on the dedicated server (`bEnableUpdateRateOptimizations`, with `AnimUpdateRateParams` tuned so a body more than 30 m from every player is posed at 10 Hz and interpolated, and a body nobody is near at 2 Hz) while the hit history interpolates between samples, which it already does; move `UOtherworldHitHistory` to a ring buffer of fixed capacity per character (no allocation per frame), a `TMap` from character to history, and a capsule test from the sample before any body transform is blended (`SampleAt` currently blends every body first); batch `Multicast_PelletHit` into one `Multicast_ShotHits` per shot carrying an array of impacts. Write the before/after numbers in `Scripts/net/CLAUDE.md`. Proof: `probe_net_lag_hits.py` with and without `--lag 150` still lands 6/8 and 7/8 or better; `probe_net_fx.py` counts the same impacts on client 2; `probe_headshot` and `probe_ads_hit` in `--game`. Design goal: the server poses and remembers bodies at the rate the game needs to judge a shot, not at the rate a screen needs to draw one; the per-pellet and per-frame costs become per-shot and per-sample costs. Big picture: this is task A4 of 5 in the multiplayer architecture pass, between phase 4 and phase 5 of the multiplayer project (the aim and the strategy are as A1 states: `serversupportsysdesign.md` 1, 4.1, 4.3, 4.8, 7). Both modes: single player renders its bodies and records no history, so nothing here runs there; the `--game` probes stay green. Local only: use no GCP or other cloud resource. Never run gcloud, gsutil or anything in `Scripts/server/gcp`; if the task seems to need one, stop and report instead. effort: high

- [ ] A5. Every Server event checks what it is told and how often. The server traces `Server_Fire` from its own muzzle to whatever `AimPoint` the client sends, so a client can fire behind itself; no Server event is rate-limited, so a client can flood the reliable channel; and Blueprint RPCs cannot use the engine's `_Validate` hook. Add `UOtherworldRpcGuard` to the `Otherworld` C++ module, a component on the player (added by `combat/install.py`) with two Blueprint-callable checks every Server event on the weapon component calls first, through a shared fragment `net/guard.py` (`author_guard(g, name, execs)`): `Allow(name)`, a token bucket per event name per connection (`net/guard_consts.py`: fire at the fastest gun's rate plus 20 %, the asks at 10/s, the look report at 30/s, everything else at 5/s) that logs `RPC-REFUSED <name>` and, past a threshold in 10 s, kicks the connection with `ClosedByRpcGuard`; and `AimAllowed(AimPoint)`, which refuses an `AimPoint` more than `AIM_CONE_DEG` (20°) off the server's copy's control rotation (`GetBaseAimRotation`) or more than the gun's range away. `Server_Throw`'s start and speed and `Server_Take`'s reach already check themselves; keep those and add the bucket. In standalone both checks pass without counting. `combat/verify/guard.py` fails on a Server event without the fragment, and `random_checks`' pattern is the model for keeping the table and the events in step. Proof: `probe_net_guard.py` (client 1 sends an `AimPoint` behind itself and the round goes nowhere; `FireForced` held at 50/s sends the SMG's rate and no more; 200 `AskSlot` in a second get client 1 kicked, logged on the server) and every M14–M26 `--net` probe clean with `--lag 120`. Design goal: the server trusts a client's request no further than physics allows and never lets one client's traffic cost the others; this is the validation layer the engine's C++ RPCs get for free and Blueprint ones do not. Big picture: this is task A5 of 5 in the multiplayer architecture pass, between phase 4 and phase 5 of the multiplayer project (the aim and the strategy are as A1 states: `serversupportsysdesign.md` 1, 4.1, 4.3, 4.7, 4.8, 7). Anti-cheat proper (EAC, phase 8) sits on top of this, not in place of it. Both modes: a standalone game has one connection and the guard counts nothing; the `--game` probes stay green. Local only: use no GCP or other cloud resource. Never run gcloud, gsutil or anything in `Scripts/server/gcp`; if the task seems to need one, stop and report instead. effort: high

## Player animation: Game Animation Sample locomotion, then the clips it lacks
## (plan: metahumanAnimationPlan.md Tasks 2 and 3; Task 1, Taro as the body, is done).
## Each item ends with the game playable, its probe clean and a commit; the next item
## starts from that commit. Local only: both sample projects are on this Mac.

- [ ] G1. Import the Game Animation Sample (GAS) into the project, no game change. Write
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

- [ ] G2. The skeleton bridge: decide how GAS clips reach the player's hidden mannequin, and
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

- [ ] G3. Unarmed locomotion from GAS, weapons off. Replace the locomotion half of the player's
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
      that covers them). Design goal: the player's base movement is Epic's shipped motion
      matching, authored by our builder from the imported graph, with nothing hand-animated
      left in locomotion. Big picture: item G3 of 5 (G1–G5) giving the player GAS motion
      matching.
      effort: high

- [ ] G4. The weapon layers back on top of GAS. Re-attach, as linked anim layers over the G3
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
      `--game` smoke run of `Lvl_Forest_200m` is clean. Remove the G3 flag. Design goal: every
      combat animation the game already had sits on the new base unchanged, so G3's locomotion
      gain costs no combat behaviour. Big picture: item G4 of 5 (G1–G5) giving the player
      GAS motion matching; C1–C5 then replace the clips one at a time.
      effort: high

- [ ] G5. Crouch, slide and traversal from GAS (optional; skip if G4 ran late). Wire GAS's
      crouch set to our crouch input and `CharacterMovementComponent` crouch, the slide to
      sprint+crouch, and `AC_TraversalLogic` (mantle, vault, hurdle) to jump against an
      obstacle, each behind its own constant in `combat/` tuning so one can be off. Done when
      a new `probe_gas_traversal.py` crouches, slides and mantles a 1 m block in
      `Lvl_Forest_200m`, `probe_metahuman_body.py` passes, and the verifier suite is green.
      Design goal: the movement set GAS ships for free is in the game where our inputs already
      exist, nothing more. Big picture: item G5 of 5 (G1–G5), the last of the GAS move.
      effort: medium

- [ ] C1. Unarmed punch from Lyra. Replace `MM_Attack_01` (the unarmed attack montage) with
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

- [ ] C2. Melee swings: axe, knife and stick. Today they are built from poses
      (`combat/hold_pose.py`, `knife_anim.py`, `axe.py`). Replace them with clips from a
      Mixamo melee set imported through the existing Mixamo import script (the one the zombie
      packs used), one swing and one ready pose per weapon class. If the clips are not in
      `~/Downloads`, stop before any editor work and end the report asking for them by name.
      Done when `combat/verify/axe.py`, `knife.py`, `chop.py` and `hold_pose.py` are green and
      `probe_metahuman_look.py` with the axe shows the clip, not the pose. Design goal: no
      pose-built swing remains. Big picture: item C2 of 5 (C1–C5) replacing the combat clips
      GAS lacks.
      effort: medium

- [ ] C3. Rifle, pistol and shotgun holds and ADS from Lyra. Replace `MF_*_Idle_ADS` and the
      hand-built `shotgun_pose.py` with Lyra's rifle and pistol hold, aim and ADS sets (the
      shotgun uses the rifle set with the grip offset the shotgun verifier expects), through
      the C1 import entry. GAS's aim offsets stay for pitch. Done when `combat/verify/aiming.py`,
      `aim_pitch.py`, `grip_fit.py`, `shotgun_pose` (its verifier) and `head_hide.py` are
      green, `probe_ads_hit` and `probe_headshot` in `--game` land as before, and the sights
      picture in `probe_metahuman_look.py` is on the barrel. Design goal: every gun pose is a
      shipped clip. Big picture: item C3 of 5 (C1–C5) replacing the combat clips GAS lacks.
      effort: high

- [ ] C4. Hit reactions. The six `MM_HitReact` montages (`combat/hit_reaction.py`) stay unless
      Lyra's or GAS's shove-receive set gives a better front/back/left/right spread on the
      new base: compare on the bridge skeleton, pick one set, and delete the other's import.
      Done when `combat/verify/hit_reactions.py` is green and `probe_hit_react` (or the
      verifier's `--game` partner) shows a reaction from each side. Design goal: a decision,
      recorded in `combat/CLAUDE.md`, not a rewrite. Big picture: item C4 of 5 (C1–C5).
      effort: low

- [ ] C5. Prone crawl from Mixamo. Replace the Quaternius `Swim_Fwd_Loop` stand-in with a
      Mixamo crawl loop through the Mixamo import script; same `~/Downloads` rule as C2.
      Done when the prone verifier and `probe_metahuman_body.py` are green and a prone
      `--game` move shows the crawl. Design goal: the last placeholder clip gone. Big
      picture: item C5 of 5 (C1–C5), the end of the player animation move.
      effort: low
