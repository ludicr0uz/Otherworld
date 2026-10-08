Completed Tasks



(done) -Implement a melee attack for the player (when no gun is equipped)
(done) -implement crouch action


(done) -Increase the inventory size to 10 items
(done) -Add concept of a consumable item, pressing the fire button with consumable selected uses it (I.E eat or drink in case of food). Don't reinvent the wheel, use standard methods for this.
(done) -Implement a "food" and a "water" item to be randomly spawned around the level. Mushrooms in the forest. Also scattered water canteens in the forest. 
(done) -Implement hunger, thirst, and temperature bars for the main character. Hunger and thirst should slowly move downwards. Eating/drinking should replenish respectively. 
(done) -Add concept of debus for characters and NPCs. Don't reinvent the wheel, use stnadard methods for this.
(done) -If either bar is at zero, the starving or dehydrated debuf should be applied to the player. When either of those is applied, the characters HP should go down slowly. 



-

(done) -Implement finger bone mapping when integrating humanoid models from meshy (apply to zombies and player)

(done -There is currently a bug where if a mushroom is eaten, and weapon is next to it in inventory, weapon fires once once the mushroom is eaten


Lower prio

(done)
-Implement ADS and shoulder aim as two separate actions. ADS should show the gun down sights as first person view. Over the should aim should be the equivalent of current implementation. ADS for sniper should be the sniper scope. 

(done)
-implement a block button for the player that reduces damage from the front. (Can be used when unarmed). Reduces stamina on every hit blocked. 


(done)-Implement crouch and prone actions (with approporiate audio levels for movement / footsteps for each). 
-Implement movement sounds for each. 

-Gun fire flash animation


(done) -Require pistol to reload every 8 shots. But have infinite reloads.


(done) -Implement daytime and nighttime (Sun and moon rotation). Sun exists during daytime. Moon exists during night time. During night stars come out also with dim light. Make the daytime / night time duration configurable in world config settings. (Creat new world config settings)


(done) -Add icons beside the health / temparture / food bars, and move them bottom left corner. Make the bars vertical. make them flash when low.
(done) -Move the heath bars center bottom of the screen (next to stamina), below item list. Make the item list icon sizes smaller by about 30%
(done) -When items or weapons are picked up, don't switch to them right away, just add them to inventory. Keep the current active item or weapon active.

(done) Integrate the new gun models that fit into the project to replace current gun models. Use AK 47 for rifle, Use AS Val for sniper rifle. Pistol is missing for now, that's ok - don't integrate yet. 



(partly done) -zombie movement more zombie like

(not done) -Another monster action animation, hide behind trees and slwoly come out

(not done) -Joining online with multiple players

(done - need to tune) -For each gun, implement both varying recoils and varying probabbility cloud around target for where the bullet actually hits. Update the reticle to be larger deppending on the probability of hitting the target. 

(done) Shoulder aim applies a factor making it more likely to hit the center
(done) sitting down also applies a factor 
(done) layying down applies a bigger factor than sittting

(done) When aiming down sights, the bullet should always fire exactly at the center

(done) Recoil should also vary based on position (highest standing, lower crouch, lowest prone)

(done) Recoil and probability of the bullet flying at exact center are naturally two different mechanics. Recoil ajust's the user's reticle, vs probabily cloud for target decides how close to the target the bullet actually fires when the trigger is pressed

(Done) These settings should be tunable for each gun.

(done) Recoil should be both horizontal and vertical, but 4x more vertical then horizontal. Recoil horizontal and vertical height should also be tunable per gun in the guns config file. 


Sep 30

Todo:
(done) -During exit character should not be able to move

(done) -When aiming scoped down with sniper rifle, and scope the weapon animation gets in the way, even with sniper rifle. For scoped aim, the weapon should not be visible for the player. (Sniper and scopes only, regular ADS is Ok)

(done) -When aiming down sights the sound of footsteps is much louder than normal TPP. Volume of actions should not change based on perspective, should always be played as if the viewer is in the location of the character. 

(done) -Implement lootable corpses from monsters, and a UI to loot it. For now add a 50% chance for them to drop water. Implement loot tables.

(done) -Implement a developer tab in the menu for gun tuning. In game I want to be able to tune the gun config table for all guns. Applied immediately as tuned. Saved to csv file that will be version controllde. 

(done) -Implement a developer tab for monster tuning. In game I want to be able to tune monster specs (agro range, agro cone distance, patrol area, damage per hit, run speed, and other specs). Applied immediately as tuned. Saved to csv file that will be version controllde. 

(done) -Implement a developer tab for world tuning. Ability to set current time of day. WHen the game starts it should start at a random time of day.

(Done) -Implement a throw button, any item in hand should be throwable. When holding the throw button, the target arc should be shown. Thrown on release.






Evening:

-The following animations were downloaded: '/Users/alexeysukhov/Downloads/Universal Animation Library[Standard].zip' /Users/alexeysukhov/Downloads/drive-download-20260930T225601Z-1-001.zip /Users/alexeysukhov/Downloads/drive-download-20260930T225405Z-1-001.zip /Users/alexeysukhov/Downloads/drive-download-20260930T225320Z-1-001.zip '/Users/alexeysukhov/Downloads/Universal Animation Library 2[Standard].zip'
Integrate them to be usable in the project. Update the prone crawl animation, crouch animation, shotgun model, pistol model from new ones from this list.

(done) -Implement usage of mouse cursor in the menus within the game

(done) -show bullet trajectories and agro cones in debug mode

(done) -When using the pick-up button, don't pick everything up. Pick up one item at a time that is closest to the reticle target.

(done) -search body kneel animation. Allow every body should be searcheble whether it has items or not. In the loot menu show item icons rather than text

(done) -sprinting and holding ADS or shoulder aim at the same time twitches the screen. fix the twitch.

(done) -For throwing make the default arc higher. Move that throwing ark as a tunable parameter in weapon stats tab. Implement the buttons a a throw button hold to show arc and mouse click to throw. 

(done) -Player is able to shoot a shot during the dying animation after they already died. Review if that's also true for NPCs. When the dieing animation starts, no further actions should be happening (at state machine level).




(done) -Implement an import script for maximo downloads to be compatible with our project. Integrate the imported zombie animations into our project. '/Users/alexeysukhov/Downloads/Scary Zombie Pack.zip' '/Users/alexeysukhov/Downloads/Not So Scary Zombie Pack.zip'



To review:
-The following error is shown lumen surface cache oversubscribed by 5%, consider increasing lumen scene.surfacecache.atlassize



Melee Weapons
(done) Knife
-Gather branches

-throwing items
(done) -Sound louder during ADS


-Wendigo - shots scare it off (certain damage), but it will come back, fire kills it. Burning knife scares it away at melee. Shots attracked zombies if they are around. 






Two housekeeping items surfaced: verify_shotgun_and_health.py is a dead verifier for a retired asset and should be deleted, and build_retarget.py must now run before build_npc_blueprints.py or the wanderers point at dead anim classes.




Next:

(done) -Implement bullet impact animation on the environment

(done) -Hitbox for bullet impact on zombies seems forgiving (around head contact), ensure hitbox aligns with zombie model

(done) -Add a close menu button that is accessible with the mouse in menus

(done) -WHen zombies are attacking they should slightly back and sidestep inbetween attacks in a natural way that prevents them from standing still

(done) -In ADS there should be weapon sway that is strictly aligned with the target. The ADS weapon model view should strictly align with the iron sights

(done) -Implement a 10 second respawn delay for monsters rather than spawning right away (when there are less than 10 existing)

(done) -The character's animation is to run with the weapon pointing forward. Improve to have a jogging animation without the weapon pointing forward. During shots the character should raise the gun. When over the shoulder aim, the gun should also be raised.

(done) -Implement temperature slowly going down at night (magnitude configurable in world tuning)

(done) -Add an axe item

(done) -Implement attacking a tree resulting in wood spawning beside the tree.

(done) -Add a "matches" item. Using matches with wood in the inventory should create a campfire. Stnading near the campfire should increase temperature for the player

(done) -There is a bug where when the player is in ADS mode, and takes a hit from a monster, the ADS jumps to a location that seems to be at crouch level? If the player gets hit in ADS, the target should stay unchanged.


Todo:

(done) -There is an issue with ADS. Right now the camera first goes to ADS sight (I.E looking down in hand), then with the gone moves towards the target. The camera should stay on the target, but the ADS gun image should move up to the reticle. Otherwise every time you ADS there is a quick, shaky up to down moving movement. The user should keep looking forward and the ADS iron sights comes into view meeting the reticle. ADS reticle should only be visible in dev mode now that the iron sights are aligned with it. Over the should aim should still have a reticle. 

(done) -M should not be titled graphics menu, it should be "Game Settings". Within it implement a graphics tab in the dev menu. The low / medium / high / ultra should be top level preconfigured options. Within the menu should have detailed developer level controls for tuning. Implement all major settings that contribute to FPS and overall image appearence, to be tunable. (grass draw distance, tree draw distance, grass density, fog on/off / density, any other that can be identified (including anything with respect to leaves ), lighting settings, brightness. Settings that affect appearence of the sun (I.E brightness or anything else), settings that affect appearence during the night (I.E stars / moon if present etc)


(done) ADS for AKM currently shows part of character head. Solve this in the implementation across all future & current weapons as well (not just AKM). 

(done) ADS available for pistol and axe, should be removed

(done) Thrown items in the air should have some rotation. Add a throwing animation for the character if available in our current library. (if not skip for now)

(done) Star size is too large currently (I.E each individual star is too large relative to the moon. Moon size is good, but star size is largel Also stars should be oriented like a real night sky rather than randomly.

----


(done) During ADS there is a unnecessary jerky movement as the camera first goes into shoulder aim, then to ADS. (two steps instead of one smooth motion). simplify this to be one small movement from current camera location into the ADS view.

(not too bad) For AKM ADS hover movement is not syncronized with the hand holding the weapon. I.E hand moves in a different motion from the AKM

(done) For shotgun holding ADS animation, the thumb sticks out upwards which is unnatural. Likely need different thumb placement for shotgun vs rifles. 

(done) Fix the pisto ADS where the user can see through hand holding the pistol

(Done) Implement a new way for wendigos to agro on you (new state - hunting). When they agro on you, they should first roar (leveraging the zombie roar animation + roaring sound). They should run towards you in a semicircle, stopping behind nearby obstacles (I.E trees), coming closer towards you tree after tree while hiding behind them. WHen they are at close range they should charge directly at you.

(Done) Update FPS metric to be always shown regardless of whether debug mode is enabled or not. Add another custom FPS setting that persists. (So Low / Med / High / Custom as 4 options). Add a save default button for the graphics setting that should modify the csv that defines the default (that I can commit later). Defaults should be driven by the CSV. 


(done) Zombie hitbox seems to have regressed after a recent change attempting to imrpove it. I suspect it may be due to movement or hit animation, sometimes shooting at zombies point blank does zero damage to them and does not register impact (potentially while they are moving).





(done) E button should be the "Interact" button moving forward, not just pick up items. If interact is pointed at an item, the item gets picked up. No functional change, just refactor the usage of this implementatino to a generic interact rather than pick up (to be used in the future)

(done) Create a process to create item icons based on their 3d models and create 2d images to use in the icons (instead of current cartoony images). Update existing 2d cartoony models with icons based on the 3d models.

(done) Holding a lit stick in front of a wendiego should prevent it from attacking you (holding torch. It should try to go around the fire trying to attack you from the side or back. If it's successful at going around at least 90 degrees from the torch, it should attack. After holding it off for 30 seconds, it should run away. 

(done) If a stick is used near a campfire, it should light and become a lit stick that can be carried in hand like a torch until it stops burning. Pressing scope/ads button should be re-purposed to a generic use item when a non-weapon is selected. Pressing this button with a burning stick should raise the stick forward (to be used for warding away creatures that are afraid of fire)

(done) Add a bleeding de-buff that a player has a chance of getting when being hit by a wendigo (33% chance). Implement a generic chance on hit logic on attacks that in the future will be extended to others. Bleeding debuff drains the health for 3 minutes. (50 health total). 

(done) When a knife or axe is equipped, using it on a fire (interact button) should heat it up, making it red, keeping it hot for 20 seconds. If the player has a bleeding debuff, using it stops the bleeding. (I.E cauterizing the wound). Hitting a Wendiego with a burning knife should deal double damage. 

(done) For wendiegos, increase their movement speed when they are running in the semicircle. Alternate semicircle direction at varying intervales. If a Wendiego is shot, it should be in the "enraged" mode and charge directly at the player to attack.

(done) Sprinting should not be allowed sideways or backwards, only in forward facing directions. (60 deg left / 60 deg right at most)


----


(done) -IF or when a wendiego is really far away it should first run directly towards you before it gets into the hunting state machine range. (I.E above 150m). I.E If the player ran really far away it should be able to catch up quickly. WHen in catchup state it should run at the same speed as the hunting movement speed.
(done) -Wendiegos should not use small trees to hinde behind
(done) -Wendiegos should not pause if there is no tree available, should either keep running to the next tree, or if there is no tree available, switch into run at player state. 
(done) -When being warded by a torch wendiego's should change strafe direction at random intervals (at least 1 second long), and roughly twice as often 
(done) -Increase wendiegos hunting movement speed by another 30%
(done) -When hunting it should not hide behind trees that are transparent (thin trunks).
(done) -Increase next tree search range by 50% when hunting

(done) -when taking damage the ads jumps as if the character is crouching
(done) -Remove ads and zoom in for knife and other items
(done) Graphics performance (tier 1)

(done) Default level for dev 200x200, default level for packaging 2000
(done) Disable wind by default
(done) Update the production build level to be the 1000x1000

Remove hard coded constants in the node trees, implement auto node placement
In monster tuning tab, add various parameters around the wendiego behavior so that they can be changed through the menu. 


Afternoon:

(done) 1. Add item highlighting when they are on the ground (configable in the world menu as on/off). Implement a glimmer if there is an item on the floor.
(done) 2. Improve the item icon generation processor to make the items look more realistic and add a thin black contour around the item models.
(done) 3. If a player runs too far away from his original location, the wendiego should go into charge directly at the player state.
(done) 4. Disable scroll wheel in menu. Allow vertical drag for vertical scrollbar.
(done) 6. Dragging items whe i is selected, should hold the item attached to the mouse cursor as its moved to the destination. Dropping it outside of the inventory area shoudl resolved in dropping the item on the floor. When the mouse is moving in the drag item state, it should not rotate the screen.   
Remove food / H2O / Temperature labels (as we already have icons). Update the food label as a chicken leg icon rather than mushroom. 
(done) 7. Instead of NPCs killed, updated to "Monster Kills"
(done) 8. Wendiegos should not make sound when they are patrolling. 
(done) 9. When looting a weapon, if there is an open weapon slot for it, it should prioritize going there before the inventory. When retrieving a melee weapon from a stuck state (I.E NPC or a tree), if the hands are empty, the weapon should go into the hand slot. Reduce footsteps volume, add a sounds menu where volume for each sound is tunable.
(done) 10. In the published build, when the game launches, the menu is not clickable until alt tabbing and tabbing back into the game or first pressing a keyboard button. In the menus escape button should navigate backwards (equivalent to back) Rename Settings in main menu to "Controls". If there is a saved state, rather than new game the main menu should say continue game.
(done) 11. Reticle turns red sometimes. Always keep the reticle white. If there is a headshot, show an X around the reticle. 
(done) 12. Q button should navigate through inventory items, not through guns


Next:

(done) Item shine is too bright, make it appear subtly when the character is near the items. Slightly glimer that appears and disapperas.

(done) Wendiego should roar when transitioning state from hunting to charging. (Just the sound here, no animation - to avoid the delay in attacking)
Pistol ADS is too close to the pistol. Should show hands partially with the pistol

(not done) The mouse bug is not resolved when the game starts. It seems when the game starts the mouse is not within the game window. After alt tabbing and alt tabbing back in the mouse issue gets resolved. 

(done) The transparent weapon slots icons on the items UI have actual weapon images which is not intended. Update them to be drawn icons of those weapon types, rather than based on the actual weapon appearence. I.E similar to how food / water / temperature are generated.

(done) Update Headshot multiplier to be 1.75 across the board




Sound feedback: 

(done) wind sound loud, don't really like it. Disable wind layer by default for now. Need to find another audio.
(done) Gun shot sounds greately regressed, the ones we had before were better
(done) Knife throw sound missing / Knife / axe landing in wood missing
(done) Chopping has a swing sound, dont need swing, just hit
(done) zombie contact no sound
(done) axe throw headshot no sound

(Done) High Quality Sound


(Done) Task1: Sounds refactor:
Refactor sound so that sound mappings can be tuned without needing to rebuild other modules (Unless new sound areas are added). All sound definitions and logic should all be in one place, with modules for the area of sound that they are responsible for.

I.E sound top level module, with sound_weapons, sound_monsters, sound_items, sound_world modules where the mappings and implementations of the sound logic is defined. 


(Done) Task2: Monster sounds:
Zombie growl 1, 2, 4 can be used during attack. Zombie growl 10 can be used when zombie agros. All other zombie growls should be played intermittently while the zombie is patrolling. Just like wendiego, allow zombie sounds to be heard from farther away. Especially the agro sound. RIght now they are often agroing but you can't hear them agro. 
Add footstep sounds for zombies and wendiego that are audible close by, don't hear them running up right now. Make footstep sound concept generic that can be used for all NPCs and players.


(Done) Task 3: World / player sounds:
Wire moving through tall grass sounds when a player or NPC walks through a bush. (world_sound module)
Wire breath_fast_01 when the energy is at 0 but the player attempts the run button. Wire heartbeat_panic to be played when on low life
Wire Jo-mungus as food eating sound
Axe / knife impact sounds are too gory, need differnt slicing ones.  Use the stab sound for now. For headshot axe thrown kills, use gore_weapon sound 1.9second version.
AKM is still too quiet even at 2 setting. Improve volume settings to allow going beyond 2 for volume. 
Play item sounds that are associated with the item type when moving items in the inventory, moving them into hand positions, or switching weapons. (Play approporiate sound when pulling out weapon or moving items within the inventory)

