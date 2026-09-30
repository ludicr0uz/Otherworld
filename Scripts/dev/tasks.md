# dev-team queue
Run: `Scripts/dev/dev-team` (this file is its default queue)
- [x] Implement mushrooms to heal 10 health when consumed (when the game is on easy setting).
      Implement game settings (easy / medium / survivor). Default to easy. Don't make any
      adjustments to other settings yet.
- [ ] Add a save and exit option to the game menu (m). When save and exit is selected, the game
      should exit to main menu after 15 seconds, backing up stats and inventory equipment. Location
      should not be stored. Being hit during these 15 seconds interrupts the exit process. When
      starting/entering a game, the game should always load to the saved profile if there is one.
      If the character dies, the saved profile should clear (you lose your character progress on
      death).
