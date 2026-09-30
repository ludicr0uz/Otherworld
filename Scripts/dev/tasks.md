# dev-team queue
Run: `Scripts/dev/dev-team` (this file is its default queue)
- [x] Implement mushrooms to heal 10 health when consumed (when the game is on easy setting).
      Implement game settings (easy / medium / survivor). Default to easy. Don't make any
      adjustments to other settings yet.
- [x] Add a save and exit option to the game menu (m). When save and exit is selected, the game
      should exit to main menu after 15 seconds, backing up stats and inventory equipment. Location
      should not be stored. Being hit during these 15 seconds interrupts the exit process. When
      starting/entering a game, the game should always load to the saved profile if there is one.
      If the character dies, the saved profile should clear (you lose your character progress on
      death).
- [x] Move the stamina bars to the center bottom of the screen, below the item list. Make the
      item list icons about 30% smaller.
- [x] Migrate from Canvas-based UI to UMG. The current HUD draws everything with DrawText/DrawRect/
      DrawTexture on a canvas, requiring manual positioning. Rebuild the main menu, pause menu, HUD
      (health/stamina/hunger/thirst/temperature bars, inventory grid, reticle, kill counter), and
      death menu using UMG Widgets. This enables responsive scaling, easier dialog/animation support,
      and faster iteration on UI changes. Keep the reticle and scope overlay as custom renders if
      performance requires it, but move all static layouts and stat bars to UMG.
- [ ] Make the pistol reload every 8 shots, with infinite reloads: an 8-round magazine and an
      unlimited reserve. It is still the fallback weapon, so it can never run dry for good.
- [ ] Implement daytime and nighttime, with the sun and moon rotating across the sky. The sun is
      up during the day and the moon at night. At night, stars come out and the light is dim.
      Create new world config settings, and make the day and night durations configurable
      there. For now for testing, set total day to be 4 minutes, and total night to be 4 minutes.
- [ ] Rework the stat bars on the HUD:
      - Move the health bar to the centre bottom of the screen, next to stamina and below the
        item list.
      - Move the temperature and food bars (and the other survival bars) to the bottom left
        corner, and make them vertical.
      - Add an icon beside each bar, and make each bar flash when it is low.
      - The item list icons should be about 30% smaller. An earlier task may already have done
        this; if so, leave them as they are and don't shrink them again.
- [ ] When an item or weapon is picked up, add it to the inventory without switching to it.
      Whatever item or weapon is active stays active.
- [ ] Integrate the new gun models that fit into the project to replace current gun models. Use
      AK 47 for rifle, Use AS Val for sniper rifle. Pistol is missing for now, that's ok - don't
      integrate yet.
      fab: FPS Weapon Bundle | url: https://www.fab.com/listings/8aeb9c48-b404-4dcd-9e56-1d0ecedba7f5 | at: /Game/FPS_Weapon_Bundle | why: real rifle and sniper models
      The new models are the FPS Weapon Bundle (Deadghost Interactive, free on Fab), already
      imported at /Game/FPS_Weapon_Bundle (Content/FPS_Weapon_Bundle, not committed; recorded in
      Scripts/asset_pipeline/fab_library.json). assets/cache/fab/index.md and index.json list
      every asset in it. Weapons are skeletal meshes under /Game/FPS_Weapon_Bundle/Weapons/Meshes/,
      each with an _X/_Y texture variant:
      - AK 47: Ka47/SK_KA47 (8 bones, 6.8k tris)
      - AS Val: KA_Val/SK_KA_Val_X or _Y (12 bones, 9k tris)
      - also in the pack, not asked for: AR4 (M4), KA74U, SMG11, M9_Knife, G67_Grenade
      - attachments (static meshes, Accessories/): SM_Scope_25x56_X/_Y, SM_T4_Sight,
        SM_Suppressor5, SM_Vertgrip
      Materials are under Weapons/Materials/, and Maps/Weapons_Showcase shows them all.
